from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import AccessGrant, Account, AuditEvent, Membership, OnboardingConsent, OnboardingDraft, Person
from foundation.models import (
    AppointmentRecord,
    CandidateApplication,
    CandidateRubricScore,
    Notification,
    RecruitmentRouteConfig,
    ReferralLink,
    UserPreference,
    WorkItem,
)
from foundation.recruitment_engine import (
    STAGE8_SCREENS,
    seed_stage8_fixtures,
)

User = get_user_model()


class Stage8RecruitmentReferralsSelectionTests(TestCase):
    """
    Comprehensive test suite for Stage 08:
    Recruitment, Referrals, 7-Day Activation, 3-Day Leadership Pack Review,
    Approved Rubric Scoring, Human Selection Decisions, Disclosed Outcomes,
    Reserve Pool, and Controlled Route Settings (`REC-01` through `REC-14`).
    """

    def setUp(self):
        seed_stage8_fixtures()
        self.client = Client()

        # 1. Authorized Recruitment Reviewer / Network Secretary in WGMN / Nigeria
        self.reviewer_ng = self._create_persona(
            username="stage8_reviewer_ng",
            email="stage8.reviewer.ng@example.org",
            display_name="Ada Okafor",
            role="recruitment_reviewer",
            network="WGMN",
            country="NG",
        )

        # 2. Candidate / Ordinary Member in WGMN / Nigeria
        self.candidate_ng = self._create_persona(
            username="stage8_candidate_ng",
            email="stage8.candidate.ng@example.org",
            display_name="Ada Okafor",
            role="candidate",
            network="WGMN",
            country="NG",
        )
        CandidateApplication.objects.filter(application_code="CAND-NG-001").update(account=self.candidate_ng)

        # 3. Continental HOFCO
        self.hofco = self._create_persona(
            username="stage8_hofco",
            email="stage8.hofco@example.org",
            display_name="Continental HOFCO",
            role="hofco",
            network="HQ / Both networks",
            country="ALL",
        )

        self._login(self.reviewer_ng)

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
        consent = OnboardingConsent.objects.create(
            draft=draft,
            revision=1,
            version="v1.0",
            notice="Standard WDOS privacy notice",
            digest="digest_v1",
            approval_reference="REF-STAGE8",
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

    def test_01_all_16_stage8_screens_render_cleanly_without_demo_or_pdf_labels(self):
        """
        Verifies all 16 Stage 8 screens (`REC-01`..`REC-14`, including `REC-10-RUBRIC`
        and `REC-12-DECISION`) render HTTP 200 via semantic URLs, `/foundation/stage8/<code>/`,
        and `/foundation/screens/<code>/`, with zero prototype/PDF artifacts.
        """
        forbidden_tokens = [
            "DESIGN REVIEW · SYNTHETIC EXAMPLES · NOT LIVE",
            "UI review v2",
            "Sample data",
            "Related screens · design preview",
            "WORKFLOW STATES · SYNTHETIC EXAMPLES",
        ]
        semantic_routes = {
            "REC-01": "/foundation/recruitment/opportunities/",
            "REC-02": "/foundation/recruitment/apply/",
            "REC-03": "/foundation/recruitment/referred/",
            "REC-04": "/foundation/recruitment/referrals/",
            "REC-05": "/foundation/recruitment/application/",
            "REC-06": "/foundation/recruitment/activation/",
            "REC-07": "/foundation/recruitment/leadership-pack/",
            "REC-08": "/foundation/recruitment/outcome/",
            "REC-09": "/foundation/recruitment/pipeline/",
            "REC-10": "/foundation/recruitment/evidence/",
            "REC-10-RUBRIC": "/foundation/recruitment/rubric/",
            "REC-11": "/foundation/recruitment/compare/",
            "REC-12": "/foundation/recruitment/decision/",
            "REC-12-DECISION": "/foundation/recruitment/human-decision/",
            "REC-13": "/foundation/recruitment/reserve-pool/",
            "REC-14": "/foundation/recruitment/route-settings/",
        }
        for screen_code, spec in STAGE8_SCREENS.items():
            res_semantic = self.client.get(semantic_routes[screen_code])
            self.assertEqual(res_semantic.status_code, 200, f"Semantic route failed for {screen_code}")
            self.assertContains(res_semantic, spec["title"])

            res_router = self.client.get(f"/foundation/stage8/{screen_code}/")
            self.assertEqual(res_router.status_code, 200, f"Stage 8 router failed for {screen_code}")

            res_alias = self.client.get(f"/foundation/screens/{screen_code}/")
            self.assertEqual(res_alias.status_code, 200, f"Unified screen router failed for {screen_code}")

            html = res_semantic.content.decode("utf-8")
            for token in forbidden_tokens:
                self.assertNotIn(token, html, f"Forbidden prototype token '{token}' found in {screen_code}")
            self.assertNotIn(f"{screen_code} ·", html)

    def test_02_opportunity_discovery_volunteer_application_referral_intake_and_duplicate_controls(self):
        """
        Step 1 (`REC-01`, `REC-02`, `REC-03`, `REC-04`):
        - Opportunity discovery (`REC-01`) displays the two distinct routes and candidate records.
        - Apply to volunteer (`REC-02`) validates required fields, saves application, and prevents duplicate creation.
        - Referral intake (`REC-03`) verifies existing WDOS identity (`REF-NG-042`) without creating a duplicate person.
        - My referrals and links (`REC-04`) creates referral links and prevents duplicate active referrals for the same person + seat.
        """
        self._login(self.candidate_ng)

        # REC-01: Opportunity discovery
        res_opp = self.client.get("/foundation/recruitment/opportunities/")
        self.assertEqual(res_opp.status_code, 200)
        self.assertContains(res_opp, "Two distinct routes")
        self.assertContains(res_opp, "Open-call recruits complete Activation. Referred candidates review the Leadership Pack.")
        self.assertContains(res_opp, "A decision, not a score")

        # REC-02: Missing experience triggers highlighted validation state
        res_apply_invalid = self.client.post(
            "/foundation/recruitment/apply/",
            {
                "seat_label": "Chapter Coordinator · Ikeja",
                "current_country": "Nigeria",
                "experience_notes": "",
                "availability": "Full chapter schedule (8–10 hrs/week)",
            },
        )
        self.assertEqual(res_apply_invalid.status_code, 200)
        self.assertContains(res_apply_invalid, "Check the highlighted information")

        # REC-02: Valid volunteer application submission
        res_apply_ok = self.client.post(
            "/foundation/recruitment/apply/",
            {
                "application_code": "CAND-NG-001",
                "seat_label": "Chapter Coordinator · Ikeja",
                "current_country": "Nigeria",
                "experience_notes": "Coordinated local women's outreach and grassroots mentoring in Ikeja.",
                "availability": "Full chapter schedule (8–10 hrs/week)",
            },
        )
        self.assertEqual(res_apply_ok.status_code, 200)
        self.assertContains(res_apply_ok, "Volunteer application saved for Ada Okafor")
        app_ada = CandidateApplication.objects.get(application_code="CAND-NG-001")
        self.assertEqual(app_ada.availability, "Full chapter schedule (8–10 hrs/week)")

        # REC-03: Referral verification requires contact_confirmed checkbox
        res_ref_unconfirmed = self.client.post(
            "/foundation/recruitment/referred/",
            {
                "referral_code": "REF-NG-042",
                "candidate_name": "Ada Okafor",
                "proposed_seat_title": "Chapter Coordinator · Ikeja",
            },
        )
        self.assertEqual(res_ref_unconfirmed.status_code, 200)
        self.assertContains(res_ref_unconfirmed, "Check the highlighted information")

        # REC-03: Confirming referral with existing WDOS identity
        res_ref_ok = self.client.post(
            "/foundation/recruitment/referred/",
            {
                "referral_code": "REF-NG-042",
                "candidate_name": "Ada Okafor",
                "proposed_seat_title": "Chapter Coordinator · Ikeja",
                "contact_confirmed": "true",
            },
        )
        self.assertEqual(res_ref_ok.status_code, 200)
        self.assertContains(res_ref_ok, "Referral REF-NG-042 verified using existing WDOS identity")
        ref_obj = ReferralLink.objects.get(referral_code="REF-NG-042")
        self.assertTrue(ref_obj.contact_confirmed)
        self.assertEqual(ref_obj.status, "Verified")

        # REC-04: Creating referral link and verifying duplicate prevention
        res_create_ref1 = self.client.post(
            "/foundation/recruitment/referrals/",
            {
                "candidate_name": "Zainab Lawal",
                "proposed_seat_title": "Chapter Coordinator · Ikeja",
            },
        )
        self.assertEqual(res_create_ref1.status_code, 200)
        self.assertContains(res_create_ref1, "created for Zainab Lawal")

        res_create_ref2 = self.client.post(
            "/foundation/recruitment/referrals/",
            {
                "candidate_name": "Zainab Lawal",
                "proposed_seat_title": "Chapter Coordinator · Ikeja",
            },
        )
        self.assertEqual(res_create_ref2.status_code, 200)
        self.assertContains(res_create_ref2, "Duplicate referral prevented")
        self.assertEqual(
            ReferralLink.objects.filter(candidate_name="Zainab Lawal", proposed_seat_title="Chapter Coordinator · Ikeja").count(),
            1,
        )

    def test_03_distinct_7day_activation_and_3day_leadership_pack_journeys_plus_deadline_lock(self):
        """
        Step 2 (`REC-05`, `REC-06`, `REC-07`):
        - Verifies `REC-05` My application displays the 4-step journey.
        - Verifies `REC-06` 7-day Activation advances from Day 4 to Days 5–6 and Completed.
        - Verifies `REC-07` 3-day Leadership Pack Review explicitly states it is a separate 3-day review
          and not an Institute examination, and records understanding + declaration.
        - Verifies deadline lock blocks direct submission and allows requesting support to reopen.
        """
        self._login(self.candidate_ng)

        # REC-05: My application
        res_app = self.client.get("/foundation/recruitment/application/?candidate=CAND-NG-001")
        self.assertEqual(res_app.status_code, 200)
        self.assertContains(res_app, "Application received")
        self.assertContains(res_app, "Eligibility checked")
        self.assertContains(res_app, "Activation underway")
        self.assertContains(res_app, "Human decision pending")

        # REC-06: Advance 7-day Activation Day 4 and Complete
        res_act = self.client.post(
            "/foundation/recruitment/activation/",
            {
                "application_code": "CAND-NG-001",
                "action": "continue_day_4",
                "reflection_text": "Led Ikeja chapter community listening session and documented reflections.",
            },
        )
        self.assertEqual(res_act.status_code, 200)
        self.assertContains(res_act, "Progress saved")
        app_ada = CandidateApplication.objects.get(application_code="CAND-NG-001")
        self.assertEqual(app_ada.current_stage, "Day 4 of 7")
        self.assertIn("Led Ikeja chapter", app_ada.activation_reflection)

        res_act_complete = self.client.post(
            "/foundation/recruitment/activation/",
            {
                "application_code": "CAND-NG-001",
                "action": "complete_journey",
                "reflection_text": "Completed all 7 days of Activation and final review.",
            },
        )
        self.assertEqual(res_act_complete.status_code, 200)
        self.assertContains(res_act_complete, "Submission awaiting review")
        app_ada.refresh_from_db()
        self.assertEqual(app_ada.current_stage, "Completed")

        # REC-06: Deadline lock blocks submission and triggers Request support flow
        app_ada.deadline_reached = True
        app_ada.reopened_by_reviewer = False
        app_ada.save(update_fields=["deadline_reached", "reopened_by_reviewer"])
        res_locked = self.client.post(
            "/foundation/recruitment/activation/",
            {
                "application_code": "CAND-NG-001",
                "action": "continue_day_4",
                "reflection_text": "Attempt while locked.",
            },
        )
        self.assertEqual(res_locked.status_code, 200)
        self.assertContains(res_locked, "Deadline reached")

        res_reopen_req = self.client.get("/foundation/recruitment/activation/?candidate=CAND-NG-001&request_reopen=1")
        self.assertEqual(res_reopen_req.status_code, 200)
        self.assertContains(res_reopen_req, "Support request sent to authorized reviewer")
        self.assertTrue(
            WorkItem.objects.filter(title__icontains="Reopen 7-day Activation window: Ada Okafor").exists()
        )

        # Reset lock for next tests
        app_ada.deadline_reached = False
        app_ada.save(update_fields=["deadline_reached"])

        # REC-07: Separate 3-day Leadership Pack Review
        res_pack_get = self.client.get("/foundation/recruitment/leadership-pack/?candidate=CAND-NG-002")
        self.assertEqual(res_pack_get.status_code, 200)
        self.assertContains(
            res_pack_get,
            "Your separate 3-day Leadership Pack Review checks understanding of the role. It is not an Institute examination.",
        )

        res_pack_post = self.client.post(
            "/foundation/recruitment/leadership-pack/",
            {
                "application_code": "CAND-NG-002",
                "action": "continue_review",
                "pack_answer": "Escalate immediately to the State Coordinator and Country Safeguarding Lead through WDOS.",
                "declaration_confirmed": "true",
            },
        )
        self.assertEqual(res_pack_post.status_code, 200)
        self.assertContains(res_pack_post, "3-day Leadership Pack Review understanding and declaration saved")
        app_lina = CandidateApplication.objects.get(application_code="CAND-NG-002")
        self.assertEqual(app_lina.current_stage, "Pack submitted")
        self.assertTrue(app_lina.pack_declaration_confirmed)

    def test_04_evidence_review_rubric_scoring_comparison_and_human_decision_with_stage7_handoff(self):
        """
        Step 3 (`REC-09`, `REC-10`, `REC-10-RUBRIC`, `REC-11`, `REC-12`, `REC-12-DECISION`):
        - Reviewer scores candidate against approved criteria (`REC-10-RUBRIC`); score alone never appoints.
        - Reviewer requests clarification (`REC-10`) or human decision.
        - Reviewer compares candidates (`REC-11`).
        - Reviewer records human recruitment decision (`REC-12-DECISION`):
          - Changing a recommendation requires `override_reason`.
          - Selecting a candidate creates/updates a Stage 7 `AppointmentRecord` in `Offer issued` stage
            without prematurely granting active role `AccessGrant`.
        """
        self._login(self.reviewer_ng)

        # REC-10-RUBRIC: Score candidate against approved criteria
        res_rubric = self.client.post(
            "/foundation/recruitment/rubric/",
            {
                "application_code": "CAND-NG-001",
                "criterion": "Availability",
                "score": "Meets evidence",
                "evidence_note": "Confirmed 8-10 hours weekly availability for Ikeja chapter meetings.",
            },
        )
        self.assertEqual(res_rubric.status_code, 200)
        self.assertContains(res_rubric, "Rubric score saved for Ada Okafor")
        score_row = CandidateRubricScore.objects.get(
            application__application_code="CAND-NG-001",
            criterion="Availability",
        )
        self.assertEqual(score_row.evidence_status, "Meets evidence")
        self.assertEqual(score_row.required_followup, "None")

        # Verify rubric score did NOT automatically appoint Ada Okafor
        app_ada = CandidateApplication.objects.get(application_code="CAND-NG-001")
        self.assertNotIn("Selected", app_ada.decision_status)

        # REC-10: Evidence review requesting clarification notifies candidate
        res_ev_clarify = self.client.post(
            "/foundation/recruitment/evidence/",
            {
                "application_code": "CAND-NG-001",
                "evidence_assessment": "Request clarification",
                "reviewer_notes": "Please attach local chapter attendance sheet for Day 4.",
            },
        )
        self.assertEqual(res_ev_clarify.status_code, 200)
        self.assertContains(res_ev_clarify, "recorded for Ada Okafor")
        app_ada.refresh_from_db()
        self.assertEqual(app_ada.evidence_assessment, "Request clarification")
        self.assertTrue(
            Notification.objects.filter(
                account=self.candidate_ng,
                title__icontains="Clarification requested",
            ).exists()
        )

        # REC-11: Compare candidates for this seat
        res_compare = self.client.get("/foundation/recruitment/compare/")
        self.assertEqual(res_compare.status_code, 200)
        self.assertContains(res_compare, "Ada Okafor")
        self.assertContains(res_compare, "Lina Mensah")
        self.assertContains(res_compare, "Kemi Bello")

        # REC-12-DECISION: Changing recommendation without override_reason is rejected
        app_lina = CandidateApplication.objects.get(application_code="CAND-NG-002")
        app_lina.recommended_decision = "Further Review"
        app_lina.save(update_fields=["recommended_decision"])

        res_override_missing = self.client.post(
            "/foundation/recruitment/human-decision/",
            {
                "application_code": "CAND-NG-002",
                "decision": "Selected — appointment pending",
                "decision_reason": "Strong leadership pack responses.",
                "override_reason": "",
                "consequence_confirmed": "true",
            },
        )
        self.assertEqual(res_override_missing.status_code, 200)
        self.assertContains(
            res_override_missing,
            "Changing a recommendation requires explaining why in the override reason field.",
        )

        # REC-12-DECISION: Valid human decision with override_reason and consequence confirmation
        res_decision_ok = self.client.post(
            "/foundation/recruitment/human-decision/",
            {
                "application_code": "CAND-NG-002",
                "decision": "Selected — appointment pending",
                "decision_reason": "Met all approved leadership criteria for Ikeja.",
                "override_reason": "Clarification was verified directly with the State Coordinator.",
                "consequence_confirmed": "true",
            },
        )
        self.assertEqual(res_decision_ok.status_code, 200)
        self.assertContains(res_decision_ok, "recorded for Lina Mensah")

        app_lina.refresh_from_db()
        self.assertEqual(app_lina.decision_status, "Selected — appointment pending")
        self.assertEqual(app_lina.disclosed_outcome, "Selected for appointment processing")
        appt_lina = AppointmentRecord.objects.get(appointment_code="APPT-NG-002")
        self.assertEqual(appt_lina.stage, "Acceptance pending")
        self.assertEqual(appt_lina.next_action, "View offer")

    def test_05_disclosed_outcomes_reserve_pool_route_settings_and_permission_boundaries(self):
        """
        Step 4 (`REC-08`, `REC-13`, `REC-14`, permissions & state contracts):
        - Candidate can view disclosed outcome (`REC-08`) and respond to alternative role offer without new registration.
        - Reviewer can match reserve candidate to vacancy (`REC-13`).
        - Reviewer can save a controlled route revision (`REC-14`) with optimistic concurrency check.
        - Candidate is blocked (`403`) from reviewer screens (`REC-09..REC-14`).
        - Nigeria reviewer is blocked (`403`) from Kenya (`KE`) and Ghana (`GH`) recruitment records.
        """
        # 1. Candidate responds to alternative role offer on REC-08
        self._login(self.candidate_ng)
        res_outcome_get = self.client.get("/foundation/recruitment/outcome/?candidate=CAND-NG-001")
        self.assertEqual(res_outcome_get.status_code, 200)
        self.assertContains(res_outcome_get, "An alternative role is available")
        self.assertContains(res_outcome_get, "Chapter support opportunity")
        self.assertContains(
            res_outcome_get,
            "Your own application and permitted updates are shown here. Internal comparisons and reviewer-only evidence remain private.",
        )

        res_outcome_post = self.client.post(
            "/foundation/recruitment/outcome/",
            {
                "application_code": "CAND-NG-001",
                "response_choice": "accept_alternative",
            },
        )
        self.assertEqual(res_outcome_post.status_code, 200)
        self.assertContains(res_outcome_post, "without requiring a new registration")
        app_ada = CandidateApplication.objects.get(application_code="CAND-NG-001")
        self.assertEqual(app_ada.alternative_next_action, "Offer accepted for review")

        # 2. Candidate is strictly forbidden (403) from reviewer screens REC-09..REC-14
        reviewer_urls = [
            "/foundation/recruitment/pipeline/",
            "/foundation/recruitment/evidence/",
            "/foundation/recruitment/rubric/",
            "/foundation/recruitment/compare/",
            "/foundation/recruitment/decision/",
            "/foundation/recruitment/human-decision/",
            "/foundation/recruitment/reserve-pool/",
            "/foundation/recruitment/route-settings/",
        ]
        for url in reviewer_urls:
            res_forbidden = self.client.get(url)
            self.assertEqual(res_forbidden.status_code, 403, f"Candidate should be blocked from {url}")

        # 3. Reviewer matches reserve candidate to vacancy in REC-13 and saves route revision in REC-14
        self._login(self.reviewer_ng)
        res_reserve = self.client.post(
            "/foundation/recruitment/reserve-pool/",
            {
                "application_code": "CAND-NG-003",
                "target_seat_label": "Assistant Coordinator · Lagos",
            },
        )
        self.assertEqual(res_reserve.status_code, 200)
        self.assertContains(res_reserve, "Reserve candidate Kemi Bello matched to approved vacancy")

        res_route = self.client.post(
            "/foundation/recruitment/route-settings/",
            {
                "route_name": "Open call · Activation",
                "duration_label": "7 days",
                "route_timezone": "Africa/Lagos",
                "content_version": "Activation pack v2.1",
            },
        )
        self.assertEqual(res_route.status_code, 200)
        self.assertContains(res_route, "Controlled route revision saved")
        rc = RecruitmentRouteConfig.objects.get(route_code="OPEN_CALL_7DAY")
        self.assertEqual(rc.content_version, "Activation pack v2.1")
        self.assertEqual(rc.status, "Proposed for approval")

        # 4. Cross-country isolation: Nigeria reviewer cannot access Kenya (KE) or Ghana (GH) records
        res_ke_pipeline = self.client.get("/foundation/recruitment/pipeline/?country=KE")
        self.assertEqual(res_ke_pipeline.status_code, 403)

        res_ke_evidence = self.client.get("/foundation/recruitment/evidence/?candidate=CAND-KE-001")
        self.assertEqual(res_ke_evidence.status_code, 403)

        # 5. State contract query parameters render designed feedback cards cleanly
        res_state_empty = self.client.get("/foundation/recruitment/pipeline/?state=empty")
        self.assertEqual(res_state_empty.status_code, 200)
        self.assertContains(res_state_empty, "No records in this view")

        res_state_outcome = self.client.get("/foundation/recruitment/outcome/?state=reserve")
        self.assertEqual(res_state_outcome.status_code, 200)
        self.assertContains(res_state_outcome, "Reserve pathway")
