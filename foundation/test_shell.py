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
from foundation.models import (
    CountryHub,
    DeviceSession,
    LeadershipLevel,
    NetworkTransition,
    Notification,
    PrivacyRequest,
    Role,
    UserPreference,
    WorkItem,
)
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

    def test_priority_work_item_redirects_to_highest_priority(self):
        self.login_as(self.user_wgmn)
        response = self.client.get("/foundation/work-queue/priority/")
        self.assertEqual(response.status_code, 302)
        # Should redirect to highest priority pending/in_progress item in scope
        self.assertIn(f"/foundation/work-queue/{self.item_wgmn_ng.id}/", response.url)

    def test_work_queue_tabs_and_lifecycle_in_history(self):
        self.login_as(self.user_wgmn)

        # 1. Overview tab shows active item
        res_overview = self.client.get("/foundation/work-queue/?tab=overview")
        self.assertEqual(res_overview.status_code, 200)
        self.assertContains(res_overview, "Nigeria Chapter Outreach")

        # 2. Records tab shows filter pills and item
        res_records = self.client.get("/foundation/work-queue/?tab=records")
        self.assertEqual(res_records.status_code, 200)
        self.assertContains(res_records, "Active records")
        self.assertContains(res_records, "Nigeria Chapter Outreach")

        # 3. Mark item completed
        self.client.post(
            f"/foundation/work-queue/{self.item_wgmn_ng.id}/action/",
            {"action": "complete"},
        )
        self.item_wgmn_ng.refresh_from_db()
        self.assertEqual(self.item_wgmn_ng.status, "completed")

        # 4. History tab now contains the completed item
        res_history = self.client.get("/foundation/work-queue/?tab=history")
        self.assertEqual(res_history.status_code, 200)
        self.assertContains(res_history, "Resolution history")
        self.assertContains(res_history, "Nigeria Chapter Outreach")


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

    def test_notifications_filter_by_status_and_search(self):
        self.login_as(self.user_wgmn)
        # Search by query
        resp_search = self.client.get("/foundation/notifications/?q=Meeting")
        self.assertContains(resp_search, "Meeting Scheduled")
        self.assertNotContains(resp_search, "SMS Dispatch Failed")

        # Filter by status=failed
        resp_failed = self.client.get("/foundation/notifications/?status=failed")
        self.assertContains(resp_failed, "SMS Dispatch Failed")
        self.assertNotContains(resp_failed, "Meeting Scheduled")

    def test_notifications_seed_default_for_empty_account(self):
        # Empty notifications for WNNN user
        Notification.objects.filter(account=self.account_wnnn).delete()
        self.login_as(self.user_wnnn)
        response = self.client.get("/foundation/notifications/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Local welcome meeting")
        self.assertContains(response, "Communication preferences")
        self.assertContains(response, "Membership profile")
        # Ensure they are saved in the DB
        self.assertEqual(Notification.objects.filter(account=self.account_wnnn).count(), 3)

    def test_mark_all_notifications_read_post(self):
        self.login_as(self.user_wgmn)
        self.assertFalse(self.notif_delivered.is_read)
        response = self.client.post("/foundation/api/notifications/mark-all-read/")
        self.assertEqual(response.status_code, 302)
        self.notif_delivered.refresh_from_db()
        self.assertTrue(self.notif_delivered.is_read)


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


class Stage4DynamicShellTests(ShellTestCaseBase):
    def test_device_sessions_view_auto_creation_and_signout(self):
        self.login_as(self.user_wgmn)
        # 1. Visiting sessions view registers the current session + auxiliary demo session
        response = self.client.get("/foundation/account/sessions/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Your signed-in devices")
        self.assertContains(response, "Keep signed in")
        self.assertContains(response, "Review sign-out")

        # 2. Check DeviceSession records in DB
        sessions = list(self.account_wgmn.device_sessions.all())
        self.assertGreaterEqual(len(sessions), 2)
        other_session = self.account_wgmn.device_sessions.filter(is_current=False).first()
        self.assertIsNotNone(other_session)

        # 3. Visit signout page for other session
        resp_signout = self.client.get(f"/foundation/account/signout-device/?device_id={other_session.id}")
        self.assertEqual(resp_signout.status_code, 200)
        self.assertContains(resp_signout, "Sign out this device?")

        # 4. Confirm signout via POST
        post_signout = self.client.post("/foundation/account/signout-device/", {
            "session_id": str(other_session.id),
            "confirm_signout": "1",
        })
        self.assertRedirects(post_signout, "/foundation/account/sessions/?signed_out=1")

        # 5. Verify session deleted and success message displayed
        self.assertFalse(self.account_wgmn.device_sessions.filter(id=other_session.id).exists())
        resp_after = self.client.get("/foundation/account/sessions/?signed_out=1")
        self.assertContains(resp_after, "Device signed out successfully")

    def test_connection_status_live_check(self):
        self.login_as(self.user_wgmn)
        # Normal GET
        resp = self.client.get("/foundation/connection-status/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Your connection is unavailable")

        # GET with ?check=1 tests real DB connection
        resp_check = self.client.get("/foundation/connection-status/?check=1")
        self.assertEqual(resp_check.status_code, 200)
        self.assertContains(resp_check, "Connection verified")
        self.assertContains(resp_check, "Return to your workspace")

    def test_privacy_request_full_lifecycle_and_review(self):
        self.login_as(self.user_wgmn)
        # 1. Submit request via confirm page
        resp_submit = self.client.post("/foundation/privacy-requests/confirm/", {
            "request_type": "correct_info",
            "details": "Please correct my middle name in chapter records.",
            "safe_reply_route": "account",
        })
        self.assertEqual(resp_submit.status_code, 302)

        pr = PrivacyRequest.objects.filter(account=self.account_wgmn).first()
        self.assertIsNotNone(pr)
        self.assertTrue(pr.reference.startswith("PR-"))
        self.assertGreaterEqual(len(pr.timeline), 2)

        # 2. Status page renders dynamic timeline
        resp_status = self.client.get(f"/foundation/privacy-requests/status/?ref={pr.reference}")
        self.assertEqual(resp_status.status_code, 200)
        self.assertContains(resp_status, pr.reference)
        self.assertContains(resp_status, "Identity check requested")

        # 3. Staff / Reviewer records approval decision
        resp_review = self.client.post("/foundation/privacy-requests/review/", {
            "request_ref": pr.reference,
            "identity_check": "verified",
            "decision": "approve",
            "reason_and_retention": "Identity card verified. Name corrected per policy.",
        })
        self.assertEqual(resp_review.status_code, 200)
        pr.refresh_from_db()
        self.assertEqual(pr.decision, "approve")
        self.assertEqual(pr.status, "Approved")
        self.assertEqual(pr.current_step, "Decision approved")
        # Timeline includes the review event
        self.assertTrue(any("Review recorded: Approve" in ev.get("what", "") for ev in pr.timeline))

    def test_network_transition_submission_and_tabs(self):
        self.login_as(self.user_wgmn)
        # 1. Overview tab renders dynamic relationship (WGMN -> WNNN transition review)
        resp_overview = self.client.get("/foundation/network-transition/?tab=overview")
        self.assertEqual(resp_overview.status_code, 200)
        self.assertContains(resp_overview, "WGMN membership")
        self.assertContains(resp_overview, "WNNN transition review")

        # 2. Submit transition request
        resp_submit = self.client.post("/foundation/network-transition/", {
            "consent_confirmed": "1",
        })
        self.assertEqual(resp_submit.status_code, 200)
        self.assertContains(resp_submit, "Review request submitted")

        trans = NetworkTransition.objects.filter(account=self.account_wgmn).first()
        self.assertIsNotNone(trans)
        self.assertEqual(trans.current_relationship, "WGMN membership")

        # 3. Records tab shows the created transition
        resp_records = self.client.get("/foundation/network-transition/?tab=records")
        self.assertEqual(resp_records.status_code, 200)
        self.assertContains(resp_records, "Network transition records")
        self.assertContains(resp_records, "WGMN membership")
        self.assertContains(resp_records, "WNNN transition review")

        # 4. History tab shows history events
        resp_history = self.client.get("/foundation/network-transition/?tab=history")
        self.assertEqual(resp_history.status_code, 200)
        self.assertContains(resp_history, "Network &amp; relationship history")
        self.assertContains(resp_history, "Transition requested")

