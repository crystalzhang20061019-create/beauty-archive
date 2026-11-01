from django.core.management.base import BaseCommand

from .cloud_migration import stage_fixture


class Command(BaseCommand):
    help = "Place a private migration fixture in Supabase Storage for Render to import."

    def handle(self, *args, **options):
        stage_fixture(self.stdout)
