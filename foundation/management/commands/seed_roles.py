from django.core.management.base import BaseCommand
from foundation.models import Role


ROLES = [
    ("management", "Management", "Oversight and approval role"),
    ("it_admin", "IT Administrator", "Platform administration role"),
    ("qa", "QA", "Quality assurance role"),
]


class Command(BaseCommand):
    help = "Create the immutable Stage 1 system role baseline idempotently."

    def handle(self, *args, **options):
        for code, name, description in ROLES:
            role, created = Role.objects.get_or_create(
                code=code,
                defaults={"name": name, "description": description, "is_system": True},
            )
            self.stdout.write(f"{code}: {'created' if created else 'present'}")
