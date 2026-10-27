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

import datetime
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
    MeetingParticipantRecord,
    MeetingRoomSession,
    MeetingSeries,
    MissionControlTask,
    PersonProfile,
    RoomChatMessage,
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

    def test_live_interim_broadcast_and_vendored_sdks(self):
        """
        Verifies:
        1. Vendored Speech SDK & LiveKit SDK exist and are served in room_workspace.html (no broken speech-sdk hyphen URL).
        2. Posting action='live_interim' broadcasts the full growing sentence + translations across workers and clears on final segment save.
        """
        seed_stage10_fixtures()
        room_session = MeetingRoomSession.objects.get(room_code="ROOM-NG-001")
        self.client.force_login(self.host_user)

        res_live = self.client.get(f"/foundation/rooms/{room_session.room_code}/live/")
        self.assertEqual(res_live.status_code, 200)
        html = res_live.content.decode("utf-8")
        self.assertIn("/static/foundation/vendor/speech-sdk-1.53.0.min.js", html)
        self.assertIn("/static/foundation/vendor/livekit-client-2.5.7.umd.min.js", html)
        self.assertNotIn("speech-sdk.bundle-min.js", html)

        # Post live interim phrase while speaker is mid-sentence
        res_interim = self.client.post(
            f"/api/rooms/{room_session.room_code}/transcript/",
            data=json.dumps({
                "action": "live_interim",
                "speaker_name": "Dev Admin",
                "original_language": "en-US",
                "original_text": "Welcome everyone to our regional coordination",
                "translations": {"fr": "Bienvenue à tous à notre coordination régionale"},
            }),
            content_type="application/json",
        )
        self.assertEqual(res_interim.status_code, 200)
        self.assertEqual(res_interim.json()["status"], "interim_recorded")

        # Polling client in French receives the live growing interim caption & translation immediately
        res_poll = self.client.get(f"/api/rooms/{room_session.room_code}/transcript/?lang=fr")
        self.assertEqual(res_poll.status_code, 200)
        poll_data = res_poll.json()
        self.assertIsNotNone(poll_data.get("live_interim"))
        self.assertEqual(poll_data["live_interim"]["original_text"], "Welcome everyone to our regional coordination")
        self.assertEqual(
            poll_data["live_interim"]["translated_text"],
            "Bienvenue à tous à notre coordination régionale",
        )

        # Finalize the full utterance -> saves complete sentence & clears live_interim
        res_final = self.client.post(
            f"/api/rooms/{room_session.room_code}/transcript/",
            data=json.dumps({
                "speaker_name": "Dev Admin",
                "original_language": "en-US",
                "original_text": "Welcome everyone to our regional coordination meeting today.",
                "translations": {"fr": "Bienvenue à tous à notre réunion de coordination régionale aujourd'hui."},
            }),
            content_type="application/json",
        )
        self.assertEqual(res_final.status_code, 201)

        res_poll_after = self.client.get(f"/api/rooms/{room_session.room_code}/transcript/?lang=fr")
        self.assertEqual(res_poll_after.status_code, 200)
        after_data = res_poll_after.json()
        self.assertIsNone(after_data.get("live_interim"))
        self.assertEqual(
            after_data["segments"][-1]["original_text"],
            "Welcome everyone to our regional coordination meeting today.",
        )

        # Verify server-side LiveKit translation agent (`RoomTranslationBot` + `synthesize_speech_pcm24k`)
        import asyncio
        from asgiref.sync import async_to_sync
        from django.core.management import call_command
        from foundation.multilingua.livekit_agent import RoomTranslationBot

        pcm = AzureSpeechAdapter.synthesize_speech_pcm24k("Bonjour à tous", "fr-FR")
        self.assertIsNotNone(pcm)
        self.assertGreaterEqual(len(pcm), 960)

        async def _test_bot_pipeline():
            loop = asyncio.get_running_loop()
            bot = RoomTranslationBot(
                room_session_id=str(room_session.id),
                room_code=room_session.room_code,
                session_name=room_session.session_name,
                loop=loop,
            )
            await bot.handle_interim_speech("Patrick", "en-US", "Testing server side translation", {"pt": "Testando tradução no servidor"})
            await bot.handle_final_speech(
                speaker_id="",
                speaker_name="Patrick",
                speaking_lang="en-US",
                original_text="Testing server side translation agent from Android phone.",
                raw_translations={"pt": "Testando agente de tradução do servidor pelo celular Android."},
            )
            await bot.stop()

        async_to_sync(_test_bot_pipeline)()
        call_command("run_translation_agent", once=True)

        res_poll_bot = self.client.get(f"/api/rooms/{room_session.room_code}/transcript/?lang=pt")
        self.assertEqual(res_poll_bot.status_code, 200)
        bot_segs = res_poll_bot.json()["segments"]
        self.assertEqual(
            bot_segs[-1]["original_text"],
            "Testing server side translation agent from Android phone.",
        )
        self.assertEqual(
            bot_segs[-1]["translated_text"],
            "Testando agente de tradução do servidor pelo celular Android.",
        )

    def test_room_screenshare_permissions_and_presentation(self):
        seeded = seed_stage10_fixtures()
        room_session = seeded["room_session"]

        # Ensure participants exist
        host_participant = RoomParticipantSession.objects.filter(
            room_session=room_session,
            person_profile=self.host_profile,
        ).first()
        if not host_participant:
            host_participant = RoomParticipantSession.objects.create(
                room_session=room_session,
                person_profile=self.host_profile,
                participant_name=self.host_profile.full_name,
                meeting_role="Host",
                speaking_language="en-US",
                listening_language="fr-FR",
            )

        member_participant = RoomParticipantSession.objects.filter(
            room_session=room_session,
            person_profile=self.participant_profile,
        ).first()
        if not member_participant:
            member_participant = RoomParticipantSession.objects.create(
                room_session=room_session,
                person_profile=self.participant_profile,
                participant_name=self.participant_profile.full_name,
                meeting_role="Participant",
                speaking_language="en-US",
                listening_language="fr-FR",
                is_speaker=False,
                connection_status="Connected",
            )
        else:
            member_participant.meeting_role = "Participant"
            member_participant.is_speaker = False
            member_participant.connection_status = "Connected"
            member_participant.save()

        host_participant.admission_status = "ADMITTED"
        host_participant.save()
        member_participant.admission_status = "ADMITTED"
        member_participant.save()

        # 1. Initial defaults
        self.assertFalse(room_session.allow_participant_screen_share)
        self.assertEqual(room_session.screen_share_policy_label, "Host only")
        self.assertEqual(room_session.active_screenshare_presenter, "")
        self.assertTrue(host_participant.can_share_screen(is_host=True))
        self.assertFalse(member_participant.can_share_screen(is_host=False))

        # 2. Non-host attempts to start sharing when restricted -> Forbidden
        self.client.force_login(self.participant_user)
        res_unauth_share = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "set_screenshare_state", "is_sharing": "true", "presenter_name": member_participant.participant_name},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_unauth_share.status_code, 403)

        # 2b. Non-host attempts to broadcast screen frame when restricted -> Forbidden
        res_unauth_frame = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {
                "action": "broadcast_screen_frame",
                "frame_data_url": "data:image/jpeg;base64,unauthorizedframe",
                "seq": "1",
                "presenter_name": member_participant.participant_name,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_unauth_frame.status_code, 403)

        # 2c. Verify in HTML UI: Screen share button is NOT shown for unauthorized participant
        res_member_ui = self.client.get(f"/foundation/rooms/{room_session.room_code}/live/")
        self.assertEqual(res_member_ui.status_code, 200)
        self.assertIn('id="btn-toggle-screenshare"', res_member_ui.content.decode("utf-8"))
        self.assertIn('style="display:none;"', res_member_ui.content.decode("utf-8"))

        # Verify in HTML UI: Screen share button IS shown for host
        self.client.force_login(self.host_user)
        res_host_ui = self.client.get(f"/foundation/rooms/{room_session.room_code}/live/")
        self.assertEqual(res_host_ui.status_code, 200)
        self.assertIn('id="btn-toggle-screenshare"', res_host_ui.content.decode("utf-8"))
        self.assertIn('style="display:inline-flex;"', res_host_ui.content.decode("utf-8"))

        # 3. Host starts sharing screen
        self.client.force_login(self.host_user)
        res_host_share = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "set_screenshare_state", "is_sharing": "true", "presenter_name": host_participant.participant_name},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_host_share.status_code, 200)
        room_session.refresh_from_db()
        self.assertEqual(room_session.active_screenshare_presenter, host_participant.participant_name)

        # 4. Host stops sharing screen
        res_host_stop = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "set_screenshare_state", "is_sharing": "false"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_host_stop.status_code, 200)
        room_session.refresh_from_db()
        self.assertEqual(room_session.active_screenshare_presenter, "")

        # 5. Host toggles room-wide policy to allow participant screen share
        res_toggle_policy = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "toggle_screenshare_policy", "screenshare_policy": "allow_all"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_toggle_policy.status_code, 200)
        room_session.refresh_from_db()
        self.assertTrue(room_session.allow_participant_screen_share)
        self.assertEqual(room_session.screen_share_policy_label, "Participants can share")
        self.assertTrue(member_participant.can_share_screen(is_host=False))

        # 6. Now member can share under room-wide policy
        self.client.force_login(self.participant_user)
        res_member_share = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "set_screenshare_state", "is_sharing": "true", "presenter_name": member_participant.participant_name},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_member_share.status_code, 200)
        room_session.refresh_from_db()
        self.assertEqual(room_session.active_screenshare_presenter, member_participant.participant_name)

        # Member stops sharing
        res_member_stop = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "set_screenshare_state", "is_sharing": "false"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_member_stop.status_code, 200)
        room_session.refresh_from_db()
        self.assertEqual(room_session.active_screenshare_presenter, "")

        # 7. Host sets policy back to host_only
        self.client.force_login(self.host_user)
        self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "toggle_screenshare_policy", "screenshare_policy": "host_only"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        room_session.refresh_from_db()
        self.assertFalse(room_session.allow_participant_screen_share)

        # 8. Host grants per-participant permission to member
        res_grant = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "toggle_screenshare_permission", "participant_id": str(member_participant.id)},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_grant.status_code, 200)
        member_participant.refresh_from_db()
        self.assertTrue(member_participant.can_share_screen(is_host=False))

        # 9. Verify member can share with individual permission
        self.client.force_login(self.participant_user)
        res_member_share_granted = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "set_screenshare_state", "is_sharing": "true", "presenter_name": member_participant.participant_name},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_member_share_granted.status_code, 200)
        room_session.refresh_from_db()
        self.assertEqual(room_session.active_screenshare_presenter, member_participant.participant_name)

        # 10. Check transcript API response serialization
        res_api = self.client.get(f"/api/rooms/{room_session.room_code}/transcript/")
        self.assertEqual(res_api.status_code, 200)
        api_data = res_api.json()
        self.assertIn("allow_participant_screen_share", api_data)
        self.assertIn("active_screenshare_presenter", api_data)
        self.assertIn("can_share_screen", api_data)
        self.assertEqual(api_data["active_screenshare_presenter"], member_participant.participant_name)
        self.assertTrue(api_data["can_share_screen"])

        # 10b. Legacy HTTP screen frame upload is strictly rejected with 410 Gone (WebRTC SFU required)
        res_frame = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {
                "action": "broadcast_screen_frame",
                "frame_data_url": "data:image/jpeg;base64,sampleframe123",
                "seq": "1",
                "presenter_name": member_participant.participant_name,
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_frame.status_code, 410)
        self.assertEqual(res_frame.json().get("code"), "WEBRTC_SCREENSHARE_REQUIRED")

        # 11. Host revokes per-participant permission
        self.client.force_login(self.host_user)
        res_revoke = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "toggle_screenshare_permission", "participant_id": str(member_participant.id)},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_revoke.status_code, 200)
        member_participant.refresh_from_db()
        self.assertFalse(member_participant.can_share_screen(is_host=False))

        # 12. Member leaves room -> immediately omitted from participants roster
        self.client.force_login(self.participant_user)
        res_leave = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "leave_room", "participant_id": str(member_participant.id)},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_leave.status_code, 200)
        member_participant.refresh_from_db()
        self.assertEqual(member_participant.admission_status, "LEFT")
        self.assertEqual(member_participant.connection_status, "Left")

        # Verify host transcript API roster now excludes member
        self.client.force_login(self.host_user)
        res_after_leave = self.client.get(f"/api/rooms/{room_session.room_code}/transcript/")
        self.assertEqual(res_after_leave.status_code, 200)
        active_names = [p["participant_name"] for p in res_after_leave.json()["participants"]]
        self.assertNotIn(member_participant.participant_name, active_names)

    def test_core_meeting_tools_chat_attendance_and_transcript_minutes_export(self):
        """
        Verifies core meeting tools:
        1. In-room persistent chat:
           - Participant sends message via /api/rooms/<room_code>/chat/
           - Host sends official announcement
           - In-room chat messages synced in transcript API and HTML workspace
        2. Attendance report:
           - Host accesses /foundation/rooms/<room_code>/attendance/
           - Printable view shows verified attendee metrics and language distribution
           - Export as CSV (?export=csv)
           - Participant list JSON endpoint (/api/rooms/<room_code>/attendance/)
        3. Saved transcript with minutes export:
           - /foundation/rooms/<room_code>/transcript/export/?format=minutes
           - Formatted executive minutes document with agenda, attendance roster,
             official MTG-05 and MTG-05-RECORD follow-up links, and bilingual transcript
           - Export as CSV (?format=csv)
           - Export as JSON (?format=json)
        4. Auto-synchronization of live room attendance into Stage 09 MeetingParticipantRecord
           upon session completion.
        """
        seeded = seed_stage10_fixtures()
        room_session = seeded["room_session"]

        # Ensure host and participant session records exist and are admitted
        host_p = RoomParticipantSession.objects.filter(
            room_session=room_session,
            person_profile=self.host_profile,
        ).first()
        if not host_p:
            host_p = RoomParticipantSession.objects.create(
                room_session=room_session,
                person_profile=self.host_profile,
                participant_name=self.host_profile.full_name,
                meeting_role="Host",
                speaking_language="en-US",
                listening_language="fr-FR",
                admission_status="ADMITTED",
                connection_status="Connected",
            )
        else:
            host_p.admission_status = "ADMITTED"
            host_p.connection_status = "Connected"
            host_p.save()

        member_p = RoomParticipantSession.objects.filter(
            room_session=room_session,
            person_profile=self.participant_profile,
        ).first()
        if not member_p:
            member_p = RoomParticipantSession.objects.create(
                room_session=room_session,
                person_profile=self.participant_profile,
                participant_name=self.participant_profile.full_name,
                meeting_role="Participant",
                speaking_language="en-US",
                listening_language="fr-FR",
                admission_status="ADMITTED",
                connection_status="Connected",
            )
        else:
            member_p.admission_status = "ADMITTED"
            member_p.connection_status = "Connected"
            member_p.save()

        # Seed some transcript segments if not present
        if not room_session.transcript_segments.exists():
            LiveTranscriptSegment.objects.create(
                room_session=room_session,
                speaker_profile=self.host_profile,
                speaker_name="Ada Okafor",
                original_language="en-US",
                original_text="Welcome to the regional strategic planning session.",
                translations={"fr": "Bienvenue à la session de planification stratégique régionale."},
                confidence_score=0.98,
                sequence_number=1,
            )
            LiveTranscriptSegment.objects.create(
                room_session=room_session,
                speaker_profile=self.participant_profile,
                speaker_name="Zainab Musa",
                original_language="en-US",
                original_text="Action: Submit chapter budget proposal by Friday.",
                translations={"fr": "Action: Soumettre la proposition de budget par vendredi."},
                confidence_score=0.96,
                sequence_number=2,
            )

        # -------------------------------------------------------------
        # 1. In-Room Chat: Participant message + Host announcement
        # -------------------------------------------------------------
        self.client.force_login(self.participant_user)
        res_member_msg = self.client.post(
            f"/api/rooms/{room_session.room_code}/chat/",
            {"message": "Hello everyone, listening in French today."},
        )
        self.assertEqual(res_member_msg.status_code, 201)
        member_msg_data = res_member_msg.json()
        self.assertTrue(member_msg_data["ok"])
        self.assertEqual(member_msg_data["message"]["sender_name"], "Zainab Musa")
        self.assertFalse(member_msg_data["message"]["is_host_announcement"])

        # Host sends an announcement message
        self.client.force_login(self.host_user)
        res_host_msg = self.client.post(
            f"/api/rooms/{room_session.room_code}/chat/",
            {
                "message": "Notice: Please review the minutes & follow-up agenda items.",
                "is_announcement": "true",
            },
        )
        self.assertEqual(res_host_msg.status_code, 201)
        host_msg_data = res_host_msg.json()
        self.assertTrue(host_msg_data["ok"])
        self.assertTrue(host_msg_data["message"]["is_host_announcement"])
        self.assertEqual(host_msg_data["message"]["sender_role"], "Host")

        # Verify chat messages via Transcript API
        res_transcript_api = self.client.get(f"/api/rooms/{room_session.room_code}/transcript/")
        self.assertEqual(res_transcript_api.status_code, 200)
        api_data = res_transcript_api.json()
        self.assertIn("chat_messages", api_data)
        chat_texts = [m["message_text"] for m in api_data["chat_messages"]]
        self.assertIn("Hello everyone, listening in French today.", chat_texts)
        self.assertIn("Notice: Please review the minutes & follow-up agenda items.", chat_texts)

        # Verify in-room workspace UI has Chat tab, dock button, and message items
        res_live_ui = self.client.get(f"/foundation/rooms/{room_session.room_code}/live/")
        self.assertEqual(res_live_ui.status_code, 200)
        html_content = res_live_ui.content.decode("utf-8")
        self.assertIn('id="btn-dock-chat"', html_content)
        self.assertIn('id="tab-pane-chat"', html_content)
        self.assertIn('id="room-chat-feed"', html_content)
        self.assertIn('id="room-chat-form"', html_content)
        self.assertIn("Hello everyone, listening in French today.", html_content)
        self.assertIn(html_lib.escape("Notice: Please review the minutes & follow-up agenda items."), html_content)

        # -------------------------------------------------------------
        # 2. Attendance Report View and CSV Export
        # -------------------------------------------------------------
        res_att_html = self.client.get(f"/foundation/rooms/{room_session.room_code}/attendance/")
        self.assertEqual(res_att_html.status_code, 200)
        att_html = res_att_html.content.decode("utf-8")
        self.assertIn("ATTENDANCE ROSTER &amp; AUDIT REPORT", att_html)
        self.assertIn("Ada Okafor", att_html)
        self.assertIn("Zainab Musa", att_html)
        self.assertIn("Minutes &amp; Follow-Up", att_html)
        self.assertIn("Export CSV", att_html)

        # Attendance CSV Export
        res_att_csv = self.client.get(f"/foundation/rooms/{room_session.room_code}/attendance/?export=csv")
        self.assertEqual(res_att_csv.status_code, 200)
        self.assertIn("text/csv", res_att_csv["Content-Type"])
        csv_body = res_att_csv.content.decode("utf-8")
        self.assertIn("Participant Name,Role,Network,Country", csv_body)
        self.assertIn("Connection Status", csv_body)
        self.assertIn("Ada Okafor", csv_body)
        self.assertIn("Zainab Musa", csv_body)

        # Attendance API JSON endpoint
        res_att_api = self.client.get(f"/api/rooms/{room_session.room_code}/attendance/")
        self.assertEqual(res_att_api.status_code, 200)
        att_json = res_att_api.json()
        self.assertTrue(att_json["ok"])
        self.assertGreaterEqual(att_json["total_count"], 2)

        # -------------------------------------------------------------
        # 3. Saved Transcript with Minutes Export (linked to Minutes & Follow-Up)
        # -------------------------------------------------------------
        # Minutes text export
        res_exp_minutes = self.client.get(f"/foundation/rooms/{room_session.room_code}/transcript/export/?format=minutes")
        self.assertEqual(res_exp_minutes.status_code, 200)
        self.assertIn("text/plain", res_exp_minutes["Content-Type"])
        self.assertIn("attachment", res_exp_minutes["Content-Disposition"])
        minutes_body = res_exp_minutes.content.decode("utf-8")
        self.assertIn("WDOS OFFICIAL MEETING MINUTES & MULTILINGUAL TRANSCRIPT", minutes_body)
        self.assertIn("SECTION 1: VERIFIED ATTENDANCE", minutes_body)
        self.assertIn("/foundation/meetings/follow-up/?meeting=", minutes_body)
        self.assertIn("/foundation/meetings/attendance-minutes/?meeting=", minutes_body)
        self.assertIn("SECTION 3: MULTILINGUAL TRANSCRIPT APPENDIX", minutes_body)
        self.assertIn("Ada Okafor", minutes_body)
        self.assertIn("Zainab Musa", minutes_body)

        # CSV transcript export
        res_exp_csv = self.client.get(f"/foundation/rooms/{room_session.room_code}/transcript/export/?format=csv")
        self.assertEqual(res_exp_csv.status_code, 200)
        self.assertIn("text/csv", res_exp_csv["Content-Type"])
        csv_transcript = res_exp_csv.content.decode("utf-8")
        self.assertIn("Timestamp,Speaker,Original Language,Original Text", csv_transcript)

        # JSON transcript export
        res_exp_json = self.client.get(f"/foundation/rooms/{room_session.room_code}/transcript/export/?format=json")
        self.assertEqual(res_exp_json.status_code, 200)
        self.assertIn("application/json", res_exp_json["Content-Type"])
        exp_json = res_exp_json.json()
        self.assertEqual(exp_json["room_code"], room_session.room_code)
        self.assertIn("segments", exp_json)
        self.assertIn("chat_messages", exp_json)

        # -------------------------------------------------------------
        # 4. Bridge & Synchronization with MTG-05 / MTG-05-RECORD
        # -------------------------------------------------------------
        # End room session via host action
        res_end = self.client.post(
            f"/api/rooms/{room_session.room_code}/end/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_end.status_code, 200)
        room_session.refresh_from_db()
        self.assertEqual(room_session.status, "COMPLETED")

        # Verify Stage 09 MeetingParticipantRecord records were created and linked to the meeting
        mtg = room_session.meeting_series
        self.assertIsNotNone(mtg)
        participant_records = MeetingParticipantRecord.objects.filter(meeting=mtg)
        p_names = list(participant_records.values_list("participant_name", flat=True))
        self.assertIn("Ada Okafor", p_names)
        self.assertIn("Zainab Musa", p_names)
        zainab_rec = participant_records.get(participant_name="Zainab Musa")
        self.assertEqual(zainab_rec.attendance_status, "Present")
        self.assertIn(room_session.room_code, zainab_rec.detail_note)

    def test_room_security_controls_lock_passcode_expiry_and_admit_all_confirmation(self):
        """
        Verifies Stage 10 Security and Room Controls:
        1. Room Lock: Host locks/unlocks room. Non-hosts blocked when locked.
        2. Optional Passcode: Host sets entry passcode. Non-hosts require passcode.
        3. Link Expiry: Non-hosts blocked when link is expired.
        4. Guest Name Impersonation Protection: Guests blocked from using registered member
           or host names, flagged as unverified guest.
        5. Admit All Confirmation Step: Host requires confirmation before admitting all.
        """
        seeded = seed_stage10_fixtures()
        room_session = seeded["room_session"]

        # Ensure host and participant session records exist
        host_p = RoomParticipantSession.objects.filter(
            room_session=room_session,
            person_profile=self.host_profile,
        ).first()
        if not host_p:
            host_p = RoomParticipantSession.objects.create(
                room_session=room_session,
                person_profile=self.host_profile,
                participant_name=self.host_profile.full_name,
                meeting_role="Host",
                speaking_language="en-US",
                listening_language="fr-FR",
                admission_status="ADMITTED",
                connection_status="Connected",
            )
        else:
            host_p.admission_status = "ADMITTED"
            host_p.connection_status = "Connected"
            host_p.save()

        # Host allows guest access so guests and members can both be tested
        self.client.force_login(self.host_user)
        res_access = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "toggle_room_access", "room_access": "anyone_with_link"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_access.status_code, 200)
        room_session.refresh_from_db()
        self.assertTrue(room_session.allow_guest_access)

        # -------------------------------------------------------------
        # 1. Room Lock Control
        # -------------------------------------------------------------
        self.assertFalse(room_session.is_locked)
        # Host locks the room
        self.client.force_login(self.host_user)
        res_lock = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "toggle_room_lock"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_lock.status_code, 200)
        self.assertTrue(res_lock.json()["is_locked"])
        room_session.refresh_from_db()
        self.assertTrue(room_session.is_locked)

        # An unadmitted/new user attempts to prejoin -> blocked with notice
        guest_client = Client()
        res_prejoin_locked = guest_client.get(f"/foundation/rooms/{room_session.room_code}/prejoin/")
        self.assertEqual(res_prejoin_locked.status_code, 200)
        locked_html = res_prejoin_locked.content.decode("utf-8")
        self.assertIn("locked by the host", locked_html)

        # Attempt to join locked room via POST -> rejected
        res_post_locked = guest_client.post(
            f"/foundation/rooms/{room_session.room_code}/prejoin/",
            {"action": "guest_join", "guest_name": "New Visitor", "speaking_language": "en-US", "listening_language": "fr-FR"},
        )
        self.assertEqual(res_post_locked.status_code, 200)
        self.assertIn("locked by the host", res_post_locked.content.decode("utf-8"))

        # Host unlocks the room
        res_unlock = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "toggle_room_lock"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_unlock.status_code, 200)
        self.assertFalse(res_unlock.json()["is_locked"])
        room_session.refresh_from_db()
        self.assertFalse(room_session.is_locked)

        # -------------------------------------------------------------
        # 2. Optional Passcode Protection
        # -------------------------------------------------------------
        self.assertFalse(room_session.has_passcode)
        # Host sets a passcode
        res_passcode = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "set_passcode", "passcode": "SECURE-9900"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_passcode.status_code, 200)
        room_session.refresh_from_db()
        self.assertTrue(room_session.has_passcode)
        self.assertEqual(room_session.passcode, "SECURE-9900")

        # Guest attempts to join without passcode -> rejected
        res_no_pass = guest_client.post(
            f"/foundation/rooms/{room_session.room_code}/prejoin/",
            {"action": "guest_join", "guest_name": "Visitor Bob", "speaking_language": "en-US", "listening_language": "fr-FR"},
        )
        self.assertIn("passcode is required", res_no_pass.content.decode("utf-8").lower())

        # Guest attempts to join with wrong passcode -> rejected
        res_wrong_pass = guest_client.post(
            f"/foundation/rooms/{room_session.room_code}/prejoin/",
            {"action": "guest_join", "guest_name": "Visitor Bob", "passcode": "WRONG-1234", "speaking_language": "en-US", "listening_language": "fr-FR"},
        )
        self.assertIn("Incorrect passcode", res_wrong_pass.content.decode("utf-8"))
        # Ensure "Go to Meetings" button is NOT displayed on error banner
        self.assertNotIn("Go to Meetings", res_wrong_pass.content.decode("utf-8"))

        # Passcode bypass attempt: reload or navigate to waiting/live room after failed passcode
        res_bypass_waiting = guest_client.get(f"/foundation/rooms/{room_session.room_code}/waiting/")
        self.assertEqual(res_bypass_waiting.status_code, 200)
        waiting_html = res_bypass_waiting.content.decode("utf-8")
        self.assertIn('id="prejoin-screen"', waiting_html)
        self.assertNotIn('id="waiting-lobby-screen"', waiting_html)

        res_bypass_live = guest_client.get(f"/foundation/rooms/{room_session.room_code}/live/")
        self.assertEqual(res_bypass_live.status_code, 200)
        live_html = res_bypass_live.content.decode("utf-8")
        self.assertIn('id="prejoin-screen"', live_html)
        self.assertNotIn('id="live-transcript-feed"', live_html)
        self.assertNotIn('id="waiting-lobby-screen"', live_html)

        # POST directly to live endpoint with wrong passcode
        res_wrong_post_live = guest_client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "guest_join", "guest_name": "Visitor Bob", "passcode": "WRONG-9999", "speaking_language": "en-US", "listening_language": "fr-FR"},
        )
        self.assertEqual(res_wrong_post_live.status_code, 200)
        post_live_html = res_wrong_post_live.content.decode("utf-8")
        self.assertIn("Incorrect passcode", post_live_html)
        self.assertIn('id="prejoin-screen"', post_live_html)
        self.assertNotIn('id="waiting-lobby-screen"', post_live_html)
        self.assertNotIn("Go to Meetings", post_live_html)

        # Token API attempt without passcode verification -> blocked with 403
        res_token_blocked = guest_client.get(f"/api/rooms/{room_session.room_code}/tokens/")
        self.assertEqual(res_token_blocked.status_code, 403)

        # Subsequent GET to waiting room must STILL be forced to prejoin screen
        res_still_blocked = guest_client.get(f"/foundation/rooms/{room_session.room_code}/waiting/")
        self.assertIn('id="prejoin-screen"', res_still_blocked.content.decode("utf-8"))
        self.assertNotIn('id="waiting-lobby-screen"', res_still_blocked.content.decode("utf-8"))

        # Guest provides correct passcode -> succeeds
        res_correct_pass = guest_client.post(
            f"/foundation/rooms/{room_session.room_code}/prejoin/",
            {"action": "guest_join", "guest_name": "Visitor Bob", "passcode": "SECURE-9900", "speaking_language": "en-US", "listening_language": "fr-FR"},
        )
        self.assertEqual(res_correct_pass.status_code, 302)

        # Host clears the passcode
        self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "set_passcode", "passcode": ""},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        room_session.refresh_from_db()
        self.assertFalse(room_session.has_passcode)

        # -------------------------------------------------------------
        # 3. Link Expiry
        # -------------------------------------------------------------
        # Set link_expires_at in the past
        room_session.link_expires_at = timezone.now() - timezone.timedelta(hours=1)
        room_session.save(update_fields=["link_expires_at"])
        self.assertTrue(room_session.is_link_expired)

        # Non-host access -> blocked with link expired notice
        guest_client2 = Client()
        res_expired = guest_client2.get(f"/foundation/rooms/{room_session.room_code}/prejoin/")
        self.assertEqual(res_expired.status_code, 200)
        self.assertIn("meeting link expired", res_expired.content.decode("utf-8").lower())

        # Host extends/clears link expiry
        self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "set_link_expiry", "expiry_hours": "clear"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        room_session.refresh_from_db()
        self.assertFalse(room_session.is_link_expired)
        self.assertIsNone(room_session.link_expires_at)

        # -------------------------------------------------------------
        # 4. Impersonation Protection & Guest Tagging
        # -------------------------------------------------------------
        # Guest attempts to use host's display name -> blocked
        res_imp_host = guest_client2.post(
            f"/foundation/rooms/{room_session.room_code}/prejoin/",
            {"action": "guest_join", "guest_name": "Ada Okafor", "speaking_language": "en-US", "listening_language": "fr-FR"},
        )
        self.assertTrue(
            "registered wdos member" in res_imp_host.content.decode("utf-8").lower()
            or "designated meeting host" in res_imp_host.content.decode("utf-8").lower()
        )

        # Guest attempts to use registered member's display name -> blocked
        res_imp_member = guest_client2.post(
            f"/foundation/rooms/{room_session.room_code}/prejoin/",
            {"action": "guest_join", "guest_name": "Zainab Musa", "speaking_language": "en-US", "listening_language": "fr-FR"},
        )
        self.assertIn("registered wdos member", res_imp_member.content.decode("utf-8").lower())

        # Guest attempts name with less than 2 chars -> blocked
        res_short = guest_client2.post(
            f"/foundation/rooms/{room_session.room_code}/prejoin/",
            {"action": "guest_join", "guest_name": "X", "speaking_language": "en-US", "listening_language": "fr-FR"},
        )
        self.assertIn("at least 2 characters", res_short.content.decode("utf-8").lower())

        # Guest joins with legitimate unique name -> allowed and tagged as guest
        res_valid_guest = guest_client2.post(
            f"/foundation/rooms/{room_session.room_code}/prejoin/",
            {"action": "guest_join", "guest_name": "Dr. Observer Mark", "speaking_language": "en-US", "listening_language": "fr-FR"},
        )
        self.assertEqual(res_valid_guest.status_code, 302)
        guest_p = RoomParticipantSession.objects.filter(
            room_session=room_session,
            participant_name="Dr. Observer Mark",
        ).first()
        self.assertIsNotNone(guest_p)
        self.assertTrue(guest_p.is_guest)
        self.assertFalse(guest_p.is_verified_member)
        self.assertEqual(guest_p.display_role_badge, "Guest")

        # -------------------------------------------------------------
        # 5. Admit All Confirmation Step
        # -------------------------------------------------------------
        # Ensure 2 participants are in WAITING_ROOM (guest_p + member_waiting)
        guest_p.admission_status = "WAITING_ROOM"
        guest_p.save()

        member_waiting = RoomParticipantSession.objects.filter(
            room_session=room_session,
            participant_name=self.participant_profile.full_name,
        ).first()
        if not member_waiting:
            member_waiting = RoomParticipantSession.objects.create(
                room_session=room_session,
                person_profile=self.participant_profile,
                participant_name=self.participant_profile.full_name,
                meeting_role="Participant",
                speaking_language="en-US",
                listening_language="fr-FR",
            )
        member_waiting.admission_status = "WAITING_ROOM"
        member_waiting.save()

        # Host issues admit_all WITHOUT confirmed flag -> returns confirmation_required
        res_unconfirmed = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "admit_all"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_unconfirmed.status_code, 200)
        unconfirmed_data = res_unconfirmed.json()
        self.assertEqual(unconfirmed_data["status"], "confirmation_required")
        self.assertEqual(unconfirmed_data["action"], "admit_all")
        self.assertGreaterEqual(unconfirmed_data["waiting_count"], 2)
        self.assertGreaterEqual(unconfirmed_data["unverified_guests_count"], 1)

        # Verify waiting participants were NOT admitted yet
        guest_p.refresh_from_db()
        self.assertEqual(guest_p.admission_status, "WAITING_ROOM")
        member_waiting.refresh_from_db()
        self.assertEqual(member_waiting.admission_status, "WAITING_ROOM")

        # Host confirms Admit All -> all waiting participants admitted
        res_confirmed = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/live/",
            {"action": "admit_all", "confirmed": "1"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_confirmed.status_code, 200)
        confirmed_data = res_confirmed.json()
        self.assertEqual(confirmed_data["status"], "updated")
        self.assertEqual(confirmed_data["action"], "admit_all")
        self.assertGreaterEqual(confirmed_data["admitted_count"], 2)

        guest_p.refresh_from_db()
        self.assertEqual(guest_p.admission_status, "ADMITTED")
        member_waiting.refresh_from_db()
        self.assertEqual(member_waiting.admission_status, "ADMITTED")

        # Verify transcript API returns security flags
        res_trans_sec = self.client.get(f"/api/rooms/{room_session.room_code}/transcript/")
        self.assertEqual(res_trans_sec.status_code, 200)
        trans_sec_data = res_trans_sec.json()
        self.assertIn("is_locked", trans_sec_data)
        self.assertIn("has_passcode", trans_sec_data)
        self.assertIn("is_link_expired", trans_sec_data)

        # 6. Verify policy update syncs MeetingSeries allow_guest_access and access_policy_label properties
        meeting_series = seeded.get("meeting_series") or room_session.meeting_series
        if meeting_series:
            from foundation.multilingua_events_views import _update_room_policies
            _update_room_policies(room_session, getattr(room_session, "scheduled_meeting", None), allow_guests=True)
            room_session.refresh_from_db()
            self.assertTrue(room_session.allow_guest_access)
            self.assertTrue(meeting_series.allow_guest_access)
            self.assertEqual(meeting_series.access_policy_label, "Anyone with the link")

            _update_room_policies(room_session, getattr(room_session, "scheduled_meeting", None), allow_guests=False)
            room_session.refresh_from_db()
            self.assertFalse(room_session.allow_guest_access)
            self.assertFalse(meeting_series.allow_guest_access)
            self.assertEqual(meeting_series.access_policy_label, "WDOS accounts only")

    def test_meeting_invitations_calendar_ics_email_dispatch_and_multi_timezone(self):
        """
        Verifies Stage 10 Meeting Invitations, Calendar (.ics), Reminders & Timezones:
        1. Multi-timezone scheduled conversion (WAT, CAT, EAT, UTC)
        2. RFC 5545 iCalendar (.ics) generation & download endpoint
        3. Email invitation dispatch with .ics attachment & invitation_history tracking
        4. Meeting reminders dispatch, reminder_count increment & history tracking
        5. UI rendering with detected/selected timezone badge & download link
        """
        from django.core import mail
        import zoneinfo

        seeded = seed_stage10_fixtures()
        room_session = seeded["room_session"]
        self.assertIsNotNone(room_session)
        self.client.force_login(self.host_user)

        # 1. Multi-Timezone conversion verification
        dt = room_session.scheduled_datetime
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, datetime.timezone.utc)
        else:
            dt = dt.astimezone(datetime.timezone.utc)

        expected_wat = f"{dt.astimezone(zoneinfo.ZoneInfo('Africa/Lagos')).strftime('%H:%M')} WAT"
        expected_cat = f"{dt.astimezone(zoneinfo.ZoneInfo('Africa/Harare')).strftime('%H:%M')} CAT"
        expected_eat = f"{dt.astimezone(zoneinfo.ZoneInfo('Africa/Nairobi')).strftime('%H:%M')} EAT"
        expected_utc = f"{dt.astimezone(datetime.timezone.utc).strftime('%H:%M')} UTC"

        self.assertEqual(room_session.wat_time_label, expected_wat)
        self.assertEqual(room_session.cat_time_label, expected_cat)
        self.assertEqual(room_session.eat_time_label, expected_eat)
        self.assertEqual(room_session.utc_time_label, expected_utc)

        # Check schedule info helper with explicit viewer timezone (e.g. Nairobi)
        from .multilingua_events_views import _get_meeting_schedule_info, generate_meeting_ics
        sched_info = _get_meeting_schedule_info(room_session, viewer_tz="Africa/Nairobi")
        expected_eat_time = dt.astimezone(zoneinfo.ZoneInfo("Africa/Nairobi")).strftime("%H:%M")
        self.assertIn(f"{expected_eat_time} Africa/Nairobi", sched_info["viewer_local_label"])
        self.assertEqual(len(sched_info["timezone_table"]), 4)

        # 2. RFC 5545 iCalendar (.ics) generation & HTTP endpoints
        ics_text = generate_meeting_ics(room_session)
        self.assertIn("BEGIN:VCALENDAR", ics_text)
        self.assertIn("VERSION:2.0", ics_text)
        self.assertIn("PRODID:-//WDOS//Multilingua Meeting Engine//EN", ics_text)
        self.assertIn("BEGIN:VEVENT", ics_text)
        self.assertIn("STATUS:CONFIRMED", ics_text)
        self.assertIn("BEGIN:VALARM", ics_text)
        self.assertIn("TRIGGER:-PT15M", ics_text)
        self.assertIn("END:VALARM", ics_text)
        self.assertIn("END:VEVENT", ics_text)
        self.assertIn("END:VCALENDAR", ics_text)

        # Test download endpoint
        res_ics = self.client.get(f"/foundation/rooms/{room_session.room_code}/calendar.ics")
        self.assertEqual(res_ics.status_code, 200)
        self.assertEqual(res_ics["Content-Type"], "text/calendar; charset=utf-8")
        self.assertIn(f"meeting_{room_session.room_code}.ics", res_ics["Content-Disposition"])
        self.assertIn(b"BEGIN:VCALENDAR", res_ics.content)

        # Test API alias for .ics
        res_ics_api = self.client.get(f"/api/rooms/{room_session.room_code}/calendar.ics")
        self.assertEqual(res_ics_api.status_code, 200)
        self.assertIn(b"BEGIN:VCALENDAR", res_ics_api.content)

        # 3. Email invitation dispatch with attached .ics
        mail.outbox.clear()
        initial_history_len = len(room_session.invitation_history)

        invite_recipients = ["invitee1@wdos.test", "invitee2@ngo.africa"]
        res_email = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/invite/email/",
            {
                "recipients": ", ".join(invite_recipients),
                "personal_note": "Please review the quarterly agenda before attending.",
                "attach_ics": "1",
            },
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_email.status_code, 200)
        data_email = res_email.json()
        self.assertEqual(data_email["status"], "success")
        self.assertEqual(data_email["recipients_count"], 2)

        # Verify email was dispatched in mail.outbox
        self.assertEqual(len(mail.outbox), 1)
        sent_email = mail.outbox[0]
        self.assertIn("Invitation:", sent_email.subject)
        self.assertIn(room_session.title, sent_email.subject)
        self.assertEqual(sorted(sent_email.to), sorted(invite_recipients))
        self.assertIn("Please review the quarterly agenda", sent_email.body)
        self.assertIn(expected_wat, sent_email.body)
        self.assertIn(expected_cat, sent_email.body)
        self.assertIn(expected_eat, sent_email.body)

        # Verify .ics attachment in email
        self.assertTrue(len(sent_email.attachments) >= 1)
        att_filename, att_content, att_mimetype = sent_email.attachments[0]
        self.assertTrue(att_filename.endswith(".ics"))
        self.assertIn("text/calendar", att_mimetype)
        self.assertIn("BEGIN:VCALENDAR", att_content)

        # Verify room_session.invitation_history tracking
        room_session.refresh_from_db()
        self.assertEqual(len(room_session.invitation_history), initial_history_len + 1)
        latest_inv = room_session.invitation_history[-1]
        self.assertEqual(latest_inv["recipient_count"], 2)
        self.assertTrue(latest_inv["has_note"])

        # 4. Meeting Reminders dispatch & tracking
        mail.outbox.clear()
        initial_reminders = room_session.reminder_count

        res_reminder = self.client.post(
            f"/foundation/rooms/{room_session.room_code}/reminders/",
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertEqual(res_reminder.status_code, 200)
        data_rem = res_reminder.json()
        self.assertEqual(data_rem["status"], "success")
        self.assertEqual(data_rem["reminder_count"], initial_reminders + 1)

        # Verify reminder email sent
        self.assertEqual(len(mail.outbox), 1)
        rem_email = mail.outbox[0]
        self.assertIn("REMINDER:", rem_email.subject)

        room_session.refresh_from_db()
        self.assertEqual(room_session.reminder_count, initial_reminders + 1)
        self.assertIsNotNone(room_session.reminder_sent_at)
        self.assertTrue(room_session.has_reminders_sent)
        self.assertNotEqual(room_session.last_reminder_label, "No reminders sent yet")

        # 5. UI Prejoin (ROOM-01) & Live Room render with Multi-Timezone & Calendar elements
        res_prejoin = self.client.get(f"/foundation/rooms/{room_session.room_code}/prejoin/")
        self.assertEqual(res_prejoin.status_code, 200)
        self.assertContains(res_prejoin, "Add to Calendar (.ics)")
        self.assertContains(res_prejoin, "Meeting Schedule &amp; Local Time")
        self.assertContains(res_prejoin, room_session.wat_time_label)
        self.assertContains(res_prejoin, "guest-local-time-badge")

        # Meeting detail page includes Invite & Calendar button, Attendance Report, and white-bg Modal
        from accounts.models import Account, OnboardingDraft, Person
        host_person = Person.objects.create(display_name="Ada Okafor")
        host_account = Account.objects.create(
            user=self.host_user,
            email=self.host_user.email,
            person=host_person,
            status="active",
            display_name="Ada Okafor",
            security_version=1,
            verified_at=timezone.now(),
        )
        OnboardingDraft.objects.create(
            account=host_account,
            state="accepted",
            next_step=8,
            data={"language": "en", "timezone": "Africa/Lagos", "network": "WGMN", "country": "NG"},
        )
        self.host_user.is_staff = True
        self.host_user.save()

        # Update test client session with valid security & MFA credentials
        self.client.force_login(self.host_user)
        session = self.client.session
        now_ts = timezone.now().timestamp()
        session["security_version"] = host_account.security_version
        session["mfa_verified"] = True
        session["last_activity"] = now_ts
        session["absolute_expiry"] = now_ts + 43200
        session.save()

        meeting_code = room_session.meeting_series.meeting_code if room_session.meeting_series else "MTG-NG-001"
        res_detail = self.client.get(f"/foundation/meetings/{meeting_code}/")
        self.assertEqual(res_detail.status_code, 200)
        self.assertContains(res_detail, "Invite &amp; Calendar")
        self.assertContains(res_detail, "Attendance Report")
        self.assertContains(res_detail, "invite-modal")
        self.assertContains(res_detail, "Download iCalendar File (.ics)")
        self.assertContains(res_detail, "Meeting Reminders")
        self.assertContains(res_detail, "Room Access &amp; Restrict Controls")

        # Live room render: Top bar only has Copy meet link, End meeting, Leave meeting;
        # Inside room controls strictly have Bypass Meeting and Lock Meeting
        res_live = self.client.get(f"/foundation/rooms/{room_session.room_code}/live/")
        self.assertEqual(res_live.status_code, 200)
        self.assertContains(res_live, "Copy meet link")
        self.assertContains(res_live, "End meeting")
        self.assertContains(res_live, "Leave meeting")
        self.assertContains(res_live, "Bypass Meeting")
        self.assertContains(res_live, "Lock Meeting")

    def test_livekit_realtime_delta_reconciliation_webhook_and_video_grid(self):
        """
        Verifies Google Meet / Zoom-grade LiveKit real-time architecture:
        1. Role-aware least-privilege LiveKit JWT grants (host vs participant vs bot).
        2. Delta state reconciliation (?mode=delta&state_v=...) returning ~80B unchanged payload
           when room state has not mutated, eliminating the 8.8 KB polling storm.
        3. Incremental transcript cursor (?after_seq=...) returning only new segments.
        4. Cryptographic JWT + SHA-256 LiveKit Server Webhook verification (/api/livekit/webhook/)
           for participant_joined, participant_left, and room_finished events.
        5. Multi-participant video grid (#live-video-grid), layout controls, quality indicator,
           and emoji reaction bar in the live room workspace.
        """
        import hashlib
        import hmac
        import base64
        from .multilingua.zoom_adapter import LiveKitAdapter

        seeded = seed_stage10_fixtures()
        room_session = seeded["room_session"]
        self.client.force_login(self.host_user)

        test_lk_key = "APIwdostestkey123"
        test_lk_secret = "wdos_super_secret_livekit_signing_key_2026_test"

        with self.settings(
            LIVEKIT_URL="wss://wdos-test.livekit.cloud",
            LIVEKIT_API_KEY=test_lk_key,
            LIVEKIT_API_SECRET=test_lk_secret,
        ):
            # 1. Verify LiveKit role-aware token grants
            host_jwt = LiveKitAdapter.generate_token(
                session_name=room_session.room_code,
                user_id="host-1",
                participant_name="Ada Okafor",
                role_type=1,
            )
            token_parts = host_jwt.split(".")
            self.assertEqual(len(token_parts), 3)
            payload_b64 = token_parts[1] + "=" * (-len(token_parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8"))
            self.assertTrue(claims["video"]["roomAdmin"])
            self.assertTrue(claims["video"]["canUpdateOwnMetadata"])
            self.assertIn("screen_share", claims["video"]["canPublishSources"])

            # 2. Verify initial transcript fetch returns state_v and ETag
            res_init = self.client.get(f"/api/rooms/{room_session.room_code}/transcript/?lang=pt")
            self.assertEqual(res_init.status_code, 200)
            init_data = res_init.json()
            self.assertIn("state_v", init_data)
            state_v = init_data["state_v"]
            self.assertTrue(len(init_data.get("segments", [])) >= 1)
            max_seq = max(s["sequence_number"] for s in init_data["segments"])

            # 3. Verify delta reconciliation returns lightweight unchanged=True when state_v matches
            res_delta_unchanged = self.client.get(
                f"/api/rooms/{room_session.room_code}/transcript/?lang=pt&mode=delta&state_v={state_v}&after_seq={max_seq}"
            )
            self.assertEqual(res_delta_unchanged.status_code, 200)
            delta_data = res_delta_unchanged.json()
            self.assertTrue(delta_data.get("unchanged"))
            self.assertEqual(delta_data.get("state_v"), state_v)
            self.assertNotIn("segments", delta_data)

            # 4. Post a new transcript segment -> state_v bumps & after_seq returns only the new segment
            res_post = self.client.post(
                f"/api/rooms/{room_session.room_code}/transcript/",
                data=json.dumps({
                    "original_text": "LiveKit WebRTC data channels eliminate HTTP polling storms.",
                    "speaker_name": "Ada Okafor",
                    "original_language": "en-US",
                }),
                content_type="application/json",
            )
            self.assertIn(res_post.status_code, (200, 201))

            res_delta_changed = self.client.get(
                f"/api/rooms/{room_session.room_code}/transcript/?lang=pt&mode=delta&state_v={state_v}&after_seq={max_seq}"
            )
            self.assertEqual(res_delta_changed.status_code, 200)
            changed_data = res_delta_changed.json()
            self.assertFalse(changed_data.get("unchanged", False))
            self.assertNotEqual(changed_data.get("state_v"), state_v)
            self.assertEqual(len(changed_data["segments"]), 1)
            self.assertGreater(changed_data["segments"][0]["sequence_number"], max_seq)

            # 5. Verify LiveKit Webhook cryptographic verification (/api/livekit/webhook/)
            guest_p = RoomParticipantSession.objects.create(
                room_session=room_session,
                participant_name="Webhook Participant",
                meeting_role="Participant",
                admission_status="ADMITTED",
            )
            webhook_payload = json.dumps({
                "event": "participant_left",
                "room": {"name": room_session.room_code},
                "participant": {"identity": str(guest_p.id), "name": "Webhook Participant"},
            }).encode("utf-8")

            # Invalid signature should return 401
            res_wh_invalid = self.client.post(
                "/api/livekit/webhook/",
                data=webhook_payload,
                content_type="application/webhook+json",
                HTTP_AUTHORIZATION="Bearer invalid.jwt.token",
            )
            self.assertEqual(res_wh_invalid.status_code, 401)

            # Valid LiveKit webhook JWT signature with SHA-256 body hash
            body_sha256 = hashlib.sha256(webhook_payload).hexdigest()
            wh_header_b64 = base64.urlsafe_b64encode(
                json.dumps({"alg": "HS256", "typ": "JWT"}).encode("utf-8")
            ).decode("ascii").rstrip("=")
            wh_claims_b64 = base64.urlsafe_b64encode(
                json.dumps({
                    "iss": test_lk_key,
                    "exp": int(timezone.now().timestamp()) + 300,
                    "sha256": body_sha256,
                }).encode("utf-8")
            ).decode("ascii").rstrip("=")
            signing_input = f"{wh_header_b64}.{wh_claims_b64}".encode("ascii")
            wh_sig_b64 = base64.urlsafe_b64encode(
                hmac.new(test_lk_secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
            ).decode("ascii").rstrip("=")
            valid_wh_jwt = f"{wh_header_b64}.{wh_claims_b64}.{wh_sig_b64}"

            res_wh_valid = self.client.post(
                "/api/livekit/webhook/",
                data=webhook_payload,
                content_type="application/webhook+json",
                HTTP_AUTHORIZATION=f"Bearer {valid_wh_jwt}",
            )
            self.assertEqual(res_wh_valid.status_code, 200)
            guest_p.refresh_from_db()
            self.assertEqual(guest_p.admission_status, "LEFT")

            # 6. Verify Live Room renders multi-participant video grid, layout controls, quality pill, and reactions
            res_live_grid = self.client.get(f"/foundation/rooms/{room_session.room_code}/live/")
            self.assertEqual(res_live_grid.status_code, 200)
            self.assertContains(res_live_grid, 'id="live-video-grid"')
            self.assertContains(res_live_grid, 'id="btn-layout-grid"')
            self.assertContains(res_live_grid, 'id="btn-layout-speaker"')
            self.assertContains(res_live_grid, 'id="webrtc-quality-pill"')
            self.assertContains(res_live_grid, 'zm-reaction-btn')

    def test_thousand_participant_scale_webinar_egress_polls_and_no_http_media_fallbacks(self):
        """
        Verifies enterprise-grade 1,000+ participant scale, zero HTTP media fallbacks,
        distributed cache state, LiveKit official SDK token/egress/permission management,
        distributed worker room leases, and live audience polls:
        1. Rejects legacy HTTP audio_chunk and broadcast_screen_frame with 410 Gone.
        2. Scales to 1,050 admitted participants in a room -> automatically activates
           Webinar / Stage mode (>= 100 threshold), issuing subscriber-only tokens
           (canPublish=False) to general attendees and publisher tokens (canPublish=True)
           to Hosts / Active Speakers.
        3. Host granting floor (grant_floor) dynamically promotes the attendee to speaker
           and invokes LiveKit UpdateParticipant permissions.
        4. Cloud Recording (toggle_recording) starts and stops LiveKit RoomCompositeEgress.
        5. Live Polls (create_poll, vote_poll, close_poll) store state in distributed cache
           and broadcast over LiveKit DataChannel.
        6. TranslationAgentSupervisor distributed lease locking prevents duplicate room
           workers across multi-worker containers.
        """
        import base64
        import json
        from unittest.mock import patch
        from foundation.multilingua.zoom_adapter import LiveKitAdapter
        from foundation.multilingua.livekit_agent import TranslationAgentSupervisor

        test_lk_key = "APItestKeyEnterpriseScale1000"
        test_lk_secret = "SecretKeyEnterpriseScale1000MustBeAtLeast32BytesLong!"

        seeded = seed_stage10_fixtures()
        room_session = seeded["room_session"]
        self.client.force_login(self.host_user)

        with self.settings(
            LIVEKIT_URL="wss://livekit.wdos.example.org",
            LIVEKIT_API_KEY=test_lk_key,
            LIVEKIT_API_SECRET=test_lk_secret,
        ):
            # 1. Verify legacy HTTP audio_chunk is rejected with 410 Gone
            res_audio_chunk = self.client.post(
                f"/api/rooms/{room_session.room_code}/transcript/",
                data=json.dumps({
                    "action": "audio_chunk",
                    "audio_data_url": "data:audio/webm;base64,AAAA",
                }),
                content_type="application/json",
            )
            self.assertEqual(res_audio_chunk.status_code, 410)
            self.assertEqual(res_audio_chunk.json().get("code"), "WEBRTC_MEDIA_REQUIRED")

            # 2. Bulk-create 1,050 admitted participants to simulate a 1,000+ global summit
            bulk_participants = [
                RoomParticipantSession(
                    room_session=room_session,
                    participant_name=f"Summit Attendee {i}",
                    meeting_role="Participant",
                    speaking_language="en-US",
                    listening_language="fr-FR",
                    admission_status="ADMITTED",
                    connection_status="Connected",
                )
                for i in range(1, 1051)
            ]
            RoomParticipantSession.objects.bulk_create(bulk_participants)
            attendee_sample = RoomParticipantSession.objects.filter(
                room_session=room_session, participant_name="Summit Attendee 500"
            ).first()
            self.assertIsNotNone(attendee_sample)

            # 3. Verify transcript API reports webinar_mode=True and total_admitted_count >= 1050
            res_tx = self.client.get(f"/api/rooms/{room_session.room_code}/transcript/?lang=fr")
            self.assertEqual(res_tx.status_code, 200)
            tx_json = res_tx.json()
            self.assertTrue(tx_json.get("webinar_mode"))
            self.assertGreaterEqual(tx_json.get("total_admitted_count", 0), 1050)
            # Roster payload is bounded to 250 in 1,000+ rooms to keep JSON payloads fast
            self.assertLessEqual(len(tx_json.get("participants", [])), 250)

            # 4. Verify token endpoint issues can_publish=True for Host, and can_publish=False for regular attendee in 1,000+ room
            res_host_tok = self.client.get(f"/api/rooms/{room_session.room_code}/tokens/")
            self.assertEqual(res_host_tok.status_code, 200)
            host_tok_data = res_host_tok.json()
            self.assertTrue(host_tok_data.get("webinar_mode"))
            self.assertTrue(host_tok_data["participant"]["can_publish"])

            # Verify attendee subscriber-only JWT via official livekit-api SDK
            attendee_jwt = LiveKitAdapter.generate_token(
                session_name=room_session.room_code,
                user_id=str(attendee_sample.id),
                participant_name=attendee_sample.participant_name,
                role_type=0,
                can_publish=False,
                can_subscribe=True,
                can_publish_sources=[],
            )
            payload_b64 = attendee_jwt.split(".")[1]
            payload_b64 += "=" * (-len(payload_b64) % 4)
            attendee_claims = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8"))
            self.assertFalse(attendee_claims["video"]["canPublish"])
            self.assertTrue(attendee_claims["video"]["canSubscribe"])
            self.assertTrue(attendee_claims["video"]["canPublishData"])

            # 5. Host grants floor to Summit Attendee 500 -> promotes speaker & updates LiveKit permissions
            res_floor = self.client.post(
                f"/foundation/rooms/{room_session.room_code}/live/",
                {"action": "grant_floor", "participant_id": str(attendee_sample.id)},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertEqual(res_floor.status_code, 200)
            room_session.refresh_from_db()
            self.assertEqual(room_session.active_speaker_name, attendee_sample.participant_name)

            # 6. Cloud Recording (LiveKit Egress start/stop — never fakes success if Egress is unavailable)
            with patch.object(LiveKitAdapter, "_sdk_or_twirp_call", return_value=None):
                res_rec_unavail = self.client.post(
                    f"/foundation/rooms/{room_session.room_code}/live/",
                    {"action": "toggle_recording"},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
                self.assertEqual(res_rec_unavail.status_code, 502)
                self.assertEqual(res_rec_unavail.json().get("code"), "EGRESS_UNAVAILABLE")

            with patch.object(
                LiveKitAdapter,
                "_sdk_or_twirp_call",
                return_value={"egress_id": "EG_LIVEKIT_CONFIRMED_99", "status": "EGRESS_ACTIVE"},
            ):
                res_rec_start = self.client.post(
                    f"/foundation/rooms/{room_session.room_code}/live/",
                    {"action": "toggle_recording"},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
                self.assertEqual(res_rec_start.status_code, 200)
                rec_start_json = res_rec_start.json()
                self.assertTrue(rec_start_json["recording_state"]["is_recording"])
                self.assertEqual(rec_start_json["recording_state"]["egress_id"], "EG_LIVEKIT_CONFIRMED_99")

            with patch.object(
                LiveKitAdapter,
                "_sdk_or_twirp_call",
                return_value={"egress_id": "EG_LIVEKIT_CONFIRMED_99", "status": "EGRESS_COMPLETE"},
            ):
                res_rec_stop = self.client.post(
                    f"/foundation/rooms/{room_session.room_code}/live/",
                    {"action": "toggle_recording"},
                    HTTP_X_REQUESTED_WITH="XMLHttpRequest",
                )
                self.assertEqual(res_rec_stop.status_code, 200)
                self.assertFalse(res_rec_stop.json()["recording_state"]["is_recording"])

            # 7. Live Audience Polls (create, vote, close)
            res_poll_create = self.client.post(
                f"/foundation/rooms/{room_session.room_code}/live/",
                {
                    "action": "create_poll",
                    "question": "Adopt Continental Gender Charter?",
                    "options": "Approve, Abstain, Oppose",
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertEqual(res_poll_create.status_code, 200)
            poll_obj = res_poll_create.json()["poll"]
            poll_id = poll_obj["id"]
            self.assertEqual(poll_obj["question"], "Adopt Continental Gender Charter?")
            self.assertEqual(len(poll_obj["options"]), 3)

            res_poll_vote = self.client.post(
                f"/foundation/rooms/{room_session.room_code}/live/",
                {
                    "action": "vote_poll",
                    "poll_id": poll_id,
                    "option_index": "0",
                },
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertEqual(res_poll_vote.status_code, 200)
            self.assertEqual(res_poll_vote.json()["poll"]["votes"][0], 1)
            self.assertEqual(res_poll_vote.json()["poll"]["total_votes"], 1)

            res_poll_close = self.client.post(
                f"/foundation/rooms/{room_session.room_code}/live/",
                {"action": "close_poll", "poll_id": poll_id},
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
            self.assertEqual(res_poll_close.status_code, 200)
            self.assertFalse(res_poll_close.json()["poll"]["is_open"])

            # 8. Distributed Room Lease Coordination for Standalone Translation Worker
            worker1 = TranslationAgentSupervisor(worker_id="worker-node-1", is_standalone_worker=True)
            worker2 = TranslationAgentSupervisor(worker_id="worker-node-2", is_standalone_worker=True)
            try:
                # First worker acquires lease
                self.assertTrue(worker1._acquire_or_renew_room_lease(room_session.room_code))
                # Second worker attempting to lease the same active room is rejected
                self.assertFalse(worker2._acquire_or_renew_room_lease(room_session.room_code))
            finally:
                worker1._release_room_lease(room_session.room_code)
            # Once worker1 releases lease, worker2 can acquire it
            try:
                self.assertTrue(worker2._acquire_or_renew_room_lease(room_session.room_code))
            finally:
                worker2._release_room_lease(room_session.room_code)








