"""
Seed standard CountryHubs, LeadershipLevels, and initial shell data for WDOS Stage 4.
Idempotent command safe for local development, testing, and staging bootstrap.
"""
from django.core.management.base import BaseCommand
from foundation.models import CountryHub, LeadershipLevel


COUNTRY_HUBS = [
    ("NG", "Nigeria", "West Africa", "active", "Dr. Aisha Bello", "aisha.bello@example.org"),
    ("GH", "Ghana", "West Africa", "active", "Grace Mensah", "grace.mensah@example.org"),
    ("KE", "Kenya", "East Africa", "active", "Wanjiru Kariuki", "wanjiru.kariuki@example.org"),
    ("ZA", "South Africa", "Southern Africa", "active", "Nandi Khumalo", "nandi.khumalo@example.org"),
    ("RW", "Rwanda", "East Africa", "active", "Aline Uwase", "aline.uwase@example.org"),
]

LEADERSHIP_LEVELS = [
    ("global_executive", "Global Executive", 1, "Global leadership and oversight across all WDOS networks"),
    ("it_admin", "IT Administrator", 1, "Technical governance, security, and access administration"),
    ("regional_coordinator", "Regional Coordinator", 2, "Zonal and regional coordination across country hubs"),
    ("country_director", "Country Director", 3, "Country hub director and principal operations lead"),
    ("chapter_lead", "Chapter Lead", 4, "Local chapter leadership and community mobilization"),
    ("reviewer", "Onboarding Reviewer", 4, "Application assessment, verification, and member review"),
    ("member", "Individual Member", 5, "Community member participating in network programs and activities"),
]


class Command(BaseCommand):
    help = "Seed standard Stage 4 CountryHubs and LeadershipLevels idempotently."

    def handle(self, *args, **options):
        # Seed Country Hubs
        for code, name, region, status, lead_name, lead_email in COUNTRY_HUBS:
            hub, created = CountryHub.objects.get_or_create(
                code=code,
                defaults={
                    "name": name,
                    "region": region,
                    "status": status,
                    "lead_name": lead_name,
                    "lead_email": lead_email,
                },
            )
            self.stdout.write(f"CountryHub {code}: {'created' if created else 'present'}")

        # Seed Leadership Levels
        for code, name, tier, description in LEADERSHIP_LEVELS:
            lvl, created = LeadershipLevel.objects.get_or_create(
                code=code,
                defaults={"name": name, "tier": tier, "description": description},
            )
            self.stdout.write(f"LeadershipLevel {code}: {'created' if created else 'present'}")

        self.stdout.write(self.style.SUCCESS("Stage 4 shell baseline seeded successfully."))
