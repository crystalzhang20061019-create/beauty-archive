"""Private Supabase Storage helpers for one-time production migration."""
import json
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError


STAGING_KEY = "private-migrations/archive-data.json"


def supabase_storage():
    if not getattr(settings, "USE_SUPABASE_STORAGE", False):
        raise CommandError("Set USE_SUPABASE_STORAGE=1 and configure the Supabase S3 credentials first.")
    from storages.backends.s3 import S3Storage

    return S3Storage()


def stage_fixture(stdout):
    from django.core.files import File
    from django.core.management import call_command

    storage = supabase_storage()
    with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", suffix=".json") as fixture:
        call_command("dumpdata", "archive", natural_foreign=True, natural_primary=True, indent=2, stdout=fixture)
        fixture.flush()
        fixture.seek(0)
        records = json.load(fixture)
        usernames = sorted({str(obj.get("fields", {}).get("user")) for obj in records
                            if obj.get("model") == "archive.usersettings" and obj.get("fields", {}).get("user")})
        if len(usernames) != 1:
            raise CommandError(f"Expected one archive owner in the fixture; found {len(usernames)}.")
        # Keep only an unusable-password cloud owner; never copy the local password hash.
        records.insert(0, {"model": "archive.migrationowner", "pk": None, "fields": {"username": usernames[0]}})
        fixture.seek(0)
        fixture.truncate()
        json.dump(records, fixture, ensure_ascii=False, indent=2)
        fixture.flush()
        fixture.seek(0)
        if storage.exists(STAGING_KEY):
            storage.delete(STAGING_KEY)
        storage.save(STAGING_KEY, File(fixture, name="archive-data.json"))
    stdout.write("Private migration fixture staged in Supabase Storage. Local password was excluded.\n")


def import_fixture(stdout):
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from django.db import transaction

    storage = supabase_storage()
    if not storage.exists(STAGING_KEY):
        raise CommandError("No private migration fixture was found in Supabase Storage.")
    with storage.open(STAGING_KEY, "rb") as source, tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", suffix=".json") as fixture:
        records = json.load(source)
        owner_records = [obj for obj in records if obj.get("model") == "archive.migrationowner"]
        if len(owner_records) != 1:
            raise CommandError("The staged fixture does not contain exactly one archive owner.")
        username = owner_records[0]["fields"]["username"]
        user_model = get_user_model()
        with transaction.atomic():
            owner, created = user_model.objects.get_or_create(
                username=username,
                defaults={"is_active": True, "is_staff": True, "is_superuser": True},
            )
            if created:
                owner.set_unusable_password()
                owner.save(update_fields=["password"])
            elif not owner.is_superuser:
                raise CommandError("The archive username already exists but is not an administrator; refusing to change it.")
            records = [obj for obj in records if obj.get("model") != "archive.migrationowner"]
            json.dump(records, fixture, ensure_ascii=False)
            fixture.flush()
            call_command("loaddata", fixture.name, verbosity=1)
    stdout.write(f"Archive data imported for {username}.\n")
    if created:
        stdout.write("The cloud account has no usable password yet; create one before signing in.\n")
