from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand

from .cloud_migration import supabase_storage


class Command(BaseCommand):
    help = "Copy local product photos into the configured private Supabase Storage bucket."

    def handle(self, *args, **options):
        source = Path(settings.MEDIA_ROOT)
        if not source.exists():
            self.stdout.write("No local media directory found; nothing to copy.")
            return
        storage = supabase_storage()
        files = [path for path in source.rglob("*") if path.is_file()]
        copied = 0
        for path in files:
            key = path.relative_to(source).as_posix()
            if storage.exists(key):
                continue
            with path.open("rb") as stream:
                storage.save(key, File(stream, name=key))
            copied += 1
            self.stdout.write(f"Copied {copied} of {len(files)} new files.")
        self.stdout.write(self.style.SUCCESS(f"Photo migration complete: {len(files)} files checked."))
