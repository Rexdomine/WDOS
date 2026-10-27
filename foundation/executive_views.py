"""
WDOS Executive Director Views
Implements all authorized workflows and screens for Role 01: Founder & Executive Director:
- GOV-03: Executive Decision Register (/foundation/governance/decisions/)
- GOV-02: Issues, Risks & Corrective Actions (/foundation/governance/issues/)
- GOV-04: Request Controlled Change (/foundation/governance/change/)
- REL-01: Stakeholder Relationships Register (/foundation/relationships/)
- REL-02: Review Proposed Strategic Partnership (/foundation/relationships/review/)
- COMMS-02: Africa-wide Announcements (/foundation/communications/announcements/)
- EVENT-01: WODDI Leadership Gathering (/foundation/events/)
- EVENT-05: Opening Plenary - Annual Gathering (/foundation/events/plenary/)
- ROOM-03: Country Coordination Multilingua Room (/foundation/rooms/coordination/)
- REP-05: Management Reporting (/foundation/reporting/management/)
- REP-06: Performance Scorecard (/foundation/reporting/scorecard/)
- SAFE-04: Assigned Case Narrative Guardrail (/foundation/safeguarding/case/<str:case_id>/)
"""

from typing import Any, Dict, Optional
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .views import _get_authenticated_context, _render_scope_error
from .scope import ScopePermissionDenied
from .executive_director_engine import (
    EXECUTIVE_SCREENS,
    assert_financial_disbursement_guardrail,
    assert_safeguarding_access_guardrail,
    chair_opening_plenary,
    get_announcements,
    get_country_coordination_room,
    get_decision_by_ref,
    get_decisions,
    get_event_leadership_data,
    get_issues_and_risks,
    get_management_reporting_data,
    get_performance_scorecard_data,
    get_relationship_by_id,
    get_relationships,
    publish_continental_announcement,
    record_executive_decision,
    record_new_issue,
    record_partnership_decision,
    submit_controlled_change,
)


def _setup_exec_context(request, screen_code: str) -> tuple[Optional[Dict[str, Any]], Optional[Any]]:
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return None, redirect_res

    screen = EXECUTIVE_SCREENS.get(screen_code.upper())
    if not screen:
        raise Http404(f"Screen {screen_code} not found.")

    ctx["screen"] = screen
    ctx["screen_id"] = screen["screen_id"]
    ctx["screen_title"] = screen["title"]
    ctx["eyebrow"] = screen["eyebrow"]
    ctx["subtitle"] = screen["subtitle"]
    nav_mapping = {
        "GOV-03": "workspace",
        "GOV-02": "workspace",
        "GOV-04": "workspace",
        "REL-01": "workspace",
        "REL-02": "workspace",
        "COMMS-02": "communications",
        "EVENT-01": "meetings",
        "EVENT-05": "meetings",
        "ROOM-03": "meetings",
        "REP-05": "reports",
        "REP-06": "reports",
        "SAFE-04": "workspace",
    }
    ctx["active_nav"] = nav_mapping.get(screen_code.upper(), "workspace")
    ctx["state_mode"] = request.GET.get("state")
    ctx["active_tab"] = (request.GET.get("tab") or "overview").lower()
    ctx["breadcrumbs"] = [
        {"label": "Home", "url": "/foundation/dashboard/", "is_current": False},
        {"label": screen.get("module", "Executive"), "url": None, "is_current": False},
        {"label": screen["title"], "url": None, "is_current": True},
    ]
    return ctx, None


# -----------------------------------------------------------------------------
# GOV-03: Executive Decision Register (Master PDF p. 666)
# -----------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def executive_decision_register_view(request):
    ctx, redirect_res = _setup_exec_context(request, "GOV-03")
    if redirect_res:
        return redirect_res

    user_scope = ctx["user_scope"]
    actor_name = ctx["account"].display_name or "Founder & Executive Director"
    state_card = None

    if request.method == "POST":
        action = request.POST.get("action", "")
        ref = request.POST.get("reference", "").strip().upper()
        decision_val = request.POST.get("decision", "Approved")
        notes = request.POST.get("notes", "").strip()

        if action == "record_decision" and ref:
            updated_item = record_executive_decision(ref, decision_val, notes, actor_name)
            state_card = {
                "title": f"Decision Recorded · {ref}",
                "message": f"Successfully updated decision status to '{updated_item['status']}' with authorized audit trail.",
                "action_label": "View Decision Log",
                "action_url": f"?tab=records#rec-{ref}",
            }

    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "")
    decisions = get_decisions(query=query, status_filter=status_filter)

    ctx["decisions"] = decisions
    ctx["search_query"] = query
    ctx["status_filter"] = status_filter
    ctx["state_card"] = state_card
    return render(request, "foundation/executive/gov_03_decision_register.html", ctx)


# -----------------------------------------------------------------------------
# GOV-02: Issues, Risks and Corrective Actions (Master PDF p. 663)
# -----------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def governance_issues_view(request):
    ctx, redirect_res = _setup_exec_context(request, "GOV-02")
    if redirect_res:
        return redirect_res

    state_card = None
    if request.method == "POST":
        ref = request.POST.get("reference", "").strip().upper()
        finding = request.POST.get("finding", "").strip()
        owner = request.POST.get("owner", ctx["account"].display_name or "QA Lead").strip()
        category = request.POST.get("category", "Governance").strip()
        severity = request.POST.get("severity", "Medium").strip()
        mitigation = request.POST.get("mitigation", "").strip()

        if ref and finding:
            record_new_issue(ref, finding, owner, category, severity, mitigation)
            state_card = {
                "title": f"New Governance Issue Logged · {ref}",
                "message": f"Issue '{finding}' has been recorded with owner {owner} and mitigation controls.",
                "action_label": "View Issues List",
                "action_url": "?tab=records",
            }

    query = request.GET.get("q", "").strip()
    issues = get_issues_and_risks(query=query)
    ctx["issues"] = issues
    ctx["search_query"] = query
    ctx["state_card"] = state_card
    return render(request, "foundation/executive/gov_02_issues_risks.html", ctx)


# -----------------------------------------------------------------------------
# GOV-04: Request Controlled Change (Master PDF p. 669)
# -----------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def request_controlled_change_view(request):
    ctx, redirect_res = _setup_exec_context(request, "GOV-04")
    if redirect_res:
        return redirect_res

    state_card = None
    step = request.GET.get("step", "1")

    if request.method == "POST":
        title = request.POST.get("change_title", "").strip()
        reason = request.POST.get("reason", "").strip()
        module = request.POST.get("affected_module", "Reports and accountability").strip()
        risk_rollback = request.POST.get("risk_rollback", "").strip()
        requester = ctx["account"].display_name or "Ada Okafor"

        if title and reason:
            rec = submit_controlled_change(title, reason, module, risk_rollback, requester)
            state_card = {
                "title": f"Controlled Change Submitted · {rec['id']}",
                "message": f"Change request '{title}' submitted for executive review within authorized scope.",
                "action_label": "Open Decision Register",
                "action_url": "/foundation/governance/decisions/?tab=records",
            }
            step = "3"

    ctx["step"] = step
    ctx["state_card"] = state_card
    return render(request, "foundation/executive/gov_04_controlled_change.html", ctx)


# -----------------------------------------------------------------------------
# REL-01: Stakeholder Relationships Register (Master PDF p. 654)
# -----------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def stakeholder_relationships_view(request):
    ctx, redirect_res = _setup_exec_context(request, "REL-01")
    if redirect_res:
        return redirect_res

    query = request.GET.get("q", "").strip()
    relationships = get_relationships(query=query)
    ctx["relationships"] = relationships
    ctx["search_query"] = query
    return render(request, "foundation/executive/rel_01_relationships.html", ctx)


# -----------------------------------------------------------------------------
# REL-02: Review Proposed Strategic Partnership (Master PDF p. 657)
# -----------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def review_partnership_view(request):
    ctx, redirect_res = _setup_exec_context(request, "REL-02")
    if redirect_res:
        return redirect_res

    partner_id = request.GET.get("partner", "rel-01")
    relationship = get_relationship_by_id(partner_id) or get_relationship_by_id("rel-01")
    state_card = None
    actor_name = ctx["account"].display_name or "Founder & Executive Director"

    if request.method == "POST":
        action = request.POST.get("action", "")
        decision_val = request.POST.get("decision", "Further review")
        notes = request.POST.get("notes", "").strip()

        if relationship:
            updated_rel = record_partnership_decision(relationship["id"], decision_val, notes, actor_name)
            state_card = {
                "title": f"Authorized Decision Recorded · {updated_rel['relationship']}",
                "message": f"Partnership status updated to '{updated_rel['status']}' with authorized executive sign-off.",
                "action_label": "View Stakeholder Register",
                "action_url": "/foundation/relationships/?tab=records",
            }

    ctx["relationship"] = relationship
    ctx["state_card"] = state_card
    return render(request, "foundation/executive/rel_02_review_partnership.html", ctx)


# -----------------------------------------------------------------------------
# COMMS-02: Africa-wide Announcements (Master PDF p. 501)
# -----------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def continental_announcements_view(request):
    ctx, redirect_res = _setup_exec_context(request, "COMMS-02")
    if redirect_res:
        return redirect_res

    state_card = None
    actor_name = ctx["account"].display_name or "Founder & Executive Director"

    if request.method == "POST":
        title = request.POST.get("title", "").strip()
        audience = request.POST.get("audience", "HQ / Both Networks").strip()
        summary = request.POST.get("summary", "").strip()
        content = request.POST.get("content", "").strip()

        if title and content:
            new_ann = publish_continental_announcement(title, audience, summary, content, actor_name)
            state_card = {
                "title": f"Official Announcement Published · {title}",
                "message": f"Successfully published official continental announcement to audience '{audience}'.",
                "action_label": "View Live Feed",
                "action_url": "?tab=records",
            }

    query = request.GET.get("q", "").strip()
    announcements = get_announcements(query=query)
    ctx["announcements"] = announcements
    ctx["search_query"] = query
    ctx["state_card"] = state_card
    return render(request, "foundation/executive/comms_02_announcements.html", ctx)


# -----------------------------------------------------------------------------
# EVENT-01: WODDI Leadership Gathering (Master PDF p. 402)
# -----------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def events_leadership_view(request):
    from .multilingua_events_views import event_01_overview
    return event_01_overview(request)


@require_http_methods(["GET", "POST"])
def opening_plenary_view(request):
    from .multilingua_events_views import event_05_plenary
    return event_05_plenary(request)


@require_http_methods(["GET", "POST"])
def multilingua_room_view(request):
    from .multilingua_events_views import room_03_live_listener
    return room_03_live_listener(request)


# -----------------------------------------------------------------------------
# REP-05: Management Reporting (Master PDF p. 486)
# -----------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def management_reporting_view(request):
    ctx, redirect_res = _setup_exec_context(request, "REP-05")
    if redirect_res:
        return redirect_res

    data = get_management_reporting_data()
    ctx["kpis"] = data["kpis"]
    ctx["reports"] = data["reports"]
    return render(request, "foundation/executive/rep_05_management_reporting.html", ctx)


# -----------------------------------------------------------------------------
# REP-06: Performance Scorecard (Master PDF p. 489)
# -----------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def performance_scorecard_view(request):
    ctx, redirect_res = _setup_exec_context(request, "REP-06")
    if redirect_res:
        return redirect_res

    data = get_performance_scorecard_data()
    ctx["scorecard_kpis"] = data["scorecard_kpis"]
    ctx["metrics"] = data["metrics"]
    ctx["local_units"] = data["local_units"]
    return render(request, "foundation/executive/rep_06_scorecard.html", ctx)


# -----------------------------------------------------------------------------
# SAFE-04: Assigned Case Narrative Guardrail (Master PDF p. 630)
# -----------------------------------------------------------------------------
@require_http_methods(["GET", "POST"])
def confidential_safeguarding_view(request, case_id: str = "SG-024"):
    """
    FAIL-CLOSED GUARDRAIL:
    Founder & Executive Director CANNOT view confidential safeguarding case narratives (SAFE-04)
    unless explicitly assigned as designated Safeguarding Lead.
    """
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    user_scope = ctx["user_scope"]
    try:
        assert_safeguarding_access_guardrail(user_scope, case_reference=case_id)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    # Only rendered if user holds dedicated safeguarding officer clearance
    ctx, redirect_res = _setup_exec_context(request, "SAFE-04")
    if redirect_res:
        return redirect_res
    ctx["case_id"] = case_id
    return render(request, "foundation/executive/safe_04_case.html", ctx)


# -----------------------------------------------------------------------------
# Executive Direct Screen Router
# -----------------------------------------------------------------------------
def executive_screen_router(request, screen_code: str):
    code = (screen_code or "").strip().upper()
    if code.startswith("ROOM-") or code.startswith("EVENT-"):
        from .multilingua_events_views import stage10_screen_view
        return stage10_screen_view(request, code)
    mapping = {
        "GOV-03": executive_decision_register_view,
        "GOV-02": governance_issues_view,
        "GOV-04": request_controlled_change_view,
        "REL-01": stakeholder_relationships_view,
        "REL-02": review_partnership_view,
        "COMMS-02": continental_announcements_view,
        "REP-05": management_reporting_view,
        "REP-06": performance_scorecard_view,
        "SAFE-04": confidential_safeguarding_view,
    }
    view_func = mapping.get(code)
    if view_func:
        return view_func(request)
    raise Http404(f"Executive screen {screen_code} not found.")

