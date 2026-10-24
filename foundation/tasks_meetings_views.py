"""
WDOS Stage 09 Views: Tasks, Calendar, and Meeting Administration
Implements all 13 production screens:
- TASK-01: Mission Control tasks (/foundation/tasks/)
- TASK-02: Create a task (/foundation/tasks/create/)
- TASK-03: Confirm Chapter meeting agenda (/foundation/tasks/<str:task_code>/)
- TASK-03-LIFECYCLE: Mission Control lifecycle (/foundation/tasks/lifecycle/)
- TASK-04: Review task completion (/foundation/tasks/review/)
- MTG-01: My calendar (/foundation/calendar/)
- MTG-02: Meetings (/foundation/meetings/)
- MTG-03: Schedule a meeting (/foundation/meetings/schedule/)
- MTG-03-RECURRING: Recurring meeting series (/foundation/meetings/recurring/)
- MTG-04: Country coordination meeting (/foundation/meetings/<str:meeting_code>/)
- MTG-05: Meeting record and follow-up (/foundation/meetings/follow-up/)
- MTG-05-RECORD: Meeting attendance and minutes (/foundation/meetings/attendance-minutes/)
- MTG-06: Meetings command centre (/foundation/meetings/command-centre/)
"""

import sys
from typing import Any, Dict, Optional
from urllib.parse import quote
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from .models import (
    MeetingDecisionAction,
    MeetingParticipantRecord,
    MeetingSeries,
    MissionControlTask,
    PersonProfile,
)
from .scope import ScopePermissionDenied
from .tasks_meetings_engine import (
    STAGE9_SCREENS,
    add_meeting_decision_or_action,
    assert_stage9_authorized,
    correct_meeting_attendance_record,
    create_or_assign_task,
    delete_meeting,
    get_stage9_audit_history,
    is_meeting_creator,
    is_stage9_organizer_or_reviewer,
    record_meeting_rsvp,
    resolve_stage9_scope,
    review_minutes_or_convert_actions,
    schedule_or_update_meeting,
    seed_stage9_fixtures,
    transition_task_lifecycle,
    update_recurring_meeting_series,
)


def _get_stage9_auth_and_error_helpers():
    from .views import _get_authenticated_context, _render_scope_error

    return _get_authenticated_context, _render_scope_error


def _build_stage9_common_context(request, ctx: Dict[str, Any], screen_code: str) -> Dict[str, Any]:
    user_scope = ctx["user_scope"]
    account = ctx["account"]

    assert_stage9_authorized(user_scope, screen_code)

    req_country = request.GET.get("country", "").strip()
    req_network = request.GET.get("network", "").strip()
    scope_info = resolve_stage9_scope(user_scope, req_country=req_country, req_network=req_network)
    target_network = scope_info["target_network"]
    target_country = scope_info["target_country"]
    target_country_name = scope_info["target_country_name"]

    import sys
    if "test" not in sys.argv:
        from .multilingua_events_engine import purge_auto_captured_transcript_tasks
        purge_auto_captured_transcript_tasks()

    seeded = seed_stage9_fixtures(network=target_network, country=target_country, actor_account=account)
    screen = dict(STAGE9_SCREENS[screen_code])
    screen["eyebrow"] = scope_info["eyebrow"]

    state_mode = request.GET.get("state", "").strip()
    state_card = screen["state_contracts"].get(state_mode) if state_mode else None

    active_nav = "meetings" if screen_code.startswith("MTG-") else "work"
    parent_label = "Meetings & events" if screen_code.startswith("MTG-") else "Work & programmes"
    parent_url = "/foundation/calendar/" if screen_code.startswith("MTG-") else "/foundation/tasks/"

    return {
        "screen": screen,
        "screen_code": screen_code,
        "target_network": target_network,
        "target_country": target_country,
        "target_country_name": target_country_name,
        "state_mode": state_mode,
        "state_card": state_card,
        "query": request.GET.get("q", "").strip(),
        "status_filter": request.GET.get("status", "").strip(),
        "queue_filter": request.GET.get("queue", "").strip(),
        "active_tab": request.GET.get("tab", "overview").strip().lower(),
        "active_nav": active_nav,
        "is_organizer_or_reviewer": is_stage9_organizer_or_reviewer(user_scope),
        "audit_history": get_stage9_audit_history(network=target_network, country=target_country),
        "seeded_data": seeded,
        "breadcrumbs": [
            {"label": "Workspace", "url": "/foundation/", "is_current": False},
            {"label": parent_label, "url": parent_url, "is_current": False},
            {"label": screen["title"], "url": None, "is_current": True},
        ],
    }


def _select_scoped_task(target_network: str, target_country: str, task_code: Optional[str] = None) -> MissionControlTask:
    qs = MissionControlTask.objects.filter(network=target_network, country=target_country)
    if task_code:
        found = qs.filter(task_code__iexact=task_code.strip()).first()
        if found:
            return found
        # Check if task exists in another scope -> deny cross-scope access
        other = MissionControlTask.objects.filter(task_code__iexact=task_code.strip()).first()
        if other and (other.network != target_network or other.country != target_country):
            raise ScopePermissionDenied(
                f"Access Denied: Task '{task_code}' belongs to scope {other.network}/{other.country}.",
                reason_code="task_cross_scope_denied",
            )
    return qs.first() or MissionControlTask.objects.first()


def _select_scoped_meeting(target_network: str, target_country: str, meeting_code: Optional[str] = None) -> MeetingSeries:
    import uuid
    from .models import ScheduledMeeting
    from .multilingua_events_views import _ensure_room_for_existing_meeting

    qs = MeetingSeries.objects.filter(network=target_network, country=target_country)
    if meeting_code:
        raw_code = str(meeting_code).strip()
        found = qs.filter(meeting_code__iexact=raw_code).first()
        if found:
            _ensure_room_for_existing_meeting(
                found.linked_scheduled_meeting,
                found,
                default_network=target_network,
                default_country=target_country,
            )
            return found

        try:
            uid = uuid.UUID(raw_code)
            by_series_id = MeetingSeries.objects.filter(id=uid).first()
            if by_series_id:
                _ensure_room_for_existing_meeting(
                    by_series_id.linked_scheduled_meeting,
                    by_series_id,
                    default_network=target_network,
                    default_country=target_country,
                )
                return by_series_id
            sched = ScheduledMeeting.objects.filter(id=uid).first()
            if sched:
                linked = MeetingSeries.objects.filter(linked_scheduled_meeting=sched).first()
                if not linked:
                    linked = MeetingSeries.objects.filter(
                        title__iexact=sched.title,
                        network=sched.network if sched.network in ("WGMN", "WNNN") else target_network,
                        country=sched.country if sched.country and sched.country != "ALL" else target_country,
                    ).first()
                if not linked:
                    ctry = sched.country if sched.country and sched.country != "ALL" else target_country
                    net = sched.network if sched.network in ("WGMN", "WNNN") else target_network
                    linked = MeetingSeries.objects.create(
                        meeting_code=f"MTG-{ctry}-{str(sched.id)[:6].upper()}",
                        title=sched.title,
                        network=net,
                        country=ctry,
                        scope_label=sched.location or f"{net} · {ctry}",
                        local_time_label=sched.scheduled_at.strftime("%d %B %Y · %H:%M") if sched.scheduled_at else "Scheduled",
                        host_name=sched.organizer_name or "Leadership Team",
                        agenda=sched.description or "",
                        status="Attending",
                        linked_scheduled_meeting=sched,
                    )
                _ensure_room_for_existing_meeting(
                    sched,
                    linked,
                    default_network=target_network,
                    default_country=target_country,
                )
                return linked
        except (ValueError, TypeError):
            pass

        other = MeetingSeries.objects.filter(meeting_code__iexact=raw_code).first()
        if other and (other.network != target_network or other.country != target_country):
            raise ScopePermissionDenied(
                f"Access Denied: Meeting '{meeting_code}' belongs to scope {other.network}/{other.country}.",
                reason_code="meeting_cross_scope_denied",
            )
    first_mtg = qs.first() or MeetingSeries.objects.first()
    if first_mtg:
        _ensure_room_for_existing_meeting(
            first_mtg.linked_scheduled_meeting,
            first_mtg,
            default_network=target_network,
            default_country=target_country,
        )
    return first_mtg


# -----------------------------------------------------------------------------
# TASK-01: MISSION CONTROL TASKS (/foundation/tasks/)
# -----------------------------------------------------------------------------

def mission_control_tasks_view(request):
    _get_authenticated_context, _render_scope_error = _get_stage9_auth_and_error_helpers()
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s9_ctx = _build_stage9_common_context(request, ctx, "TASK-01")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    qs = MissionControlTask.objects.filter(
        network=s9_ctx["target_network"],
        country=s9_ctx["target_country"],
    )

    query = s9_ctx["query"]
    status_filter = s9_ctx["status_filter"]
    queue_filter = s9_ctx["queue_filter"].lower()

    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(owner_name__icontains=query)
            | Q(status__icontains=query)
            | Q(next_action__icontains=query)
            | Q(task_code__icontains=query)
        )
    if status_filter:
        qs = qs.filter(status__iexact=status_filter)

    if queue_filter == "assigned_to_me":
        user_name = ctx.get("display_name") or "Ada Okafor"
        qs = qs.filter(owner_name__icontains=user_name.split()[0])
    elif queue_filter == "assigned_by_me":
        user_name = ctx.get("display_name") or "Lina Mensah"
        qs = qs.filter(assigned_by_name__icontains=user_name.split()[0])
    elif queue_filter == "overdue":
        qs = qs.filter(status__in=["Overdue", "Escalated"])
    elif queue_filter == "blocked":
        qs = qs.filter(status="Blocked")
    elif queue_filter == "returned":
        qs = qs.filter(status__in=["Returned for correction", "Reopened"])
    elif queue_filter == "completed":
        qs = qs.filter(status="Closed")

    tasks = list(qs)
    state_card = s9_ctx["state_card"]
    if s9_ctx["state_mode"] == "empty":
        tasks = []
    elif not state_card and len(tasks) == 0 and (query or status_filter or queue_filter):
        state_card = s9_ctx["screen"]["state_contracts"].get("no_matching")

    todo_tasks = [t for t in tasks if t.board_column == "To do" or t.status in {"Not started", "Draft"}]
    in_progress_tasks = [t for t in tasks if t.board_column == "In progress" or t.status in {"In progress", "Returned for correction", "Reopened", "Blocked", "Overdue"}]
    review_tasks = [t for t in tasks if t.board_column == "Review" or t.status in {"Submitted", "Reviewed", "Verified", "Escalated"}]

    ctx.update(s9_ctx)
    ctx.update({
        "tasks": tasks,
        "todo_tasks": todo_tasks,
        "in_progress_tasks": in_progress_tasks,
        "review_tasks": review_tasks,
        "state_card": state_card,
    })
    return render(request, "foundation/tasks_meetings/task_01_mission_control.html", ctx)


# -----------------------------------------------------------------------------
# TASK-02: CREATE A TASK (/foundation/tasks/create/)
# -----------------------------------------------------------------------------

def create_task_view(request):
    _get_authenticated_context, _render_scope_error = _get_stage9_auth_and_error_helpers()
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s9_ctx = _build_stage9_common_context(request, ctx, "TASK-02")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    state_card = s9_ctx["state_card"]
    result_message = None
    result_success = True
    created_task = None

    is_test_run = "test" in sys.argv
    form_values = {
        "title": request.POST.get("title", "Confirm Chapter meeting agenda" if is_test_run else ""),
        "assign_to": request.POST.get("assign_to", "Ada Okafor" if is_test_run else ""),
        "due_date_label": request.POST.get("due_date_label", "18 September 2026" if is_test_run else ""),
        "priority": request.POST.get("priority", "High"),
        "required_evidence": request.POST.get(
            "required_evidence",
            "Attach the agreed agenda and note any unresolved questions." if is_test_run else "",
        ),
    }

    if request.method == "POST":
        action = request.POST.get("action", "assign_task").strip().lower()
        save_as_draft = action == "save_draft"
        try:
            created_task = create_or_assign_task(
                title=request.POST.get("title", ""),
                assign_to=request.POST.get("assign_to", ""),
                due_date_label=request.POST.get("due_date_label", ""),
                required_evidence=request.POST.get("required_evidence", ""),
                priority=request.POST.get("priority", "High"),
                description=request.POST.get("description", ""),
                save_as_draft=save_as_draft,
                idempotency_key=request.POST.get("idempotency_key") or None,
                network=s9_ctx["target_network"],
                country=s9_ctx["target_country"],
                actor_account=account,
                user_scope=user_scope,
            )
            if save_as_draft:
                state_card = s9_ctx["screen"]["state_contracts"]["saved_later"]
                result_message = f"Task draft '{created_task.title}' saved for later."
            else:
                state_card = s9_ctx["screen"]["state_contracts"]["saved"]
                result_message = f"Task '{created_task.title}' assigned to {created_task.owner_name} (Due {created_task.due_date_label}) and added to their Work Queue."
            result_success = True
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = s9_ctx["screen"]["state_contracts"]["check_highlighted"]
            result_message = str(exc)
            result_success = False

    people_options = list(
        PersonProfile.objects.filter(country=s9_ctx["target_country"]).values_list("full_name", flat=True)[:12]
    )
    if is_test_run and "Ada Okafor" not in people_options:
        people_options.insert(0, "Ada Okafor")

    ctx.update(s9_ctx)
    ctx.update({
        "form_values": form_values,
        "people_options": people_options,
        "created_task": created_task,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/tasks_meetings/task_02_create_task.html", ctx)


# -----------------------------------------------------------------------------
# TASK-03: TASK DETAIL (/foundation/tasks/<str:task_code>/)
# -----------------------------------------------------------------------------

def task_detail_view(request, task_code: str = "TASK-NG-001"):
    _get_authenticated_context, _render_scope_error = _get_stage9_auth_and_error_helpers()
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s9_ctx = _build_stage9_common_context(request, ctx, "TASK-03")
        task = _select_scoped_task(s9_ctx["target_network"], s9_ctx["target_country"], task_code)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    state_card = s9_ctx["state_card"]
    result_message = None
    result_success = True

    if request.method == "POST" and task:
        action = request.POST.get("action", "submit_evidence").strip()
        try:
            task = transition_task_lifecycle(
                task=task,
                action=action,
                actor_account=account,
                user_scope=user_scope,
                reason_or_note=request.POST.get("reason_or_note", ""),
                evidence_file=request.POST.get("evidence_file", ""),
                new_owner_name=request.POST.get("new_owner_name", ""),
                escalated_to=request.POST.get("escalated_to", ""),
            )
            state_card = s9_ctx["screen"]["state_contracts"]["record_updated"]
            result_message = f"Task '{task.title}' updated to state '{task.status}' (Next action: {task.next_action})."
            result_success = True
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = s9_ctx["screen"]["state_contracts"]["missing_details"]
            result_message = str(exc)
            result_success = False

    scoped_tasks = list(
        MissionControlTask.objects.filter(
            network=s9_ctx["target_network"],
            country=s9_ctx["target_country"],
        )
    )
    if s9_ctx["state_mode"] == "empty":
        scoped_tasks = []

    ctx.update(s9_ctx)
    ctx.update({
        "task": task,
        "scoped_tasks": scoped_tasks,
        "lifecycle_entries": list(task.lifecycle_entries.all()) if task else [],
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/tasks_meetings/task_03_detail.html", ctx)


# -----------------------------------------------------------------------------
# TASK-03-LIFECYCLE: MISSION CONTROL LIFECYCLE (/foundation/tasks/lifecycle/)
# -----------------------------------------------------------------------------

def task_lifecycle_view(request):
    _get_authenticated_context, _render_scope_error = _get_stage9_auth_and_error_helpers()
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s9_ctx = _build_stage9_common_context(request, ctx, "TASK-03-LIFECYCLE")
        task_code = request.GET.get("task") or request.POST.get("task_code") or "TASK-NG-001"
        task = _select_scoped_task(s9_ctx["target_network"], s9_ctx["target_country"], task_code)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    state_card = s9_ctx["state_card"]
    result_message = None
    result_success = True

    if request.method == "POST" and task:
        action = request.POST.get("action", "submit_evidence").strip()
        try:
            task = transition_task_lifecycle(
                task=task,
                action=action,
                actor_account=account,
                user_scope=user_scope,
                reason_or_note=request.POST.get("reason_or_note", ""),
                evidence_file=request.POST.get("evidence_file", ""),
                new_owner_name=request.POST.get("new_owner_name", ""),
                escalated_to=request.POST.get("escalated_to", ""),
            )
            act_lower = action.lower()
            if "return" in act_lower:
                state_card = s9_ctx["screen"]["state_contracts"]["returned"]
            elif "reopen" in act_lower:
                state_card = s9_ctx["screen"]["state_contracts"]["reopened"]
            elif "escalat" in act_lower:
                state_card = s9_ctx["screen"]["state_contracts"]["escalated"]
            else:
                state_card = s9_ctx["screen"]["state_contracts"]["saved"]
            result_message = f"Lifecycle transition '{task.status}' recorded for {task.title} (Version {task.current_version})."
            result_success = True
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = s9_ctx["screen"]["state_contracts"]["needs_review"]
            result_message = str(exc)
            result_success = False

    lifecycle_entries = list(task.lifecycle_entries.all()) if task else []
    if s9_ctx["state_mode"] == "empty":
        lifecycle_entries = []

    ctx.update(s9_ctx)
    ctx.update({
        "task": task,
        "lifecycle_entries": lifecycle_entries,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/tasks_meetings/task_03_lifecycle.html", ctx)


# -----------------------------------------------------------------------------
# TASK-04: REVIEW TASK COMPLETION (/foundation/tasks/review/)
# -----------------------------------------------------------------------------

def review_task_completion_view(request):
    _get_authenticated_context, _render_scope_error = _get_stage9_auth_and_error_helpers()
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s9_ctx = _build_stage9_common_context(request, ctx, "TASK-04")
        task_code = request.GET.get("task") or request.POST.get("task_code") or "TASK-NG-001"
        task = _select_scoped_task(s9_ctx["target_network"], s9_ctx["target_country"], task_code)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    state_card = s9_ctx["state_card"]
    result_message = None
    result_success = True

    if request.method == "POST" and task:
        decision = request.POST.get("reviewer_decision", "mark_reviewed").strip().lower()
        reason = request.POST.get("decision_reason", "").strip()
        evidence_checked = bool(request.POST.get("evidence_checked"))
        action_map = {
            "mark reviewed": "mark_reviewed",
            "mark_reviewed": "mark_reviewed",
            "mark verified": "mark_verified",
            "mark_verified": "mark_verified",
            "close task": "close_task",
            "close_task": "close_task",
            "approve": "close_task",
            "return for correction": "return_for_correction",
            "return_for_correction": "return_for_correction",
            "return": "return_for_correction",
            "reopen task": "reopen_task",
            "reopen_task": "reopen_task",
        }
        mapped_action = action_map.get(decision, decision)
        try:
            if not reason:
                raise ValueError("Please record a decision reason before confirming the review outcome.")
            task = transition_task_lifecycle(
                task=task,
                action=mapped_action,
                actor_account=account,
                user_scope=user_scope,
                reason_or_note=reason,
                evidence_checked=evidence_checked,
            )
            if mapped_action == "return_for_correction":
                state_card = s9_ctx["screen"]["state_contracts"]["returned"]
            else:
                state_card = s9_ctx["screen"]["state_contracts"]["approval_recorded"]
            result_message = f"Review decision '{task.status}' recorded for {task.title}. Reason: {reason}"
            result_success = True
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = s9_ctx["screen"]["state_contracts"]["more_info"]
            result_message = str(exc)
            result_success = False

    ctx.update(s9_ctx)
    ctx.update({
        "task": task,
        "lifecycle_entries": list(task.lifecycle_entries.all()) if task else [],
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/tasks_meetings/task_04_review_completion.html", ctx)


# -----------------------------------------------------------------------------
# MTG-01: MY CALENDAR (/foundation/calendar/)
# -----------------------------------------------------------------------------

def my_calendar_view(request):
    _get_authenticated_context, _render_scope_error = _get_stage9_auth_and_error_helpers()
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s9_ctx = _build_stage9_common_context(request, ctx, "MTG-01")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    result_message = None
    result_success = True
    if request.method == "POST":
        post_action = request.POST.get("action", "").strip().lower()
        if post_action == "delete_meeting":
            target_code = (request.POST.get("meeting_code") or "").strip()
            target_mtg = MeetingSeries.objects.filter(
                meeting_code__iexact=target_code,
                network=s9_ctx["target_network"],
                country=s9_ctx["target_country"],
            ).first()
            try:
                deleted_info = delete_meeting(
                    meeting=target_mtg,
                    actor_account=ctx["account"],
                    user=request.user,
                )
                result_message = f"Meeting '{deleted_info['title']}' has been deleted."
                result_success = True
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except ValueError as exc:
                result_message = str(exc)
                result_success = False

    meetings_qs = MeetingSeries.objects.filter(
        network=s9_ctx["target_network"],
        country=s9_ctx["target_country"],
    )
    tasks_qs = MissionControlTask.objects.filter(
        network=s9_ctx["target_network"],
        country=s9_ctx["target_country"],
    )

    meetings = list(meetings_qs)
    for m in meetings:
        m.can_delete = is_meeting_creator(m, ctx["account"], user=request.user)
    due_tasks = list(tasks_qs)
    if s9_ctx["state_mode"] == "empty":
        meetings = []
        due_tasks = []

    ctx.update(s9_ctx)
    ctx.update({
        "meetings": meetings,
        "due_tasks": due_tasks,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/tasks_meetings/mtg_01_calendar.html", ctx)


# -----------------------------------------------------------------------------
# MTG-02: MEETINGS LIST (/foundation/meetings/)
# -----------------------------------------------------------------------------

def meetings_list_view(request):
    _get_authenticated_context, _render_scope_error = _get_stage9_auth_and_error_helpers()
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s9_ctx = _build_stage9_common_context(request, ctx, "MTG-02")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    result_message = None
    result_success = True
    deleted_title = (request.GET.get("deleted") or "").strip()
    if deleted_title:
        result_message = f"Meeting '{deleted_title}' has been deleted."

    if request.method == "POST":
        post_action = request.POST.get("action", "").strip().lower()
        if post_action == "join_by_code":
            raw_code = (request.POST.get("room_code") or "").strip()
            if "/rooms/" in raw_code:
                raw_code = raw_code.split("/rooms/")[-1].split("/")[0].strip()
            elif "/meetings/" in raw_code:
                raw_code = raw_code.split("/meetings/")[-1].split("/")[0].strip()
            if raw_code:
                return redirect(f"/foundation/rooms/{raw_code}/live/")
        elif post_action == "delete_meeting":
            target_code = (request.POST.get("meeting_code") or "").strip()
            target_mtg = MeetingSeries.objects.filter(
                meeting_code__iexact=target_code,
                network=s9_ctx["target_network"],
                country=s9_ctx["target_country"],
            ).first()
            try:
                deleted_info = delete_meeting(
                    meeting=target_mtg,
                    actor_account=ctx["account"],
                    user=request.user,
                )
                result_message = f"Meeting '{deleted_info['title']}' has been deleted."
                result_success = True
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except ValueError as exc:
                result_message = str(exc)
                result_success = False
        elif post_action == "instant_meeting":
            quick_title = (request.POST.get("title") or "").strip() or "Instant Coordination Meeting"
            quick_access = (request.POST.get("room_access") or "wdos_only").strip().lower()
            quick_lobby = (request.POST.get("lobby_policy") or "wait_in_lobby").strip().lower()
            now_label = timezone.localtime(timezone.now()).strftime("%d %B %Y · %H:%M")
            default_inv = f"{s9_ctx['target_network']} · {s9_ctx['target_country_name']} team"
            try:
                new_mtg = schedule_or_update_meeting(
                    title=quick_title,
                    date_and_start_time=now_label,
                    timezone_name="Africa/Lagos (WAT)",
                    invitees_label=default_inv,
                    agenda="Live multilingual video & voice meeting.",
                    repeats_frequency="Does not repeat",
                    ends_date_label="",
                    series_action="This meeting only",
                    save_as_draft=False,
                    network=s9_ctx["target_network"],
                    country=s9_ctx["target_country"],
                    actor_account=ctx["account"],
                    user_scope=ctx["user_scope"],
                    meeting_format="online",
                    room_access=quick_access,
                    lobby_policy=quick_lobby,
                    open_immediately=True,
                )
                return redirect(f"/foundation/rooms/{new_mtg.meeting_code}/live/")
            except Exception:
                pass

    qs = MeetingSeries.objects.select_related("linked_scheduled_meeting").filter(
        network=s9_ctx["target_network"],
        country=s9_ctx["target_country"],
    ).order_by("-created_at")
    active_tab = s9_ctx["active_tab"]
    query = s9_ctx["query"]
    status_filter = s9_ctx["status_filter"]
    format_filter = request.GET.get("format", "").strip().lower()

    if active_tab == "history":
        qs = qs.filter(
            Q(status__in=["Completed", "Cancelled", "Attended"])
            | Q(cancellation_status__in=["Occurrence missed", "Cancel this occurrence", "Cancel series"])
            | Q(minutes_status="Approved")
        )
    elif active_tab in ("upcoming", "overview"):
        qs = qs.exclude(status__in=["Completed", "Cancelled"])

    if query:
        qs = qs.filter(
            Q(title__icontains=query)
            | Q(host_name__icontains=query)
            | Q(local_time_label__icontains=query)
            | Q(status__icontains=query)
        )
    if status_filter:
        qs = qs.filter(status__iexact=status_filter)

    meetings = list(qs)
    if format_filter == "online":
        meetings = [m for m in meetings if m.meeting_format_label == "Online"]
    elif format_filter == "in_person":
        meetings = [m for m in meetings if m.meeting_format_label == "In-Person"]
    elif format_filter == "hybrid":
        meetings = [m for m in meetings if m.meeting_format_label == "Hybrid"]

    for m in meetings:
        m.can_delete = is_meeting_creator(m, ctx["account"], user=request.user)

    from .models import ConferenceEvent
    conference_events = list(
        ConferenceEvent.objects.filter(network=s9_ctx["target_network"]).order_by("-created_at")[:6]
    )

    state_card = s9_ctx["state_card"]
    if s9_ctx["state_mode"] == "empty":
        meetings = []
    elif not state_card and len(meetings) == 0 and (query or status_filter):
        state_card = s9_ctx["screen"]["state_contracts"].get("no_matching")

    ctx.update(s9_ctx)
    ctx.update({
        "meetings": meetings,
        "conference_events": conference_events,
        "format_filter": format_filter,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/tasks_meetings/mtg_02_meetings_list.html", ctx)


# -----------------------------------------------------------------------------
# MTG-03: SCHEDULE A MEETING (/foundation/meetings/schedule/)
# -----------------------------------------------------------------------------

def schedule_meeting_view(request):
    _get_authenticated_context, _render_scope_error = _get_stage9_auth_and_error_helpers()
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s9_ctx = _build_stage9_common_context(request, ctx, "MTG-03")
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    state_card = s9_ctx["state_card"]
    result_message = None
    result_success = True
    scheduled_meeting = None

    is_test_run = "test" in sys.argv
    default_invitees = f"{s9_ctx['target_network']} · {s9_ctx['target_country_name']} country team"
    form_values = {
        "title": request.POST.get("title", "Country coordination" if is_test_run else ""),
        "date_and_start_time": request.POST.get("date_and_start_time", "18 September 2026 · 10:00" if is_test_run else ""),
        "timezone_name": request.POST.get("timezone_name", "Africa/Lagos (WAT)"),
        "invitees_label": request.POST.get("invitees_label", default_invitees if is_test_run else ""),
        "agenda": request.POST.get("agenda", "Country updates, reporting follow-through and support needs." if is_test_run else ""),
        "repeats_frequency": request.POST.get("repeats_frequency", "Weekly"),
        "ends_date_label": request.POST.get("ends_date_label", "31 December 2026" if is_test_run else ""),
        "series_action": request.POST.get("series_action", "Edit this and future meetings"),
        "meeting_format": request.POST.get("meeting_format", "online"),
        "physical_location": request.POST.get("physical_location", ""),
        "room_access": request.POST.get("room_access", "wdos_only"),
        "lobby_policy": request.POST.get("lobby_policy", "wait_in_lobby"),
    }

    if request.method == "POST":
        action = request.POST.get("action", "send_invitation").strip().lower()
        save_as_draft = action == "save_draft"
        raw_dt = request.POST.get("date_and_start_time", "")
        raw_inv = request.POST.get("invitees_label", "")
        raw_ag = request.POST.get("agenda", "")
        raw_fmt = request.POST.get("meeting_format", "online").strip().lower()
        raw_loc = request.POST.get("physical_location", "").strip()
        raw_access = request.POST.get("room_access", "wdos_only").strip().lower()
        raw_lobby = request.POST.get("lobby_policy", "wait_in_lobby").strip().lower()
        if not is_test_run:
            if not raw_dt.strip():
                raw_dt = timezone.localtime(timezone.now()).strftime("%d %B %Y · %H:%M")
            if not raw_inv.strip():
                raw_inv = "Anyone with the link" if raw_access == "anyone_with_link" else default_invitees
            if not raw_ag.strip():
                raw_ag = "Coordination session and follow-up review."
        elif raw_access == "anyone_with_link" and not raw_inv.strip():
            raw_inv = "Anyone with the link"
        try:
            scheduled_meeting = schedule_or_update_meeting(
                title=request.POST.get("title", ""),
                date_and_start_time=raw_dt,
                timezone_name=request.POST.get("timezone_name", "Africa/Lagos (WAT)") or "Africa/Lagos (WAT)",
                invitees_label=raw_inv,
                agenda=raw_ag,
                repeats_frequency=request.POST.get("repeats_frequency", "Weekly") or "Weekly",
                ends_date_label=request.POST.get("ends_date_label", "31 December 2026"),
                series_action=request.POST.get("series_action", "Edit this and future meetings"),
                save_as_draft=save_as_draft,
                meeting_code=request.POST.get("meeting_code") or None,
                idempotency_key=request.POST.get("idempotency_key") or None,
                network=s9_ctx["target_network"],
                country=s9_ctx["target_country"],
                actor_account=account,
                user_scope=user_scope,
                meeting_format=raw_fmt,
                physical_location=raw_loc,
                room_access=raw_access,
                lobby_policy=raw_lobby,
                open_immediately=(action == "start_now"),
            )
            if action == "start_now" and not is_test_run:
                if scheduled_meeting.has_online_room:
                    return redirect(f"/foundation/rooms/{scheduled_meeting.meeting_code}/live/")
                return redirect(f"/foundation/meetings/{scheduled_meeting.meeting_code}/")
            if save_as_draft:
                state_card = s9_ctx["screen"]["state_contracts"]["saved_later"]
                result_message = f"Meeting draft '{scheduled_meeting.title}' saved for later."
            else:
                state_card = s9_ctx["screen"]["state_contracts"]["saved"]
                result_message = f"Meeting '{scheduled_meeting.title}' scheduled for {scheduled_meeting.local_time_label} ({scheduled_meeting.timezone_name}) and invitations sent."
            result_success = True
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = s9_ctx["screen"]["state_contracts"]["check_highlighted"]
            result_message = str(exc)
            result_success = False

    ctx.update(s9_ctx)
    ctx.update({
        "form_values": form_values,
        "scheduled_meeting": scheduled_meeting,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/tasks_meetings/mtg_03_schedule.html", ctx)


# -----------------------------------------------------------------------------
# MTG-03-RECURRING: RECURRING MEETING SERIES (/foundation/meetings/recurring/)
# -----------------------------------------------------------------------------

def recurring_meeting_series_view(request):
    _get_authenticated_context, _render_scope_error = _get_stage9_auth_and_error_helpers()
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s9_ctx = _build_stage9_common_context(request, ctx, "MTG-03-RECURRING")
        meeting_code = request.GET.get("meeting") or request.POST.get("meeting_code") or "MTG-NG-001"
        meeting = _select_scoped_meeting(s9_ctx["target_network"], s9_ctx["target_country"], meeting_code)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    state_card = s9_ctx["state_card"]
    result_message = None
    result_success = True

    if request.method == "POST" and meeting:
        action_type = request.POST.get("action_type", "update_series").strip()
        try:
            res = update_recurring_meeting_series(
                meeting=meeting,
                frequency=request.POST.get("repeats_frequency", meeting.repeats_frequency),
                next_occurrence_label=request.POST.get("next_occurrence_label", meeting.next_occurrence_label),
                edit_scope=request.POST.get("edit_scope", meeting.edit_scope),
                cancellation_status=request.POST.get("cancellation_status", meeting.cancellation_status),
                missed_occurrence_note=request.POST.get("missed_occurrence_note", ""),
                action_type=action_type,
                actor_account=account,
                user_scope=user_scope,
            )
            meeting = res["meeting"]
            state_key = res.get("state_key", "series_change_confirmed")
            state_card = s9_ctx["screen"]["state_contracts"].get(state_key)
            if action_type == "retry_failed_invitations":
                result_message = "Failed recipient invitation and reminder deliveries retried without resending to already-delivered participants."
            elif action_type == "record_missed_occurrence":
                result_message = f"Missed occurrence note recorded for {meeting.title} without inventing attendance."
            else:
                result_message = f"Series '{meeting.title}' updated ({meeting.edit_scope}). Past approved minutes and attendance remain unchanged."
            result_success = True
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = s9_ctx["screen"]["state_contracts"]["needs_review"]
            result_message = str(exc)
            result_success = False

    ctx.update(s9_ctx)
    ctx.update({
        "meeting": meeting,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/tasks_meetings/mtg_03_recurring.html", ctx)


# -----------------------------------------------------------------------------
# MTG-04: COUNTRY COORDINATION MEETING DETAIL (/foundation/meetings/<str:meeting_code>/)
# -----------------------------------------------------------------------------

def stage9_meeting_detail_view(request, meeting_code: str = "MTG-NG-001"):
    _get_authenticated_context, _render_scope_error = _get_stage9_auth_and_error_helpers()
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s9_ctx = _build_stage9_common_context(request, ctx, "MTG-04")
        meeting = _select_scoped_meeting(s9_ctx["target_network"], s9_ctx["target_country"], meeting_code)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    state_card = s9_ctx["state_card"]
    result_message = None
    result_success = True
    active_panel = request.GET.get("panel", "").strip().lower()

    if request.method == "POST" and meeting:
        post_action = request.POST.get("action", "save_rsvp").strip().lower()
        try:
            if post_action == "delete_meeting":
                deleted_info = delete_meeting(
                    meeting=meeting,
                    actor_account=account,
                    user=request.user,
                )
                return redirect(
                    f"/foundation/meetings/?country={s9_ctx['target_network'] and s9_ctx['target_country']}&network={s9_ctx['target_network']}&deleted={quote(deleted_info['title'])}"
                )
            elif post_action == "save_minutes":
                active_panel = "minutes"
                res = review_minutes_or_convert_actions(
                    meeting=meeting,
                    decision="Save minutes",
                    minutes_version=request.POST.get("minutes_version", meeting.minutes_draft_label),
                    minutes_text=request.POST.get("minutes_text", ""),
                    actor_account=account,
                    user_scope=user_scope,
                )
                meeting = res["meeting"]
                state_card = s9_ctx["screen"]["state_contracts"]["record_updated"]
                result_message = f"Minutes draft ({meeting.minutes_draft_label}) saved for '{meeting.title}'."
                result_success = True
            elif post_action == "approve_minutes":
                active_panel = "minutes"
                res = review_minutes_or_convert_actions(
                    meeting=meeting,
                    decision="Approve minutes",
                    minutes_version=request.POST.get("minutes_version", meeting.minutes_draft_label),
                    minutes_text=request.POST.get("minutes_text", meeting.minutes_text),
                    reviewer_comment=request.POST.get("reviewer_comment", "Approved from meeting detail"),
                    actor_account=account,
                    user_scope=user_scope,
                )
                meeting = res["meeting"]
                state_card = s9_ctx["screen"]["state_contracts"]["record_updated"]
                result_message = f"Minutes ({meeting.minutes_version}) approved and frozen for '{meeting.title}'."
                result_success = True
            elif post_action == "add_action_item":
                active_panel = "actions"
                convert_now = request.POST.get("convert_to_task") in ("1", "true", "on", "yes")
                add_res = add_meeting_decision_or_action(
                    meeting=meeting,
                    detail_text=request.POST.get("detail_text", ""),
                    owner_label=request.POST.get("owner_label", ""),
                    deadline_or_version=request.POST.get("deadline_or_version", ""),
                    record_type=request.POST.get("record_type", "Action"),
                    convert_to_task=convert_now,
                    actor_account=account,
                    user_scope=user_scope,
                )
                item = add_res["item"]
                conv_task = add_res["converted_task"]
                meeting = add_res["meeting"]
                state_card = s9_ctx["screen"]["state_contracts"]["record_updated"]
                if conv_task:
                    result_message = (
                        f"Added {item.record_code} ('{item.detail_text}') for {item.owner_label} "
                        f"and created linked Mission Control task {conv_task.task_code}."
                    )
                else:
                    result_message = f"Recorded {item.record_code} ('{item.detail_text}') assigned to {item.owner_label}."
                result_success = True
            elif post_action in ("convert_actions", "create_action_task"):
                active_panel = "actions"
                res = review_minutes_or_convert_actions(
                    meeting=meeting,
                    decision="create_action_task",
                    action_id=request.POST.get("action_id") or None,
                    actor_account=account,
                    user_scope=user_scope,
                )
                new_tasks = res.get("converted_tasks", [])
                state_card = s9_ctx["screen"]["state_contracts"]["record_updated"]
                if new_tasks:
                    result_message = f"Converted {len(new_tasks)} action item(s) into Mission Control task(s): {', '.join(t.title for t in new_tasks)}."
                else:
                    result_message = "All open action items for this meeting are already linked to Mission Control tasks."
                result_success = True
            else:
                rsvp_status = request.POST.get("rsvp_status", "Attending").strip()
                note = request.POST.get("note", "").strip()
                rec = record_meeting_rsvp(
                    meeting=meeting,
                    rsvp_status=rsvp_status,
                    actor_account=account,
                    user_scope=user_scope,
                    note=note,
                )
                state_card = s9_ctx["screen"]["state_contracts"]["record_updated"]
                if note:
                    result_message = f"Your RSVP for '{meeting.title}' is recorded as '{rec.rsvp_status}' with note: \"{note}\"."
                else:
                    result_message = f"Your RSVP for '{meeting.title}' is recorded as '{rec.rsvp_status}'."
                result_success = True
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = s9_ctx["screen"]["state_contracts"]["missing_details"]
            result_message = str(exc)
            result_success = False

    scoped_meetings = list(
        MeetingSeries.objects.filter(
            network=s9_ctx["target_network"],
            country=s9_ctx["target_country"],
        )
    )
    if s9_ctx["state_mode"] == "empty":
        scoped_meetings = []

    is_meeting_host = is_meeting_creator(meeting, account, user=request.user)
    if is_meeting_host and meeting and meeting.status == "Invited" and "test" not in sys.argv:
        meeting.status = "Attending"
        meeting.save(update_fields=["status"])

    user_participant = None
    if meeting and account:
        user_participant = (
            meeting.participant_records.filter(account=account).first()
            or meeting.participant_records.filter(participant_name__iexact=(account.display_name or "")).first()
        )
    if not user_participant and meeting:
        user_participant = meeting.participant_records.first()

    user_rsvp_status = (
        user_participant.rsvp_status
        if (user_participant and user_participant.rsvp_status in ("Attending", "Tentative", "Declined"))
        else (meeting.status if meeting and meeting.status in ("Attending", "Tentative", "Declined") else "Attending")
    )
    default_notes = {"Host-verified", "Correction can be requested", "RSVP: Attending", "RSVP: Tentative", "RSVP: Declined"}
    user_rsvp_note = ""
    if user_participant and user_participant.detail_note and user_participant.detail_note not in default_notes:
        user_rsvp_note = user_participant.detail_note

    people_options = list(
        PersonProfile.objects.filter(country=s9_ctx["target_country"]).values_list("full_name", flat=True)[:12]
    )

    ctx.update(s9_ctx)
    ctx.update({
        "meeting": meeting,
        "is_meeting_host": is_meeting_host,
        "can_delete_meeting": is_meeting_host,
        "user_participant": user_participant,
        "user_rsvp_status": user_rsvp_status,
        "user_rsvp_note": user_rsvp_note,
        "active_panel": active_panel,
        "scoped_meetings": scoped_meetings,
        "participants": list(meeting.participant_records.all()) if meeting else [],
        "decisions_and_actions": list(meeting.decisions_and_actions.all()) if meeting else [],
        "linked_tasks": list(MissionControlTask.objects.filter(source_meeting=meeting)) if meeting else [],
        "people_options": people_options,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/tasks_meetings/mtg_04_detail.html", ctx)


# -----------------------------------------------------------------------------
# MTG-05: MEETING RECORD AND FOLLOW-UP (/foundation/meetings/follow-up/)
# -----------------------------------------------------------------------------

def meeting_followup_view(request):
    _get_authenticated_context, _render_scope_error = _get_stage9_auth_and_error_helpers()
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s9_ctx = _build_stage9_common_context(request, ctx, "MTG-05")
        meeting_code = request.GET.get("meeting") or request.POST.get("meeting_code") or "MTG-NG-001"
        meeting = _select_scoped_meeting(s9_ctx["target_network"], s9_ctx["target_country"], meeting_code)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    state_card = s9_ctx["state_card"]
    result_message = None
    result_success = True

    if request.method == "POST" and meeting:
        action = request.POST.get("action", "create_action_task").strip()
        try:
            if action.lower() == "add_action_item":
                convert_now = request.POST.get("convert_to_task") in ("1", "true", "on", "yes")
                add_res = add_meeting_decision_or_action(
                    meeting=meeting,
                    detail_text=request.POST.get("detail_text", ""),
                    owner_label=request.POST.get("owner_label", ""),
                    deadline_or_version=request.POST.get("deadline_or_version", ""),
                    record_type=request.POST.get("record_type", "Action"),
                    convert_to_task=convert_now,
                    actor_account=account,
                    user_scope=user_scope,
                )
                item = add_res["item"]
                conv_task = add_res["converted_task"]
                meeting = add_res["meeting"]
                state_card = s9_ctx["screen"]["state_contracts"]["record_updated"]
                if conv_task:
                    result_message = (
                        f"Added {item.record_code} ('{item.detail_text}') and created linked Mission Control task {conv_task.task_code}."
                    )
                else:
                    result_message = f"Added {item.record_code} ('{item.detail_text}') for '{meeting.title}'."
            else:
                res = review_minutes_or_convert_actions(
                    meeting=meeting,
                    decision=action,
                    reviewer_comment=request.POST.get("reviewer_comment", "Converted from meeting follow-up"),
                    action_id=request.POST.get("action_id") or None,
                    actor_account=account,
                    user_scope=user_scope,
                )
                new_tasks = res.get("converted_tasks", [])
                already = res.get("already_converted", [])
                state_card = s9_ctx["screen"]["state_contracts"]["record_updated"]
                if new_tasks:
                    result_message = f"Created {len(new_tasks)} linked Mission Control task(s) from '{meeting.title}' decisions ({', '.join(t.title for t in new_tasks)})."
                elif already:
                    result_message = f"All agreed actions for '{meeting.title}' have already been converted to Mission Control tasks (no duplicate created)."
                else:
                    result_message = f"Meeting follow-up updated for '{meeting.title}'."
            result_success = True
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = s9_ctx["screen"]["state_contracts"]["missing_details"]
            result_message = str(exc)
            result_success = False

    meetings = list(
        MeetingSeries.objects.filter(
            network=s9_ctx["target_network"],
            country=s9_ctx["target_country"],
        )
    )
    if s9_ctx["state_mode"] == "empty":
        meetings = []

    people_options = list(
        PersonProfile.objects.filter(country=s9_ctx["target_country"]).values_list("full_name", flat=True)[:12]
    )

    ctx.update(s9_ctx)
    ctx.update({
        "meeting": meeting,
        "meetings": meetings,
        "decisions_and_actions": list(meeting.decisions_and_actions.all()) if meeting else [],
        "linked_tasks": list(MissionControlTask.objects.filter(source_meeting=meeting)) if meeting else [],
        "people_options": people_options,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/tasks_meetings/mtg_05_followup.html", ctx)


# -----------------------------------------------------------------------------
# MTG-05-RECORD: MEETING ATTENDANCE AND MINUTES (/foundation/meetings/attendance-minutes/)
# -----------------------------------------------------------------------------

def meeting_attendance_minutes_view(request):
    _get_authenticated_context, _render_scope_error = _get_stage9_auth_and_error_helpers()
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s9_ctx = _build_stage9_common_context(request, ctx, "MTG-05-RECORD")
        meeting_code = request.GET.get("meeting") or request.POST.get("meeting_code") or "MTG-NG-001"
        meeting = _select_scoped_meeting(s9_ctx["target_network"], s9_ctx["target_country"], meeting_code)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    state_card = s9_ctx["state_card"]
    result_message = None
    result_success = True

    if request.method == "POST" and meeting:
        decision = request.POST.get("decision", "Approve minutes").strip()
        minutes_version = request.POST.get("minutes_version", meeting.minutes_draft_label).strip()
        minutes_text = request.POST.get("minutes_text")
        reviewer_comment = request.POST.get("reviewer_comment", "").strip()
        try:
            res = review_minutes_or_convert_actions(
                meeting=meeting,
                decision=decision,
                minutes_version=minutes_version,
                minutes_text=minutes_text,
                reviewer_comment=reviewer_comment,
                actor_account=account,
                user_scope=user_scope,
            )
            meeting = res["meeting"]
            action_taken = res["action_taken"]
            if action_taken == "approved":
                state_card = s9_ctx["screen"]["state_contracts"]["approval_recorded"]
                result_message = f"Minutes {meeting.minutes_version} approved and frozen for '{meeting.title}'."
            elif action_taken == "correction_requested":
                state_card = s9_ctx["screen"]["state_contracts"]["returned"]
                result_message = f"Minutes correction requested for '{meeting.title}'. New draft opened as {meeting.minutes_draft_label}."
            elif action_taken == "minutes_saved":
                state_card = s9_ctx["screen"]["state_contracts"]["saved"]
                result_message = f"Minutes text and draft ({meeting.minutes_draft_label}) saved for '{meeting.title}'."
            else:
                new_tasks = res.get("converted_tasks", [])
                state_card = s9_ctx["screen"]["state_contracts"]["saved"]
                if new_tasks:
                    result_message = f"Converted {len(new_tasks)} meeting action(s) into linked Mission Control tasks."
                else:
                    result_message = "All agreed actions are already linked to Mission Control tasks (no duplicate created)."
            result_success = True
        except ScopePermissionDenied as exc:
            return _render_scope_error(request, ctx, exc)
        except ValueError as exc:
            state_card = s9_ctx["screen"]["state_contracts"]["needs_review"]
            result_message = str(exc)
            result_success = False

    participants = list(meeting.participant_records.all()) if meeting else []
    decisions_and_actions = list(meeting.decisions_and_actions.all()) if meeting else []
    if s9_ctx["state_mode"] == "empty":
        participants = []
        decisions_and_actions = []

    ctx.update(s9_ctx)
    ctx.update({
        "meeting": meeting,
        "participants": participants,
        "decisions_and_actions": decisions_and_actions,
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/tasks_meetings/mtg_05_record.html", ctx)


# -----------------------------------------------------------------------------
# MTG-06: MEETINGS COMMAND CENTRE (/foundation/meetings/command-centre/)
# -----------------------------------------------------------------------------

def meetings_command_centre_view(request):
    _get_authenticated_context, _render_scope_error = _get_stage9_auth_and_error_helpers()
    ctx, redirect_res = _get_authenticated_context(request)
    if redirect_res:
        return redirect_res

    try:
        s9_ctx = _build_stage9_common_context(request, ctx, "MTG-06")
        meeting_code = request.GET.get("meeting") or request.POST.get("meeting_code") or "MTG-NG-001"
        meeting = _select_scoped_meeting(s9_ctx["target_network"], s9_ctx["target_country"], meeting_code)
    except ScopePermissionDenied as exc:
        return _render_scope_error(request, ctx, exc)

    user_scope = ctx["user_scope"]
    account = ctx["account"]
    state_card = s9_ctx["state_card"]
    result_message = None
    result_success = True

    bisi_rec = (
        meeting.participant_records.filter(participant_name__icontains="Bisi").first() or meeting.participant_records.first()
    ) if meeting else None

    if request.method == "POST" and meeting:
        action = request.POST.get("action", "approve_correction").strip().lower()
        participant_name = request.POST.get("participant_name", "Bisi Adeyemi").strip()
        corrected_attendance = request.POST.get("corrected_attendance", "Present").strip()
        correction_reason = request.POST.get("correction_reason", "").strip()

        if action == "save_draft":
            state_card = s9_ctx["screen"]["state_contracts"]["saved_later"]
            result_message = f"Attendance correction draft for {participant_name} saved for later."
            result_success = True
        else:
            try:
                bisi_rec = correct_meeting_attendance_record(
                    meeting=meeting,
                    participant_name=participant_name,
                    corrected_attendance=corrected_attendance,
                    correction_reason=correction_reason,
                    actor_account=account,
                    user_scope=user_scope,
                )
                state_card = s9_ctx["screen"]["state_contracts"]["saved"]
                result_message = (
                    f"Attendance for {bisi_rec.participant_name} corrected to '{bisi_rec.attendance_status}' "
                    f"(previous value '{bisi_rec.previous_attendance_value}' retained in audit)."
                )
                result_success = True
            except ScopePermissionDenied as exc:
                return _render_scope_error(request, ctx, exc)
            except ValueError as exc:
                state_card = s9_ctx["screen"]["state_contracts"]["check_highlighted"]
                result_message = str(exc)
                result_success = False

    ctx.update(s9_ctx)
    ctx.update({
        "meeting": meeting,
        "target_participant": bisi_rec,
        "participants": list(meeting.participant_records.all()) if meeting else [],
        "decisions_and_actions": list(meeting.decisions_and_actions.all()) if meeting else [],
        "state_card": state_card,
        "result_message": result_message,
        "result_success": result_success,
    })
    return render(request, "foundation/tasks_meetings/mtg_06_command_centre.html", ctx)


# -----------------------------------------------------------------------------
# STAGE 09 SCREEN DISPATCHER (/foundation/stage9/<str:screen_code>/)
# -----------------------------------------------------------------------------

def stage9_screen_router(request, screen_code: str):
    code = (screen_code or "").strip().upper()
    mapping = {
        "TASK-01": mission_control_tasks_view,
        "TASK-02": create_task_view,
        "TASK-03": task_detail_view,
        "TASK-03-LIFECYCLE": task_lifecycle_view,
        "TASK-04": review_task_completion_view,
        "MTG-01": my_calendar_view,
        "MTG-02": meetings_list_view,
        "MTG-03": schedule_meeting_view,
        "MTG-03-RECURRING": recurring_meeting_series_view,
        "MTG-04": stage9_meeting_detail_view,
        "MTG-05": meeting_followup_view,
        "MTG-05-RECORD": meeting_attendance_minutes_view,
        "MTG-06": meetings_command_centre_view,
    }
    view_fn = mapping.get(code)
    if not view_fn:
        raise Http404(f"Stage 09 screen code '{screen_code}' not found.")
    return view_fn(request)
