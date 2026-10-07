"""
Comprehensive test suite for WDOS Stage 4: Signed-in Shell, Navigation, Work Queue,
Notifications, Confidential Search Boundary, Profile, Settings, Preferences,
and Privacy Requests.
"""
import io
import json
import uuid
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import AccessGrant, Account, Membership, OnboardingConsent, OnboardingDraft, Person
from foundation.models import CountryHub, LeadershipLevel, Notification, PrivacyRequest, Role, UserPreference, WorkItem
from foundation.scope import get_breadcrumbs, get_user_preferences, get_user_scope

User = get_user_model()


class ShellTestCaseBase(TestCase):
    def setUp(self):
        call_command("seed_roles", stdout=io.StringIO())
        call_command("seed_shell_data", stdout=io.StringIO())

        # 1. WGMN Member (Nigeria)
        self.user_wgmn = User.objects.create_user(
            username="wgmn_member",
            email="wgmn_member@example.org",
            password="TestPassword@2026!",
        )
        self.person_wgmn = Person.objects.create(display_name="Amina Bello")
        self.account_wgmn = Account.objects.create(
            user=self.user_wgmn,
            email="wgmn_member@example.org",
            display_name="Amina Bello",
            person=self.person_wgmn,
            status="active",
            verified_at=timezone.now(),
        )
        self.draft_wgmn = OnboardingDraft.objects.create(
            account=self.account_wgmn,
            state="accepted",
            data={"network": "WGMN", "country": "NG", "language": "en"},
        )
        self.consent_wgmn = OnboardingConsent.objects.create(
            draft=self.draft_wgmn,
            revision=1,
            version="1.0",
            notice="Notice",
            digest="abc",
            approval_reference="ref",
            privacy_ack=True,
            channel="web",
        )
        self.membership_wgmn = Membership.objects.create(
            draft=self.draft_wgmn,
            person=self.person_wgmn,
            network="WGMN",
            home={"country": "NG", "state": "Lagos", "lga": "Ikeja", "label": "Lagos Chapter"},
            consent=self.consent_wgmn,
            policy_digest="policy_abc",
            approved_by=self.account_wgmn,
        )

        # 2. WNNN Member (Ghana)
        self.user_wnnn = User.objects.create_user(
            username="wnnn_member",
            email="wnnn_member@example.org",
            password="TestPassword@2026!",
        )
        self.person_wnnn = Person.objects.create(display_name="Efua Mensah")
        self.account_wnnn = Account.objects.create(
            user=self.user_wnnn,
            email="wnnn_member@example.org",
            display_name="Efua Mensah",
            person=self.person_wnnn,
            status="active",
            verified_at=timezone.now(),
        )
        self.draft_wnnn = OnboardingDraft.objects.create(
            account=self.account_wnnn,
            state="accepted",
            data={"network": "WNNN", "country": "GH", "language": "en"},
        )
        self.consent_wnnn = OnboardingConsent.objects.create(
            draft=self.draft_wnnn,
            revision=1,
            version="1.0",
            notice="Notice",
            digest="abc",
            approval_reference="ref",
            privacy_ack=True,
            channel="web",
        )
        self.membership_wnnn = Membership.objects.create(
            draft=self.draft_wnnn,
            person=self.person_wnnn,
            network="WNNN",
            home={"country": "GH", "region": "Greater Accra", "district": "Accra Metro", "label": "Accra Chapter"},
            consent=self.consent_wnnn,
            policy_digest="policy_abc",
            approved_by=self.account_wnnn,
        )

        # 3. IT Admin / Management User (Global Scope)
        self.user_admin = User.objects.create_user(
            username="admin_user",
            email="admin@example.org",
            password="TestPassword@2026!",
            is_staff=True,
            is_superuser=True,
        )
        self.person_admin = Person.objects.create(display_name="System Admin")
        self.account_admin = Account.objects.create(
            user=self.user_admin,
            email="admin@example.org",
            display_name="System Admin",
            person=self.person_admin,
            status="active",
            verified_at=timezone.now(),
        )
        AccessGrant.objects.create(
            account=self.account_admin,
            role="management",
            network="*",
            geography="*",
            function="all",
            expires_at=timezone.now() + timedelta(days=365),
        )

    def login_as(self, user):
        account = Account.objects.filter(user=user).first()
        self.client.force_login(user)
        session = self.client.session
        now = timezone.now().timestamp()
        if account:
            session['security_version'] = account.security_version
        session['mfa_verified'] = True
        session['last_activity'] = now
        session['absolute_expiry'] = now + 43200
        session.save()


class ShellNavigationAndWorkspaceTests(ShellTestCaseBase):
    def test_unauthenticated_user_redirected_to_login(self):
        response = self.client.get("/foundation/")
        self.assertRedirects(response, "/auth/login/")

    def test_unaccepted_member_redirected_to_status(self):
        unaccepted_user = User.objects.create_user(
            username="unaccepted", email="unaccepted@example.org", password="Password123!"
        )
        Account.objects.create(
            user=unaccepted_user,
            email="unaccepted@example.org",
            status="active",
            verified_at=timezone.now(),
        )
        self.login_as(unaccepted_user)
        response = self.client.get("/foundation/")
        self.assertRedirects(response, "/auth/status/")

    def test_authenticated_wgmn_member_accesses_workspace(self):
        self.login_as(self.user_wgmn)
        response = self.client.get("/foundation/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "WGMN")
        self.assertContains(response, "Amina Bello")
        self.assertContains(response, "Workspace")

    def test_app_alias_routes_to_shell(self):
        self.login_as(self.user_wgmn)
        response = self.client.get("/app")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Amina Bello")


class NetworkSeparationAndGeographyTests(ShellTestCaseBase):
    def test_wgmn_member_can_access_wgmn_workspace(self):
        self.login_as(self.user_wgmn)
        response = self.client.get("/foundation/network/WGMN/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "WODDI Global Mothers Network")

    def test_wgmn_member_denied_access_to_wnnn_workspace(self):
        self.login_as(self.user_wgmn)
        response = self.client.get("/foundation/network/WNNN/")
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Access Restricted", status_code=403)
        self.assertContains(response, "wrong_network", status_code=403)
        self.assertContains(response, "Return to Authorized Workspace", status_code=403)

    def test_wnnn_member_can_access_wnnn_workspace(self):
        self.login_as(self.user_wnnn)
        response = self.client.get("/foundation/network/WNNN/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "WODDI Next-Gen Nurturers Network")

    def test_wnnn_member_denied_access_to_wgmn_workspace(self):
        self.login_as(self.user_wnnn)
        response = self.client.get("/foundation/network/WGMN/")
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Access Restricted", status_code=403)
        self.assertContains(response, "wrong_network", status_code=403)

    def test_country_hub_access_permitted_for_own_country(self):
        self.login_as(self.user_wgmn)
        response = self.client.get("/foundation/network/WGMN/country/NG/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nigeria Country Hub (NG)")

    def test_country_hub_access_denied_for_wrong_country(self):
        self.login_as(self.user_wgmn)
        # Amina is NG only; trying to access Ghana Hub GH
        response = self.client.get("/foundation/network/WGMN/country/GH/")
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Access Restricted", status_code=403)
        self.assertContains(response, "wrong_country", status_code=403)

    def test_admin_has_global_and_multi_network_access(self):
        self.login_as(self.user_admin)
        # Admin can access WGMN
        res_wgmn = self.client.get("/foundation/network/WGMN/")
        self.assertEqual(res_wgmn.status_code, 200)

        # Admin can access WNNN
        res_wnnn = self.client.get("/foundation/network/WNNN/")
        self.assertEqual(res_wnnn.status_code, 200)

        # Admin can access Ghana Hub
        res_gh = self.client.get("/foundation/network/WNNN/country/GH/")
        self.assertEqual(res_gh.status_code, 200)

    def test_switch_scope_action_validates_permissions(self):
        self.login_as(self.user_wgmn)
        # Valid switch to permitted network
        res = self.client.post("/foundation/scope/switch/", {"network": "WGMN", "country": "NG"})
        self.assertEqual(res.status_code, 302)

        # Invalid switch to unpermitted network
        res_invalid = self.client.post("/foundation/scope/switch/", {"network": "WNNN", "country": "GH"})
        self.assertEqual(res_invalid.status_code, 403)


class ScopedBreadcrumbsHierarchyTests(ShellTestCaseBase):
    def test_breadcrumbs_path_hierarchy(self):
        self.login_as(self.user_wgmn)
        # Level 1: WDOS
        res1 = self.client.get("/foundation/")
        self.assertContains(res1, "scoped-breadcrumbs")
        self.assertContains(res1, "WDOS")

        # Level 2: Network Workspace
        res2 = self.client.get("/foundation/network/WGMN/")
        self.assertContains(res2, "WGMN Workspace")

        # Level 3: Country Hub
        res3 = self.client.get("/foundation/network/WGMN/country/NG/")
        self.assertContains(res3, "Nigeria Hub")

        # Level 4: Leadership Level
        res4 = self.client.get("/foundation/network/WGMN/country/NG/leadership/member/")
        self.assertContains(res4, "Individual Member")

        # Level 5: Individual Profile
        res5 = self.client.get(f"/foundation/network/WGMN/country/NG/leadership/member/profile/{self.person_wgmn.id}/")
        self.assertContains(res5, "Amina Bello")


class WorkQueueAndDeepLinkTests(ShellTestCaseBase):
    def setUp(self):
        super().setUp()
        self.item_wgmn_ng = WorkItem.objects.create(
            title="Nigeria Chapter Outreach",
            summary="Review and plan Nigeria community outreach initiative.",
            category="review",
            network="WGMN",
            country="NG",
            priority="urgent",
            status="pending",
        )
        self.item_wnnn_gh = WorkItem.objects.create(
            title="Accra Youth Workshop",
            summary="Coordinate next-gen youth mentorship in Accra.",
            category="membership",
            network="WNNN",
            country="GH",
            priority="normal",
            status="pending",
        )
        self.item_confidential = WorkItem.objects.create(
            title="Executive Strategy Audit",
            summary="Highly confidential leadership governance audit.",
            category="review",
            network="WGMN",
            country="NG",
            priority="high",
            status="pending",
            confidential=True,
        )

    def test_work_queue_shows_only_authorized_items(self):
        self.login_as(self.user_wgmn)
        response = self.client.get("/foundation/work-queue/?status=all")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nigeria Chapter Outreach")
        self.assertNotContains(response, "Accra Youth Workshop")
        # Confidential item not visible to ordinary member
        self.assertNotContains(response, "Executive Strategy Audit")

    def test_work_item_deep_link_authorized(self):
        self.login_as(self.user_wgmn)
        response = self.client.get(f"/foundation/work-queue/{self.item_wgmn_ng.id}/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nigeria Chapter Outreach")
        self.assertContains(response, "Review and plan Nigeria community outreach initiative.")

    def test_work_item_deep_link_unauthorized_returns_403_and_leaks_nothing(self):
        self.login_as(self.user_wgmn)
        # Amina attempts to deep-link into Ghana WNNN item
        response = self.client.get(f"/foundation/work-queue/{self.item_wnnn_gh.id}/")
        self.assertEqual(response.status_code, 403)
        self.assertContains(response, "Access Restricted", status_code=403)
        # Ensure record title and summary are NOT leaked
        self.assertNotContains(response, "Accra Youth Workshop", status_code=403)
        self.assertNotContains(response, "next-gen youth mentorship", status_code=403)

    def test_confidential_deep_link_denied_to_ordinary_member(self):
        self.login_as(self.user_wgmn)
        response = self.client.get(f"/foundation/work-queue/{self.item_confidential.id}/")
        self.assertEqual(response.status_code, 403)
        self.assertNotContains(response, "Executive Strategy Audit", status_code=403)

    def test_work_item_action_transitions_state(self):
        self.login_as(self.user_wgmn)
        # Claim item
        response = self.client.post(
            f"/foundation/work-queue/{self.item_wgmn_ng.id}/action/",
            {"action": "claim"},
        )
        self.assertEqual(response.status_code, 302)
        self.item_wgmn_ng.refresh_from_db()
        self.assertEqual(self.item_wgmn_ng.status, "in_progress")
        self.assertEqual(self.item_wgmn_ng.assigned_to, self.account_wgmn)


class ConfidentialSearchBoundaryTests(ShellTestCaseBase):
    def setUp(self):
        super().setUp()
        WorkItem.objects.create(
            title="Nigeria Water Project",
            summary="Borehole installation in Ogun state.",
            network="WGMN",
            country="NG",
        )
        WorkItem.objects.create(
            title="Ghana Health Initiative",
            summary="Rural clinic support in Kumasi.",
            network="WNNN",
            country="GH",
        )
        WorkItem.objects.create(
            title="Confidential Internal Audit",
            summary="Classified budget review for Nigeria.",
            network="WGMN",
            country="NG",
            confidential=True,
        )

    def test_search_ui_enforces_boundaries_and_does_not_leak(self):
        self.login_as(self.user_wgmn)
        # Searching "Health" (matches Ghana WNNN item)
        response = self.client.get("/foundation/search/?q=Health")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No matching records found")
        self.assertNotContains(response, "Ghana Health Initiative")

        # Searching "Confidential"
        response_conf = self.client.get("/foundation/search/?q=Confidential")
        self.assertEqual(response_conf.status_code, 200)
        self.assertContains(response_conf, "No matching records found")
        self.assertNotContains(response_conf, "Confidential Internal Audit")

        # Searching permitted keyword
        response_ok = self.client.get("/foundation/search/?q=Water")
        self.assertEqual(response_ok.status_code, 200)
        self.assertContains(response_ok, "Nigeria Water Project")

    def test_search_api_zero_leakage(self):
        self.login_as(self.user_wgmn)
        response = self.client.get("/foundation/api/search/?q=Health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["total_count"], 0)
        self.assertEqual(data["results"], [])


class NotificationsTests(ShellTestCaseBase):
    def setUp(self):
        super().setUp()
        self.notif_delivered = Notification.objects.create(
            account=self.account_wgmn,
            title="Meeting Scheduled",
            message="Your weekly chapter meeting is set for Friday.",
            delivery_status="delivered",
            is_read=False,
        )
        self.notif_failed = Notification.objects.create(
            account=self.account_wgmn,
            title="SMS Dispatch Failed",
            message="Urgent notice could not be sent to mobile number.",
            delivery_status="failed",
            is_read=False,
        )

    def test_notifications_view_renders_alerts_and_failure_recovery(self):
        self.login_as(self.user_wgmn)
        response = self.client.get("/foundation/notifications/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Meeting Scheduled")
        self.assertContains(response, "SMS Dispatch Failed")
        self.assertContains(response, "Delivery Failure")
        self.assertContains(response, "Retry Delivery")

    def test_mark_notification_read_api(self):
        self.login_as(self.user_wgmn)
        response = self.client.post(f"/foundation/api/notifications/{self.notif_delivered.id}/read/")
        self.assertEqual(response.status_code, 200)
        self.notif_delivered.refresh_from_db()
        self.assertTrue(self.notif_delivered.is_read)

    def test_retry_failed_notification(self):
        self.login_as(self.user_wgmn)
        response = self.client.post(f"/foundation/api/notifications/{self.notif_failed.id}/retry/")
        self.assertEqual(response.status_code, 302)
        self.notif_failed.refresh_from_db()
        self.assertEqual(self.notif_failed.delivery_status, "delivered")


class SettingsAndAccessibilityPreferencesTests(ShellTestCaseBase):
    def test_missing_preference_recovers_with_safe_defaults(self):
        # User has no preference record
        UserPreference.objects.filter(account=self.account_wgmn).delete()
        pref = get_user_preferences(self.account_wgmn)
        self.assertEqual(pref.language, "en")
        self.assertFalse(pref.high_contrast)
        self.assertFalse(pref.reduced_motion)
        self.assertEqual(pref.font_size, "standard")

    def test_saving_preferences_persists_and_sets_cookie(self):
        self.login_as(self.user_wgmn)
        response = self.client.post(
            "/foundation/api/preferences/",
            {
                "language": "fr",
                "high_contrast": "true",
                "reduced_motion": "true",
                "font_size": "large",
                "email_notifications": "true",
                "in_app_notifications": "true",
                "activity_digest": "weekly",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies["wdos_language"].value, "fr")

        pref = UserPreference.objects.get(account=self.account_wgmn)
        self.assertEqual(pref.language, "fr")
        self.assertTrue(pref.high_contrast)
        self.assertTrue(pref.reduced_motion)
        self.assertEqual(pref.font_size, "large")
        self.assertEqual(pref.activity_digest, "weekly")

    def test_reset_preferences_to_defaults(self):
        self.login_as(self.user_wgmn)
        response = self.client.post("/foundation/settings/reset-preferences/")
        self.assertEqual(response.status_code, 302)
        pref = UserPreference.objects.get(account=self.account_wgmn)
        self.assertEqual(pref.language, "en")
        self.assertFalse(pref.high_contrast)


class PrivacyRequestsTests(ShellTestCaseBase):
    def test_submit_privacy_request_creates_record_and_work_item(self):
        self.login_as(self.user_wgmn)
        response = self.client.post(
            "/foundation/privacy-requests/new/",
            {
                "request_type": "export",
                "reason": "Requesting a copy of my personal data archive under GDPR.",
                "ack": "1",
            },
        )
        self.assertEqual(response.status_code, 302)

        pr = PrivacyRequest.objects.filter(account=self.account_wgmn).first()
        self.assertIsNotNone(pr)
        self.assertEqual(pr.request_type, "export")
        self.assertEqual(pr.status, "submitted")

        # Verify a compliance WorkItem was queued
        wi = WorkItem.objects.filter(category="privacy", created_by=self.account_wgmn).first()
        self.assertIsNotNone(wi)
        self.assertTrue(wi.confidential)

    def test_download_completed_export_data(self):
        pr = PrivacyRequest.objects.create(
            account=self.account_wgmn,
            request_type="export",
            status="completed",
        )
        self.login_as(self.user_wgmn)
        response = self.client.get(f"/foundation/privacy-requests/{pr.id}/export/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        data = json.loads(response.content)
        self.assertEqual(data["email"], "wgmn_member@example.org")


class RevocationAndSuspendedSessionTests(ShellTestCaseBase):
    def test_suspended_account_denied_access(self):
        self.account_wgmn.status = "suspended"
        self.account_wgmn.save()

        self.login_as(self.user_wgmn)
        response = self.client.get("/foundation/")
        # Suspended account redirected to status/login
        self.assertRedirects(response, "/auth/status/")
