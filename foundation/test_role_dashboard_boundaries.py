"""
Comprehensive Test Suite: Role-Based Dashboard Mapping, Cross-Network Boundaries,
Geographic Isolation, and Leadership Access Controls.

Verifies the 16 October Review & Specification Requirements:
1. Every approved role opens its exact intended dashboard (DASH-01 through DASH-17) at /foundation/dashboard/.
2. WGMN users cannot access WNN dashboards, records, or profiles (HTTP 403 network_mismatch / wrong_network).
3. WNN users cannot access WGMN dashboards, records, or profiles (HTTP 403 network_mismatch / wrong_network).
4. Direct URL parameter tampering (?network=..., ?country=...) is rejected server-side with HTTP 403.
5. Country and geographic boundaries: Kenya Country Lead denied Nigeria country/state/chapter dashboards (HTTP 403 wrong_country).
6. Leadership access control: Ordinary members, candidates, and community users are strictly denied:
   - Leadership dashboards (DASH-01 through DASH-14, DASH-10-* sub-screens) (HTTP 403 leadership_restricted).
   - Leadership-only work items and actions (claim/complete) (HTTP 403 leadership_restricted).
   - Leadership reports and report drilldown (HTTP 403 leadership_restricted).
   - Leadership alerts drilldown and member rosters (HTTP 403 leadership_restricted).
   - Leadership exports (HTTP 403 leadership_restricted).
   - Leadership profiles (HTTP 403 leadership_restricted).
7. Candidate cannot access member dashboard (DASH-15).
8. Community cannot access member (DASH-15) or candidate (DASH-16) dashboards.
9. Authorized Founder overview can view both networks and reconciles continental data.
10. Dashboard table totals and record count text reconcile to visible records within permitted scope.
"""
import io
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import AccessGrant, Account, Membership, OnboardingDraft, Person
from foundation.dashboard_engine import DASHBOARD_SCREENS, get_default_screen_for_role
from foundation.models import Chapter, CountryHub, DashboardAlert, DashboardReport, LeadershipLevel, WorkItem

User = get_user_model()


class RoleDashboardBoundariesTestCase(TestCase):
    def setUp(self):
        sink = io.StringIO()
        call_command("seed_roles", stdout=sink)
        call_command("seed_shell_data", stdout=sink)
        call_command("seed_dashboards", stdout=sink)
        call_command("seed_test_accounts", stdout=sink)

        self.user_founder = User.objects.get(email="founder@example.org")
        self.account_founder = Account.objects.get(email="founder@example.org")

        self.user_ops = User.objects.get(email="ops@example.org")
        self.account_ops = Account.objects.get(email="ops@example.org")

        self.user_country_ng = User.objects.get(email="country.ng@example.org")
        self.account_country_ng = Account.objects.get(email="country.ng@example.org")

        self.user_country_ke = User.objects.get(email="country.ke@example.org")
        self.account_country_ke = Account.objects.get(email="country.ke@example.org")

        self.user_state_lagos = User.objects.get(email="state.lagos@example.org")
        self.account_state_lagos = Account.objects.get(email="state.lagos@example.org")

        self.user_chapter_lagos = User.objects.get(email="chapter.lagos@example.org")
        self.account_chapter_lagos = Account.objects.get(email="chapter.lagos@example.org")

        self.user_member_ada = User.objects.get(email="member.ada@example.org")
        self.account_member_ada = Account.objects.get(email="member.ada@example.org")

        # WNNN Member
        self.user_member_wnnn = User.objects.get(email="wnnn.member@example.org")
        self.account_member_wnnn = Account.objects.get(email="wnnn.member@example.org")

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

    # =========================================================================
    # 1. Role-to-Dashboard Mapping Verification (Criterion 1)
    # =========================================================================
    def test_all_17_approved_roles_open_intended_dashboards(self):
        """Every approved role hits /foundation/dashboard/ and opens its intended dashboard."""
        role_expectations = [
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
        for email, expected_code, expected_title in role_expectations:
            user = User.objects.get(email=email)
            self.login_as(user)
            resp = self.client.get("/foundation/dashboard/")
            self.assertEqual(resp.status_code, 200, f"Role {email} failed on /foundation/dashboard/")
            self.assertEqual(resp.context["screen_code"], expected_code)
            self.assertContains(resp, expected_title)

    # =========================================================================
    # 2. Cross-Network Separation: WGMN vs WNN/WNNN (Criterion 2)
    # =========================================================================
    def test_wgmn_user_denied_wnn_screen_and_data(self):
        """WGMN Chapter Lead cannot access WNN screens or query parameters."""
        self.login_as(self.user_chapter_lagos)
        # Attempt to access with ?network=WNN
        resp = self.client.get("/foundation/dashboard/?network=WNN")
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "wrong_network", status_code=403)

        # Attempt to access with ?network=WNNN
        resp = self.client.get("/foundation/dashboard/?network=WNNN")
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "wrong_network", status_code=403)

    def test_wnn_user_denied_wgmn_screen_and_data(self):
        """WNN user cannot access WGMN screens or network query parameters."""
        self.login_as(self.user_member_wnnn)
        # Attempt to access with ?network=WGMN
        resp = self.client.get("/foundation/dashboard/?network=WGMN")
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "wrong_network", status_code=403)

    def test_wgmn_user_cannot_view_wnn_profile(self):
        """WGMN member cannot view WNN member's profile."""
        self.login_as(self.user_member_ada)
        url = f"/foundation/network/WNNN/country/GH/leadership/member/profile/{self.account_member_wnnn.person.id}/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_wnn_user_cannot_view_wgmn_profile(self):
        """WNN member cannot view WGMN member's profile."""
        self.login_as(self.user_member_wnnn)
        url = f"/foundation/network/WGMN/country/NG/leadership/member/profile/{self.account_member_ada.person.id}/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)

    def test_shared_screens_filter_rows_by_user_network(self):
        """DASH-02 or DASH-03 dynamically filters out rows mentioning the other network for non-founder leaders."""
        # Provision a WGMN-scoped Operations reviewer
        user_wgmn_ops = User.objects.create_user(username="ops.wgmn", email="ops.wgmn@example.org")
        p_wgmn = Person.objects.create(display_name="WGMN Ops Lead")
        acc_wgmn_ops = Account.objects.create(user=user_wgmn_ops, email="ops.wgmn@example.org", display_name="WGMN Ops Lead", person=p_wgmn, status="active", verified_at=timezone.now())
        AccessGrant.objects.create(account=acc_wgmn_ops, role="operations", network="WGMN", geography="*", expires_at=timezone.now() + timezone.timedelta(days=30))

        self.login_as(user_wgmn_ops)
        resp = self.client.get("/foundation/dashboard/")
        self.assertEqual(resp.status_code, 200)
        # WGMN Ops user must see WGMN items, NOT WNNN items
        self.assertContains(resp, "WGMN")
        self.assertNotContains(resp, "WNNN · Kenya")
        self.assertContains(resp, "WGMN / NIGERIA")

    # =========================================================================
    # 3. Geographic Boundaries (Criterion 3)
    # =========================================================================
    def test_country_lead_denied_other_country_explicit_screens(self):
        """Kenya Country Lead is denied Nigeria country and regional dashboards."""
        self.login_as(self.user_country_ke)
        # Explicit DASH-10 (Nigeria hub in registry)
        resp = self.client.get("/foundation/dashboards/dash-10/")
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "wrong_country", status_code=403)

        # Explicit DASH-11 (Lagos regional overview)
        resp = self.client.get("/foundation/dashboards/dash-11/")
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "wrong_country", status_code=403)

        # Tampering with ?country=NG on dashboard
        resp = self.client.get("/foundation/dashboard/?country=NG")
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "wrong_country", status_code=403)

    def test_chapter_lead_denied_other_chapter_records(self):
        """Lagos Central Chapter Lead cannot access records for an unrelated chapter or country."""
        self.login_as(self.user_chapter_lagos)
        # Attempt to access Kenya Country Hub
        resp = self.client.get("/foundation/network/WGMN/country/KE/")
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "wrong_country", status_code=403)

    # =========================================================================
    # 4. Leadership Access Restrictions (Criterion 4)
    # =========================================================================
    def test_ordinary_member_denied_all_leadership_dashboards(self):
        """Ordinary member (tier 5) cannot access leadership screens DASH-01 through DASH-14."""
        self.login_as(self.user_member_ada)
        leadership_screens = [
            "dash-01", "dash-02", "dash-03", "dash-04", "dash-05", "dash-06",
            "dash-07", "dash-08", "dash-09", "dash-10", "dash-10-safeguarding",
            "dash-10-coverage", "dash-11", "dash-12", "dash-13", "dash-14"
        ]
        for screen in leadership_screens:
            resp = self.client.get(f"/foundation/dashboards/{screen}/")
            self.assertEqual(resp.status_code, 403, f"Member was not denied access to {screen}")
            if "safeguarding" in screen:
                self.assertContains(resp, "safeguarding_restricted", status_code=403)
            else:
                self.assertContains(resp, "leadership_restricted", status_code=403)

    def test_ordinary_member_denied_leadership_profiles(self):
        """Ordinary member cannot view a leadership profile (e.g. Country Lead)."""
        self.login_as(self.user_member_ada)
        url = f"/foundation/network/WGMN/country/NG/leadership/country_lead/profile/{self.account_country_ng.person.id}/"
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "leadership_restricted", status_code=403)

    def test_ordinary_member_denied_leadership_work_items_and_actions(self):
        """Ordinary member cannot view or act upon leadership work items."""
        # Create a leadership-only work item
        leadership_lvl = LeadershipLevel.objects.get(code="country_director")
        item = WorkItem.objects.create(
            title="Appoint Deputy Country Lead",
            summary="Review candidates for Kenya deputy position.",
            category="governance",
            network="WGMN",
            country="NG",
            leadership_level=leadership_lvl,
            status="pending",
        )
        self.login_as(self.user_member_ada)

        # Deep link view denied
        resp = self.client.get(f"/foundation/work-queue/{item.id}/")
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "leadership_restricted", status_code=403)

        # Action POST denied
        resp_act = self.client.post(f"/foundation/work-queue/{item.id}/action/", {"action": "claim"})
        self.assertEqual(resp_act.status_code, 403)
        self.assertContains(resp_act, "leadership_restricted", status_code=403)

    def test_ordinary_member_denied_reports_and_drilldowns(self):
        """Ordinary member cannot access operational reports or leadership drilldowns."""
        self.login_as(self.user_member_ada)

        # Report detail denied
        rep = DashboardReport.objects.first()
        if rep:
            resp = self.client.get(f"/foundation/dashboard/reports/{rep.id}/")
            self.assertEqual(resp.status_code, 403)
            self.assertContains(resp, "leadership_restricted", status_code=403)

        # Reports drilldown denied
        resp_rep = self.client.get("/foundation/dashboard/drilldown/reports/")
        self.assertEqual(resp_rep.status_code, 403)
        self.assertContains(resp_rep, "leadership_restricted", status_code=403)

        # Alerts drilldown denied
        resp_alert = self.client.get("/foundation/dashboard/drilldown/alerts/")
        self.assertEqual(resp_alert.status_code, 403)
        self.assertContains(resp_alert, "leadership_restricted", status_code=403)

        # Member roster drilldown denied
        resp_mem = self.client.get("/foundation/dashboard/drilldown/members/")
        self.assertEqual(resp_mem.status_code, 403)
        self.assertContains(resp_mem, "unauthorized_drilldown", status_code=403)

    def test_ordinary_member_denied_leadership_exports(self):
        """Ordinary member cannot export leadership reports, chapters, or alerts."""
        self.login_as(self.user_member_ada)
        for exp in ("reports", "chapters", "alerts", "members"):
            resp = self.client.get(f"/foundation/dashboard/export/?type={exp}")
            self.assertEqual(resp.status_code, 403)
            self.assertContains(resp, "leadership_restricted", status_code=403)

    # =========================================================================
    # 5. Candidate and Community Boundary Restrictions (Criterion 4)
    # =========================================================================
    def test_candidate_cannot_access_member_dashboard(self):
        """Candidate (tier 6) cannot access member dashboard (DASH-15)."""
        self.login_as(self.user_candidate)
        resp = self.client.get("/foundation/dashboards/dash-15/")
        self.assertEqual(resp.status_code, 403)
        self.assertContains(resp, "unauthorized_role", status_code=403)

    def test_community_user_cannot_access_candidate_or_member_dashboard(self):
        """Community user (tier 7) cannot access member (DASH-15) or candidate (DASH-16) dashboard."""
        self.login_as(self.user_community)
        resp15 = self.client.get("/foundation/dashboards/dash-15/")
        self.assertEqual(resp15.status_code, 403)
        self.assertContains(resp15, "unauthorized_role", status_code=403)

        resp16 = self.client.get("/foundation/dashboards/dash-16/")
        self.assertEqual(resp16.status_code, 403)
        self.assertContains(resp16, "unauthorized_role", status_code=403)

    # =========================================================================
    # 6. Founder Dual-Network Authorization (Criterion 6)
    # =========================================================================
    def test_founder_overview_shows_both_networks(self):
        """Authorized Founder overview shows continental cross-network priorities."""
        self.login_as(self.user_founder)
        resp = self.client.get("/foundation/dashboard/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["screen_code"], "DASH-01")
        self.assertContains(resp, "Continental priorities")
        # Founder can see both WGMN and WNNN items in table
        self.assertContains(resp, "HQ / BOTH NETWORKS")

    # =========================================================================
    # 7. Record Count and Total Reconciliation (Criterion 7)
    # =========================================================================
    def test_table_card_record_count_reconciliation(self):
        """Dashboard table card record count text reconciles with the count of visible records."""
        self.login_as(self.user_ops)
        resp = self.client.get("/foundation/dashboard/")
        self.assertEqual(resp.status_code, 200)
        table_card = resp.context.get("table_card")
        if table_card and "rows" in table_card:
            expected_text = f"Showing {len(table_card['rows'])} records in this view"
            self.assertEqual(table_card["record_count_text"], expected_text)
