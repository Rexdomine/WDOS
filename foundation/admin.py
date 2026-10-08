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
