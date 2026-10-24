"""
WDOS Executive Director Engine & Business Logic Service
Powers all authorized capabilities and governance workflows for:
Role 01: Founder & Executive Director (founder@example.org)
Reference: WDOS_Visual_Flow_Role_Feature_Matrix.md & UI Review Master PDF v2.
"""

import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone
from .scope import ScopePermissionDenied

logger = logging.getLogger(__name__)


def _exec_screen(screen_id: str, title: str, pnum: int, eyebrow: str, subtitle: str, module: str) -> Dict[str, Any]:
    return {
        "screen_id": screen_id,
        "title": title,
        "desktop_pnum": pnum,
        "mobile_pnum": pnum + 1,
        "state_pnum": pnum + 2,
        "eyebrow": eyebrow,
        "subtitle": subtitle,
        "module": module,
    }


EXECUTIVE_SCREENS: Dict[str, Dict[str, Any]] = {
    "GOV-03": _exec_screen(
        "GOV-03", "Decision register", 666, "HQ / AUTHORIZED SCOPE",
        "Trace decisions, authority, evidence links and approval history within the active scope.",
        "Governance, audit and data quality",
    ),
    "GOV-02": _exec_screen(
        "GOV-02", "Issues, risks and corrective actions", 663, "HQ / AUTHORIZED SCOPE",
        "Manage typed risks, issues and corrective actions with owners, mitigations and closure evidence.",
        "Governance, audit and data quality",
    ),
    "GOV-04": _exec_screen(
        "GOV-04", "Request a controlled change", 669, "HQ / AUTHORIZED SCOPE",
        "Complete the information below, then review it before you continue.",
        "Governance, audit and data quality",
    ),
    "REL-01": _exec_screen(
        "REL-01", "Stakeholder relationships", 654, "HQ / BOTH NETWORKS",
        "Track authorised partners, relationship owners, scope, history and the next agreed action.",
        "Finance/resource and stakeholder oversight",
    ),
    "REL-02": _exec_screen(
        "REL-02", "Review a proposed partnership", 657, "HQ / BOTH NETWORKS",
        "Check the evidence and the impact of this decision before confirming.",
        "Finance/resource and stakeholder oversight",
    ),
    "COMMS-02": _exec_screen(
        "COMMS-02", "Announcements", 501, "HQ / BOTH NETWORKS",
        "Publish and acknowledge scoped network notices with clear audience and attachment permissions.",
        "Messaging, announcements and campaigns",
    ),
    "EVENT-01": _exec_screen(
        "EVENT-01", "WODDI leadership gathering", 402, "WODDI / ELIGIBLE ATTENDEES",
        "See the relevant woddi leadership gathering records, linked evidence and next actions for your scope.",
        "Conferences and large events",
    ),
    "EVENT-05": _exec_screen(
        "EVENT-05", "Opening plenary", 414, "WODDI / ELIGIBLE ATTENDEES",
        "See the relevant woddi leadership gathering records, linked evidence and next actions for your scope.",
        "Conferences and large events",
    ),
    "ROOM-03": _exec_screen(
        "ROOM-03", "Country coordination", 384, "HQ / PAN-AFRICA",
        "Listen in your preferred supported language, follow captions, or request the floor.",
        "Multilingua room",
    ),
    "REP-05": _exec_screen(
        "REP-05", "Management reporting", 486, "HQ / BOTH NETWORKS",
        "Compare reconciled weekly, monthly, biannual and annual reporting views by authorised scope.",
        "Reporting, accountability and performance",
    ),
    "REP-06": _exec_screen(
        "REP-06", "Performance scorecard", 489, "HQ / BOTH NETWORKS",
        "Inspect metric definitions, period values, RAG labels and linked evidence rather than opaque scores.",
        "Reporting, accountability and performance",
    ),
    "SAFE-04": _exec_screen(
        "SAFE-04", "Assigned case · SG-024", 630, "RESTRICTED / ASSIGNED CASES",
        "Manage authorised assignment, referral, escalation and closure controls with access history.",
        "Safeguarding, complaints and welfare",
    ),
}

_decisions_db: List[Dict[str, Any]] = []
_issues_db: List[Dict[str, Any]] = []
_controlled_changes_db: List[Dict[str, Any]] = []
_relationships_db: List[Dict[str, Any]] = []
_announcements_db: List[Dict[str, Any]] = []
_event_db: Dict[str, Any] = {
    "title": "WODDI leadership gathering",
    "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
    "theme": "Continental Sisterhood, Shared Accountability, Grassroots Impact",
    "date_label": "Annual Continental Gathering",
    "sessions": [],
}


# --- 1. Executive Decisions (GOV-03) ---
def get_decisions(query: Optional[str] = None, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
    results = _decisions_db
    if status_filter and status_filter.lower() != "all":
        results = [d for d in results if d["status"].lower() == status_filter.lower()]
    if query:
        q = query.lower()
        results = [d for d in results if q in d["reference"].lower() or q in d["finding"].lower() or q in d["owner"].lower()]
    return results


def get_decision_by_ref(ref: str) -> Optional[Dict[str, Any]]:
    for d in _decisions_db:
        if d["reference"].upper() == ref.upper():
            return d
    return None


def record_executive_decision(ref: str, decision: str, notes: str, actor_name: str) -> Dict[str, Any]:
    item = get_decision_by_ref(ref)
    if not item:
        item = {
            "reference": ref.upper(),
            "finding": f"Executive Mandate {ref}",
            "owner": actor_name,
            "owner_role": "Executive Directorate",
            "category": "Governance",
            "status": "Under review",
            "status_style": "amber",
            "network": "HQ / Authorized scope",
            "scope": "Pan-Africa",
            "details": notes,
            "evidence_url": "#",
            "updated_at": timezone.now().strftime("%Y-%m-%d %H:%M"),
            "history": [],
        }
        _decisions_db.append(item)

    now_str = timezone.now().strftime("%Y-%m-%d %H:%M")
    decision_clean = decision.strip().lower()
    if "approve" in decision_clean or "ratif" in decision_clean:
        item["status"] = "Approved"
        item["status_style"] = "green"
        action_verb = "Approved and ratified"
    elif "reject" in decision_clean:
        item["status"] = "Rejected"
        item["status_style"] = "red"
        action_verb = "Formally rejected"
    else:
        item["status"] = "Under review"
        item["status_style"] = "amber"
        action_verb = "Marked for further evidence review"

    item["updated_at"] = now_str
    item["history"].insert(0, {
        "date": now_str,
        "actor": actor_name,
        "action": f"{action_verb} by Founder & Executive Director. Notes: {notes or 'No additional notes'}"
    })
    return item


# --- 2. Issues, Risks & Corrective Actions (GOV-02) ---
def get_issues_and_risks(query: Optional[str] = None) -> List[Dict[str, Any]]:
    if query:
        q = query.lower()
        return [i for i in _issues_db if q in i["reference"].lower() or q in i["finding"].lower() or q in i["owner"].lower()]
    return _issues_db


def record_new_issue(ref: str, finding: str, owner: str, category: str, severity: str, mitigation: str) -> Dict[str, Any]:
    new_item = {
        "reference": ref.upper(),
        "finding": finding,
        "owner": owner,
        "category": category,
        "status": "Mitigation open",
        "status_style": "amber",
        "severity": severity,
        "mitigation": mitigation,
    }
    _issues_db.insert(0, new_item)
    return new_item


# --- 3. Controlled Change Request (GOV-04) ---
def submit_controlled_change(title: str, reason: str, module: str, risk_and_rollback: str, requester: str) -> Dict[str, Any]:
    new_id = f"CC-00{len(_controlled_changes_db) + 1}"
    record = {
        "id": new_id,
        "title": title,
        "reason": reason,
        "module": module,
        "risk_rollback": risk_and_rollback,
        "status": "Submitted",
        "requester": requester,
        "submitted_at": timezone.now().strftime("%Y-%m-%d %H:%M"),
    }
    _controlled_changes_db.insert(0, record)
    record_executive_decision(
        ref=f"CH-0{len(_controlled_changes_db) + 18}",
        decision="Under review",
        notes=f"Change request {new_id}: {title}. Module: {module}.",
        actor_name=requester,
    )
    return record


# --- 4. Strategic Partnerships (REL-01, REL-02) ---
def get_relationships(query: Optional[str] = None) -> List[Dict[str, Any]]:
    if query:
        q = query.lower()
        return [r for r in _relationships_db if q in r["relationship"].lower() or q in r["owner"].lower()]
    return _relationships_db


def get_relationship_by_id(rel_id: str) -> Optional[Dict[str, Any]]:
    for r in _relationships_db:
        if r["id"] == rel_id:
            return r
    return None


def record_partnership_decision(rel_id: str, decision: str, notes: str, actor_name: str) -> Dict[str, Any]:
    rel = get_relationship_by_id(rel_id)
    if not rel:
        rel = {
            "id": rel_id or f"rel-0{len(_relationships_db) + 1}",
            "relationship": rel_id or "Proposed Strategic Partnership",
            "partner_type": "Strategic Partner",
            "owner": actor_name,
            "owner_title": "Executive Directorate",
            "network": "Both Networks",
            "scope": "Pan-Africa",
            "next_commitment": "Review MoU",
            "proposed_commitment": notes or "Partnership review",
            "status": "Under review",
            "status_style": "amber",
            "history": [],
        }
        _relationships_db.append(rel)

    now_str = timezone.now().strftime("%Y-%m-%d %H:%M")
    decision_clean = decision.strip().lower()

    if "approve" in decision_clean or "ratif" in decision_clean or "sign" in decision_clean:
        rel["status"] = "Active"
        rel["status_style"] = "green"
        action_text = "Executive MoU signed and partnership ratified."
    elif "reject" in decision_clean:
        rel["status"] = "Rejected"
        rel["status_style"] = "red"
        action_text = "Partnership proposal rejected by Executive Director."
    else:
        rel["status"] = "Under review"
        rel["status_style"] = "amber"
        action_text = "Returned for further evidence and legal review."

    rel["history"].insert(0, {
        "date": now_str,
        "actor": actor_name,
        "note": f"{action_text} Notes: {notes or 'No additional notes.'}"
    })
    return rel


# --- 5. Executive Messaging & Announcements (COMMS-02) ---
def get_announcements(query: Optional[str] = None) -> List[Dict[str, Any]]:
    from .models import Communication
    comms = Communication.objects.all().order_by("-sent_at")
    items = list(_announcements_db)
    existing_titles = {a["title"].lower() for a in items}
    for c in comms:
        if c.subject.lower() not in existing_titles:
            items.append({
                "id": f"comm-{c.id}",
                "title": c.subject,
                "communication": c.subject,
                "audience": f"{c.network} · {c.country}",
                "scheduled": c.sent_at.strftime("%d %b · %H:%M") if c.sent_at else "Immediate",
                "status": "Approved",
                "status_style": "green",
                "author": c.sender_name or "Founder & Executive Director",
                "author_role": c.target_role or "Executive",
                "summary": c.body[:120],
                "content": c.body,
                "published_at": c.sent_at.strftime("%Y-%m-%d %H:%M") if c.sent_at else "",
            })
    if query:
        q = query.lower()
        return [a for a in items if q in a["title"].lower() or q in a["audience"].lower()]
    return items


def publish_continental_announcement(title: str, audience: str, summary: str, content: str, author_name: str) -> Dict[str, Any]:
    from .models import Communication
    new_id = f"ann-0{len(_announcements_db) + 1}"
    record = {
        "id": new_id,
        "title": title,
        "communication": title,
        "audience": audience,
        "scheduled": "Immediate",
        "status": "Approved",
        "status_style": "green",
        "author": author_name,
        "author_role": "Founder & Executive Director",
        "summary": summary,
        "content": content,
        "published_at": timezone.now().strftime("%Y-%m-%d %H:%M"),
    }
    _announcements_db.insert(0, record)
    net_val = "WGMN" if "WGMN" in audience.upper() and "BOTH" not in audience.upper() else ("WNNN" if "WNNN" in audience.upper() else "ALL")
    Communication.objects.create(
        subject=title,
        body=content or summary,
        network=net_val,
        country="ALL",
        target_role="all",
        sender_name=author_name,
        priority="high",
    )
    return record


# --- 6. Event Leadership (EVENT-01, EVENT-05, ROOM-03) ---
def get_event_leadership_data() -> Dict[str, Any]:
    from .models import ConferenceEvent
    ce = ConferenceEvent.objects.first()
    if ce:
        return {
            "title": ce.title,
            "eyebrow": ce.eyebrow,
            "theme": ce.subtitle,
            "date_label": ce.date_and_timezone,
            "sessions": [
                {
                    "id": str(s.id),
                    "title": s.title,
                    "time": s.local_time_label,
                    "format": s.format_label,
                    "access": s.access_status,
                    "description": s.description,
                    "url": "/foundation/events/plenary/" if s.is_plenary else "/foundation/rooms/coordination/",
                    "is_live": s.is_plenary,
                    "chair": "Founder & Executive Director",
                }
                for s in ce.sessions.order_by("sort_order")
            ],
        }
    return _event_db


def chair_opening_plenary(action: str, notes: str, actor_name: str) -> Dict[str, Any]:
    return {
        "status": "active",
        "session": "Opening plenary",
        "chaired_by": actor_name,
        "action": action,
        "notes": notes,
        "timestamp": timezone.now().strftime("%Y-%m-%d %H:%M"),
    }


def get_country_coordination_room() -> Dict[str, Any]:
    return {
        "room_title": "Country coordination",
        "eyebrow": "HQ / PAN-AFRICA",
        "active_speaker": "No active speaker",
        "speaker_role": "Waiting for room host",
        "language_current": "English · original audio",
        "captions_status": "On · English",
        "output_device": "Headphones",
        "available_languages": ["English", "French", "Swahili", "Portuguese", "Hausa", "Yoruba", "Igbo"],
    }


# --- 7. Performance Oversight (REP-05, REP-06) ---
def get_management_reporting_data() -> Dict[str, Any]:
    from .models import DashboardActivity, DashboardReport, MissionControlTask, ScheduledMeeting, WorkItem
    act_cnt = DashboardActivity.objects.count()
    mtg_cnt = ScheduledMeeting.objects.count()
    task_cnt = WorkItem.objects.count() + MissionControlTask.objects.count()
    reports = [
        {
            "id": f"rep-{r.id}",
            "report": r.title,
            "reporting_period": r.period or "Current",
            "owner": r.author_name or "HQ",
            "status": r.status.title() if r.status else "Draft",
            "status_style": "green" if r.status == "published" else "amber",
            "activities_count": act_cnt,
            "meetings_count": mtg_cnt,
            "actions_count": task_cnt,
        }
        for r in DashboardReport.objects.all().order_by("-created_at")
    ]
    return {
        "kpis": {
            "activities": act_cnt,
            "meetings": mtg_cnt,
            "actions": task_cnt,
        },
        "reports": reports,
    }


def get_performance_scorecard_data() -> Dict[str, Any]:
    from .models import DashboardReport, LocalOrganisationUnit, ScheduledMeeting, WorkItem
    rep_total = DashboardReport.objects.count()
    rep_pub = DashboardReport.objects.filter(status="published").count()
    mtg_total = ScheduledMeeting.objects.count()
    wi_total = WorkItem.objects.count()
    wi_done = WorkItem.objects.filter(status="completed").count()
    rep_pct = f"{int((rep_pub / rep_total) * 100)}%" if rep_total else "0%"
    wi_pct = f"{int((wi_done / wi_total) * 100)}%" if wi_total else "0%"
    units = [
        {"name": u.name, "count": 0}
        for u in LocalOrganisationUnit.objects.all()[:10]
    ]
    return {
        "scorecard_kpis": [
            {"label": "Reporting compliance", "value": rep_pct, "sub": f"{rep_pub} approved / {rep_total} expected", "is_dark": True},
            {"label": "Required meetings held", "value": str(mtg_total), "sub": f"{mtg_total} scheduled", "is_dark": False},
            {"label": "Evidence returns complete", "value": wi_pct, "sub": f"{wi_done} complete / {wi_total} expected", "is_dark": False},
        ],
        "metrics": [] if (rep_total == 0 and mtg_total == 0 and wi_total == 0) else [
            {"metric": "Reporting compliance", "source": "Approved / expected", "current": f"{rep_pub} / {rep_total}", "rule": rep_pct, "rag": "green" if rep_pub else "amber"},
            {"metric": "Evidence completion", "source": "Complete / expected", "current": f"{wi_done} / {wi_total}", "rule": wi_pct, "rag": "green" if wi_done else "amber"},
        ],
        "local_units": units,
    }


# --- 8. Strict Guardrails & Permission Boundary Enforcers ---
def assert_safeguarding_access_guardrail(user_scope: Any, case_reference: str = "SG-024") -> None:
    roles = getattr(user_scope, "roles", set()) or set()
    if "safeguarding" not in roles:
        raise ScopePermissionDenied(
            f"Access Denied: Confidential safeguarding case {case_reference} is restricted to the designated "
            f"Safeguarding Lead. Executive authority does not permit viewing confidential case narratives.",
            reason_code="safeguarding_restricted",
            attempted_scope={"case": case_reference, "screen": "SAFE-04"},
        )


def assert_financial_disbursement_guardrail(user_scope: Any, amount: float = 0.0) -> None:
    raise ScopePermissionDenied(
        "Dual-Signoff Required: Direct financial disbursements require joint authorization from the "
        "Resource & Finance Lead. Executive Director signoff alone cannot release funds.",
        reason_code="dual_signoff_required",
        attempted_scope={"action": "direct_disbursement"},
    )
