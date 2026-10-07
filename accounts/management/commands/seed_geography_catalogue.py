from django.core.management.base import BaseCommand
from accounts.geography_catalogue import import_catalogue_to_database


class Command(BaseCommand):
    help = "Seed the normalized WDOS geography catalogue into the database."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Importing WDOS administrative geography catalogue into database..."))
        stats = import_catalogue_to_database()
        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded catalogue:\n"
                f"  Countries: {stats['countries_created']} created, {stats['countries_updated']} updated\n"
                f"  Level 1 Divisions: {stats['level1_created']} created/updated\n"
                f"  Level 2 Divisions: {stats['level2_created']} created/updated"
            )
        )
