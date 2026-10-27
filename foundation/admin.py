from django.contrib import admin
from .models import (
    Role,
    CountryHub,
    LeadershipLevel,
    WorkItem,
    Notification,
    UserPreference,
    PrivacyRequest,
    Chapter,
    DashboardAlert,
    DashboardActivity,
    DashboardReport,
    ScheduledMeeting,
    Communication,
    MissionControlTask,
    VolunteerOpportunity,
    MeetingRoomSession,
    RoomParticipantSession,
    LiveTranscriptSegment,
    RoomChatMessage,
    RoomDiagnosticLane,
    ConferenceEvent,
    EventSessionTrack,
    EventRegistration,
    EventModerationQuestion,
)



@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_system", "created_at")
    search_fields = ("code", "name")


@admin.register(CountryHub)
class CountryHubAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "region", "status", "lead_name", "lead_email")
    list_filter = ("status", "region")
    search_fields = ("code", "name", "lead_name")


@admin.register(LeadershipLevel)
class LeadershipLevelAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "tier", "created_at")
    list_filter = ("tier",)
    search_fields = ("code", "name")


@admin.register(WorkItem)
class WorkItemAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "network", "country", "status", "priority", "assigned_to", "created_at")
    list_filter = ("status", "priority", "network", "category")
    search_fields = ("title", "summary")


@admin.register(Chapter)
class ChapterAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "network", "country", "region", "status")
    list_filter = ("network", "status")
    search_fields = ("name", "code")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("account", "title", "category", "network", "country", "created_at")
    list_filter = ("category", "network")
    search_fields = ("title", "message", "account__email")


@admin.register(PrivacyRequest)
class PrivacyRequestAdmin(admin.ModelAdmin):
    list_display = ("reference", "account", "request_type", "status", "created_at")
    list_filter = ("request_type", "status")
    search_fields = ("reference", "account__email")


@admin.register(ScheduledMeeting)
class ScheduledMeetingAdmin(admin.ModelAdmin):
    list_display = ("title", "meeting_type", "network", "country", "scheduled_at", "duration_minutes")
    list_filter = ("meeting_type", "network")
    search_fields = ("title", "location", "organizer_name")


@admin.register(MissionControlTask)
class MissionControlTaskAdmin(admin.ModelAdmin):
    list_display = ("task_code", "title", "network", "country", "unit_name", "board_column", "status", "priority", "due_date")
    list_filter = ("board_column", "status", "priority", "network", "country")
    search_fields = ("task_code", "title", "description", "unit_name", "owner_name")


@admin.register(VolunteerOpportunity)
class VolunteerOpportunityAdmin(admin.ModelAdmin):
    list_display = ("title", "network", "country", "unit_name", "route_type", "status", "created_at")
    list_filter = ("status", "route_type", "network", "country")
    search_fields = ("title", "description", "unit_name")


@admin.register(DashboardAlert)
class DashboardAlertAdmin(admin.ModelAdmin):
    list_display = ("title", "severity", "category", "network", "country", "is_active", "created_at")
    list_filter = ("severity", "category", "is_active", "network", "country")
    search_fields = ("title", "message")


@admin.register(DashboardActivity)
class DashboardActivityAdmin(admin.ModelAdmin):
    list_display = ("title", "activity_type", "network", "country", "actor_name", "created_at")
    list_filter = ("activity_type", "network", "country")
    search_fields = ("title", "actor_name", "details")


@admin.register(DashboardReport)
class DashboardReportAdmin(admin.ModelAdmin):
    list_display = ("title", "report_type", "network", "country", "period", "status", "author_name", "created_at")
    list_filter = ("report_type", "status", "network", "country")
    search_fields = ("title", "summary", "author_name")


@admin.register(Communication)
class CommunicationAdmin(admin.ModelAdmin):
    list_display = ("subject", "network", "country", "target_role", "priority", "sender_name", "sent_at")
    list_filter = ("network", "country", "priority", "target_role")
    search_fields = ("subject", "body", "sender_name")


@admin.register(MeetingRoomSession)
class MeetingRoomSessionAdmin(admin.ModelAdmin):
    list_display = ("room_code", "title", "network", "country", "status", "video_provider", "translation_provider", "opened_at")
    list_filter = ("status", "network", "country", "video_provider", "translation_provider")
    search_fields = ("room_code", "title", "session_name")


@admin.register(RoomParticipantSession)
class RoomParticipantSessionAdmin(admin.ModelAdmin):
    list_display = ("participant_name", "room_session", "meeting_role", "admission_status", "speaking_language", "listening_language", "connection_status")
    list_filter = ("admission_status", "meeting_role", "speaking_language", "listening_language")
    search_fields = ("participant_name",)


@admin.register(LiveTranscriptSegment)
class LiveTranscriptSegmentAdmin(admin.ModelAdmin):
    list_display = ("sequence_number", "speaker_name", "original_language", "room_session", "timestamp")
    list_filter = ("original_language",)
    search_fields = ("speaker_name", "original_text")


@admin.register(RoomChatMessage)
class RoomChatMessageAdmin(admin.ModelAdmin):
    list_display = ("sender_name", "sender_role", "room_session", "is_host_announcement", "timestamp")
    list_filter = ("sender_role", "is_host_announcement")
    search_fields = ("sender_name", "message_text")


@admin.register(RoomDiagnosticLane)
class RoomDiagnosticLaneAdmin(admin.ModelAdmin):
    list_display = ("lane_name", "language_label", "evidence_summary", "state_label", "latency_ms", "room_session")
    list_filter = ("state_label",)


@admin.register(ConferenceEvent)
class ConferenceEventAdmin(admin.ModelAdmin):
    list_display = ("event_code", "title", "network", "country", "date_and_timezone", "checked_in_count", "live_sessions_count", "support_requests_count", "status")
    list_filter = ("network", "country", "status")
    search_fields = ("event_code", "title")


@admin.register(EventSessionTrack)
class EventSessionTrackAdmin(admin.ModelAdmin):
    list_display = ("session_code", "title", "event", "local_time_label", "format_label", "access_status")
    list_filter = ("format_label", "access_status")
    search_fields = ("session_code", "title")


@admin.register(EventRegistration)
class EventRegistrationAdmin(admin.ModelAdmin):
    list_display = ("attendee_name", "event", "network", "listening_language", "selected_breakout", "registration_status", "checked_in")
    list_filter = ("network", "listening_language", "registration_status", "checked_in")
    search_fields = ("attendee_name",)


@admin.register(EventModerationQuestion)
class EventModerationQuestionAdmin(admin.ModelAdmin):
    list_display = ("author_name", "author_role", "moderation_state", "event", "created_at")
    list_filter = ("moderation_state",)
    search_fields = ("author_name", "question_text")

