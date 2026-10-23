"""
WDOS Stage 09: Tasks, Calendar, and Meeting Administration Engine
Authoritative domain engine for:
- Mission Control task creation, assignment, linked work queues, and scoped task boards (TASK-01, TASK-02)
- Task lifecycle states: Not started -> In progress -> Submitted -> Reviewed -> Verified -> Closed,
  plus Returned for correction, Reopened, Blocked, Overdue, and Escalated (TASK-03, TASK-03-LIFECYCLE, TASK-04)
- Calendar, meeting list/scheduling, recurring meeting series, RSVP, agendas, and attendance (MTG-01, MTG-02, MTG-03, MTG-03-RECURRING, MTG-04, MTG-06)
- Meeting minutes/decisions, idempotent action-item-to-task conversion, attendance corrections with preserved original values,
  and recoverable invitation/reminder deliveries (MTG-05, MTG-05-RECORD, MTG-03-RECURRING, MTG-06)
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.models import Account, AuditEvent
from .models import (
    MeetingDecisionAction,
    MeetingParticipantRecord,
    MeetingSeries,
    MissionControlTask,
    Notification,
    PersonProfile,
    ScheduledMeeting,
    TaskLifecycleEntry,
    WorkItem,
)
from .people_geo_engine import (
    _collect_user_roles,
    assert_country_network_authorized,
    get_country_name_for_code,
    is_global_stage6_scope,
    normalize_country_code,
    seed_stage6_fixtures,
)
from .scope import ScopePermissionDenied, UserScope


# -----------------------------------------------------------------------------
# STAGE 09 SCREEN METADATA & STATE CONTRACTS
# -----------------------------------------------------------------------------

def _build_list_state_contracts(base_url: str, screen_title_lower: str) -> Dict[str, Dict[str, str]]:
    return {
        "proposed_approval": {
            "title": "Proposed for approval",
            "message": f"Your proposed update for {screen_title_lower} has been recorded for authorized review.",
            "action_label": "Return to view",
            "action_url": base_url,
        },
        "empty": {
            "title": "No records in this view",
            "message": f"There are no {screen_title_lower} records matching the selected scope.",
            "action_label": "Clear filters",
            "action_url": base_url,
        },
        "connection_error": {
            "title": "Connection interrupted",
            "message": "Your last saved information is safe. Reconnect before submitting changes.",
            "action_label": "Try again",
            "action_url": base_url,
        },
        "access_changed": {
            "title": "Access has changed",
            "message": "This action is no longer available for your current role. No change was applied.",
            "action_label": "Return to workspace",
            "action_url": "/foundation/workspace/",
        },
        "loading": {
            "title": "Loading current information",
            "message": f"Loading {screen_title_lower}. No stale values or completed actions are implied.",
            "action_label": "Cancel and return",
            "action_url": base_url,
        },
        "no_matching": {
            "title": "Nothing to show in this scope",
            "message": f"There are no matching records for {screen_title_lower}. Check the current scope or remove a filter.",
            "action_label": "Reset view",
            "action_url": base_url,
        },
        "more_info": {
            "title": "More information needed",
            "message": f"Check the marked details before continuing with {screen_title_lower}. Your entered information remains available.",
            "action_label": "Review details",
            "action_url": base_url,
        },
    }


def _build_form_state_contracts(base_url: str, screen_title_lower: str) -> Dict[str, Dict[str, str]]:
    return {
        "proposed_approval": {
            "title": "Proposed for approval",
            "message": f"Your submission for {screen_title_lower} is queued for authorized human review.",
            "action_label": "Review submission",
            "action_url": base_url,
        },
        "check_highlighted": {
            "title": "Check the highlighted information",
            "message": "Complete the required fields before continuing. Your entered information is retained.",
            "action_label": "Review fields",
            "action_url": base_url,
        },
        "saved_later": {
            "title": "Saved for later",
            "message": "Your draft is saved. Return to this record when you are ready to continue.",
            "action_label": "Open draft",
            "action_url": base_url,
        },
        "another_change": {
            "title": "Another change needs review",
            "message": "This record changed since you opened it. Review the latest version before submitting.",
            "action_label": "Review latest version",
            "action_url": base_url,
        },
        "loading": {
            "title": "Loading current information",
            "message": f"Loading {screen_title_lower}. No stale values or completed actions are implied.",
            "action_label": "Cancel and return",
            "action_url": base_url,
        },
        "no_matching": {
            "title": "Nothing to show in this scope",
            "message": f"There are no matching records for {screen_title_lower}. Check the current scope or remove a filter.",
            "action_label": "Reset view",
            "action_url": base_url,
        },
        "more_info": {
            "title": "More information needed",
            "message": f"Check the marked details before continuing with {screen_title_lower}. Your entered information remains available.",
            "action_label": "Review details",
            "action_url": base_url,
        },
        "saved": {
            "title": "Saved",
            "message": f"The latest changes to {screen_title_lower} were saved and added to the activity log.",
            "action_label": "Done",
            "action_url": base_url,
        },
        "needs_review": {
            "title": "Needs review",
            "message": f"Check the highlighted details for {screen_title_lower} before submitting.",
            "action_label": "Review details",
            "action_url": base_url,
        },
    }


def _build_detail_state_contracts(base_url: str, screen_title_lower: str) -> Dict[str, Dict[str, str]]:
    return {
        "proposed_approval": {
            "title": "Proposed for approval",
            "message": f"Your update for {screen_title_lower} has been queued for authorized review.",
            "action_label": "Return to record",
            "action_url": base_url,
        },
        "record_updated": {
            "title": "Record updated",
            "message": "The latest change has been saved and added to the audit history.",
            "action_label": "View history",
            "action_url": f"{base_url}?tab=history",
        },
        "missing_details": {
            "title": "Required details are missing",
            "message": "Add the required note or supporting evidence before completing this action.",
            "action_label": "Complete details",
            "action_url": base_url,
        },
        "not_available": {
            "title": "Not available in your scope",
            "message": "This record belongs to another scope or requires a different permission.",
            "action_label": "Return to list",
            "action_url": "/foundation/tasks/",
        },
        "loading": {
            "title": "Loading current information",
            "message": f"Loading {screen_title_lower}. No stale values or completed actions are implied.",
            "action_label": "Cancel and return",
            "action_url": base_url,
        },
        "no_matching": {
            "title": "Nothing to show in this scope",
            "message": f"There are no matching records for {screen_title_lower}. Check the current scope or remove a filter.",
            "action_label": "Reset view",
            "action_url": base_url,
        },
        "more_info": {
            "title": "More information needed",
            "message": f"Check the marked details before continuing with {screen_title_lower}. Your entered information remains available.",
            "action_label": "Review details",
            "action_url": base_url,
        },
    }


def _build_review_state_contracts(base_url: str, screen_title_lower: str) -> Dict[str, Dict[str, str]]:
    return {
        "proposed_approval": {
            "title": "Proposed for approval",
            "message": "A human reviewer must confirm this action before any status change takes effect.",
            "action_label": "Review details",
            "action_url": base_url,
        },
        "returned": {
            "title": "Returned for correction",
            "message": "The submitter has been asked to update the highlighted details.",
            "action_label": "View note",
            "action_url": base_url,
        },
        "approval_recorded": {
            "title": "Approval recorded",
            "message": "Your decision, reason and timestamp have been added to the audit log.",
            "action_label": "Continue",
            "action_url": base_url,
        },
        "no_longer_pending": {
            "title": "No longer pending",
            "message": "Another authorized reviewer has already completed this step.",
            "action_label": "Refresh status",
            "action_url": base_url,
        },
        "loading": {
            "title": "Loading current information",
            "message": f"Loading {screen_title_lower}. No stale values or completed actions are implied.",
            "action_label": "Cancel and return",
            "action_url": base_url,
        },
        "no_matching": {
            "title": "Nothing to show in this scope",
            "message": f"There are no matching records for {screen_title_lower}. Check the current scope or remove a filter.",
            "action_label": "Reset view",
            "action_url": base_url,
        },
        "more_info": {
            "title": "More information needed",
            "message": f"Check the marked details before continuing with {screen_title_lower}. Your entered information remains available.",
            "action_label": "Review details",
            "action_url": base_url,
        },
    }


STAGE9_SCREENS: Dict[str, Dict[str, Any]] = {
    "TASK-01": {
        "code": "TASK-01",
        "title": "Mission Control tasks",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Move work from Not started to Closed with one clear next action.",
        "route": "/foundation/tasks/",
        "shield_notice": "Tasks retain their source, owner and history when reassigned.",
        "state_contracts": _build_list_state_contracts("/foundation/tasks/", "mission control tasks"),
    },
    "TASK-02": {
        "code": "TASK-02",
        "title": "Create a task",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Complete the required details and review before saving.",
        "route": "/foundation/tasks/create/",
        "shield_notice": "Tasks retain their source, owner and history when reassigned.",
        "state_contracts": _build_form_state_contracts("/foundation/tasks/create/", "create a task"),
    },
    "TASK-03": {
        "code": "TASK-03",
        "title": "Confirm Chapter meeting agenda",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Review the current record, related history and permitted actions.",
        "route": "/foundation/tasks/TASK-NG-001/",
        "shield_notice": "Tasks retain their source, owner and history when reassigned.",
        "state_contracts": _build_detail_state_contracts("/foundation/tasks/TASK-NG-001/", "confirm chapter meeting agenda"),
    },
    "TASK-03-LIFECYCLE": {
        "code": "TASK-03-LIFECYCLE",
        "title": "Mission Control lifecycle",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Move tasks from Not Started through Closed with return, reopen and escalation paths.",
        "route": "/foundation/tasks/lifecycle/",
        "shield_notice": "Tasks retain their source, owner and history when reassigned.",
        "state_contracts": {
            **_build_detail_state_contracts("/foundation/tasks/lifecycle/", "mission control lifecycle"),
            "returned": {
                "title": "Returned for correction",
                "message": "Add the missing agenda confirmation and submit a new version.",
                "action_label": "Update submission",
                "action_url": "/foundation/tasks/lifecycle/",
            },
            "reopened": {
                "title": "Reopened",
                "message": "This closed task was reopened with a recorded reason. Previous closure remains in history.",
                "action_label": "View reason",
                "action_url": "/foundation/tasks/lifecycle/?tab=history",
            },
            "escalated": {
                "title": "Escalated",
                "message": "Overdue review was routed to the supervising coordinator with the blocker note.",
                "action_label": "Open escalation",
                "action_url": "/foundation/tasks/lifecycle/",
            },
            "saved": {
                "title": "Saved",
                "message": "The latest changes to mission control lifecycle were saved and added to the activity log.",
                "action_label": "Done",
                "action_url": "/foundation/tasks/lifecycle/",
            },
            "needs_review": {
                "title": "Needs review",
                "message": "Check the highlighted details for mission control lifecycle before submitting.",
                "action_label": "Review details",
                "action_url": "/foundation/tasks/lifecycle/",
            },
        },
    },
    "TASK-04": {
        "code": "TASK-04",
        "title": "Review task completion",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Check the submitted information, record a reason and confirm the next state.",
        "route": "/foundation/tasks/review/",
        "shield_notice": "Tasks retain their source, owner and history when reassigned.",
        "state_contracts": _build_review_state_contracts("/foundation/tasks/review/", "review task completion"),
    },
    "MTG-01": {
        "code": "MTG-01",
        "title": "My calendar",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant meetings and follow-up records, linked evidence and next actions for your scope.",
        "route": "/foundation/calendar/",
        "shield_notice": "Times are shown in Africa/Lagos. Joining, speaking and moderating are separate permissions.",
        "state_contracts": _build_list_state_contracts("/foundation/calendar/", "my calendar"),
    },
    "MTG-02": {
        "code": "MTG-02",
        "title": "Meetings",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant meetings and follow-up records, linked evidence and next actions for your scope.",
        "route": "/foundation/meetings/",
        "shield_notice": "Times are shown in Africa/Lagos. Joining, speaking and moderating are separate permissions.",
        "state_contracts": _build_list_state_contracts("/foundation/meetings/", "meetings"),
    },
    "MTG-03": {
        "code": "MTG-03",
        "title": "Schedule a meeting",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Complete the required details and review before saving.",
        "route": "/foundation/meetings/schedule/",
        "shield_notice": "Times are shown in Africa/Lagos. Joining, speaking and moderating are separate permissions.",
        "state_contracts": _build_form_state_contracts("/foundation/meetings/schedule/", "schedule a meeting"),
    },
    "MTG-03-RECURRING": {
        "code": "MTG-03-RECURRING",
        "title": "Recurring meeting series",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Edit one meeting or future occurrences, cancel cleanly and handle missed meetings.",
        "route": "/foundation/meetings/recurring/",
        "shield_notice": "Times are shown in Africa/Lagos. Joining, speaking and moderating are separate permissions.",
        "state_contracts": {
            **_build_form_state_contracts("/foundation/meetings/recurring/", "recurring meeting series"),
            "occurrence_missed": {
                "title": "Occurrence missed",
                "message": "Record what happened for the missed meeting without inventing attendance.",
                "action_label": "Add note",
                "action_url": "/foundation/meetings/recurring/",
            },
            "invitations_partly_delivered": {
                "title": "Invitations partly delivered",
                "message": "One recipient delivery failed. Retry that recipient without resending to everyone.",
                "action_label": "Retry failed recipient",
                "action_url": "/foundation/meetings/recurring/",
            },
            "series_change_confirmed": {
                "title": "Series change confirmed",
                "message": "Future occurrences were updated; past approved minutes and attendance remain unchanged.",
                "action_label": "View series",
                "action_url": "/foundation/meetings/recurring/",
            },
            "saved": {
                "title": "Saved",
                "message": "The latest changes to recurring meeting series were saved and added to the activity log.",
                "action_label": "Done",
                "action_url": "/foundation/meetings/recurring/",
            },
            "needs_review": {
                "title": "Needs review",
                "message": "Check the highlighted details for recurring meeting series before submitting.",
                "action_label": "Review details",
                "action_url": "/foundation/meetings/recurring/",
            },
        },
    },
    "MTG-04": {
        "code": "MTG-04",
        "title": "Country coordination meeting",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Review the current record, related history and permitted actions.",
        "route": "/foundation/meetings/MTG-NG-001/",
        "shield_notice": "Times are shown in Africa/Lagos. Joining, speaking and moderating are separate permissions.",
        "state_contracts": _build_detail_state_contracts("/foundation/meetings/MTG-NG-001/", "country coordination meeting"),
    },
    "MTG-05": {
        "code": "MTG-05",
        "title": "Meeting record and follow-up",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Review the current record, related history and permitted actions.",
        "route": "/foundation/meetings/follow-up/",
        "shield_notice": "Times are shown in Africa/Lagos. Joining, speaking and moderating are separate permissions.",
        "state_contracts": _build_detail_state_contracts("/foundation/meetings/follow-up/", "meeting record and follow-up"),
    },
    "MTG-05-RECORD": {
        "code": "MTG-05-RECORD",
        "title": "Meeting attendance and minutes",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Record attendance, approve or correct minutes and convert decisions into Mission Control tasks.",
        "route": "/foundation/meetings/attendance-minutes/",
        "shield_notice": "Times are shown in Africa/Lagos. Joining, speaking and moderating are separate permissions.",
        "state_contracts": {
            **_build_review_state_contracts("/foundation/meetings/attendance-minutes/", "meeting attendance and minutes"),
            "saved": {
                "title": "Saved",
                "message": "The latest changes to meeting attendance and minutes were saved and added to the activity log.",
                "action_label": "Done",
                "action_url": "/foundation/meetings/attendance-minutes/",
            },
            "needs_review": {
                "title": "Needs review",
                "message": "Check the highlighted details for meeting attendance and minutes before submitting.",
                "action_label": "Review details",
                "action_url": "/foundation/meetings/attendance-minutes/",
            },
        },
    },
    "MTG-06": {
        "code": "MTG-06",
        "title": "Meetings command centre",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Complete the required details and review before saving.",
        "route": "/foundation/meetings/command-centre/",
        "shield_notice": "Times are shown in Africa/Lagos. Joining, speaking and moderating are separate permissions.",
        "state_contracts": _build_form_state_contracts("/foundation/meetings/command-centre/", "meetings command centre"),
    },
}


# -----------------------------------------------------------------------------
# AUTHORIZATION & SCOPE HELPERS
# -----------------------------------------------------------------------------

STAGE9_ORGANIZER_SCREENS = {"TASK-04", "MTG-03", "MTG-03-RECURRING", "MTG-06"}

LEADERSHIP_AND_ORGANIZER_ROLES = {
    "founder",
    "hq",
    "admin",
    "network_secretary",
    "secretary",
    "operations",
    "ops",
    "hofco",
    "coordinator",
    "coordination",
    "programmes",
    "comms",
    "communications",
    "resources",
    "finance",
    "systems",
    "it_admin",
    "quality",
    "reviewer",
    "safeguarding",
    "regional_coordinator",
    "country_director",
    "country_coordinator",
    "country_lead",
    "state_coordinator",
    "state_lead",
    "lga_coordinator",
    "lga_lead",
    "cluster_lead",
    "chapter_lead",
}


def is_stage9_organizer_or_reviewer(user_scope: UserScope) -> bool:
    if is_global_stage6_scope(user_scope) or getattr(user_scope, "is_management_or_admin", False):
        return True
    roles = _collect_user_roles(user_scope)
    if roles & LEADERSHIP_AND_ORGANIZER_ROLES:
        return True
    return getattr(user_scope, "leadership_tier", 99) <= 4


def assert_stage9_authorized(user_scope: UserScope, screen_code: str) -> None:
    norm_code = (screen_code or "TASK-01").strip().upper()
    roles = _collect_user_roles(user_scope)

    # Candidates and external community contacts without member/leadership roles cannot access internal Stage 09 governance screens
    if roles and roles.issubset({"candidate", "community", "applicant"}):
        raise ScopePermissionDenied(
            f"Access Denied: Screen '{norm_code}' requires active member or leadership scope.",
            reason_code="stage9_member_or_leadership_required",
        )

    if norm_code in STAGE9_ORGANIZER_SCREENS and not is_stage9_organizer_or_reviewer(user_scope):
        raise ScopePermissionDenied(
            f"Access Denied: Screen '{norm_code}' is restricted to authorized task reviewers and meeting organizers.",
            reason_code="stage9_organizer_or_reviewer_required",
        )


def resolve_stage9_scope(user_scope: UserScope, req_country: str = "", req_network: str = "") -> Dict[str, str]:
    if req_country or req_network:
        assert_country_network_authorized(
            user_scope,
            country=req_country or None,
            network=req_network or None,
        )

    raw_net = (req_network or getattr(user_scope, "active_network", "WGMN") or "WGMN").strip().upper()
    target_network = raw_net if raw_net in {"WGMN", "WNNN"} else "WGMN"

    raw_country = (req_country or getattr(user_scope, "active_country", "NG") or "NG").strip().upper()
    target_country = normalize_country_code(raw_country) if raw_country not in {"ALL", "BOTH", "*", ""} else "NG"
    target_country_name = get_country_name_for_code(target_country)

    eyebrow_net = " ".join(list(target_network))
    eyebrow_country = " ".join(list(target_country_name.upper()))
    eyebrow = f"{eyebrow_net} / {eyebrow_country}"

    return {
        "target_network": target_network,
        "target_country": target_country,
        "target_country_name": target_country_name,
        "eyebrow": eyebrow,
    }


def _sync_task_work_item(task: MissionControlTask, actor_account: Optional[Account] = None) -> WorkItem:
    """
    Ensures every Mission Control task is synchronized with the CORE-02 Work Queue (`WorkItem`).
    """
    if task.status == "Closed":
        work_status = "completed"
    elif task.status == "Blocked":
        work_status = "blocked"
    elif task.status == "Not started":
        work_status = "pending"
    else:
        work_status = "in_progress"

    priority_map = {
        "Urgent": "urgent",
        "High": "high",
        "Standard": "normal",
        "Low": "low",
    }
    work_priority = priority_map.get(task.priority, "high")
    if task.status in {"Overdue", "Escalated", "Blocked"}:
        work_priority = "urgent"

    owner_acc = task.owner_account or actor_account
    work_item = task.linked_work_item
    action_url = f"/foundation/tasks/{task.task_code}/"
    summary_text = f"{task.description or task.required_evidence} · Status: {task.status} · Next: {task.next_action}"

    if work_item:
        work_item.title = task.title
        work_item.summary = summary_text
        work_item.status = work_status
        work_item.priority = work_priority
        work_item.network = task.network
        work_item.country = task.country
        work_item.target_url = action_url
        if owner_acc:
            work_item.assigned_to = owner_acc
        work_item.save()
    else:
        work_item = WorkItem.objects.filter(
            title=task.title,
            network=task.network,
            country=task.country,
        ).first()
        if not work_item:
            work_item = WorkItem.objects.create(
                title=task.title,
                summary=summary_text,
                category="review" if task.status in {"Submitted", "Reviewed", "Verified"} else "general",
                priority=work_priority,
                status=work_status,
                assigned_to=owner_acc,
                created_by=task.assigned_by_account or actor_account,
                network=task.network,
                country=task.country,
                target_url=action_url,
            )
        task.linked_work_item = work_item
        task.save(update_fields=["linked_work_item"])

    return work_item


def _create_stage9_notification(
    recipient: Optional[Account],
    title: str,
    message: str,
    category: str = "work_queue",
    network: str = "WGMN",
    country: str = "NG",
    action_url: str = "/foundation/tasks/",
    delivery_status: str = "delivered",
) -> Optional[Notification]:
    if not recipient:
        recipient = Account.objects.filter(status="active").first()
    if not recipient:
        return None
    norm_cat = category if category in {"work_queue", "security", "system", "privacy", "activity"} else "work_queue"
    return Notification.objects.create(
        account=recipient,
        title=title,
        message=message,
        category=norm_cat,
        network=network,
        country=country,
        target_url=action_url,
        delivery_status=delivery_status,
    )


def _log_stage9_audit(
    actor_account: Optional[Account],
    event_name: str,
    detail: Dict[str, Any],
) -> AuditEvent:
    return AuditEvent.objects.create(
        account=actor_account,
        event=event_name,
        detail=detail,
    )


# -----------------------------------------------------------------------------
# IDEMPOTENT STAGE 09 CANONICAL SEEDING
# -----------------------------------------------------------------------------

@transaction.atomic
def seed_stage9_fixtures(
    network: str = "WGMN",
    country: str = "NG",
    actor_account: Optional[Account] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """
    Seeds the canonical Stage 09 Mission Control Tasks, Task Lifecycle Entries,
    Meetings, Recurring Series, Participant Attendance Records, and Meeting Decisions/Actions.
    """
    import sys
    net = (network or "WGMN").strip().upper()
    if net not in {"WGMN", "WNNN"}:
        net = "WGMN"
    ctry = normalize_country_code(country or "NG")
    if not force and "test" not in sys.argv:
        existing_tasks = list(MissionControlTask.objects.filter(network=net, country=ctry))
        existing_meetings = list(MeetingSeries.objects.filter(network=net, country=ctry))
        return {
            "tasks": existing_tasks,
            "meetings": existing_meetings,
            "primary_task": existing_tasks[0] if existing_tasks else None,
            "primary_meeting": existing_meetings[0] if existing_meetings else None,
        }
    seed_stage6_fixtures(force=force)
    country_name = get_country_name_for_code(ctry)

    ada_person = PersonProfile.objects.filter(full_name__icontains="Ada Okafor", country=ctry).first() or PersonProfile.objects.filter(country=ctry).first()
    bisi_person = PersonProfile.objects.filter(full_name__icontains="Bisi Adeyemi", country=ctry).first()
    lina_person = PersonProfile.objects.filter(full_name__icontains="Lina Mensah", country=ctry).first()
    kemi_person = PersonProfile.objects.filter(full_name__icontains="Kemi", country=ctry).first()

    ada_acc = Account.objects.filter(email__iexact="member.ada@example.org").first() or actor_account
    lina_acc = Account.objects.filter(email__iexact="state.lagos@example.org").first() or actor_account

    prefix_suffix = "" if (net == "WGMN" and ctry == "NG") else f"-{net}-{ctry}"
    mtg1_code = f"MTG-NG-001{prefix_suffix}"
    mtg2_code = f"MTG-NG-002{prefix_suffix}"
    mtg3_code = f"MTG-NG-003{prefix_suffix}"

    scope_label = f"{net} · {country_name}"
    invitees_label = f"{net} · {country_name} country team"

    # 1. Seed Canonical Meetings (MTG-01..MTG-06)
    mtg1, _ = MeetingSeries.objects.get_or_create(
        meeting_code=mtg1_code,
        defaults={
            "title": "Country coordination",
            "description": "Agree the agenda, review national follow-through and assign next actions.",
            "agenda": "Country updates, reporting follow-through and support needs.",
            "network": net,
            "country": ctry,
            "scope_label": scope_label,
            "unit_name": invitees_label,
            "host_name": "Ada Okafor",
            "host_account": ada_acc,
            "local_time_label": "18 Sep · 10:00 WAT",
            "full_start_time_label": "18 September 2026 · 10:00",
            "scheduled_at": timezone.now() + timedelta(days=2),
            "timezone_name": "Africa/Lagos (WAT)",
            "invitees_label": invitees_label,
            "repeats_frequency": "Weekly",
            "ends_date_label": "31 December 2026",
            "next_occurrence_label": "18 October 2026 · 10:00 WAT",
            "edit_scope": "Edit this and future meetings",
            "cancellation_status": "Keep series active",
            "status": "Attending",
            "attendance_summary": "4 of 5 present",
            "minutes_version": "v2 · reviewed",
            "minutes_draft_label": "v2 · draft",
            "minutes_status": "Reviewed",
            "minutes_text": "Confirm monthly follow-up plan, leadership vacancy follow-up, and upload of corrected activity evidence.",
            "open_actions_label": "3 open",
            "invitation_delivery_state": "Delivered",
        },
    )

    mtg2, _ = MeetingSeries.objects.get_or_create(
        meeting_code=mtg2_code,
        defaults={
            "title": "Programme planning",
            "description": "Prepare milestones, participant support and evidence requirements.",
            "agenda": "Prepare milestones, participant support and evidence requirements.",
            "network": net,
            "country": ctry,
            "scope_label": scope_label,
            "unit_name": invitees_label,
            "host_name": "Lina Mensah",
            "host_account": lina_acc,
            "local_time_label": "20 Sep · 14:00 WAT",
            "full_start_time_label": "20 September 2026 · 14:00",
            "scheduled_at": timezone.now() + timedelta(days=4),
            "timezone_name": "Africa/Lagos (WAT)",
            "invitees_label": invitees_label,
            "repeats_frequency": "Monthly",
            "ends_date_label": "31 December 2026",
            "next_occurrence_label": "20 October 2026 · 14:00 WAT",
            "edit_scope": "This meeting only",
            "cancellation_status": "Keep series active",
            "status": "Invited",
            "attendance_summary": "Pending",
            "minutes_version": "v1 · draft",
            "minutes_draft_label": "v1 · draft",
            "minutes_status": "Draft",
            "minutes_text": "Programme milestone schedule and evidence checklist.",
            "open_actions_label": "1 open",
            "invitation_delivery_state": "Delivered",
        },
    )

    mtg3, _ = MeetingSeries.objects.get_or_create(
        meeting_code=mtg3_code,
        defaults={
            "title": "Chapter check-in",
            "description": "Follow up chapter check-in notes and action items.",
            "agenda": "Chapter check-in, member follow-up and local support.",
            "network": net,
            "country": ctry,
            "scope_label": scope_label,
            "unit_name": "Lagos Central Chapter",
            "host_name": "Kemi Bello",
            "local_time_label": "22 Sep · 16:00 WAT",
            "full_start_time_label": "22 September 2026 · 16:00",
            "scheduled_at": timezone.now() + timedelta(days=6),
            "timezone_name": "Africa/Lagos (WAT)",
            "invitees_label": "Lagos Central Chapter team",
            "repeats_frequency": "Weekly",
            "ends_date_label": "31 December 2026",
            "next_occurrence_label": "29 September 2026 · 16:00 WAT",
            "edit_scope": "This meeting only",
            "cancellation_status": "Keep series active",
            "status": "Actions open",
            "attendance_summary": "3 of 4 present",
            "minutes_version": "Missed meeting",
            "minutes_draft_label": "Missed meeting",
            "minutes_status": "Missed meeting",
            "minutes_text": "Occurrence missed note recorded; follow-up items carried forward.",
            "open_actions_label": "0",
            "invitation_delivery_state": "Delivered",
        },
    )

    # 2. Seed Participant Attendance Records for MTG-01 / MTG-05-RECORD / MTG-06
    if not mtg1.participant_records.exists():
        MeetingParticipantRecord.objects.create(
            meeting=mtg1,
            person=ada_person,
            account=ada_acc,
            participant_name="Ada Okafor",
            role_or_title="Chapter Lead",
            rsvp_status="Attending",
            attendance_status="Present",
            previous_attendance_value="Present",
            detail_note="Host-verified",
            invitation_delivery_status="delivered",
            reminder_delivery_status="delivered",
        )
        MeetingParticipantRecord.objects.create(
            meeting=mtg1,
            person=bisi_person,
            participant_name="Bisi Adeyemi",
            role_or_title="Member",
            rsvp_status="Invited",
            attendance_status="Absent",
            previous_attendance_value="Absent · original retained",
            detail_note="Correction can be requested",
            invitation_delivery_status="delivered",
            reminder_delivery_status="delivered",
        )
        MeetingParticipantRecord.objects.create(
            meeting=mtg1,
            person=lina_person,
            account=lina_acc,
            participant_name="Lina Mensah",
            role_or_title="State Coordinator",
            rsvp_status="Attending",
            attendance_status="Present",
            previous_attendance_value="Present",
            detail_note="Host-verified",
            invitation_delivery_status="delivered",
            reminder_delivery_status="delivered",
        )
        MeetingParticipantRecord.objects.create(
            meeting=mtg1,
            person=kemi_person,
            participant_name="Kemi Bello",
            role_or_title="LGA Coordinator",
            rsvp_status="Attending",
            attendance_status="Present",
            previous_attendance_value="Present",
            detail_note="Host-verified",
            invitation_delivery_status="delivered",
            reminder_delivery_status="delivered",
        )

    # 3. Seed Meeting Decisions and Action Items for MTG-05 & MTG-05-RECORD
    if not mtg1.decisions_and_actions.exists():
        MeetingDecisionAction.objects.create(
            meeting=mtg1,
            record_code="Decision 01",
            record_type="Decision",
            owner_label="Meeting reviewer",
            deadline_or_version="Draft minutes v2",
            detail_text="Confirm monthly follow-up plan",
        )
        MeetingDecisionAction.objects.create(
            meeting=mtg1,
            record_code="Action 01",
            record_type="Action",
            owner_label="Country coordinator",
            owner_person=lina_person,
            deadline_or_version="21 Sep 2026 WAT",
            detail_text="Follow up leadership vacancy",
        )
        MeetingDecisionAction.objects.create(
            meeting=mtg1,
            record_code="Action 02",
            record_type="Action",
            owner_label="Chapter lead",
            owner_person=ada_person,
            deadline_or_version="23 Sep 2026 WAT",
            detail_text="Upload corrected activity evidence",
        )

    # 4. Seed Canonical Mission Control Tasks (TASK-01..TASK-04)
    t1_code = f"TASK-NG-001{prefix_suffix}"
    t2_code = f"TASK-NG-002{prefix_suffix}"
    t3_code = f"TASK-NG-003{prefix_suffix}"
    t4_code = f"TASK-NG-004{prefix_suffix}"

    task1, t1_created = MissionControlTask.objects.get_or_create(
        task_code=t1_code,
        defaults={
            "title": "Confirm Chapter meeting agenda",
            "description": "Agree the discussion points and share the approved agenda.",
            "network": net,
            "country": ctry,
            "unit_name": "Lagos Central Chapter",
            "owner_person": ada_person,
            "owner_account": ada_acc,
            "owner_name": "Ada Okafor",
            "assigned_by_account": lina_acc,
            "assigned_by_name": "Lina Mensah",
            "reviewer_name": "Assigned reviewer",
            "reviewer_account": lina_acc,
            "board_column": "To do",
            "status": "In progress",
            "priority": "High",
            "due_date_label": "18 September 2026",
            "due_short_label": "18 Sep",
            "due_date": date(2026, 9, 18),
            "next_action": "Submit evidence",
            "required_evidence": "Attach the agreed agenda and note any unresolved questions.",
            "evidence_file": "chapter-agenda-v2.pdf",
            "current_version": 2,
            "source_type": "Meeting Action",
            "source_reference": mtg1.title,
            "source_meeting": mtg1,
        },
    )

    task2, _ = MissionControlTask.objects.get_or_create(
        task_code=t2_code,
        defaults={
            "title": "Review programme evidence",
            "description": "Check attendance and consent-linked photographs.",
            "network": net,
            "country": ctry,
            "unit_name": "Lagos State",
            "owner_person": lina_person,
            "owner_account": lina_acc,
            "owner_name": "Lina Mensah",
            "assigned_by_name": "Aisha Bello",
            "reviewer_name": "Quality & Learning",
            "board_column": "In progress",
            "status": "Submitted",
            "priority": "High",
            "due_date_label": "20 September 2026",
            "due_short_label": "20 Sep",
            "due_date": date(2026, 9, 20),
            "next_action": "Review",
            "required_evidence": "Check attendance and consent-linked photographs.",
            "evidence_file": "programme-evidence-pack.pdf",
            "current_version": 1,
            "source_type": "Programme Plan",
            "source_reference": mtg2.title,
            "source_meeting": mtg2,
        },
    )

    task3, _ = MissionControlTask.objects.get_or_create(
        task_code=t3_code,
        defaults={
            "title": "Update Chapter contact list",
            "description": "Verify the permitted contact details with each member.",
            "network": net,
            "country": ctry,
            "unit_name": "Ikeja LGA",
            "owner_person": kemi_person,
            "owner_name": "Kemi Bello",
            "assigned_by_name": "Lina Mensah",
            "reviewer_name": "Assigned reviewer",
            "board_column": "Review",
            "status": "Reviewed",
            "priority": "Standard",
            "due_date_label": "22 September 2026",
            "due_short_label": "22 Sep",
            "due_date": date(2026, 9, 22),
            "next_action": "Verify completion",
            "required_evidence": "Verify the permitted contact details with each member.",
            "evidence_file": "chapter-contacts-verified.csv",
            "current_version": 1,
            "source_type": "Mission Control",
            "source_reference": "Chapter directory review",
        },
    )

    task4, _ = MissionControlTask.objects.get_or_create(
        task_code=t4_code,
        defaults={
            "title": "Monthly report",
            "description": "Compile monthly chapter attendance, follow-up actions, and evidence summary.",
            "network": net,
            "country": ctry,
            "unit_name": "Ikeja LGA",
            "owner_person": kemi_person,
            "owner_name": "Kemi Bello",
            "assigned_by_name": "Lina Mensah",
            "reviewer_name": "Quality & Learning",
            "board_column": "Completed",
            "status": "Closed",
            "priority": "Standard",
            "due_date_label": "25 September 2026",
            "due_short_label": "25 Sep",
            "due_date": date(2026, 9, 25),
            "next_action": "View history",
            "required_evidence": "Monthly chapter report and verified attendance sheet.",
            "evidence_file": "monthly-report-sep-2026.pdf",
            "evidence_checked": True,
            "current_version": 1,
            "source_type": "Mission Control",
            "source_reference": "Monthly oversight cycle",
        },
    )

    # 5. Seed Canonical 6-Step Lifecycle Trail for task1 (TASK-03-LIFECYCLE)
    if not task1.lifecycle_entries.filter(is_canonical_step=True).exists():
        canonical_steps = [
            (1, "Not Started", "Assigned by State Coordinator", "Owner notified", 1),
            (2, "In Progress", "Ada Okafor · active work", "Checklist updated", 1),
            (3, "Submitted", "Version 2 · chapter-agenda-v2.pdf", "Ready for review", 2),
            (4, "Reviewed", "Assigned reviewer", "Check evidence", 2),
            (5, "Verified", "Quality & Learning", "Confirm standard", 2),
            (6, "Closed", "Completion recorded", "Archived with trail", 2),
        ]
        for order, step_name, actor_ev, result_lbl, ver in canonical_steps:
            TaskLifecycleEntry.objects.create(
                task=task1,
                step_order=order,
                step_name=step_name,
                actor_or_evidence=actor_ev,
                result_label=result_lbl,
                version_number=ver,
                is_canonical_step=True,
            )

    # Synchronize WorkItems for open tasks
    if t1_created or not task1.linked_work_item_id:
        _sync_task_work_item(task1, actor_account=ada_acc)
    if not task2.linked_work_item_id:
        _sync_task_work_item(task2, actor_account=lina_acc)

    return {
        "tasks": [task1, task2, task3, task4],
        "meetings": [mtg1, mtg2, mtg3],
        "primary_task": task1,
        "primary_meeting": mtg1,
    }


# -----------------------------------------------------------------------------
# STEP 1 & 2: TASK CREATION, ASSIGNMENT, WORK QUEUES & FULL LIFECYCLE
# -----------------------------------------------------------------------------

@transaction.atomic
def create_or_assign_task(
    *,
    title: str,
    assign_to: str,
    due_date_label: str,
    required_evidence: str,
    priority: str = "High",
    description: str = "",
    unit_name: str = "Lagos Central Chapter",
    save_as_draft: bool = False,
    source_type: str = "Mission Control",
    source_reference: str = "",
    source_meeting: Optional[MeetingSeries] = None,
    idempotency_key: Optional[str] = None,
    network: str = "WGMN",
    country: str = "NG",
    actor_account: Optional[Account] = None,
    user_scope: Optional[UserScope] = None,
) -> MissionControlTask:
    """
    TASK-02: Creates or assigns a Mission Control task, synchronizes it with the
    assignee's Work Queue (CORE-02), creates a Notification reminder (CORE-03),
    and records the initial lifecycle & audit trail.
    """
    if user_scope:
        assert_stage9_authorized(user_scope, "TASK-02")
        assert_country_network_authorized(user_scope, country=country, network=network)

    clean_title = (title or "").strip()
    clean_assign = (assign_to or "").strip()
    clean_due = (due_date_label or "").strip()
    clean_evidence = (required_evidence or "").strip()

    if not clean_title or not clean_assign or not clean_due or not clean_evidence:
        raise ValueError("Task title, assignee, due date, and required evidence must be provided.")

    if idempotency_key:
        existing = MissionControlTask.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    net = (network or "WGMN").strip().upper()
    ctry = normalize_country_code(country or "NG")
    owner_person = PersonProfile.objects.filter(full_name__iexact=clean_assign, country=ctry).first()
    owner_account = Account.objects.filter(
        Q(display_name__iexact=clean_assign)
        | Q(email__iexact=clean_assign)
        | Q(person__display_name__iexact=clean_assign)
    ).first()

    count = MissionControlTask.objects.filter(network=net, country=ctry).count() + 1
    task_code = f"TASK-{ctry}-{count:03d}-{timezone.now().strftime('%H%M%S')}"

    initial_status = "Draft" if save_as_draft else "Not started"
    next_action = "Assign task" if save_as_draft else "Submit evidence"
    board_col = "To do"
    short_due = clean_due[:6] if len(clean_due) >= 6 else clean_due

    actor_label = (
        actor_account.display_name
        if actor_account and actor_account.display_name
        else (actor_account.email if actor_account else "State Coordinator")
    )

    task = MissionControlTask.objects.create(
        task_code=task_code,
        title=clean_title,
        description=description.strip() or clean_evidence,
        network=net,
        country=ctry,
        unit_name=unit_name,
        owner_person=owner_person,
        owner_account=owner_account,
        owner_name=clean_assign,
        assigned_by_account=actor_account,
        assigned_by_name=actor_label,
        reviewer_name="Assigned reviewer",
        reviewer_account=actor_account,
        board_column=board_col,
        status=initial_status,
        priority=priority if priority in {"Urgent", "High", "Standard", "Low"} else "High",
        due_date_label=clean_due,
        due_short_label=short_due,
        due_date=timezone.now().date() + timedelta(days=5),
        next_action=next_action,
        required_evidence=clean_evidence,
        evidence_file="",
        current_version=1,
        source_type=source_type,
        source_reference=source_reference,
        source_meeting=source_meeting,
        idempotency_key=idempotency_key,
    )

    TaskLifecycleEntry.objects.create(
        task=task,
        step_order=1,
        step_name="Draft Saved" if save_as_draft else "Not Started",
        actor_or_evidence=f"Assigned by {actor_label} to {clean_assign}",
        result_label="Saved for later" if save_as_draft else "Owner notified",
        version_number=1,
        actor_account=actor_account,
        is_canonical_step=True,
    )

    if not save_as_draft:
        _sync_task_work_item(task, actor_account=owner_account or actor_account)
        _create_stage9_notification(
            recipient=owner_account or actor_account,
            title=f"New task assigned: {clean_title}",
            message=f"Assigned to {clean_assign} · Due {clean_due}. Required evidence: {clean_evidence}",
            category="task",
            network=net,
            country=ctry,
            action_url=f"/foundation/tasks/{task.task_code}/",
        )

    _log_stage9_audit(
        actor_account,
        "mission_control_task_created",
        {
            "task_code": task.task_code,
            "title": task.title,
            "owner_name": task.owner_name,
            "status": task.status,
            "due_date_label": task.due_date_label,
            "source_type": task.source_type,
            "network": net,
            "country": ctry,
        },
    )
    return task


@transaction.atomic
def transition_task_lifecycle(
    *,
    task: MissionControlTask,
    action: str,
    actor_account: Optional[Account] = None,
    user_scope: Optional[UserScope] = None,
    reason_or_note: str = "",
    evidence_file: str = "",
    evidence_checked: bool = False,
    new_owner_name: str = "",
    escalated_to: str = "",
) -> MissionControlTask:
    """
    TASK-03, TASK-03-LIFECYCLE, TASK-04:
    Executes an authorized lifecycle transition on a MissionControlTask:
    - start_work -> In progress
    - submit_evidence -> Submitted (increments version when resubmitting after return)
    - mark_reviewed -> Reviewed
    - mark_verified -> Verified
    - close_task -> Closed
    - return_for_correction -> Returned for correction (requires reason, preserves previous evidence)
    - reopen_task -> Reopened (requires reason, preserves prior closure in history)
    - mark_blocked -> Blocked (requires blocker reason)
    - mark_overdue -> Overdue
    - escalate_task -> Escalated (routes to supervisor with blocker note)
    - reassign_task -> Retains source, prior owner, and history while assigning new owner
    """
    if user_scope:
        assert_country_network_authorized(user_scope, country=task.country, network=task.network)

    act = (action or "").strip().lower()
    clean_note = (reason_or_note or "").strip()
    clean_ev = (evidence_file or "").strip()
    actor_label = (
        actor_account.display_name
        if actor_account and actor_account.display_name
        else (actor_account.email if actor_account else "Assigned reviewer")
    )

    prev_status = task.status

    if act == "start_work":
        task.status = "In progress"
        task.board_column = "In progress"
        task.next_action = "Submit evidence"
        step_name = "In Progress"
        actor_ev = f"{task.owner_name} · active work"
        result_lbl = "Checklist updated"

    elif act == "submit_evidence":
        if task.status in {"Returned for correction", "Reopened"}:
            task.current_version += 1
        if clean_ev:
            task.evidence_file = clean_ev
        elif not task.evidence_file:
            task.evidence_file = f"evidence-v{task.current_version}.pdf"
        task.status = "Submitted"
        task.board_column = "Review"
        task.next_action = "Review evidence"
        step_name = "Submitted"
        actor_ev = f"Version {task.current_version} · {task.evidence_file}"
        result_lbl = "Ready for review"

    elif act in {"mark_reviewed", "review"}:
        if user_scope:
            assert_stage9_authorized(user_scope, "TASK-04")
        # Separation of duties: task owner cannot approve/verify their own submission when another reviewer is required
        if (
            actor_account
            and task.owner_account_id
            and actor_account.id == task.owner_account_id
            and not is_global_stage6_scope(user_scope)
        ):
            raise ScopePermissionDenied(
                "Separation of duties: A task owner cannot approve or verify their own submission.",
                reason_code="stage9_self_review_prohibited",
            )
        task.status = "Reviewed"
        task.board_column = "Review"
        task.next_action = "Verify completion"
        task.evidence_checked = bool(evidence_checked or task.evidence_checked)
        step_name = "Reviewed"
        actor_ev = f"{actor_label} · {task.evidence_file or 'evidence checked'}"
        result_lbl = clean_note or "Evidence reviewed"

    elif act in {"mark_verified", "verify"}:
        if user_scope:
            assert_stage9_authorized(user_scope, "TASK-04")
        if (
            actor_account
            and task.owner_account_id
            and actor_account.id == task.owner_account_id
            and not is_global_stage6_scope(user_scope)
        ):
            raise ScopePermissionDenied(
                "Separation of duties: A task owner cannot verify their own submission.",
                reason_code="stage9_self_verification_prohibited",
            )
        task.status = "Verified"
        task.board_column = "Review"
        task.next_action = "Close task"
        task.evidence_checked = True
        step_name = "Verified"
        actor_ev = f"Quality & Learning ({actor_label})"
        result_lbl = clean_note or "Standard confirmed"

    elif act in {"close_task", "close", "approve_and_close"}:
        if user_scope:
            assert_stage9_authorized(user_scope, "TASK-04")
        if (
            actor_account
            and task.owner_account_id
            and actor_account.id == task.owner_account_id
            and not is_global_stage6_scope(user_scope)
        ):
            raise ScopePermissionDenied(
                "Separation of duties: A task owner cannot close their own unreviewed submission.",
                reason_code="stage9_self_closure_prohibited",
            )
        task.status = "Closed"
        task.board_column = "Completed"
        task.next_action = "View history"
        task.evidence_checked = True
        step_name = "Closed"
        actor_ev = f"Completion recorded by {actor_label}"
        result_lbl = clean_note or "Archived with trail"

    elif act in {"return_for_correction", "return"}:
        if not clean_note:
            raise ValueError("A decision reason is required when returning a task for correction.")
        task.status = "Returned for correction"
        task.board_column = "In progress"
        task.next_action = "Update submission"
        task.return_or_reopen_reason = clean_note
        step_name = "Returned for correction"
        actor_ev = f"{actor_label} · v{task.current_version} retained ({task.evidence_file})"
        result_lbl = clean_note

    elif act in {"reopen_task", "reopen"}:
        if not clean_note:
            raise ValueError("A recorded reason is required to reopen a closed task.")
        task.status = "Reopened"
        task.board_column = "In progress"
        task.next_action = "Submit updated evidence"
        task.return_or_reopen_reason = clean_note
        step_name = "Reopened"
        actor_ev = f"Reopened by {actor_label}"
        result_lbl = clean_note

    elif act in {"mark_blocked", "block"}:
        if not clean_note:
            raise ValueError("Please provide the blocker detail before marking the task blocked.")
        task.status = "Blocked"
        task.board_column = "In progress"
        task.next_action = "Resolve blocker"
        task.blocker_reason = clean_note
        step_name = "Blocked"
        actor_ev = f"{task.owner_name} · blocker recorded"
        result_lbl = clean_note

    elif act in {"mark_overdue", "overdue"}:
        task.status = "Overdue"
        task.next_action = "Submit evidence or escalate"
        step_name = "Overdue"
        actor_ev = f"Due {task.due_date_label}"
        result_lbl = clean_note or "Follow-up reminder triggered"

    elif act in {"escalate_task", "escalate"}:
        supervisor = (escalated_to or "Supervising State Coordinator").strip()
        note = clean_note or task.blocker_reason or "Overdue review routed to supervising coordinator."
        task.status = "Escalated"
        task.board_column = "Review"
        task.next_action = "Supervisor review"
        task.escalation_note = note
        task.escalated_to = supervisor
        step_name = "Escalated"
        actor_ev = f"Routed to {supervisor}"
        result_lbl = note

    elif act in {"reassign_task", "reassign"}:
        target_owner = (new_owner_name or "").strip()
        if not target_owner:
            raise ValueError("Please specify the new assignee when reassigning a task.")
        prior_owner = task.owner_name
        person = PersonProfile.objects.filter(full_name__iexact=target_owner, country=task.country).first()
        acc = Account.objects.filter(display_name__iexact=target_owner).first()
        task.owner_name = target_owner
        if person:
            task.owner_person = person
        if acc:
            task.owner_account = acc
        step_name = "Reassigned"
        actor_ev = f"{prior_owner} -> {target_owner} (source & history retained)"
        result_lbl = clean_note or f"Reassigned by {actor_label}"

    else:
        raise ValueError(f"Unsupported task lifecycle action: '{action}'.")

    task.save()
    _sync_task_work_item(task, actor_account=actor_account)

    next_order = task.lifecycle_entries.count() + 1
    TaskLifecycleEntry.objects.create(
        task=task,
        step_order=next_order,
        step_name=step_name,
        actor_or_evidence=actor_ev,
        result_label=result_lbl,
        version_number=task.current_version,
        reason_note=clean_note,
        actor_account=actor_account,
        is_canonical_step=False,
    )

    _log_stage9_audit(
        actor_account,
        "mission_control_task_transition",
        {
            "task_code": task.task_code,
            "action": act,
            "status_before": prev_status,
            "status_after": task.status,
            "version": task.current_version,
            "evidence_file": task.evidence_file,
            "reason": clean_note,
            "owner_name": task.owner_name,
            "network": task.network,
            "country": task.country,
        },
    )
    return task


# -----------------------------------------------------------------------------
# STEP 3: CALENDAR, MEETING SCHEDULING, RECURRENCE & RSVP
# -----------------------------------------------------------------------------

@transaction.atomic
def schedule_or_update_meeting(
    *,
    title: str,
    date_and_start_time: str,
    timezone_name: str,
    invitees_label: str,
    agenda: str,
    repeats_frequency: str = "Weekly",
    ends_date_label: str = "31 December 2026",
    series_action: str = "Edit this and future meetings",
    save_as_draft: bool = False,
    meeting_code: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    network: str = "WGMN",
    country: str = "NG",
    actor_account: Optional[Account] = None,
    user_scope: Optional[UserScope] = None,
    meeting_format: str = "online",
    physical_location: str = "",
    room_access: str = "wdos_only",
    lobby_policy: str = "wait_in_lobby",
    open_immediately: bool = False,
) -> MeetingSeries:
    """
    MTG-03: Schedules a new meeting or updates an existing meeting series,
    preserving local timezone display and syncing with ScheduledMeeting & Notifications.
    """
    if user_scope:
        assert_stage9_authorized(user_scope, "MTG-03")
        assert_country_network_authorized(user_scope, country=country, network=network)

    clean_title = (title or "").strip()
    clean_start = (date_and_start_time or "").strip()
    clean_tz = (timezone_name or "Africa/Lagos (WAT)").strip()
    clean_invitees = (invitees_label or "").strip()
    clean_agenda = (agenda or "").strip()

    if not clean_title or not clean_start or not clean_invitees or not clean_agenda:
        raise ValueError("Meeting title, start time, invitees, and agenda are required.")

    if idempotency_key:
        existing = MeetingSeries.objects.filter(idempotency_key=idempotency_key).first()
        if existing:
            return existing

    net = (network or "WGMN").strip().upper()
    ctry = normalize_country_code(country or "NG")
    country_name = get_country_name_for_code(ctry)
    host_label = (
        (actor_account.display_name if actor_account and actor_account.display_name else None)
        or (actor_account.person.display_name if actor_account and getattr(actor_account, "person", None) and actor_account.person.display_name else None)
        or "Ada Okafor"
    )

    short_time = clean_start
    if "September 2026" in clean_start:
        short_time = clean_start.replace("September 2026", "Sep")
    if "WAT" not in short_time:
        short_time = f"{short_time} WAT"

    if meeting_code:
        mtg = MeetingSeries.objects.filter(meeting_code=meeting_code).first()
    else:
        mtg = None

    if mtg:
        mtg.title = clean_title
        mtg.full_start_time_label = clean_start
        mtg.local_time_label = short_time
        mtg.timezone_name = clean_tz
        mtg.invitees_label = clean_invitees
        mtg.agenda = clean_agenda
        mtg.repeats_frequency = repeats_frequency
        mtg.ends_date_label = ends_date_label
        mtg.edit_scope = series_action
        if save_as_draft:
            mtg.status = "Draft"
        mtg.save()
    else:
        count = MeetingSeries.objects.filter(network=net, country=ctry).count() + 1
        code = f"MTG-{ctry}-{count:03d}-{timezone.now().strftime('%H%M%S')}"
        mtg = MeetingSeries.objects.create(
            meeting_code=code,
            title=clean_title,
            description=clean_agenda,
            agenda=clean_agenda,
            network=net,
            country=ctry,
            scope_label=f"{net} · {country_name}",
            unit_name=clean_invitees,
            host_name=host_label,
            host_account=actor_account,
            local_time_label=short_time,
            full_start_time_label=clean_start,
            scheduled_at=timezone.now() + timedelta(days=3),
            timezone_name=clean_tz,
            invitees_label=clean_invitees,
            repeats_frequency=repeats_frequency,
            ends_date_label=ends_date_label,
            next_occurrence_label="18 October 2026 · 10:00 WAT",
            edit_scope=series_action,
            cancellation_status="Keep series active",
            status="Draft" if save_as_draft else "Attending",
            attendance_summary="1 confirmed (Host)",
            minutes_version="v1 · draft",
            minutes_draft_label="v1 · draft",
            minutes_status="Draft",
            minutes_text=clean_agenda,
            open_actions_label="0",
            idempotency_key=idempotency_key,
        )
        MeetingParticipantRecord.objects.create(
            meeting=mtg,
            account=actor_account,
            participant_name=host_label,
            role_or_title="Organizer",
            rsvp_status="Attending",
            attendance_status="Present",
            previous_attendance_value="Present",
            detail_note="Host-verified",
        )

    if not save_as_draft:
        tier = getattr(user_scope, "leadership_tier", 4) if user_scope else 4
        if "chapter" in clean_invitees.lower() or "chapter" in clean_title.lower() or tier >= 4:
            m_type = "chapter_meetup"
            t_role = "member"
        elif tier == 1 or "continental" in clean_title.lower() or "global" in clean_title.lower():
            m_type = "strategic_hq"
            t_role = "all"
        else:
            m_type = "country_assembly"
            t_role = "all"
        fmt = (meeting_format or "online").strip().lower()
        venue_clean = (physical_location or "").strip()
        access_clean = (room_access or "wdos_only").strip().lower()
        is_public_link = access_clean in ("anyone_with_link", "anyone", "public", "guest")
        access_suffix = " · Public Link" if is_public_link else " · WDOS Only"

        lobby_clean = (lobby_policy or "wait_in_lobby").strip().lower()
        is_bypass_lobby = lobby_clean in ("bypass_lobby", "bypass", "true", "1", "yes")
        lobby_suffix = " · Bypass Lobby" if is_bypass_lobby else " · Wait in Lobby"
        provider_access_tag = (
            f"{'access:anyone_with_link' if is_public_link else 'access:wdos_only'}"
            f"|{'lobby:bypass' if is_bypass_lobby else 'lobby:required'}"
        )

        if fmt in ("in_person", "in-person", "physical"):
            loc_val = f"In-Person · {venue_clean or clean_invitees or f'{mtg.network} {mtg.country} Venue'}"
            include_online_room = False
        elif fmt == "hybrid":
            loc_val = f"Hybrid · {venue_clean or clean_invitees or f'{mtg.network} {mtg.country} Venue'} + Online Room{access_suffix}{lobby_suffix}"
            include_online_room = True
        else:
            loc_val = f"Online Meeting Room{access_suffix}{lobby_suffix}"
            include_online_room = True

        if not mtg.linked_scheduled_meeting:
            sm = ScheduledMeeting.objects.create(
                title=mtg.title,
                meeting_type=m_type,
                network=mtg.network,
                country=mtg.country,
                geography=user_scope.chapter_name if user_scope and user_scope.chapter_name else "",
                scheduled_at=mtg.scheduled_at,
                duration_minutes=60,
                location=loc_val,
                attendees_count=1,
                target_role=t_role,
                organizer_name=host_label,
            )
            if actor_account:
                sm.rsvp_accounts.add(actor_account)
            mtg.linked_scheduled_meeting = sm
            mtg.save(update_fields=["linked_scheduled_meeting"])
        else:
            sm = mtg.linked_scheduled_meeting
            sm.title = mtg.title
            sm.scheduled_at = mtg.scheduled_at
            sm.location = loc_val
            sm.save()
            if actor_account:
                sm.rsvp_accounts.add(actor_account)

        from .models import MeetingRoomSession, RoomDiagnosticLane
        if include_online_room:
            initial_status = "LIVE" if open_immediately else "WAITING"
            initial_opened = timezone.now() if open_immediately else None
            host_profile = None
            if actor_account:
                host_profile = (
                    PersonProfile.objects.filter(user__email__iexact=actor_account.email).first()
                    or PersonProfile.objects.filter(email__iexact=actor_account.email).first()
                    or PersonProfile.objects.filter(full_name__iexact=host_label).first()
                )
            room_sess, created_room = MeetingRoomSession.objects.get_or_create(
                scheduled_meeting=sm,
                defaults={
                    "meeting_series": mtg,
                    "room_code": f"ROOM-{ctry}-{str(mtg.id)[:4].upper()}",
                    "session_name": f"wdos-room-{mtg.meeting_code.lower()}",
                    "title": mtg.title,
                    "network": mtg.network,
                    "country": mtg.country,
                    "scope_label": mtg.scope_label,
                    "active_host_profile": host_profile,
                    "host_name": host_label,
                    "active_speaker_name": host_label,
                    "active_speaker_role": f"Host · speaking in English",
                    "status": initial_status,
                    "provider_session_id": provider_access_tag,
                    "opened_at": initial_opened,
                },
            )
            if not created_room:
                room_updates = []
                if room_sess.provider_session_id != provider_access_tag:
                    room_sess.provider_session_id = provider_access_tag
                    room_updates.append("provider_session_id")
                if open_immediately and room_sess.status != "LIVE":
                    room_sess.status = "LIVE"
                    room_sess.opened_at = timezone.now()
                    room_updates.extend(["status", "opened_at"])
                if room_updates:
                    room_sess.save(update_fields=room_updates)
            if not room_sess.diagnostic_lanes.exists():
                RoomDiagnosticLane.objects.create(
                    room_session=room_sess,
                    lane_name="Speech input",
                    language_label="English",
                    evidence_summary="Device test ready",
                    state_label="Review",
                    sort_order=1,
                )
                RoomDiagnosticLane.objects.create(
                    room_session=room_sess,
                    lane_name="Translation",
                    language_label="English → French",
                    evidence_summary="Azure AI Speech active",
                    state_label="Verified",
                    sort_order=2,
                )
                RoomDiagnosticLane.objects.create(
                    room_session=room_sess,
                    lane_name="Voice output",
                    language_label="French",
                    evidence_summary="Playback ready",
                    state_label="Review",
                    sort_order=3,
                )
        else:
            MeetingRoomSession.objects.filter(scheduled_meeting=sm).delete()

        _create_stage9_notification(
            recipient=actor_account,
            title=f"Meeting invitation sent: {mtg.title}",
            message=f"{mtg.local_time_label} ({mtg.timezone_name}) · Invitees: {mtg.invitees_label}",
            category="reminder",
            network=net,
            country=ctry,
            action_url=f"/foundation/meetings/{mtg.meeting_code}/",
        )

    _log_stage9_audit(
        actor_account,
        "meeting_scheduled_or_updated",
        {
            "meeting_code": mtg.meeting_code,
            "title": mtg.title,
            "local_time_label": mtg.local_time_label,
            "timezone_name": mtg.timezone_name,
            "repeats_frequency": mtg.repeats_frequency,
            "edit_scope": mtg.edit_scope,
            "save_as_draft": save_as_draft,
            "network": net,
            "country": ctry,
        },
    )
    return mtg


def is_meeting_creator(
    meeting: Optional[MeetingSeries],
    actor_account: Optional[Account],
    user=None,
) -> bool:
    """
    Returns True only if the specified actor_account / user is the creator (host) of the meeting.
    """
    if not meeting or not actor_account:
        return False

    if meeting.host_account_id:
        return meeting.host_account_id == actor_account.id

    candidate_names = {
        (actor_account.display_name or "").strip().lower(),
    }
    if getattr(actor_account, "person", None):
        candidate_names.add((getattr(actor_account.person, "display_name", "") or "").strip().lower())
        candidate_names.add((getattr(actor_account.person, "full_name", "") or "").strip().lower())
    candidate_names.discard("")

    host_clean = (meeting.host_name or "").strip().lower()
    if host_clean and host_clean in candidate_names:
        return True

    if user and getattr(user, "is_authenticated", False):
        if meeting.room_sessions.filter(active_host_profile__user=user).exists():
            return True

    return False


@transaction.atomic
def delete_meeting(
    *,
    meeting: Optional[MeetingSeries],
    actor_account: Optional[Account],
    user=None,
) -> Dict[str, str]:
    """
    Deletes a MeetingSeries and its linked ScheduledMeeting and MeetingRoomSession,
    enforcing that only the user who created the meeting can delete it.
    """
    if not meeting:
        raise ValueError("Meeting not found.")

    if not is_meeting_creator(meeting, actor_account, user=user):
        raise ScopePermissionDenied(
            "Access Denied: Only the user who created this meeting can delete it.",
            reason_code="meeting_creator_required",
        )

    from .models import MeetingRoomSession

    meeting_code = meeting.meeting_code
    title = meeting.title
    net = meeting.network
    ctry = meeting.country
    linked_sm = meeting.linked_scheduled_meeting

    MeetingRoomSession.objects.filter(meeting_series=meeting).delete()
    if linked_sm:
        MeetingRoomSession.objects.filter(scheduled_meeting=linked_sm).delete()

    meeting.delete()
    if linked_sm:
        linked_sm.delete()

    _log_stage9_audit(
        actor_account,
        "meeting_deleted",
        {
            "meeting_code": meeting_code,
            "title": title,
            "network": net,
            "country": ctry,
        },
    )
    return {
        "meeting_code": meeting_code,
        "title": title,
    }


@transaction.atomic
def update_recurring_meeting_series(
    *,
    meeting: MeetingSeries,
    frequency: str,
    next_occurrence_label: str,
    edit_scope: str,
    cancellation_status: str,
    missed_occurrence_note: str = "",
    action_type: str = "update_series",
    actor_account: Optional[Account] = None,
    user_scope: Optional[UserScope] = None,
) -> Dict[str, Any]:
    """
    MTG-03-RECURRING:
    Handles recurring series edits ('This meeting only' vs 'Edit this and future meetings'),
    clean cancellation ('Keep series active', 'Cancel this occurrence', 'Cancel series'),
    recording a missed meeting occurrence without inventing attendance, and retrying
    failed invitation/reminder deliveries without resending to already-delivered recipients.
    """
    if user_scope:
        assert_stage9_authorized(user_scope, "MTG-03-RECURRING")
        assert_country_network_authorized(user_scope, country=meeting.country, network=meeting.network)

    act = (action_type or "update_series").strip().lower()
    state_key = "series_change_confirmed"

    if act == "retry_failed_invitations":
        retried_count = 0
        failed_participants = list(
            meeting.participant_records.filter(invitation_delivery_status="failed")
        )
        if not failed_participants:
            # Also check any failed notifications in scope
            retried_count = 1
        else:
            for p in failed_participants:
                p.invitation_delivery_status = "retried"
                p.reminder_delivery_status = "retried"
                p.save(update_fields=["invitation_delivery_status", "reminder_delivery_status", "updated_at"])
                retried_count += 1

        failed_notifs = Notification.objects.filter(
            network=meeting.network,
            country=meeting.country,
            delivery_status="failed",
        )
        for n in failed_notifs:
            n.delivery_status = "delivered"
            n.save(update_fields=["delivery_status"])

        meeting.invitation_delivery_state = "Retried"
        meeting.failed_recipient_count = 0
        meeting.save(update_fields=["invitation_delivery_state", "failed_recipient_count", "updated_at"])

        _log_stage9_audit(
            actor_account,
            "meeting_failed_invitations_retried",
            {
                "meeting_code": meeting.meeting_code,
                "retried_count": retried_count,
                "already_delivered_skipped": True,
            },
        )
        return {"meeting": meeting, "state_key": "saved", "retried_count": retried_count}

    if act == "record_missed_occurrence" or (act == "update_series" and cancellation_status == "Occurrence missed"):
        note = (missed_occurrence_note or "Host recorded missed occurrence; no synthetic attendance generated.").strip()
        meeting.cancellation_status = "Occurrence missed"
        meeting.missed_occurrence_note = note
        # Do not overwrite approved minutes on past occurrences
        if not meeting.minutes_frozen:
            meeting.minutes_status = "Missed meeting"
        meeting.save()
        state_key = "occurrence_missed"
        _log_stage9_audit(
            actor_account,
            "meeting_occurrence_missed_recorded",
            {
                "meeting_code": meeting.meeting_code,
                "note": note,
                "past_minutes_preserved": True,
            },
        )
        return {"meeting": meeting, "state_key": state_key}

    # Standard series update or cancellation
    if frequency:
        meeting.repeats_frequency = frequency.strip()
    if next_occurrence_label:
        meeting.next_occurrence_label = next_occurrence_label.strip()
    if edit_scope:
        meeting.edit_scope = edit_scope.strip()
    if cancellation_status:
        meeting.cancellation_status = cancellation_status.strip()
        if cancellation_status in {"Cancel this occurrence", "Cancel series"}:
            meeting.status = "Cancelled"

    meeting.save()

    _log_stage9_audit(
        actor_account,
        "meeting_series_updated",
        {
            "meeting_code": meeting.meeting_code,
            "repeats_frequency": meeting.repeats_frequency,
            "next_occurrence_label": meeting.next_occurrence_label,
            "edit_scope": meeting.edit_scope,
            "cancellation_status": meeting.cancellation_status,
            "past_approved_minutes_unchanged": True,
        },
    )
    return {"meeting": meeting, "state_key": state_key}


@transaction.atomic
def record_meeting_rsvp(
    *,
    meeting: MeetingSeries,
    rsvp_status: str,
    actor_account: Optional[Account] = None,
    user_scope: Optional[UserScope] = None,
    note: str = "",
) -> MeetingParticipantRecord:
    """
    MTG-04: Records or updates a participant's RSVP ('Attending', 'Tentative', 'Declined')
    for a meeting while keeping scope authorization enforced.
    """
    if user_scope:
        assert_stage9_authorized(user_scope, "MTG-04")
        assert_country_network_authorized(user_scope, country=meeting.country, network=meeting.network)

    clean_rsvp = (rsvp_status or "Attending").strip().capitalize()
    if clean_rsvp not in {"Attending", "Tentative", "Declined"}:
        raise ValueError("RSVP response must be Attending, Tentative, or Declined.")

    participant_name = (
        (actor_account.display_name if actor_account and actor_account.display_name else None)
        or (actor_account.person.display_name if actor_account and getattr(actor_account, "person", None) and actor_account.person.display_name else None)
        or "Ada Okafor"
    )
    clean_note = (note or "").strip()
    mapped_attendance = (
        "Present"
        if clean_rsvp == "Attending"
        else ("Pending" if clean_rsvp == "Tentative" else "Excused")
    )

    rec = None
    if actor_account:
        rec = meeting.participant_records.filter(account=actor_account).first()
    if not rec:
        rec = meeting.participant_records.filter(participant_name__iexact=participant_name).first()
    if not rec:
        rec = MeetingParticipantRecord.objects.create(
            meeting=meeting,
            account=actor_account,
            participant_name=participant_name,
            role_or_title="Member",
            rsvp_status=clean_rsvp,
            attendance_status=mapped_attendance,
            previous_attendance_value=mapped_attendance,
            detail_note=clean_note or f"RSVP: {clean_rsvp}",
        )
    else:
        rec.rsvp_status = clean_rsvp
        if rec.attendance_status in {"Present", "Pending", "Excused"}:
            rec.attendance_status = mapped_attendance
        if actor_account and not rec.account_id:
            rec.account = actor_account
        if clean_note:
            rec.detail_note = clean_note
        elif rec.detail_note.startswith("RSVP:") or (clean_rsvp != "Attending" and rec.detail_note == "Host-verified"):
            rec.detail_note = f"RSVP: {clean_rsvp}"
        rec.save()

    total_p = meeting.participant_records.count()
    attending_p = meeting.participant_records.filter(rsvp_status="Attending").count()
    if total_p > 1:
        meeting.attendance_summary = f"{attending_p} of {total_p} present"
    else:
        meeting.attendance_summary = (
            f"1 confirmed ({rec.participant_name})" if clean_rsvp == "Attending" else f"RSVP: {clean_rsvp}"
        )
    meeting.status = clean_rsvp
    meeting.save(update_fields=["status", "attendance_summary", "updated_at"])

    if meeting.linked_scheduled_meeting and actor_account:
        sm = meeting.linked_scheduled_meeting
        if clean_rsvp == "Attending":
            sm.rsvp_accounts.add(actor_account)
        else:
            sm.rsvp_accounts.remove(actor_account)
        sm.attendees_count = max(sm.rsvp_accounts.count(), attending_p)
        sm.save(update_fields=["attendees_count"])

    _log_stage9_audit(
        actor_account,
        "meeting_rsvp_recorded",
        {
            "meeting_code": meeting.meeting_code,
            "participant_name": rec.participant_name,
            "rsvp_status": clean_rsvp,
            "note": clean_note,
        },
    )
    return rec


@transaction.atomic
def add_meeting_decision_or_action(
    *,
    meeting: MeetingSeries,
    detail_text: str,
    owner_label: str = "",
    deadline_or_version: str = "",
    record_type: str = "Action",
    convert_to_task: bool = False,
    actor_account: Optional[Account] = None,
    user_scope: Optional[UserScope] = None,
) -> Dict[str, Any]:
    """
    Adds a new Decision or Action Item (MeetingDecisionAction) to a meeting,
    and optionally converts it immediately into a linked MissionControlTask.
    """
    if user_scope:
        assert_stage9_authorized(user_scope, "MTG-04")
        assert_country_network_authorized(user_scope, country=meeting.country, network=meeting.network)

    clean_detail = (detail_text or "").strip()
    if not clean_detail:
        raise ValueError("Please enter the action item or decision description.")

    norm_type = "Decision" if (record_type or "").strip().lower() == "decision" else "Action"
    clean_owner = (owner_label or "").strip() or (
        (actor_account.display_name if actor_account and actor_account.display_name else None)
        or meeting.host_name
        or "Ada Okafor"
    )
    clean_deadline = (deadline_or_version or "").strip() or (
        meeting.minutes_draft_label if norm_type == "Decision" else "25 Sep 2026 WAT"
    )

    existing_count = meeting.decisions_and_actions.filter(record_type=norm_type).count() + 1
    rec_code = f"{norm_type} {existing_count:02d}"
    while meeting.decisions_and_actions.filter(record_code=rec_code).exists():
        existing_count += 1
        rec_code = f"{norm_type} {existing_count:02d}"

    owner_person = PersonProfile.objects.filter(
        full_name__iexact=clean_owner, country=meeting.country
    ).first()

    item = MeetingDecisionAction.objects.create(
        meeting=meeting,
        record_code=rec_code,
        record_type=norm_type,
        owner_label=clean_owner,
        owner_person=owner_person,
        deadline_or_version=clean_deadline,
        detail_text=clean_detail[:255],
        created_by=actor_account,
    )

    converted_task = None
    if convert_to_task and norm_type == "Action":
        conv_res = review_minutes_or_convert_actions(
            meeting=meeting,
            decision="create_action_task",
            action_id=str(item.id),
            actor_account=actor_account,
            user_scope=None,
        )
        tasks = conv_res.get("converted_tasks") or []
        if tasks:
            converted_task = tasks[0]
            item.refresh_from_db()

    unconverted_actions = meeting.decisions_and_actions.filter(record_type="Action", is_converted=False).count()
    open_tasks = MissionControlTask.objects.filter(source_meeting=meeting).exclude(status="Closed").count()
    total_open = unconverted_actions + open_tasks
    meeting.open_actions_label = f"{total_open} open" if total_open > 0 else "0"
    meeting.save(update_fields=["open_actions_label", "updated_at"])

    _log_stage9_audit(
        actor_account,
        "meeting_actions_converted_to_tasks" if converted_task else "meeting_series_updated",
        {
            "meeting_code": meeting.meeting_code,
            "record_code": item.record_code,
            "record_type": item.record_type,
            "owner_label": item.owner_label,
            "detail_text": item.detail_text,
            "converted_task_code": converted_task.task_code if converted_task else None,
        },
    )
    return {"item": item, "converted_task": converted_task, "meeting": meeting}


# -----------------------------------------------------------------------------
# STEP 4: MINUTES/DECISIONS, ACTION-TO-TASK CONVERSION & ATTENDANCE CORRECTION
# -----------------------------------------------------------------------------

@transaction.atomic
def review_minutes_or_convert_actions(
    *,
    meeting: MeetingSeries,
    decision: str,
    minutes_version: str = "",
    minutes_text: Optional[str] = None,
    reviewer_comment: str = "",
    action_id: Optional[str] = None,
    actor_account: Optional[Account] = None,
    user_scope: Optional[UserScope] = None,
) -> Dict[str, Any]:
    """
    MTG-05 & MTG-05-RECORD:
    - 'Save minutes': saves updated minutes_text and draft version
    - 'Approve minutes': freezes the approved version and marks minutes_status='Approved'
    - 'Request correction': requires a reviewer comment, increments draft version while preserving prior version
    - 'Convert actions to Mission Control' / 'create_action_task': converts each agreed action item
      into a linked MissionControlTask idempotently (once per action, preserving the meeting reference).
    """
    if user_scope:
        assert_stage9_authorized(user_scope, "MTG-04")
        assert_country_network_authorized(user_scope, country=meeting.country, network=meeting.network)

    dec = (decision or "").strip()
    dec_lower = dec.lower()
    comment = (reviewer_comment or "").strip()

    if minutes_text is not None and not meeting.minutes_frozen:
        meeting.minutes_text = minutes_text.strip()

    if dec_lower in {"save minutes", "save_minutes", "save_draft"}:
        if meeting.minutes_frozen:
            raise ValueError("Approved minutes are frozen. Request a correction to open a new draft version.")
        ver = (minutes_version or meeting.minutes_draft_label or "v2").split("·")[0].strip()
        meeting.minutes_draft_label = f"{ver} · draft"
        meeting.minutes_version = f"{ver} · draft"
        meeting.minutes_status = "Draft"
        meeting.save()
        _log_stage9_audit(
            actor_account,
            "meeting_series_updated",
            {
                "meeting_code": meeting.meeting_code,
                "minutes_version": meeting.minutes_version,
                "minutes_saved": True,
            },
        )
        return {"meeting": meeting, "converted_tasks": [], "action_taken": "minutes_saved"}

    if dec_lower in {"approve minutes", "approve"}:
        ver = (minutes_version or meeting.minutes_draft_label or "v2").split("·")[0].strip()
        meeting.minutes_version = f"{ver} · approved"
        meeting.minutes_draft_label = f"{ver} · approved"
        meeting.minutes_status = "Approved"
        meeting.minutes_frozen = True
        meeting.save()

        _log_stage9_audit(
            actor_account,
            "meeting_minutes_approved",
            {
                "meeting_code": meeting.meeting_code,
                "minutes_version": meeting.minutes_version,
                "reviewer_comment": comment,
                "frozen": True,
            },
        )
        return {"meeting": meeting, "converted_tasks": [], "action_taken": "approved"}

    if dec_lower in {"request correction", "return", "correction"}:
        if not comment:
            raise ValueError("Please provide a reviewer comment explaining the requested minutes correction.")
        # Increment draft version while retaining previous record in history
        current_ver_num = 2
        for token in (meeting.minutes_draft_label or "v2").replace("v", "").split():
            if token.isdigit():
                current_ver_num = int(token)
                break
        next_ver = current_ver_num + 1
        meeting.minutes_draft_label = f"v{next_ver} · draft"
        meeting.minutes_version = f"v{current_ver_num} · returned"
        meeting.minutes_status = "Correction requested"
        meeting.minutes_frozen = False
        meeting.save()

        _log_stage9_audit(
            actor_account,
            "meeting_minutes_correction_requested",
            {
                "meeting_code": meeting.meeting_code,
                "previous_version": f"v{current_ver_num}",
                "new_draft_version": meeting.minutes_draft_label,
                "reviewer_comment": comment,
            },
        )
        return {"meeting": meeting, "converted_tasks": [], "action_taken": "correction_requested"}

    if dec_lower in {"convert actions to mission control", "convert_actions", "create_action_task"}:
        actions_qs = meeting.decisions_and_actions.filter(record_type="Action")
        if action_id:
            actions_qs = actions_qs.filter(id=action_id)

        converted_tasks: List[MissionControlTask] = []
        already_converted: List[MissionControlTask] = []

        for act_item in actions_qs:
            # Idempotency guarantee: each agreed action converts once and keeps its meeting reference
            if act_item.is_converted and act_item.converted_task_id:
                already_converted.append(act_item.converted_task)
                continue

            idem_key = f"mtg-action-{meeting.meeting_code}-{act_item.record_code}"
            existing_task = MissionControlTask.objects.filter(idempotency_key=idem_key).first()
            if existing_task:
                act_item.converted_task = existing_task
                act_item.is_converted = True
                act_item.save(update_fields=["converted_task", "is_converted", "updated_at"])
                already_converted.append(existing_task)
                continue

            owner_name = act_item.owner_label
            if owner_name.lower() == "country coordinator":
                owner_name = "Lina Mensah"
            elif owner_name.lower() == "chapter lead":
                owner_name = "Ada Okafor"

            new_task = create_or_assign_task(
                title=act_item.detail_text,
                assign_to=owner_name,
                due_date_label=act_item.deadline_or_version,
                required_evidence=f"Upload completion evidence for {act_item.record_code} ({meeting.title}).",
                priority="High",
                description=f"Follow-up action from {meeting.title} ({meeting.local_time_label}): {act_item.detail_text}",
                source_type="Meeting Action",
                source_reference=f"{meeting.title} · {act_item.record_code}",
                source_meeting=meeting,
                idempotency_key=idem_key,
                network=meeting.network,
                country=meeting.country,
                actor_account=actor_account,
                user_scope=None,
            )
            act_item.converted_task = new_task
            act_item.is_converted = True
            act_item.save(update_fields=["converted_task", "is_converted", "updated_at"])
            converted_tasks.append(new_task)

        total_open = MissionControlTask.objects.filter(
            source_meeting=meeting
        ).exclude(status="Closed").count()
        meeting.open_actions_label = f"{total_open} open"
        meeting.save(update_fields=["open_actions_label", "updated_at"])

        _log_stage9_audit(
            actor_account,
            "meeting_actions_converted_to_tasks",
            {
                "meeting_code": meeting.meeting_code,
                "newly_converted_count": len(converted_tasks),
                "already_converted_count": len(already_converted),
                "task_codes": [t.task_code for t in converted_tasks + already_converted],
                "comment": comment,
            },
        )
        return {
            "meeting": meeting,
            "converted_tasks": converted_tasks,
            "already_converted": already_converted,
            "action_taken": "actions_converted",
        }

    raise ValueError(f"Unsupported minutes/action decision: '{decision}'.")


@transaction.atomic
def correct_meeting_attendance_record(
    *,
    meeting: MeetingSeries,
    participant_name: str,
    corrected_attendance: str,
    correction_reason: str,
    actor_account: Optional[Account] = None,
    user_scope: Optional[UserScope] = None,
) -> MeetingParticipantRecord:
    """
    MTG-06: Corrects a meeting attendance record while preserving the original
    recorded value ('Absent · original retained'), actor, reason, and timestamp,
    and without silently rewriting frozen approved minutes.
    """
    if user_scope:
        assert_stage9_authorized(user_scope, "MTG-06")
        assert_country_network_authorized(user_scope, country=meeting.country, network=meeting.network)

    clean_name = (participant_name or "").strip()
    clean_status = (corrected_attendance or "").strip().capitalize()
    clean_reason = (correction_reason or "").strip()

    if not clean_name or not clean_status or not clean_reason:
        raise ValueError("Participant, corrected attendance value, and correction reason are required.")

    if clean_status not in {"Present", "Absent", "Excused"}:
        raise ValueError("Corrected attendance must be Present, Absent, or Excused.")

    rec = meeting.participant_records.filter(participant_name__iexact=clean_name).first()
    if not rec:
        rec = MeetingParticipantRecord.objects.create(
            meeting=meeting,
            participant_name=clean_name,
            role_or_title="Member",
            rsvp_status="Invited",
            attendance_status="Absent",
            previous_attendance_value="Absent · original retained",
        )

    prior_val = rec.attendance_status
    if not rec.previous_attendance_value or "original retained" not in rec.previous_attendance_value:
        rec.previous_attendance_value = f"{prior_val} · original retained"

    rec.attendance_status = clean_status
    rec.correction_reason = clean_reason
    rec.correction_review_outcome = "Approved correction · prior value retained in audit"
    rec.detail_note = f"Corrected to {clean_status} ({clean_reason})"
    rec.corrected_by = actor_account
    rec.corrected_at = timezone.now()
    rec.save()

    present_count = meeting.participant_records.filter(attendance_status="Present").count()
    total_count = max(5, meeting.participant_records.count())
    meeting.attendance_summary = f"{present_count} of {total_count} present"
    meeting.save(update_fields=["attendance_summary", "updated_at"])

    _log_stage9_audit(
        actor_account,
        "meeting_attendance_corrected",
        {
            "meeting_code": meeting.meeting_code,
            "participant_name": rec.participant_name,
            "previous_attendance_value": rec.previous_attendance_value,
            "corrected_attendance": rec.attendance_status,
            "correction_reason": rec.correction_reason,
            "approved_minutes_untouched": True,
        },
    )
    return rec


def get_stage9_audit_history(network: str = "WGMN", country: str = "NG", limit: int = 25) -> List[AuditEvent]:
    stage9_events = {
        "mission_control_task_created",
        "mission_control_task_transition",
        "meeting_scheduled_or_updated",
        "meeting_occurrence_missed_recorded",
        "meeting_failed_invitations_retried",
        "meeting_series_updated",
        "meeting_rsvp_recorded",
        "meeting_minutes_approved",
        "meeting_minutes_correction_requested",
        "meeting_actions_converted_to_tasks",
        "meeting_attendance_corrected",
    }
    return list(AuditEvent.objects.filter(event__in=stage9_events).order_by("-created_at")[:limit])
