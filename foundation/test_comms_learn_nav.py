"""
Unit and integration tests verifying sidebar navigation routes for Messages and Learning & resources,
and verifying the COMMS-01, LEARN-01, and RES-01 views match the UI review specifications.
"""

import io
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import Account, Membership, OnboardingConsent, OnboardingDraft, Person

User = get_user_model()


class CommsLearnNavigationTests(TestCase):
    def setUp(self):
        call_command("seed_roles", stdout=io.StringIO())
        call_command("seed_shell_data", stdout=io.StringIO())

        # Ordinary Member (Ada Okafor)
        self.user = User.objects.create_user(
            username="ada_member",
            email="ada_member@example.org",
            password="TestPassword@2026!",
        )
        self.person = Person.objects.create(display_name="Ada Okafor")
        self.account = Account.objects.create(
            user=self.user,
            email="ada_member@example.org",
            display_name="Ada Okafor",
            person=self.person,
            status="active",
            verified_at=timezone.now(),
        )
        self.draft = OnboardingDraft.objects.create(
            account=self.account,
            state="accepted",
            data={"network": "WGMN", "country": "NG", "language": "en"},
        )
        self.consent = OnboardingConsent.objects.create(
            draft=self.draft,
            revision=1,
            version="1.0",
            notice="Notice",
            digest="abc",
            approval_reference="ref",
            privacy_ack=True,
            channel="web",
        )
        self.membership = Membership.objects.create(
            draft=self.draft,
            person=self.person,
            network="WGMN",
            home={"country": "NG", "state": "Lagos", "lga": "Ikeja", "label": "Lagos Central Chapter"},
            consent=self.consent,
            policy_digest="policy_abc",
            approved_by=self.account,
        )

        self.login_as(self.user)

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

    def test_sidebar_navigation_destinations(self):
        """Verify sidebar items link to their correct dedicated screens."""
        resp = self.client.get("/foundation/work-queue/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")

        # Messages must link to /foundation/messages/, NOT /foundation/notifications/
        self.assertIn('href="/foundation/messages/"', content)
        self.assertNotIn('href="/foundation/notifications/">\n      <svg class="nav-svg"', content)

        # Learning & resources must link to /foundation/learning/, NOT /foundation/settings/
        self.assertIn('href="/foundation/learning/"', content)

        # Settings still links to /foundation/settings/
        self.assertIn('href="/foundation/settings/"', content)

        # Meetings & events links to /foundation/meetings/
        self.assertIn('href="/foundation/meetings/"', content)

        # Topbar bell icon links to /foundation/notifications/
        self.assertIn('href="/foundation/notifications/" class="icon"', content)

    def test_notifications_page_does_not_falsely_activate_messages_navitem(self):
        """Visiting /foundation/notifications/ must not mark 'Messages' sidebar link as active."""
        resp = self.client.get("/foundation/notifications/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")

        # Notifications heading is shown
        self.assertIn("Notifications</h1>", content)

        # Messages link should NOT have class "active"
        self.assertNotIn('class="navitem active" href="/foundation/messages/"', content)
        self.assertIn('class="navitem " href="/foundation/messages/"', content)

    def test_messages_inbox_comms_01_renders_and_interacts(self):
        """COMMS-01: Inbox view renders correctly with threads, breadcrumbs, and allows replying."""
        # 1. GET inbox
        resp = self.client.get("/foundation/messages/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")

        self.assertIn("Inbox</h1>", content)
        self.assertIn("Messaging, announcements and campaigns", content)
        self.assertIn("Country coordination", content)
        self.assertIn("Please review the agenda for the country coordination meeting.", content)
        self.assertIn('class="navitem active" href="/foundation/messages/"', content)

        # 2. POST reply
        reply_resp = self.client.post("/foundation/messages/", {
            "conversation_id": "conv-country-coord",
            "message": "Acknowledged. I will review the agenda now.",
        })
        self.assertEqual(reply_resp.status_code, 302)

        # 3. Follow redirect and check reply
        follow_resp = self.client.get(reply_resp.url)
        self.assertIn("Acknowledged. I will review the agenda now.", follow_resp.content.decode("utf-8"))

    def test_learning_development_learn_01_renders(self):
        """LEARN-01: My learning and development view renders correctly with courses and pathway."""
        resp = self.client.get("/foundation/learning/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")

        self.assertIn("My learning and development</h1>", content)
        self.assertIn("Learning and personal development", content)
        self.assertIn("Role orientation", content)
        self.assertIn("Reporting with evidence", content)
        self.assertIn("Peer-learning reflection", content)
        self.assertIn('class="navitem active" href="/foundation/learning/"', content)

    def test_resources_for_role_res_01_renders(self):
        """RES-01: Resources for your role view renders correctly with files and versions."""
        resp = self.client.get("/foundation/resources/")
        self.assertEqual(resp.status_code, 200)
        content = resp.content.decode("utf-8")

        self.assertIn("Resources for your role</h1>", content)
        self.assertIn("Resources and institutional knowledge", content)
        self.assertIn("Leadership Pack", content)
        self.assertIn("Reporting guide", content)
        self.assertIn("Activity evidence template", content)

    def test_screen_router_dispatches_comms_learn_res(self):
        """Direct screen code dispatcher /foundation/screens/<SCREEN-CODE>/ routes properly."""
        for code, expected_text in [
            ("COMMS-01", "Inbox</h1>"),
            ("LEARN-01", "My learning and development</h1>"),
            ("RES-01", "Resources for your role</h1>"),
        ]:
            resp = self.client.get(f"/foundation/screens/{code}/")
            self.assertEqual(resp.status_code, 200, f"Failed for screen code {code}")
            self.assertIn(expected_text, resp.content.decode("utf-8"))

    def test_founder_leadership_sidebar_persists_across_all_menu_destinations(self):
        """
        Regression test: When signed in as founder@example.org (or any leadership tier role),
        clicking side menu items must keep the leadership side menu intact and never switch
        to the ordinary member side menu ('My activities').
        """
        call_command("seed_dashboards", stdout=io.StringIO())
        founder_user = User.objects.get(email="founder@example.org")
        self.login_as(founder_user)

        leadership_destinations = [
            ("/foundation/dashboard/", "workspace"),
            ("/foundation/people/", "people"),
            ("/foundation/leadership/structure/", "people"),
            ("/foundation/work-queue/", "work"),
            ("/foundation/meetings/", "meetings"),
            ("/foundation/messages/", "communications"),
            ("/foundation/learning/", "learning"),
            ("/foundation/dashboard/drilldown/reports/", "reports"),
            ("/foundation/settings/", "settings"),
            ("/foundation/", "workspace"),
        ]

        for url, _ in leadership_destinations:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"Failed on {url}")
            content = resp.content.decode("utf-8")
            self.assertTrue(resp.context.get("is_leadership_tier"), f"is_leadership_tier missing on {url}")
            self.assertIn("People & leadership", content, f"Leadership sidebar missing 'People & leadership' on {url}")
            self.assertIn('href="/foundation/people/"', content, f"People & leadership link incorrect on {url}")
            self.assertIn("Work & programmes", content, f"Leadership sidebar missing 'Work & programmes' on {url}")
            self.assertIn("Communications", content, f"Leadership sidebar missing 'Communications' on {url}")
            self.assertIn("Reports & oversight", content, f"Leadership sidebar missing 'Reports & oversight' on {url}")
            self.assertNotIn("My activities", content, f"Sidebar unexpectedly switched to member menu on {url}")

