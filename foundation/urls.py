from django.urls import path
from .views import (
    acknowledge_alert,
    alert_detail_view,
    app_shell,
    chapter_detail_view,
    country_hub_view,
    dashboard_drilldown,
    dashboard_export,
    health,
    individual_profile_view,
    leadership_level_view,
    mark_all_notifications_read,
    mark_notification_read,
    meeting_detail_view,
    meeting_rsvp,
    network_workspace_view,
    new_privacy_request,
    notifications_api,
    notifications_view,
    preferences_api,
    privacy_request_detail,
    privacy_request_export_download,
    privacy_requests_view,
    profile_view,
    report_detail_view,
    reset_preferences,
    retry_notification,
    search_api,
    search_view,
    settings_view,
    switch_role_view,
    switch_scope,
    dev_switch_user,
    work_item_action_view,
    work_item_detail_view,
    work_queue_view,
)

urlpatterns = [
    path("foundation/", app_shell, name="app-shell"),
    path("foundation/workspace/", app_shell, name="workspace"),
    path("app/", app_shell, name="app-shell-slash"),
    path("app", app_shell, name="app-shell-alias"),
    path("health", health, name="health"),
    path("api/health", health, name="api-health"),

    # Scope Hierarchy
    path("foundation/network/<str:network>/", network_workspace_view, name="network-workspace"),
    path("foundation/network/<str:network>/country/<str:country>/", country_hub_view, name="country-hub"),
    path("foundation/network/<str:network>/country/<str:country>/leadership/<str:level>/", leadership_level_view, name="leadership-level"),
    path("foundation/network/<str:network>/country/<str:country>/leadership/<str:level>/profile/<uuid:profile_id>/", individual_profile_view, name="individual-profile"),
    path("foundation/profile/", profile_view, name="profile"),
    path("foundation/scope/switch/", switch_scope, name="switch-scope"),

    # Work Queue
    path("foundation/work-queue/", work_queue_view, name="work-queue"),
    path("foundation/work-queue/<uuid:item_id>/", work_item_detail_view, name="work-item-detail"),
    path("foundation/work-queue/<uuid:item_id>/action/", work_item_action_view, name="work-item-action"),

    # Search Boundary
    path("foundation/search/", search_view, name="search"),
    path("foundation/api/search/", search_api, name="api-search"),

    # Notifications
    path("foundation/notifications/", notifications_view, name="notifications"),
    path("foundation/api/notifications/", notifications_api, name="api-notifications"),
    path("foundation/api/notifications/<uuid:notification_id>/read/", mark_notification_read, name="mark-notification-read"),
    path("foundation/api/notifications/mark-all-read/", mark_all_notifications_read, name="mark-all-notifications-read"),
    path("foundation/api/notifications/<uuid:notification_id>/retry/", retry_notification, name="retry-notification"),

    # Settings & Accessibility
    path("foundation/settings/", settings_view, name="settings"),
    path("foundation/api/preferences/", preferences_api, name="api-preferences"),
    path("foundation/settings/reset-preferences/", reset_preferences, name="reset-preferences"),

    # Privacy Requests
    path("foundation/privacy-requests/", privacy_requests_view, name="privacy-requests"),
    path("foundation/privacy-requests/new/", new_privacy_request, name="new-privacy-request"),
    path("foundation/privacy-requests/<uuid:request_id>/", privacy_request_detail, name="privacy-request-detail"),
    path("foundation/privacy-requests/<uuid:request_id>/export/", privacy_request_export_download, name="privacy-request-export"),

    # Stage 4 Dashboards, Drilldowns, Details, Actions & Exports
    path("foundation/dashboard/drilldown/<str:category>/", dashboard_drilldown, name="dashboard-drilldown"),
    path("foundation/dashboard/alerts/<uuid:alert_id>/", alert_detail_view, name="dashboard-alert-detail"),
    path("foundation/dashboard/alerts/<uuid:alert_id>/acknowledge/", acknowledge_alert, name="dashboard-alert-acknowledge"),
    path("foundation/dashboard/reports/<uuid:report_id>/", report_detail_view, name="dashboard-report-detail"),
    path("foundation/dashboard/meetings/<uuid:meeting_id>/", meeting_detail_view, name="dashboard-meeting-detail"),
    path("foundation/dashboard/meetings/<uuid:meeting_id>/rsvp/", meeting_rsvp, name="dashboard-meeting-rsvp"),
    path("foundation/dashboard/chapters/<uuid:chapter_id>/", chapter_detail_view, name="dashboard-chapter-detail"),
    path("foundation/dashboard/export/", dashboard_export, name="dashboard-export"),
    path("foundation/dashboard/switch-role/", switch_role_view, name="dashboard-switch-role"),
    path("foundation/dev-switch/<str:role_or_alias>/", dev_switch_user, name="dev-switch-user"),
]

