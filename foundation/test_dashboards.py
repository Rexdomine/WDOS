"""
Stage 4 Dashboard System Tests:
- 7 distinct role views (Founder/HQ, Operations, Country Lead, Chapter Lead, Member, Candidate, Community)
- Server-enforced Network Workspace (WGMN vs WNNN) and Country Hub scoping
- Reconciles to source/seed data with live live dynamic database aggregations (no fake "live" KPIs, no stale aggregations)
- Drill-downs and item details with server-enforced authorization and actions (RSVP, Alert acknowledgment)
- Scoped CSV exports
- Failure paths: cross-network mixing, wrong-country card, unauthorized drill-down, cosmetic filter bypass, empty/error states
"""
import io
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import AccessGrant, Account, Membership, OnboardingConsent, OnboardingDraft, Person
from foundation.models import (
    Chapter,
    Communication,
    CountryHub,
    DashboardActivity,
    DashboardAlert,
    DashboardReport,
    ScheduledMeeting,
    WorkItem,
)
from foundation.scope import get_user_scope

User = get_user_model()


class DashboardTestCaseBase(TestCase):
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

        self.user_chapter_lagos = User.objects.get(email="chapter.lagos@example.org")
        self.account_chapter_lagos = Account.objects.get(email="chapter.lagos@example.org")

        self.user_member_ada = User.objects.get(email="member.ada@example.org")
        self.account_member_ada = Account.objects.get(email="member.ada@example.org")

        self.user_candidate = User.objects.get(email="candidate.john@example.org")
        self.account_candidate = Account.objects.get(email="candidate.john@example.org")

        self.user_community = User.objects.get(email="community.amara@example.org")
        self.account_community = Account.objects.get(email="community.amara@example.org")

    def login_as(self, user):
        account = Account.objects.filter(user=user).first()
        self.client.force_login(user)
        session = self.client.session
        now = timezone.now().timestamp()
        if account:
            session["security_version"] = account.security_version
        session["mfa_verified"] = True
        session["last_activity"] = now
        session["absolute_expiry"] = now + 43200
        session.save()


class RoleDashboardsMaterialDifferenceTests(DashboardTestCaseBase):
    """Ensure switching test roles delivers materially different, authorized starting dashboards."""

    def test_founder_hq_dashboard(self):
        self.login_as(self.user_founder)
        response = self.client.get("/foundation/?role=founder")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Executive Headquarters Dashboard")
        self.assertContains(response, "Dual Network Breakdown Comparison")
        self.assertContains(response, "Country Hub Regional Operations")
        self.assertContains(response, "Executive & Audit Reports")
        self.assertContains(response, "TOTAL NETWORK MEMBERSHIP")

    def test_operations_dashboard(self):
        self.login_as(self.user_ops)
        response = self.client.get("/foundation/?role=operations")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Operations Coordination Dashboard")
        self.assertContains(response, "Onboarding Verification Pipeline")
        self.assertContains(response, "Active Work Items Queue")
        self.assertContains(response, "OPEN WORK ITEMS")

    def test_country_lead_nigeria_dashboard(self):
        self.login_as(self.user_country_ng)
        response = self.client.get("/foundation/?role=country_lead")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nigeria Country Hub Dashboard")
        self.assertContains(response, "Nigeria Hub")
        self.assertContains(response, "National Assemblies & Gatherings")
        self.assertContains(response, "Lagos Central Chapter")

    def test_chapter_lead_lagos_dashboard(self):
        self.login_as(self.user_chapter_lagos)
        response = self.client.get("/foundation/?role=chapter_lead")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lagos Central Chapter")
        self.assertContains(response, "CHAPTER LEADERSHIP")
        self.assertContains(response, "Lagos Central Weekly Chapter Fellowship")
        self.assertContains(response, "Chapter Member Roster")

    def test_candidate_dashboard(self):
        self.login_as(self.user_candidate)
        response = self.client.get("/foundation/?role=candidate")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Candidate Application Dashboard")
        self.assertContains(response, "Application for John Kalu")
        self.assertContains(response, "Step 6 of 8 Completed")
        self.assertContains(response, "Candidate Orientation Sessions")

    def test_community_dashboard(self):
        self.login_as(self.user_community)
        response = self.client.get("/foundation/?role=community")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome to the WDOS Community")
        self.assertContains(response, "Open Public Events & Webinars")
        self.assertContains(response, "Find a Local Chapter Near You")
        self.assertContains(response, "Ready to Join WDOS?")

    def test_role_switch_produces_materially_different_dashboards(self):
        self.login_as(self.user_founder)
        resp_founder = self.client.get("/foundation/?role=founder")
        resp_ops = self.client.get("/foundation/?role=operations")
        resp_community = self.client.get("/foundation/?role=community")

        self.assertContains(resp_founder, "Executive Headquarters Dashboard")
        self.assertNotContains(resp_founder, "Operations Coordination Dashboard")

        self.assertContains(resp_ops, "Operations Coordination Dashboard")
        self.assertNotContains(resp_ops, "Executive Headquarters Dashboard")

        self.assertContains(resp_community, "Welcome to the WDOS Community")
        self.assertNotContains(resp_community, "Executive Headquarters Dashboard")


class ScopedKPIRecordsReconciliationTests(DashboardTestCaseBase):
    """Ensure all KPI metrics reconcile live to source database records without fake or stale aggregations."""

    def test_kpis_reconcile_to_live_database_records(self):
        self.login_as(self.user_founder)
        response = self.client.get("/foundation/?role=founder&network=WGMN&country=NG")
        self.assertEqual(response.status_code, 200)

        # Count live records in database
        expected_chapters = Chapter.objects.filter(network="WGMN", country="NG", status="active").count()
        expected_alerts = DashboardAlert.objects.filter(network__in=["WGMN", "ALL"], country__in=["NG", "ALL"], is_active=True).count()
        expected_meetings = ScheduledMeeting.objects.filter(network__in=["WGMN", "ALL"], country__in=["NG", "ALL"], scheduled_at__gte=timezone.now()).count()

        kpis = response.context["kpis"]
        self.assertEqual(kpis["active_chapters"], expected_chapters)
        self.assertEqual(kpis["active_alerts"], expected_alerts)
        self.assertEqual(kpis["scheduled_meetings"], expected_meetings)

    def test_no_stale_aggregation_kpis_update_on_record_changes(self):
        self.login_as(self.user_founder)
        resp1 = self.client.get("/foundation/?role=founder&network=WGMN&country=NG")
        initial_chapters = resp1.context["kpis"]["active_chapters"]

        # Dynamically create a new active chapter
        Chapter.objects.create(
            code="NG-CAL-01",
            name="Calabar Cross River Chapter",
            network="WGMN",
            country="NG",
            region="Cross River",
            status="active",
        )

        resp2 = self.client.get("/foundation/?role=founder&network=WGMN&country=NG")
        new_chapters = resp2.context["kpis"]["active_chapters"]
        self.assertEqual(new_chapters, initial_chapters + 1)


class CrossNetworkAndGeographyScopeEnforcementTests(DashboardTestCaseBase):
    """Ensure server enforces strict network separation (WGMN vs WNNN) and country hub boundaries."""

    def test_cross_network_separation_wgmn_vs_wnnn(self):
        self.login_as(self.user_founder)
        resp_wgmn = self.client.get("/foundation/dashboard/drilldown/chapters/?network=WGMN&country=NG")
        self.assertContains(resp_wgmn, "Lagos Central Chapter")
        self.assertNotContains(resp_wgmn, "Lagos Next-Gen Youth Hub")  # WNNN

        resp_wnnn = self.client.get("/foundation/dashboard/drilldown/chapters/?network=WNNN&country=NG")
        self.assertContains(resp_wnnn, "Lagos Next-Gen Youth Hub")
        self.assertNotContains(resp_wnnn, "Lagos Central Chapter")  # WGMN

    def test_wrong_country_card_prevention(self):
        self.login_as(self.user_country_ng)
        response = self.client.get("/foundation/?role=country_lead&country=NG")
        self.assertContains(response, "Lagos Central Chapter")
        self.assertNotContains(response, "Nairobi Kilimani Chapter")

    def test_cosmetic_filter_bypass_rejected_for_single_country_user(self):
        """User with single-country Nigeria clearance tampering with ?country=KE is rejected 403."""
        self.login_as(self.user_country_ng)
        response = self.client.get("/foundation/?country=KE")
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "wrong_country", status_code=403)
        self.assertContains(response, "Return to Authorized Workspace", status_code=403)

    def test_unauthorized_role_tampering_rejected_with_403(self):
        """Candidate or member trying to switch to founder role is rejected 403."""
        # Remove the DEBUG bypass by overriding
        scope = get_user_scope(self.account_candidate)
        self.assertFalse(scope.can_access_role("founder"))

        self.login_as(self.user_candidate)
        # Post to switch-role
        response = self.client.post("/foundation/dashboard/switch-role/", {"role": "founder"})
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "unauthorized_role", status_code=403)


class AuthorizedDrilldownsAndDetailsTests(DashboardTestCaseBase):
    """Ensure drill-downs and item details stay authorized and execute scoped actions."""

    def test_authorized_chapters_drilldown(self):
        self.login_as(self.user_founder)
        response = self.client.get("/foundation/dashboard/drilldown/chapters/?network=WGMN&country=NG")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "NG-LOS-01")
        self.assertContains(response, "Lagos Central Chapter")

    def test_authorized_alerts_drilldown(self):
        self.login_as(self.user_founder)
        response = self.client.get("/foundation/dashboard/drilldown/alerts/?network=WGMN&country=NG")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "SLA Verification Backlog")

    def test_authorized_meetings_drilldown(self):
        self.login_as(self.user_founder)
        response = self.client.get("/foundation/dashboard/drilldown/meetings/?network=WGMN&country=NG")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nigeria National Leadership Assembly")

    def test_authorized_reports_drilldown(self):
        self.login_as(self.user_founder)
        response = self.client.get("/foundation/dashboard/drilldown/reports/?network=WGMN&country=NG")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "West Africa Regional Field Report")

    def test_unauthorized_member_drilldown_rejected(self):
        """Regular member trying to view sensitive member roster drilldown is denied 403."""
        self.login_as(self.user_member_ada)
        response = self.client.get("/foundation/dashboard/drilldown/members/")
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "unauthorized_drilldown", status_code=403)

    def test_unauthorized_verification_drilldown_rejected(self):
        """Regular member trying to view verification queue drilldown is denied 403."""
        self.login_as(self.user_member_ada)
        response = self.client.get("/foundation/dashboard/drilldown/verifications/")
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "unauthorized_drilldown", status_code=403)

    def test_alert_detail_view_and_acknowledge_action(self):
        self.login_as(self.user_ops)
        alert = DashboardAlert.objects.filter(country="NG", network="WGMN").first()
        self.assertIsNotNone(alert)

        # GET detail view
        resp1 = self.client.get(f"/foundation/dashboard/alerts/{alert.id}/")
        self.assertEqual(resp1.status_code, 200)
        self.assertContains(resp1, "Acknowledge Alert")

        # POST acknowledge action
        resp_ack = self.client.post(f"/foundation/dashboard/alerts/{alert.id}/acknowledge/")
        self.assertEqual(resp_ack.status_code, 302)

        # Re-fetch detail view
        resp2 = self.client.get(f"/foundation/dashboard/alerts/{alert.id}/")
        self.assertContains(resp2, "Acknowledged")

    def test_meeting_detail_view_and_rsvp_action(self):
        self.login_as(self.user_country_ng)
        meeting = ScheduledMeeting.objects.filter(country="NG", network="WGMN").first()
        self.assertIsNotNone(meeting)
        init_count = meeting.attendees_count

        # POST RSVP
        resp_rsvp = self.client.post(f"/foundation/dashboard/meetings/{meeting.id}/rsvp/")
        self.assertEqual(resp_rsvp.status_code, 302)

        meeting.refresh_from_db()
        self.assertEqual(meeting.attendees_count, init_count + 1)
        self.assertTrue(meeting.rsvp_accounts.filter(id=self.account_country_ng.id).exists())

        # POST again to cancel RSVP
        resp_cancel = self.client.post(f"/foundation/dashboard/meetings/{meeting.id}/rsvp/")
        self.assertEqual(resp_cancel.status_code, 302)

        meeting.refresh_from_db()
        self.assertEqual(meeting.attendees_count, init_count)
        self.assertFalse(meeting.rsvp_accounts.filter(id=self.account_country_ng.id).exists())

    def test_chapter_detail_view(self):
        self.login_as(self.user_founder)
        chapter = Chapter.objects.filter(code="NG-LOS-01").first()
        self.assertIsNotNone(chapter)

        response = self.client.get(f"/foundation/dashboard/chapters/{chapter.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, chapter.name)
        self.assertContains(response, chapter.code)
        self.assertContains(response, "Chapter Profile")

    def test_report_detail_view(self):
        self.login_as(self.user_founder)
        report = DashboardReport.objects.filter(network="WGMN", country="ALL").first()
        self.assertIsNotNone(report)

        response = self.client.get(f"/foundation/dashboard/reports/{report.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, report.title.replace("&", "&amp;"))
        self.assertContains(response, report.period)
        self.assertContains(response, "Executive Summary")


class ScopedCSVExportTests(DashboardTestCaseBase):
    """Ensure data exports deliver streamed CSV data strictly scoped to active network & country."""

    def test_export_summary_kpis(self):
        self.login_as(self.user_founder)
        response = self.client.get("/foundation/dashboard/export/?type=summary&network=WGMN&country=NG")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("attachment; filename=\"wdos-summary-WGMN-NG.csv\"", response["Content-Disposition"])
        content = response.content.decode("utf-8")
        self.assertIn("Metric,Value,Network,Country", content)
        self.assertIn("active_chapters", content)

    def test_export_chapters_strictly_scoped(self):
        self.login_as(self.user_founder)
        response = self.client.get("/foundation/dashboard/export/?type=chapters&network=WGMN&country=NG")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("Lagos Central Chapter", content)
        self.assertNotIn("Nairobi Kilimani Chapter", content)
        self.assertNotIn("Lagos Next-Gen Youth Hub", content)

    def test_export_denied_when_scope_unauthorized(self):
        """Nigeria lead cannot export Kenya data."""
        self.login_as(self.user_country_ng)
        response = self.client.get("/foundation/dashboard/export/?type=chapters&network=WGMN&country=KE")
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "wrong_country", status_code=403)


class EmptyAndErrorStatesTests(DashboardTestCaseBase):
    """Ensure truthful empty states with ARIA role='status' and robust error states."""

    def test_empty_state_rendered_truthfully_with_aria_status(self):
        self.login_as(self.user_founder)
        # South Africa has no WNNN chapters in fixtures
        response = self.client.get("/foundation/dashboard/drilldown/chapters/?network=WNNN&country=ZA")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "role=\"status\"")
        self.assertContains(response, "No Chapters in Current Scope")

    def test_scope_error_page_renders_reason_code_and_recovery_link(self):
        self.login_as(self.user_country_ng)
        response = self.client.get("/foundation/?country=ZA")
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Access Restricted", status_code=403)
        self.assertContains(response, "wrong_country", status_code=403)
        self.assertContains(response, "Return to Authorized Workspace", status_code=403)
