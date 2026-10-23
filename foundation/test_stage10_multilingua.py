"""
WDOS Stage 10 Automated Verification Suite:
Multilingua Meeting, Translation (Zoom Video SDK + Azure AI Speech) & Large Events
Covers:
- Module 12: Multilingua Room (ROOM-01 through ROOM-08)
- Module 13: Conferences & Large Events (EVENT-01 through EVENT-10)
- Provider Adapters: ZoomVideoSDKAdapter & AzureSpeechAdapter
- Scope & Network Isolation (WGMN vs WNNN), Waiting Room Gate, Host Floor Controls,
  Audio Recovery, Diagnostics, and Live Transcript -> MTG-05 / TASK-01 Bridge.
"""
from __future__ import annotations

import html as html_lib
import json


from django.contrib.auth.models import User
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import (
    ConferenceEvent,
    EventModerationQuestion,
    EventRegistration,
    LiveTranscriptSegment,
    MeetingRoomSession,
    MeetingSeries,
    MissionControlTask,
    PersonProfile,
    RoomDiagnosticLane,
    RoomParticipantSession,
    ScheduledMeeting,
)
from .multilingua.azure_speech_adapter import AzureSpeechAdapter
from .multilingua.zoom_adapter import ZoomVideoSDKAdapter
from .multilingua_events_engine import STAGE10_SCREENS, seed_stage10_fixtures


FORBIDDEN_WATERMARKS = (
    "UI REVIEW V2",
    "SYNTHETIC EXAMPLES",
    "NOT LIVE",
    "Sample data",
    "Sample timestamp",
    "SAMPLE CAPTION",
    "PDF 378",
)


class Stage10MultilinguaAndEventsTestSuite(TestCase):
    def setUp(self):
        self.client = Client()
        self.host_user = User.objects.create_user(
            username="ada_host",
            email="ada.host@wgmn.example.org",
            password="StrongPassword123!",
        )
        self.host_profile = PersonProfile.objects.create(
            user=self.host_user,
            full_name="Ada Okafor",
            primary_network="WGMN",
            country="NG",
            primary_relationship="Country Coordinator",
        )

        self.participant_user = User.objects.create_user(
            username="lina_participant",
            email="lina.participant@wgmn.example.org",
            password="StrongPassword123!",
        )
        self.participant_profile = PersonProfile.objects.create(
            user=self.participant_user,
            full_name="Zainab Musa",
            primary_network="WGMN",
            country="NG",
            primary_relationship="Member",
        )

        self.wrong_scope_user = User.objects.create_user(
            username="wnnn_outsider",
            email="outsider@wnnn.example.org",
            password="StrongPassword123!",
        )
        self.wrong_scope_profile = PersonProfile.objects.create(
            user=self.wrong_scope_user,
            full_name="Tunde Outsider",
            primary_network="WNNN",
            country="NG",
            primary_relationship="Member",
        )

    # -------------------------------------------------------------------------
    # 1. Provider Adapter Unit Tests (Zoom Video SDK & Azure AI Speech)
    # -------------------------------------------------------------------------
    def test_zoom_token_generation(self):
        token = ZoomVideoSDKAdapter.generate_token("test-session", "user-123", role_type=0)
        self.assertIsInstance(token, str)
        self.assertGreater(len(token), 20)

        decoded = ZoomVideoSDKAdapter.decode_token(token)
        self.assertEqual(decoded["tpc"], "test-session")
        self.assertEqual(decoded["user_identity"], "user-123")
        self.assertEqual(decoded["role_type"], 0)

        with override_settings(ZOOM_SDK_KEY="", ZOOM_SDK_SECRET=""):
            with self.assertRaises(ValueError):
                ZoomVideoSDKAdapter.generate_token("test-session", "user-123", role_type=1)

    def test_azure_speech_adapter_token_and_translation(self):
        from unittest.mock import MagicMock, patch
        import requests

        token_data = AzureSpeechAdapter.get_ephemeral_token()
        self.assertIn("token", token_data)
        self.assertIn("region", token_data)
        self.assertIn("supported_languages", token_data)
        self.assertIn("fr-FR", token_data["supported_languages"])
        self.assertIn("pt-BR", token_data["supported_languages"])

        # Verify secondary key (AZURE_SPEECH_KEY_2) failover when primary key returns 401
        fail_resp = MagicMock()
        fail_resp.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
        ok_resp = MagicMock()
        ok_resp.raise_for_status.return_value = None
        ok_resp.text = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.live_failover_key2_token"

        with patch("foundation.multilingua.azure_speech_adapter.requests.post", side_effect=[fail_resp, ok_resp]) as mocked_post:
            failover_data = AzureSpeechAdapter.get_ephemeral_token()
            self.assertEqual(failover_data["token"], "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.live_failover_key2_token")
            self.assertEqual(failover_data["mode"], "live")
            self.assertEqual(mocked_post.call_count, 2)

        translations = AzureSpeechAdapter.translate_segment(
            "We must finalize the Nigeria Q3 budget by Friday.",
            "en-US",
        )
        self.assertIn("fr", translations)
        self.assertIn("Nigéria", translations["fr"])
        self.assertIn("pt", translations)

        with override_settings(AZURE_SPEECH_KEY="", AZURE_SPEECH_KEY_2=""):
            with self.assertRaises(ValueError):
                AzureSpeechAdapter.get_ephemeral_token()

    # -------------------------------------------------------------------------
    # 2. Scope Isolation, Waiting Room Gate & Host Admission Triage
    # -------------------------------------------------------------------------
    def test_multilingua_room_scope_and_waiting_room_gate(self):
        meeting = ScheduledMeeting.objects.create(
            title="WGMN Nigeria Sync",
            host_profile=self.host_profile,
            scheduled_start=timezone.now(),
            network_scope="WGMN",
            country="NG",
        )

        # 1. Cross-Network Isolation Test (WNNN user blocked from WGMN room)
        self.client.force_login(self.wrong_scope_user)
        res = self.client.get(reverse("room_prejoin", args=[meeting.id]))
        self.assertEqual(res.status_code, 403)

        res_tokens_wrong = self.client.get(reverse("api_room_tokens", args=[meeting.id]))
        self.assertEqual(res_tokens_wrong.status_code, 403)

        # 2. Valid Participant Pre-Join -> Placed in Waiting Room (ROOM-02)
        self.client.force_login(self.participant_user)
        res = self.client.get(reverse("room_prejoin", args=[meeting.id]))
        self.assertEqual(res.status_code, 200)

        # 3. Participant blocked from getting live tokens while in Waiting Room
        res_tokens = self.client.get(reverse("api_room_tokens", args=[meeting.id]))
        self.assertEqual(res_tokens.status_code, 403)
        self.assertEqual(res_tokens.json()["status"], "waiting")

        # 4. Host Pre-Join -> Automatically Admitted & Receives Tokens
        self.client.force_login(self.host_user)
        self.client.get(reverse("room_prejoin", args=[meeting.id]))
        res_host_tokens = self.client.get(reverse("api_room_tokens", args=[meeting.id]))
        self.assertEqual(res_host_tokens.status_code, 200)
        host_json = res_host_tokens.json()
        self.assertEqual(host_json["status"], "admitted")
        self.assertEqual(host_json["zoom"]["role_type"], 1)

        # 5. Host Admits Waiting Participant (ROOM-05 -> ROOM-03)
        participant_session = RoomParticipantSession.objects.get(
            person_profile=self.participant_profile,
            room_session__scheduled_meeting=meeting,
        )
        res_admit = self.client.post(
            reverse("api_room_admit", args=[meeting.id]),
            {"participant_id": str(participant_session.id), "action": "admit"},
        )
        self.assertEqual(res_admit.status_code, 200)
        self.assertEqual(res_admit.json()["admission_status"], "ADMITTED")

        # 6. Admitted Participant Now Receives Live Tokens
        self.client.force_login(self.participant_user)
        res_admitted_tokens = self.client.get(reverse("api_room_tokens", args=[meeting.id]))
        self.assertEqual(res_admitted_tokens.status_code, 200)
        self.assertEqual(res_admitted_tokens.json()["status"], "admitted")
        self.assertEqual(res_admitted_tokens.json()["zoom"]["role_type"], 0)

    # -------------------------------------------------------------------------
    # 3. Live Transcript Persistence & MTG-05 / TASK-01 Auto-Minutes Bridge
    # -------------------------------------------------------------------------
    def test_live_transcript_persistence_and_mtg05_bridge(self):
        seeded = seed_stage10_fixtures()
        room_session = seeded["room_session"]
        mtg_series = seeded["meeting_series"]

        self.client.force_login(self.host_user)

        # Post a new live spoken segment via the transcript API
        res_post = self.client.post(
            reverse("api_room_transcript", args=[room_session.room_code]),
            data=json.dumps(
                {
                    "speaker_name": "Ada Okafor",
                    "original_language": "en-US",
                    "original_text": "We must finalize the Nigeria Q3 budget by Friday.",
                }
            ),
            content_type="application/json",
        )
        self.assertEqual(res_post.status_code, 201)
        seg_data = res_post.json()["segment"]
        self.assertIn("Nigéria", seg_data["translations"]["fr"])

        # End the live room session via API -> triggers MTG-05 minutes & TASK-01 creation
        res_end = self.client.post(reverse("api_room_end", args=[room_session.room_code]))
        self.assertEqual(res_end.status_code, 200)
        end_json = res_end.json()
        self.assertEqual(end_json["status"], "completed")
        self.assertGreaterEqual(end_json["segment_count"], 3)
        self.assertGreaterEqual(len(end_json["created_tasks"]), 1)

        room_session.refresh_from_db()
        self.assertEqual(room_session.status, "COMPLETED")

        mtg_series.refresh_from_db()
        self.assertIn("We must finalize the Nigeria Q3 budget by Friday.", mtg_series.minutes_text)
        self.assertIn("Nous devons finaliser le budget du T3 pour le Nigéria", mtg_series.minutes_text)
        self.assertTrue(
            MissionControlTask.objects.filter(
                source_meeting=mtg_series,
                title__icontains="finalize the Nigeria Q3 budget",
            ).exists()
        )

    # -------------------------------------------------------------------------
    # 4. All 18 Stage 10 Screens Render, Copy & State Contract Verification
    # -------------------------------------------------------------------------
    def test_all_18_stage10_screens_render_and_state_contracts(self):
        self.client.force_login(self.host_user)

        expected_titles = {
            "ROOM-01": "Ready to join?",
            "ROOM-02": "Waiting for admission",
            "ROOM-03": "Country coordination",
            "ROOM-04": "Your turn to speak",
            "ROOM-05": "Host controls",
            "ROOM-06": "Your meeting preferences",
            "ROOM-07": "Let’s restore your audio",
            "ROOM-08": "Room diagnostics",
            "EVENT-01": "WODDI leadership gathering",
            "EVENT-02": "Register for the gathering",
            "EVENT-03": "Your event lobby",
            "EVENT-04": "Agenda and session tracks",
            "EVENT-05": "Opening plenary",
            "EVENT-06": "Choose a breakout room",
            "EVENT-07": "Questions and moderation",
            "EVENT-08": "Event resources and reflections",
            "EVENT-09": "Conference setup",
            "EVENT-10": "Live event operations",
        }

        for code, title in expected_titles.items():
            # Direct Stage 10 route
            res = self.client.get(f"/foundation/stage10/{code}/")
            self.assertEqual(res.status_code, 200, f"{code} failed to render")
            html = res.content.decode("utf-8")
            self.assertIn(title, html, f"Expected title '{title}' on {code}")

            for watermark in FORBIDDEN_WATERMARKS:
                self.assertNotIn(watermark, html, f"Forbidden token '{watermark}' found on {code}")

            # Universal screen alias route
            res_alias = self.client.get(f"/foundation/screens/{code}/")
            self.assertEqual(res_alias.status_code, 200)

            # Verify state contracts (loading, empty, validation, denied, degraded)
            for state_key in ("loading", "empty", "validation", "denied", "degraded"):
                res_state = self.client.get(f"/foundation/stage10/{code}/?state={state_key}")
                self.assertEqual(res_state.status_code, 200)
                expected_contract_title = STAGE10_SCREENS[code]["state_contracts"][state_key]["title"]
                self.assertIn(expected_contract_title, html_lib.unescape(res_state.content.decode("utf-8")))



    # -------------------------------------------------------------------------
    # 5. Interactive Room Workflows (ROOM-01..ROOM-08) & Event Workflows (EVENT-01..EVENT-10)
    # -------------------------------------------------------------------------
    def test_room_and_event_interactive_workflows(self):
        self.client.force_login(self.host_user)
        seeded = seed_stage10_fixtures()
        room_session = seeded["room_session"]

        # ROOM-06: Update meeting preferences
        res_r06 = self.client.post(
            "/foundation/stage10/ROOM-06/",
            {
                "listening_language": "Portuguese",
                "caption_language": "Portuguese",
                "audio_output": "Headphones",
                "show_translated_captions": "1",
            },
        )
        self.assertEqual(res_r06.status_code, 200)
        self.assertIn("Portuguese", res_r06.content.decode("utf-8"))

        # ROOM-07: Audio recovery API & view
        res_r07_api = self.client.post(reverse("api_room_restore_audio", args=[room_session.room_code]))
        self.assertEqual(res_r07_api.status_code, 200)
        self.assertEqual(res_r07_api.json()["status"], "restored")

        # ROOM-08: Verify diagnostic lane
        lane = RoomDiagnosticLane.objects.filter(room_session=room_session, state_label="Review").first()
        res_r08 = self.client.post("/foundation/stage10/ROOM-08/", {"lane_id": str(lane.id)})
        self.assertEqual(res_r08.status_code, 200)
        lane.refresh_from_db()
        self.assertEqual(lane.state_label, "Verified")


        # EVENT-02: Confirm conference registration
        res_e02 = self.client.post(
            "/foundation/events/register/",
            {
                "attendee_name": "Ada Okafor",
                "network": "WGMN",
                "listening_language": "French",
                "access_support": "French simultaneous interpretation",
            },
        )
        self.assertEqual(res_e02.status_code, 200)
        self.assertTrue(
            EventRegistration.objects.filter(attendee_name="Ada Okafor", listening_language="French").exists()
        )

        # EVENT-06: Breakout room selection
        res_e06 = self.client.post(
            "/foundation/events/breakouts/",
            {"selected_session": "Country conversations"},
        )
        self.assertEqual(res_e06.status_code, 200)
        self.assertIn("Country conversations", res_e06.content.decode("utf-8"))

        # EVENT-07: Attendee submits question, then Host approves & publishes it
        self.client.force_login(self.participant_user)
        res_q_submit = self.client.post(
            "/foundation/events/moderation/",
            {"question_text": "How can our chapter access French breakout slides?"},
        )
        self.assertEqual(res_q_submit.status_code, 200)
        new_q = EventModerationQuestion.objects.get(
            question_text="How can our chapter access French breakout slides?"
        )
        self.assertEqual(new_q.moderation_state, "Pending")

        # Non-host cannot approve questions
        res_q_forbidden = self.client.post(
            "/foundation/events/moderation/",
            {"action": "approve_question", "question_id": str(new_q.id)},
        )
        self.assertEqual(res_q_forbidden.status_code, 403)

        # Host approves and publishes the question
        self.client.force_login(self.host_user)
        res_q_approve = self.client.post(
            "/foundation/events/moderation/",
            {
                "action": "approve_question",
                "question_id": str(new_q.id),
                "host_reply": "French slides are posted in EVENT-08 Event resources.",
            },
        )
        self.assertEqual(res_q_approve.status_code, 200)
        new_q.refresh_from_db()
        self.assertEqual(new_q.moderation_state, "Published")

        # EVENT-08: Submit post-event reflection
        res_e08 = self.client.post(
            "/foundation/events/resources/",
            {"reflection_text": "We will share the French plenary pack at our Lagos chapter sync."},
        )
        self.assertEqual(res_e08.status_code, 200)
        self.assertIn("post-event reflection", res_e08.content.decode("utf-8"))

        # EVENT-09 & EVENT-10: Host updates conference setup & resolves live ops support ticket
        res_e09 = self.client.post(
            "/foundation/events/setup/",
            {
                "title": "WODDI leadership gathering",
                "date_and_timezone": "20 October 2026 · Africa/Lagos",
                "eligibility_label": "Approved member and leader audience",
                "session_model": "Plenary broadcast with controlled breakouts",
            },
        )
        self.assertEqual(res_e09.status_code, 200)

        res_e10 = self.client.post("/foundation/events/operations/", {"action": "resolve_support"})
        self.assertEqual(res_e10.status_code, 200)
        conf_event = ConferenceEvent.objects.get(event_code="EVENT-WODDI-2026")
        self.assertEqual(conf_event.support_requests_count, 3)

    def test_room_access_policy_wdos_only_vs_anyone_with_link(self):
        """
        Verifies that:
        1. By default ('wdos_only'), unauthenticated visitors opening a room link are redirected to sign in.
        2. When a meeting is created or toggled to 'anyone_with_link', anyone with the link can join the live room,
           set their guest display name, fetch room tokens, and publish/read live translated transcripts without a WDOS account.
        """
        seed_stage10_fixtures()
        room_session = MeetingRoomSession.objects.get(room_code="ROOM-NG-001")
        guest_client = Client()

        # 1. Default room is WDOS Accounts Only -> unauthenticated guest is redirected to /auth/login/
        self.assertFalse(room_session.allow_guest_access)
        res_blocked = guest_client.get(f"/foundation/rooms/{room_session.room_code}/live/")
        self.assertEqual(res_blocked.status_code, 302)
        self.assertIn("/auth/login/", res_blocked.url)

        res_tokens_blocked = guest_client.get(f"/api/rooms/{room_session.room_code}/tokens/")
        self.assertEqual(res_tokens_blocked.status_code, 401)

        # 2. Host toggles room to 'anyone_with_link', sets status to WAITING first to verify host-must-open-first rule
        self.client.force_login(self.host_user)
        res_toggle = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "toggle_room_access", "room_access": "anyone_with_link"},
        )
        self.assertEqual(res_toggle.status_code, 200)
        room_session.refresh_from_db()
        self.assertTrue(room_session.allow_guest_access)
        self.assertFalse(room_session.bypass_lobby)

        # Put room in WAITING state (before host opens it) even with bypass_lobby enabled -> guest must wait
        room_session.status = "WAITING"
        room_session.save(update_fields=["status"])
        res_guest_before_open = guest_client.get(f"/api/rooms/{room_session.room_code}/tokens/")
        self.assertEqual(res_guest_before_open.status_code, 403)
        self.assertEqual(res_guest_before_open.json()["status"], "waiting")
        self.assertEqual(res_guest_before_open.json()["waiting_reason"], "host_not_opened")

        # 3. Host opens the room (hits live room as host -> status transitions to LIVE)
        res_host_open = self.client.get(f"/foundation/rooms/{room_session.room_code}/live/")
        self.assertEqual(res_host_open.status_code, 200)
        room_session.refresh_from_db()
        self.assertEqual(room_session.status, "LIVE")

        # Since bypass_lobby is False ('wait_in_lobby'), guest waits in lobby until admitted or bypass_lobby is enabled
        res_guest_lobby = guest_client.get(f"/api/rooms/{room_session.room_code}/tokens/")
        self.assertEqual(res_guest_lobby.status_code, 403)
        self.assertEqual(res_guest_lobby.json()["status"], "waiting")
        self.assertEqual(res_guest_lobby.json()["waiting_reason"], "lobby_admission_required")

        # 4. Unauthenticated guest pastes the link in their browser while Lobby is enabled (bypass_lobby=False):
        #    Must land on the Join Page (#prejoin-screen) first (not lobby immediately),
        #    with NO account sidebar/header chrome, and without creating a premature participant row.
        lobby_guest_client = Client()
        self.assertFalse(room_session.bypass_lobby)
        initial_participant_count = RoomParticipantSession.objects.filter(room_session=room_session).count()

        res_lobby_join_page = lobby_guest_client.get(f"/foundation/rooms/{room_session.room_code}/live/")
        self.assertEqual(res_lobby_join_page.status_code, 200)
        lobby_join_html = res_lobby_join_page.content.decode("utf-8")
        self.assertIn('id="prejoin-screen"', lobby_join_html)
        self.assertIn("Join Meeting Room", lobby_join_html)
        self.assertNotIn('<aside class="sidebar"', lobby_join_html)
        self.assertNotIn('placeholder="Search WDOS"', lobby_join_html)
        self.assertEqual(
            RoomParticipantSession.objects.filter(room_session=room_session).count(),
            initial_participant_count,
        )

        # Submitting the Join form when Lobby is enabled takes the guest to the Waiting Lobby (#waiting-lobby-screen)
        res_lobby_submit = lobby_guest_client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {
                "action": "guest_join",
                "guest_name": "Kofi Mensah (Lobby Guest)",
                "speaking_language": "en-US",
                "listening_language": "fr-FR",
            },
        )
        self.assertEqual(res_lobby_submit.status_code, 200)
        lobby_waiting_html = res_lobby_submit.content.decode("utf-8")
        self.assertIn('id="waiting-lobby-screen"', lobby_waiting_html)
        self.assertNotIn('<aside class="sidebar"', lobby_waiting_html)
        kofi_p = RoomParticipantSession.objects.get(
            room_session=room_session,
            participant_name="Kofi Mensah (Lobby Guest)",
            admission_status="WAITING_ROOM",
        )

        # Host clicks Admit on Kofi -> immediately admits Kofi and updates waiting_participants & participants
        res_admit_kofi = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "admit", "participant_id": str(kofi_p.id)},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_admit_kofi.status_code, 200)
        admit_json = res_admit_kofi.json()
        self.assertIn("admitted to the live room", admit_json["message"])
        self.assertFalse(any(p["participant_name"] == "Kofi Mensah (Lobby Guest)" for p in admit_json["waiting_participants"]))
        self.assertTrue(any(p["participant_name"] == "Kofi Mensah (Lobby Guest)" for p in admit_json["participants"]))

        # Kofi's lobby poll now receives status='admitted'
        res_kofi_poll = lobby_guest_client.get(f"/api/rooms/{room_session.room_code}/tokens/?check=lobby")
        self.assertEqual(res_kofi_poll.status_code, 200)
        self.assertEqual(res_kofi_poll.json()["status"], "admitted")

        # If another waiting guest cancels and leaves the lobby (action='cancel'), they are removed from waiting_participants
        cancel_guest = Client()
        cancel_guest.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {
                "action": "guest_join",
                "guest_name": "Cancelled Lobby Guest",
                "speaking_language": "en-US",
                "listening_language": "fr-FR",
            },
        )
        cancelled_p = RoomParticipantSession.objects.get(
            room_session=room_session,
            participant_name="Cancelled Lobby Guest",
        )
        cancel_guest.post(
            f"/foundation/rooms/{room_session.room_code}/waiting/",
            {"action": "cancel"},
        )
        cancelled_p.refresh_from_db()
        self.assertEqual(cancelled_p.admission_status, "LEFT")

        # Host enables lobby bypass (or admits waiting participants) -> new guests go Join Page -> Live Meeting
        res_bypass = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "toggle_lobby_policy", "lobby_policy": "bypass_lobby"},
        )
        self.assertEqual(res_bypass.status_code, 200)
        room_session.refresh_from_db()
        self.assertTrue(room_session.bypass_lobby)

        direct_guest_client = Client()
        res_guest_live = direct_guest_client.get(f"/foundation/rooms/{room_session.room_code}/live/")
        self.assertEqual(res_guest_live.status_code, 200)
        guest_prejoin_html = res_guest_live.content.decode("utf-8")
        self.assertIn('id="prejoin-screen"', guest_prejoin_html)
        self.assertNotIn('<aside class="sidebar"', guest_prejoin_html)

        # 5. Guest fills details and clicks Join -> taken directly into the live meeting (no lobby)
        res_guest_join = direct_guest_client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {
                "action": "guest_join",
                "guest_name": "Marie Laurent (External Guest)",
                "speaking_language": "fr-FR",
                "listening_language": "en-US",
            },
        )
        self.assertEqual(res_guest_join.status_code, 200)
        guest_live_html = res_guest_join.content.decode("utf-8")
        self.assertIn('id="live-transcript-feed"', guest_live_html)
        self.assertNotIn('id="prejoin-screen"', guest_live_html)
        self.assertNotIn('id="waiting-lobby-screen"', guest_live_html)
        self.assertNotIn('<aside class="sidebar"', guest_live_html)
        self.assertIn("Marie Laurent (External Guest)", guest_live_html)

        # 6. Guest fetches live room tokens & publishes a live speech segment
        res_guest_tokens = direct_guest_client.get(f"/api/rooms/{room_session.room_code}/tokens/")
        self.assertEqual(res_guest_tokens.status_code, 200)
        self.assertEqual(res_guest_tokens.json()["status"], "admitted")
        self.assertEqual(res_guest_tokens.json()["participant"]["name"], "Marie Laurent (External Guest)")

        res_guest_speak = direct_guest_client.post(
            f"/api/rooms/{room_session.room_code}/transcript/",
            data=json.dumps({
                "original_text": "Bonjour à tous depuis Paris",
                "original_language": "fr-FR",
            }),
            content_type="application/json",
        )
        self.assertEqual(res_guest_speak.status_code, 201)
        seg_data = res_guest_speak.json()["segment"]
        self.assertEqual(seg_data["speaker_name"], "Marie Laurent (External Guest)")
        self.assertTrue(seg_data["translations"].get("en"))

        # 7. Neural TTS audio endpoint streams MP3 voice audio for listeners
        res_tts = direct_guest_client.get(
            f"/api/rooms/{room_session.room_code}/tts/",
            {"text": "Bonjour à tous depuis Paris", "lang": "fr-FR"},
        )
        self.assertEqual(res_tts.status_code, 200)
        self.assertEqual(res_tts["Content-Type"], "audio/mpeg")
        self.assertGreater(len(res_tts.content), 10)

        # 8. Non-host guest cannot end the meeting
        res_guest_end = direct_guest_client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "end_session"},
        )
        self.assertEqual(res_guest_end.status_code, 403)

        # 9. Host ends the meeting -> renders Meeting Ended screen & notifies polling clients
        res_host_end = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "end_session"},
        )
        self.assertEqual(res_host_end.status_code, 200)
        self.assertIn("This online meeting has ended", res_host_end.content.decode("utf-8"))

        res_poll_after_end = direct_guest_client.get(f"/api/rooms/{room_session.room_code}/transcript/")
        self.assertEqual(res_poll_after_end.status_code, 200)
        self.assertEqual(res_poll_after_end.json()["room_status"], "COMPLETED")

    def test_all_eight_languages_translate_and_synthesize_without_defaulting_to_english(self):
        """
        Verifies that all 8 dropdown languages (en-US, fr-FR, pt-BR, ar-EG, sw-KE, ha-NG, yo-NG, ig-NG)
        return distinct target-language translations (never defaulting non-English targets to raw English)
        and stream MP3 audio from the TTS endpoint.
        """
        seed_stage10_fixtures()
        room_session = MeetingRoomSession.objects.get(room_code="ROOM-NG-001")
        self.client.force_login(self.host_user)

        # Post a statement in English
        res_post = self.client.post(
            f"/api/rooms/{room_session.room_code}/transcript/",
            data=json.dumps({
                "original_text": "We must finalize the Nigeria Q3 budget by Friday.",
                "original_language": "en-US",
            }),
            content_type="application/json",
        )
        self.assertEqual(res_post.status_code, 201)

        all_codes = [
            ("en-US", "en"),
            ("fr-FR", "fr"),
            ("pt-BR", "pt"),
            ("ar-EG", "ar"),
            ("sw-KE", "sw"),
            ("ha-NG", "ha"),
            ("yo-NG", "yo"),
            ("ig-NG", "ig"),
        ]
        english_source = "We must finalize the Nigeria Q3 budget by Friday."

        for bcp47, short_code in all_codes:
            # Switch listening language in live room
            res_switch = self.client.post(
                f"/foundation/rooms/{room_session.room_code}/live/",
                {
                    "action": "switch_language",
                    "speaking_language": "en-US",
                    "listening_language": bcp47,
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertEqual(res_switch.status_code, 200)

            # Poll transcript for this language
            res_get = self.client.get(f"/api/rooms/{room_session.room_code}/transcript/?lang={short_code}")
            self.assertEqual(res_get.status_code, 200)
            segs = res_get.json()["segments"]
            self.assertGreaterEqual(len(segs), 1)
            latest = segs[-1]
            self.assertTrue(latest["translated_text"])
            if short_code != "en":
                self.assertNotEqual(latest["translated_text"], english_source)

            # Verify TTS MP3 endpoint for this language
            res_tts = self.client.get(
                f"/api/rooms/{room_session.room_code}/tts/",
                {"text": latest["translated_text"], "lang": bcp47},
            )
            self.assertEqual(res_tts.status_code, 200)
            self.assertEqual(res_tts["Content-Type"], "audio/mpeg")



