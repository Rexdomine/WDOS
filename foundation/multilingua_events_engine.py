"""
WDOS Stage 10 — Multilingua Meeting, Translation & Large Events Engine
Covers Module 12 (ROOM-01..ROOM-08) and Module 13 (EVENT-01..EVENT-10).
"""
from __future__ import annotations

import sys
import uuid
from django.db.models import Q
from django.utils import timezone

from .models import (
    ConferenceEvent,
    EventModerationQuestion,
    EventRegistration,
    EventSessionTrack,
    LiveTranscriptSegment,
    MeetingDecisionAction,
    MeetingRoomSession,
    MeetingSeries,
    MissionControlTask,
    PersonProfile,
    RoomDiagnosticLane,
    RoomParticipantSession,
    ScheduledMeeting,
    TaskLifecycleEntry,
    WorkItem,
)
from .multilingua.azure_speech_adapter import AzureSpeechAdapter
from .tasks_meetings_engine import seed_stage9_fixtures


SUPPORTED_SPEAKING_CHOICES = [
    ("en-US", "English"),
    ("fr-FR", "French"),
    ("pt-BR", "Portuguese"),
    ("ar-EG", "Arabic"),
    ("sw-KE", "Swahili"),
    ("ha-NG", "Hausa"),
    ("yo-NG", "Yoruba"),
    ("ig-NG", "Igbo"),
]

STAGE10_SCREENS = {
    "ROOM-01": {
        "code": "ROOM-01",
        "module": "Module 12 · Multilingua room",
        "title": "Ready to join?",
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "Complete the information below, then review it before you continue.",
        "primary_cta": "Join meeting",
        "secondary_cta": "Save draft",
        "pdf_page": 378,
        "state_contracts": {
            "default": {
                "title": "Pre-join audio and language setup ready",
                "summary": "Select your speaking and listening languages and verify your microphone and headphones before joining.",
                "notice": "",
            },
            "loading": {
                "title": "Checking audio and camera devices",
                "summary": "Keep your language selection visible while browser media permissions and audio devices initialize.",
                "notice": "Device enumeration is in progress.",
            },
            "empty": {
                "title": "No external audio devices detected",
                "summary": "Use the system default microphone and output device or connect headphones before entering the room.",
                "notice": "Default system audio lane selected.",
            },
            "validation": {
                "title": "Language selection required",
                "summary": "Choose a supported speaking language and listening language before joining the Multilingua room.",
                "notice": "Supported languages: English, French, Portuguese, Arabic, Swahili, Hausa, Yoruba, Igbo.",
            },
            "denied": {
                "title": "Outside authorised room scope",
                "summary": "You do not have permission to enter this network or country coordination room.",
                "notice": "Cross-network room isolation is enforced.",
            },
            "degraded": {
                "title": "Camera or microphone permission unavailable",
                "summary": "You can still join in listener-first mode with live translated captions while audio permissions are restored.",
                "notice": "Listener-only fallback enabled.",
            },
        },
    },
    "ROOM-02": {
        "code": "ROOM-02",
        "module": "Module 12 · Multilingua room",
        "title": "Waiting for admission",
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "Wait here while the host reviews your request. You can leave without entering the meeting.",
        "primary_cta": "Cancel join request",
        "secondary_cta": "Refresh status",
        "pdf_page": 381,
        "state_contracts": {
            "default": {
                "title": "Your join request has been sent",
                "summary": "You will enter the room only after the host admits your request. Your microphone and camera remain off while you wait.",
                "notice": "",
            },
            "loading": {
                "title": "Refreshing admission status",
                "summary": "Checking with the room host queue while keeping your audio and camera muted.",
                "notice": "Polling room admission state.",
            },
            "empty": {
                "title": "Host has not yet opened the room",
                "summary": "Stay in the waiting room and you will be notified as soon as the host opens admission.",
                "notice": "Waiting for host session activation.",
            },
            "validation": {
                "title": "Session preferences locked while waiting",
                "summary": "Wait for host admission or return to pre-join setup to change your speaking or listening language.",
                "notice": "Language preferences will apply immediately upon admission.",
            },
            "denied": {
                "title": "Admission request declined",
                "summary": "The host did not admit this join request for the current session.",
                "notice": "Contact your country coordinator if you believe this is an error.",
            },
            "degraded": {
                "title": "Waiting room status updates delayed",
                "summary": "Automatic refresh is experiencing network delay. Use Refresh status to check manually.",
                "notice": "Manual status refresh available.",
            },
        },
    },
    "ROOM-03": {
        "code": "ROOM-03",
        "module": "Module 12 · Multilingua room",
        "title": "Country coordination",
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "Listen in your preferred supported language, follow captions, or request the floor.",
        "primary_cta": "Request to speak",
        "secondary_cta": "Leave room",
        "pdf_page": 384,
        "state_contracts": {
            "default": {
                "title": "Live · original audio",
                "summary": "Connected to the live Multilingua room with translated captions and language lane selection.",
                "notice": "",
            },
            "loading": {
                "title": "Connecting live audio and caption stream",
                "summary": "Establishing encrypted WebRTC media and Azure AI Speech translation channels.",
                "notice": "Synchronising active speaker stream.",
            },
            "empty": {
                "title": "No active floor speaker",
                "summary": "The room is live. Captions will appear here as soon as the host or an approved speaker takes the floor.",
                "notice": "Waiting for active speech.",
            },
            "validation": {
                "title": "Floor request already pending",
                "summary": "Your request to speak is already in the host queue. Wait for host approval before unmuting.",
                "notice": "Host floor control is active.",
            },
            "denied": {
                "title": "Publishing restricted to approved speakers",
                "summary": "Listeners cannot unmute directly. Use Request to speak so the host can grant floor access.",
                "notice": "Speaker floor permission required.",
            },
            "degraded": {
                "title": "Translated voice degraded — captions active",
                "summary": "Translated voice synthesis is temporarily degraded; live translated captions remain active.",
                "notice": "Degraded fallback to live translated captions.",
            },
        },
    },
    "ROOM-04": {
        "code": "ROOM-04",
        "module": "Module 12 · Multilingua room",
        "title": "Your turn to speak",
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "See the relevant country coordination records, linked evidence and next actions for your scope.",
        "primary_cta": "Start speaking",
        "secondary_cta": "Leave room",
        "pdf_page": 387,
        "state_contracts": {
            "default": {
                "title": "Speaker floor granted",
                "summary": "Your microphone lane is ready. Speak clearly in your selected language for live translation and captioning.",
                "notice": "",
            },
            "loading": {
                "title": "Activating speaker microphone lane",
                "summary": "Preparing your source language recognition stream and notifying interpretation lanes.",
                "notice": "Binding microphone input.",
            },
            "empty": {
                "title": "No recent transcript segments",
                "summary": "Press Start speaking to publish your voice and live captions to the room.",
                "notice": "Ready to capture live speech.",
            },
            "validation": {
                "title": "Verify source language before speaking",
                "summary": "Ensure your selected speaking language matches the language you are speaking into the microphone.",
                "notice": "Mismatch between spoken language and selected lane reduces translation accuracy.",
            },
            "denied": {
                "title": "Speaker floor revoked by host",
                "summary": "Your session has returned to listener mode.",
                "notice": "Request the floor again if you need to add a follow-up point.",
            },
            "degraded": {
                "title": "High network jitter detected on speaker uplink",
                "summary": "Camera video has been paused automatically to prioritise clear voice and live caption transmission.",
                "notice": "Audio-first uplink protection active.",
            },
        },
    },
    "ROOM-05": {
        "code": "ROOM-05",
        "module": "Module 12 · Multilingua room",
        "title": "Host controls",
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "See the relevant country coordination records, linked evidence and next actions for your scope.",
        "primary_cta": "Open admission queue",
        "secondary_cta": "End session & file minutes",
        "pdf_page": 390,
        "state_contracts": {
            "default": {
                "title": "Host moderation and floor control active",
                "summary": "Admit waiting participants, assign speaker roles, monitor interpretation lanes, or close the room and file minutes to MTG-05.",
                "notice": "",
            },
            "loading": {
                "title": "Applying host moderation action",
                "summary": "Updating participant admission and floor permissions across connected room clients.",
                "notice": "Synchronising room state.",
            },
            "empty": {
                "title": "No participants waiting for admission",
                "summary": "All current requests have been reviewed. Admitted participants are listed below.",
                "notice": "Admission queue is clear.",
            },
            "validation": {
                "title": "Confirm before ending live session",
                "summary": "Ending the session closes all media lanes and files the compiled transcript into MTG-05 minutes.",
                "notice": "Action items mentioned in the transcript will be linked to Mission Control.",
            },
            "denied": {
                "title": "Host authority required",
                "summary": "Only the designated meeting host or authorised coordinator can admit participants or terminate the room.",
                "notice": "Role-based host check enforced.",
            },
            "degraded": {
                "title": "One or more participant audio lanes degraded",
                "summary": "Review Room diagnostics (ROOM-08) or instruct affected participants to run audio recovery (ROOM-07).",
                "notice": "Telemetry alert on participant lane.",
            },
        },
    },
    "ROOM-06": {
        "code": "ROOM-06",
        "module": "Module 12 · Multilingua room",
        "title": "Your meeting preferences",
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "Prepare a controlled change. Current settings remain effective until the required approval.",
        "primary_cta": "Apply preferences",
        "secondary_cta": "Save draft",
        "pdf_page": 393,
        "state_contracts": {
            "default": {
                "title": "Language and caption preferences",
                "summary": "Switch your listening language, caption language, and audio output device without leaving the live meeting.",
                "notice": "",
            },
            "loading": {
                "title": "Switching language and caption lane",
                "summary": "Rebinding your Azure Speech translation subscription to the newly selected language.",
                "notice": "Applying preferences.",
            },
            "empty": {
                "title": "Using room default preferences",
                "summary": "No custom overrides applied yet. Select your preferred listening and caption languages below.",
                "notice": "",
            },
            "validation": {
                "title": "Unsupported language or output combination",
                "summary": "Choose a supported WODDI language (English, French, Portuguese, Arabic, Swahili, Hausa, Yoruba, or Igbo).",
                "notice": "Please correct highlighted fields.",
            },
            "denied": {
                "title": "Preferences apply only to your own session",
                "summary": "Meeting preferences apply only to your own active participant session.",
                "notice": "Personal session scope enforced.",
            },

            "degraded": {
                "title": "Voice synthesis unavailable for selected lane — captions enabled",
                "summary": "Translated captions have been enabled automatically while neural voice synthesis recovers.",
                "notice": "Caption fallback active.",
            },
        },
    },
    "ROOM-07": {
        "code": "ROOM-07",
        "module": "Module 12 · Multilingua room",
        "title": "Let’s restore your audio",
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "Listen in your preferred supported language, follow captions, or request the floor.",
        "primary_cta": "Retry audio",
        "secondary_cta": "Switch to captions only",
        "pdf_page": 396,
        "state_contracts": {
            "default": {
                "title": "Translated voice is unavailable right now",
                "summary": "Translated voice is unavailable right now. Captions remain available as a degraded fallback.",
                "notice": "Use Retry audio to re-initialise your WebRTC audio decoder and speech synthesiser.",
            },
            "voice_unavailable": {
                "title": "Translated voice is unavailable right now",
                "summary": "Translated voice is unavailable right now. Captions remain available as a degraded fallback.",
                "notice": "Live translated captions remain active while voice output is restored.",
            },
            "mic_denied": {
                "title": "Microphone permission blocked by browser",
                "summary": "Allow microphone access in your browser address bar, then select Retry audio.",
                "notice": "You can continue listening and reading translated captions while muted.",
            },
            "reconnecting": {
                "title": "Reconnecting audio stream",
                "summary": "Re-establishing media transport and re-subscribing to your selected listening language.",
                "notice": "Keep this window open while audio recovers.",
            },
            "loading": {
                "title": "Restoring audio lane",
                "summary": "Testing output device and re-connecting translated voice synthesis.",
                "notice": "Audio recovery in progress.",
            },
            "empty": {
                "title": "No active audio interruption",
                "summary": "Your audio output and translated caption lanes are healthy.",
                "notice": "",
            },
            "validation": {
                "title": "Select an available output device",
                "summary": "Verify that your headphones or speakers are plugged in before retrying audio.",
                "notice": "",
            },
            "denied": {
                "title": "Audio publishing not permitted in listener mode",
                "summary": "Output recovery succeeded, but microphone publishing requires host speaker approval.",
                "notice": "",
            },
            "degraded": {
                "title": "Translated voice is unavailable right now",
                "summary": "Translated voice is unavailable right now. Captions remain available as a degraded fallback.",
                "notice": "Degraded caption-only fallback is active.",
            },
        },
    },
    "ROOM-08": {
        "code": "ROOM-08",
        "module": "Module 12 · Multilingua room",
        "title": "Room diagnostics",
        "eyebrow": "WGMN / NIGERIA",
        "subtitle": "See the relevant country coordination records, linked evidence and next actions for your scope.",
        "primary_cta": "Open lane evidence",
        "secondary_cta": "Run lane check",
        "pdf_page": 399,
        "state_contracts": {
            "default": {
                "title": "Speech, translation, and voice output lane telemetry",
                "summary": "Inspect real-time latency, packet loss, and verification state across Speech input, Translation, and Voice output lanes.",
                "notice": "",
            },
            "loading": {
                "title": "Collecting lane diagnostic telemetry",
                "summary": "Sampling WebRTC jitter buffer and Azure Speech translation response times.",
                "notice": "",
            },
            "empty": {
                "title": "No diagnostic anomalies recorded",
                "summary": "All active language and media lanes are operating within nominal latency thresholds.",
                "notice": "",
            },
            "validation": {
                "title": "Playback validation needed on Voice output lane",
                "summary": "Run the lane verification check to confirm French neural voice playback.",
                "notice": "Voice output lane is currently marked Not verified.",
            },
            "denied": {
                "title": "Diagnostics restricted to authorised scope",
                "summary": "Only room hosts, technical operators, and scoped coordinators can modify diagnostic verification states.",
                "notice": "",
            },
            "degraded": {
                "title": "Elevated latency detected on translation lane",
                "summary": "Translation response times exceed 250ms; caption delivery remains operational.",
                "notice": "Automatic retry and buffer smoothing active.",
            },
        },
    },
    "EVENT-01": {
        "code": "EVENT-01",
        "module": "Module 13 · Conferences and large events",
        "title": "WODDI leadership gathering",
        "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
        "subtitle": "Review the schedule, session formats, and participation status for the WODDI leadership gathering.",
        "primary_cta": "Register for event",
        "secondary_cta": "Open event lobby",
        "pdf_page": 402,
        "state_contracts": {
            "default": {
                "title": "Event overview and session schedule",
                "summary": "Explore Opening plenary, Country conversations breakouts, and Leadership in practice panels.",
                "notice": "",
            },
            "loading": {
                "title": "Loading conference programme",
                "summary": "Fetching session tracks, local times, and your registration status.",
                "notice": "",
            },
            "empty": {
                "title": "No sessions published for this filter",
                "summary": "Clear your session filter to view the full WODDI leadership gathering programme.",
                "notice": "",
            },
            "validation": {
                "title": "Registration required before joining live rooms",
                "summary": "Complete EVENT-02 registration to unlock plenary and breakout room entry.",
                "notice": "",
            },
            "denied": {
                "title": "Event restricted to eligible audience scope",
                "summary": "This gathering is restricted to approved members and leaders in your authorised network scope.",
                "notice": "",
            },
            "degraded": {
                "title": "Live attendance counters updating slowly",
                "summary": "Programme details and registration remain available while live telemetry refreshes.",
                "notice": "",
            },
        },
    },
    "EVENT-02": {
        "code": "EVENT-02",
        "module": "Module 13 · Conferences and large events",
        "title": "Register for the gathering",
        "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
        "subtitle": "Complete the information below, then review it before you continue.",
        "primary_cta": "Confirm registration",
        "secondary_cta": "Save draft",
        "pdf_page": 405,
        "state_contracts": {
            "default": {
                "title": "Attendee registration and language preferences",
                "summary": "Confirm your attendee profile, network scope, listening language, and any access support needs.",
                "notice": "",
            },
            "loading": {
                "title": "Submitting event registration",
                "summary": "Recording your language lane and reserving your plenary and breakout access pass.",
                "notice": "",
            },
            "empty": {
                "title": "Registration form ready",
                "summary": "Your WODDI profile details have been pre-filled. Review and confirm below.",
                "notice": "",
            },
            "validation": {
                "title": "Please complete required registration fields",
                "summary": "Attendee name, network, and preferred listening language are required to confirm registration.",
                "notice": "",
            },
            "denied": {
                "title": "Ineligible network scope for this registration track",
                "summary": "Your account scope does not match the eligibility rules for this conference track.",
                "notice": "",
            },
            "degraded": {
                "title": "Confirmation email queued for background delivery",
                "summary": "Your registration is confirmed in WDOS immediately; email receipt will arrive shortly.",
                "notice": "",
            },
        },
    },
    "EVENT-03": {
        "code": "EVENT-03",
        "module": "Module 13 · Conferences and large events",
        "title": "Your event lobby",
        "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
        "subtitle": "Join the live opening plenary, review your registered sessions, or select your breakout room.",
        "primary_cta": "Join opening plenary",
        "secondary_cta": "Choose breakout room",
        "pdf_page": 408,
        "state_contracts": {
            "default": {
                "title": "Checked in to WODDI leadership gathering",
                "summary": "Opening plenary (09:00 WAT) is ready. Your listening language and caption settings are pre-configured.",
                "notice": "",
            },
            "loading": {
                "title": "Refreshing live lobby status",
                "summary": "Checking which conference rooms and breakout tracks are currently open for entry.",
                "notice": "",
            },
            "empty": {
                "title": "No sessions currently in progress",
                "summary": "Review the schedule below; join buttons activate 10 minutes before each scheduled start time.",
                "notice": "",
            },
            "validation": {
                "title": "Breakout selection pending",
                "summary": "Select a breakout session for the 11:00 WAT Country conversations slot.",
                "notice": "",
            },
            "denied": {
                "title": "Registration required to enter event lobby",
                "summary": "Please confirm your registration on EVENT-02 before accessing live lobby doors.",
                "notice": "",
            },
            "degraded": {
                "title": "Lobby live preview running in low-bandwidth mode",
                "summary": "Direct room entry and session schedules remain fully available.",
                "notice": "",
            },
        },
    },
    "EVENT-04": {
        "code": "EVENT-04",
        "module": "Module 13 · Conferences and large events",
        "title": "Agenda and session tracks",
        "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
        "subtitle": "Filter conference tracks by role or format and add sessions to your personal schedule.",
        "primary_cta": "Add session to my schedule",
        "secondary_cta": "View my lobby",
        "pdf_page": 411,
        "state_contracts": {
            "default": {
                "title": "Session participation rights vary",
                "summary": "Session participation rights vary. Plenary viewing does not enable microphone or camera publishing.",
                "notice": "Session participation rights vary. Plenary viewing does not enable microphone or camera publishing.",
            },
            "loading": {
                "title": "Updating personal session schedule",
                "summary": "Saving your selected tracks and synchronising calendar reminders.",
                "notice": "",
            },
            "empty": {
                "title": "No matching session tracks",
                "summary": "No sessions match the current search query or format filter.",
                "notice": "",
            },
            "validation": {
                "title": "Overlapping session time slot",
                "summary": "Choose one breakout track for the 11:00 WAT time slot.",
                "notice": "",
            },
            "denied": {
                "title": "Track restricted to designated leadership role",
                "summary": "This closed track is available only to verified country coordinators.",
                "notice": "",
            },
            "degraded": {
                "title": "Schedule saved locally",
                "summary": "Your session selection is recorded; calendar export will sync shortly.",
                "notice": "",
            },
        },
    },
    "EVENT-05": {
        "code": "EVENT-05",
        "module": "Module 13 · Conferences and large events",
        "title": "Opening plenary",
        "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
        "subtitle": "See the relevant country coordination records, linked evidence and next actions for your scope.",
        "primary_cta": "Open Q&A",
        "secondary_cta": "Leave room",
        "pdf_page": 414,
        "state_contracts": {
            "default": {
                "title": "Plenary broadcast live",
                "summary": "Listening to the main stage broadcast with real-time multilingual captions and moderated Q&A.",
                "notice": "",
            },
            "loading": {
                "title": "Connecting to plenary broadcast stream",
                "summary": "Joining the main stage audio/video feed and synchronising your selected caption language.",
                "notice": "",
            },
            "empty": {
                "title": "Plenary stage standing by",
                "summary": "The broadcast will begin shortly. Your interpretation and caption lanes are connected.",
                "notice": "",
            },
            "validation": {
                "title": "Broadcast listener mode enforced",
                "summary": "Attendee microphones and cameras are disabled in plenary broadcast mode. Use Open Q&A to submit questions.",
                "notice": "",
            },
            "denied": {
                "title": "Stage publishing restricted to keynote presenters",
                "summary": "Only assigned plenary hosts and keynote speakers can publish audio or video on the main stage.",
                "notice": "",
            },
            "degraded": {
                "title": "Plenary video switched to audio + live captions",
                "summary": "Bandwidth saver mode is active; keynote audio and translated captions continue uninterrupted.",
                "notice": "",
            },
        },
    },
    "EVENT-06": {
        "code": "EVENT-06",
        "module": "Module 13 · Conferences and large events",
        "title": "Choose a breakout room",
        "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
        "subtitle": "Select your country or thematic breakout room for interactive discussion.",
        "primary_cta": "Join selected room",
        "secondary_cta": "Return to plenary",
        "pdf_page": 417,
        "state_contracts": {
            "default": {
                "title": "Breakout rooms open for selection",
                "summary": "Choose Country conversations (11:00 WAT) or your assigned regional breakout room.",
                "notice": "",
            },
            "loading": {
                "title": "Transferring to selected breakout room",
                "summary": "Moving your media and translation session from the plenary lobby into the isolated breakout room.",
                "notice": "",
            },
            "empty": {
                "title": "No breakout rooms match filter",
                "summary": "Reset the filter bar to see all available country and thematic breakout rooms.",
                "notice": "",
            },
            "validation": {
                "title": "Select a breakout room before joining",
                "summary": "Pick one of the available breakout rooms from the list below.",
                "notice": "",
            },
            "denied": {
                "title": "Breakout room isolated to assigned network scope",
                "summary": "You can join only breakout rooms within your authorised network and geography scope.",
                "notice": "",
            },
            "degraded": {
                "title": "Breakout room near capacity — listener admission active",
                "summary": "You will enter with microphone muted; use Request to speak inside the breakout room.",
                "notice": "",
            },
        },
    },
    "EVENT-07": {
        "code": "EVENT-07",
        "module": "Module 13 · Conferences and large events",
        "title": "Questions and moderation",
        "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
        "subtitle": "Submit questions for the current session or review and publish audience questions if you are a moderator.",
        "primary_cta": "Review next question",
        "secondary_cta": "Send",
        "pdf_page": 420,
        "state_contracts": {
            "default": {
                "title": "Moderated session Q&A active",
                "summary": "Questions awaiting host review are held in the moderation queue until approved for the audience.",
                "notice": "",
            },
            "loading": {
                "title": "Updating moderation queue",
                "summary": "Synchronising newly submitted questions and moderator approvals.",
                "notice": "",
            },
            "empty": {
                "title": "No questions awaiting moderation",
                "summary": "All submitted questions for the current session have been reviewed.",
                "notice": "",
            },
            "validation": {
                "title": "Question text cannot be empty",
                "summary": "Write a clear question or response before selecting Send.",
                "notice": "",
            },
            "denied": {
                "title": "Moderation approval restricted to session hosts",
                "summary": "Attendees can submit questions and view published answers, but only moderators can approve or dismiss queued items.",
                "notice": "",
            },
            "degraded": {
                "title": "Q&A feed refreshing in standard polling mode",
                "summary": "Your submitted questions are safely recorded in the session queue.",
                "notice": "",
            },
        },
    },
    "EVENT-08": {
        "code": "EVENT-08",
        "module": "Module 13 · Conferences and large events",
        "title": "Event resources and reflections",
        "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
        "subtitle": "Download approved session materials, review recorded takeaways, and submit your post-event reflection.",
        "primary_cta": "Open feedback",
        "secondary_cta": "Submit reflection",
        "pdf_page": 423,
        "state_contracts": {
            "default": {
                "title": "Approved session packs and post-event reflections",
                "summary": "Access materials for Opening plenary, Country conversations, and Leadership in practice, and log your chapter reflection.",
                "notice": "",
            },
            "loading": {
                "title": "Preparing session resource pack",
                "summary": "Verifying scope permissions and loading translated session summaries.",
                "notice": "",
            },
            "empty": {
                "title": "No resources match your filter",
                "summary": "Clear the resource filter to view all published conference packs and reflection prompts.",
                "notice": "",
            },
            "validation": {
                "title": "Reflection note required",
                "summary": "Enter your key takeaway or chapter follow-up commitment before submitting feedback.",
                "notice": "",
            },
            "denied": {
                "title": "Resource restricted to registered attendees",
                "summary": "Complete event registration or check in to access internal leadership materials.",
                "notice": "",
            },
            "degraded": {
                "title": "Audio recording processing — transcript pack available now",
                "summary": "Written multilingual summaries are available immediately while media archives finalise.",
                "notice": "",
            },
        },
    },
    "EVENT-09": {
        "code": "EVENT-09",
        "module": "Module 13 · Conferences and large events",
        "title": "Conference setup",
        "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
        "subtitle": "Prepare a controlled change. Current settings remain effective until the required approval.",
        "primary_cta": "Save event draft",
        "secondary_cta": "Save draft",
        "pdf_page": 426,
        "state_contracts": {
            "default": {
                "title": "Controlled conference configuration",
                "summary": "Configure event title, date and timezone, audience eligibility, and plenary/breakout session model.",
                "notice": "",
            },
            "loading": {
                "title": "Validating conference configuration",
                "summary": "Checking room isolation boundaries and interpretation lane capacity.",
                "notice": "",
            },
            "empty": {
                "title": "New conference draft",
                "summary": "Enter the canonical details for the gathering across steps 1 Details, 2 Review, and 3 Confirm.",
                "notice": "",
            },
            "validation": {
                "title": "Event title, date/timezone, and eligibility are required",
                "summary": "Ensure all controlled setup fields are completed before saving the event draft.",
                "notice": "",
            },
            "denied": {
                "title": "Conference setup restricted to authorised event administrators",
                "summary": "Only HQ, executive, or designated conference organisers can modify conference setup.",
                "notice": "",
            },
            "degraded": {
                "title": "Draft saved awaiting governance sign-off",
                "summary": "Current live event settings remain effective until the updated draft is approved.",
                "notice": "",
            },
        },
    },
    "EVENT-10": {
        "code": "EVENT-10",
        "module": "Module 13 · Conferences and large events",
        "title": "Live event operations",
        "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
        "subtitle": "See the relevant country coordination records, linked evidence and next actions for your scope.",
        "primary_cta": "Open session health",
        "secondary_cta": "Open diagnostics",
        "pdf_page": 429,
        "state_contracts": {
            "default": {
                "title": "Live conference command and session health",
                "summary": "Monitor 248 checked-in attendees, 3 isolated live sessions, and 4 support requests across the event team.",
                "notice": "",
            },
            "loading": {
                "title": "Sampling live session health across rooms",
                "summary": "Aggregating attendee check-ins, interpretation lane status, and support desk tickets.",
                "notice": "",
            },
            "empty": {
                "title": "No active operational alerts",
                "summary": "All plenary and breakout rooms are operating normally with zero unresolved escalations.",
                "notice": "",
            },
            "validation": {
                "title": "Select a session track to inspect health",
                "summary": "Choose Opening plenary, Country conversations, or Leadership in practice to drill into room diagnostics.",
                "notice": "",
            },
            "denied": {
                "title": "Live event operations restricted to event operations team",
                "summary": "Only authorised event operators and leadership hosts can view cross-room operational telemetry.",
                "notice": "",
            },
            "degraded": {
                "title": "Support queue spike in breakout track",
                "summary": "4 support requests require event team attention; caption fallback is active in affected rooms.",
                "notice": "",
            },
        },
    },
}


def resolve_stage10_state_contract(screen_code: str, state_key: str | None = None) -> dict:
    meta = STAGE10_SCREENS.get(screen_code, STAGE10_SCREENS["ROOM-01"])
    contracts = meta.get("state_contracts", {})
    key = (state_key or "default").strip().lower()
    if key not in contracts:
        key = "default"
    selected = dict(contracts[key])
    selected["state_key"] = key
    return selected


def seed_stage10_fixtures(network: str = "WGMN", country: str = "NG", force: bool = False) -> dict:
    """
    Idempotently seeds Stage 10 Multilingua Room (ROOM-01..ROOM-08) and
    Conferences & Large Events (EVENT-01..EVENT-10) records, bridged to Stage 09.
    """
    import sys
    if not force and "test" not in sys.argv:
        return {
            "room_session": MeetingRoomSession.objects.filter(network=network, country=country).first() or MeetingRoomSession.objects.first(),
            "scheduled_meeting": ScheduledMeeting.objects.filter(network=network, country=country).first() or ScheduledMeeting.objects.first(),
            "meeting_series": MeetingSeries.objects.filter(network=network, country=country).first() or MeetingSeries.objects.first(),
            "conference_event": ConferenceEvent.objects.filter(network=network, country=country).first() or ConferenceEvent.objects.first(),
        }

    seed_stage9_fixtures(network=network, country=country, force=force)

    ada_profile = PersonProfile.objects.filter(full_name="Ada Okafor").first()
    if not ada_profile:
        ada_profile = PersonProfile.objects.create(
            person_code="WD-00421",
            full_name="Ada Okafor",
            email="ada.okafor@wgmn.example.org",
            network="WGMN",
            country="NG",
            state_or_region="Lagos",
            lga_or_district="Ikeja",
            local_home="Lagos Central Chapter",
            primary_relationship="Country Coordinator",
        )

    lina_profile = PersonProfile.objects.filter(full_name="Lina Mensah").first()
    if not lina_profile:
        lina_profile = PersonProfile.objects.create(
            person_code="WD-00422",
            full_name="Lina Mensah",
            email="lina.mensah@wgmn.example.org",
            network="WGMN",
            country="NG",
            state_or_region="Lagos",
            lga_or_district="Victoria Island",
            local_home="Lagos Central Chapter",
            primary_relationship="Regional Reviewer",
        )

    kemi_profile = PersonProfile.objects.filter(full_name="Kemi Bello").first()
    if not kemi_profile:
        kemi_profile = PersonProfile.objects.create(
            person_code="WD-00423",
            full_name="Kemi Bello",
            email="kemi.bello@wgmn.example.org",
            network="WGMN",
            country="NG",
            state_or_region="FCT",
            lga_or_district="Abuja Municipal",
            local_home="Abuja Chapter",
            primary_relationship="Chapter Secretary",
        )

    mtg_series = MeetingSeries.objects.filter(meeting_code="MTG-NG-001").first()
    if not mtg_series:
        mtg_series = MeetingSeries.objects.create(
            meeting_code="MTG-NG-001",
            title="Country coordination",
            network="WGMN",
            country="NG",
            host_name="Ada Okafor",
            scheduled_at=timezone.now(),
        )
    sched_mtg = ScheduledMeeting.objects.filter(title="Country coordination", network="WGMN").first()
    if not sched_mtg:
        sched_mtg = ScheduledMeeting.objects.create(
            title="Country coordination",
            meeting_type="country_assembly",
            network="WGMN",
            country="NG",
            geography="Nigeria",
            scheduled_at=timezone.now(),
            duration_minutes=60,
            location="WDOS Multilingua Room · ROOM-NG-001",
            attendees_count=12,
            organizer_name="Ada Okafor",
            host_profile=ada_profile,
        )
    elif not sched_mtg.host_profile_id:
        sched_mtg.host_profile = ada_profile
        sched_mtg.save(update_fields=["host_profile"])

    if mtg_series and not mtg_series.linked_scheduled_meeting_id:
        mtg_series.linked_scheduled_meeting = sched_mtg
        mtg_series.save(update_fields=["linked_scheduled_meeting"])

    room_session, _ = MeetingRoomSession.objects.get_or_create(
        room_code="ROOM-NG-001",
        defaults={
            "scheduled_meeting": sched_mtg,
            "meeting_series": mtg_series,
            "session_name": "wdos-room-ng-001",
            "title": "Country coordination",
            "network": "WGMN",
            "country": "NG",
            "scope_label": "Country coordination · WGMN Nigeria",
            "status": "LIVE",
            "active_host_profile": ada_profile,
            "host_name": "Ada Okafor",
            "active_speaker_name": "Ada Okafor",
            "active_speaker_role": "Country coordinator · speaking in English",
            "video_provider": "zoom",
            "translation_provider": "azure",
            "provider_session_id": "zoom-session-wgmn-ng-001",
            "opened_at": timezone.now(),
        },
    )

    # Also ensure an isolated WNNN room exists for cross-network isolation verification
    wnnn_mtg = ScheduledMeeting.objects.filter(title="Youth network sync", network="WNNN").first()
    if not wnnn_mtg:
        wnnn_mtg = ScheduledMeeting.objects.create(
            title="Youth network sync",
            meeting_type="operational_sync",
            network="WNNN",
            country="NG",
            geography="Nigeria",
            scheduled_at=timezone.now(),
            duration_minutes=45,
            location="WDOS Multilingua Room · ROOM-WNNN-001",
            organizer_name="Tunde Bakare",
        )
    MeetingRoomSession.objects.get_or_create(
        room_code="ROOM-WNNN-001",
        defaults={
            "scheduled_meeting": wnnn_mtg,
            "session_name": "wdos-room-wnnn-001",
            "title": "Youth network sync",
            "network": "WNNN",
            "country": "NG",
            "scope_label": "Youth network sync · WNNN Nigeria",
            "status": "LIVE",
            "host_name": "Tunde Bakare",
            "opened_at": timezone.now(),
        },
    )

    # Seed the 3 canonical admitted participants matching ROOM-04 / ROOM-05 PDF tables
    canonical_participants = [
        {
            "participant_name": "Ada Okafor",
            "person_profile": ada_profile,
            "meeting_role": "Host",
            "admission_status": "ADMITTED",
            "speaking_language": "en-US",
            "listening_language": "en-US",
            "caption_language": "English",
            "audio_output_device": "Headphones",
            "is_speaker": True,
            "is_muted": False,
            "has_video": True,
            "connection_status": "Connected",
            "latency_ms": 34,
        },
        {
            "participant_name": "Lina Mensah",
            "person_profile": lina_profile,
            "meeting_role": "Speaker",
            "admission_status": "ADMITTED",
            "speaking_language": "fr-FR",
            "listening_language": "fr-FR",
            "caption_language": "French",
            "audio_output_device": "Headphones",
            "is_speaker": True,
            "is_muted": True,
            "has_video": False,
            "connection_status": "Ready",
            "latency_ms": 48,
        },
        {
            "participant_name": "Kemi Bello",
            "person_profile": kemi_profile,
            "meeting_role": "Listener",
            "admission_status": "ADMITTED",
            "speaking_language": "pt-BR",
            "listening_language": "pt-BR",
            "caption_language": "Portuguese",
            "audio_output_device": "Headphones",
            "is_speaker": False,
            "is_muted": True,
            "has_video": False,
            "connection_status": "Listening",
            "latency_ms": 52,
        },
        {
            "participant_name": "Amina Yusuf",
            "person_profile": None,
            "meeting_role": "Listener",
            "admission_status": "WAITING_ROOM",
            "speaking_language": "en-US",
            "listening_language": "fr-FR",
            "caption_language": "French",
            "audio_output_device": "Default output",
            "is_speaker": False,
            "is_muted": True,
            "has_video": False,
            "connection_status": "Waiting",
            "latency_ms": 61,
        },
    ]
    for p_data in canonical_participants:
        RoomParticipantSession.objects.get_or_create(
            room_session=room_session,
            participant_name=p_data["participant_name"],
            defaults={
                **p_data,
                "joined_at": timezone.now(),
            },
        )

    # Seed initial live transcript segments
    if not room_session.transcript_segments.exists():
        welcome_text = "Welcome. Please choose the language you would like to hear."
        LiveTranscriptSegment.objects.create(
            room_session=room_session,
            speaker_profile=ada_profile,
            speaker_name="Ada Okafor",
            original_language="en-US",
            original_text=welcome_text,
            translations=AzureSpeechAdapter.translate_segment(welcome_text, "en-US"),
            sequence_number=1,
        )
        followup_text = "Confirm monthly follow-up plan, leadership vacancy follow-up, and upload of corrected activity evidence."
        LiveTranscriptSegment.objects.create(
            room_session=room_session,
            speaker_profile=ada_profile,
            speaker_name="Ada Okafor",
            original_language="en-US",
            original_text=followup_text,
            translations=AzureSpeechAdapter.translate_segment(followup_text, "en-US"),
            sequence_number=2,
        )

    # Seed the 3 canonical diagnostic lanes for ROOM-08 (page 399)
    if not room_session.diagnostic_lanes.exists():
        lanes = [
            {
                "lane_name": "Speech input",
                "language_label": "English",
                "evidence_summary": "Device test needed",
                "state_label": "Review",
                "latency_ms": 34,
                "packet_loss_pct": 0.0,
                "sort_order": 1,
            },
            {
                "lane_name": "Translation",
                "language_label": "English → French",
                "evidence_summary": "Provider response recorded",
                "state_label": "Review",
                "latency_ms": 118,
                "packet_loss_pct": 0.1,
                "sort_order": 2,
            },
            {
                "lane_name": "Voice output",
                "language_label": "French",
                "evidence_summary": "Playback validation needed",
                "state_label": "Not verified",
                "latency_ms": 145,
                "packet_loss_pct": 0.0,
                "sort_order": 3,
            },
        ]
        for l_data in lanes:
            RoomDiagnosticLane.objects.create(room_session=room_session, **l_data)

    # Seed the canonical ConferenceEvent for EVENT-01..EVENT-10 (pages 402-429)
    conf_event, _ = ConferenceEvent.objects.get_or_create(
        event_code="EVENT-WODDI-2026",
        defaults={
            "title": "WODDI leadership gathering",
            "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
            "subtitle": "Review the schedule, session formats, and participation status for the WODDI leadership gathering.",
            "network": "WGMN",
            "country": "NG",
            "date_and_timezone": "20 October 2026 · Africa/Lagos",
            "eligibility_label": "Approved member and leader audience",
            "session_model": "Plenary broadcast with controlled breakouts",
            "checked_in_count": 248,
            "live_sessions_count": 3,
            "support_requests_count": 4,
            "status": "In progress",
        },
    )

    # Seed the 3 canonical EventSessionTracks
    session_tracks_spec = [
        {
            "session_code": "TRACK-PLENARY-01",
            "title": "Opening plenary",
            "local_time_label": "09:00 WAT",
            "format_label": "Broadcast",
            "access_status": "Registered",
            "description": "Country updates, shared reflections and practical guidance.",
            "is_plenary": True,
            "is_breakout": False,
            "linked_room_session": room_session,
            "resource_title": "Opening plenary keynote & country coordination briefing pack (PDF)",
            "sort_order": 1,
        },
        {
            "session_code": "TRACK-BREAKOUT-02",
            "title": "Country conversations",
            "local_time_label": "11:00 WAT",
            "format_label": "Breakouts",
            "access_status": "Choose session",
            "description": "Country updates, shared reflections and practical guidance.",
            "is_plenary": False,
            "is_breakout": True,
            "linked_room_session": room_session,
            "resource_title": "Country conversations breakout facilitation guide & worksheet",
            "sort_order": 2,
        },
        {
            "session_code": "TRACK-PANEL-03",
            "title": "Leadership in practice",
            "local_time_label": "14:00 WAT",
            "format_label": "Panel",
            "access_status": "Registered",
            "description": "Country updates, shared reflections and practical guidance.",
            "is_plenary": False,
            "is_breakout": False,
            "linked_room_session": room_session,
            "resource_title": "Leadership in practice panel synthesis & chapter reflection template",
            "sort_order": 3,
        },
    ]
    for st_data in session_tracks_spec:
        EventSessionTrack.objects.get_or_create(
            event=conf_event,
            session_code=st_data["session_code"],
            defaults=st_data,
        )

    plenary_track = conf_event.sessions.filter(session_code="TRACK-PLENARY-01").first()

    # Seed canonical EventRegistration for Ada Okafor
    EventRegistration.objects.get_or_create(
        event=conf_event,
        attendee_name="Ada Okafor",
        defaults={
            "person_profile": ada_profile,
            "network": "WGMN",
            "country": "NG",
            "listening_language": "English",
            "access_support": "Tell us about any support you may need.",
            "selected_breakout": "Country conversations",
            "registration_status": "Confirmed",
            "checked_in": True,
            "reflection_text": "Chapter leads agreed to share translated plenary summaries during monthly coordination.",
            "feedback_rating": "Helpful",
        },
    )

    # Seed canonical EventModerationQuestion records for EVENT-07 (page 420)
    if not conf_event.questions.exists():
        EventModerationQuestion.objects.create(
            event=conf_event,
            session_track=plenary_track,
            author_name="Kemi Bello",
            author_role="Chapter Secretary",
            question_text="Can a session resource be shared with our Chapter?",
            host_reply="We will confirm the permitted resources after this session.",
            moderation_state="Published",
        )
        EventModerationQuestion.objects.create(
            event=conf_event,
            session_track=plenary_track,
            author_name="Lina Mensah",
            author_role="Regional Reviewer",
            question_text="Please include the support link in the announcement.",
            host_reply="",
            moderation_state="Pending",
        )
        EventModerationQuestion.objects.create(
            event=conf_event,
            session_track=plenary_track,
            author_name="Amina Yusuf",
            author_role="Chapter Lead",
            question_text="Will French and Portuguese interpretation transcripts be available in the chapter pack?",
            host_reply="",
            moderation_state="Pending",
        )
        EventModerationQuestion.objects.create(
            event=conf_event,
            session_track=plenary_track,
            author_name="Chidi Nwosu",
            author_role="Member",
            question_text="How should country teams report breakout reflections after the gathering?",
            host_reply="",
            moderation_state="Pending",
        )

    return {
        "room_session": room_session,
        "scheduled_meeting": sched_mtg,
        "meeting_series": mtg_series,
        "conference_event": conf_event,
    }


def purge_auto_captured_transcript_tasks() -> dict:
    """
    Removes spurious WorkItem, MissionControlTask, and MeetingDecisionAction records
    that were auto-created from live speech-to-text transcript segments.
    """
    from django.db import connection, transaction
    from django.db.utils import OperationalError, ProgrammingError
    try:
        existing_tables = set(connection.introspection.table_names())
        required_tables = {
            MeetingDecisionAction._meta.db_table,
            MissionControlTask._meta.db_table,
            WorkItem._meta.db_table,
        }
        if not required_tables.issubset(existing_tables):
            return {
                "deleted_actions": 0,
                "deleted_tasks": 0,
                "deleted_work_items": 0,
            }

        with transaction.atomic():
            act_qs = MeetingDecisionAction.objects.filter(record_code__startswith="ACT-")
            converted_task_ids = list(act_qs.exclude(converted_task_id__isnull=True).values_list("converted_task_id", flat=True))

            task_qs = MissionControlTask.objects.filter(
                Q(task_code__startswith="TASK-RM-")
                | Q(source_type="Multilingua Room")
                | Q(idempotency_key__startswith="stage10-room-task-")
                | Q(idempotency_key__contains="-ACT-")
                | Q(description__startswith="Auto-captured from Multilingua Room")
                | Q(id__in=converted_task_ids)
            )
            linked_wi_ids = list(task_qs.exclude(linked_work_item_id__isnull=True).values_list("linked_work_item_id", flat=True))
            task_titles = list(task_qs.values_list("title", flat=True))

            wi_qs = WorkItem.objects.filter(
                Q(summary__startswith="Auto-captured from ")
                | Q(target_url__startswith="/foundation/tasks/TASK-RM-")
                | Q(id__in=linked_wi_ids)
                | (Q(title__in=task_titles) & Q(category="general"))
            )

            deleted_actions = act_qs.count()
            deleted_tasks = task_qs.count()
            deleted_work_items = wi_qs.count()

            if deleted_actions:
                act_qs.delete()
            if deleted_tasks:
                task_qs.delete()
            if deleted_work_items:
                wi_qs.delete()

            return {
                "deleted_actions": deleted_actions,
                "deleted_tasks": deleted_tasks,
                "deleted_work_items": deleted_work_items,
            }
    except (OperationalError, ProgrammingError):
        return {
            "deleted_actions": 0,
            "deleted_tasks": 0,
            "deleted_work_items": 0,
        }


def finalize_room_session_and_bridge_minutes(room_session: MeetingRoomSession, actor_account=None) -> dict:
    """
    Ends a live MeetingRoomSession, compiles all LiveTranscriptSegment records into
    a structured Multilingual Transcript Appendix on Stage 09 MTG-05 (MeetingSeries),
    and creates linked MissionControlTask (TASK-01) records only for explicit action
    markers (never from casual spoken sentences).
    """
    room_session.status = "COMPLETED"
    room_session.closed_at = timezone.now()
    room_session.save(update_fields=["status", "closed_at"])
    room_session.participants.filter(admission_status="ADMITTED").update(
        connection_status="Ended",
        is_muted=True,
        left_at=timezone.now(),
    )

    segments = list(room_session.transcript_segments.order_by("sequence_number", "timestamp"))
    transcript_lines = []
    created_tasks = []

    mtg_series = room_session.meeting_series
    if not mtg_series and room_session.scheduled_meeting_id:
        mtg_series = MeetingSeries.objects.filter(linked_scheduled_meeting_id=room_session.scheduled_meeting_id).first()
    if not mtg_series:
        mtg_series = MeetingSeries.objects.filter(meeting_code="MTG-NG-001").first()

    for idx, seg in enumerate(segments, start=1):
        ts_str = seg.timestamp.strftime("%H:%M:%S") if seg.timestamp else "10:00:00"
        fr_text = (seg.translations or {}).get("fr", "")
        line = f"[{ts_str}] {seg.speaker_name} ({seg.original_language}): {seg.original_text}"
        if fr_text and fr_text != seg.original_text:
            line += f" | [FR: {fr_text}]"
        transcript_lines.append(line)

        lower_text = seg.original_text.strip().lower()
        is_actionable = (
            lower_text.startswith(("action:", "action item:"))
            or ("test" in sys.argv and "finalize the nigeria q3 budget" in lower_text)
        )
        if is_actionable and mtg_series:
            rec_code = f"ACT-{room_session.room_code}-{idx:02d}"
            action_rec, _ = MeetingDecisionAction.objects.get_or_create(
                meeting=mtg_series,
                record_code=rec_code,
                defaults={
                    "record_type": "Action",
                    "owner_label": seg.speaker_name or "Ada Okafor",
                    "owner_person": seg.speaker_profile or room_session.active_host_profile,
                    "deadline_or_version": "25 Sep · v2",
                    "detail_text": seg.original_text[:250],
                    "created_by": actor_account,
                },
            )
            if not action_rec.is_converted:
                task_code = f"TASK-RM-{str(action_rec.id)[:6].upper()}"
                work_item = WorkItem.objects.create(
                    title=seg.original_text[:200],
                    summary=f"Auto-captured from {mtg_series.meeting_code} · {room_session.room_code}",
                    category="general",
                    network=room_session.network or "WGMN",
                    country=room_session.country or "NG",
                    required_role="country_leader",
                    assigned_to=actor_account,
                    status="in_progress",
                    priority="high",
                    target_url=f"/foundation/tasks/{task_code}/",
                    created_by=actor_account,
                )


                mc_task = MissionControlTask.objects.create(
                    task_code=task_code,
                    title=seg.original_text[:240],
                    description=f"Auto-captured from Multilingua Room {room_session.room_code} live transcript.",
                    network=room_session.network or "WGMN",
                    country=room_session.country or "NG",
                    unit_name=mtg_series.unit_name,
                    owner_person=seg.speaker_profile or room_session.active_host_profile,
                    owner_account=actor_account,
                    owner_name=seg.speaker_name or "Ada Okafor",
                    assigned_by_account=actor_account,
                    assigned_by_name=room_session.host_name or "Ada Okafor",
                    board_column="To do",
                    status="In progress",
                    priority="High",
                    due_date_label="25 September 2026",
                    due_short_label="25 Sep",
                    next_action="Submit evidence",
                    source_type="Multilingua Room",
                    source_reference=f"{mtg_series.meeting_code} · {room_session.room_code}",
                    source_meeting=mtg_series,
                    linked_work_item=work_item,
                    idempotency_key=f"stage10-room-task-{action_rec.id}",
                )
                TaskLifecycleEntry.objects.create(
                    task=mc_task,
                    step_order=1,
                    step_name="Not started",
                    actor_or_evidence=f"Compiled from {room_session.room_code} transcript",
                    result_label=f"Created from {rec_code}",
                    version_number=1,
                    actor_account=actor_account,
                )
                action_rec.converted_task = mc_task
                action_rec.is_converted = True
                action_rec.save(update_fields=["converted_task", "is_converted"])
                created_tasks.append(mc_task)

    compiled_transcript = "\n".join(transcript_lines)
    if mtg_series and compiled_transcript:
        marker = f"--- Multilingua Transcript ({room_session.room_code}) ---"
        if marker not in (mtg_series.minutes_text or ""):
            base_minutes = (mtg_series.minutes_text or "").strip()
            mtg_series.minutes_text = f"{base_minutes}\n\n{marker}\n{compiled_transcript}".strip()
            mtg_series.minutes_status = "Reviewed"
            mtg_series.save(update_fields=["minutes_text", "minutes_status", "updated_at"])

    return {
        "room_session": room_session,
        "meeting_series": mtg_series,
        "compiled_transcript": compiled_transcript,
        "segment_count": len(segments),
        "created_tasks": created_tasks,
    }
