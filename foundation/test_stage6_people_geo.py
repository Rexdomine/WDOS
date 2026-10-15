"""
Automated Unit and Integration Test Suite for WDOS Stage 06:
People, Community and Geography Spine
Tests all 11 screens (PEOPLE-01 through GEO-05), server-side authorization,
duplicate prevention, local-home reassignment, country dossier verification,
geography terminology, and interaction contracts.
"""

from datetime import date
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import AccessGrant, Account, AuditEvent, Membership, OnboardingConsent, OnboardingDraft, Person
from foundation.models import (
    CountryDossier,
    GeographyTerminology,
    LocalHomeReassignment,
    LocalOrganisationUnit,
    PersonProfile,
    PersonRelationship,
    Role,
)
from foundation.people_geo_engine import (
    add_or_link_person_record,
    check_for_duplicate_person,
    save_geography_terminology_revision,
    save_person_relationship,
    seed_stage6_fixtures,
    submit_reassignment_decision,
    verify_country_dossier_submission,
)
from foundation.scope import ScopePermissionDenied

User = get_user_model()


class Stage06PeopleGeoTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        seed_stage6_fixtures()

        # Create Network Secretary test user (authorized for Nigeria / WGMN people operations)
        self.secretary_user = User.objects.create_user(
            username="ada_secretary",
            email="ada.secretary@example.org",
            password="test-password-123",
        )
        self.secretary_person = Person.objects.create(display_name="Ada Okafor")
        self.secretary_account = Account.objects.create(
            user=self.secretary_user,
            email="ada.secretary@example.org",
            display_name="Ada Okafor",
            person=self.secretary_person,
            status="active",
            security_version=1,
        )
        self.sec_draft = OnboardingDraft.objects.create(
            account=self.secretary_account,
            state="accepted",
            data={"language": "en", "timezone": "Africa/Lagos"},
        )
        self.sec_consent = OnboardingConsent.objects.create(
            draft=self.sec_draft,
            revision=1,
            version="1.0",
            notice="Consent",
            digest="abc",
            approval_reference="ref-1",
            privacy_ack=True,
            channel="web",
        )
        Membership.objects.create(
            draft=self.sec_draft,
            person=self.secretary_person,
            network="WGMN",
            home={"country": "NG", "region": "Lagos", "chapter": "Ikeja Chapter"},
            consent=self.sec_consent,
            policy_digest="digest-1",
            approved_by=self.secretary_account,
        )
        AccessGrant.objects.create(
            account=self.secretary_account,
            role="network_secretary",
            network="WGMN",
            geography="NG",
            function="leadership",
            expires_at=timezone.now() + timezone.timedelta(days=365),
        )

        # Create HOFCO / Executive test user (authorized for continental geography oversight)
        self.hofco_user = User.objects.create_user(
            username="executive_hofco",
            email="hofco@example.org",
            password="test-password-123",
        )
        self.hofco_person = Person.objects.create(display_name="Executive HOFCO")
        self.hofco_account = Account.objects.create(
            user=self.hofco_user,
            email="hofco@example.org",
            display_name="Executive HOFCO",
            person=self.hofco_person,
            status="active",
            security_version=1,
        )
        self.hofco_draft = OnboardingDraft.objects.create(
            account=self.hofco_account,
            state="accepted",
            data={"language": "en"},
        )
        self.hofco_consent = OnboardingConsent.objects.create(
            draft=self.hofco_draft,
            revision=1,
            version="1.0",
            notice="Consent",
            digest="abc",
            approval_reference="ref-2",
            privacy_ack=True,
            channel="web",
        )
        Membership.objects.create(
            draft=self.hofco_draft,
            person=self.hofco_person,
            network="WGMN",
            home={"country": "NG", "region": "HQ"},
            consent=self.hofco_consent,
            policy_digest="digest-2",
            approved_by=self.hofco_account,
        )
        AccessGrant.objects.create(
            account=self.hofco_account,
            role="hofco",
            network="HQ / Both networks",
            geography="ALL",
            function="oversight",
            expires_at=timezone.now() + timezone.timedelta(days=365),
        )

        # Create Ordinary Member test user (unauthorized for restricted decisions)
        self.member_user = User.objects.create_user(
            username="regular_member",
            email="member@example.org",
            password="test-password-123",
        )
        self.member_person = Person.objects.create(display_name="Regular Member")
        self.member_account = Account.objects.create(
            user=self.member_user,
            email="member@example.org",
            display_name="Regular Member",
            person=self.member_person,
            status="active",
            security_version=1,
        )
        self.mem_draft = OnboardingDraft.objects.create(
            account=self.member_account,
            state="accepted",
            data={"language": "en"},
        )
        self.mem_consent = OnboardingConsent.objects.create(
            draft=self.mem_draft,
            revision=1,
            version="1.0",
            notice="Consent",
            digest="abc",
            approval_reference="ref-3",
            privacy_ack=True,
            channel="web",
        )
        Membership.objects.create(
            draft=self.mem_draft,
            person=self.member_person,
            network="WGMN",
            home={"country": "NG", "region": "Lagos"},
            consent=self.mem_consent,
            policy_digest="digest-3",
            approved_by=self.member_account,
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
    # STEP 1 TESTS: PEOPLE DIRECTORY, PROFILE, AND SAFE ADD-OR-LINK
    # -------------------------------------------------------------------------

    def test_people_directory_view_renders_scoped_records(self):
        """PEOPLE-01: People directory renders authorized records."""
        self._login(self.secretary_user)
        response = self.client.get("/foundation/people/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "People directory")
        self.assertContains(response, "Ada Okafor")
        self.assertContains(response, "Lina Mensah")
        self.assertContains(response, "Kemi Bello")
        self.assertContains(response, "Connected relationships")
        self.assertContains(response, "Verification required")

    def test_people_directory_search_filter(self):
        """PEOPLE-01: Searching records filters by name or location."""
        self._login(self.secretary_user)
        response = self.client.get("/foundation/people/?q=Lina")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lina Mensah")
        self.assertNotContains(response, "Kemi Bello")

    def test_people_directory_empty_state_contract(self):
        """PEOPLE-01: ?state=empty displays state contract card."""
        self._login(self.secretary_user)
        response = self.client.get("/foundation/people/?state=empty")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No records in this view")
        self.assertContains(response, "Clear filters")

    def test_person_profile_view_renders_ada_okafor(self):
        """PEOPLE-02: Ada Okafor profile summary view."""
        self._login(self.secretary_user)
        response = self.client.get("/foundation/people/WD-00421/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ada Okafor")
        self.assertContains(response, "WD-00421")
        self.assertContains(response, "WGMN")
        self.assertContains(response, "Ikeja Chapter")
        self.assertContains(response, "Verified")

    def test_safe_duplicate_check_and_link(self):
        """PEOPLE-03: Duplicate check links existing person identity."""
        dup = check_for_duplicate_person(email="ada@example.org", full_name="Ada Okafor")
        self.assertTrue(dup["duplicate_found"])
        self.assertEqual(dup["person"].person_code, "WD-00421")

        # Submitting duplicate email links rather than creating a new identity
        res = add_or_link_person_record(
            full_name="Ada Okafor",
            email="ada@example.org",
            country="NG",
            relationship_to_add="WGMN mentorship",
            network="WGMN",
            actor_account=self.secretary_account,
        )
        self.assertEqual(res["action_type"], "linked")
        self.assertEqual(res["person"].person_code, "WD-00421")

    def test_add_new_person_creates_unique_record(self):
        """PEOPLE-03: Creating a brand new person identity generates new record."""
        res = add_or_link_person_record(
            full_name="Grace Eze",
            email="grace.eze@example.org",
            country="NG",
            relationship_to_add="WGMN membership",
            network="WGMN",
            actor_account=self.secretary_account,
        )
        self.assertEqual(res["action_type"], "created")
        self.assertTrue(res["person"].person_code.startswith("WD-"))
        self.assertEqual(res["person"].full_name, "Grace Eze")

    # -------------------------------------------------------------------------
    # STEP 2 TESTS: COMMUNITY RELATIONSHIPS & REASSIGNMENT
    # -------------------------------------------------------------------------

    def test_community_relationships_view(self):
        """PEOPLE-04: Community relationships list view."""
        self._login(self.secretary_user)
        response = self.client.get("/foundation/community/relationships/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Community relationships")
        self.assertContains(response, "Find a resource")
        self.assertContains(response, "For my role")

    def test_manage_relationships_submission(self):
        """PEOPLE-05: Saves relationship attached to person identity."""
        self._login(self.secretary_user)
        response = self.client.post("/foundation/community/relationships/manage/", {
            "person_code": "WD-00421",
            "relationship_category": "Programme participant",
            "related_programme": "Community Skills Exchange",
            "effective_date": "18 September 2026",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Relationship successfully saved")

        ada = PersonProfile.objects.get(person_code="WD-00421")
        self.assertTrue(ada.relationships.filter(related_programme="Community Skills Exchange").exists())

    def test_local_home_reassignment_unauthorized_role_denied(self):
        """PEOPLE-06: Ordinary member cannot approve reassignment."""
        self._login(self.member_user)
        response = self.client.post("/foundation/community/reassignment/review/", {
            "person_code": "WD-00421",
            "proposed_local_home": "Ikeja Chapter",
            "reason": "Move to Lagos",
            "member_confirmation": "true",
        })
        # Should render 403 Scope Error
        self.assertEqual(response.status_code, 403)

    def test_local_home_reassignment_authorized_submission(self):
        """PEOPLE-06: Authorized Network Secretary submits and approves reassignment."""
        self._login(self.secretary_user)
        response = self.client.post("/foundation/community/reassignment/review/", {
            "person_code": "WD-00421",
            "proposed_local_home": "Ikeja Chapter",
            "reason": "Member has confirmed a move to Lagos.",
            "member_confirmation": "true",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reassignment to &#x27;Ikeja Chapter&#x27; submitted and approved")

        ada = PersonProfile.objects.get(person_code="WD-00421")
        self.assertEqual(ada.local_home, "Ikeja Chapter")
        reassignment = LocalHomeReassignment.objects.filter(person=ada).first()
        self.assertEqual(reassignment.status, "approved")
        self.assertTrue(reassignment.member_confirmation)

    # -------------------------------------------------------------------------
    # STEP 3 TESTS: NETWORK COVERAGE & COUNTRY COMMAND PROFILE
    # -------------------------------------------------------------------------

    def test_africa_network_coverage_view_rendered(self):
        """GEO-01: Africa and network coverage view."""
        self._login(self.hofco_user)
        response = self.client.get("/foundation/geography/coverage/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Africa and network coverage")
        self.assertContains(response, "Continental view")
        self.assertContains(response, "Nigeria &middot; WGMN")
        self.assertContains(response, "Country verified")

    def test_country_command_profile_view_rendered(self):
        """GEO-02: Nigeria Country Command Profile."""
        self._login(self.hofco_user)
        response = self.client.get("/foundation/geography/country/NG/command/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nigeria &middot; Country Command Profile")
        self.assertContains(response, "Africa/Lagos · WAT")
        self.assertContains(response, "Country verified")

    # -------------------------------------------------------------------------
    # STEP 4 TESTS: LOCAL ORGANISATION & DOSSIER VERIFICATION
    # -------------------------------------------------------------------------

    def test_local_organisation_5_tier_hierarchy(self):
        """GEO-03: Local organisation 5-tier structure and unit directory."""
        self._login(self.hofco_user)
        response = self.client.get("/foundation/geography/local-org/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "WGMN / Nigeria")
        self.assertContains(response, "Lagos State")
        self.assertContains(response, "Ikeja LGA")
        self.assertContains(response, "Ikeja Central")
        self.assertContains(response, "Allen Chapter")

        # Verify unit directory records
        units = LocalOrganisationUnit.objects.filter(country="NG", network="WGMN")
        self.assertEqual(units.count(), 5)

    def test_verify_country_dossier_unauthorized_denied(self):
        """GEO-04: Unauthorized user cannot submit country dossier verification."""
        self._login(self.member_user)
        response = self.client.post("/foundation/geography/dossier/verify/", {
            "country_code": "NG",
            "network": "WGMN",
            "verification_stage": "Country custodian review",
            "evidence_reference": "Revision 03",
            "verification_notes": "All resolved",
        })
        self.assertEqual(response.status_code, 403)

    def test_verify_country_dossier_authorized_submission(self):
        """GEO-04: Authorized HOFCO submits country dossier verification."""
        self._login(self.hofco_user)
        response = self.client.post("/foundation/geography/dossier/verify/", {
            "country_code": "NG",
            "network": "WGMN",
            "verification_stage": "Country custodian review",
            "evidence_reference": "Country register revision 03",
            "verification_notes": "Leadership corrections resolved; language readiness remains under review.",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "verified successfully")

        dossier = CountryDossier.objects.get(country_code="NG", network="WGMN")
        self.assertEqual(dossier.verification_status, "Country verified")
        self.assertEqual(dossier.evidence_reference, "Country register revision 03")

    def test_geography_terminology_revision(self):
        """GEO-05: Saves controlled revision for geography terminology."""
        self._login(self.hofco_user)
        response = self.client.post("/foundation/geography/terminology/", {
            "country_code": "NG",
            "first_level_term": "State / FCT",
            "second_level_term": "LGA",
            "effective_date": "01 October 2026",
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Proposed terminology revision for Nigeria saved")

        term = GeographyTerminology.objects.get(country="NG")
        self.assertEqual(term.first_level_term, "State / FCT")
        self.assertEqual(term.second_level_term, "LGA")

    # -------------------------------------------------------------------------
    # STAGE 06 SCREEN ROUTER TESTS
    # -------------------------------------------------------------------------

    def test_stage6_screen_router_all_11_screens(self):
        """Screen router dispatches all 11 screen codes successfully."""
        self._login(self.hofco_user)
        screens = [
            "PEOPLE-01", "PEOPLE-02", "PEOPLE-03", "PEOPLE-04", "PEOPLE-05", "PEOPLE-06",
            "GEO-01", "GEO-02", "GEO-03", "GEO-04", "GEO-05"
        ]
        for screen in screens:
            res = self.client.get(f"/foundation/screens/{screen}/")
            self.assertEqual(res.status_code, 200, f"Screen {screen} failed with status {res.status_code}")

    # -------------------------------------------------------------------------
    # END-TO-END FUNCTIONAL & SCOPE ISOLATION TESTS
    # -------------------------------------------------------------------------

    def _create_kenya_lead_user(self):
        ke_user = User.objects.create_user(
            username="wanjiru_ke_lead",
            email="wanjiru.ke@example.org",
            password="test-password-123",
        )
        ke_person = Person.objects.create(display_name="Wanjiru Kariuki")
        ke_account = Account.objects.create(
            user=ke_user,
            email="wanjiru.ke@example.org",
            display_name="Wanjiru Kariuki",
            person=ke_person,
            status="active",
            security_version=1,
        )
        ke_draft = OnboardingDraft.objects.create(
            account=ke_account,
            state="accepted",
            data={"language": "en", "timezone": "Africa/Nairobi"},
        )
        ke_consent = OnboardingConsent.objects.create(
            draft=ke_draft,
            revision=1,
            version="1.0",
            notice="Consent",
            digest="abc",
            approval_reference="ref-ke",
            privacy_ack=True,
            channel="web",
        )
        Membership.objects.create(
            draft=ke_draft,
            person=ke_person,
            network="WGMN",
            home={"country": "KE", "region": "Nairobi", "chapter": "Westlands Chapter"},
            consent=ke_consent,
            policy_digest="digest-ke",
            approved_by=ke_account,
        )
        AccessGrant.objects.create(
            account=ke_account,
            role="country_lead",
            network="WGMN",
            geography="KE",
            function="leadership",
            expires_at=timezone.now() + timezone.timedelta(days=365),
        )
        return ke_user

    def test_multi_country_scope_isolation_and_restricted_states(self):
        """Kenya Country Lead sees only Kenya records and is blocked from Nigeria records/mutations."""
        ke_user = self._create_kenya_lead_user()
        self._login(ke_user)

        # PEOPLE-01 shows Kenya records (Wanjiru Kariuki, Amina Ochieng) and hides Nigeria records (Ada Okafor)
        res_dir = self.client.get("/foundation/people/")
        self.assertEqual(res_dir.status_code, 200)
        self.assertContains(res_dir, "Wanjiru Kariuki")
        self.assertContains(res_dir, "Amina Ochieng")
        self.assertNotContains(res_dir, "Ada Okafor")

        # PEOPLE-02: Opening Kenya person WD-00424 succeeds and shows belonging spine
        res_ke_prof = self.client.get("/foundation/people/WD-00424/")
        self.assertEqual(res_ke_prof.status_code, 200)
        self.assertContains(res_ke_prof, "Wanjiru Kariuki")
        self.assertContains(res_ke_prof, "Nairobi Central Chapter")
        self.assertContains(res_ke_prof, "Nairobi County")

        # PEOPLE-02: Opening Nigeria person WD-00421 returns 403 Restricted State
        res_ng_prof = self.client.get("/foundation/people/WD-00421/")
        self.assertEqual(res_ng_prof.status_code, 403)

        # GEO-02: Opening Kenya command profile succeeds; opening Nigeria command profile returns 403
        res_ke_cmd = self.client.get("/foundation/geography/country/KE/command/")
        self.assertEqual(res_ke_cmd.status_code, 200)
        self.assertContains(res_ke_cmd, "Kenya &middot; Country Command Profile")

        res_ng_cmd = self.client.get("/foundation/geography/country/NG/command/")
        self.assertEqual(res_ng_cmd.status_code, 403)

    def test_profile_update_changed_record_and_concurrency_protection(self):
        """PEOPLE-02: Authorized user updates profile, marks record as changed, and detects concurrent edits."""
        self._login(self.secretary_user)

        ada = PersonProfile.objects.get(person_code="WD-00421")
        initial_ts = ada.updated_at.isoformat()

        # Valid update
        res = self.client.post("/foundation/people/WD-00421/", {
            "action": "update_profile",
            "expected_updated_at": initial_ts,
            "full_name": "Ada Okafor",
            "email": "ada@example.org",
            "local_home": "Victoria Island Chapter",
            "primary_relationship": "WGMN Chapter Lead",
            "status": "Active",
            "contact_verification": "Verified",
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Profile updated")
        self.assertContains(res, "Changed record")

        ada.refresh_from_db()
        self.assertEqual(ada.local_home, "Victoria Island Chapter")
        self.assertEqual(ada.primary_relationship, "WGMN Chapter Lead")

        # Concurrent stale update with old timestamp triggers 'Another change needs review'
        res_stale = self.client.post("/foundation/people/WD-00421/", {
            "action": "update_profile",
            "expected_updated_at": "2020-01-01T00:00:00+00:00",
            "full_name": "Ada Okafor",
            "email": "ada@example.org",
            "local_home": "Stale Overwrite Chapter",
            "primary_relationship": "Member",
            "status": "Active",
            "contact_verification": "Verified",
        })
        self.assertEqual(res_stale.status_code, 200)
        self.assertContains(res_stale, "Another change needs review")
        ada.refresh_from_db()
        self.assertEqual(ada.local_home, "Victoria Island Chapter")

    def test_search_and_lists_automatic_no_matching_empty_states(self):
        """Search queries with 0 matches automatically display the 'Nothing to show in this scope' empty state card."""
        self._login(self.hofco_user)

        for url in [
            "/foundation/people/?q=NonExistentRecordXYZ",
            "/foundation/community/relationships/?q=NonExistentRecordXYZ",
            "/foundation/geography/coverage/?q=NonExistentRecordXYZ",
            "/foundation/geography/local-org/?q=NonExistentRecordXYZ",
        ]:
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, f"Failed for {url}")
            self.assertContains(res, "Nothing to show in this scope")
            self.assertContains(res, "no matching records")
            self.assertContains(res, "Reset view")

    def test_local_organisation_unit_editing_and_scope_enforcement(self):
        """GEO-03: Authorized user creates/updates a local organisation unit within permitted country scope."""
        self._login(self.secretary_user)

        res = self.client.post("/foundation/geography/local-org/?country=NG", {
            "action": "save_unit",
            "country_code": "NG",
            "network": "WGMN",
            "unit_name": "Surulere Chapter",
            "level": "Chapter",
            "responsible_leader_name": "Chioma Nwosu",
            "evidence_type": "Charter record",
        })
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, "Surulere Chapter")
        self.assertTrue(
            LocalOrganisationUnit.objects.filter(
                country="NG", network="WGMN", unit_name="Surulere Chapter"
            ).exists()
        )

        # Attempting to create a unit in Kenya (outside Nigeria secretary's scope) returns 403
        res_denied = self.client.post("/foundation/geography/local-org/?country=KE", {
            "action": "save_unit",
            "country_code": "KE",
            "network": "WGMN",
            "unit_name": "Unauthorized Kenya Unit",
            "level": "Chapter",
            "responsible_leader_name": "Someone",
            "evidence_type": "Charter record",
        })
        self.assertEqual(res_denied.status_code, 403)

    def test_global_scoped_search_finds_people_and_units_in_scope(self):
        """Global search (/foundation/search/) returns authorized people and local units and hides out-of-scope records."""
        self._login(self.secretary_user)

        # Nigeria secretary finds Ada Okafor
        res_ada = self.client.get("/foundation/search/?q=Ada")
        self.assertEqual(res_ada.status_code, 200)
        self.assertContains(res_ada, "Ada Okafor")

        # Nigeria secretary cannot find Kenya's Wanjiru Kariuki via global search
        res_ke = self.client.get("/foundation/search/?q=Wanjiru")
        self.assertEqual(res_ke.status_code, 200)
        self.assertNotContains(res_ke, "Wanjiru Kariuki")

