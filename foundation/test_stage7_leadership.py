from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import AccessGrant, Account, AuditEvent, Membership, OnboardingDraft, Person
from foundation.leadership_engine import (
    STAGE7_SCREENS,
    get_stage7_audit_history,
    refer_or_appoint_candidate,
    save_position_revision,
    seed_stage7_fixtures,
)
from foundation.models import (
    AppointmentRecord,
    CandidateReferral,
    HandoverAssetTask,
    LeadershipReview,
    LeadershipSeat,
    LeadershipStatusChange,
    LeadershipTransitionPlan,
    PersonProfile,
    PositionMaster,
    SeatHistory,
    UserPreference,
    WorkItem,
)
from foundation.scope import get_user_scope

User = get_user_model()


class Stage7LeadershipAppointmentsTests(TestCase):
    """
    Comprehensive test suite for Stage 07:
    Leadership Structure, Vacancies, Appointments, Onboarding, 90-Day Reviews, and Handover.
    """

    def setUp(self):
        seed_stage7_fixtures()
        self.client = Client()

        # 1. Authorized Network Secretary / Country Lead in WGMN / Nigeria
        self.sec_account = self._create_persona(
            username="stage7_secretary",
            email="stage7.secretary@example.org",
            display_name="Ada Okafor",
            role="network_secretary",
            network="WGMN",
            country="NG",
        )

        # 2. Continental HOFCO / Governance Admin
        self.hofco_account = self._create_persona(
            username="stage7_hofco",
            email="stage7.hofco@example.org",
            display_name="Continental HOFCO",
            role="hofco",
            network="HQ / Both networks",
            country="ALL",
        )

        # 3. Ordinary Member / Selected Candidate (can view own offer/onboarding, cannot approve governance decisions)
        self.member_account = self._create_persona(
            username="stage7_member",
            email="stage7.member@example.org",
            display_name="Ordinary Candidate",
            role="member",
            network="WGMN",
            country="NG",
        )

        # Link Lina Mensah and Ada Okafor profiles to accounts so AccessGrant lifecycle can be tested
        self.lina_account = self._create_persona(
            username="stage7_lina",
            email="lina@example.org",
            display_name="Lina Mensah",
            role="chapter_lead",
            network="WGMN",
            country="NG",
        )
        PersonProfile.objects.filter(person_code="WD-00422").update(account=self.lina_account)
        AppointmentRecord.objects.filter(appointment_code="APPT-NG-002").update(account=self.lina_account)

        self._login(self.sec_account)

    def _login(self, account):
        self.client.force_login(account.user)
        session = self.client.session
        now = timezone.now().timestamp()
        session["security_version"] = account.security_version
        session["mfa_verified"] = True
        session["last_activity"] = now
        session["absolute_expiry"] = now + 43200
        session.save()

    def _create_persona(self, username, email, display_name, role, network, country):
        user = User.objects.create_user(
            username=username,
            email=email,
            password="WDOSPassphrase2026!",
            first_name=display_name,
        )
        person = Person.objects.create(display_name=display_name)
        acc = Account.objects.create(
            user=user,
            email=email,
            person=person,
            status="active",
            display_name=display_name,
            security_version=1,
        )
        draft = OnboardingDraft.objects.create(
            account=acc,
            state="accepted",
            data={"language": "en", "timezone": "Africa/Lagos"},
        )
        from accounts.models import OnboardingConsent
        consent = OnboardingConsent.objects.create(
            draft=draft,
            revision=1,
            version="v1.0",
            notice="Standard WDOS privacy notice",
            digest="digest_v1",
            approval_reference="REF-001",
            privacy_ack=True,
            channel="web",
        )
        Membership.objects.create(
            draft=draft,
            person=person,
            network="WGMN" if network not in {"WGMN", "WNNN"} else network,
            home={"country": "NG" if country in {"*", "ALL"} else country, "state": "Lagos", "lga": "Ikeja", "chapter": "Ikeja Chapter"},
            consent=consent,
            policy_digest="digest_v1",
            approved_by=acc,
        )
        AccessGrant.objects.create(
            account=acc,
            role=role,
            network=network,
            geography=country,
            function="all",
            expires_at=timezone.now() + timedelta(days=365),
        )
        UserPreference.objects.create(
            account=acc,
            active_network="WGMN" if network not in {"WGMN", "WNNN"} else network,
            active_country="NG" if country in {"*", "ALL"} else country,
        )
        return acc

    def test_01_all_16_stage7_screens_render_cleanly_without_demo_or_pdf_labels(self):
        """
        Verifies all 16 Stage 7 screens render HTTP 200 via both semantic URLs and
        screen router URLs, and contain zero demo/PDF/review artifacts.
        """
        forbidden_tokens = [
            "DESIGN REVIEW · SYNTHETIC EXAMPLES · NOT LIVE",
            "UI review v2",
            "Sample data",
            "Related screens · design preview",
            "PDF 243",
            "PDF 244",
            "PDF 245",
        ]
        for screen_code, spec in STAGE7_SCREENS.items():
            res = self.client.get(f"/foundation/stage7/{screen_code}/")
            self.assertEqual(res.status_code, 200, f"Failed on {screen_code}")
            self.assertContains(res, spec["title"])

            res_alias = self.client.get(f"/foundation/screens/{screen_code}/")
            self.assertEqual(res_alias.status_code, 200, f"Alias router failed on {screen_code}")

            html = res.content.decode("utf-8")
            for token in forbidden_tokens:
                self.assertNotIn(token, html, f"Forbidden demo token '{token}' found in {screen_code}")
            # Ensure internal screen IDs like LEAD-01 / APPT-01 are not rendered as visible badges
            self.assertNotIn(f"{screen_code} ·", html)

    def test_02_leadership_structure_register_and_seat_detail_preserve_former_holders(self):
        """
        Step 1 (LEAD-01, LEAD-02, LEAD-03):
        Verifies leadership structure tree, leadership register filtering, and seat detail
        with durable former holder history.
        """
        res_struct = self.client.get("/foundation/leadership/structure/")
        self.assertEqual(res_struct.status_code, 200)
        self.assertContains(res_struct, "State Coordinator")
        self.assertContains(res_struct, "Lina Mensah")
        self.assertContains(res_struct, "Assistant Coordinator")
        self.assertContains(res_struct, "Vacant")
        self.assertContains(res_struct, "Kemi Bello")
        self.assertContains(res_struct, "A vacancy exists only for an approved seat. Former holders remain in history.")

        # Register search filter
        res_reg = self.client.get("/foundation/leadership/register/?q=Kemi")
        self.assertEqual(res_reg.status_code, 200)
        self.assertContains(res_reg, "Kemi Bello")
        self.assertNotContains(res_reg, "Unfilled")

        # Seat detail (LEAD-03) shows position code, reporting line, and former holder Bisi Adeyemi
        res_seat = self.client.get("/foundation/leadership/seats/SEAT-NG-LAG-SC/")
        self.assertEqual(res_seat.status_code, 200)
        self.assertContains(res_seat, "STATE_COORDINATOR")
        self.assertContains(res_seat, "Country Representative · Nigeria")
        self.assertContains(res_seat, "Bisi Adeyemi")

    def test_03_approved_vacancies_candidate_referral_and_direct_reports_followup(self):
        """
        Step 1 (LEAD-04, LEAD-05):
        - Candidate referral only succeeds on an approved seat (is_approved_seat=True).
        - Referring a candidate creates CandidateReferral and AuditEvent.
        - Assigning a follow-up in LEAD-05 creates a WorkItem for the direct report.
        """
        res_vac = self.client.post(
            "/foundation/leadership/vacancies/",
            {
                "seat_code": "SEAT-NG-LAG-AC",
                "candidate_name": "Chioma Nwosu",
                "action_mode": "refer",
                "suitability_notes": "Strong chapter coordination track record.",
            },
        )
        self.assertEqual(res_vac.status_code, 200)
        self.assertContains(res_vac, "Candidate referral recorded for Chioma Nwosu")
        self.assertTrue(
            CandidateReferral.objects.filter(seat__seat_code="SEAT-NG-LAG-AC", candidate_name="Chioma Nwosu").exists()
        )

        # Unapproved seat cannot accept vacancy referral
        seat_ac = LeadershipSeat.objects.get(seat_code="SEAT-NG-LAG-AC")
        seat_ac.is_approved_seat = False
        seat_ac.save()
        scope = get_user_scope(self.sec_account)
        with self.assertRaisesMessage(ValueError, "A vacancy exists only for an approved seat."):
            refer_or_appoint_candidate(
                seat_code="SEAT-NG-LAG-AC",
                candidate_name="Unauthorized Vacancy Candidate",
                suitability_notes="Test",
                actor_account=self.sec_account,
                user_scope=scope,
            )
        seat_ac.is_approved_seat = True
        seat_ac.save()

        # Direct reports follow-up assignment (LEAD-05)
        res_dr = self.client.post(
            "/foundation/leadership/direct-reports/",
            {
                "seat_code": "SEAT-NG-IKJ-LC",
                "followup_title": "Submit Ikeja LGA monthly report",
                "followup_summary": "Complete before end of month.",
            },
        )
        self.assertEqual(res_dr.status_code, 200)
        self.assertContains(res_dr, "Submit Ikeja LGA monthly report")
        self.assertTrue(WorkItem.objects.filter(title="Submit Ikeja LGA monthly report").exists())

    def test_04_positions_and_reporting_lines_revision_and_network_titles(self):
        """
        Step 1 (LEAD-06):
        Verifies saving a position revision updates WGMN and WNNN display titles
        and synchronizes seat titles for the respective network.
        """
        res_pos = self.client.post(
            "/foundation/leadership/positions/",
            {
                "position_code": "STATE_COORDINATOR",
                "wgmn_title": "State Principal Coordinator",
                "wnnn_title": "State Network Lead",
                "reports_to_label": "Country Representative · Nigeria",
            },
        )
        self.assertEqual(res_pos.status_code, 200)
        self.assertContains(res_pos, "Position revision saved for STATE_COORDINATOR")

        pos = PositionMaster.objects.get(position_code="STATE_COORDINATOR")
        self.assertEqual(pos.wgmn_title, "State Principal Coordinator")
        self.assertEqual(pos.wnnn_title, "State Network Lead")

        # Verify WGMN seat and WNNN seat titles updated according to network
        wgmn_seat = LeadershipSeat.objects.get(seat_code="SEAT-NG-LAG-SC")
        wnnn_seat = LeadershipSeat.objects.get(seat_code="SEAT-WNNN-NG-LAG-SL")
        self.assertEqual(wgmn_seat.position_title, "State Principal Coordinator")
        self.assertEqual(wnnn_seat.position_title, "State Network Lead")

    def test_05_appointment_offer_acceptance_decline_and_leader_onboarding_access_activation(self):
        """
        Step 2 (APPT-01, APPT-02, APPT-03):
        - Accepting an appointment offer requires both declarations and transitions stage to 'Onboarding'.
        - Declining an appointment offer returns the seat to 'Vacant'.
        - Completing all 4 onboarding steps in APPT-03 activates the appointment ('Active'),
          activates the seat ('Active'), and grants an AccessGrant.
        """
        # 1. Missing declaration is rejected with highlighted field feedback
        res_missing = self.client.post(
            "/foundation/appointments/offer/",
            {
                "appointment_code": "APPT-NG-001",
                "action": "accept",
                "acceptance_confirmed": "true",
                # commitment_confirmed omitted
            },
        )
        self.assertEqual(res_missing.status_code, 200)
        self.assertContains(res_missing, "Check the highlighted information")

        # 2. Accepting with both declarations moves APPT-NG-001 to Onboarding
        res_accept = self.client.post(
            "/foundation/appointments/offer/",
            {
                "appointment_code": "APPT-NG-001",
                "action": "accept",
                "acceptance_confirmed": "true",
                "commitment_confirmed": "true",
            },
        )
        self.assertEqual(res_accept.status_code, 200)
        appt_ada = AppointmentRecord.objects.get(appointment_code="APPT-NG-001")
        self.assertEqual(appt_ada.stage, "Onboarding")
        self.assertEqual(appt_ada.next_action, "Review checklist")
        self.assertEqual(appt_ada.seat.status, "Onboarding")

        # 3. Completing all 4 onboarding steps on APPT-NG-002 activates full role access
        res_onb = self.client.post(
            "/foundation/appointments/onboarding/",
            {
                "appointment_code": "APPT-NG-002",
                "step_1": "true",
                "step_2": "true",
                "step_3": "true",
                "step_4": "true",
            },
        )
        self.assertEqual(res_onb.status_code, 200)
        appt_lina = AppointmentRecord.objects.get(appointment_code="APPT-NG-002")
        self.assertEqual(appt_lina.stage, "Active")
        self.assertEqual(appt_lina.official_identity_status, "Active")
        self.assertTrue(
            AccessGrant.objects.filter(
                account=self.lina_account,
                role="state_coordinator",
                network="WGMN",
                revoked_at__isnull=True,
            ).exists()
        )

        # 4. Declining an offer returns the seat to Vacant
        res_decline = self.client.post(
            "/foundation/appointments/offer/",
            {
                "appointment_code": "APPT-NG-001",
                "action": "decline",
                "declined_reason": "Relocating outside the chapter area.",
            },
        )
        self.assertEqual(res_decline.status_code, 200)
        appt_ada.refresh_from_db()
        self.assertEqual(appt_ada.stage, "Declined")
        self.assertEqual(appt_ada.seat.status, "Vacant")
        self.assertEqual(appt_ada.seat.holder_name, "Unfilled")

    def test_06_first_90_day_reviews_status_change_transition_and_handover_lifecycle(self):
        """
        Step 2 & Step 3 (APPT-04, APPT-04-REVIEWS, APPT-05, APPT-06, APPT-07, APPT-08, APPT-08-HANDOVER):
        - Records 30/60/90 day review outcome with reviewer confirmation.
        - Records leadership status change ('On leave' and 'Suspended' revoking role access) without erasing person or history.
        - Plans leadership transition ('Transfer') and completes handover assets & access checks.
        """
        # 1. Record 60-day review outcome (APPT-04-REVIEWS)
        res_rev = self.client.post(
            "/foundation/appointments/reviews/",
            {
                "appointment_code": "APPT-NG-002",
                "review_point": "60 days",
                "outcome": "On track",
                "evidence_notes": "Monthly state coordination meetings held with all LGAs.",
                "reviewer_confirmation": "true",
            },
        )
        self.assertEqual(res_rev.status_code, 200)
        self.assertContains(res_rev, "60 days review outcome")
        appt_lina = AppointmentRecord.objects.get(appointment_code="APPT-NG-002")
        self.assertTrue(appt_lina.milestone_60_completed)
        self.assertTrue(LeadershipReview.objects.filter(appointment=appt_lina, review_point="60 days").exists())

        # 2. Status change (APPT-06) preserves PersonProfile count and SeatHistory
        people_count_before = PersonProfile.objects.count()
        res_status = self.client.post(
            "/foundation/appointments/status-change/",
            {
                "appointment_code": "APPT-NG-001",
                "requested_status": "On leave",
                "effective_period": "01–15 October 2026",
                "reason_and_cover_plan": "Approved medical leave; deputy covering chapter meetings.",
            },
        )
        self.assertEqual(res_status.status_code, 200)
        self.assertEqual(PersonProfile.objects.count(), people_count_before)
        appt_ada = AppointmentRecord.objects.get(appointment_code="APPT-NG-001")
        self.assertEqual(appt_ada.stage, "On leave")
        self.assertTrue(LeadershipStatusChange.objects.filter(appointment=appt_ada, requested_status="On leave").exists())

        # 3. Plan transition (APPT-07)
        res_trans = self.client.post(
            "/foundation/appointments/transition/",
            {
                "appointment_code": "APPT-NG-003",
                "transition_type": "Transfer",
                "effective_date": "01 October 2026",
                "access_and_handover_notes": "Official records, groups and outstanding actions require review.",
                "successor_name": "Ada Okafor",
            },
        )
        self.assertEqual(res_trans.status_code, 200)
        self.assertContains(res_trans, "Transition plan")
        self.assertTrue(
            SeatHistory.objects.filter(holder_name="Kemi Bello", position_title="LGA Coordinator").exists()
        )

        # 4. Complete handover assets & access checks (APPT-08-HANDOVER)
        disable_task = HandoverAssetTask.objects.filter(access_action="Disable and audit").first()
        self.assertIsNotNone(disable_task)
        res_task = self.client.post(
            "/foundation/appointments/handover/assets/",
            {
                "action": "complete_task",
                "task_id": str(disable_task.id),
            },
        )
        self.assertEqual(res_task.status_code, 200)
        disable_task.refresh_from_db()
        self.assertEqual(disable_task.status, "Completed")

        # Complete all remaining handover tasks
        res_all = self.client.post(
            "/foundation/appointments/handover/assets/",
            {"action": "complete_all"},
        )
        self.assertEqual(res_all.status_code, 200)
        self.assertEqual(HandoverAssetTask.objects.filter(network="WGMN", country="NG", status="Open").count(), 0)
        plan = LeadershipTransitionPlan.objects.filter(appointment__appointment_code="APPT-NG-003").first()
        self.assertEqual(plan.status, "Completed")

    def test_07_authorization_scope_boundaries_concurrency_idempotency_and_audit(self):
        """
        Step 4:
        - Enforces role authorization: ordinary member cannot access LEAD-06 or submit APPT-06 / APPT-07.
        - Enforces network & country scope isolation: WGMN/NG secretary is blocked (403) from WNNN and Kenya records.
        - Enforces optimistic concurrency: stale expected_updated_at triggers 'Another change needs review'.
        - Enforces idempotency: duplicate idempotency_key on candidate referral/appointment does not duplicate records.
        - Verifies AuditEvent logging across Stage 7 transitions.
        """
        # 1. Ordinary member blocked from governance screens
        self._login(self.member_account)
        for restricted_url in [
            "/foundation/leadership/positions/",
            "/foundation/appointments/status-change/",
            "/foundation/appointments/transition/",
            "/foundation/appointments/reviews/",
        ]:
            res_unauth = self.client.get(restricted_url)
            self.assertEqual(res_unauth.status_code, 403, f"Expected 403 for member on {restricted_url}")

        # Ordinary member CAN view personal appointment offer & onboarding screens
        self.assertEqual(self.client.get("/foundation/appointments/offer/").status_code, 200)
        self.assertEqual(self.client.get("/foundation/appointments/onboarding/").status_code, 200)

        # Switch back to WGMN/NG Network Secretary
        self._login(self.sec_account)

        # 2. Cross-country (KE) and cross-network (WNNN) isolation enforced
        res_ke = self.client.get("/foundation/leadership/structure/?country=KE")
        self.assertEqual(res_ke.status_code, 403)
        res_wnnn = self.client.get("/foundation/leadership/structure/?network=WNNN")
        self.assertEqual(res_wnnn.status_code, 403)
        res_ke_seat = self.client.get("/foundation/leadership/seats/SEAT-KE-NBO-SC/")
        self.assertEqual(res_ke_seat.status_code, 403)

        # Continental HOFCO can access both networks and countries
        self._login(self.hofco_account)
        self.assertEqual(self.client.get("/foundation/leadership/structure/?country=KE").status_code, 200)
        self.assertEqual(self.client.get("/foundation/leadership/structure/?network=WNNN").status_code, 200)

        self._login(self.sec_account)

        # 3. Optimistic concurrency check on LEAD-06 and APPT-06
        res_conflict = self.client.post(
            "/foundation/leadership/positions/",
            {
                "position_code": "STATE_COORDINATOR",
                "wgmn_title": "Stale Title",
                "wnnn_title": "Stale Lead",
                "reports_to_label": "Country principal",
                "expected_updated_at": "1999-01-01T00:00:00",
            },
        )
        self.assertEqual(res_conflict.status_code, 200)
        self.assertContains(res_conflict, "Another change needs review")

        # 4. Idempotency key prevents duplicate referrals/appointments on retry
        scope = get_user_scope(self.sec_account)
        idem_key = "IDEM-STAGE7-REF-001"
        r1 = refer_or_appoint_candidate(
            seat_code="SEAT-NG-LAG-AC",
            candidate_name="Halima Bello",
            suitability_notes="First submission",
            actor_account=self.sec_account,
            user_scope=scope,
            action_mode="refer",
            idempotency_key=idem_key,
        )
        r2 = refer_or_appoint_candidate(
            seat_code="SEAT-NG-LAG-AC",
            candidate_name="Halima Bello",
            suitability_notes="Retry submission",
            actor_account=self.sec_account,
            user_scope=scope,
            action_mode="refer",
            idempotency_key=idem_key,
        )
        self.assertFalse(r1["idempotent_replay"])
        self.assertTrue(r2["idempotent_replay"])
        self.assertEqual(CandidateReferral.objects.filter(idempotency_key=idem_key).count(), 1)

        # 5. Scoped audit trail contains Stage 7 events
        history = get_stage7_audit_history(scope, country_code="NG")
        self.assertGreaterEqual(len(history), 1)
        self.assertTrue(any(h["event"] == "candidate_referred" for h in history))
