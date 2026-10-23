"""
Comprehensive automated tests for WDOS Stage 09:
Tasks, Calendar, and Meeting Administration (TASK-01..TASK-04, MTG-01..MTG-06).
"""

from datetime import timedelta
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import (
    AccessGrant,
    Account,
    AuditEvent,
    Membership,
    OnboardingConsent,
    OnboardingDraft,
    Person,
)
from .models import (
    MeetingDecisionAction,
    MeetingParticipantRecord,
    MeetingSeries,
    MissionControlTask,
    Notification,
    TaskLifecycleEntry,
    UserPreference,
    WorkItem,
)
from .tasks_meetings_engine import STAGE9_SCREENS, seed_stage9_fixtures

User = get_user_model()


class Stage9TasksMeetingsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.reviewer_account = cls._create_persona(
            username="stage9_reviewer",
            email="state.lagos@example.org",
            display_name="Lina Mensah",
            role="state_coordinator",
            network="WGMN",
            country="NG",
        )
        cls.member_account = cls._create_persona(
            username="stage9_member",
            email="member.ada@example.org",
            display_name="Ada Okafor",
            role="member",
            network="WGMN",
            country="NG",
        )
        cls.candidate_account = cls._create_persona(
            username="stage9_candidate",
            email="candidate.john@example.org",
            display_name="John Kalu",
            role="candidate",
            network="WGMN",
            country="NG",
            is_candidate=True,
        )
        seed_stage9_fixtures(network="WGMN", country="NG", actor_account=cls.reviewer_account)
        MissionControlTask.objects.filter(task_code="TASK-NG-001").update(
            owner_account=cls.member_account,
            reviewer_account=cls.reviewer_account,
        )

    @classmethod
    def _create_persona(cls, username, email, display_name, role, network, country, is_candidate=False):
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
            verified_at=timezone.now(),
        )
        draft = OnboardingDraft.objects.create(
            account=acc,
            state="review_needed" if is_candidate else "accepted",
            next_step=6 if is_candidate else 8,
            data={"language": "en", "timezone": "Africa/Lagos", "network": network, "country": country},
        )
        consent = OnboardingConsent.objects.create(
            draft=draft,
            revision=1,
            version="v1.0",
            notice="Standard WDOS privacy notice",
            digest="digest_v1",
            approval_reference="REF-STAGE9",
            privacy_ack=True,
            channel="web",
        )
        if not is_candidate:
            Membership.objects.create(
                draft=draft,
                person=person,
                network="WGMN" if network not in {"WGMN", "WNNN"} else network,
                home={"country": "NG" if country in {"*", "ALL"} else country, "state": "Lagos", "lga": "Ikeja", "chapter": "Lagos Central Chapter"},
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

    def _login_as(self, email: str) -> Client:
        client = Client()
        acc = Account.objects.select_related("user").get(email__iexact=email)
        client.force_login(acc.user)
        session = client.session
        now = timezone.now().timestamp()
        session["security_version"] = acc.security_version
        session["mfa_verified"] = True
        session["last_activity"] = now
        session["absolute_expiry"] = now + 43200
        session.save()
        return client

    def test_all_13_stage9_screens_render_cleanly_without_demo_or_pdf_labels(self):
        """
        Verifies all 13 Stage 09 screens render 200 OK for an authorized coordinator/reviewer
        and contain zero demo banners, synthetic badges, or PDF page labels.
        """
        client = self._login_as("state.lagos@example.org")
        forbidden_tokens = [
            "PDF 243",
            "PDF 244",
            "PDF 245",
            "PDF 339",
            "PDF 377",
            "UI REVIEW V2",
            "SYNTHETIC EXAMPLES",
            "NOT LIVE",
            "Related screens · design preview",
            "Sample data",
            "Host-verified example",
        ]

        for code, meta in STAGE9_SCREENS.items():
            res = client.get(meta["route"])
            self.assertEqual(res.status_code, 200, f"Failed GET {meta['route']} for {code}")
            html = res.content.decode("utf-8")
            self.assertIn(meta["title"], html, f"Expected title '{meta['title']}' on {code}")
            for token in forbidden_tokens:
                self.assertNotIn(token, html, f"Forbidden demo token '{token}' found on {code}")

            # Also verify dispatcher routes
            res_router = client.get(f"/foundation/stage9/{code}/")
            self.assertEqual(res_router.status_code, 200, f"Router /foundation/stage9/{code}/ failed")
            res_alias = client.get(f"/foundation/screens/{code}/")
            self.assertEqual(res_alias.status_code, 200, f"Alias /foundation/screens/{code}/ failed")

    def test_step1_task_creation_assignment_work_queue_and_scoped_boards(self):
        """
        Step 1: Creating and assigning a task creates a MissionControlTask,
        links a WorkItem in the assignee's Work Queue (CORE-02), sends a Notification (CORE-03),
        and displays across scoped task board queues (TASK-01, TASK-02).
        """
        client = self._login_as("state.lagos@example.org")

        res = client.post(
            "/foundation/tasks/create/",
            {
                "title": "Verify Ikeja Chapter attendance register",
                "assign_to": "Ada Okafor",
                "due_date_label": "28 September 2026",
                "priority": "Urgent",
                "required_evidence": "Attach signed attendance sheet and summary note.",
                "action": "assign_task",
            },
        )
        self.assertEqual(res.status_code, 200)
        task = MissionControlTask.objects.filter(title="Verify Ikeja Chapter attendance register").first()
        self.assertIsNotNone(task)
        self.assertEqual(task.owner_name, "Ada Okafor")
        self.assertEqual(task.status, "Not started")
        self.assertIsNotNone(task.linked_work_item)

        # Verify WorkItem is present in Work Queue (CORE-02)
        wq_res = client.get("/foundation/work-queue/?status=all")
        self.assertEqual(wq_res.status_code, 200)
        self.assertContains(wq_res, "Verify Ikeja Chapter attendance register")

        # Verify Notification was created
        self.assertTrue(
            Notification.objects.filter(title__icontains="Verify Ikeja Chapter attendance register").exists()
        )

        # Verify scoped queue filters on TASK-01
        for queue in ["assigned_to_me", "assigned_by_me", "overdue", "blocked", "returned", "completed"]:
            q_res = client.get(f"/foundation/tasks/?queue={queue}")
            self.assertEqual(q_res.status_code, 200)

    def test_step2_task_lifecycle_states_and_separation_of_duties(self):
        """
        Step 2: Tests full task lifecycle transitions:
        In progress -> Blocked -> Submitted -> Returned for correction (requires reason) ->
        Resubmitted (version incremented) -> Reviewed -> Verified -> Closed -> Reopened (requires reason) -> Escalated,
        plus reassignment preserving source/history and separation-of-duties enforcement.
        """
        member_client = self._login_as("member.ada@example.org")
        reviewer_client = self._login_as("state.lagos@example.org")

        task = MissionControlTask.objects.get(task_code="TASK-NG-001")

        # 1. Mark blocked (requires reason)
        res_missing_block = member_client.post(
            f"/foundation/tasks/{task.task_code}/",
            {"action": "mark_blocked", "reason_or_note": ""},
        )
        self.assertEqual(res_missing_block.status_code, 200)
        task.refresh_from_db()
        self.assertNotEqual(task.status, "Blocked")

        res_block = member_client.post(
            f"/foundation/tasks/{task.task_code}/",
            {"action": "mark_blocked", "reason_or_note": "Waiting on venue confirmation from chapter secretary."},
        )
        self.assertEqual(res_block.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, "Blocked")
        self.assertEqual(task.linked_work_item.status, "blocked")

        # 2. Submit evidence
        res_submit = member_client.post(
            f"/foundation/tasks/{task.task_code}/",
            {
                "action": "submit_evidence",
                "evidence_file": "chapter-agenda-v2.pdf",
                "reason_or_note": "Agenda confirmed and attached.",
            },
        )
        self.assertEqual(res_submit.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, "Submitted")

        # 3. Separation of duties: task owner (Ada Okafor) cannot approve/close her own task
        res_self_approve = member_client.post(
            "/foundation/tasks/review/",
            {
                "task_code": task.task_code,
                "reviewer_decision": "close_task",
                "decision_reason": "Self approving my own task",
                "evidence_checked": "1",
            },
        )
        self.assertEqual(res_self_approve.status_code, 403)
        task.refresh_from_db()
        self.assertEqual(task.status, "Submitted")

        # 4. Reviewer returns for correction (requires reason, keeps prior evidence)
        prev_version = task.current_version
        res_return = reviewer_client.post(
            "/foundation/tasks/review/",
            {
                "task_code": task.task_code,
                "reviewer_decision": "return_for_correction",
                "decision_reason": "Add the missing agenda confirmation and submit a new version.",
                "evidence_checked": "1",
            },
        )
        self.assertEqual(res_return.status_code, 200)
        task.refresh_from_db()
        self.assertEqual(task.status, "Returned for correction")
        self.assertEqual(task.evidence_file, "chapter-agenda-v2.pdf")

        # 5. Task owner resubmits -> increments version
        member_client.post(
            "/foundation/tasks/lifecycle/",
            {
                "task_code": task.task_code,
                "action": "submit_evidence",
                "evidence_file": "chapter-agenda-v3.pdf",
                "reason_or_note": "Added missing confirmation.",
            },
        )
        task.refresh_from_db()
        self.assertEqual(task.status, "Submitted")
        self.assertEqual(task.current_version, prev_version + 1)

        # 6. Reviewer marks reviewed, verified, and closed
        reviewer_client.post(
            "/foundation/tasks/review/",
            {
                "task_code": task.task_code,
                "reviewer_decision": "mark_reviewed",
                "decision_reason": "Agenda structure checked.",
                "evidence_checked": "1",
            },
        )
        task.refresh_from_db()
        self.assertEqual(task.status, "Reviewed")

        reviewer_client.post(
            "/foundation/tasks/review/",
            {
                "task_code": task.task_code,
                "reviewer_decision": "mark_verified",
                "decision_reason": "Verified against chapter quality standard.",
                "evidence_checked": "1",
            },
        )
        task.refresh_from_db()
        self.assertEqual(task.status, "Verified")

        reviewer_client.post(
            "/foundation/tasks/review/",
            {
                "task_code": task.task_code,
                "reviewer_decision": "close_task",
                "decision_reason": "All evidence verified and complete.",
                "evidence_checked": "1",
            },
        )
        task.refresh_from_db()
        self.assertEqual(task.status, "Closed")
        self.assertEqual(task.linked_work_item.status, "completed")

        # 7. Reopen closed task with recorded reason -> prior closure remains in history
        reviewer_client.post(
            "/foundation/tasks/lifecycle/",
            {
                "task_code": task.task_code,
                "action": "reopen_task",
                "reason_or_note": "Additional speaker item added for September session.",
            },
        )
        task.refresh_from_db()
        self.assertEqual(task.status, "Reopened")
        self.assertTrue(task.lifecycle_entries.filter(step_name="Closed").exists())
        self.assertTrue(task.lifecycle_entries.filter(step_name="Reopened").exists())

        # 8. Escalate overdue/blocked task & reassign while preserving source and history
        reviewer_client.post(
            "/foundation/tasks/lifecycle/",
            {
                "task_code": task.task_code,
                "action": "escalate_task",
                "reason_or_note": "Overdue review routed to supervising coordinator with blocker note.",
            },
        )
        task.refresh_from_db()
        self.assertEqual(task.status, "Escalated")

        original_source = task.source_reference
        reviewer_client.post(
            f"/foundation/tasks/{task.task_code}/",
            {
                "action": "reassign_task",
                "new_owner_name": "Kemi Bello",
                "reason_or_note": "Reassigned during chapter handover.",
            },
        )
        task.refresh_from_db()
        self.assertEqual(task.owner_name, "Kemi Bello")
        self.assertEqual(task.source_reference, original_source)
        self.assertTrue(
            task.lifecycle_entries.filter(
                step_name="Reassigned",
                actor_or_evidence__icontains="Ada Okafor -> Kemi Bello",
            ).exists()
        )

    def test_step3_calendar_meeting_scheduling_recurrence_and_rsvp(self):
        """
        Step 3: Tests My Calendar (MTG-01), Meetings List (MTG-02), Schedule Meeting (MTG-03),
        Recurring Meeting Series (MTG-03-RECURRING: single vs future edits, missed occurrence note,
        retry failed recipient without resending to everyone), and RSVP (MTG-04).
        """
        organizer_client = self._login_as("state.lagos@example.org")
        member_client = self._login_as("member.ada@example.org")

        # 1. Schedule a new meeting (MTG-03)
        res_sched = organizer_client.post(
            "/foundation/meetings/schedule/",
            {
                "title": "Lagos State Chapter Leads Sync",
                "date_and_start_time": "24 September 2026 · 11:00",
                "timezone_name": "Africa/Lagos (WAT)",
                "invitees_label": "WGMN · Lagos State Chapter Leads",
                "agenda": "Review chapter task completion, attendance verification, and Q4 readiness.",
                "repeats_frequency": "Monthly",
                "ends_date_label": "31 December 2026",
                "series_action": "Edit this and future meetings",
                "action": "send_invitation",
            },
        )
        self.assertEqual(res_sched.status_code, 200)
        new_mtg = MeetingSeries.objects.filter(title="Lagos State Chapter Leads Sync").first()
        self.assertIsNotNone(new_mtg)
        self.assertEqual(new_mtg.timezone_name, "Africa/Lagos (WAT)")

        # 2. Verify meeting appears on Calendar (MTG-01) and Meetings List (MTG-02)
        cal_res = member_client.get("/foundation/calendar/")
        self.assertContains(cal_res, "Country coordination")
        self.assertContains(cal_res, "Confirm Chapter meeting agenda")

        list_res = member_client.get("/foundation/meetings/?q=Lagos+State+Chapter+Leads+Sync")
        self.assertContains(list_res, "Lagos State Chapter Leads Sync")

        # 3. Participant RSVP on MTG-04
        mtg1 = MeetingSeries.objects.get(meeting_code="MTG-NG-001")
        rsvp_res = member_client.post(
            f"/foundation/meetings/{mtg1.meeting_code}/",
            {"rsvp_status": "Tentative", "note": "Joining 10 minutes after start."},
        )
        self.assertEqual(rsvp_res.status_code, 200)
        self.assertContains(rsvp_res, "Joining 10 minutes after start.")
        mtg1.refresh_from_db()
        self.assertEqual(mtg1.status, "Tentative")

        # 3b. Inline minutes save and action item creation on MTG-04
        min_save_res = organizer_client.post(
            f"/foundation/meetings/{mtg1.meeting_code}/",
            {
                "action": "save_minutes",
                "minutes_text": "Updated country coordination minutes and key takeaways.",
                "minutes_version": "v2 · draft",
            },
        )
        self.assertEqual(min_save_res.status_code, 200)
        mtg1.refresh_from_db()
        self.assertIn("Updated country coordination minutes", mtg1.minutes_text)

        act_add_res = organizer_client.post(
            f"/foundation/meetings/{mtg1.meeting_code}/",
            {
                "action": "add_action_item",
                "detail_text": "Circulate Q4 chapter calendar to all LGA leads",
                "owner_label": "Ada Okafor",
                "deadline_or_version": "29 Sep 2026 WAT",
                "record_type": "Action",
                "convert_to_task": "1",
            },
        )
        self.assertEqual(act_add_res.status_code, 200)
        self.assertTrue(
            MeetingDecisionAction.objects.filter(
                meeting=mtg1,
                detail_text="Circulate Q4 chapter calendar to all LGA leads",
                is_converted=True,
            ).exists()
        )

        # 4. Recurring series update, missed occurrence note, and failed recipient retry (MTG-03-RECURRING)
        rec_res = organizer_client.post(
            "/foundation/meetings/recurring/",
            {
                "meeting_code": mtg1.meeting_code,
                "repeats_frequency": "Weekly",
                "next_occurrence_label": "25 October 2026 · 10:00 WAT",
                "edit_scope": "Edit this and future meetings",
                "cancellation_status": "Keep series active",
                "action_type": "update_series",
            },
        )
        self.assertEqual(rec_res.status_code, 200)
        self.assertContains(rec_res, "Series change confirmed")

        missed_res = organizer_client.post(
            "/foundation/meetings/recurring/",
            {
                "meeting_code": mtg1.meeting_code,
                "missed_occurrence_note": "Public holiday in Lagos; rescheduled to next week without synthetic attendance.",
                "action_type": "record_missed_occurrence",
            },
        )
        self.assertEqual(missed_res.status_code, 200)
        self.assertContains(missed_res, "Occurrence missed")
        mtg1.refresh_from_db()
        self.assertIn("Public holiday", mtg1.missed_occurrence_note)

        # Simulate a failed invitation recipient and retry only failed recipient
        bisi = mtg1.participant_records.filter(participant_name="Bisi Adeyemi").first()
        bisi.invitation_delivery_status = "failed"
        bisi.save()

        retry_res = organizer_client.post(
            "/foundation/meetings/recurring/",
            {
                "meeting_code": mtg1.meeting_code,
                "action_type": "retry_failed_invitations",
            },
        )
        self.assertEqual(retry_res.status_code, 200)
        bisi.refresh_from_db()
        self.assertEqual(bisi.invitation_delivery_status, "retried")

        # 5. Creator-only meeting deletion: non-creator is denied (403); creator can delete
        non_creator_del = member_client.post(
            "/foundation/meetings/",
            {
                "action": "delete_meeting",
                "meeting_code": new_mtg.meeting_code,
            },
        )
        self.assertEqual(non_creator_del.status_code, 403)
        self.assertTrue(MeetingSeries.objects.filter(meeting_code=new_mtg.meeting_code).exists())

        creator_detail = organizer_client.get(f"/foundation/meetings/{new_mtg.meeting_code}/")
        self.assertContains(creator_detail, "Delete Meeting")

        creator_del = organizer_client.post(
            "/foundation/meetings/",
            {
                "action": "delete_meeting",
                "meeting_code": new_mtg.meeting_code,
            },
        )
        self.assertEqual(creator_del.status_code, 200)
        self.assertContains(creator_del, "Lagos State Chapter Leads Sync")
        self.assertFalse(MeetingSeries.objects.filter(meeting_code=new_mtg.meeting_code).exists())

    def test_step4_minutes_approval_idempotent_action_conversion_and_attendance_correction(self):
        """
        Step 4:
        - Approving minutes freezes that version; requesting a correction increments draft version with reason.
        - Converting meeting action items creates linked MissionControlTasks idempotently once per action
          and preserves the meeting reference.
        - Correcting attendance in MTG-06 retains 'Absent · original retained' and does not silently overwrite approved minutes.
        """
        organizer_client = self._login_as("state.lagos@example.org")
        mtg1 = MeetingSeries.objects.get(meeting_code="MTG-NG-001")

        # 1. Request correction on minutes (requires comment, increments version)
        corr_res = organizer_client.post(
            "/foundation/meetings/attendance-minutes/",
            {
                "meeting_code": mtg1.meeting_code,
                "minutes_version": "v2 · draft",
                "decision": "Request correction",
                "reviewer_comment": "Clarify deadline for Action 02 before final approval.",
            },
        )
        self.assertEqual(corr_res.status_code, 200)
        mtg1.refresh_from_db()
        self.assertEqual(mtg1.minutes_status, "Correction requested")
        self.assertEqual(mtg1.minutes_draft_label, "v3 · draft")

        # 2. Approve minutes -> freezes version
        app_res = organizer_client.post(
            "/foundation/meetings/attendance-minutes/",
            {
                "meeting_code": mtg1.meeting_code,
                "minutes_version": "v3 · draft",
                "decision": "Approve minutes",
                "reviewer_comment": "Minutes v3 verified and approved.",
            },
        )
        self.assertEqual(app_res.status_code, 200)
        mtg1.refresh_from_db()
        self.assertEqual(mtg1.minutes_status, "Approved")
        self.assertEqual(mtg1.minutes_version, "v3 · approved")
        self.assertTrue(mtg1.minutes_frozen)

        # 3. Convert agreed actions into linked Mission Control tasks (MTG-05 / MTG-05-RECORD)
        before_count = MissionControlTask.objects.filter(source_meeting=mtg1).count()
        conv_res1 = organizer_client.post(
            "/foundation/meetings/follow-up/",
            {
                "meeting_code": mtg1.meeting_code,
                "action": "create_action_task",
            },
        )
        self.assertEqual(conv_res1.status_code, 200)
        after_first_conversion = MissionControlTask.objects.filter(source_meeting=mtg1).count()
        self.assertEqual(after_first_conversion, before_count + 2)

        # Verify idempotency: converting again does NOT create duplicate tasks
        conv_res2 = organizer_client.post(
            "/foundation/meetings/follow-up/",
            {
                "meeting_code": mtg1.meeting_code,
                "action": "create_action_task",
            },
        )
        self.assertEqual(conv_res2.status_code, 200)
        after_second_conversion = MissionControlTask.objects.filter(source_meeting=mtg1).count()
        self.assertEqual(after_second_conversion, after_first_conversion)

        # 4. Attendance correction in Meetings Command Centre (MTG-06)
        att_res = organizer_client.post(
            "/foundation/meetings/command-centre/",
            {
                "meeting_code": mtg1.meeting_code,
                "participant_name": "Bisi Adeyemi",
                "corrected_attendance": "Present",
                "correction_reason": "Signed physical attendance sheet verified by chapter host.",
                "action": "approve_correction",
            },
        )
        self.assertEqual(att_res.status_code, 200)
        bisi = mtg1.participant_records.get(participant_name="Bisi Adeyemi")
        self.assertEqual(bisi.attendance_status, "Present")
        self.assertEqual(bisi.previous_attendance_value, "Absent · original retained")
        self.assertIn("Signed physical attendance sheet", bisi.correction_reason)

        # Approved minutes remain untouched
        mtg1.refresh_from_db()
        self.assertEqual(mtg1.minutes_version, "v3 · approved")
        self.assertTrue(mtg1.minutes_frozen)

    def test_scope_and_role_isolation_across_stage9(self):
        """
        Verifies:
        - Candidates are blocked from Stage 09 governance screens (403).
        - Standard members cannot access organizer/reviewer-only screens (TASK-04, MTG-03, MTG-03-RECURRING, MTG-06) (403).
        - Cross-country/cross-network task and meeting access is denied (403).
        """
        candidate_client = self._login_as("candidate.john@example.org")
        res_cand = candidate_client.get("/foundation/tasks/")
        self.assertEqual(res_cand.status_code, 403)

        member_client = self._login_as("member.ada@example.org")
        for restricted_route in [
            "/foundation/tasks/review/",
            "/foundation/meetings/schedule/",
            "/foundation/meetings/recurring/",
            "/foundation/meetings/command-centre/",
        ]:
            res_mem = member_client.get(restricted_route)
            self.assertEqual(res_mem.status_code, 403, f"Expected 403 for member on {restricted_route}")

        # Cross-country / cross-network isolation: WGMN/NG member cannot access WNNN/GH tasks or meetings
        res_cross_net = member_client.get("/foundation/tasks/?network=WNNN&country=GH")
        self.assertEqual(res_cross_net.status_code, 403)
