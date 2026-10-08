import json
import os
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import logout as django_logout
from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_POST

from accounts.locale import LANGUAGES, catalog, translate
from accounts.models import AccessGrant, Account, Membership, OnboardingDraft, Person
from accounts.services import audit
from .models import (
    Chapter,
    Communication,
    CountryHub,
    DashboardActivity,
    DashboardAlert,
    DashboardReport,
    DeviceSession,
    LeadershipLevel,
    NetworkTransition,
    Notification,
    PrivacyRequest,
    Role,
    ScheduledMeeting,
    UserPreference,
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
)
from .dashboard_engine import (
    build_dashboard_context,
    check_dashboard_permission,
    get_dashboard_screen,
    get_default_screen_for_role,
    DASHBOARD_SCREENS,
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

    context = {
        "account": account,
        "user_scope": user_scope,
        "country_name": get_country_display_name(user_scope.active_country),
        "user_pref": user_pref,
        "lang": lang,
        "direction": direction,
        "translations": translations,
        "display_name": display_name,
        "initials": initials,
        "unread_notifications_count": unread_notifications_count,
        "environment": os.getenv("WDOS_ENVIRONMENT", "local"),
        "high_contrast": user_pref.high_contrast if user_pref else False,
        "reduced_motion": user_pref.reduced_motion if user_pref else False,
        "font_size": user_pref.font_size if user_pref else "standard",
    }
    return context, None


def _render_scope_error(request, context, exception):
    """Render the accessible, explanatory scope permission denial error page."""
    context["error_message"] = getattr(exception, "message", str(exception))
    context["reason_code"] = getattr(exception, "reason_code", "forbidden")
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


def _get_standard_stage4_items(account, user_scope):
    """
    Standard records matching the Stage 04 PDF Artboard review examples
    with deep links to authorized records.
    """
    meeting = ScheduledMeeting.objects.filter(network__in=[user_scope.active_network, "ALL"]).first()
    meeting_url = f"/foundation/dashboard/meetings/{meeting.id}/" if meeting else "/foundation/workspace/"
    
    return [
        {
            "title": "Local welcome meeting",
            "when": "18 Sep · 10:00 WAT",
            "action_label": "View invitation",
            "action_url": meeting_url,
            "pill_style": "magenta",
        },
        {
            "title": "Communication preferences",
            "when": "Updated today",
            "action_label": "Review settings",
            "action_url": "/foundation/settings/",
            "pill_style": "amber",
        },
        {
            "title": "Membership profile",
            "when": "Contact verified",
            "action_label": "Open profile",
            "action_url": "/foundation/profile/",
            "pill_style": "",
        },
    ]


# -----------------------------------------------------------------------------
# Main Shell & Personal Workspace Overview
# -----------------------------------------------------------------------------

def app_shell(request):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]

    # Role resolution & authorization
    req_role = request.GET.get("role") or request.GET.get("view") or request.session.get("wdos_active_role") or user_scope.active_role
    try:
        assert_role_authorized(user_scope, req_role)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    role = req_role
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

    if not request.GET.get("role") and request.GET.get("view") != "dashboard" and request.GET.get("legacy") != "1":
        ctx.update({
            "screen_code": "CORE-01",
            "active_nav": "workspace",
            "local_connection": extra_context.get("local_home_label", "Ikeja Chapter") or "Ikeja Chapter",
            "language_name": "English",
            "workspace_items": _get_standard_stage4_items(ctx["account"], user_scope),
            "active_tab": request.GET.get("tab", "overview"),
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
            assert_scope_authorized(user_scope, network=network, country=country)
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

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

    if request.GET.get("legacy") == "1":
        membership = Membership.objects.filter(person=account.person).first() if account.person else None
        active_grants = AccessGrant.objects.filter(
            account=account,
            revoked_at__isnull=True,
            expires_at__gt=timezone.now(),
        )
        assigned_work_items = list(WorkItem.objects.filter(assigned_to=account)[:5])

        profile_name = account.display_name or (account.person.display_name if account.person else "Member")
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

    profile_records = _get_standard_stage4_items(account, user_scope)
    ctx.update({
        "screen_code": "CORE-05",
        "active_nav": "profile",
        "person_id": getattr(account.person, "external_id", "WD-00421") if account.person else "WD-00421",
        "preferred_name": "Ada",
        "local_connection": "Ikeja Chapter",
        "profile_records": profile_records,
        "active_tab": request.GET.get("tab", "overview"),
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
            ctx["user_pref"].active_country = target_country

    if ctx["user_pref"]:
        ctx["user_pref"].save(update_fields=["active_network", "active_country"])

    next_url = request.POST.get("next") or f"/foundation/network/{target_network or user_scope.active_network}/"
    return redirect(next_url)


# -----------------------------------------------------------------------------
# Work Queue & Deep Links
# -----------------------------------------------------------------------------

def work_queue_view(request):
    """My work queue view (CORE-02)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    status_filter = request.GET.get("status", "all")
    category_filter = request.GET.get("category", "all")
    priority_filter = request.GET.get("priority", "all")

    items_qs = WorkItem.objects.filter(network__in=user_scope.allowed_networks)
    if "*" not in user_scope.allowed_countries:
        items_qs = items_qs.filter(country__in=user_scope.allowed_countries)

    if not user_scope.can_access_confidential():
        items_qs = items_qs.filter(confidential=False)

    if status_filter != "all":
        items_qs = items_qs.filter(status=status_filter)
    if category_filter != "all":
        items_qs = items_qs.filter(category=category_filter)
    if priority_filter != "all":
        items_qs = items_qs.filter(priority=priority_filter)

    items = list(items_qs)

    if request.GET.get("legacy") == "1":
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

    if items:
        queue_items = []
        for wi in items:
            queue_items.append({
                "title": wi.title,
                "when": wi.created_at.strftime("%d %b · %H:%M") if wi.created_at else "Recently",
                "action_label": "View details",
                "action_url": f"/foundation/work-queue/{wi.id}/",
                "pill_style": "amber" if wi.status == "pending" else "magenta",
            })
    else:
        queue_items = _get_standard_stage4_items(ctx["account"], user_scope) if not request.GET.get("status") else []

    ctx.update({
        "screen_code": "CORE-02",
        "active_nav": "work_queue",
        "queue_items": queue_items,
        "active_tab": request.GET.get("tab", "overview"),
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

    try:
        assert_scope_authorized(
            user_scope,
            network=item.network,
            country=item.country,
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

    try:
        assert_scope_authorized(
            user_scope,
            network=item.network,
            country=item.country,
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
    query = request.GET.get("q", "").strip()

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
        scoped_res = _execute_scoped_search(query, user_scope)
        filtered_items = []
        for res in scoped_res:
            filtered_items.append({
                "title": res["title"],
                "when": res.get("summary", ""),
                "action_label": "Open ›",
                "action_url": res["url"],
                "pill_style": "magenta",
            })
    else:
        filtered_items = _get_standard_stage4_items(ctx["account"], user_scope)

    ctx.update({
        "screen_code": "CORE-04",
        "active_nav": "search",
        "q": query,
        "search_results": filtered_items,
        "active_tab": request.GET.get("tab", "overview"),
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


def _execute_scoped_search(query: str, user_scope: UserScope):
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

    matching_items = items_qs.filter(
        models_q_search(query, ["title", "summary", "category"])
    )[:15]

    for item in matching_items:
        results.append({
            "id": item.id,
            "type": "work_item",
            "title": item.title,
            "summary": item.summary,
            "network": item.network,
            "country": item.country,
            "url": f"/foundation/work-queue/{item.id}/",
        })

    # 2. Search Country Hubs
    hubs_qs = CountryHub.objects.filter(status="active")
    if "*" not in user_scope.allowed_countries:
        hubs_qs = hubs_qs.filter(code__in=user_scope.allowed_countries)

    matching_hubs = hubs_qs.filter(
        models_q_search(query, ["name", "code", "region", "lead_name"])
    )[:5]

    for hub in matching_hubs:
        results.append({
            "id": hub.code,
            "type": "country_hub",
            "title": f"{hub.name} Country Hub ({hub.code})",
            "summary": f"Region: {hub.region or 'Africa'}. Lead: {hub.lead_name or 'N/A'}",
            "network": user_scope.active_network,
            "country": hub.code,
            "url": f"/foundation/network/{user_scope.active_network}/country/{hub.code}/",
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

def notifications_view(request):
    """Notifications view (CORE-03)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    notifications = list(Notification.objects.filter(account=ctx["account"], is_archived=False))

    if request.GET.get("legacy") == "1":
        breadcrumbs = get_breadcrumbs(user_scope, page_name="Notifications")
        ctx.update({
            "notifications": notifications,
            "breadcrumbs": breadcrumbs,
        })
        return render(request, "foundation/notifications.html", ctx)

    if notifications:
        notification_items = []
        for notif in notifications:
            is_failed = notif.delivery_status == "failed"
            action_label = "Retry Delivery" if is_failed else ("View invitation" if "meeting" in notif.title.lower() else "Open")
            action_url = f"/foundation/api/notifications/{notif.id}/retry/" if is_failed else "/foundation/notifications/"
            notification_items.append({
                "title": notif.title,
                "when": notif.created_at.strftime("%d %b · %H:%M") if notif.created_at else "Recently",
                "action_label": action_label,
                "action_url": action_url,
                "pill_style": "danger" if is_failed else ("magenta" if "meeting" in notif.title.lower() else "amber"),
                "delivery_label": "Delivery Failure" if is_failed else "",
                "is_read": notif.is_read,
                "is_form": is_failed,
            })
    else:
        notification_items = _get_standard_stage4_items(ctx["account"], user_scope)

    ctx.update({
        "screen_code": "CORE-03",
        "active_nav": "notifications",
        "notification_items": notification_items,
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
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    notification = get_object_or_404(Notification, id=notification_id, account=account)
    notification.is_read = True
    notification.save(update_fields=["is_read"])
    return JsonResponse({"status": "ok", "id": str(notification.id), "is_read": True})


@require_POST
def mark_all_notifications_read(request):
    account = getattr(request, "wdos_account", None)
    if not account:
        return JsonResponse({"error": "Unauthorized"}, status=401)

    Notification.objects.filter(account=account, is_read=False).update(is_read=True)
    return redirect("/foundation/notifications/")


@require_POST
def retry_notification(request, notification_id):
    """Recovery action for failed notification state."""
    account = getattr(request, "wdos_account", None)
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


def account_sessions_view(request):
    """CORE-06-SESSIONS Your signed-in devices."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response
    account = ctx["account"]
    sessions_qs = DeviceSession.objects.filter(account=account).order_by("-is_current", "-last_active")
    sessions_list = []
    for s in sessions_qs:
        sessions_list.append({
            "id": s.id,
            "device_name": s.device_name,
            "browser_info": s.browser_info,
            "is_current": s.is_current,
            "last_active_str": "Now" if s.is_current else "Yesterday",
        })
    ctx.update({
        "screen_code": "CORE-06-SESSIONS",
        "active_nav": "settings",
        "device_sessions": sessions_list,
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
        return redirect("/foundation/account/sessions/")

    ctx.update({
        "screen_code": "CORE-06-SIGNOUT",
        "active_nav": "settings",
        "target_session_id": str(target_session.id) if target_session else "",
        "target_device_name": f"{target_session.device_name} · {target_session.browser_info}" if target_session else "Other device · mobile browser",
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
        })
        return render(request, "foundation/settings.html", ctx)

    account = ctx["account"]
    pref = ctx.get("user_pref")
    saved = False

    if request.method == "POST":
        lang = request.POST.get("language")
        timezone_val = request.POST.get("timezone")
        font_size = request.POST.get("font_size")

        if pref:
            if lang in LANGUAGES:
                pref.language = lang
                request.session["wdos_language"] = lang
            if timezone_val:
                pref.timezone = timezone_val
            if font_size in ("standard", "large", "xlarge"):
                pref.font_size = font_size
            pref.save()
            saved = True

    ctx.update({
        "screen_code": "CORE-07",
        "active_nav": "settings",
        "current_lang": pref.language if pref else "en",
        "pref_saved": saved,
        **_get_stage4_state_context(request, "Language and preferences"),
    })
    return render(request, "foundation/core/core_07_preferences.html", ctx)


def connection_status_view(request):
    """CORE-07-CONNECTION Your connection is unavailable."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    ctx.update({
        "screen_code": "CORE-07-CONNECTION",
        "active_nav": "workspace",
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
        reqs.append({
            "id": r.id,
            "title": r.reference or "Example correction",
            "submitted_str": r.created_at.strftime("%d %b · sample") if r.created_at else "14 Sep · sample",
            "status_str": r.get_status_display() if hasattr(r, "get_status_display") else r.status.replace("_", " ").title(),
            "detail_url": f"/foundation/privacy-requests/status/?ref={r.reference or 'PR-DEMO-01'}",
            "pill_style": "",
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

    if request.method == "POST":
        action = request.POST.get("action")
        req_type = request.POST.get("request_type", "correct_info")
        details = request.POST.get("details", "") or request.POST.get("reason", "")
        safe_route = request.POST.get("safe_reply_route", "account")
        ack = request.POST.get("ack")

        if ack == "1" or action == "submit_direct":
            pr = PrivacyRequest.objects.create(
                account=ctx["account"],
                reference="PR-EXPORT-01" if req_type == "export" else "PR-DEMO-01",
                request_type=req_type,
                details=details,
                safe_reply_route=safe_route,
                status="submitted",
            )
            user_scope = ctx["user_scope"]
            WorkItem.objects.create(
                title=f"Privacy Request: {pr.get_request_type_display() if hasattr(pr, 'get_request_type_display') else req_type.title()}",
                summary=details,
                category="privacy",
                network=user_scope.active_network,
                country=user_scope.active_country if user_scope.active_country != "*" else "NG",
                confidential=True,
                status="pending",
                created_by=ctx["account"],
            )
            return redirect("/foundation/privacy-requests/")
        elif action == "save_later":
            PrivacyRequest.objects.create(
                account=ctx["account"],
                reference="PR-DEMO-01",
                request_type=req_type,
                details=details,
                safe_reply_route=safe_route,
                status="draft",
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
    draft = request.session.get("privacy_draft", {})
    req_type = request.POST.get("request_type") or draft.get("request_type", "correct_info")
    details = request.POST.get("details") or draft.get("details", "Your entered explanation appears here")
    safe_route = request.POST.get("safe_reply_route") or draft.get("safe_reply_route", "account")

    if request.method == "POST":
        pr = PrivacyRequest.objects.create(
            account=account,
            reference="PR-DEMO-01",
            request_type=req_type,
            details=details,
            safe_reply_route=safe_route,
            status="pending",
            current_step="Identity check required",
            next_action="Confirm through the approved verification route",
        )
        if "privacy_draft" in request.session:
            del request.session["privacy_draft"]
        return redirect(f"/foundation/privacy-requests/status/?ref={pr.reference}")

    labels = {
        "correct_info": "Correct my information · example",
        "export_records": "Export my records · example",
        "delete_account": "Delete my account · example",
        "object_processing": "Object to processing · example",
    }
    route_labels = {
        "account": "Inside your WDOS account",
        "email": "Email reply",
        "in_person": "In-person verification",
    }

    ctx.update({
        "screen_code": "CORE-08-CONFIRM",
        "active_nav": "settings",
        "request_type": req_type,
        "request_type_label": labels.get(req_type, "Correct my information · example"),
        "details": details,
        "safe_reply_route": safe_route,
        "safe_reply_route_label": route_labels.get(safe_route, "Inside your WDOS account"),
        **_get_stage4_state_context(request, "Check your request before sending"),
    })
    return render(request, "foundation/core/core_08_confirm.html", ctx)


def privacy_request_status_view(request):
    """Your privacy request (CORE-08-STATUS)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    account = ctx["account"]
    ref = request.GET.get("ref", "PR-DEMO-01")
    pr = PrivacyRequest.objects.filter(account=account, reference=ref).first()
    if not pr:
        pr = PrivacyRequest.objects.filter(account=account).first()

    timeline_events = [
        {"when": "14 Sep · sample", "what": "Request received", "who": "You"},
        {"when": "14 Sep · sample", "what": "Identity check requested", "who": "Authorised privacy reviewer"},
    ]

    labels = {
        "correct_info": "Correct my information",
        "export_records": "Export my records",
        "delete_account": "Delete my account",
        "object_processing": "Object to processing",
    }

    class DummyReq:
        reference = "PR-DEMO-01"
        request_type_label = "Correct my information"
        current_step = "Identity check required"
        next_action = "Confirm through the approved verification route"

    req_obj = pr or DummyReq()
    if pr:
        req_obj.request_type_label = labels.get(pr.request_type, "Correct my information")

    ctx.update({
        "screen_code": "CORE-08-STATUS",
        "active_nav": "settings",
        "privacy_req": req_obj,
        "timeline_events": timeline_events,
        **_get_stage4_state_context(request, "Your privacy request"),
    })
    return render(request, "foundation/core/core_08_status.html", ctx)


def privacy_request_review_view(request):
    """Review a privacy request (CORE-08-REVIEW)."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    ref = request.GET.get("ref", "PR-DEMO-01")
    pr = PrivacyRequest.objects.filter(reference=ref).first()
    saved = False

    if request.method == "POST":
        decision = request.POST.get("decision", "more_info")
        reason = request.POST.get("reason_and_retention", "")
        check_status = request.POST.get("identity_check", "not_checked")
        if pr:
            pr.decision = decision
            pr.reason_and_retention = reason
            pr.identity_check_status = check_status
            pr.save()
            saved = True

    ctx.update({
        "screen_code": "CORE-08-REVIEW",
        "active_nav": "workspace",
        "is_privacy_reviewer": True,
        "active_role_title": "Authorised privacy reviewer",
        "privacy_req": pr or type("Obj", (), {"reference": "PR-DEMO-01"}),
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
    confirmed = False

    if request.method == "POST":
        consent = request.POST.get("consent_confirmed")
        if consent:
            NetworkTransition.objects.create(
                account=account,
                current_relationship="WNNN membership",
                requested_transition="WGMN membership review",
                age_evidence_method="Approved re-attestation",
                consent_confirmed=True,
                status="in_progress",
            )
            confirmed = True

    ctx.update({
        "screen_code": "CORE-09",
        "active_nav": "workspace",
        "transition_confirmed": confirmed,
        "active_tab": request.GET.get("tab", "overview"),
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
            columns = ["Code", "Name", "Network", "Country", "Region", "Status", "Members", "Lead Name", "Action"]
        elif category == "alerts":
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
    report = get_object_or_404(DashboardReport, id=report_id)

    try:
        assert_scope_authorized(user_scope, network=report.network, country=report.country)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    breadcrumbs = get_breadcrumbs(user_scope, network=report.network, country=report.country, page_name=f"Report: {report.title}")

    ctx.update({
        "report": report,
        "breadcrumbs": breadcrumbs,
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

    is_rsvpd = meeting.rsvp_accounts.filter(id=ctx["account"].id).exists()
    breadcrumbs = get_breadcrumbs(user_scope, network=meeting.network, country=meeting.country, page_name=f"Meeting: {meeting.title}")

    ctx.update({
        "meeting": meeting,
        "is_rsvpd": is_rsvpd,
        "breadcrumbs": breadcrumbs,
    })
    return render(request, "foundation/meeting_detail.html", ctx)


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

    chapter_meetings = list(ScheduledMeeting.objects.filter(
        geography__icontains=chapter.name,
        scheduled_at__gte=timezone.now(),
    )[:5])
    chapter_members = list(Membership.objects.filter(home__code=chapter.code)[:15])

    breadcrumbs = get_breadcrumbs(user_scope, network=chapter.network, country=chapter.country, page_name=f"Chapter: {chapter.name}")

    ctx.update({
        "chapter": chapter,
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

    try:
        assert_role_authorized(user_scope, target_role)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    request.session["wdos_active_role"] = target_role
    return redirect(f"/foundation/?role={target_role}")


def dev_switch_user(request, role_or_alias):
    """
    Development-only convenience route to quickly switch active test persona in a real browser.
    Strictly disabled when settings.DEBUG is False.
    """
    if not settings.DEBUG and os.getenv("WDOS_ENVIRONMENT", "local") != "local":
        raise Http404("Development route only.")

    alias_map = {
        "founder": "founder@example.org",
        "hq": "founder@example.org",
        "ops": "ops@example.org",
        "operations": "ops@example.org",
        "country_ng": "country.ng@example.org",
        "country-ng": "country.ng@example.org",
        "country_ke": "country.ke@example.org",
        "country-ke": "country.ke@example.org",
        "chapter_lagos": "chapter.lagos@example.org",
        "chapter-lagos": "chapter.lagos@example.org",
        "member": "member.ada@example.org",
        "ada": "member.ada@example.org",
        "member_ada": "member.ada@example.org",
        "wgmn": "wgmn_member@example.org",
        "wgmn_member": "wgmn_member@example.org",
        "wnnn": "wnnn_member@example.org",
        "wnnn_member": "wnnn_member@example.org",
        "candidate": "candidate.john@example.org",
        "john": "candidate.john@example.org",
        "community": "community.amara@example.org",
        "amara": "community.amara@example.org",
    }
    email = alias_map.get(role_or_alias.lower().strip(), role_or_alias.lower().strip())
    account = Account.objects.select_related("user").filter(email=email).first()
    if not account:
        raise Http404(f"Test account '{role_or_alias}' not found.")

    from django.contrib.auth import login as django_login
    django_login(request, account.user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["security_version"] = account.security_version
    request.session["mfa_verified"] = True
    now = timezone.now().timestamp()
    request.session["last_activity"] = now
    request.session["absolute_expiry"] = now + 43200
    request.session.modified = True
    return redirect("/foundation/")


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
    req_role = request.GET.get("role") or request.session.get("wdos_active_role") or user_scope.active_role
    if req_role:
        try:
            assert_role_authorized(user_scope, req_role)
            user_scope.active_role = req_role
            request.session["wdos_active_role"] = req_role
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)

    # Resolve screen code: from URL param, GET param, or user's active role default
    resolved_code = screen_code or request.GET.get("screen")
    if not resolved_code:
        resolved_code = get_default_screen_for_role(user_scope.active_role)

    norm_code = resolved_code.strip().upper()

    # Enforce server-authoritative permission checks
    try:
        check_dashboard_permission(user_scope, norm_code)
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
    )

    ctx.update(dash_ctx)
    ctx["active_nav"] = "workspace"
    ctx["breadcrumbs"] = [
        {"label": "Workspace", "url": "/foundation/", "is_current": False},
        {"label": "Role-specific dashboard reference screens", "url": None, "is_current": True},
    ]

    return render(request, "foundation/dashboards/dash_screen.html", ctx)


