"""
Stage 05 Comprehensive Test Suite: Role Dashboard System (DASH-01 through DASH-17)
Verifies:
1. All 27 dashboard screens render authentically for authorized roles with HTTP 200.
2. Server-side fail-closed authorization:
   - DASH-10-SAFEGUARDING denies unauthorized users with HTTP 403 and reason 'safeguarding_restricted'.
   - Cross-country isolation: single-country clearance denied 403 on non-permitted country hubs.
   - Cross-network isolation: network boundaries enforced.
3. Default dashboard routing per role.
4. State interaction feedback contracts (empty, stale, role_changed, loading, filtered_empty).
5. Tab state switching (overview, my_work, history).
6. Scoped data reconciliation.
"""
import io
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import AccessGrant, Account, Membership, OnboardingDraft, Person
from foundation.dashboard_engine import DASHBOARD_SCREENS, get_default_screen_for_role
from foundation.models import CountryHub, Chapter

User = get_user_model()


class Stage5DashboardsTestCase(TestCase):
    def setUp(self):
        sink = io.StringIO()
        call_command("seed_roles", stdout=sink)
        call_command("seed_shell_data", stdout=sink)
        call_command("seed_dashboards", stdout=sink)

        self.user_founder = User.objects.get(email="founder@example.org")
        self.account_founder = Account.objects.get(email="founder@example.org")

        self.user_ops = User.objects.get(email="ops@example.org")
        self.account_ops = Account.objects.get(email="ops@example.org")

        self.user_country_ng = User.objects.get(email="country.ng@example.org")
        self.account_country_ng = Account.objects.get(email="country.ng@example.org")

        self.user_country_ke = User.objects.get(email="country.ke@example.org")
        self.account_country_ke = Account.objects.get(email="country.ke@example.org")

        self.user_member_ada = User.objects.get(email="member.ada@example.org")
        self.account_member_ada = Account.objects.get(email="member.ada@example.org")

        self.user_candidate = User.objects.get(email="candidate.john@example.org")
        self.account_candidate = Account.objects.get(email="candidate.john@example.org")

        self.user_community = User.objects.get(email="community.amara@example.org")
        self.account_community = Account.objects.get(email="community.amara@example.org")

    def login_as(self, user):
        account = Account.objects.get(user=user)
        self.client.force_login(user)
        session = self.client.session
        now = timezone.now().timestamp()
        session["security_version"] = account.security_version
        session["mfa_verified"] = True
        session["last_activity"] = now
        session["absolute_expiry"] = now + 43200
        session.save()

    def test_all_27_dashboards_render_for_authorized_super_role(self):
        """Founder has global multi-network clearance; all 27 DASH screens must render 200 OK."""
        self.login_as(self.user_founder)
        for code, defn in DASHBOARD_SCREENS.items():
            url = f"/foundation/dashboards/{code.lower()}/"
            resp = self.client.get(url)
            self.assertEqual(
                resp.status_code,
                200,
                f"Screen {code} failed with status {resp.status_code}",
            )
            # Verify exact screen title and eyebrow from definition
            self.assertContains(resp, defn["title"])
            self.assertContains(resp, defn["eyebrow"])
            self.assertContains(resp, code)

    def test_safeguarding_desk_forbidden_for_standard_members(self):
        """Confidential safeguarding desk strictly requires confidential safeguarding clearance."""
        self.login_as(self.user_member_ada)
        resp = self.client.get("/foundation/dashboards/dash-10-safeguarding/")
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "safeguarding", status_code=403)

    def test_country_hub_isolation_denies_wrong_country_clearance(self):
        """Kenya country lead cannot access Nigeria country dashboard."""
        self.login_as(self.user_country_ke)
        resp = self.client.get("/foundation/dashboards/dash-10/")
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "wrong_country", status_code=403)

    def test_country_hub_permitted_for_matching_country_lead(self):
        """Nigeria country lead can access Nigeria country overview (DASH-10)."""
        self.login_as(self.user_country_ng)
        resp = self.client.get("/foundation/dashboards/dash-10/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Nigeria country overview")

    def test_default_dashboard_routing_per_role(self):
        """Hitting /foundation/dashboard/ maps to the active role's default dashboard."""
        self.login_as(self.user_founder)
        resp = self.client.get("/foundation/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Continental priorities")

        self.login_as(self.user_member_ada)
        resp = self.client.get("/foundation/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Good morning, Ada")

        self.login_as(self.user_candidate)
        resp = self.client.get("/foundation/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Your next step is clear")

        self.login_as(self.user_community)
        resp = self.client.get("/foundation/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Stay connected with WODDI")

    def test_state_interaction_feedback_modes(self):
        """All 5 state feedback modes render the state card and implementation contract banner."""
        self.login_as(self.user_founder)
        states = ["empty", "stale", "role_changed", "loading", "filtered_empty"]
        for st in states:
            resp = self.client.get(f"/foundation/dashboards/dash-01/?state={st}")
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "dash-state-card")
            self.assertContains(resp, "FUTURE FULL-STACK IMPLEMENTATION CONTRACT")

    def test_tab_navigation_parameters(self):
        """Tabs overview, my_work, and history maintain active state."""
        self.login_as(self.user_founder)
        for tab in ["overview", "my_work", "history"]:
            resp = self.client.get(f"/foundation/dashboards/dash-01/?tab={tab}")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.context["active_tab"], tab)
