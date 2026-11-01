from django.core.management.base import BaseCommand

from .cloud_migration import import_fixture


class Command(BaseCommand):
    help = "Import the private staged archive fixture into the production database."

    def handle(self, *args, **options):
        import_fixture(self.stdout)
