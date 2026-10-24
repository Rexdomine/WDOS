"""
WDOS Messaging, Communications, Learning and Resources Views
Addresses:
- COMMS-01: Inbox (Messaging, announcements and campaigns, Desktop p498, Mobile p499, State p500)
- LEARN-01: My learning and development (Learning and personal development, Desktop p564, Mobile p565, State p566)
- RES-01: Resources for your role (Resources and institutional knowledge, Desktop p585, Mobile p586, State p587)
"""

from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import Communication, DashboardReport, WorkItem


@require_http_methods(["GET", "POST"])
def messages_inbox_view(request):
    """
    COMMS-01: Inbox
    Module: Messaging, announcements and campaigns (PDF Desktop p498, Mobile p500)
    """
    from .views import _get_authenticated_context
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    user_scope = ctx["user_scope"]
    comms_qs = Communication.objects.filter(
        network__in=[user_scope.active_network or "WGMN", "ALL"],
        country__in=[user_scope.active_country or "NG", "ALL"],
    ).order_by("-sent_at")
    session_convs = []
    for comm in comms_qs:
        sent_str = comm.sent_at.strftime("%d %b · %H:%M") if comm.sent_at else ""
        session_convs.append({
            "id": f"comm-{comm.id}",
            "title": comm.subject,
            "snippet": comm.body[:90],
            "time": sent_str,
            "unread": False,
            "category": comm.priority.title() if comm.priority else "General",
            "messages": [
                {
                    "sender": comm.sender_name or "System",
                    "role": comm.target_role.title() if comm.target_role else "",
                    "text": comm.body,
                    "is_self": False,
                    "time": sent_str,
                }
            ],
        })

    active_conv_id = request.GET.get("c") or request.POST.get("conversation_id") or (session_convs[0]["id"] if session_convs else "")
    active_conv = next((c for c in session_convs if c["id"] == active_conv_id), session_convs[0] if session_convs else None)

    if request.method == "POST":
        message_body = (request.POST.get("message") or "").strip()
        if message_body:
            new_msg = {
                "sender": "You",
                "role": ctx.get("active_role_title", "Member"),
                "text": message_body,
                "is_self": True,
                "time": timezone.now().strftime("%H:%M"),
            }
            comm = Communication.objects.create(
                subject=active_conv["title"] if active_conv else message_body[:60],
                body=message_body,
                network=user_scope.active_network or "WGMN",
                country=user_scope.active_country if (user_scope.active_country and user_scope.active_country != "*") else "NG",
                target_role=user_scope.active_role or "all",
                sender_name=ctx.get("display_name") or "You",
                priority="normal",
            )
            if request.headers.get("x-requested-with") == "XMLHttpRequest":
                return JsonResponse({"status": "sent", "message": new_msg})
            return redirect(f"{request.path}?c=comm-{comm.id}")

    state_contract = request.GET.get("state", "").strip().lower()
    contracts = {
        "proposed_approval": {
            "title": "Proposed for approval",
            "message": "Your conversation update has been submitted for review before delivery.",
            "action_label": "Return to inbox",
            "action_url": request.path,
        },
        "empty": {
            "title": "No records in this view",
            "message": "There are no communications and visibility records matching the selected scope.",
            "action_label": "Clear filters",
            "action_url": request.path,
        },
        "connection_interrupted": {
            "title": "Connection interrupted",
            "message": "Your last saved information is safe. Reconnect before submitting changes.",
            "action_label": "Try again",
            "action_url": request.path,
        },
        "access_changed": {
            "title": "Access has changed",
            "message": "This action is no longer available for your current role. No change was applied.",
            "action_label": "Return to workspace",
            "action_url": "/foundation/dashboard/",
        },
        "loading": {
            "title": "Loading current information",
            "message": "Loading inbox. No stale values or completed actions are implied.",
            "action_label": "Cancel and return",
            "action_url": request.path,
        },
        "more_info": {
            "title": "More information needed",
            "message": "Check the marked details before continuing with inbox. Your entered information remains available.",
            "action_label": "Review details",
            "action_url": request.path,
        },
    }
    state_feedback = contracts.get(state_contract)

    breadcrumbs = [
        {"label": "Workspace", "url": "/foundation/"},
        {"label": "Messaging, announcements and campaigns", "url": "", "is_current": True},
    ]

    active_tab = request.GET.get("tab", "overview").lower()
    if state_contract == "empty":
        conversations_to_show = []
    elif active_tab in ("announcements", "records"):
        conversations_to_show = [
            c for c in session_convs
            if c.get("category", "").lower() in ("announcement", "urgent", "high", "governance", "coordination")
            or c.get("unread")
        ]
    elif active_tab in ("sent", "history"):
        conversations_to_show = [
            c for c in session_convs
            if any(m.get("is_self") for m in c.get("messages", [])) or not c.get("unread")
        ]
    else:
        conversations_to_show = session_convs

    ctx.update({
        "screen_id": "COMMS-01",
        "active_nav": "messages",
        "breadcrumbs": breadcrumbs,
        "custom_breadcrumbs": breadcrumbs,
        "page_title": "Inbox",
        "page_description": "Find authorised direct, team and group conversations, attachments and unread replies.",
        "conversations": conversations_to_show,
        "active_conv": active_conv if state_contract != "empty" else None,
        "state_feedback": state_feedback,
        "active_tab": active_tab,
        "total_conversations_count": len(conversations_to_show),
    })

    return render(request, "foundation/comms_01_inbox.html", ctx)


@require_http_methods(["GET"])
def learning_development_view(request):
    """
    LEARN-01: My learning and development
    Module: Learning and personal development (PDF Desktop p564, Mobile p565, State p566)
    """
    from .views import _get_authenticated_context
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    state_contract = request.GET.get("state", "").strip().lower()
    contracts = {
        "empty": {
            "title": "No records in this view",
            "message": "There are no leadership development records matching the selected scope.",
            "action_label": "Clear filters",
            "action_url": request.path,
        },
        "nothing_in_scope": {
            "title": "Nothing to show in this scope",
            "message": "There are no matching records for my learning and development. Check the current scope or remove a filter.",
            "action_label": "Reset view",
            "action_url": request.path,
        },
        "connection_interrupted": {
            "title": "Connection interrupted",
            "message": "Your last saved information is safe. Reconnect before submitting changes.",
            "action_label": "Try again",
            "action_url": request.path,
        },
        "access_changed": {
            "title": "Access has changed",
            "message": "This action is no longer available for your current role. No change was applied.",
            "action_label": "Return to workspace",
            "action_url": "/foundation/dashboard/",
        },
        "loading": {
            "title": "Loading current information",
            "message": "Loading my learning and development. No stale values or completed actions are implied.",
            "action_label": "Cancel and return",
            "action_url": request.path,
        },
    }
    state_feedback = contracts.get(state_contract)

    breadcrumbs = [
        {"label": "Workspace", "url": "/foundation/"},
        {"label": "Learning and personal development", "url": "", "is_current": True},
    ]

    active_tab = request.GET.get("tab", "overview").lower()
    if state_contract in ("empty", "nothing_in_scope"):
        learning_items = []
    else:
        user_scope = ctx["user_scope"]
        qs = WorkItem.objects.filter(
            category__in=["learning", "orientation", "training"],
            network__in=user_scope.allowed_networks,
        ).order_by("-created_at")
        learning_items = [
            {
                "code": f"LRN-{wi.id}",
                "title": wi.title,
                "description": wi.summary,
                "requirement": "Required" if wi.priority in ("urgent", "high", "critical") else "Recommended",
                "due": wi.created_at.strftime("%d %b") if wi.created_at else "",
                "progress": "In progress" if wi.status == "in_progress" else ("Completed" if wi.status == "completed" else "Not started"),
                "progress_badge": wi.status,
                "type": wi.category.title(),
                "action_label": "Open",
                "action_url": wi.target_url or f"/foundation/work-queue/{wi.id}/",
            }
            for wi in qs
        ]

    ctx.update({
        "screen_id": "LEARN-01",
        "active_nav": "learning",
        "breadcrumbs": breadcrumbs,
        "custom_breadcrumbs": breadcrumbs,
        "page_title": "My learning and development",
        "page_description": "See required, recommended and optional learning with due dates and the next action.",
        "learning_items": learning_items,
        "state_feedback": state_feedback,
        "active_tab": active_tab,
        "total_items_count": len(learning_items),
    })

    return render(request, "foundation/learn_01_learning.html", ctx)


@require_http_methods(["GET"])
def resources_view(request):
    """
    RES-01: Resources for your role
    Module: Resources and institutional knowledge (PDF Desktop p585, Mobile p586, State p587)
    """
    from .views import _get_authenticated_context
    ctx, redirect_response = _get_authenticated_context(request)
    if redirect_response:
        return redirect_response

    state_contract = request.GET.get("state", "").strip().lower()
    contracts = {
        "empty": {
            "title": "No records in this view",
            "message": "There are no resources and knowledge records matching the selected scope.",
            "action_label": "Clear filters",
            "action_url": request.path,
        },
        "nothing_in_scope": {
            "title": "Nothing to show in this scope",
            "message": "There are no matching records for resources for your role. Check the current scope or remove a filter.",
            "action_label": "Reset view",
            "action_url": request.path,
        },
        "connection_interrupted": {
            "title": "Connection interrupted",
            "message": "Your last saved information is safe. Reconnect before submitting changes.",
            "action_label": "Try again",
            "action_url": request.path,
        },
    }
    state_feedback = contracts.get(state_contract)

    breadcrumbs = [
        {"label": "Workspace", "url": "/foundation/"},
        {"label": "Resources and institutional knowledge", "url": "", "is_current": True},
    ]

    active_tab = request.GET.get("tab", "overview").lower()
    if state_contract in ("empty", "nothing_in_scope"):
        resources = []
    else:
        user_scope = ctx["user_scope"]
        rep_qs = DashboardReport.objects.filter(
            status="published",
            network__in=[user_scope.active_network or "WGMN", "ALL"],
        ).order_by("-created_at")
        resources = [
            {
                "code": f"RES-{r.id}",
                "title": r.title,
                "description": r.summary,
                "version": r.period or "v1",
                "format": "Document",
                "effective": r.created_at.strftime("%d %b") if r.created_at else "",
                "access": "Read / download",
                "category": r.report_type.replace("_", " ").title() if r.report_type else "Guidance",
            }
            for r in rep_qs
        ]

    ctx.update({
        "screen_id": "RES-01",
        "active_nav": "learning",
        "breadcrumbs": breadcrumbs,
        "custom_breadcrumbs": breadcrumbs,
        "page_title": "Resources for your role",
        "page_description": "Find current policies, role packs, templates and guidance within the user’s permitted scope.",
        "resources": resources,
        "state_feedback": state_feedback,
        "active_tab": active_tab,
        "total_resources_count": len(resources),
    })

    return render(request, "foundation/res_01_resources.html", ctx)
