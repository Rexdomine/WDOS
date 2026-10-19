"""
Test Suite for Visual Identity and Geography Presentation.
Validates the requirements from 16 October Review & Rebuild Master Specification v1.2:
1. A user can visually distinguish WGMN from WNN on the welcome page and dashboard.
2. Country-level views show the correct country and approved geographic visualisation.
3. The visual context identifies the user's country and permitted local scope.
4. Maps do not label Lagos, Ikeja, or another public area as a Chapter unless WDOS organizational data says so.
5. Every visual map has a text equivalent for the network, country, geographic levels, Community Cluster, and Chapter.
6. Users cannot see map layers or local records outside their permitted network and geography (fail-closed server-side authorization).
7. The implementation uses approved assets and does not introduce placeholder branding into the client-facing flow.
"""

import io
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import Account
from foundation.models import Chapter, CountryDossier, LocalOrganisationUnit, GeographyTerminology
from foundation.people_geo_engine import seed_stage6_fixtures

User = get_user_model()


class VisualIdentityGeographyTestCase(TestCase):
    def setUp(self):
        sink = io.StringIO()
        call_command("seed_roles", stdout=sink)
        call_command("seed_shell_data", stdout=sink)
        call_command("seed_dashboards", stdout=sink)
        seed_stage6_fixtures()

        self.user_founder = User.objects.get(email="founder@example.org")
        self.account_founder = Account.objects.get(email="founder@example.org")

        self.user_country_ng = User.objects.get(email="country.ng@example.org")
        self.account_country_ng = Account.objects.get(email="country.ng@example.org")

        self.user_country_ke = User.objects.get(email="country.ke@example.org")
        self.account_country_ke = Account.objects.get(email="country.ke@example.org")

        self.user_member_ada = User.objects.get(email="member.ada@example.org")
        self.account_member_ada = Account.objects.get(email="member.ada@example.org")

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

    def test_welcome_page_visual_distinction_wgmn_vs_wnn(self):
        """Acceptance Criterion 1: Welcome page visually distinguishes WGMN and WNN."""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)

        # 1. Distinct Network Cards & Badges
        self.assertContains(resp, "network-choice-card")
        self.assertContains(resp, "badge-wgmn")
        self.assertContains(resp, "badge-wnn")
        self.assertContains(resp, "WGMN &middot; 30+")
        self.assertContains(resp, "WNN &middot; 18–29")

        # 2. Approved Network SVG Logos
        self.assertContains(resp, "wgmn-logo")
        self.assertContains(resp, "wnn-logo")

        # 3. Dedicated Branded CTA Buttons with Leading Arrow Icon
        self.assertContains(resp, "btn-wgmn")
        self.assertContains(resp, "btn-wnn")
        self.assertContains(resp, "Enter Good Mother Network")
        self.assertContains(resp, "Enter Next-Gen Nurturers")
        self.assertContains(resp, '<span class="icon" aria-hidden="true">')

    def test_dashboard_visual_identity_distinction(self):
        """Acceptance Criterion 1: Dashboard visually distinguishes WGMN from WNN."""
        self.login_as(self.user_founder)

        # WGMN view
        resp_wgmn = self.client.get("/foundation/?network=WGMN")
        self.assertEqual(resp_wgmn.status_code, 200)
        self.assertContains(resp_wgmn, "brand-wgmn")
        self.assertContains(resp_wgmn, "WODDI Good Mother Network")
        self.assertContains(resp_wgmn, "#D4006A")

        # WNN view
        resp_wnn = self.client.get("/foundation/?network=WNNN")
        self.assertEqual(resp_wnn.status_code, 200)
        self.assertContains(resp_wnn, "brand-wnnn")
        self.assertContains(resp_wnn, "WNN")
        self.assertContains(resp_wnn, "WODDI Next-Gen Nurturers Network")

    def test_country_command_profile_visual_map_and_scope(self):
        """Acceptance Criteria 2, 3, 4, 5: Country command profile displays approved map and hierarchy."""
        self.login_as(self.user_founder)

        resp = self.client.get("/foundation/geography/country/NG/command/")
        self.assertEqual(resp.status_code, 200)

        # Geographic Visualisation Card
        self.assertContains(resp, "country-map-card")
        self.assertContains(resp, "country-map-svg")
        self.assertContains(resp, "Lagos State")
        self.assertContains(resp, "Ikeja LGA")

        # Distinguish public administrative area from WDOS units
        self.assertContains(resp, "Public Geography")
        self.assertContains(resp, "WDOS Cluster")
        self.assertContains(resp, "WDOS Chapter")
        self.assertContains(resp, "Allen Chapter")
        self.assertContains(resp, "Ikeja Central Cluster")

        # Critical: Lagos and Ikeja must NOT be labelled as chapters
        self.assertNotContains(resp, "Lagos Chapter")
        self.assertNotContains(resp, "Ikeja Chapter")

        # Accessible Map Text Equivalent with 6-level hierarchy path
        self.assertContains(resp, "Accessible Map Text Equivalent")
        self.assertContains(resp, "Authoritative Hierarchy Trail")
        self.assertContains(resp, "WGMN → Nigeria → Lagos State → Ikeja LGA → Ikeja Central Cluster → Allen Chapter")

    def test_country_lead_dashboard_includes_map_and_hierarchy_path(self):
        """Acceptance Criteria 2, 3, 4, 5: Country Hub dashboard shows geographic context and full hierarchy trail."""
        self.login_as(self.user_country_ng)

        resp = self.client.get("/foundation/dashboard/")
        self.assertEqual(resp.status_code, 200)

        # Country Map Card on Country Lead Overview
        self.assertContains(resp, "country-map-card")
        self.assertContains(resp, "Nigeria &middot; Country Geographic Visualisation")
        self.assertContains(resp, "Accessible Map Text Equivalent")
        self.assertContains(resp, "Authoritative Hierarchy Trail")
        self.assertContains(resp, "Nigeria → Lagos State → Ikeja LGA → Ikeja Central Cluster → Allen Chapter")

    def test_local_organisation_view_semantic_badges(self):
        """Acceptance Criteria 4 & 5: Local organisation view displays distinct semantic badges."""
        self.login_as(self.user_founder)

        resp = self.client.get("/foundation/geography/local-org/?country=NG")
        self.assertEqual(resp.status_code, 200)

        # Semantic Badges for Public Geography vs WDOS Units
        self.assertContains(resp, "badge-public-geo")
        self.assertContains(resp, "badge-wdos-org")
        self.assertContains(resp, "badge-wdos-operating")
        self.assertContains(resp, "Public Administrative Geography")
        self.assertContains(resp, "WDOS Organisational Unit")
        self.assertContains(resp, "WDOS Operating Unit")

        # Authoritative Hierarchy Trail Breadcrumb Box at top of tree
        self.assertContains(resp, "Authoritative Hierarchy Trail")
        self.assertContains(resp, "WGMN → Nigeria → Lagos State → Ikeja LGA → Ikeja Central Cluster → Allen Chapter")

    def test_africa_network_coverage_map_text_equivalent(self):
        """Acceptance Criteria 2, 5: Africa coverage view includes accessible text equivalent and network theme."""
        self.login_as(self.user_founder)

        resp = self.client.get("/foundation/geography/coverage/?network=WGMN")
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "stage6-continental-card")
        self.assertContains(resp, "Accessible Map Text Equivalent")
        self.assertContains(resp, "Authoritative Hierarchy Trail")
        self.assertContains(resp, "theme-wgmn")

        # Switch to WNN
        resp_wnn = self.client.get("/foundation/geography/coverage/?network=WNNN")
        self.assertEqual(resp_wnn.status_code, 200)
        self.assertContains(resp_wnn, "theme-wnn")
        self.assertContains(resp_wnn, "WNN &middot; Next-Gen Nurturers")

    def test_fail_closed_server_side_permissions(self):
        """Acceptance Criterion 6: Users cannot see map layers or local records outside their permitted network and geography."""
        # Kenya Country Lead attempting to access Nigeria dossier
        self.login_as(self.user_country_ke)

        resp_geo02 = self.client.get("/foundation/geography/country/NG/command/")
        self.assertEqual(resp_geo02.status_code, 403)
        self.assertContains(resp_geo02, "country_mismatch", status_code=403)

        resp_geo03 = self.client.get("/foundation/geography/local-org/?country=NG")
        self.assertEqual(resp_geo03.status_code, 403)
        self.assertContains(resp_geo03, "country_mismatch", status_code=403)

    def test_no_placeholder_branding(self):
        """Acceptance Criterion 7: Client-facing flow uses approved branding without placeholder text or placeholder assets."""
        self.login_as(self.user_founder)

        screens_to_check = [
            "/foundation/",
            "/foundation/geography/coverage/",
            "/foundation/geography/country/NG/command/",
            "/foundation/geography/local-org/?country=NG",
        ]
        for url in screens_to_check:
            resp = self.client.get(url)
            self.assertEqual(resp.status_code, 200, f"Failed accessing {url}")
            self.assertNotContains(resp, "lorem ipsum", msg_prefix=f"Placeholder text found on {url}")
            self.assertNotContains(resp, "placeholder.png", msg_prefix=f"Placeholder image found on {url}")
