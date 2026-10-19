"""
Test Suite for Persistent Identity and Operational Context Block.
Validates the requirements from 16 October Review & Rebuild Master Specification v1.2:
1. Every authenticated dashboard displays the active user identity and scope.
2. The active role, network, country, and geographic assignment are visible together.
3. The display distinguishes a Chapter from a Community Cluster and from public administrative geography.
4. A role or network change updates the context shown to the user.
5. The context is correct for founder, country, regional/local operations, Community Cluster, Chapter, member, candidate, and community experiences.
6. Sensitive fields not permitted for the viewer are not exposed.
7. The presentation uses the approved network branding and remains consistent across dashboard types.
8. The context remains readable and persistent throughout dashboard workflows without opening a profile page.
"""

import io
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import Account, Membership, OnboardingDraft, Person, AccessGrant
from foundation.context_block import get_identity_context
from foundation.models import Chapter, CountryHub, LocalOrganisationUnit, GeographyTerminology
from foundation.scope import get_user_scope

from foundation.people_geo_engine import seed_stage6_fixtures

User = get_user_model()


class IdentityContextBlockTestCase(TestCase):
    def setUp(self):
        sink = io.StringIO()
        call_command("seed_roles", stdout=sink)
        call_command("seed_shell_data", stdout=sink)
        call_command("seed_dashboards", stdout=sink)
        seed_stage6_fixtures()

        # Standard test personas
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
        account = Account.objects.get(user=user)
        self.client.force_login(user)
        session = self.client.session
        now = timezone.now().timestamp()
        session["security_version"] = account.security_version
        session["mfa_verified"] = True
        session["last_activity"] = now
        session["absolute_expiry"] = now + 43200
        session.save()

    def test_identity_context_dictionary_structure(self):
        """Verify the data dictionary returned by get_identity_context contains all required fields."""
        scope = get_user_scope(self.account_member_ada)
        ctx = get_identity_context(self.account_member_ada, scope)

        # 1. Identity
        self.assertEqual(ctx["display_name"], "Ada Okafor")
        self.assertTrue(ctx["initials"])
        self.assertIn("has_profile_photo", ctx)
        self.assertIn("profile_photo_url", ctx)

        # 2. Role & Scope
        self.assertIn("active_role_title", ctx)
        self.assertIn("scope_badge", ctx)

        # 3. Network branding
        self.assertIn("network_code", ctx)
        self.assertIn("network_short_name", ctx)
        self.assertIn("network_name", ctx)
        self.assertIn("network_brand_color", ctx)
        self.assertIn("network_logo_svg", ctx)

        # 4. Country & Flag
        self.assertEqual(ctx["country_code"], "NG")
        self.assertEqual(ctx["country_name"], "Nigeria")
        self.assertEqual(ctx["country_flag_emoji"], "🇳🇬")

        # 5. Public Geography
        self.assertTrue(ctx["first_level_name"])
        self.assertTrue(ctx["first_level_term"])
        self.assertTrue(ctx["second_level_name"])
        self.assertTrue(ctx["second_level_term"])

        # 6. WODDI Units (Community Cluster and Chapter)
        self.assertTrue(ctx["cluster_name"])
        self.assertEqual(ctx["cluster_term"], "Community Cluster")
        self.assertTrue(ctx["chapter_name"])
        self.assertEqual(ctx["chapter_term"], "Chapter")

        # 7. Hierarchy trail & breadcrumb text
        self.assertEqual(len(ctx["hierarchy_trail"]), 6)
        self.assertIn("→", ctx["context_breadcrumb_text"])
        self.assertIn("Nigeria", ctx["context_breadcrumb_text"])
        self.assertIn("Lagos State", ctx["context_breadcrumb_text"])
        self.assertIn("Ikeja LGA", ctx["context_breadcrumb_text"])

    def test_context_block_rendered_on_authenticated_dashboards(self):
        """Verify the persistent context block is rendered on root workspace and role dashboards."""
        self.login_as(self.user_member_ada)
        
        # Workspace view
        resp = self.client.get("/foundation/")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "identity-context-block")
        self.assertContains(resp, "Ada Okafor")
        self.assertContains(resp, "Nigeria")
        self.assertContains(resp, "🇳🇬")
        self.assertContains(resp, "Lagos State")
        self.assertContains(resp, "Ikeja LGA")
        self.assertContains(resp, "Community Cluster")
        self.assertContains(resp, "Chapter")

        # Generic Role Dashboard Screen (DASH-15 for member)
        resp_dash = self.client.get("/foundation/dashboard/")
        self.assertEqual(resp_dash.status_code, 200)
        self.assertContains(resp_dash, "identity-context-block")
        self.assertContains(resp_dash, "Ada Okafor")
        self.assertContains(resp_dash, "Nigeria")

    def test_distinguishes_chapter_from_cluster_and_public_geo(self):
        """Verify that Chapter, Community Cluster, and Public Geography have distinct markup & semantic classes."""
        self.login_as(self.user_chapter_lagos)
        resp = self.client.get("/foundation/")
        self.assertEqual(resp.status_code, 200)

        # Public Geography nodes
        self.assertContains(resp, "pill-country")
        self.assertContains(resp, "pill-first-level")
        self.assertContains(resp, "pill-second-level")
        self.assertContains(resp, "geo-badge-tag")

        # Distinct WODDI Organisational units
        self.assertContains(resp, "pill-cluster")
        self.assertContains(resp, "tag-cluster")
        self.assertContains(resp, "Community Cluster")

        self.assertContains(resp, "pill-chapter")
        self.assertContains(resp, "tag-chapter")
        self.assertContains(resp, "Chapter")

    def test_network_switch_updates_context(self):
        """Switching active network updates network short name, branding colors, and logo."""
        self.login_as(self.user_founder)

        # Default WGMN
        resp_wgmn = self.client.get("/foundation/?network=WGMN")
        self.assertEqual(resp_wgmn.status_code, 200)
        self.assertContains(resp_wgmn, "brand-wgmn")
        self.assertContains(resp_wgmn, "WODDI Good Mother Network")

        # Switch to WNNN (WNN)
        resp_wnnn = self.client.get("/foundation/?network=WNNN")
        self.assertEqual(resp_wnnn.status_code, 200)
        self.assertContains(resp_wnnn, "brand-wnnn")
        self.assertContains(resp_wnnn, "WNN")
        self.assertContains(resp_wnnn, "WODDI Next-Gen Nurturers Network")
        self.assertContains(resp_wnnn, "#7CB518")

    def test_role_switch_updates_context(self):
        """Switching test role updates active role title and scope indicators."""
        self.login_as(self.user_founder)

        # As Founder
        resp_founder = self.client.get("/foundation/?role=founder")
        self.assertEqual(resp_founder.status_code, 200)
        self.assertContains(resp_founder, "Founder / Executive")

        # Switch to Country Lead
        resp_country = self.client.get("/foundation/?role=country_lead")
        self.assertEqual(resp_country.status_code, 200)
        self.assertContains(resp_country, "Country Representative")

        # Switch to Chapter Lead
        resp_chapter = self.client.get("/foundation/?role=chapter_lead")
        self.assertEqual(resp_chapter.status_code, 200)
        self.assertContains(resp_chapter, "Chapter Coordinator")

    def test_country_switch_updates_context(self):
        """Switching country updates flag, country name, and country-specific terminology."""
        self.login_as(self.user_founder)

        # Kenya
        resp_ke = self.client.get("/foundation/?country=KE")
        self.assertEqual(resp_ke.status_code, 200)
        self.assertContains(resp_ke, "Kenya")
        self.assertContains(resp_ke, "🇰🇪")
        self.assertContains(resp_ke, "County")
        self.assertContains(resp_ke, "Sub-County")

    def test_all_eight_experiences_supported(self):
        """Verify context correctness across all 8 user populations specified in acceptance criteria."""
        # 1. Founder
        scope = get_user_scope(self.account_founder)
        ctx = get_identity_context(self.account_founder, scope, active_role="founder")
        self.assertEqual(ctx["active_role_title"], "Founder / Executive")
        self.assertIn("Continental Oversight", ctx["scope_badge"])

        # 2. Country Lead (Nigeria)
        scope = get_user_scope(self.account_country_ng)
        ctx = get_identity_context(self.account_country_ng, scope, active_role="country_lead")
        self.assertEqual(ctx["active_role_title"], "Country Representative")
        self.assertIn("National Scope", ctx["scope_badge"])
        self.assertEqual(ctx["country_code"], "NG")

        # Country Lead (Kenya)
        scope = get_user_scope(self.account_country_ke)
        ctx = get_identity_context(self.account_country_ke, scope, active_role="country_lead")
        self.assertEqual(ctx["country_code"], "KE")
        self.assertEqual(ctx["country_flag_emoji"], "🇰🇪")

        # 3. Operations / State Lead
        scope = get_user_scope(self.account_ops)
        ctx = get_identity_context(self.account_ops, scope, active_role="state_lead")
        self.assertIn("State", ctx["active_role_title"])
        self.assertIn("Lagos State", ctx["first_level_name"])

        # 4. Community Cluster
        ctx = get_identity_context(self.account_member_ada, scope, active_role="cluster_lead")
        self.assertIn("Cluster", ctx["active_role_title"])
        self.assertIn("Cluster", ctx["cluster_name"])

        # 5. Chapter Lead
        scope = get_user_scope(self.account_chapter_lagos)
        ctx = get_identity_context(self.account_chapter_lagos, scope, active_role="chapter_lead")
        self.assertIn("Chapter", ctx["active_role_title"])
        self.assertTrue(ctx["chapter_name"])

        # 6. Member
        scope = get_user_scope(self.account_member_ada)
        ctx = get_identity_context(self.account_member_ada, scope, active_role="member")
        self.assertEqual(ctx["active_role_title"], "Ordinary Member")
        self.assertEqual(ctx["scope_badge"], "Enrolled Member")

        # 7. Candidate
        scope = get_user_scope(self.account_candidate)
        ctx = get_identity_context(self.account_candidate, scope, active_role="candidate")
        self.assertEqual(ctx["active_role_title"], "Leadership Candidate")
        self.assertIn("Candidate", ctx["scope_badge"])

        # 8. Community
        scope = get_user_scope(self.account_community)
        ctx = get_identity_context(self.account_community, scope, active_role="community")
        self.assertEqual(ctx["active_role_title"], "WODDI Community Participant")
        self.assertEqual(ctx["scope_badge"], "WODDI Community Participant")

    def test_sensitive_fields_not_exposed(self):
        """Verify sensitive credentials, auth digests, or confidential tokens are not exposed."""
        self.login_as(self.user_member_ada)
        resp = self.client.get("/foundation/")
        self.assertEqual(resp.status_code, 200)

        # Must not expose private fields
        if self.account_member_ada.mfa_secret:
            self.assertNotContains(resp, self.account_member_ada.mfa_secret)
        self.assertNotContains(resp, self.user_member_ada.password)
        self.assertNotContains(resp, "recovery_code")
        self.assertNotContains(resp, "security_version")

    def test_remains_available_during_dashboard_workflows(self):
        """Context block remains available across drill-downs, settings, and work queue workflows."""
        self.login_as(self.user_member_ada)

        workflows = [
            "/foundation/work-queue/",
            "/foundation/settings/",
            "/foundation/notifications/",
            "/foundation/profile/",
        ]
        for url in workflows:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"Workflow {url} failed with {resp.status_code}")
            self.assertContains(resp, "identity-context-block", msg_prefix=f"Missing on {url}")
            self.assertContains(resp, "Ada Okafor", msg_prefix=f"Missing name on {url}")
            self.assertContains(resp, "Nigeria", msg_prefix=f"Missing country on {url}")
