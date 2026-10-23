from django.core.management.base import BaseCommand
from django.core.management import call_command
from foundation.leadership_engine import seed_stage7_fixtures


class Command(BaseCommand):
    help = "Seed Stage 07 Leadership, Vacancies, Appointments, and Handover data and personas"

    def handle(self, *args, **options):
        call_command("seed_stage6_data")
        seed_stage7_fixtures()
        self.stdout.write(self.style.SUCCESS("Stage 07 leadership and appointments fixtures seeded successfully."))
