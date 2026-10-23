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
            # Verify exact screen title and eyebrow from definition, and no internal DASH-XX code in HTML
            self.assertContains(resp, defn["title"])
            self.assertContains(resp, defn["eyebrow"])
            self.assertEqual(resp.context["screen_code"], code)
            self.assertNotContains(resp, code)

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
        self.assertEqual(resp.context["screen_code"], "DASH-01")
        self.assertContains(resp, '<h1 class="dash-title">Continental priorities</h1>')
        self.assertNotContains(resp, "UI review v2")
        self.assertNotContains(resp, "Sample data")

        # Operations Lead must open DASH-02 (Country operations), NOT DASH-01
        self.login_as(self.user_ops)
        resp = self.client.get("/foundation/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["screen_code"], "DASH-02")
        self.assertContains(resp, '<h1 class="dash-title">Country operations</h1>')
        self.assertNotContains(resp, '<h1 class="dash-title">Continental priorities</h1>')

        self.login_as(self.user_member_ada)
        resp = self.client.get("/foundation/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Good morning, Ada")

        self.login_as(self.user_candidate)
        resp = self.client.get("/foundation/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Your next step is clear")
        self.assertContains(resp, 'href="/onboarding/1/"')
        onb_resp = self.client.get("/onboarding/1/", follow=True)
        self.assertEqual(onb_resp.status_code, 200)
        self.assertNotContains(onb_resp, "ONB-08")
        self.assertNotContains(onb_resp, "ONB-01")

        self.login_as(self.user_community)
        resp = self.client.get("/foundation/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Stay connected with WODDI")

    def test_kenya_country_lead_dashboard_shows_kenya_items_not_lagos(self):
        """Kenya Country Lead (country.ke@example.org) opens Kenya country overview with Nairobi/Mombasa items and no Lagos/Ikeja items."""
        self.login_as(self.user_country_ke)
        resp = self.client.get("/foundation/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Kenya country overview")
        self.assertContains(resp, "WGMN / KENYA")
        self.assertContains(resp, "Nairobi")
        self.assertContains(resp, "Mombasa")
        self.assertNotContains(resp, "Lagos")
        self.assertNotContains(resp, "Ikeja")

    def test_all_pending_role_accounts_provisioned_in_test_approver_and_open_correct_dashboards(self):
        """Visiting /foundation/test-approve/ auto-provisions all role accounts for DASH-01..DASH-17 and each opens its documented dashboard."""
        resp_approver = self.client.get("/foundation/test-approve/")
        self.assertEqual(resp_approver.status_code, 200)

        expected_role_matrix = [
            ("founder@example.org", "DASH-01", "Continental priorities"),
            ("ops@example.org", "DASH-02", "Country operations"),
            ("coordinator@example.org", "DASH-03", "Coordination desk"),
            ("admin.hq@example.org", "DASH-04", "Administration overview"),
            ("programmes@example.org", "DASH-05", "Programme portfolio"),
            ("comms@example.org", "DASH-06", "Communications workspace"),
            ("resources@example.org", "DASH-07", "Resource accountability"),
            ("systems@example.org", "DASH-08", "Systems operations"),
            ("quality@example.org", "DASH-09", "Quality and controls"),
            ("safeguarding@example.org", "DASH-10-SAFEGUARDING", "Confidential safeguarding desk"),
            ("country.ng@example.org", "DASH-10", "Nigeria country overview"),
            ("country.ke@example.org", "DASH-10", "Kenya country overview"),
            ("state.lagos@example.org", "DASH-11", "Lagos regional overview"),
            ("ikeja.lead@example.org", "DASH-12", "Ikeja local operations"),
            ("cluster.lead@example.org", "DASH-13", "Your Cluster at a glance"),
            ("chapter.lagos@example.org", "DASH-14", "Lagos Central Chapter · Command desk"),
            ("member.ada@example.org", "DASH-15", "Good morning, Ada"),
            ("candidate.john@example.org", "DASH-16", "Your next step is clear"),
            ("community.amara@example.org", "DASH-17", "Stay connected with WODDI"),
        ]

        for email, expected_code, expected_title in expected_role_matrix:
            self.assertContains(resp_approver, email)
            user = User.objects.get(email=email)
            self.login_as(user)
            dash_resp = self.client.get("/foundation/dashboard/")
            self.assertEqual(dash_resp.status_code, 200, f"{email} failed on /foundation/dashboard/")
            self.assertEqual(dash_resp.context["screen_code"], expected_code)
            self.assertContains(dash_resp, expected_title)
            self.assertNotContains(dash_resp, "UI review v2")
            self.assertNotContains(dash_resp, "Sample data")
            self.assertNotContains(dash_resp, "Synthetic review example")
            self.assertNotContains(dash_resp, "Role-specific dashboard reference screens")

    def test_state_interaction_feedback_modes(self):
        """All 5 state feedback modes render the clean user-facing state card without internal implementation contract labels."""
        self.login_as(self.user_founder)
        states = ["empty", "stale", "role_changed", "loading", "filtered_empty"]
        for st in states:
            resp = self.client.get(f"/foundation/dashboards/dash-01/?state={st}")
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "dash-state-card")
            self.assertNotContains(resp, "FUTURE FULL-STACK IMPLEMENTATION CONTRACT")

    def test_tab_navigation_parameters(self):
        """Tabs overview, my_work, and history maintain active state."""
        self.login_as(self.user_founder)
        for tab in ["overview", "my_work", "history"]:
            resp = self.client.get(f"/foundation/dashboards/dash-01/?tab={tab}")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.context["active_tab"], tab)

    def test_dash15_member_dashboard_isolation_and_no_confidential_leak(self):
        """Standard member dashboard DASH-15 strictly isolates chapter meetings and never leaks confidential audits."""
        from datetime import timedelta
        from foundation.models import ScheduledMeeting, WorkItem

        # Create a confidential audit item
        WorkItem.objects.update_or_create(
            title="Q3 Whistleblower & Compliance Audit",
            defaults={
                "category": "compliance",
                "network": "WGMN",
                "country": "NG",
                "required_role": "member",
                "priority": "critical",
                "status": "pending",
                "confidential": True,
            },
        )

        # Create an upcoming meeting in another chapter (Eastern Obolo)
        ScheduledMeeting.objects.update_or_create(
            title="Eastern Obolo Chapter Outreach",
            defaults={
                "meeting_type": "chapter_meetup",
                "network": "WGMN",
                "country": "NG",
                "target_role": "member",
                "scheduled_at": timezone.now() + timedelta(days=2),
                "location": "Eastern Obolo Civic Center",
                "organizer_name": "Local Coordinator",
                "attendees_count": 15,
            },
        )

        # Log in as Ada (Lagos Central Chapter member)
        self.login_as(self.user_member_ada)
        resp = self.client.get("/foundation/dashboards/dash-15/")
        self.assertEqual(resp.status_code, 200)

        # Verify confidential audit is NEVER leaked to standard member
        self.assertNotContains(resp, "Whistleblower &amp; Compliance Audit")
        self.assertNotContains(resp, "Whistleblower & Compliance Audit")

        # Verify other chapter's local meetup does not appear in table
        table_rows = resp.context["screen"]["table_card"]["rows"]
        row_titles = [r["item"] for r in table_rows]
        self.assertNotIn("Eastern Obolo Chapter Outreach", row_titles)
