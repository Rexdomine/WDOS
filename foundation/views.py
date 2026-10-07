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
    LeadershipLevel,
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

    role_template_map = {
        "founder": "foundation/dashboards/founder_hq.html",
        "hq": "foundation/dashboards/founder_hq.html",
        "operations": "foundation/dashboards/operations.html",
        "country_lead": "foundation/dashboards/country_lead.html",
        "country_director": "foundation/dashboards/country_lead.html",
        "field_lead": "foundation/dashboards/country_lead.html",
        "chapter_lead": "foundation/dashboards/chapter_lead.html",
        "chapter": "foundation/dashboards/chapter_lead.html",
        "member": "foundation/app_shell.html",
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
    """Direct shortcut to authenticated user's profile."""
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    account = ctx["account"]
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
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    status_filter = request.GET.get("status", "pending")
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
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    query = request.GET.get("q", "").strip()

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
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    notifications = list(Notification.objects.filter(account=ctx["account"], is_archived=False))

    breadcrumbs = get_breadcrumbs(user_scope, page_name="Notifications")

    ctx.update({
        "notifications": notifications,
        "breadcrumbs": breadcrumbs,
    })
    return render(request, "foundation/notifications.html", ctx)


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
# Settings & Accessibility Preferences
# -----------------------------------------------------------------------------

def settings_view(request):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    breadcrumbs = get_breadcrumbs(user_scope, page_name="Settings & Preferences")

    ctx.update({
        "languages": LANGUAGES,
        "breadcrumbs": breadcrumbs,
    })
    return render(request, "foundation/settings.html", ctx)


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
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    privacy_requests = list(PrivacyRequest.objects.filter(account=ctx["account"]))

    breadcrumbs = get_breadcrumbs(user_scope, page_name="Privacy Requests")

    ctx.update({
        "privacy_requests": privacy_requests,
        "breadcrumbs": breadcrumbs,
    })
    return render(request, "foundation/privacy_requests.html", ctx)


@require_POST
def new_privacy_request(request):
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    account = ctx["account"]
    request_type = request.POST.get("request_type")
    reason = request.POST.get("reason", "").strip()
    ack = request.POST.get("ack") == "1" or request.POST.get("ack") == "true"

    if request_type not in ("export", "rectification", "erasure", "restriction"):
        ctx["error"] = "Please select a valid privacy request type."
        return render(request, "foundation/privacy_requests.html", ctx, status=400)

    if not ack:
        ctx["error"] = "You must acknowledge the identity and data request conditions."
        return render(request, "foundation/privacy_requests.html", ctx, status=400)

    with transaction.atomic():
        pr = PrivacyRequest.objects.create(
            account=account,
            request_type=request_type,
            reason=reason,
            status="submitted",
        )
        audit(account, "privacy_request_submitted", {"request_id": str(pr.id), "type": request_type})

        # Queue a WorkItem for the data protection officer / compliance role
        user_scope = ctx["user_scope"]
        WorkItem.objects.create(
            title=f"Privacy Request: {pr.get_request_type_display()} from {account.display_name or account.email}",
            summary=f"User requested {pr.get_request_type_display()}. Reason: {reason or 'Not specified'}",
            category="privacy",
            network=user_scope.active_network,
            country=user_scope.active_country,
            required_role="it_admin",
            priority="urgent" if request_type == "erasure" else "high",
            status="pending",
            confidential=True,
            created_by=account,
        )

    return redirect("/foundation/privacy-requests/")


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

