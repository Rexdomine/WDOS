"""
Unit and Integration Tests for WDOS Enterprise Rebuild Hierarchy Specification.
Reference: WDOS_Enterprise_Rebuild_Master_Specification_v1_2.docx
Approved Hierarchy:
HQ -> Country -> State/first-level area equivalent -> Local government/LGA/district equivalent -> Community Cluster -> Chapter -> Person

Covers all 7 Acceptance Criteria:
1. A person's path can be followed from Country to First-level area, Local-government/district equivalent, Community Cluster, Chapter, and Person.
2. Community Cluster and Chapter are separate selectable/displayed entities.
3. Multiple Chapters can exist under a Community Cluster.
4. Country-specific terminology comes from approved geography data rather than hard-coded assumptions.
5. Chapter and Community Cluster labels are correct in dashboards, search results, assignments, and leadership views.
6. Role permissions follow the same network and geography hierarchy.
7. Prevent broad places such as Lagos or Ikeja from being displayed as a Chapter unless authoritative WDOS data explicitly defines them that way.
"""

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.utils import timezone
from accounts.models import (
    Account,
    Person,
    OnboardingDraft,
    OnboardingConsent,
    AccessGrant,
    Membership,
)
from foundation.models import (
    PersonProfile,
    LocalOrganisationUnit,
    Chapter,
    GeographyTerminology,
)
from foundation.people_geo_engine import (
    seed_stage6_fixtures,
    save_local_organisation_unit,
    add_or_link_person_record,
    update_person_profile_record,
)
from foundation.scope import (
    get_user_scope,
    is_broad_geographic_place,
    sanitize_chapter_display,
    is_authoritative_chapter,
    UserScope,
)
from foundation.context_block import get_identity_context


class HierarchySpecificationTests(TestCase):
    def setUp(self):
        self.client = Client()
        seed_stage6_fixtures()

        # Create test users and accounts
        self.hq_user = User.objects.create_user(
            username="test_hq_lead",
            email="hq.lead@woddi.org",
            password="testpass123",
        )
        self.hq_person = Person.objects.create(display_name="HQ Global Lead")
        self.hq_account = Account.objects.create(
            user=self.hq_user,
            email="hq.lead@woddi.org",
            display_name="HQ Global Lead",
            person=self.hq_person,
            status="active",
            security_version=1,
        )
        draft = OnboardingDraft.objects.create(account=self.hq_account, state="accepted")
        OnboardingConsent.objects.create(
            draft=draft,
            revision=1,
            version="1.0",
            notice="Consent",
            digest="abc-1",
            approval_reference="ref-1",
            privacy_ack=True,
            channel="web",
        )
        AccessGrant.objects.create(
            account=self.hq_account,
            role="founder",
            network="WGMN",
            geography="ALL",
            function="leadership",
            expires_at=timezone.now() + timezone.timedelta(days=365),
        )

        # Cluster lead account
        self.cluster_user = User.objects.create_user(
            username="test_cluster_lead",
            email="cluster.lead@woddi.org",
            password="testpass123",
        )
        self.cluster_person = Person.objects.create(display_name="Ikeja Cluster Coordinator")
        self.cluster_account = Account.objects.create(
            user=self.cluster_user,
            email="cluster.lead@woddi.org",
            display_name="Ikeja Cluster Coordinator",
            person=self.cluster_person,
            status="active",
            security_version=1,
        )
        c_draft = OnboardingDraft.objects.create(account=self.cluster_account, state="accepted")
        OnboardingConsent.objects.create(
            draft=c_draft,
            revision=1,
            version="1.0",
            notice="Consent",
            digest="abc-2",
            approval_reference="ref-2",
            privacy_ack=True,
            channel="web",
        )
        AccessGrant.objects.create(
            account=self.cluster_account,
            role="cluster_lead",
            network="WGMN",
            geography="Ikeja Central",
            function="leadership",
            expires_at=timezone.now() + timezone.timedelta(days=365),
        )
        PersonProfile.objects.create(
            account=self.cluster_account,
            full_name="Ikeja Cluster Coordinator",
            person_code="WD-CLUST-01",
            country="NG",
            network="WGMN",
            community_cluster="Ikeja Central Cluster",
            state_or_region="Lagos State",
            lga_or_district="Ikeja LGA",
        )

        # Chapter lead account
        self.chapter_user = User.objects.create_user(
            username="test_chapter_lead",
            email="allen.lead@woddi.org",
            password="testpass123",
        )
        self.chapter_person = Person.objects.create(display_name="Allen Chapter Coordinator")
        self.chapter_account = Account.objects.create(
            user=self.chapter_user,
            email="allen.lead@woddi.org",
            display_name="Allen Chapter Coordinator",
            person=self.chapter_person,
            status="active",
            security_version=1,
        )
        ch_draft = OnboardingDraft.objects.create(account=self.chapter_account, state="accepted")
        OnboardingConsent.objects.create(
            draft=ch_draft,
            revision=1,
            version="1.0",
            notice="Consent",
            digest="abc-3",
            approval_reference="ref-3",
            privacy_ack=True,
            channel="web",
        )
        AccessGrant.objects.create(
            account=self.chapter_account,
            role="chapter_lead",
            network="WGMN",
            geography="Allen Chapter",
            function="leadership",
            expires_at=timezone.now() + timezone.timedelta(days=365),
        )
        PersonProfile.objects.create(
            account=self.chapter_account,
            full_name="Allen Chapter Coordinator",
            person_code="WD-CHAP-01",
            country="NG",
            network="WGMN",
            chapter_name="Allen Chapter",
            community_cluster="Ikeja Central Cluster",
            state_or_region="Lagos State",
            lga_or_district="Ikeja LGA",
        )

    def _login(self, user):
        account = Account.objects.get(user=user)
        self.client.force_login(user)
        session = self.client.session
        now = timezone.now().timestamp()
        session["security_version"] = account.security_version
        session["mfa_verified"] = True
        session["last_activity"] = now
        session["absolute_expiry"] = now + 43200
        session.save()

    # -------------------------------------------------------------------------
    # Acceptance Criterion 1: 6-Tier Person Path & Country-Specific Terms
    # -------------------------------------------------------------------------

    def test_ac1_person_path_nigeria(self):
        """AC 1: A person's path can be followed from Country to LGA, Cluster, Chapter, and Person (Nigeria)."""
        ada = PersonProfile.objects.get(person_code="WD-00421")
        path = ada.get_hierarchy_path()

        self.assertEqual(path["country_code"], "NG")
        self.assertEqual(path["country_name"], "Nigeria")
        self.assertEqual(path["first_level_term"], "State / FCT")
        self.assertEqual(path["first_level_name"], "Lagos State")
        self.assertEqual(path["second_level_term"], "LGA")
        self.assertEqual(path["second_level_name"], "Ikeja LGA")
        self.assertEqual(path["cluster_name"], "Ikeja Central Cluster")
        self.assertEqual(path["chapter_name"], "Allen Chapter")
        self.assertEqual(path["person_name"], "Ada Okafor")

        # Verify all 6 nodes in path_nodes
        nodes = path["path_nodes"]
        self.assertEqual(len(nodes), 6)
        self.assertEqual(nodes[0]["tier"], "country")
        self.assertEqual(nodes[0]["name"], "Nigeria")
        self.assertEqual(nodes[1]["tier"], "first_level")
        self.assertEqual(nodes[1]["term"], "State / FCT")
        self.assertEqual(nodes[1]["name"], "Lagos State")
        self.assertEqual(nodes[2]["tier"], "second_level")
        self.assertEqual(nodes[2]["term"], "LGA")
        self.assertEqual(nodes[2]["name"], "Ikeja LGA")
        self.assertEqual(nodes[3]["tier"], "cluster")
        self.assertEqual(nodes[3]["badge_type"], "woddi_cluster")
        self.assertEqual(nodes[3]["name"], "Ikeja Central Cluster")
        self.assertEqual(nodes[4]["tier"], "chapter")
        self.assertEqual(nodes[4]["badge_type"], "woddi_chapter")
        self.assertEqual(nodes[4]["name"], "Allen Chapter")
        self.assertEqual(nodes[5]["tier"], "person")
        self.assertEqual(nodes[5]["badge_type"], "person")
        self.assertEqual(nodes[5]["name"], "Ada Okafor")

    def test_ac1_person_path_kenya(self):
        """AC 1: A person's path uses country-specific equivalents for Kenya (County & Sub-County)."""
        wanjiru = PersonProfile.objects.get(person_code="WD-00424")
        path = wanjiru.get_hierarchy_path()

        self.assertEqual(path["country_code"], "KE")
        self.assertEqual(path["country_name"], "Kenya")
        self.assertEqual(path["first_level_term"], "County")
        self.assertEqual(path["first_level_name"], "Nairobi County")
        self.assertEqual(path["second_level_term"], "Sub-County")
        self.assertEqual(path["second_level_name"], "Westlands Sub-County")
        self.assertEqual(path["cluster_name"], "Westlands Cluster")
        self.assertEqual(path["chapter_name"], "Nairobi Central Chapter")
        self.assertEqual(path["person_name"], "Wanjiru Kariuki")

    def test_ac1_profile_view_displays_hierarchy(self):
        """AC 1: Profile view renders the full 6-tier pipeline trail and dynamic badges."""
        self._login(self.hq_user)
        res = self.client.get("/foundation/people/WD-00421/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Ikeja Central Cluster")
        self.assertContains(res, "Allen Chapter")
        self.assertContains(res, "State / FCT")
        self.assertContains(res, "LGA")
        self.assertContains(res, "Where this person belongs (Geographic &amp; Organizational Spine)")

    # -------------------------------------------------------------------------
    # Acceptance Criterion 2: Separate Selectable & Displayed Entities
    # -------------------------------------------------------------------------

    def test_ac2_cluster_and_chapter_separate_entities(self):
        """AC 2: Community Cluster and Chapter are separate selectable/displayed entities in models and database."""
        cluster_units = LocalOrganisationUnit.objects.filter(level="Community Cluster")
        chapter_units = LocalOrganisationUnit.objects.filter(level="Chapter")

        self.assertTrue(cluster_units.exists())
        self.assertTrue(chapter_units.exists())

        # Ensure Chapter model has foreign key to cluster unit
        chapter = Chapter.objects.filter(name="Allen Chapter").first()
        self.assertIsNotNone(chapter)
        self.assertIsNotNone(chapter.cluster_unit)
        self.assertEqual(chapter.cluster_unit.level, "Community Cluster")
        self.assertEqual(chapter.cluster_unit.unit_name, "Ikeja Central")

    def test_ac2_directory_view_displays_cluster_and_chapter_separately(self):
        """AC 2: Directory view renders separate Chapter and Community Cluster badges."""
        self._login(self.hq_user)
        res = self.client.get("/foundation/people/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Cluster: Ikeja Central")
        self.assertContains(res, "Allen Chapter")

    # -------------------------------------------------------------------------
    # Acceptance Criterion 3: Multiple Chapters under one Community Cluster
    # -------------------------------------------------------------------------

    def test_ac3_multiple_chapters_under_community_cluster(self):
        """AC 3: Multiple Chapters can exist under a single Community Cluster."""
        ke_cluster = LocalOrganisationUnit.objects.filter(country="KE", level="Community Cluster").first()
        self.assertIsNotNone(ke_cluster)

        # Kenya has both Nairobi Central Chapter and Parklands Chapter under Westlands Cluster
        child_chapters = Chapter.objects.filter(cluster_unit=ke_cluster)
        self.assertGreaterEqual(child_chapters.count(), 2)

        names = list(child_chapters.values_list("name", flat=True))
        self.assertIn("Nairobi Central Chapter", names)
        self.assertIn("Parklands Chapter", names)

    def test_ac3_create_new_chapter_under_existing_cluster(self):
        """AC 3: An authorized user can add another Chapter under an existing Community Cluster."""
        self._login(self.hq_user)
        ke_cluster = LocalOrganisationUnit.objects.filter(country="KE", level="Community Cluster").first()

        res = save_local_organisation_unit(
            network="WGMN",
            country="KE",
            level="Chapter",
            unit_name="Kilimani Chapter",
            responsible_leader_name="Grace Wambui",
            parent_id=ke_cluster.id,
            actor_account=self.hq_account,
            user_scope=get_user_scope(self.hq_account),
        )
        self.assertTrue(res["created"])
        new_unit = res["unit"]
        self.assertEqual(new_unit.parent, ke_cluster)

        # Check Chapter record created and linked
        ch = Chapter.objects.filter(name="Kilimani Chapter").first()
        self.assertIsNotNone(ch)
        self.assertEqual(ch.cluster_unit, ke_cluster)
        self.assertEqual(ch.community_cluster, ke_cluster.unit_name)

    # -------------------------------------------------------------------------
    # Acceptance Criterion 4: Country-Specific Terminology from Approved Data
    # -------------------------------------------------------------------------

    def test_ac4_approved_geography_terminology_all_supported_countries(self):
        """AC 4: Country-specific terminology comes from approved geography data (NG, KE, GH, AO, ET)."""
        terms = {t.country: (t.first_level_term, t.second_level_term) for t in GeographyTerminology.objects.all()}

        self.assertEqual(terms.get("NG"), ("State / FCT", "LGA"))
        self.assertEqual(terms.get("KE"), ("County", "Sub-County"))
        self.assertEqual(terms.get("GH"), ("Region", "Metropolitan / District"))
        self.assertEqual(terms.get("AO"), ("Province", "Municipality"))
        self.assertEqual(terms.get("ET"), ("Region / Chartered City", "Sub-City / Woreda"))

    def test_ac4_dynamic_terminology_update_propagates(self):
        """AC 4: Updating GeographyTerminology dynamically changes person path labels."""
        term_ng = GeographyTerminology.objects.get(country="NG")
        original_term = term_ng.first_level_term

        try:
            term_ng.first_level_term = "Federating State"
            term_ng.save()

            ada = PersonProfile.objects.get(person_code="WD-00421")
            path = ada.get_hierarchy_path()
            self.assertEqual(path["first_level_term"], "Federating State")
        finally:
            term_ng.first_level_term = original_term
            term_ng.save()

    # -------------------------------------------------------------------------
    # Acceptance Criterion 5: Dashboards, Search, and Chapter Detail Views
    # -------------------------------------------------------------------------

    def test_ac5_dashboard_cluster_lead_view(self):
        """AC 5: DASH-13 displays connected chapters under the Community Cluster."""
        self._login(self.cluster_user)
        res = self.client.get("/foundation/dashboards/DASH-13/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Community Cluster Coordinator")
        self.assertContains(res, "Ikeja Central")
        self.assertContains(res, "Connected Chapters")

    def test_ac5_dashboard_chapter_lead_view(self):
        """AC 5: DASH-14 displays sanitized Chapter name and parent Community Cluster."""
        self._login(self.chapter_user)
        res = self.client.get("/foundation/dashboards/DASH-14/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Chapter Lead")
        self.assertContains(res, "Allen Chapter")
        self.assertContains(res, "Community Cluster")

    def test_ac5_scoped_search_distinguishes_clusters_and_chapters(self):
        """AC 5: Scoped search differentiates Community Cluster and Chapter results."""
        self._login(self.hq_user)
        res = self.client.get("/foundation/search/?q=Cluster")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Community Cluster")

        res_chap = self.client.get("/foundation/search/?q=Allen")
        self.assertEqual(res_chap.status_code, 200)
        self.assertContains(res_chap, "Chapter")
        self.assertContains(res_chap, "Allen Chapter")

    def test_ac5_chapter_detail_view(self):
        """AC 5: Chapter detail view shows parent community cluster and dynamic terms."""
        self._login(self.hq_user)
        allen_chapter = Chapter.objects.get(name="Allen Chapter")
        res = self.client.get(f"/foundation/dashboard/chapters/{allen_chapter.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Allen Chapter")
        self.assertContains(res, "Ikeja Central Cluster")
        self.assertContains(res, "State / FCT")
        self.assertContains(res, "LGA")

    # -------------------------------------------------------------------------
    # Acceptance Criterion 6: Role Permissions Follow Network & Geo Hierarchy
    # -------------------------------------------------------------------------

    def test_ac6_role_permission_hierarchy_downward(self):
        """AC 6: Downward role inheritance allows higher-tier leads to access child tiers."""
        scope_hq = get_user_scope(self.hq_account)
        self.assertTrue(scope_hq.can_access_role("country_lead"))
        self.assertTrue(scope_hq.can_access_role("state_lead"))
        self.assertTrue(scope_hq.can_access_role("cluster_lead"))
        self.assertTrue(scope_hq.can_access_role("chapter_lead"))
        self.assertTrue(scope_hq.can_access_role("member"))

        scope_cluster = get_user_scope(self.cluster_account)
        self.assertTrue(scope_cluster.can_access_role("cluster_lead"))
        self.assertTrue(scope_cluster.can_access_role("chapter_lead"))
        self.assertTrue(scope_cluster.can_access_role("member"))
        # Cluster lead CANNOT act as Country or State lead
        self.assertFalse(scope_cluster.can_access_role("country_lead"))
        self.assertFalse(scope_cluster.can_access_role("state_lead"))
        self.assertFalse(scope_cluster.can_access_role("founder"))

        scope_chapter = get_user_scope(self.chapter_account)
        self.assertTrue(scope_chapter.can_access_role("chapter_lead"))
        self.assertTrue(scope_chapter.can_access_role("member"))
        self.assertFalse(scope_chapter.can_access_role("cluster_lead"))
        self.assertFalse(scope_chapter.can_access_role("state_lead"))

    def test_ac6_dashboard_permission_enforcement(self):
        """AC 6: Dashboard engine enforces role permission across hierarchy tiers."""
        self._login(self.chapter_user)
        # Chapter lead can access DASH-14
        res_chap = self.client.get("/foundation/dashboards/DASH-14/")
        self.assertEqual(res_chap.status_code, 200)

        # Chapter lead cannot access DASH-13 (Cluster Lead) or DASH-10 (Country Director)
        res_cluster = self.client.get("/foundation/dashboards/DASH-13/")
        self.assertEqual(res_cluster.status_code, 403)
        res_country = self.client.get("/foundation/dashboards/DASH-10/")
        self.assertEqual(res_country.status_code, 403)

    # -------------------------------------------------------------------------
    # Acceptance Criterion 7: Prevent Broad Places from Being Displayed as Chapters
    # -------------------------------------------------------------------------

    def test_ac7_is_broad_geographic_place(self):
        """AC 7: is_broad_geographic_place identifies states, LGAs, and broad areas."""
        self.assertTrue(is_broad_geographic_place("Lagos"))
        self.assertTrue(is_broad_geographic_place("lagos"))
        self.assertTrue(is_broad_geographic_place("Ikeja"))
        self.assertTrue(is_broad_geographic_place("Nairobi"))
        self.assertTrue(is_broad_geographic_place("Accra"))
        self.assertTrue(is_broad_geographic_place("Luanda"))
        self.assertTrue(is_broad_geographic_place("Addis Ababa"))

        # Actual chapters are NOT broad places
        self.assertFalse(is_broad_geographic_place("Allen Chapter"))
        self.assertFalse(is_broad_geographic_place("Surulere Central Chapter"))
        self.assertFalse(is_broad_geographic_place("Nairobi Central Chapter"))

    def test_ac7_sanitize_chapter_display(self):
        """AC 7: sanitize_chapter_display prevents Lagos or Ikeja from displaying as a chapter."""
        self.assertNotEqual(sanitize_chapter_display("Lagos Chapter"), "Lagos Chapter")
        self.assertNotEqual(sanitize_chapter_display("Ikeja Chapter"), "Ikeja Chapter")

        # Legitimate chapters remain intact
        self.assertEqual(sanitize_chapter_display("Allen Chapter"), "Allen Chapter")
        self.assertEqual(sanitize_chapter_display("Parklands Chapter"), "Parklands Chapter")

    def test_ac7_identity_context_block_no_broad_place_as_chapter(self):
        """AC 7: Identity context block hierarchy trail does NOT show Lagos or Ikeja as Chapter."""
        scope_ada = get_user_scope(self.hq_account)
        ada = PersonProfile.objects.get(person_code="WD-00421")

        id_ctx = get_identity_context(
            self.hq_account,
            scope_ada,
            active_network="WGMN",
            active_role="founder",
            active_country="NG",
            target_person=ada,
        )

        # Hierarchy trail nodes: 1=network, 2=country, 3=first_level, 4=second_level, 5=cluster, 6=chapter
        trail_nodes = id_ctx.get("hierarchy_trail", [])
        # Node 3 is First-Level Area (State)
        self.assertEqual(trail_nodes[2]["label"], "Lagos State")
        self.assertEqual(trail_nodes[2]["term"], "State / FCT")
        # Node 4 is Second-Level Area (LGA)
        self.assertEqual(trail_nodes[3]["label"], "Ikeja LGA")
        self.assertEqual(trail_nodes[3]["term"], "LGA")
        # Node 5 is Community Cluster
        self.assertEqual(trail_nodes[4]["label"], "Ikeja Central Cluster")
        self.assertEqual(trail_nodes[4]["term"], "Community Cluster")
        # Node 6 is Chapter
        self.assertNotEqual(trail_nodes[5]["label"], "Ikeja")
        self.assertNotEqual(trail_nodes[5]["label"], "Lagos")
        self.assertEqual(trail_nodes[5]["label"], "Allen Chapter")
        # Target person is reflected
        self.assertEqual(id_ctx["person_name"], "Ada Okafor")
