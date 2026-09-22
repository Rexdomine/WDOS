from io import StringIO

from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from .models import Role


class FoundationTests(TestCase):
    def test_health_reports_database_and_environment(self):
        response = self.client.get(reverse("health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")
        self.assertEqual(response.json()["database"], "ok")

    def test_api_health_alias(self):
        response = self.client.get(reverse("api-health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["service"], "wdos")

    def test_app_shell_renders_django_brand_and_tokens(self):
        response = self.client.get(reverse("app-shell"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "WODDI DIGITAL OPERATING SYSTEM")
        self.assertContains(response, "/static/foundation/tokens.css")
        css = Path(settings.BASE_DIR / "foundation/static/foundation/tokens.css").read_text()
        self.assertIn("--wdos-magenta: #D4006A", css)

    def test_seed_command_is_idempotent(self):
        call_command("seed_roles", stdout=StringIO())
        call_command("seed_roles", stdout=StringIO())
        self.assertEqual(Role.objects.count(), 3)
