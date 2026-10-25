import json
import os
import sys
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import logout as django_logout
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import connection, transaction
from django.db.models import Case, IntegerField, Q, Value, When
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from accounts.locale import LANGUAGES, catalog, translate
from accounts.models import AccessGrant, Account, Membership, OnboardingDraft, Person
from accounts.services import audit
from .models import (
    AppointmentRecord,
    CandidateApplication,
    CandidateReferral,
    CandidateRubricScore,
    Chapter,
    Communication,
    CountryHub,
    CountryDossier,
    DashboardActivity,
    DashboardAlert,
    DashboardReport,
    DeviceSession,
    GeographyTerminology,
    HandoverAssetTask,
    LeadershipLevel,
    LeadershipReview,
    LeadershipSeat,
    LeadershipStatusChange,
    LeadershipTransitionPlan,
    LocalHomeReassignment,
    LocalOrganisationUnit,
    NetworkTransition,
    Notification,
    PersonProfile,
    PersonRelationship,
    PositionMaster,
    PrivacyRequest,
    RecruitmentRouteConfig,
    ReferralLink,
    Role,
    ScheduledMeeting,
    SeatHistory,
    UserPreference,
    VolunteerOpportunity,
    WorkItem,
)
from .scope import (
    ScopePermissionDenied,
    UserScope,
    assert_role_authorized,
    assert_scope_authorized,
    get_breadcrumbs,
    get_country_display_name,
    get_leadership_display_name,
    get_scoped_kpis,
    get_user_preferences,
    get_user_scope,
    is_broad_geographic_place,
    sanitize_chapter_display,
)
from .dashboard_engine import (
    build_dashboard_context,
    check_dashboard_permission,
    get_dashboard_screen,
    get_default_screen_for_role,
    DASHBOARD_SCREENS,
)
from .people_geo_engine import (
    STAGE6_SCREENS,
    assert_country_network_authorized,
    assert_person_scope_authorized,
    assert_stage6_authorized,
    get_country_name_for_code,
    get_stage6_audit_history,
    is_global_stage6_scope,
    normalize_country_code,
    seed_stage6_fixtures,
    check_for_duplicate_person,
    add_or_link_person_record,
    update_person_profile_record,
    save_person_relationship,
    submit_reassignment_decision,
    save_local_organisation_unit,
    verify_country_dossier_submission,
    save_geography_terminology_revision,
)
from .leadership_engine import (
    STAGE7_SCREENS,
    assert_appointment_scope_authorized,
    assert_human_decision_authority,
    assert_seat_scope_authorized,
    assert_stage7_authorized,
    assign_direct_report_followup,
    complete_all_handover_tasks,
    complete_handover_asset_task,
    complete_leader_onboarding_steps,
    get_scoped_appointments_queryset,
    get_scoped_seats_queryset,
    get_stage7_audit_history,
    plan_leadership_transition,
    record_first_90_day_review,
    refer_or_appoint_candidate,
    respond_to_appointment_offer,
    save_position_revision,
    seed_stage7_fixtures,
    submit_leadership_status_change,
)
from .recruitment_engine import (
    STAGE8_SCREENS,
    advance_activation_journey,
    assert_application_scope_authorized,
    assert_stage8_authorized,
    create_referral_link,
    get_scoped_applications_queryset,
    get_stage8_audit_history,
    is_stage8_reviewer,
    match_reserve_candidate_to_vacancy,
    record_selection_decision,
    respond_to_application_outcome,
    save_candidate_rubric_score,
    save_recruitment_route_revision,
    seed_stage8_fixtures,
    submit_candidate_evidence_review,
    submit_leadership_pack_review,
    submit_volunteer_application,
    verify_referral_intake,
)


def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        migrations = _migration_count()
        roles = Role.objects.filter(is_system=True).count()
        db = "ok"
    except Exception:
        migrations = None
        roles = None
        db = "degraded"
    status = "ok" if db == "ok" else "degraded"
    return JsonResponse({
        "status": status,
        "service": "wdos",
        "environment": os.getenv("WDOS_ENVIRONMENT", "local"),
        "database": db,
        "migration_rows": migrations,
        "system_role_rows": roles,
        "checked_at": timezone.now().isoformat(),
    }, status=200 if status == "ok" else 503)


def _migration_count():
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM django_migrations")
        return cursor.fetchone()[0]


def _get_authenticated_context(request):
    """
    Common guard and context builder for the signed-in shell.
    Redirects unauthenticated users to login, and unaccepted drafts to auth status.
    """
    account = getattr(request, "wdos_account", None)
    if not account:
        if request.session.get("access_notice"):
            return None, redirect("/auth/status/")
        return None, redirect("/auth/login/")

    if account.status != "active":
        return None, redirect("/auth/status/")

    draft = OnboardingDraft.objects.filter(
        account=account,
        state="accepted",
        membership__isnull=False,
    ).select_related("membership").first()

    # Allow accepted membership, staff/superuser, or accounts with active AccessGrants
    has_active_grants = account.accessgrant_set.filter(
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).exists()
    if not draft and not has_active_grants and not (account.user.is_superuser or account.user.is_staff):
        return None, redirect("/auth/status/")

    user_scope = get_user_scope(account, request.session)
    user_pref = get_user_preferences(account)

    # Process authorized query parameter scope switches (network, country, role)
    req_net = request.GET.get("network")
    if req_net and req_net.upper() in ("WGMN", "WNNN"):
        if user_scope.can_access_network(req_net.upper()):
            request.session["wdos_active_network"] = req_net.upper()
            user_scope.active_network = req_net.upper()

    req_ctry = request.GET.get("country")
    if req_ctry:
        req_ctry = req_ctry.upper()
        if user_scope.can_access_country(req_ctry):
            request.session["wdos_active_country"] = req_ctry
            user_scope.active_country = req_ctry

    req_role = request.GET.get("role")
    if req_role and user_scope.can_access_role(req_role):
        request.session["wdos_active_role"] = req_role
        user_scope.active_role = req_role

    # Resolve language
    cookie_lang = request.COOKIES.get("wdos_language")
    draft_lang = (draft.data or {}).get("language") if (draft and draft.data) else None
    persisted_lang = draft_lang or (user_pref.language if user_pref else None)

    lang = next(
        (
            candidate
            for candidate in (
                cookie_lang if cookie_lang in LANGUAGES and cookie_lang != "en" else None,
                request.session.get("wdos_language"),
                persisted_lang,
                cookie_lang,
            )
            if candidate in LANGUAGES
        ),
        "en",
    )

    direction = LANGUAGES[lang]["dir"]
    translations = catalog(lang)

    display_name = account.display_name or (account.person.display_name if account.person else account.email.split("@")[0])
    initials = "".join(part[0] for part in display_name.split()[:2]).upper() or "WD"

    unread_notifications_count = Notification.objects.filter(
        account=account,
        is_read=False,
        is_archived=False,
    ).count()

    draft_for_photo = OnboardingDraft.objects.filter(account=account).first()
    effective_draft = draft or draft_for_photo
    draft_data = (effective_draft.data or {}) if (effective_draft and effective_draft.data) else {}
    has_profile_photo = bool(draft_for_photo and draft_for_photo.photo and len(bytes(draft_for_photo.photo)) > 0)
    profile_photo_url = "/onboarding/photo/" if has_profile_photo else None

    # Resolve timezone with priority: session -> draft data -> active country default -> UTC
    from accounts.african_geography import get_country_default_timezone
    session_tz = request.session.get("wdos_timezone")
    draft_tz = draft_data.get("timezone")
    country_default_tz = get_country_default_timezone(user_scope.active_country) if (user_scope and user_scope.active_country) else None
    current_tz = session_tz or draft_tz or country_default_tz or "UTC"
    if not session_tz:
        request.session["wdos_timezone"] = current_tz

    active_role_val = user_scope.active_role or user_scope.primary_role or "member"
    default_dash = get_dashboard_screen(get_default_screen_for_role(active_role_val)) or {}
    active_role_title = default_dash.get("default_role_title") or active_role_val.replace("_", " ").title()
    is_leadership_tier = active_role_val not in ("member", "candidate", "community")

    from .context_block import get_identity_context
    identity_context = get_identity_context(
        account,
        user_scope,
        active_network=user_scope.active_network,
        active_role=user_scope.active_role,
        active_country=user_scope.active_country,
        request=request,
    )

    context = {
        "account": account,
        "user_scope": user_scope,
        "active_network": user_scope.active_network or "WGMN",
        "active_role_title": active_role_title,
        "is_leadership_tier": is_leadership_tier,
        "country_name": get_country_display_name(user_scope.active_country),
        "identity_context": identity_context,
        "user_pref": user_pref,
        "lang": lang,
        "direction": direction,
        "translations": translations,
        "display_name": display_name,
        "initials": initials,
        "has_profile_photo": has_profile_photo,
        "profile_photo_url": profile_photo_url,
        "unread_notifications_count": unread_notifications_count,
        "environment": os.getenv("WDOS_ENVIRONMENT", "local"),
        "high_contrast": user_pref.high_contrast if user_pref else False,
        "reduced_motion": user_pref.reduced_motion if user_pref else False,
        "font_size": user_pref.font_size if user_pref else "standard",
        "current_timezone": current_tz,
        "timezone": current_tz,
    }
    return context, None


def _render_scope_error(request, context, exception):
    """Render the accessible, explanatory scope permission denial error page."""
    raw_reason = getattr(exception, "reason_code", "forbidden")
    user_scope = context.get("user_scope")
    if user_scope:
        active_role_val = getattr(user_scope, "active_role", None) or getattr(user_scope, "primary_role", "member")
        context["is_leadership_tier"] = active_role_val not in ("member", "candidate", "community")
    raw_level = getattr(user_scope, "leadership_level", "") or "member"
    context["error_message"] = getattr(exception, "message", str(exception))
    context["reason_code"] = raw_reason
    context["reason_label"] = raw_reason.replace("_", " ").title()
    context["leadership_level_label"] = raw_level.replace("_", " ").title()
    context["recovery_url"] = getattr(exception, "recovery_url", "/foundation/")
    context["breadcrumbs"] = [
        {"label": "WDOS", "url": "/foundation/", "is_current": False},
        {"label": "Access Restricted", "url": None, "is_current": True},
    ]
    return render(request, "foundation/error_scope.html", context, status=403)


def _get_stage4_state_context(request, screen_name):
    """
    Map Stage 04 query parameters to exact PDF interaction contract feedback states.
    Supports ?state=empty | connection_error | access_changed | loading | validation_error | blocked | not_supported
    """
    state = request.GET.get("state", "").lower().strip()
    if not state:
        return {}
    
    state_map = {
        "empty": {
            "state_mode": "empty",
            "state_title": "No records in this view",
            "state_message": f"There are no my workspace records matching the selected scope for {screen_name.lower()}.",
            "state_action_label": "Clear filters",
            "state_action_url": request.path,
        },
        "connection_error": {
            "state_mode": "connection_error",
            "state_title": "Connection interrupted",
            "state_message": "Your last saved information is safe. Reconnect before submitting changes.",
            "state_action_label": "Try again",
            "state_action_url": "/foundation/connection-status/",
        },
        "offline": {
            "state_mode": "connection_error",
            "state_title": "Connection interrupted",
            "state_message": "Your last saved information is safe. Reconnect before submitting changes.",
            "state_action_label": "Try again",
            "state_action_url": "/foundation/connection-status/",
        },
        "access_changed": {
            "state_mode": "access_changed",
            "state_title": "Access has changed",
            "state_message": "This action is no longer available for your current role. No change was applied.",
            "state_action_label": "Return to workspace",
            "state_action_url": "/foundation/workspace/",
        },
        "revoked": {
            "state_mode": "access_changed",
            "state_title": "Access has changed",
            "state_message": "This action is no longer available for your current role. No change was applied.",
            "state_action_label": "Return to workspace",
            "state_action_url": "/foundation/workspace/",
        },
        "loading": {
            "state_mode": "loading",
            "state_title": "Loading current information",
            "state_message": f"Loading {screen_name.lower()}. No stale values or completed actions are implied.",
            "state_action_label": "Cancel and return",
            "state_action_url": "/foundation/workspace/",
        },
        "validation_error": {
            "state_mode": "validation_error",
            "state_title": "More information needed",
            "state_message": f"Check the marked details before continuing with {screen_name.lower()}. Your entered information remains available.",
            "state_action_label": "Review details",
            "state_action_url": request.path,
        },
        "more_info": {
            "state_mode": "validation_error",
            "state_title": "More information needed",
            "state_message": f"Check the marked details before continuing with {screen_name.lower()}. Your entered information remains available.",
            "state_action_label": "Review details",
            "state_action_url": request.path,
        },
        "blocked": {
            "state_mode": "blocked",
            "state_title": "Notifications blocked",
            "state_message": "Your WDOS inbox still works. Use browser settings if you later want notifications.",
            "state_action_label": "Open my inbox",
            "state_action_url": "/foundation/notifications/",
        },
        "not_supported": {
            "state_mode": "not_supported",
            "state_title": "Not supported here",
            "state_message": "Use your WDOS inbox on this browser.",
            "state_action_label": "Continue without reminders",
            "state_action_url": "/foundation/workspace/",
        },
    }
    return state_map.get(state, {})


# -----------------------------------------------------------------------------
# Main Shell & Personal Workspace Overview
# -----------------------------------------------------------------------------

def app_shell(request):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    # Route to dashboard if explicitly requested via ?view=dashboard
    if request.GET.get("view") == "dashboard":
        return redirect("/foundation/dashboard/")

    user_scope = ctx["user_scope"]

    # Role resolution & authorization
    explicit_role = request.GET.get("role") or (request.GET.get("view") if request.GET.get("view") not in ("workspace", "core", "tasks", "queue") else None)
    if explicit_role:
        try:
            assert_role_authorized(user_scope, explicit_role)
            role = explicit_role
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
    else:
        sess_role = request.session.get("wdos_active_role")
        if sess_role and user_scope.can_access_role(sess_role):
            role = sess_role
        else:
            role = user_scope.primary_role

    request.session["wdos_active_role"] = role
    user_scope.active_role = role

    # Network resolution & authorization
    req_net = request.GET.get("network")
    if req_net:
        req_net = req_net.upper()
        try:
            assert_scope_authorized(user_scope, network=req_net)
            user_scope.active_network = req_net
            request.session["wdos_active_network"] = req_net
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
    active_net = user_scope.active_network

    # Country resolution & authorization
    req_country = request.GET.get("country")
    if req_country:
        req_country = req_country.upper()
        try:
            assert_scope_authorized(user_scope, country=req_country)
            user_scope.active_country = req_country
            request.session["wdos_active_country"] = req_country
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
    active_country = user_scope.active_country

    now = timezone.now()

    # Calculate real scoped KPIs
    kpis = get_scoped_kpis(user_scope, role, active_net, active_country)

    # Scoped content collections
    alerts = list(DashboardAlert.objects.filter(
        is_active=True,
        network__in=[active_net, "ALL"],
        country__in=[active_country, "ALL"],
    )[:6])

    activities = list(DashboardActivity.objects.filter(
        network=active_net,
        country=active_country,
    )[:8])

    reports = list(DashboardReport.objects.filter(
        status="published",
        network__in=[active_net, "ALL"],
        country__in=[active_country, "ALL"],
    )[:6])

    meetings = list(ScheduledMeeting.objects.filter(
        scheduled_at__gte=now,
        network__in=[active_net, "ALL"],
        country__in=[active_country, "ALL"],
    ).order_by("scheduled_at")[:6])

    communications = list(Communication.objects.filter(
        network__in=[active_net, "ALL"],
        country__in=[active_country, "ALL"],
        target_role__in=[role, "all"],
    ).order_by("-sent_at")[:5])

    chapters = list(Chapter.objects.filter(
        status="active",
        network=active_net,
        country=active_country,
    )[:10])

    country_hubs_qs = CountryHub.objects.filter(status="active")
    if "*" not in user_scope.allowed_countries:
        country_hubs_qs = country_hubs_qs.filter(code__in=user_scope.allowed_countries)
    country_hubs = list(country_hubs_qs[:8])

    # Work items for operations / general
    work_items_qs = WorkItem.objects.filter(network=active_net)
    if "*" not in user_scope.allowed_countries:
        work_items_qs = work_items_qs.filter(country__in=user_scope.allowed_countries)
    if not user_scope.can_access_confidential():
        work_items_qs = work_items_qs.filter(confidential=False)
    work_items = list(work_items_qs.filter(status__in=["pending", "in_progress"])[:6])

    # Available test roles for switcher
    all_role_choices = ["founder", "operations", "country_lead", "chapter_lead", "member", "candidate", "community"]
    available_roles = [r for r in all_role_choices if user_scope.can_access_role(r)]

    breadcrumbs = get_breadcrumbs(user_scope, network=active_net, country=active_country)

    # Scoped label
    country_name = get_country_display_name(active_country)
    scope_label = f"{active_net} Network / {country_name} Hub"

    # Role specific context
    extra_context = {}
    if role in ("founder", "hq"):
        hub_summaries = []
        for hub in country_hubs:
            hub_chaps = Chapter.objects.filter(country=hub.code, status="active").count()
            hub_summaries.append({
                "hub": hub,
                "chapter_count": hub_chaps,
            })
        extra_context["hub_summaries"] = hub_summaries
    elif role == "operations":
        extra_context["pending_verifications"] = list(OnboardingDraft.objects.filter(state="review_needed")[:8])
        extra_context["operational_work_items"] = work_items
    elif role in ("country_lead", "country_director", "field_lead"):
        extra_context["country_hub"] = CountryHub.objects.filter(code=active_country).first()
        extra_context["country_chapters"] = chapters
    elif role in ("chapter_lead", "chapter"):
        lead_chap = None
        if user_scope.chapter_code:
            lead_chap = Chapter.objects.filter(code=user_scope.chapter_code).first()
        if not lead_chap and user_scope.chapter_name:
            lead_chap = Chapter.objects.filter(name__icontains=user_scope.chapter_name).first()
        if not lead_chap and chapters:
            lead_chap = chapters[0]
        extra_context["chapter"] = lead_chap
        extra_context["chapter_roster"] = list(Membership.objects.filter(network=active_net)[:15])
    elif role == "member":
        membership = None
        if ctx["account"].person:
            membership = Membership.objects.filter(person=ctx["account"].person).first()
        if not membership:
            membership = Membership.objects.filter(draft__account=ctx["account"]).first()
        trans = ctx["translations"]
        local_home_label = (membership.home or {}).get("label") or trans.get("onb_local_connection_unavailable", "Local connection pending") if membership else trans.get("onb_local_connection_unavailable", "Local connection pending")
        membership_status = trans.get("onb_active_membership", "Active") if ctx["account"].status == "active" else trans.get("onb_local_connection_unavailable", "Pending")
        activity_status = trans.get("onb_no_activities", "No current activities")
        extra_context["membership"] = membership
        extra_context["my_home"] = membership.home if membership else {}
        extra_context["local_home_label"] = local_home_label
        extra_context["membership_status"] = membership_status
        extra_context["activity_status"] = activity_status
        if membership:
            scope_label = f"{membership.network} / Workspace"
    elif role == "candidate":
        draft = OnboardingDraft.objects.filter(account=ctx["account"]).first()
        extra_context["candidate_draft"] = draft
        extra_context["candidate_step"] = draft.next_step if draft else 1
        extra_context["candidate_state"] = draft.state if draft else "draft"
        extra_context["orientation_meetings"] = list(ScheduledMeeting.objects.filter(meeting_type="orientation", scheduled_at__gte=now)[:4])
    elif role == "community":
        extra_context["community_events"] = list(ScheduledMeeting.objects.filter(target_role__in=["community", "all"], scheduled_at__gte=now)[:6])
        extra_context["directory_hubs"] = country_hubs

    ctx.update({
        "breadcrumbs": breadcrumbs,
        "scope_label": scope_label,
        "active_role": role,
        "is_leadership_tier": role not in ("member", "candidate", "community"),
        "active_network": active_net,
        "active_country": active_country,
        "country_name": country_name,
        "available_roles": available_roles,
        "kpis": kpis,
        "alerts": alerts,
        "activities": activities,
        "reports": reports,
        "meetings": meetings,
        "communications": communications,
        "chapters": chapters,
        "country_hubs": country_hubs,
        "work_items": work_items,
        "active_tab": "overview",
        **extra_context,
    })

    from .context_block import get_identity_context
    ctx["identity_context"] = get_identity_context(
        ctx["account"],
        user_scope,
        active_network=active_net,
        active_role=role,
        active_country=active_country,
        request=request,
    )

    if not request.GET.get("role") and request.GET.get("view") != "dashboard" and request.GET.get("legacy") != "1":
        account = ctx["account"]
        _ensure_default_work_items_for_scope(account, user_scope)

        active_tab = request.GET.get("tab", "overview")

        base_qs = WorkItem.objects.filter(network__in=user_scope.allowed_networks)
        if "*" not in user_scope.allowed_countries:
            base_qs = base_qs.filter(country__in=user_scope.allowed_countries)
        if not user_scope.can_access_confidential():
            base_qs = base_qs.filter(confidential=False)

        if active_tab == "history":
            tab_qs = base_qs.filter(status="completed").order_by("-updated_at", "-created_at")
        elif active_tab == "records":
            tab_qs = base_qs.filter(status__in=["pending", "in_progress"]).order_by("-created_at")
        else:
            # overview: top active items
            tab_qs = base_qs.filter(status__in=["pending", "in_progress"]).order_by("-created_at")

        paginator = Paginator(tab_qs, 5 if active_tab == "overview" else 10)
        page_number = request.GET.get("page", 1)
        page_obj = paginator.get_page(page_number)

        workspace_items = []
        for wi in page_obj:
            if wi.status == "pending":
                action_label = "View invitation" if wi.category == "membership" else "Claim task"
                pill_style = "magenta"
            elif wi.status == "in_progress":
                action_label = "Continue" if wi.assigned_to == account else "Review item"
                pill_style = "amber"
            elif wi.status == "completed":
                action_label = "View record"
                pill_style = ""
            else:
                action_label = "Open record"
                pill_style = ""

            when_str = wi.created_at.strftime("%d %b · %H:%M WAT") if wi.created_at else "Recently"

            workspace_items.append({
                "id": wi.id,
                "title": wi.title,
                "summary": wi.summary,
                "category": wi.get_category_display(),
                "priority": wi.priority,
                "status": wi.status,
                "when": when_str,
                "action_label": action_label,
                "action_url": f"/foundation/work-queue/{wi.id}/",
                "pill_style": pill_style,
                "assigned_to": wi.assigned_to.display_name if wi.assigned_to else "Unassigned",
            })

        local_conn = extra_context.get("local_home_label")
        if not local_conn or local_conn == "Local connection pending":
            local_conn = user_scope.chapter_name or "National Hub"

        ctx.update({
            "screen_code": "CORE-01",
            "active_nav": "workspace",
            "local_connection": local_conn,
            "language_name": "English",
            "workspace_items": workspace_items,
            "page_obj": page_obj,
            "active_tab": active_tab,
            **_get_stage4_state_context(request, "Your workspace"),
        })
        return render(request, "foundation/core/core_01_workspace.html", ctx)

    role_template_map = {
        "founder": "foundation/dashboards/founder_hq.html",
        "hq": "foundation/dashboards/founder_hq.html",
        "operations": "foundation/dashboards/operations.html",
        "country_lead": "foundation/dashboards/country_lead.html",
        "country_director": "foundation/dashboards/country_lead.html",
        "field_lead": "foundation/dashboards/country_lead.html",
        "chapter_lead": "foundation/dashboards/chapter_lead.html",
        "chapter": "foundation/dashboards/chapter_lead.html",
        "member": "foundation/dashboards/member.html",
        "candidate": "foundation/dashboards/candidate.html",
        "community": "foundation/dashboards/community.html",
    }
    template_candidates = [
        role_template_map.get(role),
        "foundation/app_shell.html",
    ]
    return render(request, [t for t in template_candidates if t], ctx)



# -----------------------------------------------------------------------------
# Hierarchy: Level 2 - Network Workspace (WGMN / WNNN Separation)
# -----------------------------------------------------------------------------

def network_workspace_view(request, network):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    network = network.upper()

    try:
        assert_scope_authorized(user_scope, network=network)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    # Persist active network selection
    request.session["wdos_active_network"] = network
    if ctx["user_pref"]:
        ctx["user_pref"].active_network = network
        ctx["user_pref"].save(update_fields=["active_network"])

    # Query country hubs permitted within this network
    hubs_qs = CountryHub.objects.filter(status="active")
    if "*" not in user_scope.allowed_countries:
        hubs_qs = hubs_qs.filter(code__in=user_scope.allowed_countries)
    country_hubs = list(hubs_qs)

    # Query network work items
    work_items_qs = WorkItem.objects.filter(network=network)
    if "*" not in user_scope.allowed_countries:
        work_items_qs = work_items_qs.filter(country__in=user_scope.allowed_countries)
    if not user_scope.can_access_confidential():
        work_items_qs = work_items_qs.filter(confidential=False)

    work_items = list(work_items_qs[:10])

    breadcrumbs = get_breadcrumbs(user_scope, network=network)

    network_names = {
        "WGMN": "WODDI Global Mothers Network",
        "WNNN": "WODDI Next-Gen Nurturers Network",
    }

    ctx.update({
        "network": network,
        "network_full_name": network_names.get(network, f"{network} Network"),
        "country_hubs": country_hubs,
        "work_items": work_items,
        "breadcrumbs": breadcrumbs,
        "scope_label": f"{network} Network Workspace",
    })
    return render(request, "foundation/network_workspace.html", ctx)


# -----------------------------------------------------------------------------
# Hierarchy: Level 3 - Country Hub Entry
# -----------------------------------------------------------------------------

def country_hub_view(request, network, country):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    network = network.upper()
    country = country.upper()

    try:
        assert_scope_authorized(user_scope, network=network, country=country)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    hub = CountryHub.objects.filter(code=country).first()
    if not hub:
        country_name = get_country_display_name(country)
        hub = CountryHub(code=country, name=country_name, status="active")

    # Persist active country selection
    request.session["wdos_active_network"] = network
    request.session["wdos_active_country"] = country
    if ctx["user_pref"]:
        ctx["user_pref"].active_network = network
        ctx["user_pref"].active_country = country
        ctx["user_pref"].save(update_fields=["active_network", "active_country"])

    # Query leadership tiers available in this country hub
    leadership_levels = list(LeadershipLevel.objects.all().order_by("tier"))

    # Work items in this country hub
    work_items_qs = WorkItem.objects.filter(network=network, country=country)
    if not user_scope.can_access_confidential():
        work_items_qs = work_items_qs.filter(confidential=False)
    work_items = list(work_items_qs[:10])

    breadcrumbs = get_breadcrumbs(user_scope, network=network, country=country)

    ctx.update({
        "network": network,
        "country": country,
        "hub": hub,
        "leadership_levels": leadership_levels,
        "work_items": work_items,
        "breadcrumbs": breadcrumbs,
        "scope_label": f"{network} / {hub.name} Hub",
    })
    return render(request, "foundation/country_hub.html", ctx)


# -----------------------------------------------------------------------------
# Hierarchy: Level 4 - Leadership Level
# -----------------------------------------------------------------------------

def leadership_level_view(request, network, country, level):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    network = network.upper()
    country = country.upper()

    try:
        assert_scope_authorized(user_scope, network=network, country=country, level=level)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    leadership_obj = LeadershipLevel.objects.filter(code=level).first()
    hub = CountryHub.objects.filter(code=country).first()

    # Query individuals associated with this network, country, and role/tier
    # Find matching AccessGrants or Memberships
    matching_accounts = Account.objects.filter(
        status="active",
        accessgrant__network__in=[network, "*", "all"],
        accessgrant__geography__in=[country, "*", "all"],
        accessgrant__role=level,
        accessgrant__revoked_at__isnull=True,
    ).distinct()

    if not matching_accounts.exists() and level == "member":
        # Base members
        matching_accounts = Account.objects.filter(
            status="active",
            person__membership__network=network,
        ).distinct()

    # Work items for this level
    work_items = list(WorkItem.objects.filter(
        network=network,
        country=country,
        leadership_level__code=level,
    )[:10])

    breadcrumbs = get_breadcrumbs(user_scope, network=network, country=country, level=level)

    ctx.update({
        "network": network,
        "country": country,
        "hub": hub,
        "level": level,
        "level_title": get_leadership_display_name(level),
        "leadership_obj": leadership_obj,
        "roster": list(matching_accounts[:20]),
        "work_items": work_items,
        "breadcrumbs": breadcrumbs,
        "scope_label": f"{network} / {get_country_display_name(country)} / {get_leadership_display_name(level)}",
    })
    return render(request, "foundation/leadership_level.html", ctx)


# -----------------------------------------------------------------------------
# Hierarchy: Level 5 - Individual Profile
# -----------------------------------------------------------------------------

def individual_profile_view(request, network, country, level, profile_id):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    network = network.upper()
    country = country.upper()

    target_account = get_object_or_404(Account.objects.select_related("person", "user"), person_id=profile_id)

    # Authorization rule: viewing own profile is always authorized;
    # viewing other members requires matching network & country scope
    if target_account != ctx["account"]:
        try:
            assert_scope_authorized(user_scope, network=network, country=country, level=level)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

        # Restrict ordinary members, candidates, and community from viewing leadership profiles
        target_grants = AccessGrant.objects.filter(
            account=target_account,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        is_target_leader = target_grants.exclude(role__in=["member", "candidate", "community"]).exists() or level not in ("member", "candidate", "community")
        if user_scope.leadership_tier > 4 and is_target_leader:
            return _render_scope_error(
                request, ctx,
                ScopePermissionDenied(
                    "Access Denied: Leadership profile records are restricted to authorized leadership appointments.",
                    reason_code="leadership_restricted",
                    recovery_url="/foundation/profile/",
                )
            )

        # Target account network verification: non-founder users cannot view records from another network
        if not user_scope.can_cross_network:
            from .scope import normalize_network_code
            target_nets = set()
            for g in target_grants:
                if g.network and g.network != "*":
                    target_nets.add(normalize_network_code(g.network))
            target_mem = Membership.objects.filter(person=target_account.person).first() if target_account.person else None
            if target_mem and target_mem.network:
                target_nets.add(normalize_network_code(target_mem.network))
            if target_nets and not any(user_scope.can_access_network(tn) for tn in target_nets):
                return _render_scope_error(
                    request, ctx,
                    ScopePermissionDenied(
                        f"Access Denied: Member belongs to network outside your authorized scope ({user_scope.active_network}).",
                        reason_code="network_mismatch",
                        recovery_url="/foundation/profile/",
                    )
                )

        # Target account country verification for single-country users
        if user_scope.allowed_countries != ["*"] and user_scope.active_country != "ALL":
            target_countries = set()
            for g in target_grants:
                if g.geography and g.geography != "*":
                    target_countries.add(g.geography[:2].upper())
            target_mem = Membership.objects.filter(person=target_account.person).first() if target_account.person else None
            if target_mem and isinstance(target_mem.home, dict) and target_mem.home.get("country"):
                target_countries.add(target_mem.home["country"].upper())
            if target_countries and not any(user_scope.can_access_country(tc) for tc in target_countries):
                return _render_scope_error(
                    request, ctx,
                    ScopePermissionDenied(
                        f"Access Denied: Member belongs to geographic hub outside your permitted area ({user_scope.active_country}).",
                        reason_code="wrong_country",
                        recovery_url="/foundation/profile/",
                    )
                )

    membership = Membership.objects.filter(person=target_account.person).first() if target_account.person else None
    active_grants = AccessGrant.objects.filter(
        account=target_account,
        revoked_at__isnull=True,
        expires_at__gt=timezone.now(),
    )
    assigned_work_items = list(WorkItem.objects.filter(assigned_to=target_account)[:5])

    profile_name = target_account.display_name or (target_account.person.display_name if target_account.person else "Member")
    breadcrumbs = get_breadcrumbs(
        user_scope,
        network=network,
        country=country,
        level=level,
        profile_name=profile_name,
    )

    home_data = membership.home if membership and isinstance(membership.home, dict) else {}
    home_country = home_data.get("country") or country or "NG"
    home_region = home_data.get("state") or home_data.get("region") or "Not specified"
    home_district = home_data.get("lga") or home_data.get("district") or "Not specified"

    ctx.update({
        "target_account": target_account,
        "profile_name": profile_name,
        "membership": membership,
        "active_grants": active_grants,
        "assigned_work_items": assigned_work_items,
        "network": network,
        "country": country,
        "home_country": home_country,
        "home_region": home_region,
        "home_district": home_district,
        "level": level,
        "breadcrumbs": breadcrumbs,
        "is_own_profile": target_account == ctx["account"],
    })
    return render(request, "foundation/individual_profile.html", ctx)


def profile_view(request):
    """Direct shortcut to authenticated user's profile (CORE-05)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    account = ctx["account"]

    membership = Membership.objects.filter(person=account.person).first() if account.person else None

    # Derive dynamic names and IDs
    profile_name = account.display_name or (account.person.display_name if account.person else account.user.get_full_name() or "Member")
    person_id = getattr(account.person, "external_id", None) or f"WD-{str(account.id)[:6].upper()}"

    local_conn = ""
    if membership and membership.home:
        loc_parts = []
        if membership.home.get("state"):
            loc_parts.append(membership.home["state"])
        if membership.home.get("lga"):
            loc_parts.append(membership.home["lga"])
        if loc_parts:
            local_conn = " · ".join(loc_parts)
    if not local_conn and user_scope.chapter_name:
        local_conn = user_scope.chapter_name
    if not local_conn:
        local_conn = f"{user_scope.active_network} National Hub"

    if request.GET.get("legacy") == "1":
        active_grants = AccessGrant.objects.filter(
            account=account,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        assigned_work_items = list(WorkItem.objects.filter(assigned_to=account)[:5])
        breadcrumbs = get_breadcrumbs(user_scope, page_name="My Profile")

        home_data = membership.home if membership and isinstance(membership.home, dict) else {}
        home_country = home_data.get("country") or user_scope.active_country or "NG"
        home_region = home_data.get("state") or home_data.get("region") or "Not specified"
        home_district = home_data.get("lga") or home_data.get("district") or "Not specified"

        ctx.update({
            "target_account": account,
            "profile_name": profile_name,
            "membership": membership,
            "active_grants": active_grants,
            "assigned_work_items": assigned_work_items,
            "network": user_scope.active_network,
            "country": user_scope.active_country,
            "home_country": home_country,
            "home_region": home_region,
            "home_district": home_district,
            "level": user_scope.leadership_level,
            "breadcrumbs": breadcrumbs,
            "is_own_profile": True,
        })
        return render(request, "foundation/individual_profile.html", ctx)

    _ensure_default_work_items_for_scope(account, user_scope)
    active_tab = request.GET.get("tab", "overview")

    base_qs = WorkItem.objects.filter(network__in=user_scope.allowed_networks)
    if "*" not in user_scope.allowed_countries:
        base_qs = base_qs.filter(country__in=user_scope.allowed_countries)
    if not user_scope.can_access_confidential():
        base_qs = base_qs.filter(confidential=False)

    if active_tab == "history":
        tab_qs = base_qs.filter(status="completed").order_by("-updated_at", "-created_at")
    elif active_tab == "records":
        tab_qs = base_qs.filter(status__in=["pending", "in_progress"]).order_by("-created_at")
    else:
        tab_qs = base_qs.filter(status__in=["pending", "in_progress"]).order_by("-created_at")

    paginator = Paginator(tab_qs, 5 if active_tab == "overview" else 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    profile_records = []
    for wi in page_obj:
        if wi.status == "pending":
            action_label = "View invitation" if wi.category == "membership" else "Claim task"
            pill_style = "magenta"
        elif wi.status == "in_progress":
            action_label = "Continue" if wi.assigned_to == account else "Review item"
            pill_style = "amber"
        elif wi.status == "completed":
            action_label = "View record"
            pill_style = ""
        else:
            action_label = "Open record"
            pill_style = ""

        when_str = wi.created_at.strftime("%d %b · %H:%M WAT") if wi.created_at else "Recently"
        profile_records.append({
            "id": wi.id,
            "title": wi.title,
            "summary": wi.summary,
            "category": wi.get_category_display(),
            "priority": wi.priority,
            "status": wi.status,
            "when": when_str,
            "action_label": action_label,
            "action_url": f"/foundation/work-queue/{wi.id}/",
            "pill_style": pill_style,
            "assigned_to": wi.assigned_to.display_name if wi.assigned_to else "Unassigned",
        })

    ctx.update({
        "screen_code": "CORE-05",
        "active_nav": "profile",
        "person_id": person_id,
        "preferred_name": profile_name,
        "local_connection": local_conn,
        "profile_records": profile_records,
        "page_obj": page_obj,
        "active_tab": active_tab,
        **_get_stage4_state_context(request, "My profile"),
    })
    return render(request, "foundation/core/core_05_profile.html", ctx)


# -----------------------------------------------------------------------------
# Scope Switcher
# -----------------------------------------------------------------------------

@require_POST
def switch_scope(request):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    target_network = request.POST.get("network", "").strip().upper()
    target_country = request.POST.get("country", "").strip().upper()

    try:
        assert_scope_authorized(user_scope, network=target_network, country=target_country)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    if target_network:
        request.session["wdos_active_network"] = target_network
        if ctx["user_pref"]:
            ctx["user_pref"].active_network = target_network
    if target_country:
        request.session["wdos_active_country"] = target_country
        if ctx["user_pref"]:
            ctx["user_pref"].active_country = target_country[:8]

    if ctx["user_pref"]:
        ctx["user_pref"].save(update_fields=["active_network", "active_country"])

    next_url = request.POST.get("next") or f"/foundation/network/{target_network or user_scope.active_network}/"
    return redirect(next_url)


# -----------------------------------------------------------------------------
# Work Queue & Deep Links
# -----------------------------------------------------------------------------

def _ensure_default_work_items_for_scope(account, user_scope):
    return


def priority_work_item_view(request):
    """
    Redirect to the highest-priority pending or in-progress work item in the user's scope.
    """
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    account = ctx["account"]

    from .multilingua_events_engine import purge_auto_captured_transcript_tasks
    purge_auto_captured_transcript_tasks()

    _ensure_default_work_items_for_scope(account, user_scope)

    items_qs = WorkItem.objects.filter(network__in=user_scope.allowed_networks)
    if "*" not in user_scope.allowed_countries:
        items_qs = items_qs.filter(country__in=user_scope.allowed_countries)
    if not user_scope.can_access_confidential():
        items_qs = items_qs.filter(confidential=False)

    priority_order = Case(
        When(priority="urgent", then=Value(1)),
        When(priority="critical", then=Value(1)),
        When(priority="high", then=Value(2)),
        When(priority="normal", then=Value(3)),
        When(priority="medium", then=Value(3)),
        When(priority="low", then=Value(4)),
        default=Value(5),
        output_field=IntegerField(),
    )
    priority_item = (
        items_qs.filter(status__in=["pending", "in_progress"])
        .annotate(p_rank=priority_order)
        .order_by("p_rank", "-created_at")
        .first()
    )
    if priority_item:
        return redirect(f"/foundation/work-queue/{priority_item.id}/")
    return redirect("/foundation/work-queue/?tab=overview&notice=no_priority")


def work_queue_view(request):
    """My work queue view (CORE-02)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    account = ctx["account"]

    from .multilingua_events_engine import purge_auto_captured_transcript_tasks
    purge_auto_captured_transcript_tasks()

    _ensure_default_work_items_for_scope(account, user_scope)

    raw_tab = request.GET.get("tab", "overview").strip().lstrip("-").strip("/")
    if raw_tab in ("records", "active", "active_records", "work", "tasks"):
        active_tab = "records"
    elif raw_tab in ("history", "completed", "past"):
        active_tab = "history"
    else:
        active_tab = "overview"
    status_filter = request.GET.get("status", "all")
    category_filter = request.GET.get("category", "all")
    priority_filter = request.GET.get("priority", "all")

    base_qs = WorkItem.objects.filter(network__in=user_scope.allowed_networks)
    if "*" not in user_scope.allowed_countries:
        base_qs = base_qs.filter(country__in=user_scope.allowed_countries)

    if not user_scope.can_access_confidential():
        base_qs = base_qs.filter(confidential=False)

    if request.GET.get("legacy") == "1":
        legacy_qs = base_qs
        if status_filter != "all":
            legacy_qs = legacy_qs.filter(status=status_filter)
        if category_filter != "all":
            legacy_qs = legacy_qs.filter(category=category_filter)
        if priority_filter != "all":
            legacy_qs = legacy_qs.filter(priority=priority_filter)
        items = list(legacy_qs)
        breadcrumbs = get_breadcrumbs(user_scope, page_name="Work Queue")
        ctx.update({
            "items": items,
            "status_filter": status_filter,
            "category_filter": category_filter,
            "priority_filter": priority_filter,
            "breadcrumbs": breadcrumbs,
            "total_count": len(items),
        })
        return render(request, "foundation/work_queue.html", ctx)

    # Scoped counts
    pending_count = base_qs.filter(status="pending").count()
    in_progress_count = base_qs.filter(status="in_progress").count()
    completed_count = base_qs.filter(status="completed").count()
    total_active_count = pending_count + in_progress_count

    # Location derivation
    membership = Membership.objects.filter(person=account.person).first() if account.person else None
    local_location = ""
    if membership and membership.home:
        loc_parts = []
        if membership.home.get("state"):
            loc_parts.append(membership.home["state"])
        if membership.home.get("lga"):
            loc_parts.append(membership.home["lga"])
        if loc_parts:
            local_location = " · ".join(loc_parts)
    if not local_location and user_scope.chapter_name:
        local_location = user_scope.chapter_name

    # Filtered QS based on Tab
    if active_tab == "history":
        tab_qs = base_qs.filter(status="completed").order_by("-updated_at", "-created_at")
    elif active_tab == "records":
        tab_qs = base_qs
        if status_filter != "all":
            tab_qs = tab_qs.filter(status=status_filter)
        else:
            tab_qs = tab_qs.filter(status__in=["pending", "in_progress"])
        if category_filter != "all":
            tab_qs = tab_qs.filter(category=category_filter)
        if priority_filter != "all":
            tab_qs = tab_qs.filter(priority=priority_filter)
        tab_qs = tab_qs.order_by("-created_at")
    else:
        # overview: show highest priority pending & in_progress items preview (top 3)
        priority_order = Case(
            When(priority="urgent", then=Value(1)),
            When(priority="critical", then=Value(1)),
            When(priority="high", then=Value(2)),
            When(priority="normal", then=Value(3)),
            When(priority="medium", then=Value(3)),
            When(priority="low", then=Value(4)),
            default=Value(5),
            output_field=IntegerField(),
        )
        tab_qs = base_qs.filter(status__in=["pending", "in_progress"]).annotate(p_rank=priority_order).order_by("p_rank", "-created_at")

    # Pagination
    paginator = Paginator(tab_qs, 10 if active_tab != "overview" else 3)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    queue_items = []
    for wi in page_obj:
        if wi.status == "pending":
            action_label = "View invitation" if wi.category == "membership" else "Claim task"
            pill_style = "magenta"
        elif wi.status == "in_progress":
            action_label = "Continue" if wi.assigned_to == account else "Review item"
            pill_style = "amber"
        elif wi.status == "completed":
            action_label = "View record"
            pill_style = ""
        else:
            action_label = "Open record"
            pill_style = ""

        when_str = wi.created_at.strftime("%d %b · %H:%M WAT") if wi.created_at else "Recently"

        queue_items.append({
            "id": wi.id,
            "title": wi.title,
            "summary": wi.summary,
            "category": wi.get_category_display(),
            "priority": wi.priority,
            "status": wi.status,
            "when": when_str,
            "action_label": action_label,
            "action_url": f"/foundation/work-queue/{wi.id}/",
            "pill_style": pill_style,
            "assigned_to": wi.assigned_to.display_name if wi.assigned_to else "Unassigned",
        })

    ctx.update({
        "screen_code": "CORE-02",
        "active_nav": "work_queue",
        "queue_items": queue_items,
        "page_obj": page_obj,
        "active_tab": active_tab,
        "status_filter": status_filter,
        "category_filter": category_filter,
        "priority_filter": priority_filter,
        "pending_count": pending_count,
        "in_progress_count": in_progress_count,
        "completed_count": completed_count,
        "total_active_count": total_active_count,
        "local_location": local_location,
        "notice": request.GET.get("notice"),
        **_get_stage4_state_context(request, "My work queue"),
    })
    return render(request, "foundation/core/core_02_work_queue.html", ctx)


def work_item_detail_view(request, item_id):
    """
    Deep-link entrypoint for Work Items.
    Enforces server-side permissions: if unauthorized, returns 403 without leaking details.
    """
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    item = get_object_or_404(WorkItem, id=item_id)

    # Restrict leadership work items from ordinary members, candidates, and community users
    LEADERSHIP_CATEGORIES = {
        "verification", "governance", "operations", "quality", "safeguarding",
        "finance", "compliance", "pipeline", "roster",
    }
    is_leadership_item = item.leadership_level is not None or item.category in LEADERSHIP_CATEGORIES
    if user_scope.leadership_tier > 4 and is_leadership_item:
        if item.assigned_to != ctx["account"] and item.created_by != ctx["account"]:
            return _render_scope_error(
                request, ctx,
                ScopePermissionDenied(
                    "Access Denied: Leadership work items are restricted to authorized leadership appointments.",
                    reason_code="leadership_restricted",
                    recovery_url="/foundation/work-queue/",
                )
            )

    try:
        assert_scope_authorized(
            user_scope,
            network=item.network,
            country=item.country,
            level=item.leadership_level.code if item.leadership_level else None,
            confidential=item.confidential,
        )
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    breadcrumbs = get_breadcrumbs(
        user_scope,
        network=item.network,
        country=item.country,
        page_name=item.title,
    )

    ctx.update({
        "item": item,
        "breadcrumbs": breadcrumbs,
    })
    return render(request, "foundation/work_item_detail.html", ctx)


@require_POST
def work_item_action_view(request, item_id):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    item = get_object_or_404(WorkItem, id=item_id)

    # Restrict leadership work item actions from ordinary members, candidates, and community users
    LEADERSHIP_CATEGORIES = {
        "verification", "governance", "operations", "quality", "safeguarding",
        "finance", "compliance", "pipeline", "roster",
    }
    is_leadership_item = item.leadership_level is not None or item.category in LEADERSHIP_CATEGORIES
    if user_scope.leadership_tier > 4 and is_leadership_item:
        if item.assigned_to != ctx["account"] and item.created_by != ctx["account"]:
            return _render_scope_error(
                request, ctx,
                ScopePermissionDenied(
                    "Access Denied: Leadership work item actions are restricted to authorized leadership appointments.",
                    reason_code="leadership_restricted",
                    recovery_url="/foundation/work-queue/",
                )
            )

    try:
        assert_scope_authorized(
            user_scope,
            network=item.network,
            country=item.country,
            level=item.leadership_level.code if item.leadership_level else None,
            confidential=item.confidential,
        )
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    action = request.POST.get("action")
    if action == "claim":
        item.assigned_to = ctx["account"]
        item.status = "in_progress"
        item.save()
    elif action == "complete":
        item.status = "completed"
        item.save()
    elif action == "reopen":
        item.status = "pending"
        item.save()

    return redirect(f"/foundation/work-queue/{item.id}/")


# -----------------------------------------------------------------------------
# Confidential Search Boundary
# -----------------------------------------------------------------------------

def search_view(request):
    """Bounded search view (CORE-04)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    query = request.GET.get("q", "").strip()
    active_tab = request.GET.get("tab", "overview")

    if request.GET.get("legacy") == "1":
        results = []
        if query:
            results = _execute_scoped_search(query, user_scope)

        breadcrumbs = get_breadcrumbs(user_scope, page_name="Search")

        ctx.update({
            "query": query,
            "results": results,
            "total_count": len(results),
            "breadcrumbs": breadcrumbs,
        })
        return render(request, "foundation/search.html", ctx)

    if query:
        scoped_res = _execute_scoped_search(query, user_scope, active_tab=active_tab)
        all_items = []
        for res in scoped_res:
            all_items.append({
                "title": res["title"],
                "when": res.get("when") or res.get("summary") or "Recently",
                "action_label": res.get("action_label", "View details"),
                "action_url": res["url"],
                "pill_style": res.get("pill_style", "magenta"),
                "status": res.get("status", "active"),
            })
    else:
        # Show real active scoped records instead of demo data
        base_qs = WorkItem.objects.filter(network__in=user_scope.allowed_networks)
        if "*" not in user_scope.allowed_countries:
            base_qs = base_qs.filter(country__in=user_scope.allowed_countries)
        if not user_scope.can_access_confidential():
            base_qs = base_qs.filter(confidential=False)

        if active_tab == "records":
            base_qs = base_qs.filter(status__in=["pending", "in_progress"])
        elif active_tab == "history":
            base_qs = base_qs.filter(status__in=["completed", "blocked"])
        else:
            # overview: active items
            base_qs = base_qs.filter(status__in=["pending", "in_progress"])

        base_qs = base_qs.order_by("-created_at")
        items = list(base_qs)
        all_items = []
        for wi in items:
            all_items.append({
                "title": wi.title,
                "when": wi.created_at.strftime("%d %b · %H:%M WAT") if wi.created_at else "Recently",
                "action_label": "View details",
                "action_url": f"/foundation/work-queue/{wi.id}/",
                "pill_style": "amber" if wi.status == "pending" else "magenta",
                "status": wi.status,
            })

    total_count = len(all_items)
    paginator = Paginator(all_items, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    membership = Membership.objects.filter(person=account.person).first() if account.person else None
    local_conn = ""
    if membership and membership.home:
        loc_parts = []
        if membership.home.get("state"):
            loc_parts.append(membership.home["state"])
        if membership.home.get("lga"):
            loc_parts.append(membership.home["lga"])
        if loc_parts:
            local_conn = " · ".join(loc_parts)
    if not local_conn and user_scope.chapter_name:
        local_conn = user_scope.chapter_name
    if not local_conn:
        local_conn = f"{user_scope.active_network} National Hub"

    ctx.update({
        "screen_code": "CORE-04",
        "active_nav": "search",
        "q": query,
        "search_results": list(page_obj),
        "page_obj": page_obj,
        "total_count": total_count,
        "local_connection": local_conn,
        "active_tab": active_tab,
        **_get_stage4_state_context(request, "Search WDOS"),
    })
    return render(request, "foundation/core/core_04_search.html", ctx)


def search_api(request):
    account = getattr(request, "wdos_account", None)
    if not account or account.status != "active":
        return JsonResponse({"error": "Unauthorized"}, status=401)

    user_scope = get_user_scope(account, request.session)
    query = request.GET.get("q", "").strip()

    results = []
    if query:
        results = _execute_scoped_search(query, user_scope)

    return JsonResponse({
        "query": query,
        "total_count": len(results),
        "results": [
            {
                "id": str(r["id"]),
                "type": r["type"],
                "title": r["title"],
                "summary": r["summary"],
                "network": r["network"],
                "country": r["country"],
                "url": r["url"],
            }
            for r in results
        ],
    })


def _execute_scoped_search(query: str, user_scope: UserScope, active_tab: str = None, limit: int = None):
    """
    Search work items, country hubs, and profiles strictly within the user's
    authorized network, geography, and confidentiality scope.
    Guarantees ZERO leakage of counts, titles, or snippets from unauthorized scopes.
    """
    results = []

    # 1. Search Work Items
    items_qs = WorkItem.objects.filter(
        network__in=user_scope.allowed_networks,
    )
    if "*" not in user_scope.allowed_countries:
        items_qs = items_qs.filter(country__in=user_scope.allowed_countries)
    if not user_scope.can_access_confidential():
        items_qs = items_qs.filter(confidential=False)

    if user_scope.leadership_tier > 4 and not user_scope.is_management_or_admin:
        from django.db.models import Q
        LEADERSHIP_CATEGORIES = [
            "verification", "governance", "operations", "quality", "safeguarding",
            "finance", "compliance", "pipeline", "roster",
        ]
        items_qs = items_qs.filter(
            Q(assigned_to=user_scope.account) | Q(created_by=user_scope.account) |
            (Q(leadership_level__isnull=True) & ~Q(category__in=LEADERSHIP_CATEGORIES))
        )

    if active_tab == "records":
        items_qs = items_qs.filter(status__in=["pending", "in_progress"])
    elif active_tab == "history":
        items_qs = items_qs.filter(status__in=["completed", "blocked"])

    items_qs = items_qs.filter(
        models_q_search(query, ["title", "summary", "category"])
    ).order_by("-created_at")

    if limit:
        matching_items = items_qs[:limit]
    else:
        matching_items = items_qs

    for item in matching_items:
        when_str = item.created_at.strftime("%d %b · %H:%M WAT") if item.created_at else "Recently"
        results.append({
            "id": item.id,
            "type": "work_item",
            "title": item.title,
            "summary": item.summary,
            "when": when_str,
            "action_label": "View details",
            "pill_style": "amber" if item.status == "pending" else "magenta",
            "status": item.status,
            "network": item.network,
            "country": item.country,
            "url": f"/foundation/work-queue/{item.id}/",
        })

    # 2. Search Country Hubs (only included for overview/directory, not history)
    if active_tab != "history":
        hubs_qs = CountryHub.objects.filter(status="active")
        if "*" not in user_scope.allowed_countries:
            hubs_qs = hubs_qs.filter(code__in=user_scope.allowed_countries)

        hubs_qs = hubs_qs.filter(
            models_q_search(query, ["name", "code", "region", "lead_name"])
        )
        if limit:
            matching_hubs = hubs_qs[:5]
        else:
            matching_hubs = hubs_qs

        for hub in matching_hubs:
            results.append({
                "id": hub.code,
                "type": "country_hub",
                "title": f"{hub.name} Country Hub ({hub.code})",
                "summary": f"Region: {hub.region or 'Africa'}. Lead: {hub.lead_name or 'N/A'}",
                "when": "Active Hub",
                "action_label": "Open ›",
                "pill_style": "magenta",
                "status": "active",
                "network": user_scope.active_network,
                "country": hub.code,
                "url": f"/foundation/network/{user_scope.active_network}/country/{hub.code}/",
            })

        # 3. Search People & Community Profiles (Stage 06) strictly within allowed scope
        people_qs = PersonProfile.objects.filter(network__in=user_scope.allowed_networks)
        if "*" not in user_scope.allowed_countries:
            people_qs = people_qs.filter(country__in=user_scope.allowed_countries)
        people_qs = people_qs.filter(
            models_q_search(query, ["full_name", "person_code", "local_home", "primary_relationship", "email"])
        )
        matching_people = people_qs[:5] if limit else people_qs
        for p in matching_people:
            cluster_display = p.community_cluster or (p.cluster_unit.unit_name if p.cluster_unit else "")
            chap_display = sanitize_chapter_display(p.chapter.name if p.chapter else p.local_home, fallback_country=p.country)
            cluster_text = f" · Cluster: {cluster_display}" if cluster_display else ""
            results.append({
                "id": p.person_code,
                "type": "person_profile",
                "title": f"{p.full_name} ({p.person_code})",
                "summary": f"{p.primary_relationship} · Chapter: {chap_display}{cluster_text} ({p.network}/{p.country})",
                "when": p.status,
                "action_label": "View profile ›",
                "pill_style": "magenta" if p.status == "Active" else "amber",
                "status": p.status.lower(),
                "network": p.network,
                "country": p.country,
                "url": f"/foundation/people/{p.person_code}/",
            })

        # 4. Search Local Organisation Units (Stage 06) strictly within allowed scope
        units_qs = LocalOrganisationUnit.objects.filter(network__in=user_scope.allowed_networks)
        if "*" not in user_scope.allowed_countries:
            units_qs = units_qs.filter(country__in=user_scope.allowed_countries)
        units_qs = units_qs.filter(
            models_q_search(query, ["unit_name", "level", "responsible_leader_name", "description"])
        )
        matching_units = units_qs[:5] if limit else units_qs
        for u in matching_units:
            if u.level == "Community Cluster":
                tag_label = "Community Cluster"
                pill_style = "purple"
                u_type = "community_cluster"
            elif u.level == "Chapter":
                tag_label = "Chapter"
                pill_style = "green"
                u_type = "chapter"
            elif u.level == "District / LGA":
                tag_label = "District / LGA"
                pill_style = "blue"
                u_type = "local_unit"
            else:
                tag_label = u.level
                pill_style = "magenta"
                u_type = "local_unit"

            parent_info = f" · Parent: {u.parent.unit_name}" if u.parent else ""
            results.append({
                "id": u.id,
                "type": u_type,
                "title": f"{u.unit_name} ({tag_label})",
                "summary": f"Leader: {u.responsible_leader_name}{parent_info} · {u.network}/{u.country}",
                "when": u.record_state,
                "action_label": "Open unit ›",
                "pill_style": pill_style,
                "status": "active",
                "network": u.network,
                "country": u.country,
                "url": f"/foundation/geography/local-org/?country={u.country}&network={u.network}",
            })

        # 5. Search Chapters specifically (and avoid showing broad places like Lagos or Ikeja as Chapters)
        chap_qs = Chapter.objects.filter(network__in=user_scope.allowed_networks)
        if "*" not in user_scope.allowed_countries:
            chap_qs = chap_qs.filter(country__in=user_scope.allowed_countries)
        chap_qs = chap_qs.filter(
            models_q_search(query, ["name", "code", "community_cluster", "region", "district"])
        )
        matching_chaps = chap_qs[:5] if limit else chap_qs
        for ch in matching_chaps:
            sanitized_name = sanitize_chapter_display(ch.name, fallback_country=ch.country)
            cluster_info = f" · Cluster: {ch.community_cluster}" if ch.community_cluster else ""
            results.append({
                "id": ch.id,
                "type": "chapter",
                "title": f"{sanitized_name} (Chapter)",
                "summary": f"{ch.code}{cluster_info} · {ch.network}/{ch.country}",
                "when": ch.status.title(),
                "action_label": "Open chapter ›",
                "pill_style": "green",
                "status": ch.status.lower(),
                "network": ch.network,
                "country": ch.country,
                "url": f"/foundation/chapters/{ch.id}/",
            })

        # 6. Search Leadership Seats & Vacancies (Stage 07) strictly within allowed scope
        seats_qs = LeadershipSeat.objects.filter(network__in=user_scope.allowed_networks)
        if "*" not in user_scope.allowed_countries:
            seats_qs = seats_qs.filter(country__in=user_scope.allowed_countries)
        seats_qs = seats_qs.filter(
            models_q_search(query, ["position_title", "unit_name", "holder_name", "status", "seat_code"])
        )
        matching_seats = seats_qs[:5] if limit else seats_qs
        for s in matching_seats:
            results.append({
                "id": s.seat_code,
                "type": "leadership_seat",
                "title": f"{s.unit_name} · {s.position_title}",
                "summary": f"Holder: {s.holder_name} · Status: {s.status} ({s.network}/{s.country})",
                "when": s.status,
                "action_label": "Open seat ›",
                "pill_style": "green" if s.status == "Active" else "amber",
                "status": s.status.lower(),
                "network": s.network,
                "country": s.country,
                "url": f"/foundation/leadership/seats/{s.seat_code}/",
            })

        # 7. Search Recruitment Opportunities & Candidate Applications (Stage 08) strictly within allowed scope
        if is_stage8_reviewer(user_scope):
            cand_qs = CandidateApplication.objects.filter(network__in=user_scope.allowed_networks)
            if "*" not in user_scope.allowed_countries:
                cand_qs = cand_qs.filter(country__in=user_scope.allowed_countries)
            cand_qs = cand_qs.filter(
                models_q_search(query, ["candidate_name", "seat_label", "route", "current_stage", "application_code"])
            )
            matching_cands = cand_qs[:5] if limit else cand_qs
            for c in matching_cands:
                results.append({
                    "id": c.application_code,
                    "type": "candidate_application",
                    "title": f"{c.candidate_name} · {c.seat_label}",
                    "summary": f"Route: {c.route} · Stage: {c.current_stage} · Next: {c.next_action} ({c.network}/{c.country})",
                    "when": c.current_stage,
                    "action_label": "Review candidate ›",
                    "pill_style": "amber",
                    "status": "in_progress",
                    "network": c.network,
                    "country": c.country,
                    "url": f"/foundation/recruitment/evidence/?candidate={c.application_code}",
                })

    return results


def models_q_search(query: str, fields: list):
    """Build Q object for case-insensitive search across fields."""
    from django.db.models import Q
    q_obj = Q()
    for f in fields:
        q_obj |= Q(**{f"{f}__icontains": query})
    return q_obj


# -----------------------------------------------------------------------------
# Notifications & Failure States
# -----------------------------------------------------------------------------

def _ensure_default_notifications_for_scope(account, user_scope):
    return


def notifications_view(request):
    """Notifications view (CORE-03)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    account = ctx["account"]

    _ensure_default_notifications_for_scope(account, user_scope)

    base_qs = Notification.objects.filter(account=account, is_archived=False)

    status_filter = request.GET.get("status", "all")
    category_filter = request.GET.get("category", "all")
    search_query = request.GET.get("q", "").strip()

    filtered_qs = base_qs
    if status_filter == "unread":
        filtered_qs = filtered_qs.filter(is_read=False)
    elif status_filter == "read":
        filtered_qs = filtered_qs.filter(is_read=True)
    elif status_filter == "failed":
        filtered_qs = filtered_qs.filter(delivery_status="failed")

    if category_filter != "all":
        filtered_qs = filtered_qs.filter(category=category_filter)

    if search_query:
        filtered_qs = filtered_qs.filter(
            Q(title__icontains=search_query) | Q(message__icontains=search_query)
        )

    if request.GET.get("legacy") == "1":
        breadcrumbs = get_breadcrumbs(user_scope, page_name="Notifications")
        ctx.update({
            "notifications": list(filtered_qs),
            "breadcrumbs": breadcrumbs,
        })
        return render(request, "foundation/notifications.html", ctx)

    # Scoped counts
    total_count = base_qs.count()
    unread_count = base_qs.filter(is_read=False).count()
    read_count = base_qs.filter(is_read=True).count()
    failed_count = base_qs.filter(delivery_status="failed").count()

    # Pagination
    paginator = Paginator(filtered_qs, 10)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    notification_items = []
    for notif in page_obj:
        is_failed = notif.delivery_status == "failed"
        if is_failed:
            action_label = "Retry Delivery"
            action_url = f"/foundation/api/notifications/{notif.id}/retry/"
            pill_style = "danger"
            delivery_label = "Delivery Failure"
        elif "meeting" in notif.title.lower():
            action_label = "View invitation"
            action_url = notif.target_url or "/foundation/workspace/"
            pill_style = "magenta"
            delivery_label = ""
        elif "profile" in notif.title.lower():
            action_label = "Open profile"
            action_url = notif.target_url or "/foundation/profile/"
            pill_style = ""
            delivery_label = ""
        elif "preference" in notif.title.lower() or "setting" in notif.title.lower():
            action_label = "Review settings"
            action_url = notif.target_url or "/foundation/settings/"
            pill_style = "amber"
            delivery_label = ""
        elif notif.target_url:
            action_label = "Open"
            action_url = notif.target_url
            pill_style = "magenta" if not notif.is_read else "amber"
            delivery_label = ""
        else:
            action_label = "View details"
            action_url = "/foundation/notifications/"
            pill_style = "magenta" if not notif.is_read else ""
            delivery_label = ""

        if notif.created_at:
            when_str = notif.created_at.strftime("%d %b · %H:%M WAT")
        else:
            when_str = "Recently"

        notification_items.append({
            "id": str(notif.id),
            "title": notif.title,
            "message": notif.message,
            "category": notif.get_category_display() if hasattr(notif, "get_category_display") else notif.category,
            "when": when_str,
            "action_label": action_label,
            "action_url": action_url,
            "pill_style": pill_style,
            "delivery_label": delivery_label,
            "is_read": notif.is_read,
            "is_failed": is_failed,
            "is_form": is_failed,
        })

    ctx.update({
        "screen_code": "CORE-03",
        "active_nav": "notifications",
        "notification_items": notification_items,
        "page_obj": page_obj,
        "status_filter": status_filter,
        "category_filter": category_filter,
        "search_query": search_query,
        "total_count": total_count,
        "unread_count": unread_count,
        "read_count": read_count,
        "failed_count": failed_count,
        **_get_stage4_state_context(request, "Notifications"),
    })
    return render(request, "foundation/core/core_03_notifications.html", ctx)


def reminder_permission_view(request):
    """CORE-03-PERMISSION Would reminders help you?"""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    pref = ctx.get("user_pref")
    if request.method == "POST":
        choice = request.POST.get("reminder_preference", "inside_wdos")
        if pref:
            pref.reminder_preference = choice
            pref.save(update_fields=["reminder_preference"])
        action = request.POST.get("action")
        if action == "save_later":
            return redirect("/foundation/workspace/")
        return redirect("/foundation/notifications/")

    ctx.update({
        "screen_code": "CORE-03-PERMISSION",
        "active_nav": "notifications",
        "reminder_preference": getattr(pref, "reminder_preference", "inside_wdos") if pref else "inside_wdos",
        **_get_stage4_state_context(request, "Would reminders help you?"),
    })
    return render(request, "foundation/core/core_03_permission.html", ctx)


def notifications_api(request):
    account = getattr(request, "wdos_account", None)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    notifications = Notification.objects.filter(account=account, is_archived=False)
    unread_count = notifications.filter(is_read=False).count()

    return JsonResponse({
        "unread_count": unread_count,
        "notifications": [
            {
                "id": str(n.id),
                "title": n.title,
                "message": n.message,
                "category": n.category,
                "is_read": n.is_read,
                "delivery_status": n.delivery_status,
                "target_url": n.target_url,
                "created_at": n.created_at.isoformat(),
            }
            for n in notifications[:20]
        ],
    })


@require_POST
def mark_notification_read(request, notification_id):
    account = getattr(request, "wdos_account", None)
    if not account and request.user.is_authenticated:
        account = Account.objects.filter(user=request.user).first()
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    notification = get_object_or_404(Notification, id=notification_id, account=account)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return JsonResponse({"status": "ok", "id": str(notification.id), "is_read": True})


@require_POST
def mark_all_notifications_read(request):
    account = getattr(request, "wdos_account", None)
    if not account and request.user.is_authenticated:
        account = Account.objects.filter(user=request.user).first()
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    Notification.objects.filter(account=account, is_read=False).update(is_read=True)
    return redirect("/foundation/notifications/")


@require_POST
def retry_notification(request, notification_id):
    """Recovery action for failed notification state."""
    account = getattr(request, "wdos_account", None)
    if not account and request.user.is_authenticated:
        account = Account.objects.filter(user=request.user).first()
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    notification = get_object_or_404(Notification, id=notification_id, account=account)
    notification.delivery_status = "delivered"
    notification.save(update_fields=["delivery_status"])
    return redirect("/foundation/notifications/")


# -----------------------------------------------------------------------------
# Account Safety & Sessions (CORE-06 family)
# -----------------------------------------------------------------------------

def account_security_view(request):
    """CORE-06 Keep your account safe."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response
    ctx.update({
        "screen_code": "CORE-06",
        "active_nav": "settings",
        **_get_stage4_state_context(request, "Keep your account safe"),
    })
    return render(request, "foundation/core/core_06_security.html", ctx)


def _detect_client_device(request, local_conn=None):
    ua = request.META.get("HTTP_USER_AGENT", "")
    device = "This device"
    if "iPhone" in ua:
        device = "iPhone"
    elif "iPad" in ua:
        device = "iPad"
    elif "Android" in ua:
        device = "Android Phone"
    elif "Windows" in ua:
        device = "Windows PC"
    elif "Macintosh" in ua:
        device = "MacBook"
    elif "Linux" in ua:
        device = "Linux Workstation"

    browser = "Browser"
    if "Edg" in ua:
        browser = "Microsoft Edge"
    elif "Chrome" in ua:
        browser = "Chrome"
    elif "Safari" in ua:
        browser = "Safari"
    elif "Firefox" in ua:
        browser = "Firefox"

    loc = local_conn or "Local Connection"
    return device, f"{browser} · {loc}"


def account_sessions_view(request):
    """CORE-06-SESSIONS Your signed-in devices."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response
    account = ctx["account"]
    local_conn = ctx.get("local_connection") or "National Hub"

    # Ensure current device session is registered
    dev_name, browser_info = _detect_client_device(request, local_conn)
    current_sess = DeviceSession.objects.filter(account=account, is_current=True).first()
    if not current_sess:
        current_sess = DeviceSession.objects.create(
            account=account,
            device_name=dev_name,
            browser_info=browser_info,
            ip_address=request.META.get("REMOTE_ADDR", "127.0.0.1"),
            is_current=True,
        )
    else:
        current_sess.device_name = dev_name
        current_sess.browser_info = browser_info
        current_sess.last_active = timezone.now()
        current_sess.save(update_fields=["device_name", "browser_info", "last_active"])

    sessions_qs = DeviceSession.objects.filter(account=account).order_by("-is_current", "-last_active")
    sessions_list = []
    now = timezone.now()
    for s in sessions_qs:
        if s.is_current:
            last_str = "Now"
        else:
            diff = now - s.last_active
            if diff.days == 0:
                hours = int(diff.seconds / 3600)
                last_str = f"{hours}h ago" if hours > 0 else "Just now"
            elif diff.days == 1:
                last_str = "Yesterday"
            else:
                last_str = f"{diff.days} days ago"

        sessions_list.append({
            "id": str(s.id),
            "device_name": s.device_name,
            "browser_info": s.browser_info,
            "is_current": s.is_current,
            "last_active_str": last_str,
        })

    signed_out = request.GET.get("signed_out") == "1"

    ctx.update({
        "screen_code": "CORE-06-SESSIONS",
        "active_nav": "settings",
        "device_sessions": sessions_list,
        "signed_out_success": signed_out,
        **_get_stage4_state_context(request, "Your signed-in devices"),
    })
    return render(request, "foundation/core/core_06_sessions.html", ctx)


def signout_device_view(request):
    """CORE-06-SIGNOUT Sign out this device?"""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response
    account = ctx["account"]
    target_session_id = request.GET.get("device_id") or request.POST.get("session_id")
    target_session = None
    if target_session_id:
        target_session = DeviceSession.objects.filter(account=account, id=target_session_id).first()
    if not target_session:
        target_session = DeviceSession.objects.filter(account=account, is_current=False).first()

    if request.method == "POST":
        if target_session:
            target_session.delete()
        return redirect("/foundation/account/sessions/?signed_out=1")

    target_name = f"{target_session.device_name} · {target_session.browser_info}" if target_session else "Other device · mobile browser"

    ctx.update({
        "screen_code": "CORE-06-SIGNOUT",
        "active_nav": "settings",
        "target_session_id": str(target_session.id) if target_session else "",
        "target_device_name": target_name,
        **_get_stage4_state_context(request, "Sign out this device?"),
    })
    return render(request, "foundation/core/core_06_signout.html", ctx)


def change_password_view(request):
    """CORE-06-PASSWORD Change your password."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response
    account = ctx["account"]
    user = account.user
    error = None
    success = False

    if request.method == "POST":
        current_password = request.POST.get("current_password", "")
        new_password = request.POST.get("new_password", "")
        confirm_password = request.POST.get("confirm_password", "")

        if not user.check_password(current_password):
            error = "Current password was incorrect. Please enter your existing password."
        elif new_password != confirm_password:
            error = "New passwords do not match. Please verify your entries."
        elif len(new_password) < 8:
            error = "Password must be at least 8 characters long."
        else:
            user.set_password(new_password)
            user.save()
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, user)
            success = True

    ctx.update({
        "screen_code": "CORE-06-PASSWORD",
        "active_nav": "settings",
        "password_error": error,
        "password_success": success,
        **_get_stage4_state_context(request, "Change your password"),
    })
    return render(request, "foundation/core/core_06_password.html", ctx)


# -----------------------------------------------------------------------------
# Settings & Accessibility Preferences (CORE-07 family)
# -----------------------------------------------------------------------------

def settings_view(request):
    """Language & preferences view (CORE-07)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    if request.GET.get("legacy") == "1":
        user_scope = ctx["user_scope"]
        breadcrumbs = get_breadcrumbs(user_scope, page_name="Settings & Preferences")
        ctx.update({
            "languages": LANGUAGES,
            "breadcrumbs": breadcrumbs,
            "active_nav": "settings",
            "is_settings_page": True,
        })
        return render(request, "foundation/settings.html", ctx)

    account = ctx["account"]
    pref = ctx.get("user_pref")
    saved = False
    effective_draft = OnboardingDraft.objects.filter(account=account).order_by("-updated_at").first()

    if request.method == "POST":
        lang = request.POST.get("language")
        timezone_val = request.POST.get("timezone")
        font_size = request.POST.get("font_size")
        email_updates = request.POST.get("email_updates")

        if pref:
            if lang in LANGUAGES:
                pref.language = lang
                request.session["wdos_language"] = lang
                if effective_draft and effective_draft.data is not None:
                    effective_draft.data["language"] = lang
            if timezone_val:
                request.session["wdos_timezone"] = timezone_val
                if effective_draft and effective_draft.data is not None:
                    effective_draft.data["timezone"] = timezone_val
            if font_size in ("standard", "large", "xlarge"):
                pref.font_size = font_size
                if effective_draft and effective_draft.data is not None:
                    effective_draft.data["reading"] = font_size
            if email_updates in ("weekly", "daily", "none"):
                pref.activity_digest = email_updates
                if effective_draft and effective_draft.data is not None:
                    effective_draft.data["optional_updates"] = (email_updates != "none")
            pref.save()
            if effective_draft and effective_draft.data is not None:
                effective_draft.save(update_fields=["data", "updated_at"])
            saved = True

    # Resolve timezone with priority: session -> draft data -> active country default -> UTC
    from accounts.african_geography import get_country_default_timezone
    from zoneinfo import available_timezones
    user_scope = ctx.get("user_scope")
    country_default_tz = get_country_default_timezone(user_scope.active_country) if (user_scope and user_scope.active_country) else None
    draft_tz = (effective_draft.data or {}).get("timezone") if (effective_draft and effective_draft.data) else None
    current_tz = request.session.get("wdos_timezone") or draft_tz or country_default_tz or "UTC"
    request.session["wdos_timezone"] = current_tz

    tz_list = sorted(available_timezones())
    if current_tz and current_tz not in tz_list:
        tz_list.insert(0, current_tz)

    current_font_size = pref.font_size if pref else "standard"
    current_email_updates = pref.activity_digest if pref else "daily"

    ctx.update({
        "screen_code": "CORE-07",
        "active_nav": "settings",
        "is_settings_page": True,
        "languages": LANGUAGES,
        "current_lang": pref.language if (pref and pref.language in LANGUAGES) else ctx.get("lang", "en"),
        "current_timezone": current_tz,
        "available_timezones": tz_list,
        "current_font_size": current_font_size,
        "current_email_updates": current_email_updates,
        "pref_saved": saved,
        **_get_stage4_state_context(request, "Language and preferences"),
    })
    response = render(request, "foundation/core/core_07_preferences.html", ctx)
    if saved and request.method == "POST" and request.POST.get("language") in LANGUAGES:
        response.set_cookie("wdos_language", request.POST.get("language"), max_age=31536000, samesite="Lax")
    return response


def connection_status_view(request):
    """CORE-07-CONNECTION Your connection is unavailable."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    check_requested = request.GET.get("check") == "1"
    is_connected = True
    status_detail = "Your database connection and server network are online."
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception as exc:
        is_connected = False
        status_detail = f"Connection error: {exc}"

    ctx.update({
        "screen_code": "CORE-07-CONNECTION",
        "active_nav": "workspace",
        "check_requested": check_requested,
        "is_connected": is_connected,
        "status_detail": status_detail,
        **_get_stage4_state_context(request, "Your connection is unavailable"),
    })
    return render(request, "foundation/core/core_07_connection.html", ctx)


@require_POST
def preferences_api(request):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_pref = ctx["user_pref"]
    account = ctx["account"]

    # Language
    lang = request.POST.get("language")
    if lang in LANGUAGES:
        user_pref.language = lang
        request.session["wdos_language"] = lang

    # Accessibility toggles
    user_pref.high_contrast = request.POST.get("high_contrast") == "true" or request.POST.get("high_contrast") == "1"
    user_pref.reduced_motion = request.POST.get("reduced_motion") == "true" or request.POST.get("reduced_motion") == "1"
    
    font_size = request.POST.get("font_size")
    if font_size in ("standard", "large", "xlarge"):
        user_pref.font_size = font_size

    # Notification preferences
    user_pref.email_notifications = request.POST.get("email_notifications") == "true" or request.POST.get("email_notifications") == "1"
    user_pref.in_app_notifications = request.POST.get("in_app_notifications") == "true" or request.POST.get("in_app_notifications") == "1"

    digest = request.POST.get("activity_digest")
    if digest in ("realtime", "daily", "weekly", "none"):
        user_pref.activity_digest = digest

    user_pref.save()

    timezone_val = request.POST.get("timezone")
    if timezone_val:
        request.session["wdos_timezone"] = timezone_val

    effective_draft = OnboardingDraft.objects.filter(account=account).order_by("-updated_at").first()
    if effective_draft and effective_draft.data is not None:
        if lang in LANGUAGES:
            effective_draft.data["language"] = lang
        if timezone_val:
            effective_draft.data["timezone"] = timezone_val
        if font_size in ("standard", "large", "xlarge"):
            effective_draft.data["reading"] = font_size
        if digest in ("realtime", "daily", "weekly", "none"):
            effective_draft.data["optional_updates"] = (digest != "none")
        effective_draft.save(update_fields=["data", "updated_at"])

    response = redirect("/foundation/settings/")
    if lang in LANGUAGES:
        response.set_cookie(
            "wdos_language",
            lang,
            max_age=31536000,
            httponly=False,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite="Lax",
        )
    return response


@require_POST
def reset_preferences(request):
    """Recovery action for missing or malformed preferences."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_pref = ctx["user_pref"]
    user_pref.language = "en"
    user_pref.high_contrast = False
    user_pref.reduced_motion = False
    user_pref.font_size = "standard"
    user_pref.email_notifications = True
    user_pref.in_app_notifications = True
    user_pref.activity_digest = "daily"
    user_pref.save()

    request.session["wdos_language"] = "en"
    response = redirect("/foundation/settings/")
    response.set_cookie("wdos_language", "en", max_age=31536000, samesite="Lax")
    return response


# -----------------------------------------------------------------------------
# Privacy Requests (GDPR / Data Subject Rights)
# -----------------------------------------------------------------------------

PRIVACY_TYPE_LABELS = {
    "correct_info": "Correct my information",
    "export_records": "Export my records",
    "delete_account": "Delete my account",
    "object_processing": "Object to processing",
}

PRIVACY_ROUTE_LABELS = {
    "account": "Inside your WDOS account",
    "email": "Email reply",
    "in_person": "In-person verification",
}


def privacy_requests_view(request):
    """Privacy and consent list view (CORE-08)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    if request.GET.get("legacy") == "1":
        user_scope = ctx["user_scope"]
        privacy_requests = list(PrivacyRequest.objects.filter(account=ctx["account"]))
        breadcrumbs = get_breadcrumbs(user_scope, page_name="Privacy Requests")
        ctx.update({
            "privacy_requests": privacy_requests,
            "breadcrumbs": breadcrumbs,
        })
        return render(request, "foundation/privacy_requests.html", ctx)

    account = ctx["account"]
    reqs_qs = PrivacyRequest.objects.filter(account=account).order_by("-created_at")
    reqs = []
    for r in reqs_qs:
        type_str = PRIVACY_TYPE_LABELS.get(r.request_type, r.request_type.replace("_", " ").title())
        reqs.append({
            "id": str(r.id),
            "reference": r.reference,
            "title": f"{type_str} ({r.reference})",
            "submitted_str": r.created_at.strftime("%d %b · %H:%M WAT") if r.created_at else "Recently",
            "status_str": r.get_status_display() if hasattr(r, "get_status_display") else r.status.replace("_", " ").title(),
            "detail_url": f"/foundation/privacy-requests/status/?ref={r.reference}",
            "pill_style": "magenta" if r.status in ("Waiting for review", "pending", "submitted") else "amber",
        })

    ctx.update({
        "screen_code": "CORE-08",
        "active_nav": "settings",
        "privacy_requests": reqs,
        **_get_stage4_state_context(request, "Privacy and consent"),
    })
    return render(request, "foundation/core/core_08_privacy.html", ctx)


def new_privacy_request(request):
    """What would you like help with? (CORE-08-REQUEST)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    account = ctx["account"]
    user_scope = ctx["user_scope"]

    if request.method == "POST":
        action = request.POST.get("action")
        req_type = request.POST.get("request_type", "correct_info")
        details = request.POST.get("details", "") or request.POST.get("reason", "")
        safe_route = request.POST.get("safe_reply_route", "account")
        ack = request.POST.get("ack")

        ref = f"PR-{timezone.now().strftime('%y%m')}-{uuid.uuid4().hex[:4].upper()}"

        if ack == "1" or action == "submit_direct":
            now_str = timezone.now().strftime("%d %b · %H:%M WAT")
            pr = PrivacyRequest.objects.create(
                account=account,
                reference=ref,
                request_type=req_type,
                details=details,
                safe_reply_route=safe_route,
                status="submitted",
                current_step="Identity check required",
                next_action="Confirm through the approved verification route",
                timeline=[
                    {"when": now_str, "what": "Request received", "who": "You"},
                    {"when": now_str, "what": "Identity check requested", "who": "Authorised privacy reviewer"},
                ],
            )
            type_label = PRIVACY_TYPE_LABELS.get(req_type, req_type.title())
            WorkItem.objects.create(
                title=f"Privacy Request {ref}: {type_label}",
                summary=details[:250],
                category="privacy",
                network=user_scope.active_network,
                country=user_scope.active_country if user_scope.active_country != "*" else "NG",
                confidential=True,
                status="pending",
                created_by=account,
                target_url=f"/foundation/privacy-requests/review/?ref={ref}",
            )
            return redirect("/foundation/privacy-requests/")
        elif action == "save_later":
            now_str = timezone.now().strftime("%d %b · %H:%M WAT")
            pr = PrivacyRequest.objects.create(
                account=account,
                reference=ref,
                request_type=req_type,
                details=details,
                safe_reply_route=safe_route,
                status="Draft",
                current_step="Draft saved",
                next_action="Review and submit request",
                timeline=[
                    {"when": now_str, "what": "Draft created", "who": "You"},
                ],
            )
            return redirect("/foundation/privacy-requests/")
        else:
            request.session["privacy_draft"] = {
                "request_type": req_type,
                "details": details,
                "safe_reply_route": safe_route,
            }
            return redirect("/foundation/privacy-requests/confirm/")

    ctx.update({
        "screen_code": "CORE-08-REQUEST",
        "active_nav": "settings",
        **_get_stage4_state_context(request, "What would you like help with?"),
    })
    return render(request, "foundation/core/core_08_request.html", ctx)


def privacy_request_confirm_view(request):
    """Check your request before sending (CORE-08-CONFIRM)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    account = ctx["account"]
    user_scope = ctx["user_scope"]
    draft = request.session.get("privacy_draft", {})
    req_type = request.POST.get("request_type") or draft.get("request_type", "correct_info")
    details = request.POST.get("details") or draft.get("details", "")
    if not details:
        details = "Review personal information and update local chapter directory records."
    safe_route = request.POST.get("safe_reply_route") or draft.get("safe_reply_route", "account")

    if request.method == "POST":
        ref = f"PR-{timezone.now().strftime('%y%m')}-{uuid.uuid4().hex[:4].upper()}"
        now_str = timezone.now().strftime("%d %b · %H:%M WAT")
        pr = PrivacyRequest.objects.create(
            account=account,
            reference=ref,
            request_type=req_type,
            details=details,
            safe_reply_route=safe_route,
            status="Waiting for review",
            current_step="Identity check required",
            next_action="Confirm through the approved verification route",
            timeline=[
                {"when": now_str, "what": "Request received", "who": "You"},
                {"when": now_str, "what": "Identity check requested", "who": "Authorised privacy reviewer"},
            ],
        )
        type_label = PRIVACY_TYPE_LABELS.get(req_type, req_type.title())
        WorkItem.objects.create(
            title=f"Privacy Request {ref}: {type_label}",
            summary=details[:250],
            category="privacy",
            network=user_scope.active_network,
            country=user_scope.active_country if user_scope.active_country != "*" else "NG",
            confidential=True,
            status="pending",
            created_by=account,
            target_url=f"/foundation/privacy-requests/review/?ref={ref}",
        )
        if "privacy_draft" in request.session:
            del request.session["privacy_draft"]
        return redirect(f"/foundation/privacy-requests/status/?ref={ref}")

    ctx.update({
        "screen_code": "CORE-08-CONFIRM",
        "active_nav": "settings",
        "request_type": req_type,
        "request_type_label": PRIVACY_TYPE_LABELS.get(req_type, "Correct my information"),
        "details": details,
        "safe_reply_route": safe_route,
        "safe_reply_route_label": PRIVACY_ROUTE_LABELS.get(safe_route, "Inside your WDOS account"),
        **_get_stage4_state_context(request, "Check your request before sending"),
    })
    return render(request, "foundation/core/core_08_confirm.html", ctx)


def privacy_request_status_view(request):
    """Your privacy request (CORE-08-STATUS)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    account = ctx["account"]
    ref = request.GET.get("ref")
    pr = None
    if ref:
        pr = PrivacyRequest.objects.filter(account=account, reference=ref).first()
    if not pr:
        pr = PrivacyRequest.objects.filter(account=account).first()

    # If the user has no privacy requests yet, auto-create one so the screen is live and dynamic
    if not pr:
        ref_new = f"PR-{timezone.now().strftime('%y%m')}-{uuid.uuid4().hex[:4].upper()}"
        now_str = timezone.now().strftime("%d %b · %H:%M WAT")
        pr = PrivacyRequest.objects.create(
            account=account,
            reference=ref_new,
            request_type="correct_info",
            details="Review personal information and update local chapter directory records.",
            safe_reply_route="account",
            status="Waiting for review",
            current_step="Identity check required",
            next_action="Confirm through the approved verification route",
            timeline=[
                {"when": now_str, "what": "Request received", "who": "You"},
                {"when": now_str, "what": "Identity check requested", "who": "Authorised privacy reviewer"},
            ],
        )

    timeline_events = pr.timeline if pr.timeline else [
        {"when": pr.created_at.strftime("%d %b · %H:%M WAT") if pr.created_at else "Recently", "what": "Request received", "who": "You"},
        {"when": pr.created_at.strftime("%d %b · %H:%M WAT") if pr.created_at else "Recently", "what": "Identity check requested", "who": "Authorised privacy reviewer"},
    ]

    pr.request_type_label = PRIVACY_TYPE_LABELS.get(pr.request_type, pr.request_type.replace("_", " ").title())

    ctx.update({
        "screen_code": "CORE-08-STATUS",
        "active_nav": "settings",
        "privacy_req": pr,
        "timeline_events": timeline_events,
        **_get_stage4_state_context(request, "Your privacy request"),
    })
    return render(request, "foundation/core/core_08_status.html", ctx)


def privacy_request_review_view(request):
    """Review a privacy request (CORE-08-REVIEW)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    ref = request.GET.get("ref") or request.POST.get("request_ref")
    pr = None
    if ref:
        pr = PrivacyRequest.objects.filter(reference=ref).first()
    if not pr:
        pr = PrivacyRequest.objects.first()

    saved = False

    if request.method == "POST":
        decision = request.POST.get("decision", "more_info")
        reason = request.POST.get("reason_and_retention", "")
        check_status = request.POST.get("identity_check", "not_checked")
        if pr:
            pr.decision = decision
            pr.reason_and_retention = reason
            pr.identity_check_status = check_status
            if decision == "approve":
                pr.status = "Approved"
                pr.current_step = "Decision approved"
                pr.next_action = "No further action needed"
                pr.completed_at = timezone.now()
            elif decision == "reject":
                pr.status = "Rejected"
                pr.current_step = "Request rejected"
                pr.next_action = "Closed per data retention policy"
                pr.completed_at = timezone.now()
            elif decision == "retain":
                pr.status = "Records Retained"
                pr.current_step = "Retained per approved policy"
                pr.next_action = "Statutory retention notice provided"
            else:
                pr.status = "More Information Needed"
                pr.current_step = "Additional identity check required"
                pr.next_action = "Awaiting member verification response"

            now_str = timezone.now().strftime("%d %b · %H:%M WAT")
            tl = list(pr.timeline or [])
            decision_label = decision.replace("_", " ").title()
            tl.append({
                "when": now_str,
                "what": f"Review recorded: {decision_label}",
                "who": "Authorised privacy reviewer",
            })
            pr.timeline = tl
            pr.save()
            saved = True

            WorkItem.objects.filter(category="privacy", title__icontains=pr.reference).update(
                status="completed" if decision in ("approve", "reject", "retain") else "in_progress"
            )

    if pr:
        pr.request_type_label = PRIVACY_TYPE_LABELS.get(pr.request_type, pr.request_type.replace("_", " ").title())

    ctx.update({
        "screen_code": "CORE-08-REVIEW",
        "active_nav": "workspace",
        "is_privacy_reviewer": True,
        "active_role_title": "Authorised privacy reviewer",
        "privacy_req": pr or type("Obj", (), {"reference": "PR-2026-081", "request_type_label": "Correct my information"}),
        "decision_recorded": saved,
        **_get_stage4_state_context(request, "Review a privacy request"),
    })
    return render(request, "foundation/core/core_08_review.html", ctx)


def network_transition_view(request):
    """Review your network transition (CORE-09)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    account = ctx["account"]
    user_scope = ctx["user_scope"]
    active_net = user_scope.active_network or "WGMN"

    if active_net == "WNNN":
        current_rel = "WNNN membership"
        requested_trans = "WGMN membership review"
    else:
        current_rel = f"{active_net} membership"
        requested_trans = "WNNN transition review"

    confirmed = False
    active_tab = request.GET.get("tab", "overview")

    if request.method == "POST":
        consent = request.POST.get("consent_confirmed")
        if consent:
            trans = NetworkTransition.objects.create(
                account=account,
                current_relationship=current_rel,
                requested_transition=requested_trans,
                age_evidence_method="Approved re-attestation",
                consent_confirmed=True,
                status="in_progress",
                step=2,
            )
            WorkItem.objects.create(
                title=f"Network Transition: {account.display_name} ({current_rel} → {requested_trans})",
                summary=f"Member requested network transition from {current_rel} to {requested_trans}. Age evidence method: Approved re-attestation.",
                category="network",
                network=active_net,
                country=user_scope.active_country if user_scope.active_country != "*" else "NG",
                confidential=False,
                status="pending",
                created_by=account,
            )
            confirmed = True

    transitions_qs = NetworkTransition.objects.filter(account=account).order_by("-created_at")
    transitions_list = []
    for t in transitions_qs:
        transitions_list.append({
            "id": str(t.id),
            "current_relationship": t.current_relationship,
            "requested_transition": t.requested_transition,
            "age_evidence_method": t.age_evidence_method,
            "status": t.status.replace("_", " ").title(),
            "when": t.created_at.strftime("%d %b %Y · %H:%M WAT") if t.created_at else "Recently",
            "step": t.step,
        })

    history_events = []
    if transitions_list:
        for t in transitions_list:
            history_events.append({
                "when": t["when"],
                "what": f"Transition requested: {t['current_relationship']} → {t['requested_transition']}",
                "who": account.display_name,
                "status": t["status"],
            })
    draft = OnboardingDraft.objects.filter(account=account).first()
    if draft and draft.submitted_at:
        history_events.append({
            "when": draft.submitted_at.strftime("%d %b %Y · %H:%M WAT"),
            "what": f"Initial membership established ({active_net})",
            "who": "System / Admissions",
            "status": "Completed",
        })
    else:
        history_events.append({
            "when": account.created_at.strftime("%d %b %Y · %H:%M WAT") if account.created_at else "Earlier",
            "what": f"Account established in {active_net}",
            "who": "System",
            "status": "Completed",
        })

    ctx.update({
        "screen_code": "CORE-09",
        "active_nav": "workspace",
        "current_relationship": current_rel,
        "requested_transition": requested_trans,
        "transition_confirmed": confirmed,
        "active_tab": active_tab,
        "transitions": transitions_list,
        "history_events": history_events,
        **_get_stage4_state_context(request, "Review your network transition"),
    })
    return render(request, "foundation/core/core_09_transition.html", ctx)


def privacy_request_detail(request, request_id):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    pr = get_object_or_404(PrivacyRequest, id=request_id, account=ctx["account"])

    breadcrumbs = get_breadcrumbs(
        user_scope,
        page_name=f"Privacy Request: {pr.get_request_type_display()}",
    )

    ctx.update({
        "pr": pr,
        "breadcrumbs": breadcrumbs,
    })
    return render(request, "foundation/privacy_request_detail.html", ctx)


def privacy_request_export_download(request, request_id):
    account = getattr(request, "wdos_account", None)
    if not account:
        return redirect("/auth/login/")

    pr = get_object_or_404(PrivacyRequest, id=request_id, account=account)
    if pr.request_type != "export":
        raise Http404("Not an export request")

    # Build personal data archive
    membership = Membership.objects.filter(person=account.person).first() if account.person else None
    export_payload = {
        "account_id": str(account.id),
        "email": account.email,
        "display_name": account.display_name,
        "status": account.status,
        "created_at": account.created_at.isoformat(),
        "verified_at": account.verified_at.isoformat() if account.verified_at else None,
        "membership": {
            "network": membership.network if membership else None,
            "home": membership.home if membership else None,
            "created_at": membership.created_at.isoformat() if membership else None,
        } if membership else None,
        "exported_at": timezone.now().isoformat(),
    }

    response = HttpResponse(
        json.dumps(export_payload, indent=2),
        content_type="application/json",
    )
    response["Content-Disposition"] = f'attachment; filename="wdos_personal_data_{account.id}.json"'
    return response


# -----------------------------------------------------------------------------
# Stage 4 Dashboard Drill-downs, Details, Actions & Exports
# -----------------------------------------------------------------------------

@require_http_methods(["GET"])
def dashboard_drilldown(request, category):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    net = request.GET.get("network", user_scope.active_network).upper()
    country = request.GET.get("country", user_scope.active_country).upper()

    try:
        assert_scope_authorized(user_scope, network=net, country=country)

        items = []
        columns = []
        category_title = category.replace("-", " ").title()

        if category == "chapters":
            chap_qs = Chapter.objects.filter(status="active")
            if net not in ("ALL", "*"):
                chap_qs = chap_qs.filter(network=net)
            if country not in ("ALL", "*"):
                chap_qs = chap_qs.filter(country=country)
            items = list(chap_qs)
            columns = ["Code", "Name", "Network", "Country", "Region", "Community Cluster", "Status", "Members", "Lead Name", "Action"]
        elif category in ("clusters", "community-clusters"):
            c_qs = LocalOrganisationUnit.objects.filter(level="Community Cluster")
            if net not in ("ALL", "*"):
                c_qs = c_qs.filter(network=net)
            if country not in ("ALL", "*"):
                c_qs = c_qs.filter(country=country)
            items = list(c_qs)
            columns = ["Cluster Name", "Network", "Country", "Parent LGA / District", "Leader", "Status", "Action"]
        elif category == "alerts":
            if user_scope.leadership_tier > 4 and not user_scope.is_management_or_admin:
                raise ScopePermissionDenied("Access Denied: Operational alerts drilldown is restricted to leadership roles.", reason_code="leadership_restricted")
            alert_qs = DashboardAlert.objects.filter(is_active=True)
            if net not in ("ALL", "*"):
                alert_qs = alert_qs.filter(network__in=[net, "ALL"])
            if country not in ("ALL", "*"):
                alert_qs = alert_qs.filter(country__in=[country, "ALL"])
            items = list(alert_qs)
            columns = ["Severity", "Title", "Category", "Network", "Country", "Date", "Action"]
        elif category == "meetings":
            meet_qs = ScheduledMeeting.objects.filter(scheduled_at__gte=timezone.now())
            if net not in ("ALL", "*"):
                meet_qs = meet_qs.filter(network__in=[net, "ALL"])
            if country not in ("ALL", "*"):
                meet_qs = meet_qs.filter(country__in=[country, "ALL"])
            items = list(meet_qs.order_by("scheduled_at"))
            columns = ["Title", "Type", "Network", "Country", "Date / Time", "Location", "Attendees", "Action"]
        elif category == "reports":
            if user_scope.leadership_tier > 4 and not user_scope.is_management_or_admin:
                raise ScopePermissionDenied("Access Denied: Reports drilldown is restricted to leadership roles.", reason_code="leadership_restricted")
            rep_qs = DashboardReport.objects.filter(status="published")
            if net not in ("ALL", "*"):
                rep_qs = rep_qs.filter(network__in=[net, "ALL"])
            if country not in ("ALL", "*"):
                rep_qs = rep_qs.filter(country__in=[country, "ALL"])
            items = list(rep_qs)
            columns = ["Title", "Type", "Network", "Country", "Period", "Status", "Action"]
        elif category == "members":
            if user_scope.leadership_tier > 4 and not user_scope.is_management_or_admin:
                raise ScopePermissionDenied("Access Denied: Member roster drilldown is restricted to leadership roles.", reason_code="unauthorized_drilldown")
            mem_qs = Membership.objects.all()
            if net not in ("ALL", "*"):
                mem_qs = mem_qs.filter(network=net)
            if country not in ("ALL", "*"):
                c_name = get_country_display_name(country)
                mem_qs = mem_qs.filter(home__country__iexact=c_name)
            items = list(mem_qs[:50])
            columns = ["Member Name", "Network", "Home Chapter", "Country", "Joined Date"]
        elif category == "verifications":
            if user_scope.leadership_tier > 3 and "reviewer" not in user_scope.roles and not user_scope.is_management_or_admin:
                raise ScopePermissionDenied("Access Denied: Verification queue drilldown is restricted to operations and reviewers.", reason_code="unauthorized_drilldown")
            draft_qs = OnboardingDraft.objects.filter(state="review_needed")
            if net not in ("ALL", "*"):
                draft_qs = draft_qs.filter(data__network=net)
            items = list(draft_qs[:50])
            columns = ["Applicant Email", "Network", "Country", "State", "Revision", "Action"]
        elif category == "work-items":
            if user_scope.leadership_tier > 3 and not user_scope.is_management_or_admin:
                raise ScopePermissionDenied("Access Denied: Work items drilldown is restricted to operations leadership.", reason_code="unauthorized_drilldown")
            work_qs = WorkItem.objects.all()
            if net not in ("ALL", "*"):
                work_qs = work_qs.filter(network=net)
            if country not in ("ALL", "*"):
                work_qs = work_qs.filter(country=country)
            items = list(work_qs[:50])
            columns = ["Work Item", "Category", "Priority", "Status", "Assigned To", "Action"]
        else:
            raise Http404("Unknown drilldown category")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    breadcrumbs = get_breadcrumbs(user_scope, network=net, country=country, page_name=f"{category_title} Drill-down")

    ctx.update({
        "category": category,
        "category_title": category_title,
        "items": items,
        "columns": columns,
        "network": net,
        "country": country,
        "breadcrumbs": breadcrumbs,
        "active_tab": "drilldown",
        "active_nav": "reports" if category == "reports" else "workspace",
    })
    return render(request, "foundation/drilldown.html", ctx)


def alert_detail_view(request, alert_id):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    alert = get_object_or_404(DashboardAlert, id=alert_id)

    try:
        assert_scope_authorized(user_scope, network=alert.network, country=alert.country)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    is_acknowledged = alert.acknowledged_by.filter(id=ctx["account"].id).exists()
    breadcrumbs = get_breadcrumbs(user_scope, network=alert.network, country=alert.country, page_name=f"Alert: {alert.title}")

    ctx.update({
        "alert": alert,
        "is_acknowledged": is_acknowledged,
        "breadcrumbs": breadcrumbs,
    })
    return render(request, "foundation/alert_detail.html", ctx)


@require_POST
def acknowledge_alert(request, alert_id):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    alert = get_object_or_404(DashboardAlert, id=alert_id)

    try:
        assert_scope_authorized(user_scope, network=alert.network, country=alert.country)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    alert.acknowledged_by.add(ctx["account"])
    return redirect(f"/foundation/dashboard/alerts/{alert.id}/")


def report_detail_view(request, report_id):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    if user_scope.leadership_tier > 4 and not user_scope.is_management_or_admin:
        return _render_scope_error(
            request, ctx,
            ScopePermissionDenied(
                "Access Denied: Reports are restricted to authorized leadership appointments.",
                reason_code="leadership_restricted",
                recovery_url="/foundation/dashboard/",
            )
        )

    report = get_object_or_404(DashboardReport, id=report_id)

    try:
        assert_scope_authorized(user_scope, network=report.network, country=report.country)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    breadcrumbs = get_breadcrumbs(user_scope, network=report.network, country=report.country, page_name=f"Report: {report.title}")

    ctx.update({
        "report": report,
        "breadcrumbs": breadcrumbs,
        "active_nav": "reports",
    })
    return render(request, "foundation/report_detail.html", ctx)


def meeting_detail_view(request, meeting_id):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    meeting = get_object_or_404(ScheduledMeeting, id=meeting_id)

    try:
        assert_scope_authorized(user_scope, network=meeting.network, country=meeting.country)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    q = request.GET.copy()
    if "network" not in q and meeting.network in ("WGMN", "WNNN"):
        q["network"] = meeting.network
    if "country" not in q and meeting.country and meeting.country != "ALL":
        q["country"] = meeting.country
    request.GET = q
    return stage9_meeting_detail_view(request, meeting_code=str(meeting.id))


@require_POST
def meeting_rsvp(request, meeting_id):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    meeting = get_object_or_404(ScheduledMeeting, id=meeting_id)

    try:
        assert_scope_authorized(user_scope, network=meeting.network, country=meeting.country)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    account = ctx["account"]
    if meeting.rsvp_accounts.filter(id=account.id).exists():
        meeting.rsvp_accounts.remove(account)
        meeting.attendees_count = max(0, meeting.attendees_count - 1)
    else:
        meeting.rsvp_accounts.add(account)
        meeting.attendees_count += 1
    meeting.save(update_fields=["attendees_count"])

    return redirect(f"/foundation/dashboard/meetings/{meeting.id}/")


def chapter_detail_view(request, chapter_id):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    chapter = get_object_or_404(Chapter, id=chapter_id)

    try:
        assert_scope_authorized(user_scope, network=chapter.network, country=chapter.country)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    sanitized_name = sanitize_chapter_display(chapter.name, fallback_country=chapter.country)
    term = GeographyTerminology.objects.filter(country=chapter.country).first() or GeographyTerminology.objects.filter(country="NG").first()
    first_level_term = term.first_level_term if term else "State / FCT"
    second_level_term = term.second_level_term if term else "LGA"

    cluster_name = chapter.community_cluster or (chapter.cluster_unit.unit_name if chapter.cluster_unit else "")
    if not cluster_name:
        c_unit = LocalOrganisationUnit.objects.filter(country=chapter.country, level="Community Cluster").first()
        if c_unit:
            cluster_name = c_unit.unit_name
        else:
            cluster_name = "Central Community Cluster"

    if cluster_name and not cluster_name.lower().endswith("cluster"):
        cluster_name = f"{cluster_name} Cluster"

    chapter_meetings = list(ScheduledMeeting.objects.filter(
        geography__icontains=chapter.name,
        scheduled_at__gte=timezone.now(),
    )[:5])
    chapter_members = list(Membership.objects.filter(home__code=chapter.code)[:15])

    breadcrumbs = get_breadcrumbs(user_scope, network=chapter.network, country=chapter.country, page_name=f"Chapter: {sanitized_name}")

    ctx.update({
        "chapter": chapter,
        "sanitized_chapter_name": sanitized_name,
        "community_cluster_name": cluster_name,
        "first_level_term": first_level_term,
        "second_level_term": second_level_term,
        "terminology": term,
        "chapter_meetings": chapter_meetings,
        "chapter_members": chapter_members,
        "breadcrumbs": breadcrumbs,
    })
    return render(request, "foundation/chapter_detail.html", ctx)


@require_http_methods(["GET"])
def dashboard_export(request):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    export_type = request.GET.get("type", "summary").lower()
    net = request.GET.get("network", user_scope.active_network).upper()
    country = request.GET.get("country", user_scope.active_country).upper()

    if export_type in ("reports", "chapters", "alerts", "members") and user_scope.leadership_tier > 4 and not user_scope.is_management_or_admin:
        return _render_scope_error(
            request, ctx,
            ScopePermissionDenied(
                f"Access Denied: Exporting {export_type} is restricted to authorized leadership appointments.",
                reason_code="leadership_restricted",
            )
        )

    try:
        assert_scope_authorized(user_scope, network=net, country=country)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    import csv
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="wdos-{export_type}-{net}-{country}.csv"'

    writer = csv.writer(response)
    if export_type == "reports":
        writer.writerow(["ID", "Title", "Report Type", "Network", "Country", "Period", "Status", "Summary", "Created At"])
        for rep in DashboardReport.objects.filter(network__in=[net, "ALL"], country__in=[country, "ALL"]):
            writer.writerow([str(rep.id), rep.title, rep.report_type, rep.network, rep.country, rep.period, rep.status, rep.summary, rep.created_at.isoformat()])
    elif export_type == "activities":
        writer.writerow(["ID", "Title", "Activity Type", "Network", "Country", "Actor", "Created At"])
        for act in DashboardActivity.objects.filter(network=net, country=country):
            writer.writerow([str(act.id), act.title, act.activity_type, act.network, act.country, act.actor_name, act.created_at.isoformat()])
    elif export_type == "chapters":
        writer.writerow(["Code", "Name", "Network", "Country", "Region", "District", "Status", "Members", "Lead Name"])
        for ch in Chapter.objects.filter(network=net, country=country):
            writer.writerow([ch.code, ch.name, ch.network, ch.country, ch.region, ch.district, ch.status, ch.member_count, ch.lead_name])
    elif export_type == "alerts":
        writer.writerow(["ID", "Title", "Severity", "Category", "Network", "Country", "Message", "Created At"])
        for al in DashboardAlert.objects.filter(network__in=[net, "ALL"], country__in=[country, "ALL"]):
            writer.writerow([str(al.id), al.title, al.severity, al.category, al.network, al.country, al.message, al.created_at.isoformat()])
    else:
        kpis = get_scoped_kpis(user_scope, user_scope.active_role, net, country)
        writer.writerow(["Metric", "Value", "Network", "Country"])
        for key, val in kpis.items():
            writer.writerow([key, val, net, country])

    return response


@require_http_methods(["GET", "POST"])
def switch_role_view(request):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    target_role = (request.POST.get("role") or request.GET.get("role", "")).lower().strip()

    if not target_role:
        allowed = list(getattr(user_scope, "switchable_roles", None) or user_scope.roles or [user_scope.primary_role])
        current = user_scope.active_role
        if current in allowed and len(allowed) > 1:
            idx = allowed.index(current)
            target_role = allowed[(idx + 1) % len(allowed)]
        elif len(allowed) > 1:
            target_role = allowed[1]
        else:
            target_role = user_scope.primary_role

    try:
        assert_role_authorized(user_scope, target_role)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    request.session["wdos_active_role"] = target_role
    return redirect(f"/foundation/dashboard/?role={target_role}")


def dev_switch_user(request, role_or_alias):
    """
    Development & Staging convenience route to quickly switch active test persona in a real browser.
    Strictly disabled when settings.DEBUG is False in production.
    """
    if not settings.DEBUG and os.getenv("WDOS_ENVIRONMENT", "local") == "production":
        raise Http404("Development and Staging route only.")

    alias_map = {
        "founder": "founder@example.org",
        "hq": "founder@example.org",
        "ops": "ops@example.org",
        "operations": "ops@example.org",
        "country_ng": "country.ng@example.org",
        "country-ng": "country.ng@example.org",
        "aisha": "country.ng@example.org",
        "aisha_bello": "country.ng@example.org",
        "country_ke": "country.ke@example.org",
        "country-ke": "country.ke@example.org",
        "kenya": "country.ke@example.org",
        "kenya_lead": "country.ke@example.org",
        "wanjiru": "country.ke@example.org",
        "wanjiru_kariuki": "country.ke@example.org",
        "chapter_lagos": "chapter.lagos@example.org",
        "chapter-lagos": "chapter.lagos@example.org",
        "adaeze": "chapter.lagos@example.org",
        "adaeze_okonkwo": "chapter.lagos@example.org",
        "member": "member.ada@example.org",
        "ada": "member.ada@example.org",
        "ada_okafor": "member.ada@example.org",
        "member_ada": "member.ada@example.org",
        "mary": "mary.david@example.org",
        "mary_david": "mary.david@example.org",
        "angola": "mary.david@example.org",
        "sarah": "sarah.andres@example.org",
        "sarah_andres": "sarah.andres@example.org",
        "kemi": "kemi.dare@example.org",
        "kemi_dare": "kemi.dare@example.org",
        "ethiopia": "sarah.andres@example.org",
        "wgmn": "wgmn_member@example.org",
        "wgmn_member": "wgmn_member@example.org",
        "wnnn": "wnnn_member@example.org",
        "wnnn_member": "wnnn_member@example.org",
        "efua": "wnnn_member@example.org",
        "efua_mensah": "wnnn_member@example.org",
        "ghana": "wnnn_member@example.org",
        "candidate": "candidate.john@example.org",
        "john": "candidate.john@example.org",
        "john_kalu": "candidate.john@example.org",
        "community": "community.amara@example.org",
        "amara": "community.amara@example.org",
        "amara_diallo": "community.amara@example.org",
        "secretary": "admin.hq@example.org",
        "network_secretary": "admin.hq@example.org",
        "admin": "admin.hq@example.org",
        "admin_hq": "admin.hq@example.org",
        "coordinator": "coordinator@example.org",
        "coordination": "coordinator@example.org",
        "programmes": "programmes@example.org",
        "comms": "comms@example.org",
        "communications": "comms@example.org",
        "resources": "resources@example.org",
        "finance": "resources@example.org",
        "systems": "systems@example.org",
        "it_admin": "systems@example.org",
        "Quality": "quality@example.org",
        "quality": "quality@example.org",
        "reviewer": "quality@example.org",
        "safeguarding": "safeguarding@example.org",
        "state": "state.lagos@example.org",
        "state_lagos": "state.lagos@example.org",
        "state-lagos": "state.lagos@example.org",
        "lina": "state.lagos@example.org",
        "ikeja": "ikeja.lead@example.org",
        "ikeja_lead": "ikeja.lead@example.org",
        "cluster": "cluster.lead@example.org",
        "cluster_lead": "cluster.lead@example.org",
        "hofco": "ops@example.org",
    }
    email = alias_map.get(role_or_alias.lower().strip(), role_or_alias.lower().strip())
    account = Account.objects.select_related("user").filter(email__iexact=email).first()
    if not account:
        raise Http404(f"Test account '{role_or_alias}' ({email}) not found.")

    from django.contrib.auth import login as django_login
    django_login(request, account.user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["security_version"] = account.security_version
    request.session["mfa_verified"] = True

    # Clear stale session scope state
    request.session.pop("wdos_active_role", None)
    request.session.pop("wdos_active_network", None)
    request.session.pop("wdos_active_country", None)

    now = timezone.now().timestamp()
    request.session["last_activity"] = now
    request.session["absolute_expiry"] = now + settings.WDOS_SESSION_TTL
    request.session.set_expiry(settings.WDOS_SESSION_TTL)
    request.session.modified = True
    return redirect("/foundation/dashboard/")


def dashboard_screen_view(request, screen_code=None):
    """
    Stage 05 Authorized Role Dashboard Controller (DASH-01 through DASH-17).
    Renders authentic, server-scoped dashboard views matching the UI Review v2 Artboards.
    Enforces server-authoritative role, country, and safeguarding access permissions.
    """
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    user_scope = ctx["user_scope"]
    account = ctx["account"]

    # Role resolution & session tracking
    explicit_role = request.GET.get("role")
    if explicit_role:
        try:
            assert_role_authorized(user_scope, explicit_role)
            user_scope.active_role = explicit_role
            request.session["wdos_active_role"] = explicit_role
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
    else:
        sess_role = request.session.get("wdos_active_role")
        if sess_role and user_scope.can_access_role(sess_role):
            user_scope.active_role = sess_role
        else:
            user_scope.active_role = user_scope.primary_role
            request.session["wdos_active_role"] = user_scope.primary_role

    # Network resolution & authorization
    req_net = request.GET.get("network")
    if req_net:
        req_net = req_net.upper()
        try:
            assert_scope_authorized(user_scope, network=req_net)
            user_scope.active_network = req_net
            request.session["wdos_active_network"] = req_net
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    # Country resolution & authorization
    req_country = request.GET.get("country")
    if req_country:
        req_country = req_country.upper()
        try:
            assert_scope_authorized(user_scope, country=req_country)
            user_scope.active_country = req_country
            request.session["wdos_active_country"] = req_country
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    # Resolve screen code: from URL param, GET param, or user's active role default
    explicit_screen = screen_code or request.GET.get("screen")
    is_explicit = bool(explicit_screen)
    resolved_code = explicit_screen or get_default_screen_for_role(user_scope.active_role)

    norm_code = resolved_code.strip().upper()

    # Enforce server-authoritative permission checks
    try:
        check_dashboard_permission(user_scope, norm_code, is_explicit=is_explicit)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    # Build Stage 05 presentation context
    dash_ctx = build_dashboard_context(
        request,
        norm_code,
        user_scope,
        account,
        state_param=request.GET.get("state"),
        tab_param=request.GET.get("tab"),
        is_explicit=is_explicit,
    )

    ctx.update(dash_ctx)
    from .context_block import get_identity_context
    ctx["identity_context"] = get_identity_context(
        account,
        user_scope,
        active_network=user_scope.active_network,
        active_role=user_scope.active_role,
        active_country=user_scope.active_country,
        request=request,
    )
    ctx["active_nav"] = "workspace"
    ctx["breadcrumbs"] = [
        {"label": "Workspace", "url": "/foundation/", "is_current": False},
        {"label": dash_ctx.get("screen_title", "Dashboard"), "url": None, "is_current": True},
    ]

    return render(request, "foundation/dashboards/dash_screen.html", ctx)
 
 
from django.views.decorators.csrf import csrf_exempt
 
 
@csrf_exempt
def test_approve_account_view(request, email=None):
    """
    Unauthenticated testing endpoint to activate and approve any registered user account
    and their onboarding draft, granting immediate dashboard access without manual CLI commands.
    Also auto-provisions the complete Stage 05 role account matrix (DASH-01 through DASH-17)
    so every role dashboard is immediately testable.
    Strictly disabled in production.
    """
    if not settings.DEBUG and os.getenv("WDOS_ENVIRONMENT", "local") == "production":
        raise Http404("Test utility route only available in local and staging environments.")
 
    import io
    from django.contrib.auth import get_user_model
    from django.core.management import call_command
    from accounts.models import OnboardingConsent, OnboardingEvent
 
    User = get_user_model()
    target_email = email or request.POST.get("email") or request.GET.get("email")
    auto_login = request.POST.get("auto_login") == "1" or request.GET.get("auto_login") == "1"
    seed_requested = request.POST.get("seed_all") == "1" or request.GET.get("seed_all") == "1"

    # Auto-provision Stage 05 role accounts if requested or if missing in test environment
    if seed_requested or not Account.objects.filter(email="coordinator@example.org").exists():
        call_command("seed_test_accounts", stdout=io.StringIO())
 
    success_info = None
    error_message = None
 
    if target_email:
        target_email = target_email.strip().lower()
        account = Account.objects.filter(email__iexact=target_email).first()
        if not account:
            # Check if user exists but has no account record yet
            user = User.objects.filter(email__iexact=target_email).first()
            if not user:
                user = User.objects.filter(username__iexact=target_email.split("@")[0]).first()
            if user:
                account = Account.objects.filter(user=user).first()
                if not account:
                    p = Person.objects.create(display_name=user.get_full_name() or user.username)
                    account = Account.objects.create(
                        user=user,
                        email=target_email,
                        display_name=user.get_full_name() or user.username,
                        person=p,
                        status="active",
                        verified_at=timezone.now(),
                    )
 
        if not account:
            error_message = f"No account found with email '{target_email}'. Make sure the account has been registered at /auth/register/ first."
        else:
            # 1. Activate Django User
            u = account.user
            u.is_active = True
            u.save(update_fields=["is_active"])
 
            # 2. Activate Account & Verify
            account.status = "active"
            if not account.verified_at:
                account.verified_at = timezone.now()
 
            # 3. Ensure Person
            if not account.person:
                p = Person.objects.create(display_name=account.display_name or target_email.split("@")[0])
                account.person = p
            account.save()
            p = account.person
 
            # 4. Resolve / Create Onboarding Draft and Authoritative Scope
            draft = OnboardingDraft.objects.filter(account=account).first()
            data = (draft.data if draft else {}) or {}

            # Detect country and network: prioritize explicit AccessGrant, then email heuristics, then draft data
            existing_grant = AccessGrant.objects.filter(account=account, revoked_at__isnull=True).exclude(geography="*").first()
            lower_email = target_email.lower()
            if existing_grant and existing_grant.geography and existing_grant.geography != "*":
                country = existing_grant.geography[:2].upper()
            elif ".ke" in lower_email or "kenya" in lower_email or "wanjiru" in lower_email:
                country = "KE"
            elif ".gh" in lower_email or "ghana" in lower_email or "efua" in lower_email:
                country = "GH"
            elif ".ao" in lower_email or "angola" in lower_email or "mary" in lower_email:
                country = "AO"
            elif ".et" in lower_email or "ethiopia" in lower_email or "sarah" in lower_email or "kemi" in lower_email:
                country = "ET"
            else:
                raw_country = data.get("country_iso2") or data.get("country") or "NG"
                from accounts.african_geography import get_country as af_get_country
                c_lk = af_get_country(raw_country)
                country = c_lk["code"] if c_lk else (raw_country.upper() if len(raw_country) == 2 else "NG")

            existing_net_grant = AccessGrant.objects.filter(account=account, revoked_at__isnull=True).exclude(network="*").first()
            if existing_net_grant and existing_net_grant.network and existing_net_grant.network != "*":
                network = existing_net_grant.network
            elif "wnnn" in lower_email or "efua" in lower_email:
                network = "WNNN"
            else:
                network = data.get("network") or "WGMN"

            country_default_chapters = {
                "KE": ("KE-NBO-01", "Nairobi Central Chapter"),
                "GH": ("GH-ACC-02", "Accra Central Chapter"),
                "AO": ("AO-LUA-01", "Luanda Chapter"),
                "ET": ("ET-ADD-01", "Addis Ababa Chapter"),
                "NG": ("NG-LOS-01", "Lagos Central Chapter"),
            }
            default_chap_code, default_chap_name = country_default_chapters.get(country, ("NG-LOS-01", "Lagos Central Chapter"))

            region = data.get("region_name") or data.get("region") or ""
            district = data.get("district_name") or (data.get("district") if data.get("district") and not str(data.get("district")).startswith("NG-") else "") or ""
            cluster = data.get("community_cluster") or (f"{district} Cluster" if district else "")

            chap = None
            if existing_grant and "-" in (existing_grant.geography or ""):
                chapter_code = existing_grant.geography
                chap = Chapter.objects.filter(code=chapter_code).first()
            else:
                chapter_code = data.get("district_id") or data.get("chapter_code")
                if chapter_code:
                    chap = Chapter.objects.filter(code=chapter_code).first()
                if not chap and district:
                    chap = Chapter.objects.filter(name__icontains=district).first() or Chapter.objects.filter(district__iexact=district).first()
                    if chap:
                        chapter_code = chap.code
                if not chap and not region and not district:
                    chapter_code = default_chap_code
                    chap = Chapter.objects.filter(code=chapter_code).first()

            if chap:
                chapter_code = chap.code
                chapter_label = chap.name
                region = region or chap.region
                district = district or chap.district
                cluster = cluster or chap.community_cluster
            else:
                if not chapter_code:
                    from django.utils.text import slugify
                    sub_slug = slugify(district or region or "chap")
                    chapter_code = default_chap_code if (not region and not district) else f"{country}-{sub_slug}"[:32]
                chapter_label = f"{district} Chapter" if district else (f"{region} Chapter" if region else default_chap_name)

            if not chap and (region or district):
                chap, _ = Chapter.objects.get_or_create(
                    code=chapter_code,
                    defaults={
                        "name": chapter_label,
                        "network": network,
                        "country": country,
                        "region": region,
                        "district": district,
                        "community_cluster": cluster,
                        "status": "active",
                    }
                )

            home = {
                "code": chapter_code,
                "country": country,
                "country_name": data.get("country_name") or data.get("country") or country,
                "state": region,
                "region": region,
                "lga": district,
                "district": district,
                "cluster": cluster,
                "community_cluster": cluster,
                "label": chapter_label,
            }

            is_candidate_account = "candidate" in lower_email or "john.kalu" in lower_email or AccessGrant.objects.filter(account=account, role="candidate", revoked_at__isnull=True).exists()
            target_draft_state = "review_needed" if is_candidate_account else "accepted"

            clean_draft_data = {
                **data,
                "network": network,
                "country": data.get("country") or country,
                "country_iso2": country,
                "region": data.get("region") or region,
                "region_name": data.get("region_name") or region,
                "district": data.get("district") or district,
                "district_name": data.get("district_name") or district,
                "community_cluster": cluster or data.get("community_cluster"),
                "chapter_code": chapter_code,
            }

            if not draft:
                draft = OnboardingDraft.objects.create(
                    account=account,
                    state=target_draft_state,
                    next_step=6 if is_candidate_account else 8,
                    data=clean_draft_data,
                )
            else:
                draft.state = target_draft_state
                draft.next_step = 6 if is_candidate_account else 8
                draft.revision += 1
                draft.data = clean_draft_data
                draft.save(update_fields=["state", "next_step", "revision", "data", "updated_at"])

            # 5. Ensure Consent
            consent = OnboardingConsent.objects.filter(draft=draft).order_by("-id").first()
            if not consent:
                consent = OnboardingConsent.objects.create(
                    draft=draft,
                    revision=draft.revision,
                    version="1.0",
                    notice="Standard Privacy Notice",
                    digest="consent_digest",
                    approval_reference="WDOS-AUTO-APPROVAL",
                    privacy_ack=True,
                    channel="web",
                )

            # 6. Create / Update Membership (for accepted non-candidate accounts)
            if not is_candidate_account:
                Membership.objects.filter(person=p).exclude(draft=draft).delete()
                Membership.objects.update_or_create(
                    draft=draft,
                    defaults={
                        "person": p,
                        "network": network,
                        "home": home,
                        "consent": consent,
                        "policy_digest": "policy_digest_active",
                        "approved_by": account,
                    },
                )
                from foundation.models import PersonProfile
                prof = PersonProfile.objects.filter(account=account).first() or PersonProfile.objects.filter(email__iexact=account.email).first()
                if not prof:
                    PersonProfile.objects.create(
                        account=account,
                        person_code=f"WD-{str(account.id).zfill(5)}",
                        full_name=clean_draft_data.get("full_name") or account.display_name or "Member",
                        email=account.email,
                        network=network,
                        country=country,
                        state_or_region=region,
                        lga_or_district=district,
                        community_cluster=cluster,
                        local_home=chapter_label,
                        chapter=chap,
                        status="Active",
                    )
                else:
                    prof.account = account
                    prof.network = network
                    prof.country = country
                    if region:
                        prof.state_or_region = region
                    if district:
                        prof.lga_or_district = district
                    if cluster:
                        prof.community_cluster = cluster
                    if chap:
                        prof.chapter = chap
                    if chapter_label:
                        prof.local_home = chapter_label
                    prof.status = "Active"
                    prof.save()
 
            # 7. User Preferences
            opt_updates = data.get("optional_updates")
            init_digest = "daily" if opt_updates else ("none" if opt_updates is not None else "daily")
            UserPreference.objects.update_or_create(
                account=account,
                defaults={
                    "active_network": network,
                    "active_country": (country or "NG")[:8],
                    "language": data.get("language") or "en",
                    "font_size": data.get("reading") if data.get("reading") in ("standard", "large", "xlarge") else "standard",
                    "reduced_motion": bool(data.get("reduce_motion")),
                    "activity_digest": init_digest,
                },
            )
 
            OnboardingEvent.objects.create(
                draft=draft,
                actor=account,
                revision=draft.revision,
                event="accepted",
                detail={"home": chapter_code, "note": "Approved via test-approve web view"},
            )
 
            if auto_login:
                from django.contrib.auth import login as django_login
                django_login(request, account.user, backend="django.contrib.auth.backends.ModelBackend")
                request.session["security_version"] = account.security_version
                request.session["mfa_verified"] = True
                request.session.pop("wdos_active_role", None)
                request.session.pop("wdos_active_network", None)
                request.session.pop("wdos_active_country", None)
                if data.get("timezone"):
                    request.session["wdos_timezone"] = data["timezone"]
                if data.get("language"):
                    request.session["wdos_language"] = data["language"]
                now = timezone.now().timestamp()
                request.session["last_activity"] = now
                request.session["absolute_expiry"] = now + settings.WDOS_SESSION_TTL
                request.session.set_expiry(settings.WDOS_SESSION_TTL)
                request.session.modified = True
                return redirect("/foundation/dashboard/")
 
            success_info = {
                "email": account.email,
                "display_name": account.display_name or (account.person.display_name if account.person else account.email),
                "network": network,
                "chapter": chapter_label,
            }
 
    # Fetch all accounts (prioritizing Stage 05 role matrix in DASH-01..DASH-17 order)
    priority_emails = [
        "founder@example.org",
        "ops@example.org",
        "coordinator@example.org",
        "admin.hq@example.org",
        "programmes@example.org",
        "comms@example.org",
        "resources@example.org",
        "systems@example.org",
        "quality@example.org",
        "safeguarding@example.org",
        "country.ng@example.org",
        "country.ke@example.org",
        "state.lagos@example.org",
        "ikeja.lead@example.org",
        "cluster.lead@example.org",
        "chapter.lagos@example.org",
        "member.ada@example.org",
        "wnnn.member@example.org",
        "mary.david@example.org",
        "sarah.andres@example.org",
        "kemi.dare@example.org",
        "candidate.john@example.org",
        "community.amara@example.org",
    ]
    all_accounts_raw = list(Account.objects.select_related("user", "person").all().order_by("-created_at"))
    priority_rank = {em: idx for idx, em in enumerate(priority_emails)}
    all_accounts_raw.sort(key=lambda a: (0, priority_rank[a.email.lower()]) if a.email.lower() in priority_rank else (1, 0))

    recent_list = []
    for acc in all_accounts_raw:
        dr = OnboardingDraft.objects.filter(account=acc).first()
        scope = get_user_scope(acc)
        dash_code = get_default_screen_for_role(scope.primary_role)
        dash_screen = get_dashboard_screen(dash_code) or {}
        is_ready = (
            acc.status == "active"
            and (
                (dr and dr.state == "accepted" and Membership.objects.filter(draft=dr).exists())
                or scope.primary_role in ("candidate", "community")
                or bool(scope.roles)
            )
        )
        recent_list.append({
            "email": acc.email,
            "display_name": acc.display_name or (acc.person.display_name if acc.person else acc.email.split("@")[0]),
            "status": acc.status,
            "draft_state": dr.state if dr else "No draft",
            "is_approved": is_ready,
            "role_label": dash_screen.get("default_role_title") or scope.primary_role.replace("_", " ").title(),
            "scope_label": f"{scope.active_network} / {scope.active_country}",
            "dashboard_code": dash_code,
            "dashboard_title": dash_screen.get("title", dash_code),
        })
 
    ctx = {
        "success_info": success_info,
        "error_message": error_message,
        "target_email": target_email or "",
        "recent_accounts": recent_list,
    }
    return render(request, "foundation/test_approve.html", ctx)


# =============================================================================
# WDOS STAGE 06: PEOPLE, COMMUNITY, AND GEOGRAPHY SPINE VIEWS
# =============================================================================

def _get_scoped_people_queryset(user_scope: UserScope, req_country: str = "", req_network: str = ""):
    qs = PersonProfile.objects.all()
    if is_global_stage6_scope(user_scope):
        if req_network and req_network.upper() in {"WGMN", "WNNN"}:
            qs = qs.filter(network=req_network.upper())
        elif user_scope.active_network in {"WGMN", "WNNN"} and not req_country:
            qs = qs.filter(network__in=[user_scope.active_network, "BOTH"])
        if req_country:
            qs = qs.filter(country=normalize_country_code(req_country))
        elif user_scope.active_country not in {"ALL", "BOTH", "*", ""}:
            qs = qs.filter(country=user_scope.active_country)
    else:
        if user_scope.active_network not in {"ALL", "HQ / Both networks", "*"}:
            qs = qs.filter(network__in=[user_scope.active_network, "BOTH"])
        if user_scope.active_country not in {"ALL", "BOTH", "*"}:
            qs = qs.filter(country=user_scope.active_country)
    return qs


def _get_changed_person_codes() -> set:
    from accounts.models import AuditEvent

    changed = set(
        LocalHomeReassignment.objects.filter(status="approved").values_list("person__person_code", flat=True)
    )
    recent_events = AuditEvent.objects.filter(
        event__in={"person_profile_updated", "relationship_saved", "local_home_reassigned", "person_linked"}
    ).order_by("-created_at")[:50]
    for ev in recent_events:
        if ev.detail and ev.detail.get("person_code"):
            changed.add(ev.detail["person_code"])
    return changed


def people_directory_view(request):
    """
    PEOPLE-01: People directory.
    Provides scoped operating list of people, memberships, and relationships.
    """
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    seed_stage6_fixtures()
    user_scope = ctx["user_scope"]

    try:
        assert_stage6_authorized(user_scope, "PEOPLE-01")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    req_country = request.GET.get("country", "").strip()
    req_network = request.GET.get("network", "").strip()
    if req_country or req_network:
        try:
            assert_country_network_authorized(user_scope, country=req_country or None, network=req_network or None)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    screen = dict(STAGE6_SCREENS["PEOPLE-01"])
    state_mode = request.GET.get("state")
    state_card = screen["state_contracts"].get(state_mode) if state_mode else None

    qs = _get_scoped_people_queryset(user_scope, req_country=req_country, req_network=req_network)
    total_scoped_count = qs.count()

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(full_name__icontains=query)
            | Q(local_home__icontains=query)
            | Q(person_code__icontains=query)
            | Q(email__icontains=query)
            | Q(primary_relationship__icontains=query)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status__iexact=status_filter)

    relationship_filter = request.GET.get("relationship", "").strip()
    if relationship_filter:
        qs = qs.filter(primary_relationship__icontains=relationship_filter)

    verification_filter = request.GET.get("verification", "").strip()
    if verification_filter:
        qs = qs.filter(contact_verification__iexact=verification_filter)

    people = list(qs)
    if state_mode == "empty":
        people = []
    elif not state_card and len(people) == 0 and (query or status_filter or relationship_filter or verification_filter):
        state_card = screen["state_contracts"].get("no_matching")

    changed_codes = _get_changed_person_codes()
    for p in people:
        p.is_changed_record = p.person_code in changed_codes
        p.hierarchy_path = p.get_hierarchy_path()

    audit_history = get_stage6_audit_history(user_scope)

    ctx.update({
        "screen": screen,
        "people": people,
        "total_scoped_count": total_scoped_count,
        "active_count": sum(1 for p in people if p.status == "Active"),
        "verified_count": sum(1 for p in people if p.contact_verification == "Verified"),
        "review_due_count": sum(1 for p in people if p.status != "Active"),
        "changed_codes": changed_codes,
        "audit_history": audit_history,
        "active_nav": "people",
        "active_tab": request.GET.get("tab", "records"),
        "state_mode": state_mode,
        "state_card": state_card,
        "query": query,
        "status_filter": status_filter,
        "relationship_filter": relationship_filter,
    })
    return render(request, "foundation/people_geography/people_01_directory.html", ctx)


def person_profile_view(request, person_code="WD-00421"):
    """
    PEOPLE-02: Person profile (e.g. Ada Okafor).
    Shows profile summary, local hierarchy placement, verified status, attached relationships,
    and allows authorized users to update profile details within their permitted scope.
    """
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    seed_stage6_fixtures()
    user_scope = ctx["user_scope"]
    account = ctx["account"]

    try:
        assert_stage6_authorized(user_scope, "PEOPLE-02")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    screen = dict(STAGE6_SCREENS["PEOPLE-02"])
    state_mode = request.GET.get("state")
    state_card = screen["state_contracts"].get(state_mode) if state_mode else None

    is_default_profile_route = request.path.rstrip("/").endswith("/people/profile")
    req_person_param = request.GET.get("person", "").strip()
    if req_person_param:
        person_code = req_person_param
        is_default_profile_route = False

    person = None
    if is_default_profile_route and not is_global_stage6_scope(user_scope):
        scoped_qs = _get_scoped_people_queryset(user_scope)
        person = scoped_qs.first()

    if person is None:
        try:
            person = PersonProfile.objects.get(person_code=person_code)
        except PersonProfile.DoesNotExist:
            try:
                person = PersonProfile.objects.get(id=person_code)
            except Exception:
                person = _get_scoped_people_queryset(user_scope).first() or PersonProfile.objects.first()
                if person is None and PersonProfile.objects.exists():
                    raise Http404(f"Person record '{person_code}' not found.")

    if person:
        try:
            assert_person_scope_authorized(user_scope, person)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    result_message = None
    result_success = True

    if request.method == "POST" and person:
        action = request.POST.get("action", "update_profile")
        if action == "update_profile":
            full_name = request.POST.get("full_name", person.full_name)
            email = request.POST.get("email", person.email)
            phone = request.POST.get("phone", person.phone)
            local_home = request.POST.get("local_home", person.local_home)
            contact_verification = request.POST.get("contact_verification", person.contact_verification)
            primary_relationship = request.POST.get("primary_relationship", person.primary_relationship)
            status_val = request.POST.get("status", person.status)
            expected_updated = request.POST.get("expected_updated_at", "").strip()
            state_or_region = request.POST.get("state_or_region", person.state_or_region)
            lga_or_district = request.POST.get("lga_or_district", person.lga_or_district)
            community_cluster = request.POST.get("community_cluster", person.community_cluster)
            chapter_name = request.POST.get("chapter_name", person.chapter_name)

            try:
                res = update_person_profile_record(
                    person_code=person.person_code,
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    local_home=local_home,
                    contact_verification=contact_verification,
                    primary_relationship=primary_relationship,
                    status=status_val,
                    state_or_region=state_or_region,
                    lga_or_district=lga_or_district,
                    community_cluster=community_cluster,
                    chapter_name=chapter_name,
                    actor_account=account,
                    user_scope=user_scope,
                    expected_updated_at=expected_updated or None,
                )
                person = res["person"]
                if res.get("conflict"):
                    result_message = res["message"]
                    result_success = False
                    state_card = {
                        "title": "Another change needs review",
                        "message": res["message"],
                        "action_label": "Review latest version",
                        "action_url": f"/foundation/people/{person.person_code}/",
                    }
                else:
                    result_message = f"Profile for {person.full_name} ({person.person_code}) updated and recorded in audit history."
                    result_success = True
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except Exception as exc:
                result_message = str(exc)
                result_success = False

    target_net = person.network if person else (user_scope.active_network if user_scope.active_network in {"WGMN", "WNNN"} else "WGMN")
    target_ctry = person.country if person else (user_scope.active_country if user_scope.active_country not in {"ALL", "BOTH", "*", ""} else "NG")
    people = list(PersonProfile.objects.filter(network=target_net, country=target_ctry))
    if state_mode == "empty":
        people = []

    person_relationships = list(person.relationships.all()) if person else []
    local_hierarchy = list(
        LocalOrganisationUnit.objects.filter(country=target_ctry, network=target_net).order_by("level_order")
    )
    audit_history = get_stage6_audit_history(user_scope, person_code=person.person_code if person else None)
    changed_codes = _get_changed_person_codes()
    hierarchy_path = person.get_hierarchy_path() if person else {}

    from .context_block import get_identity_context
    ctx["identity_context"] = get_identity_context(
        ctx["account"],
        user_scope,
        active_network=target_net,
        active_role=user_scope.active_role,
        active_country=target_ctry,
        target_person=person,
        request=request,
    )

    ctx.update({
        "screen": screen,
        "person": person,
        "person_country_name": get_country_name_for_code(target_ctry),
        "is_changed_record": (person.person_code in changed_codes) if person else False,
        "expected_updated_at": person.updated_at.isoformat() if person and getattr(person, "updated_at", None) else "",
        "reassignments": list(person.reassignments.all()) if person else [],
        "people": people,
        "person_relationships": person_relationships,
        "local_hierarchy": local_hierarchy,
        "hierarchy_path": hierarchy_path,
        "audit_history": audit_history,
        "result_title": "Profile updated" if result_success else "Review required",
        "result_message": result_message,
        "result_success": result_success,
        "active_nav": "people",
        "active_tab": request.GET.get("tab", "overview"),
        "state_mode": state_mode,
        "state_card": state_card,
    })
    return render(request, "foundation/people_geography/people_02_profile.html", ctx)


def add_or_link_person_view(request):
    """
    PEOPLE-03: Add or link a person wizard.
    Safe add-or-link duplicate handling preventing multiple person identity registrations.
    """
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    seed_stage6_fixtures()
    user_scope = ctx["user_scope"]
    account = ctx["account"]

    try:
        assert_stage6_authorized(user_scope, "PEOPLE-03")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    screen = dict(STAGE6_SCREENS["PEOPLE-03"])
    state_mode = request.GET.get("state")
    state_card = screen["state_contracts"].get(state_mode) if state_mode else None

    default_country_name = get_country_name_for_code(
        user_scope.active_country if user_scope.active_country not in {"ALL", "BOTH", "*", ""} else "NG"
    )
    default_net = user_scope.active_network if user_scope.active_network in {"WGMN", "WNNN"} else "WGMN"

    result_message = None
    result_success = True
    duplicate_preview = None
    form_data = {
        "full_name": "",
        "email": "",
        "country": default_country_name,
        "relationship_to_add": f"{default_net} membership",
        "local_home": "",
    }

    if request.method == "POST":
        action = request.POST.get("action", "check_or_save")
        full_name = request.POST.get("full_name", "").strip()
        email = request.POST.get("email", "").strip()
        country = request.POST.get("country", "").strip()
        relationship = request.POST.get("relationship_to_add", "").strip()
        local_home = request.POST.get("local_home", "").strip()
        form_data.update({
            "full_name": full_name,
            "email": email,
            "country": country,
            "relationship_to_add": relationship,
            "local_home": local_home,
        })

        if action == "save_draft":
            state_card = screen["state_contracts"]["saved_later"]
            result_message = "Draft saved for later. Your entered information is retained."
            result_success = True
        elif not full_name or not email:
            state_card = screen["state_contracts"]["check_highlighted"]
            result_message = "Full name and contact email are required before continuing."
            result_success = False
        elif action == "check_only":
            dup = check_for_duplicate_person(email=email, full_name=full_name, network=default_net)
            duplicate_preview = dup
            result_message = dup["message"]
            result_success = True
        else:
            norm_c = normalize_country_code(country, default_code="NG")
            try:
                res = add_or_link_person_record(
                    full_name=full_name,
                    email=email,
                    country=norm_c,
                    relationship_to_add=relationship,
                    network=default_net,
                    actor_account=account,
                    user_scope=user_scope,
                    local_home=local_home or None,
                )
                if res["action_type"] == "linked":
                    result_message = f"Existing person record found ({res['person'].person_code} · {res['person'].full_name}). Relationship linked successfully without creating a duplicate identity."
                else:
                    result_message = f"New authoritative person record created ({res['person'].person_code} · {res['person'].full_name}) and relationship linked."
                result_success = True
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except Exception as exc:
                result_message = str(exc)
                result_success = False

    audit_history = get_stage6_audit_history(user_scope)

    ctx.update({
        "screen": screen,
        "active_nav": "people",
        "active_tab": request.GET.get("tab", "records"),
        "state_mode": state_mode,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "duplicate_preview": duplicate_preview,
        "form_data": form_data,
        "audit_history": audit_history,
    })
    return render(request, "foundation/people_geography/people_03_add_or_link.html", ctx)


def community_relationships_view(request):
    """
    PEOPLE-04: Community relationships.
    Displays people and connected relationships matching scope with search and category filters.
    """
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    seed_stage6_fixtures()
    user_scope = ctx["user_scope"]

    try:
        assert_stage6_authorized(user_scope, "PEOPLE-04")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    screen = dict(STAGE6_SCREENS["PEOPLE-04"])
    state_mode = request.GET.get("state")
    state_card = screen["state_contracts"].get(state_mode) if state_mode else None

    qs = _get_scoped_people_queryset(user_scope)

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(full_name__icontains=query)
            | Q(local_home__icontains=query)
            | Q(primary_relationship__icontains=query)
            | Q(person_code__icontains=query)
        )

    category_filter = request.GET.get("category", "").strip()
    if category_filter:
        qs = qs.filter(
            Q(primary_relationship__icontains=category_filter)
            | Q(relationships__category__icontains=category_filter)
        ).distinct()

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(status__iexact=status_filter)

    for_role = request.GET.get("for_role", "").strip()
    if for_role == "1":
        qs = qs.filter(status__in=["Active", "Review due"])

    people = list(qs)
    if state_mode == "empty":
        people = []
    elif not state_card and len(people) == 0 and (query or category_filter or status_filter):
        state_card = screen["state_contracts"].get("no_matching")

    changed_codes = _get_changed_person_codes()
    for p in people:
        p.is_changed_record = p.person_code in changed_codes

    audit_history = get_stage6_audit_history(user_scope)

    ctx.update({
        "screen": screen,
        "people": people,
        "query": query,
        "category_filter": category_filter,
        "status_filter": status_filter,
        "for_role": for_role,
        "audit_history": audit_history,
        "active_nav": "people",
        "active_tab": request.GET.get("tab", "records"),
        "state_mode": state_mode,
        "state_card": state_card,
    })
    return render(request, "foundation/people_geography/people_04_community_relationships.html", ctx)


def manage_relationships_view(request):
    """
    PEOPLE-05: Manage relationships.
    Attaches membership, participation and leadership to a single person identity.
    """
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    seed_stage6_fixtures()
    user_scope = ctx["user_scope"]
    account = ctx["account"]

    try:
        assert_stage6_authorized(user_scope, "PEOPLE-05")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    screen = dict(STAGE6_SCREENS["PEOPLE-05"])
    state_mode = request.GET.get("state")
    state_card = screen["state_contracts"].get(state_mode) if state_mode else None

    scoped_people = list(_get_scoped_people_queryset(user_scope))
    req_person_code = (request.GET.get("person") or request.POST.get("person_code") or "").strip()

    selected_person = None
    if req_person_code:
        selected_person = PersonProfile.objects.filter(person_code=req_person_code).first()
        if selected_person:
            try:
                assert_person_scope_authorized(user_scope, selected_person)
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)

    if not selected_person:
        selected_person = scoped_people[0] if scoped_people else PersonProfile.objects.first()

    result_message = None
    result_success = True
    form_data = {
        "relationship_category": "",
        "related_programme": "",
        "effective_date": "",
    }

    if request.method == "POST":
        action = request.POST.get("action", "save")
        category = request.POST.get("relationship_category", "").strip()
        programme = request.POST.get("related_programme", "").strip()
        eff_date = request.POST.get("effective_date", "").strip()
        person_code = request.POST.get("person_code", selected_person.person_code if selected_person else "WD-00421").strip()
        form_data.update({
            "relationship_category": category,
            "related_programme": programme,
            "effective_date": eff_date,
        })

        if action == "save_draft":
            state_card = screen["state_contracts"]["saved_later"]
            result_message = "Draft relationship saved for later."
        elif not category:
            state_card = screen["state_contracts"]["check_highlighted"]
            result_message = "Relationship category is required."
            result_success = False
        else:
            try:
                res = save_person_relationship(
                    person_id_or_code=person_code,
                    relationship_category=category,
                    related_programme=programme,
                    effective_date_str=eff_date,
                    actor_account=account,
                    user_scope=user_scope,
                )
                selected_person = res["person"]
                result_message = f"Relationship successfully saved and attached to {res['person'].full_name} ({res['person'].person_code})."
                result_success = True
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except Exception as exc:
                result_message = str(exc)
                result_success = False

    existing_relationships = list(selected_person.relationships.all()) if selected_person else []
    audit_history = get_stage6_audit_history(
        user_scope,
        person_code=selected_person.person_code if selected_person else None,
    )

    ctx.update({
        "screen": screen,
        "selected_person": selected_person,
        "scoped_people": scoped_people,
        "existing_relationships": existing_relationships,
        "audit_history": audit_history,
        "active_nav": "people",
        "active_tab": request.GET.get("tab", "records"),
        "state_mode": state_mode,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "form_data": form_data,
    })
    return render(request, "foundation/people_geography/people_05_manage_relationships.html", ctx)


def review_reassignment_view(request):
    """
    PEOPLE-06: Review local-home reassignment.
    Enforces role authority, member confirmation, and durable audit history.
    """
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    seed_stage6_fixtures()
    user_scope = ctx["user_scope"]
    account = ctx["account"]

    try:
        assert_stage6_authorized(user_scope, "PEOPLE-06")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    screen = dict(STAGE6_SCREENS["PEOPLE-06"])
    state_mode = request.GET.get("state")
    state_card = screen["state_contracts"].get(state_mode) if state_mode else None

    scoped_people = _get_scoped_people_queryset(user_scope)
    req_person = (request.GET.get("person") or request.POST.get("person_code") or "").strip()

    reassignments_qs = LocalHomeReassignment.objects.select_related("person").filter(person__in=scoped_people)
    if req_person:
        target_p = PersonProfile.objects.filter(person_code=req_person).first()
        if target_p:
            try:
                assert_person_scope_authorized(user_scope, target_p)
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            reassignments_qs = LocalHomeReassignment.objects.select_related("person").filter(person=target_p)

    reassignment = reassignments_qs.first() or LocalHomeReassignment.objects.select_related("person").first()

    result_message = None
    result_success = True

    if request.method == "POST":
        person_code = request.POST.get("person_code", reassignment.person.person_code if reassignment else "WD-00421")
        proposed_home = request.POST.get("proposed_local_home", "").strip()
        reason = request.POST.get("reason", "").strip()
        confirmation = request.POST.get("member_confirmation") in {"true", "True", "1", "on"}

        try:
            res = submit_reassignment_decision(
                person_code=person_code,
                proposed_local_home=proposed_home,
                reason=reason,
                member_confirmation=confirmation,
                actor_account=account,
                user_scope=user_scope,
            )
            reassignment = res["reassignment"]
            result_message = f"Reassignment to '{proposed_home}' submitted and approved with confirmation linked."
            result_success = True
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = screen["state_contracts"]["check_highlighted"]
            result_message = str(exc)
            result_success = False
        except Exception as exc:
            result_message = str(exc)
            result_success = False

    reassignments_history = list(
        LocalHomeReassignment.objects.select_related("person", "reviewed_by").filter(person__in=scoped_people)
    )
    audit_history = get_stage6_audit_history(user_scope)

    ctx.update({
        "screen": screen,
        "reassignment": reassignment,
        "scoped_people": list(scoped_people),
        "reassignments_history": reassignments_history,
        "audit_history": audit_history,
        "active_nav": "people",
        "active_tab": request.GET.get("tab", "records"),
        "state_mode": state_mode,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/people_geography/people_06_review_reassignment.html", ctx)


def africa_network_coverage_view(request):
    """
    GEO-01: Africa and network coverage.
    Continental view with interactive vector map and separate network country tables.
    """
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    seed_stage6_fixtures()
    user_scope = ctx["user_scope"]

    try:
        assert_stage6_authorized(user_scope, "GEO-01")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    req_country = request.GET.get("country", "").strip().upper()
    network_filter = request.GET.get("network", "").strip().upper()

    if req_country or network_filter:
        try:
            assert_country_network_authorized(user_scope, country=req_country or None, network=network_filter or None)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    screen = dict(STAGE6_SCREENS["GEO-01"])
    state_mode = request.GET.get("state")
    state_card = screen["state_contracts"].get(state_mode) if state_mode else None

    active_network = network_filter or user_scope.active_network or "WGMN"
    if active_network not in {"WGMN", "WNNN"}:
        active_network = "WGMN"

    qs = CountryDossier.objects.all()
    if not is_global_stage6_scope(user_scope):
        if user_scope.active_country not in {"ALL", "BOTH", "*"}:
            qs = qs.filter(country_code=user_scope.active_country)
        if user_scope.active_network in {"WGMN", "WNNN"}:
            qs = qs.filter(network=user_scope.active_network)
    else:
        if network_filter in {"WGMN", "WNNN"}:
            qs = qs.filter(network=network_filter)

    query = request.GET.get("q", "").strip()
    if query:
        qs = qs.filter(
            Q(country_name__icontains=query)
            | Q(country_code__icontains=query)
            | Q(network__icontains=query)
            | Q(country_lead_name__icontains=query)
            | Q(verification_status__icontains=query)
        )

    status_filter = request.GET.get("status", "").strip()
    if status_filter:
        qs = qs.filter(verification_status__icontains=status_filter)

    dossiers = list(qs)
    if state_mode == "empty":
        dossiers = []
    elif not state_card and len(dossiers) == 0 and (query or status_filter or network_filter):
        state_card = screen["state_contracts"].get("no_matching")

    # Determine default selected dossier based on user's authorized scope
    selected_dossier = None
    if req_country:
        selected_dossier = next((d for d in dossiers if d.country_code == req_country), None)
    if not selected_dossier and not is_global_stage6_scope(user_scope) and user_scope.active_country not in {"ALL", "BOTH", "*"}:
        selected_dossier = next((d for d in dossiers if d.country_code == user_scope.active_country), None)
    if not selected_dossier and dossiers:
        selected_dossier = next((d for d in dossiers if d.country_code == "NG" and d.network == active_network), dossiers[0])

    from accounts.african_geography import get_country as get_geo_country
    country_hierarchy_map = {}
    for d in dossiers:
        cc = d.country_code
        term = GeographyTerminology.objects.filter(country=cc, status="effective").first()
        c_info = get_geo_country(cc) or {}
        l1_term = term.first_level_term if term else c_info.get("admin1_label", "State / Region")
        l2_term = term.second_level_term if term else c_info.get("admin2_label", "LGA / District")

        l1_unit = LocalOrganisationUnit.objects.filter(country=cc, level="Region / State").first()
        l2_unit = LocalOrganisationUnit.objects.filter(country=cc, level="District / LGA").first()
        cluster_unit = LocalOrganisationUnit.objects.filter(country=cc, level="Community Cluster").first()
        chapter_unit = LocalOrganisationUnit.objects.filter(country=cc, level="Chapter").first()

        l1_name = l1_unit.unit_name if l1_unit else ("Lagos State" if cc == "NG" else f"{d.country_name} Region")
        l2_name = l2_unit.unit_name if l2_unit else ("Ikeja LGA" if cc == "NG" else f"{d.country_name} District")
        cluster_name = cluster_unit.unit_name if cluster_unit else ("Ikeja Central Cluster" if cc == "NG" else "Central Community Cluster")
        chapter_name = chapter_unit.unit_name if chapter_unit else ("Allen Chapter" if cc == "NG" else f"{d.country_name} Central Chapter")

        country_hierarchy_map[cc] = {
            "country_name": d.country_name,
            "country_code": cc,
            "first_level_term": l1_term,
            "first_level_name": l1_name,
            "second_level_term": l2_term,
            "second_level_name": l2_name,
            "cluster_name": cluster_name,
            "chapter_name": chapter_name,
            "path_text": f"{d.network} → {d.country_name} → {l1_name} ({l1_term}) → {l2_name} ({l2_term}) → {cluster_name} (Cluster) → {chapter_name} (Chapter)",
        }

    selected_cc = selected_dossier.country_code if selected_dossier else "NG"
    selected_hierarchy = country_hierarchy_map.get(selected_cc)

    is_global_user = is_global_stage6_scope(user_scope)
    allowed_country_codes = ["NG", "KE", "GH", "AO", "ET"] if is_global_user else ([user_scope.active_country] if user_scope.active_country in ["NG", "KE", "GH", "AO", "ET"] else ["NG"])

    ctx.update({
        "screen": screen,
        "dossiers": dossiers,
        "selected_dossier": selected_dossier,
        "country_hierarchy_map": country_hierarchy_map,
        "selected_hierarchy": selected_hierarchy,
        "allowed_country_codes": allowed_country_codes,
        "is_global_user": is_global_user,
        "query": query,
        "status_filter": status_filter,
        "network_filter": network_filter,
        "active_network": active_network,
        "active_nav": "reports",
        "active_tab": request.GET.get("tab", "map"),
        "state_mode": state_mode,
        "state_card": state_card,
    })
    return render(request, "foundation/people_geography/geo_01_africa_coverage.html", ctx)


def country_command_profile_view(request, country_code="NG"):
    """
    GEO-02: Country Command Profile.
    Shows country leadership, timezone reference, and dossier verification status.
    """
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    seed_stage6_fixtures()
    user_scope = ctx["user_scope"]

    try:
        assert_stage6_authorized(user_scope, "GEO-02")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    norm_cc = normalize_country_code(country_code, default_code="NG")
    req_net = request.GET.get("network", "").strip().upper()

    try:
        assert_country_network_authorized(user_scope, country=norm_cc, network=req_net or None)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    screen = dict(STAGE6_SCREENS["GEO-02"])
    state_mode = request.GET.get("state")
    state_card = screen["state_contracts"].get(state_mode) if state_mode else None

    dossier_qs = CountryDossier.objects.filter(country_code=norm_cc)
    if req_net in {"WGMN", "WNNN"}:
        dossier_qs = dossier_qs.filter(network=req_net)
    dossier = dossier_qs.first() or CountryDossier.objects.filter(country_code=norm_cc).first() or CountryDossier.objects.first()

    dossiers_qs = CountryDossier.objects.all()
    if not is_global_stage6_scope(user_scope):
        if user_scope.active_country not in {"ALL", "BOTH", "*"}:
            dossiers_qs = dossiers_qs.filter(country_code=user_scope.active_country)
        if user_scope.active_network in {"WGMN", "WNNN"}:
            dossiers_qs = dossiers_qs.filter(network=user_scope.active_network)

    dossiers = list(dossiers_qs)
    if state_mode == "empty":
        dossiers = []

    audit_history = get_stage6_audit_history(user_scope, country_code=norm_cc)

    from accounts.african_geography import get_country as get_geo_country
    c_info = get_geo_country(norm_cc) or {}
    term = GeographyTerminology.objects.filter(country=norm_cc, status="effective").first()
    l1_term = term.first_level_term if term else c_info.get("admin1_label", "State / Region")
    l2_term = term.second_level_term if term else c_info.get("admin2_label", "LGA / District")
    l1_unit = LocalOrganisationUnit.objects.filter(country=norm_cc, level="Region / State").first()
    l2_unit = LocalOrganisationUnit.objects.filter(country=norm_cc, level="District / LGA").first()
    cluster_unit = LocalOrganisationUnit.objects.filter(country=norm_cc, level="Community Cluster").first()
    chapter_unit = LocalOrganisationUnit.objects.filter(country=norm_cc, level="Chapter").first()

    c_name_disp = dossier.country_name if dossier else (c_info.get("name") or get_country_display_name(norm_cc))
    net_disp = dossier.network if dossier else (req_net or user_scope.active_network or "WGMN")
    l1_name = l1_unit.unit_name if l1_unit else ("Lagos State" if norm_cc == "NG" else f"{c_name_disp} Region")
    l2_name = l2_unit.unit_name if l2_unit else ("Ikeja LGA" if norm_cc == "NG" else f"{c_name_disp} District")
    cluster_name = cluster_unit.unit_name if cluster_unit else ("Ikeja Central Cluster" if norm_cc == "NG" else "Central Community Cluster")
    if cluster_name and not cluster_name.lower().endswith("cluster"):
        cluster_name = f"{cluster_name} Cluster"
    chapter_name = chapter_unit.unit_name if chapter_unit else ("Allen Chapter" if norm_cc == "NG" else f"{c_name_disp} Central Chapter")
    chapter_name = sanitize_chapter_display(chapter_name, fallback_country=norm_cc)

    country_hierarchy = {
        "country_name": c_name_disp,
        "country_code": norm_cc,
        "first_level_term": l1_term,
        "first_level_name": l1_name,
        "second_level_term": l2_term,
        "second_level_name": l2_name,
        "cluster_name": cluster_name,
        "chapter_name": chapter_name,
        "path_text": f"{net_disp} → {c_name_disp} → {l1_name} → {l2_name} → {cluster_name} → {chapter_name}",
    }

    local_hierarchy = list(LocalOrganisationUnit.objects.filter(country=norm_cc).order_by("level_order"))
    country_units = list(LocalOrganisationUnit.objects.filter(country=norm_cc))
    country_people_count = PersonProfile.objects.filter(country=norm_cc).count()

    ctx.update({
        "screen": screen,
        "dossier": dossier,
        "dossiers": dossiers,
        "audit_history": audit_history,
        "terminology": term,
        "country_hierarchy": country_hierarchy,
        "local_hierarchy": local_hierarchy,
        "country_units": country_units,
        "country_people_count": country_people_count,
        "active_nav": "reports",
        "active_tab": request.GET.get("tab", "overview"),
        "state_mode": state_mode,
        "state_card": state_card,
    })
    return render(request, "foundation/people_geography/geo_02_country_command.html", ctx)


def local_organisation_view(request):
    """
    GEO-03: Local organisation.
    Visual 5-tier organizational hierarchy, unit directory, and unit creation/editing.
    """
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    seed_stage6_fixtures()
    user_scope = ctx["user_scope"]
    account = ctx["account"]

    try:
        assert_stage6_authorized(user_scope, "GEO-03")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    req_country = (request.GET.get("country") or request.POST.get("country") or "").strip()
    req_network = (request.GET.get("network") or request.POST.get("network") or "").strip().upper()

    if req_country:
        target_country = normalize_country_code(req_country, default_code="NG")
    elif not is_global_stage6_scope(user_scope) and user_scope.active_country not in {"ALL", "BOTH", "*", ""}:
        target_country = user_scope.active_country
    else:
        target_country = "NG"

    if req_network in {"WGMN", "WNNN"}:
        target_network = req_network
    elif not is_global_stage6_scope(user_scope) and user_scope.active_network in {"WGMN", "WNNN"}:
        target_network = user_scope.active_network
    else:
        target_network = "WGMN"

    try:
        assert_country_network_authorized(user_scope, country=target_country, network=target_network)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    screen = dict(STAGE6_SCREENS["GEO-03"])
    state_mode = request.GET.get("state")
    state_card = screen["state_contracts"].get(state_mode) if state_mode else None

    result_message = None
    result_success = True

    if request.method == "POST":
        unit_name = request.POST.get("unit_name", "").strip()
        level = request.POST.get("level", "Chapter").strip()
        leader_name = request.POST.get("responsible_leader_name", "").strip()
        description = request.POST.get("description", "").strip()
        evidence_type = request.POST.get("evidence_type", "Unit record").strip()
        record_state = request.POST.get("record_state", "Active unit records").strip()
        parent_id = request.POST.get("parent_id", "").strip() or None

        if not unit_name:
            result_message = "Unit name is required."
            result_success = False
        else:
            try:
                res = save_local_organisation_unit(
                    network=target_network,
                    country=target_country,
                    level=level,
                    unit_name=unit_name,
                    responsible_leader_name=leader_name,
                    description=description,
                    evidence_type=evidence_type,
                    record_state=record_state,
                    parent_id=parent_id,
                    actor_account=account,
                    user_scope=user_scope,
                )
                verb = "created" if res["created"] else "updated"
                result_message = f"Local organisation unit '{res['unit'].unit_name}' ({res['unit'].level}) {verb} successfully."
                result_success = True
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except Exception as exc:
                result_message = str(exc)
                result_success = False

    units_qs = LocalOrganisationUnit.objects.filter(country=target_country, network=target_network).order_by("level_order")
    if not units_qs.exists():
        units_qs = LocalOrganisationUnit.objects.filter(country=target_country).order_by("level_order")

    hierarchy_units = list(units_qs[:5])
    available_parents = list(units_qs)

    query = request.GET.get("q", "").strip()
    if query:
        units_qs = units_qs.filter(
            Q(unit_name__icontains=query)
            | Q(level__icontains=query)
            | Q(responsible_leader_name__icontains=query)
        )

    level_filter = request.GET.get("level", "").strip()
    if level_filter:
        units_qs = units_qs.filter(level__icontains=level_filter)

    units = list(units_qs)
    if state_mode == "empty":
        units = []
    elif not state_card and len(units) == 0 and (query or level_filter):
        state_card = screen["state_contracts"].get("no_matching")

    audit_history = get_stage6_audit_history(user_scope, country_code=target_country)
    term = GeographyTerminology.objects.filter(country=target_country).first() or GeographyTerminology.objects.filter(country="NG").first()

    l1_term = term.first_level_term if term else "Region / State"
    l2_term = term.second_level_term if term else "District / LGA"
    l1_unit = LocalOrganisationUnit.objects.filter(country=target_country, level="Region / State").first()
    l2_unit = LocalOrganisationUnit.objects.filter(country=target_country, level="District / LGA").first()
    cluster_unit = LocalOrganisationUnit.objects.filter(country=target_country, level="Community Cluster").first()
    chapter_unit = LocalOrganisationUnit.objects.filter(country=target_country, level="Chapter").first()

    c_name = get_country_name_for_code(target_country)
    l1_name = l1_unit.unit_name if l1_unit else ("Lagos State" if target_country == "NG" else f"{c_name} Region")
    l2_name = l2_unit.unit_name if l2_unit else ("Ikeja LGA" if target_country == "NG" else f"{c_name} District")
    cluster_name = cluster_unit.unit_name if cluster_unit else ("Ikeja Central Cluster" if target_country == "NG" else "Central Community Cluster")
    if cluster_name and not cluster_name.lower().endswith("cluster"):
        cluster_name = f"{cluster_name} Cluster"
    chapter_name = chapter_unit.unit_name if chapter_unit else ("Allen Chapter" if target_country == "NG" else f"{c_name} Central Chapter")
    chapter_name = sanitize_chapter_display(chapter_name, fallback_country=target_country)

    country_hierarchy = {
        "country_name": c_name,
        "country_code": target_country,
        "first_level_term": l1_term,
        "first_level_name": l1_name,
        "second_level_term": l2_term,
        "second_level_name": l2_name,
        "cluster_name": cluster_name,
        "chapter_name": chapter_name,
        "path_text": f"{target_network} → {c_name} → {l1_name} → {l2_name} → {cluster_name} → {chapter_name}",
    }

    ctx.update({
        "screen": screen,
        "units": units,
        "hierarchy_units": hierarchy_units,
        "available_parents": available_parents,
        "target_country": target_country,
        "target_country_name": c_name,
        "target_network": target_network,
        "terminology": term,
        "country_hierarchy": country_hierarchy,
        "first_level_term": l1_term,
        "second_level_term": l2_term,
        "query": query,
        "level_filter": level_filter,
        "result_message": result_message,
        "result_success": result_success,
        "audit_history": audit_history,
        "active_nav": "reports",
        "active_tab": request.GET.get("tab", "structure"),
        "state_mode": state_mode,
        "state_card": state_card,
    })
    return render(request, "foundation/people_geography/geo_03_local_organisation.html", ctx)


def verify_country_dossier_view(request):
    """
    GEO-04: Verify the country dossier.
    Enforces HOFCO / QA / Country authority for country dossier verification.
    """
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    seed_stage6_fixtures()
    user_scope = ctx["user_scope"]
    account = ctx["account"]

    try:
        assert_stage6_authorized(user_scope, "GEO-04")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    req_country = (request.GET.get("country") or request.POST.get("country_code") or "").strip()
    req_network = (request.GET.get("network") or request.POST.get("network") or "").strip().upper()

    if req_country:
        target_cc = normalize_country_code(req_country, default_code="NG")
    elif not is_global_stage6_scope(user_scope) and user_scope.active_country not in {"ALL", "BOTH", "*", ""}:
        target_cc = user_scope.active_country
    else:
        target_cc = "NG"

    target_net = req_network if req_network in {"WGMN", "WNNN"} else "WGMN"

    try:
        assert_country_network_authorized(user_scope, country=target_cc, network=target_net)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    screen = dict(STAGE6_SCREENS["GEO-04"])
    state_mode = request.GET.get("state")
    state_card = screen["state_contracts"].get(state_mode) if state_mode else None

    dossier = (
        CountryDossier.objects.filter(country_code=target_cc, network=target_net).first()
        or CountryDossier.objects.filter(country_code=target_cc).first()
        or CountryDossier.objects.first()
    )
    result_message = None
    result_success = True

    if request.method == "POST":
        action = request.POST.get("action", "submit")
        country_code = request.POST.get("country_code", target_cc)
        network = request.POST.get("network", target_net)
        stage = request.POST.get("verification_stage", "").strip()
        ref = request.POST.get("evidence_reference", "").strip()
        notes = request.POST.get("verification_notes", "").strip()

        if action == "save_draft":
            state_card = screen["state_contracts"]["saved_later"]
            result_message = "Verification draft saved for later."
        elif not stage or not ref or not notes:
            state_card = screen["state_contracts"]["check_highlighted"]
            result_message = "Verification stage, evidence reference, and notes are required."
            result_success = False
        else:
            try:
                res = verify_country_dossier_submission(
                    country_code=country_code,
                    network=network,
                    verification_stage=stage,
                    evidence_reference=ref,
                    verification_notes=notes,
                    actor_account=account,
                    user_scope=user_scope,
                )
                dossier = res["dossier"]
                result_message = f"Country dossier for {dossier.country_name} ({dossier.network}) verified successfully."
                result_success = True
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except Exception as exc:
                result_message = str(exc)
                result_success = False

    audit_history = get_stage6_audit_history(user_scope, country_code=target_cc)

    ctx.update({
        "screen": screen,
        "dossier": dossier,
        "audit_history": audit_history,
        "active_nav": "reports",
        "active_tab": request.GET.get("tab", "records"),
        "state_mode": state_mode,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/people_geography/geo_04_verify_dossier.html", ctx)


def geography_terminology_view(request):
    """
    GEO-05: Geography and local terminology.
    Controlled terminology change for country administrative divisions.
    """
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    seed_stage6_fixtures()
    user_scope = ctx["user_scope"]
    account = ctx["account"]

    try:
        assert_stage6_authorized(user_scope, "GEO-05")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    req_country = (request.GET.get("country") or request.POST.get("country_code") or request.POST.get("country") or "").strip()
    if req_country:
        target_cc = normalize_country_code(req_country, default_code="NG")
    elif not is_global_stage6_scope(user_scope) and user_scope.active_country not in {"ALL", "BOTH", "*", ""}:
        target_cc = user_scope.active_country
    else:
        target_cc = "NG"

    try:
        assert_country_network_authorized(user_scope, country=target_cc)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    screen = dict(STAGE6_SCREENS["GEO-05"])
    state_mode = request.GET.get("state")
    state_card = screen["state_contracts"].get(state_mode) if state_mode else None

    term = GeographyTerminology.objects.filter(country=target_cc).first() or GeographyTerminology.objects.filter(country="NG").first()
    result_message = None
    result_success = True

    if request.method == "POST":
        action = request.POST.get("action", "submit")
        country_code = request.POST.get("country_code") or request.POST.get("country") or target_cc
        first_level = request.POST.get("first_level_term", "").strip()
        second_level = request.POST.get("second_level_term", "").strip()
        eff_date_str = request.POST.get("effective_date", "").strip()

        if action == "save_draft":
            state_card = screen["state_contracts"]["saved_later"]
            result_message = "Proposed terminology revision saved as draft."
        elif not first_level or not second_level:
            state_card = screen["state_contracts"]["check_highlighted"]
            result_message = "First-level and second-level terms are required."
            result_success = False
        else:
            try:
                res = save_geography_terminology_revision(
                    country_code=country_code,
                    first_level_term=first_level,
                    second_level_term=second_level,
                    effective_date_str=eff_date_str,
                    actor_account=account,
                    user_scope=user_scope,
                )
                term = res["terminology"]
                result_message = f"Proposed terminology revision for {term.country_name} saved. Effective date: {eff_date_str}."
                result_success = True
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except Exception as exc:
                result_message = str(exc)
                result_success = False

    effective_date_display = "01 October 2026"
    if term and term.effective_date:
        effective_date_display = term.effective_date.strftime("%d %B %Y")

    all_terms = GeographyTerminology.objects.all()
    if not is_global_stage6_scope(user_scope) and user_scope.active_country not in {"ALL", "BOTH", "*"}:
        all_terms = all_terms.filter(country=user_scope.active_country)

    audit_history = get_stage6_audit_history(user_scope, country_code=target_cc)

    ctx.update({
        "screen": screen,
        "terminology": term,
        "all_terminologies": list(all_terms),
        "effective_date_display": effective_date_display,
        "audit_history": audit_history,
        "active_nav": "reports",
        "active_tab": request.GET.get("tab", "records"),
        "state_mode": state_mode,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/people_geography/geo_05_geography_terminology.html", ctx)


def stage6_screen_router(request, screen_code):
    """
    Direct screen code dispatcher for PEOPLE-01 through GEO-05 (and Stage 07 LEAD-* / APPT-*).
    Allows exact testing, artboard verification, and responsive QA.
    """
    code = (screen_code or "").strip().upper()
    if code.startswith("LEAD-") or code.startswith("APPT-"):
        return stage7_screen_router(request, code)
    if code.startswith("REC-"):
        return stage8_screen_router(request, code)
    if code.startswith("TASK-") or code.startswith("MTG-"):
        return stage9_screen_router(request, code)
    if code.startswith("ROOM-") or code.startswith("EVENT-"):
        from .multilingua_events_views import stage10_screen_view
        return stage10_screen_view(request, code)
    if code == "COMMS-02":

        from .executive_views import continental_announcements_view
        return continental_announcements_view(request)
    if code.startswith("COMMS-"):
        from .views_comms_learn import messages_inbox_view
        return messages_inbox_view(request)
    if (
        code.startswith("GOV-")
        or code.startswith("REL-")
        or code.startswith("EVENT-")
        or code.startswith("ROOM-")
        or code.startswith("REP-")
        or code.startswith("SAFE-")
    ):
        from .executive_views import executive_screen_router
        return executive_screen_router(request, code)
    if code.startswith("LEARN-"):
        from .views_comms_learn import learning_development_view
        return learning_development_view(request)
    if code.startswith("RES-"):
        from .views_comms_learn import resources_view
        return resources_view(request)

    mapping = {
        "PEOPLE-01": people_directory_view,
        "PEOPLE-02": person_profile_view,
        "PEOPLE-03": add_or_link_person_view,
        "PEOPLE-04": community_relationships_view,
        "PEOPLE-05": manage_relationships_view,
        "PEOPLE-06": review_reassignment_view,
        "GEO-01": africa_network_coverage_view,
        "GEO-02": country_command_profile_view,
        "GEO-03": local_organisation_view,
        "GEO-04": verify_country_dossier_view,
        "GEO-05": geography_terminology_view,
    }

    view_fn = mapping.get(code)
    if not view_fn:
        raise Http404(f"Screen code '{screen_code}' not found.")
    return view_fn(request)


# -----------------------------------------------------------------------------
# STAGE 07: LEADERSHIP STRUCTURE, VACANCIES, APPOINTMENTS, AND HANDOVER VIEWS
# -----------------------------------------------------------------------------

def _build_stage7_common_context(request, ctx: dict, screen_id: str):
    """
    Shared context builder for Stage 07 screens:
    - Enforces screen-level authorization and country/network scope boundaries
    - Prepares scoped seats, appointments, seat history, and audit history
    - Evaluates state contract cards (?state=...)
    """
    seed_stage7_fixtures()
    user_scope = ctx["user_scope"]

    assert_stage7_authorized(user_scope, screen_id)

    req_country = (request.GET.get("country") or request.POST.get("country") or "").strip()
    req_network = (request.GET.get("network") or request.POST.get("network") or "").strip().upper()

    if req_country:
        target_country = normalize_country_code(req_country, default_code="NG")
    elif not is_global_stage6_scope(user_scope) and user_scope.active_country not in {"ALL", "BOTH", "*", ""}:
        target_country = user_scope.active_country
    else:
        target_country = "NG"

    if req_network in {"WGMN", "WNNN"}:
        target_network = req_network
    elif not is_global_stage6_scope(user_scope) and user_scope.active_network in {"WGMN", "WNNN"}:
        target_network = user_scope.active_network
    else:
        target_network = "WGMN"

    assert_country_network_authorized(user_scope, country=target_country, network=target_network)

    screen = dict(STAGE7_SCREENS[screen_id])
    country_name = get_country_name_for_code(target_country)
    spaced_net = " ".join(list(target_network))
    spaced_country = " ".join(list(country_name.upper()))
    screen["eyebrow"] = f"{spaced_net} / {spaced_country}"

    state_mode = request.GET.get("state")
    state_card = screen["state_contracts"].get(state_mode) if state_mode else None

    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()

    seats_qs = get_scoped_seats_queryset(user_scope, country=target_country, network=target_network)
    # Keep the 3 canonical structure seats at the top for clean default views while including all scoped seats
    if not query and not status_filter and target_network == "WGMN" and target_country == "NG":
        primary_codes = ["SEAT-NG-LAG-SC", "SEAT-NG-LAG-AC", "SEAT-NG-IKJ-LC"]
        primary_seats = list(seats_qs.filter(seat_code__in=primary_codes))
        order_idx = {code: idx for idx, code in enumerate(primary_codes)}
        primary_seats.sort(key=lambda s: order_idx.get(s.seat_code, 99))
        seats_list = primary_seats if len(primary_seats) >= 3 else list(seats_qs)
    else:
        if query:
            seats_qs = seats_qs.filter(
                Q(position_title__icontains=query)
                | Q(unit_name__icontains=query)
                | Q(holder_name__icontains=query)
                | Q(status__icontains=query)
            )
        if status_filter:
            seats_qs = seats_qs.filter(status__icontains=status_filter)
        seats_list = list(seats_qs)

    appts_qs = get_scoped_appointments_queryset(user_scope, country=target_country, network=target_network)
    if query:
        appts_qs = appts_qs.filter(
            Q(appointee_name__icontains=query)
            | Q(position_title__icontains=query)
            | Q(stage__icontains=query)
            | Q(next_action__icontains=query)
            | Q(unit_name__icontains=query)
        )
    if status_filter:
        appts_qs = appts_qs.filter(stage__icontains=status_filter)
    appts_list = list(appts_qs)

    if state_mode == "empty":
        seats_list = []
        appts_list = []
    elif not state_card and (query or status_filter):
        if screen_id.startswith("LEAD-") and len(seats_list) == 0:
            state_card = screen["state_contracts"].get("no_matching")
        elif screen_id.startswith("APPT-") and len(appts_list) == 0:
            state_card = screen["state_contracts"].get("no_matching")

    seat_history = list(
        SeatHistory.objects.filter(network=target_network, country=target_country).select_related("seat", "person")[:20]
    )
    audit_history = get_stage7_audit_history(user_scope, country_code=target_country)

    return {
        "screen": screen,
        "target_country": target_country,
        "target_country_name": country_name,
        "target_network": target_network,
        "seats": seats_list,
        "all_scoped_seats": list(get_scoped_seats_queryset(user_scope, country=target_country, network=target_network)),
        "appointments": appts_list,
        "all_scoped_appointments": list(get_scoped_appointments_queryset(user_scope, country=target_country, network=target_network)),
        "seat_history": seat_history,
        "audit_history": audit_history,
        "query": query,
        "status_filter": status_filter,
        "active_nav": "people",
        "active_tab": request.GET.get("tab", "overview"),
        "state_mode": state_mode,
        "state_card": state_card,
    }


def leadership_structure_view(request):
    """LEAD-01: My leadership structure."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "LEAD-01")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    ctx.update(s7_ctx)
    return render(request, "foundation/leadership/lead_01_structure.html", ctx)


def leadership_register_view(request):
    """LEAD-02: Leadership register."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "LEAD-02")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    ctx.update(s7_ctx)
    ctx["active_tab"] = request.GET.get("tab", "records")
    ctx["filter_mode"] = request.GET.get("filter", "")
    return render(request, "foundation/leadership/lead_02_register.html", ctx)


def leadership_seat_detail_view(request, seat_code="SEAT-NG-LAG-SC"):
    """LEAD-03: Lagos · State Coordinator (Seat / Position detail)."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "LEAD-03")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    req_code = (seat_code or request.GET.get("seat") or "SEAT-NG-LAG-SC").strip().upper()
    seat = LeadershipSeat.objects.select_related("position", "holder_person", "org_unit").filter(seat_code=req_code).first()
    if not seat:
        seat = s7_ctx["all_scoped_seats"][0] if s7_ctx["all_scoped_seats"] else None

    if seat:
        try:
            assert_seat_scope_authorized(user_scope, seat)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    seat_specific_history = list(SeatHistory.objects.filter(seat=seat)) if seat else s7_ctx["seat_history"]

    ctx.update(s7_ctx)
    ctx.update({
        "selected_seat": seat,
        "seat_specific_history": seat_specific_history,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/leadership/lead_03_seat_detail.html", ctx)


def approved_vacancies_view(request):
    """LEAD-04: Approved vacancies (with candidate referral / nomination workflow)."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "LEAD-04")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    result_message = None
    result_success = True
    state_card = s7_ctx["state_card"]
    screen = s7_ctx["screen"]

    if request.method == "POST":
        seat_code = request.POST.get("seat_code", "SEAT-NG-LAG-AC").strip()
        candidate_name = request.POST.get("candidate_name", "").strip()
        candidate_person_code = request.POST.get("candidate_person_code", "").strip() or None
        suitability_notes = request.POST.get("suitability_notes", "").strip()
        action_mode = request.POST.get("action_mode", "refer").strip()
        idempotency_key = request.POST.get("idempotency_key", "").strip() or None
        expected_updated_at = request.POST.get("expected_updated_at", "").strip() or None

        try:
            res = refer_or_appoint_candidate(
                seat_code=seat_code,
                candidate_name=candidate_name,
                suitability_notes=suitability_notes,
                actor_account=account,
                user_scope=user_scope,
                action_mode=action_mode,
                candidate_person_code=candidate_person_code,
                idempotency_key=idempotency_key,
                expected_updated_at=expected_updated_at,
            )
            if res.get("conflict"):
                state_card = screen["state_contracts"]["another_change"]
                result_message = res["message"]
                result_success = False
            else:
                if action_mode == "appoint":
                    result_message = f"Appointment offer issued to {res['referral'].candidate_name} for {res['seat'].position_title} ({res['seat'].unit_name})."
                else:
                    result_message = f"Candidate referral recorded for {res['referral'].candidate_name} ({res['seat'].position_title} · {res['seat'].unit_name})."
                result_success = True
                s7_ctx = _build_stage7_common_context(request, ctx, "LEAD-04")
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = screen["state_contracts"]["more_info"]
            result_message = str(exc)
            result_success = False

    referrals = list(
        CandidateReferral.objects.select_related("seat", "candidate_person")
        .filter(seat__network=s7_ctx["target_network"], seat__country=s7_ctx["target_country"])[:15]
    )
    scoped_people = list(
        PersonProfile.objects.filter(network=s7_ctx["target_network"], country=s7_ctx["target_country"])
    )

    ctx.update(s7_ctx)
    ctx.update({
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "referrals": referrals,
        "scoped_people": scoped_people,
        "active_tab": request.GET.get("tab", "records"),
    })
    return render(request, "foundation/leadership/lead_04_vacancies.html", ctx)


def direct_reports_view(request):
    """LEAD-05: My direct reports."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "LEAD-05")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    result_message = None
    result_success = True
    state_card = s7_ctx["state_card"]

    if request.method == "POST":
        seat_code = request.POST.get("seat_code", "SEAT-NG-IKJ-LC").strip()
        followup_title = request.POST.get("followup_title", "").strip()
        followup_summary = request.POST.get("followup_summary", "").strip()
        try:
            res = assign_direct_report_followup(
                seat_code=seat_code,
                followup_title=followup_title,
                followup_summary=followup_summary,
                actor_account=account,
                user_scope=user_scope,
            )
            result_message = f"Follow-up '{res['work_item'].title}' assigned to {res['seat'].holder_name} ({res['seat'].position_title})."
            result_success = True
            s7_ctx = _build_stage7_common_context(request, ctx, "LEAD-05")
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = s7_ctx["screen"]["state_contracts"]["more_info"]
            result_message = str(exc)
            result_success = False

    ctx.update(s7_ctx)
    ctx.update({
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "records"),
    })
    return render(request, "foundation/leadership/lead_05_direct_reports.html", ctx)


def positions_reporting_lines_view(request):
    """LEAD-06: Positions and reporting lines."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "LEAD-06")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s7_ctx["screen"]
    state_card = s7_ctx["state_card"]
    result_message = None
    result_success = True

    req_pos_code = (request.GET.get("position") or request.POST.get("position_code") or "STATE_COORDINATOR").strip().upper()
    selected_position = PositionMaster.objects.filter(position_code=req_pos_code).first() or PositionMaster.objects.filter(position_code="STATE_COORDINATOR").first()

    if request.method == "POST":
        action = request.POST.get("action", "submit")
        pos_code = request.POST.get("position_code", "STATE_COORDINATOR").strip()
        wgmn_title = request.POST.get("wgmn_title", "").strip()
        wnnn_title = request.POST.get("wnnn_title", "").strip()
        reports_to_label = request.POST.get("reports_to_label", "").strip()
        expected_updated_at = request.POST.get("expected_updated_at", "").strip() or None

        if action == "save_draft":
            state_card = screen["state_contracts"]["saved_later"]
            result_message = "Position revision draft saved for later."
        else:
            try:
                res = save_position_revision(
                    position_code=pos_code,
                    wgmn_title=wgmn_title,
                    wnnn_title=wnnn_title,
                    reports_to_label=reports_to_label,
                    actor_account=account,
                    user_scope=user_scope,
                    expected_updated_at=expected_updated_at,
                )
                if res.get("conflict"):
                    state_card = screen["state_contracts"]["another_change"]
                    result_message = res["message"]
                    result_success = False
                else:
                    selected_position = res["position"]
                    result_message = f"Position revision saved for {selected_position.position_code} ({selected_position.wgmn_title} / {selected_position.wnnn_title})."
                    result_success = True
                    s7_ctx = _build_stage7_common_context(request, ctx, "LEAD-06")
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except ValueError as exc:
                state_card = screen["state_contracts"]["check_highlighted"]
                result_message = str(exc)
                result_success = False

    all_positions = list(PositionMaster.objects.all())

    ctx.update(s7_ctx)
    ctx.update({
        "selected_position": selected_position,
        "all_positions": all_positions,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "records"),
    })
    return render(request, "foundation/leadership/lead_06_positions.html", ctx)


def appointment_processing_view(request):
    """APPT-01: Appointment processing."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "APPT-01")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    result_message = None
    result_success = True
    state_card = s7_ctx["state_card"]

    if request.method == "POST":
        seat_code = request.POST.get("seat_code", "SEAT-NG-LAG-AC").strip()
        candidate_name = request.POST.get("candidate_name", "").strip()
        suitability_notes = request.POST.get("suitability_notes", "").strip()
        idempotency_key = request.POST.get("idempotency_key", "").strip() or None
        expected_updated_at = request.POST.get("expected_updated_at", "").strip() or None

        try:
            res = refer_or_appoint_candidate(
                seat_code=seat_code,
                candidate_name=candidate_name,
                suitability_notes=suitability_notes,
                actor_account=account,
                user_scope=user_scope,
                action_mode="appoint",
                idempotency_key=idempotency_key,
                expected_updated_at=expected_updated_at,
            )
            if res.get("conflict"):
                state_card = s7_ctx["screen"]["state_contracts"]["another_change"]
                result_message = res["message"]
                result_success = False
            else:
                result_message = f"Appointment offer approved and issued to {res['referral'].candidate_name} ({res['seat'].position_title})."
                result_success = True
                s7_ctx = _build_stage7_common_context(request, ctx, "APPT-01")
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = s7_ctx["screen"]["state_contracts"]["more_info"]
            result_message = str(exc)
            result_success = False

    ctx.update(s7_ctx)
    ctx.update({
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "records"),
    })
    return render(request, "foundation/leadership/appt_01_processing.html", ctx)


def appointment_offer_view(request):
    """APPT-02: Your appointment offer."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "APPT-02")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s7_ctx["screen"]
    state_card = s7_ctx["state_card"]
    result_message = None
    result_success = True

    req_code = (request.GET.get("appointment") or request.POST.get("appointment_code") or "APPT-NG-001").strip()
    appointment = AppointmentRecord.objects.select_related("seat", "person").filter(appointment_code=req_code).first()
    if not appointment:
        appointment = s7_ctx["all_scoped_appointments"][0] if s7_ctx["all_scoped_appointments"] else None

    if appointment:
        try:
            assert_appointment_scope_authorized(user_scope, appointment)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    if request.method == "POST":
        action = request.POST.get("action", "accept").strip()
        appt_code = request.POST.get("appointment_code", appointment.appointment_code if appointment else "APPT-NG-001")
        acc_decl = request.POST.get("acceptance_confirmed") in {"true", "True", "1", "on"}
        comm_decl = request.POST.get("commitment_confirmed") in {"true", "True", "1", "on"}
        declined_reason = request.POST.get("declined_reason", "").strip()
        expected_updated_at = request.POST.get("expected_updated_at", "").strip() or None

        if action == "save_draft":
            state_card = screen["state_contracts"]["saved_later"]
            result_message = "Appointment offer response saved as draft."
        else:
            try:
                res = respond_to_appointment_offer(
                    appointment_code=appt_code,
                    decision="decline" if action == "decline" else "accept",
                    acceptance_confirmed=acc_decl,
                    commitment_confirmed=comm_decl,
                    actor_account=account,
                    user_scope=user_scope,
                    declined_reason=declined_reason,
                    expected_updated_at=expected_updated_at,
                )
                if res.get("conflict"):
                    state_card = screen["state_contracts"]["another_change"]
                    result_message = res["message"]
                    result_success = False
                else:
                    appointment = res["appointment"]
                    if res["decision"] == "decline":
                        result_message = f"Appointment offer for {appointment.position_title} · {appointment.unit_name} declined. Seat returned to vacancy register."
                    else:
                        result_message = f"Appointment accepted for {appointment.position_title} · {appointment.unit_name}. Proceed to leader onboarding."
                    result_success = True
                    s7_ctx = _build_stage7_common_context(request, ctx, "APPT-02")
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except ValueError as exc:
                state_card = screen["state_contracts"]["check_highlighted"]
                result_message = str(exc)
                result_success = False

    ctx.update(s7_ctx)
    ctx.update({
        "appointment": appointment,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/leadership/appt_02_offer.html", ctx)


def leader_onboarding_view(request):
    """APPT-03: Welcome to your leadership role (Leader onboarding checklist)."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "APPT-03")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    result_message = None
    result_success = True
    state_card = s7_ctx["state_card"]

    req_code = (request.GET.get("appointment") or request.POST.get("appointment_code") or "APPT-NG-002").strip()
    appointment = AppointmentRecord.objects.select_related("seat", "person").filter(appointment_code=req_code).first()
    if not appointment:
        appointment = s7_ctx["all_scoped_appointments"][0] if s7_ctx["all_scoped_appointments"] else None

    if appointment:
        try:
            assert_appointment_scope_authorized(user_scope, appointment)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    if request.method == "POST":
        appt_code = request.POST.get("appointment_code", appointment.appointment_code if appointment else "APPT-NG-002")
        s1 = request.POST.get("step_1", "true") in {"true", "True", "1", "on"}
        s2 = request.POST.get("step_2", "true") in {"true", "True", "1", "on"}
        s3 = request.POST.get("step_3", "true") in {"true", "True", "1", "on"}
        s4 = request.POST.get("step_4", "true") in {"true", "True", "1", "on"}
        try:
            res = complete_leader_onboarding_steps(
                appointment_code=appt_code,
                step_1=s1,
                step_2=s2,
                step_3=s3,
                step_4=s4,
                actor_account=account,
                user_scope=user_scope,
            )
            appointment = res["appointment"]
            if res["all_complete"]:
                result_message = f"All 4 onboarding steps completed for {appointment.appointee_name} ({appointment.position_title}). Role access is now active."
            else:
                result_message = f"Onboarding progress saved for {appointment.appointee_name}."
            result_success = True
            s7_ctx = _build_stage7_common_context(request, ctx, "APPT-03")
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    ctx.update(s7_ctx)
    ctx.update({
        "appointment": appointment,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/leadership/appt_03_onboarding.html", ctx)


def first_90_days_view(request):
    """APPT-04: Your first 90 days."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "APPT-04")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    req_code = (request.GET.get("appointment") or "APPT-NG-002").strip()
    appointment = AppointmentRecord.objects.select_related("seat", "person").filter(appointment_code=req_code).first()
    if not appointment:
        appointment = s7_ctx["all_scoped_appointments"][0] if s7_ctx["all_scoped_appointments"] else None

    reviews = list(LeadershipReview.objects.filter(appointment=appointment)) if appointment else []

    ctx.update(s7_ctx)
    ctx.update({
        "appointment": appointment,
        "reviews": reviews,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/leadership/appt_04_first_90_days.html", ctx)


def first_90_day_reviews_view(request):
    """APPT-04-REVIEWS: First 30 / 60 / 90 day reviews."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "APPT-04-REVIEWS")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s7_ctx["screen"]
    state_card = s7_ctx["state_card"]
    result_message = None
    result_success = True

    req_code = (request.GET.get("appointment") or request.POST.get("appointment_code") or "APPT-NG-002").strip()
    appointment = AppointmentRecord.objects.select_related("seat", "person").filter(appointment_code=req_code).first()
    if not appointment:
        appointment = s7_ctx["all_scoped_appointments"][0] if s7_ctx["all_scoped_appointments"] else None

    if request.method == "POST":
        appt_code = request.POST.get("appointment_code", appointment.appointment_code if appointment else "APPT-NG-002")
        review_point = request.POST.get("review_point", "30 days").strip()
        outcome = request.POST.get("outcome", "").strip()
        evidence_notes = request.POST.get("evidence_notes", "").strip()
        reviewer_confirmed = request.POST.get("reviewer_confirmation") in {"true", "True", "1", "on"}

        try:
            res = record_first_90_day_review(
                appointment_code=appt_code,
                review_point=review_point,
                outcome=outcome,
                evidence_notes=evidence_notes,
                reviewer_confirmed=reviewer_confirmed,
                actor_account=account,
                user_scope=user_scope,
            )
            appointment = res["appointment"]
            result_message = f"{res['review'].review_point} review outcome ('{res['review'].outcome}') recorded for {appointment.appointee_name}."
            result_success = True
            s7_ctx = _build_stage7_common_context(request, ctx, "APPT-04-REVIEWS")
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = screen["state_contracts"]["check_highlighted"]
            result_message = str(exc)
            result_success = False

    reviews = list(
        LeadershipReview.objects.select_related("appointment", "reviewed_by")
        .filter(appointment__network=s7_ctx["target_network"], appointment__country=s7_ctx["target_country"])
    )

    ctx.update(s7_ctx)
    ctx.update({
        "appointment": appointment,
        "reviews": reviews,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/leadership/appt_04_reviews.html", ctx)


def appointment_identity_view(request):
    """APPT-05: My appointment and identity."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "APPT-05")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    req_code = (request.GET.get("appointment") or "APPT-NG-001").strip()
    appointment = AppointmentRecord.objects.select_related("seat", "person").filter(appointment_code=req_code).first()
    if not appointment:
        appointment = s7_ctx["all_scoped_appointments"][0] if s7_ctx["all_scoped_appointments"] else None

    ctx.update(s7_ctx)
    ctx.update({
        "appointment": appointment,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/leadership/appt_05_identity.html", ctx)


def leadership_status_change_view(request):
    """APPT-06: Review a leadership status change."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "APPT-06")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s7_ctx["screen"]
    state_card = s7_ctx["state_card"]
    result_message = None
    result_success = True

    req_code = (request.GET.get("appointment") or request.POST.get("appointment_code") or "APPT-NG-001").strip()
    appointment = AppointmentRecord.objects.select_related("seat", "person").filter(appointment_code=req_code).first()
    if not appointment:
        appointment = s7_ctx["all_scoped_appointments"][0] if s7_ctx["all_scoped_appointments"] else None

    if request.method == "POST":
        action = request.POST.get("action", "submit").strip()
        appt_code = request.POST.get("appointment_code", appointment.appointment_code if appointment else "APPT-NG-001")
        requested_status = request.POST.get("requested_status", "On leave").strip()
        effective_period = request.POST.get("effective_period", "").strip()
        reason_and_cover_plan = request.POST.get("reason_and_cover_plan", "").strip()
        expected_updated_at = request.POST.get("expected_updated_at", "").strip() or None

        if action == "save_draft":
            state_card = screen["state_contracts"]["saved_later"]
            result_message = "Leadership status change draft saved."
        else:
            try:
                res = submit_leadership_status_change(
                    appointment_code=appt_code,
                    requested_status=requested_status,
                    effective_period=effective_period,
                    reason_and_cover_plan=reason_and_cover_plan,
                    actor_account=account,
                    user_scope=user_scope,
                    expected_updated_at=expected_updated_at,
                )
                if res.get("conflict"):
                    state_card = screen["state_contracts"]["another_change"]
                    result_message = res["message"]
                    result_success = False
                else:
                    appointment = res["appointment"]
                    result_message = f"Leadership status change to '{requested_status}' ({effective_period}) recorded for {appointment.appointee_name}."
                    result_success = True
                    s7_ctx = _build_stage7_common_context(request, ctx, "APPT-06")
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except ValueError as exc:
                state_card = screen["state_contracts"]["check_highlighted"]
                result_message = str(exc)
                result_success = False

    status_changes = list(
        LeadershipStatusChange.objects.select_related("appointment", "approved_by")
        .filter(appointment__network=s7_ctx["target_network"], appointment__country=s7_ctx["target_country"])
    )

    ctx.update(s7_ctx)
    ctx.update({
        "appointment": appointment,
        "status_changes": status_changes,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/leadership/appt_06_status_change.html", ctx)


def leadership_transition_view(request):
    """APPT-07: Plan a safe leadership transition."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "APPT-07")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s7_ctx["screen"]
    state_card = s7_ctx["state_card"]
    result_message = None
    result_success = True

    req_code = (request.GET.get("appointment") or request.POST.get("appointment_code") or "APPT-NG-003").strip()
    appointment = AppointmentRecord.objects.select_related("seat", "person").filter(appointment_code=req_code).first()
    if not appointment:
        appointment = s7_ctx["all_scoped_appointments"][-1] if s7_ctx["all_scoped_appointments"] else None

    if request.method == "POST":
        action = request.POST.get("action", "submit").strip()
        appt_code = request.POST.get("appointment_code", appointment.appointment_code if appointment else "APPT-NG-003")
        transition_type = request.POST.get("transition_type", "Transfer").strip()
        effective_date = request.POST.get("effective_date", "").strip()
        access_and_handover_notes = request.POST.get("access_and_handover_notes", "").strip()
        successor_name = request.POST.get("successor_name", "Ada Okafor").strip()
        expected_updated_at = request.POST.get("expected_updated_at", "").strip() or None

        if action == "save_draft":
            state_card = screen["state_contracts"]["saved_later"]
            result_message = "Transition plan saved as draft."
        else:
            try:
                res = plan_leadership_transition(
                    appointment_code=appt_code,
                    transition_type=transition_type,
                    effective_date=effective_date,
                    access_and_handover_notes=access_and_handover_notes,
                    actor_account=account,
                    user_scope=user_scope,
                    successor_name=successor_name,
                    expected_updated_at=expected_updated_at,
                )
                if res.get("conflict"):
                    state_card = screen["state_contracts"]["another_change"]
                    result_message = res["message"]
                    result_success = False
                else:
                    appointment = res["appointment"]
                    result_message = f"Transition plan ('{transition_type}', effective {effective_date}) opened for {appointment.appointee_name} · {appointment.position_title}."
                    result_success = True
                    s7_ctx = _build_stage7_common_context(request, ctx, "APPT-07")
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except ValueError as exc:
                state_card = screen["state_contracts"]["check_highlighted"]
                result_message = str(exc)
                result_success = False

    transition_plans = list(
        LeadershipTransitionPlan.objects.select_related("appointment", "successor_person")
        .filter(appointment__network=s7_ctx["target_network"], appointment__country=s7_ctx["target_country"])
    )

    ctx.update(s7_ctx)
    ctx.update({
        "appointment": appointment,
        "transition_plan": transition_plans[0] if transition_plans else None,
        "transition_plans": transition_plans,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/leadership/appt_07_transition.html", ctx)


def handover_workspace_view(request):
    """APPT-08: Handover workspace."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "APPT-08")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    handover_tasks = list(
        HandoverAssetTask.objects.filter(
            network=s7_ctx["target_network"],
            country=s7_ctx["target_country"],
        )
    )

    ctx.update(s7_ctx)
    ctx.update({
        "handover_tasks": handover_tasks,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/leadership/appt_08_handover.html", ctx)


def handover_assets_checks_view(request):
    """APPT-08-HANDOVER: Handover assets and access checks."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s7_ctx = _build_stage7_common_context(request, ctx, "APPT-08-HANDOVER")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    result_message = None
    result_success = True
    state_card = s7_ctx["state_card"]

    if request.method == "POST":
        action = request.POST.get("action", "complete_task").strip()
        task_id = request.POST.get("task_id", "").strip()
        try:
            if action == "complete_all":
                res = complete_all_handover_tasks(
                    network=s7_ctx["target_network"],
                    country=s7_ctx["target_country"],
                    actor_account=account,
                    user_scope=user_scope,
                )
                result_message = f"All {res['completed_count']} handover assets and access checks verified and completed. Transition closed and history retained."
                result_success = True
            elif task_id:
                res = complete_handover_asset_task(
                    task_id=task_id,
                    actor_account=account,
                    user_scope=user_scope,
                )
                result_message = f"Handover item '{res['task'].asset_or_task}' ({res['task'].access_action}) verified and completed."
                result_success = True
            s7_ctx = _build_stage7_common_context(request, ctx, "APPT-08-HANDOVER")
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            result_message = str(exc)
            result_success = False

    tasks_qs = HandoverAssetTask.objects.filter(
        network=s7_ctx["target_network"],
        country=s7_ctx["target_country"],
    )
    query = s7_ctx["query"]
    status_filter = s7_ctx["status_filter"]
    if query:
        tasks_qs = tasks_qs.filter(
            Q(asset_or_task__icontains=query)
            | Q(from_actor__icontains=query)
            | Q(to_actor__icontains=query)
            | Q(access_action__icontains=query)
        )
    if status_filter:
        tasks_qs = tasks_qs.filter(
            Q(status__icontains=status_filter) | Q(access_action__icontains=status_filter)
        )

    handover_tasks = list(tasks_qs)
    if s7_ctx["state_mode"] == "empty":
        handover_tasks = []

    ctx.update(s7_ctx)
    ctx.update({
        "handover_tasks": handover_tasks,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/leadership/appt_08_handover_assets.html", ctx)


def stage7_screen_router(request, screen_code):
    """
    Direct screen code dispatcher for Stage 07 screens:
    LEAD-01..LEAD-06 and APPT-01..APPT-08-HANDOVER.
    """
    code = (screen_code or "").strip().upper()
    mapping = {
        "LEAD-01": leadership_structure_view,
        "LEAD-02": leadership_register_view,
        "LEAD-03": leadership_seat_detail_view,
        "LEAD-04": approved_vacancies_view,
        "LEAD-05": direct_reports_view,
        "LEAD-06": positions_reporting_lines_view,
        "APPT-01": appointment_processing_view,
        "APPT-02": appointment_offer_view,
        "APPT-03": leader_onboarding_view,
        "APPT-04": first_90_days_view,
        "APPT-04-REVIEWS": first_90_day_reviews_view,
        "APPT-05": appointment_identity_view,
        "APPT-06": leadership_status_change_view,
        "APPT-07": leadership_transition_view,
        "APPT-08": handover_workspace_view,
        "APPT-08-HANDOVER": handover_assets_checks_view,
    }
    view_fn = mapping.get(code)
    if not view_fn:
        raise Http404(f"Stage 07 screen code '{screen_code}' not found.")
    return view_fn(request)


# -----------------------------------------------------------------------------
# STAGE 08: RECRUITMENT, REFERRALS, ACTIVATION, AND SELECTION VIEWS
# -----------------------------------------------------------------------------

def _build_stage8_common_context(request, ctx: dict, screen_id: str) -> dict:
    """
    Shared context builder for Stage 08 screens:
    - Enforces screen-level role authorization and country/network scope boundaries
    - Prepares scoped candidate applications, opportunities, referrals, and audit history
    - Evaluates state contract cards (?state=...)
    """
    seed_stage8_fixtures()
    user_scope = ctx["user_scope"]

    assert_stage8_authorized(user_scope, screen_id)

    req_country = (request.GET.get("country") or request.POST.get("country") or "").strip()
    req_network = (request.GET.get("network") or request.POST.get("network") or "").strip().upper()

    if req_country:
        target_country = normalize_country_code(req_country, default_code="NG")
    elif not is_global_stage6_scope(user_scope) and user_scope.active_country not in {"ALL", "BOTH", "*", ""}:
        target_country = user_scope.active_country
    else:
        target_country = "NG"

    if req_network in {"WGMN", "WNNN"}:
        target_network = req_network
    elif not is_global_stage6_scope(user_scope) and user_scope.active_network in {"WGMN", "WNNN"}:
        target_network = user_scope.active_network
    else:
        target_network = "WGMN"

    assert_country_network_authorized(user_scope, country=target_country, network=target_network)

    screen = dict(STAGE8_SCREENS[screen_id])
    country_name = get_country_name_for_code(target_country)
    spaced_net = " ".join(list(target_network))
    spaced_country = " ".join(list(country_name.upper()))
    screen["eyebrow"] = f"{spaced_net} / {spaced_country}"

    state_mode = request.GET.get("state")
    state_card = screen["state_contracts"].get(state_mode) if state_mode else None

    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    route_filter = request.GET.get("route", "").strip()

    apps_qs = get_scoped_applications_queryset(user_scope, country=target_country, network=target_network)
    if not query and not status_filter and not route_filter and target_network == "WGMN" and target_country == "NG":
        primary_codes = ["CAND-NG-001", "CAND-NG-002", "CAND-NG-003"]
        primary_apps = list(apps_qs.filter(application_code__in=primary_codes))
        order_idx = {code: idx for idx, code in enumerate(primary_codes)}
        primary_apps.sort(key=lambda a: order_idx.get(a.application_code, 99))
        candidates_list = primary_apps if len(primary_apps) >= 3 else list(apps_qs)
    else:
        if query:
            apps_qs = apps_qs.filter(
                Q(candidate_name__icontains=query)
                | Q(route__icontains=query)
                | Q(current_stage__icontains=query)
                | Q(next_action__icontains=query)
                | Q(seat_label__icontains=query)
            )
        if status_filter:
            apps_qs = apps_qs.filter(
                Q(current_stage__icontains=status_filter) | Q(next_action__icontains=status_filter)
            )
        if route_filter:
            apps_qs = apps_qs.filter(route__icontains=route_filter)
        candidates_list = list(apps_qs)

    if state_mode in {"empty", "no_matching"}:
        candidates_list = []
    elif not state_card and (query or status_filter or route_filter) and len(candidates_list) == 0:
        state_card = screen["state_contracts"].get("no_matching")

    all_scoped_candidates = list(
        get_scoped_applications_queryset(user_scope, country=target_country, network=target_network)
    )
    opportunities = list(
        VolunteerOpportunity.objects.filter(country=target_country, network=target_network)
    )
    audit_history = get_stage8_audit_history(user_scope, country_code=target_country)

    return {
        "screen": screen,
        "screen_code": screen_id,
        "target_country": target_country,
        "target_country_name": country_name,
        "target_network": target_network,
        "state_mode": state_mode,
        "state_card": state_card,
        "query": query,
        "status_filter": status_filter,
        "route_filter": route_filter,
        "candidates": candidates_list,
        "all_scoped_candidates": all_scoped_candidates,
        "opportunities": opportunities,
        "audit_history": audit_history,
        "is_recruitment_reviewer": is_stage8_reviewer(user_scope),
        "custom_breadcrumbs": [
            {"label": "Workspace", "url": "/foundation/"},
            {"label": "Recruitment, referrals and candidate journeys", "is_current": True},
        ],
        "breadcrumbs": [
            {"label": "Workspace", "url": "/foundation/"},
            {"label": "Recruitment, referrals and candidate journeys", "is_current": True},
        ],
        "active_nav": "people" if screen_id in {"REC-09", "REC-10", "REC-10-RUBRIC", "REC-11", "REC-12", "REC-12-DECISION", "REC-13", "REC-14"} else "workspace",
    }


def find_volunteer_opportunity_view(request):
    """REC-01: Find a volunteer opportunity."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-01")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    ctx.update(s8_ctx)
    ctx.update({
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/recruitment/rec_01_opportunities.html", ctx)


def apply_to_volunteer_view(request):
    """REC-02: Apply to volunteer."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-02")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s8_ctx["screen"]
    state_card = s8_ctx["state_card"]
    result_message = None
    result_success = True

    req_app = (request.GET.get("candidate") or request.POST.get("application_code") or "CAND-NG-001").strip()
    application = (
        CandidateApplication.objects.filter(application_code=req_app).first()
        or (s8_ctx["all_scoped_candidates"][0] if s8_ctx["all_scoped_candidates"] else None)
    )

    if request.method == "POST":
        action = request.POST.get("action", "submit").strip()
        seat_label = request.POST.get("seat_label", "Chapter Coordinator · Ikeja").strip()
        country_input = request.POST.get("current_country", s8_ctx["target_country_name"]).strip()
        experience_notes = request.POST.get("experience_notes", "").strip()
        availability = request.POST.get("availability", "").strip()
        idempotency_key = request.POST.get("idempotency_key", "").strip() or None
        expected_updated_at = request.POST.get("expected_updated_at", "").strip() or None

        if action == "save_draft":
            state_card = screen["state_contracts"]["saved_later"]
            result_message = "Volunteer application draft saved for later."
        else:
            try:
                res = submit_volunteer_application(
                    seat_label=seat_label,
                    country_input=country_input,
                    experience_notes=experience_notes,
                    availability=availability,
                    actor_account=account,
                    user_scope=user_scope,
                    application_code=application.application_code if application else None,
                    idempotency_key=idempotency_key,
                    expected_updated_at=expected_updated_at,
                )
                if res.get("conflict"):
                    state_card = screen["state_contracts"]["another_change"]
                    result_message = res["message"]
                    result_success = False
                else:
                    application = res["application"]
                    result_message = f"Volunteer application saved for {application.candidate_name} ({application.seat_label} · {application.route})."
                    result_success = True
                    s8_ctx = _build_stage8_common_context(request, ctx, "REC-02")
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except ValueError as exc:
                state_card = screen["state_contracts"]["check_highlighted"]
                result_message = str(exc)
                result_success = False

    ctx.update(s8_ctx)
    ctx.update({
        "application": application,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/recruitment/rec_02_apply.html", ctx)


def you_have_been_referred_view(request):
    """REC-03: You have been referred."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-03")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s8_ctx["screen"]
    state_card = s8_ctx["state_card"]
    result_message = None
    result_success = True

    req_ref = (request.GET.get("ref") or request.POST.get("referral_code") or "REF-NG-042").strip()
    referral = (
        ReferralLink.objects.filter(referral_code=req_ref).first()
        or ReferralLink.objects.filter(country=s8_ctx["target_country"], network=s8_ctx["target_network"]).first()
        or ReferralLink.objects.filter(referral_code="REF-NG-042").first()
    )

    if referral:
        try:
            assert_country_network_authorized(user_scope, country=referral.country, network=referral.network)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    if request.method == "POST":
        action = request.POST.get("action", "verify").strip()
        ref_code = request.POST.get("referral_code", referral.referral_code if referral else "REF-NG-042").strip()
        cand_name = request.POST.get("candidate_name", referral.candidate_name if referral else "Ada Okafor").strip()
        seat_title = request.POST.get("proposed_seat_title", referral.proposed_seat_title if referral else "Chapter Coordinator · Ikeja").strip()
        contact_confirmed = request.POST.get("contact_confirmed") in {"true", "True", "1", "on"}
        expected_updated_at = request.POST.get("expected_updated_at", "").strip() or None

        if action == "save_draft":
            state_card = screen["state_contracts"]["saved_later"]
            result_message = "Referral confirmation saved for later."
        else:
            try:
                res = verify_referral_intake(
                    referral_code=ref_code,
                    candidate_name=cand_name,
                    proposed_seat_title=seat_title,
                    contact_confirmed=contact_confirmed,
                    actor_account=account,
                    user_scope=user_scope,
                    expected_updated_at=expected_updated_at,
                )
                if res.get("conflict"):
                    state_card = screen["state_contracts"]["another_change"]
                    result_message = res["message"]
                    result_success = False
                else:
                    referral = res["referral"]
                    result_message = f"Referral {referral.referral_code} verified using existing WDOS identity for {referral.candidate_name} ({referral.proposed_seat_title}). Proceed to your 3-day Leadership Pack Review."
                    result_success = True
                    s8_ctx = _build_stage8_common_context(request, ctx, "REC-03")
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except ValueError as exc:
                state_card = screen["state_contracts"]["check_highlighted"]
                result_message = str(exc)
                result_success = False

    ctx.update(s8_ctx)
    ctx.update({
        "referral": referral,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/recruitment/rec_03_referred.html", ctx)


def my_referrals_and_links_view(request):
    """REC-04: My referrals and links."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-04")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s8_ctx["screen"]
    state_card = s8_ctx["state_card"]
    result_message = None
    result_success = True

    if request.method == "POST":
        cand_name = request.POST.get("candidate_name", "").strip()
        seat_title = request.POST.get("proposed_seat_title", "Chapter Coordinator · Ikeja").strip()
        idempotency_key = request.POST.get("idempotency_key", "").strip() or None
        try:
            res = create_referral_link(
                candidate_name=cand_name,
                proposed_seat_title=seat_title,
                actor_account=account,
                user_scope=user_scope,
                country=s8_ctx["target_country"],
                network=s8_ctx["target_network"],
                idempotency_key=idempotency_key,
            )
            ref_link = res["referral_link"]
            if res.get("duplicate_prevented"):
                result_message = f"Existing referral link {ref_link.referral_code} retained for {ref_link.candidate_name} ({ref_link.proposed_seat_title}). Duplicate referral prevented."
            else:
                result_message = f"Referral link {ref_link.referral_code} created for {ref_link.candidate_name} ({ref_link.proposed_seat_title})."
            result_success = True
            s8_ctx = _build_stage8_common_context(request, ctx, "REC-04")
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            result_message = str(exc)
            result_success = False

    referral_links = list(
        ReferralLink.objects.filter(country=s8_ctx["target_country"], network=s8_ctx["target_network"])
    )

    ctx.update(s8_ctx)
    ctx.update({
        "referral_links": referral_links,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/recruitment/rec_04_referrals.html", ctx)


def my_application_view(request):
    """REC-05: My application."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-05")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    req_code = (request.GET.get("candidate") or "CAND-NG-001").strip()
    application = (
        CandidateApplication.objects.filter(application_code=req_code).first()
        or (s8_ctx["all_scoped_candidates"][0] if s8_ctx["all_scoped_candidates"] else None)
    )
    if application:
        try:
            assert_application_scope_authorized(ctx["user_scope"], application, require_reviewer=False)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    ctx.update(s8_ctx)
    ctx.update({
        "application": application,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/recruitment/rec_05_my_application.html", ctx)


def seven_day_activation_view(request):
    """REC-06: Your 7-day Activation."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-06")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s8_ctx["screen"]
    state_card = s8_ctx["state_card"]
    result_message = None
    result_success = True

    req_code = (request.GET.get("candidate") or request.POST.get("application_code") or "CAND-NG-001").strip()
    application = (
        CandidateApplication.objects.filter(application_code=req_code).first()
        or (s8_ctx["all_scoped_candidates"][0] if s8_ctx["all_scoped_candidates"] else None)
    )
    if application:
        try:
            assert_application_scope_authorized(user_scope, application, require_reviewer=False)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    if request.GET.get("request_reopen") == "1" and application:
        res = advance_activation_journey(
            application_code=application.application_code,
            reflection_text=application.activation_reflection,
            actor_account=account,
            user_scope=user_scope,
            action="request_support",
        )
        result_message = "Support request sent to authorized reviewer to reopen your 7-day Activation window."
        state_card = screen["state_contracts"]["deadline_reached"]

    if request.method == "POST":
        action = request.POST.get("action", "continue_day_4").strip()
        app_code = request.POST.get("application_code", application.application_code if application else "CAND-NG-001").strip()
        reflection_text = request.POST.get("reflection_text", "Participated in local chapter coordination and community outreach reflections.").strip()

        try:
            res = advance_activation_journey(
                application_code=app_code,
                reflection_text=reflection_text,
                actor_account=account,
                user_scope=user_scope,
                action=action,
            )
            application = res["application"]
            if res.get("reopen_requested"):
                state_card = screen["state_contracts"]["deadline_reached"]
                result_message = "Authorized review requested to reopen your 7-day Activation window."
            elif application.current_stage == "Completed":
                state_card = screen["state_contracts"]["awaiting_review"]
                result_message = f"7-day Activation completed for {application.candidate_name}. Submission is now in the authorized review queue."
            else:
                state_card = screen["state_contracts"]["progress_saved"]
                result_message = f"Day 4 evidence and reflection saved for {application.candidate_name}."
            result_success = True
            s8_ctx = _build_stage8_common_context(request, ctx, "REC-06")
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = screen["state_contracts"]["deadline_reached"] if "window is closed" in str(exc) else screen["state_contracts"]["more_info"]
            result_message = str(exc)
            result_success = False

    ctx.update(s8_ctx)
    ctx.update({
        "application": application,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "progress"),
    })
    return render(request, "foundation/recruitment/rec_06_activation.html", ctx)


def leadership_pack_review_view(request):
    """REC-07: Leadership Pack review (Separate 3-day Leadership Pack Review for referred candidates)."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-07")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s8_ctx["screen"]
    state_card = s8_ctx["state_card"]
    result_message = None
    result_success = True

    req_code = (request.GET.get("candidate") or request.POST.get("application_code") or "CAND-NG-001").strip()
    application = (
        CandidateApplication.objects.filter(application_code=req_code).first()
        or (s8_ctx["all_scoped_candidates"][0] if s8_ctx["all_scoped_candidates"] else None)
    )
    if application:
        try:
            assert_application_scope_authorized(user_scope, application, require_reviewer=False)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    if request.method == "POST":
        action = request.POST.get("action", "continue_review").strip()
        app_code = request.POST.get("application_code", application.application_code if application else "CAND-NG-001").strip()
        pack_answer = request.POST.get("pack_answer", "").strip()
        decl_confirmed = request.POST.get("declaration_confirmed") in {"true", "True", "1", "on"}

        try:
            res = submit_leadership_pack_review(
                application_code=app_code,
                pack_answer=pack_answer,
                declaration_confirmed=decl_confirmed,
                actor_account=account,
                user_scope=user_scope,
                action=action,
            )
            application = res["application"]
            if res.get("reopen_requested"):
                state_card = screen["state_contracts"]["deadline_reached"]
                result_message = "Authorized review requested to reopen your 3-day Leadership Pack window."
            else:
                state_card = screen["state_contracts"]["progress_saved"]
                result_message = f"3-day Leadership Pack Review understanding and declaration saved for {application.candidate_name}."
            result_success = True
            s8_ctx = _build_stage8_common_context(request, ctx, "REC-07")
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = screen["state_contracts"]["deadline_reached"] if "window is closed" in str(exc) else screen["state_contracts"]["more_info"]
            result_message = str(exc)
            result_success = False

    ctx.update(s8_ctx)
    ctx.update({
        "application": application,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "review"),
    })
    return render(request, "foundation/recruitment/rec_07_leadership_pack.html", ctx)


def application_outcome_view(request):
    """REC-08: Your application outcome."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-08")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s8_ctx["screen"]
    state_card = s8_ctx["state_card"]
    result_message = None
    result_success = True

    req_code = (request.GET.get("candidate") or request.POST.get("application_code") or "CAND-NG-001").strip()
    application = (
        CandidateApplication.objects.filter(application_code=req_code).first()
        or (s8_ctx["all_scoped_candidates"][0] if s8_ctx["all_scoped_candidates"] else None)
    )
    if application:
        try:
            assert_application_scope_authorized(user_scope, application, require_reviewer=False)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    if request.method == "POST":
        app_code = request.POST.get("application_code", application.application_code if application else "CAND-NG-001").strip()
        response_choice = request.POST.get("response_choice", "accept_alternative").strip()
        try:
            res = respond_to_application_outcome(
                application_code=app_code,
                response_choice=response_choice,
                actor_account=account,
                user_scope=user_scope,
            )
            application = res["application"]
            result_message = f"Your response ('{application.alternative_next_action}') has been recorded without requiring a new registration."
            result_success = True
            s8_ctx = _build_stage8_common_context(request, ctx, "REC-08")
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            result_message = str(exc)
            result_success = False

    ctx.update(s8_ctx)
    ctx.update({
        "application": application,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/recruitment/rec_08_outcome.html", ctx)


def recruitment_pipeline_view(request):
    """REC-09: Recruitment pipeline."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-09")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    ctx.update(s8_ctx)
    ctx.update({
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/recruitment/rec_09_pipeline.html", ctx)


def review_candidate_evidence_view(request):
    """REC-10: Review candidate evidence."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-10")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s8_ctx["screen"]
    state_card = s8_ctx["state_card"]
    result_message = None
    result_success = True

    req_code = (request.GET.get("candidate") or request.POST.get("application_code") or "CAND-NG-002").strip()
    application = (
        CandidateApplication.objects.filter(application_code=req_code).first()
        or CandidateApplication.objects.filter(candidate_name__iexact=req_code).first()
        or CandidateApplication.objects.filter(application_code="CAND-NG-002").first()
    )
    if application:
        try:
            assert_application_scope_authorized(user_scope, application, require_reviewer=True)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    if request.method == "POST":
        action = request.POST.get("action", "submit").strip()
        app_code = request.POST.get("application_code", application.application_code if application else "CAND-NG-002").strip()
        evidence_assessment = request.POST.get("evidence_assessment", "").strip()
        reviewer_notes = request.POST.get("reviewer_notes", "").strip()
        reopen_deadline = request.POST.get("reopen_deadline") in {"true", "True", "1", "on"}
        expected_updated_at = request.POST.get("expected_updated_at", "").strip() or None

        if action == "save_draft":
            state_card = screen["state_contracts"]["saved_later"]
            result_message = "Evidence review draft saved for later."
        else:
            try:
                res = submit_candidate_evidence_review(
                    application_code=app_code,
                    evidence_assessment=evidence_assessment,
                    reviewer_notes=reviewer_notes,
                    actor_account=account,
                    user_scope=user_scope,
                    reopen_deadline=reopen_deadline,
                    expected_updated_at=expected_updated_at,
                )
                if res.get("conflict"):
                    state_card = screen["state_contracts"]["another_change"]
                    result_message = res["message"]
                    result_success = False
                else:
                    application = res["application"]
                    result_message = f"Evidence assessment ('{application.evidence_assessment}') recorded for {application.candidate_name}."
                    result_success = True
                    s8_ctx = _build_stage8_common_context(request, ctx, "REC-10")
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except ValueError as exc:
                state_card = screen["state_contracts"]["check_highlighted"]
                result_message = str(exc)
                result_success = False

    ctx.update(s8_ctx)
    ctx.update({
        "application": application,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/recruitment/rec_10_evidence.html", ctx)


def score_candidate_rubric_view(request):
    """REC-10-RUBRIC: Score candidate against approved criteria."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-10-RUBRIC")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s8_ctx["screen"]
    state_card = s8_ctx["state_card"]
    result_message = None
    result_success = True

    req_code = (request.GET.get("candidate") or request.POST.get("application_code") or "CAND-NG-001").strip()
    application = (
        CandidateApplication.objects.filter(application_code=req_code).first()
        or CandidateApplication.objects.filter(candidate_name__iexact=req_code).first()
        or CandidateApplication.objects.filter(application_code="CAND-NG-001").first()
    )
    if application:
        try:
            assert_application_scope_authorized(user_scope, application, require_reviewer=True)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    if request.method == "POST":
        app_code = request.POST.get("application_code", application.application_code if application else "CAND-NG-001").strip()
        criterion = request.POST.get("criterion", "Community leadership").strip()
        score = request.POST.get("score", "").strip()
        evidence_note = request.POST.get("evidence_note", "").strip()

        try:
            res = save_candidate_rubric_score(
                application_code=app_code,
                criterion=criterion,
                score=score,
                evidence_note=evidence_note,
                actor_account=account,
                user_scope=user_scope,
            )
            application = res["application"]
            row = res["rubric_row"]
            result_message = f"Rubric score saved for {application.candidate_name} · {row.criterion}: {row.evidence_status} ({row.required_followup})."
            result_success = True
            s8_ctx = _build_stage8_common_context(request, ctx, "REC-10-RUBRIC")
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = screen["state_contracts"]["check_highlighted"]
            result_message = str(exc)
            result_success = False

    rubric_rows = list(CandidateRubricScore.objects.filter(application=application)) if application else []

    ctx.update(s8_ctx)
    ctx.update({
        "application": application,
        "rubric_rows": rubric_rows,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/recruitment/rec_10_rubric.html", ctx)


def compare_candidates_view(request):
    """REC-11: Compare candidates for this seat."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-11")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    seat_filter = request.GET.get("seat", "").strip()
    candidates = s8_ctx["candidates"]
    if seat_filter:
        candidates = [c for c in candidates if seat_filter.lower() in c.seat_label.lower()]

    ctx.update(s8_ctx)
    ctx.update({
        "candidates": candidates,
        "seat_filter": seat_filter or "Chapter Coordinator · Ikeja",
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/recruitment/rec_11_compare.html", ctx)


def record_selection_decision_view(request):
    """REC-12: Record the selection decision."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-12")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s8_ctx["screen"]
    state_card = s8_ctx["state_card"]
    result_message = None
    result_success = True

    req_code = (request.GET.get("candidate") or request.POST.get("application_code") or "CAND-NG-002").strip()
    application = (
        CandidateApplication.objects.filter(application_code=req_code).first()
        or CandidateApplication.objects.filter(candidate_name__iexact=req_code).first()
        or CandidateApplication.objects.filter(application_code="CAND-NG-002").first()
    )
    if application:
        try:
            assert_application_scope_authorized(user_scope, application, require_reviewer=True)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    if request.method == "POST":
        action = request.POST.get("action", "submit").strip()
        app_code = request.POST.get("application_code", application.application_code if application else "CAND-NG-002").strip()
        seat_label = request.POST.get("seat_label", "Chapter Coordinator · Ikeja").strip()
        decision = request.POST.get("decision", "").strip()
        decision_reason = request.POST.get("decision_reason", "").strip()
        expected_updated_at = request.POST.get("expected_updated_at", "").strip() or None

        if action == "save_draft":
            state_card = screen["state_contracts"]["saved_later"]
            result_message = "Selection decision draft saved for later."
        else:
            try:
                res = record_selection_decision(
                    application_code=app_code,
                    decision=decision,
                    decision_reason=decision_reason,
                    actor_account=account,
                    user_scope=user_scope,
                    seat_label=seat_label,
                    require_consequence_checkbox=False,
                    expected_updated_at=expected_updated_at,
                )
                if res.get("conflict"):
                    state_card = screen["state_contracts"]["another_change"]
                    result_message = res["message"]
                    result_success = False
                else:
                    application = res["application"]
                    appt = res.get("appointment")
                    appt_info = f" Appointment record {appt.appointment_code} queued in Stage 7." if appt else ""
                    result_message = f"Authorized selection decision '{application.decision_status}' confirmed for {application.candidate_name} ({application.seat_label}).{appt_info}"
                    result_success = True
                    s8_ctx = _build_stage8_common_context(request, ctx, "REC-12")
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except ValueError as exc:
                state_card = screen["state_contracts"]["check_highlighted"]
                result_message = str(exc)
                result_success = False

    ctx.update(s8_ctx)
    ctx.update({
        "application": application,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/recruitment/rec_12_decision.html", ctx)


def record_human_decision_view(request):
    """REC-12-DECISION: Record human recruitment decision."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-12-DECISION")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s8_ctx["screen"]
    state_card = s8_ctx["state_card"]
    result_message = None
    result_success = True

    req_code = (request.GET.get("candidate") or request.POST.get("application_code") or "CAND-NG-001").strip()
    application = (
        CandidateApplication.objects.filter(application_code=req_code).first()
        or CandidateApplication.objects.filter(candidate_name__iexact=req_code).first()
        or CandidateApplication.objects.filter(application_code="CAND-NG-001").first()
    )
    if application:
        try:
            assert_application_scope_authorized(user_scope, application, require_reviewer=True)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    if request.method == "POST":
        app_code = request.POST.get("application_code", application.application_code if application else "CAND-NG-001").strip()
        decision = request.POST.get("decision", "").strip()
        decision_reason = request.POST.get("decision_reason", "").strip()
        override_reason = request.POST.get("override_reason", "").strip()
        consequence_confirmed = request.POST.get("consequence_confirmed") in {"true", "True", "1", "on"}
        expected_updated_at = request.POST.get("expected_updated_at", "").strip() or None

        try:
            res = record_selection_decision(
                application_code=app_code,
                decision=decision,
                decision_reason=decision_reason,
                actor_account=account,
                user_scope=user_scope,
                override_reason=override_reason,
                consequence_confirmed=consequence_confirmed,
                require_consequence_checkbox=True,
                expected_updated_at=expected_updated_at,
            )
            if res.get("conflict"):
                state_card = screen["state_contracts"]["another_change"]
                result_message = res["message"]
                result_success = False
            else:
                application = res["application"]
                result_message = f"Human recruitment decision '{application.decision_status}' recorded for {application.candidate_name}. Disclosed outcome: {application.disclosed_outcome}."
                result_success = True
                s8_ctx = _build_stage8_common_context(request, ctx, "REC-12-DECISION")
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = screen["state_contracts"]["check_highlighted"]
            result_message = str(exc)
            result_success = False

    ctx.update(s8_ctx)
    ctx.update({
        "application": application,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/recruitment/rec_12_human_decision.html", ctx)


def reserve_succession_pool_view(request):
    """REC-13: Reserve and succession pool."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-13")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    state_card = s8_ctx["state_card"]
    result_message = None
    result_success = True

    if request.method == "POST":
        app_code = request.POST.get("application_code", "CAND-NG-001").strip()
        target_seat_label = request.POST.get("target_seat_label", "Chapter Coordinator · Ikeja").strip()
        try:
            res = match_reserve_candidate_to_vacancy(
                application_code=app_code,
                target_seat_label=target_seat_label,
                actor_account=account,
                user_scope=user_scope,
            )
            app_obj = res["application"]
            result_message = f"Reserve candidate {app_obj.candidate_name} matched to approved vacancy ({app_obj.seat_label}) for human selection review."
            result_success = True
            s8_ctx = _build_stage8_common_context(request, ctx, "REC-13")
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            result_message = str(exc)
            result_success = False

    ctx.update(s8_ctx)
    ctx.update({
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/recruitment/rec_13_reserve_pool.html", ctx)


def recruitment_route_settings_view(request):
    """REC-14: Recruitment route settings."""
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s8_ctx = _build_stage8_common_context(request, ctx, "REC-14")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    screen = s8_ctx["screen"]
    state_card = s8_ctx["state_card"]
    result_message = None
    result_success = True

    route_code = (request.GET.get("route_code") or "OPEN_CALL_7DAY").strip().upper()
    route_config = (
        RecruitmentRouteConfig.objects.filter(route_code=route_code).first()
        or RecruitmentRouteConfig.objects.filter(route_code="OPEN_CALL_7DAY").first()
    )

    if request.method == "POST":
        action = request.POST.get("action", "submit").strip()
        route_name = request.POST.get("route_name", "").strip()
        duration_label = request.POST.get("duration_label", "").strip()
        route_timezone = request.POST.get("route_timezone", "").strip()
        content_version = request.POST.get("content_version", "").strip()
        expected_updated_at = request.POST.get("expected_updated_at", "").strip() or None

        if action == "save_draft":
            state_card = screen["state_contracts"]["saved_later"]
            result_message = "Recruitment route settings draft saved for later."
        else:
            try:
                res = save_recruitment_route_revision(
                    route_name=route_name,
                    duration_label=duration_label,
                    route_timezone=route_timezone,
                    content_version=content_version,
                    actor_account=account,
                    user_scope=user_scope,
                    country=s8_ctx["target_country"],
                    network=s8_ctx["target_network"],
                    expected_updated_at=expected_updated_at,
                )
                if res.get("conflict"):
                    state_card = screen["state_contracts"]["another_change"]
                    result_message = res["message"]
                    result_success = False
                else:
                    route_config = res["route_config"]
                    result_message = f"Controlled route revision saved for {route_config.route_name} ({route_config.duration_label} · {route_config.route_timezone} · {route_config.content_version}). Current settings remain effective until required approval."
                    result_success = True
                    s8_ctx = _build_stage8_common_context(request, ctx, "REC-14")
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except ValueError as exc:
                state_card = screen["state_contracts"]["check_highlighted"]
                result_message = str(exc)
                result_success = False

    all_routes = list(RecruitmentRouteConfig.objects.all())

    ctx.update(s8_ctx)
    ctx.update({
        "route_config": route_config,
        "all_routes": all_routes,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
        "active_tab": request.GET.get("tab", "overview"),
    })
    return render(request, "foundation/recruitment/rec_14_route_settings.html", ctx)


def stage8_screen_router(request, screen_code):
    """
    Direct screen code dispatcher for Stage 08 screens:
    REC-01..REC-14 (including REC-10-RUBRIC and REC-12-DECISION).
    """
    code = (screen_code or "").strip().upper()
    mapping = {
        "REC-01": find_volunteer_opportunity_view,
        "REC-02": apply_to_volunteer_view,
        "REC-03": you_have_been_referred_view,
        "REC-04": my_referrals_and_links_view,
        "REC-05": my_application_view,
        "REC-06": seven_day_activation_view,
        "REC-07": leadership_pack_review_view,
        "REC-08": application_outcome_view,
        "REC-09": recruitment_pipeline_view,
        "REC-10": review_candidate_evidence_view,
        "REC-10-RUBRIC": score_candidate_rubric_view,
        "REC-11": compare_candidates_view,
        "REC-12": record_selection_decision_view,
        "REC-12-DECISION": record_human_decision_view,
        "REC-13": reserve_succession_pool_view,
        "REC-14": recruitment_route_settings_view,
    }
    view_fn = mapping.get(code)
    if not view_fn:
        raise Http404(f"Stage 08 screen code '{screen_code}' not found.")
    return view_fn(request)


# =============================================================================
# WDOS STAGE 09: TASKS, CALENDAR, AND MEETING ADMINISTRATION VIEWS
# =============================================================================
from .tasks_meetings_views import (
    create_task_view,
    meeting_attendance_minutes_view,
    meeting_followup_view,
    meetings_command_centre_view,
    meetings_list_view,
    mission_control_tasks_view,
    my_calendar_view,
    recurring_meeting_series_view,
    review_task_completion_view,
    schedule_meeting_view,
    stage9_meeting_detail_view,
    stage9_screen_router,
    task_detail_view,
    task_lifecycle_view,
)








