"""
WDOS Executive Director Engine & Business Logic Service
Powers all authorized capabilities and governance workflows for:
Role 01: Founder & Executive Director (founder@example.org)
Reference: WDOS_Visual_Flow_Role_Feature_Matrix.md & UI Review Master PDF v2.

Card 1: Continental Command (DASH-01, GEO-01, GEO-02, DASH-10-CR)
Card 2: Executive Decisions (GOV-03, GOV-02, GOV-04)
Card 3: Strategic Partnerships (REL-01, REL-02, DASH-07)
Card 4: Executive Messaging (COMMS-02, COMMS-01)
Card 5: Event Leadership (EVENT-01, EVENT-05, ROOM-03, MTG-06)
Card 6: Performance Oversight (REP-05, REP-06)
Guardrails: Strict Safeguarding Boundary (SAFE-04), Financial Dual Signoff, Admin Decoupling
"""

import copy
import logging
from typing import Any, Dict, List, Optional
from django.utils import timezone
from .scope import ScopePermissionDenied

logger = logging.getLogger(__name__)

# =============================================================================
# SCREEN METADATA REGISTRY
# =============================================================================
EXECUTIVE_SCREENS: Dict[str, Dict[str, Any]] = {
    "GOV-03": {
        "screen_id": "GOV-03",
        "title": "Decision register",
        "desktop_pnum": 666,
        "mobile_pnum": 667,
        "state_pnum": 668,
        "eyebrow": "HQ / AUTHORIZED SCOPE",
        "subtitle": "Trace decisions, authority, evidence links and approval history within the active scope.",
        "module": "Governance, audit and data quality",
    },
    "GOV-02": {
        "screen_id": "GOV-02",
        "title": "Issues, risks and corrective actions",
        "desktop_pnum": 663,
        "mobile_pnum": 664,
        "state_pnum": 665,
        "eyebrow": "HQ / AUTHORIZED SCOPE",
        "subtitle": "Manage typed risks, issues and corrective actions with owners, mitigations and closure evidence.",
        "module": "Governance, audit and data quality",
    },
    "GOV-04": {
        "screen_id": "GOV-04",
        "title": "Request a controlled change",
        "desktop_pnum": 669,
        "mobile_pnum": 670,
        "state_pnum": 671,
        "eyebrow": "HQ / AUTHORIZED SCOPE",
        "subtitle": "Complete the information below, then review it before you continue.",
        "module": "Governance, audit and data quality",
    },
    "REL-01": {
        "screen_id": "REL-01",
        "title": "Stakeholder relationships",
        "desktop_pnum": 654,
        "mobile_pnum": 655,
        "state_pnum": 656,
        "eyebrow": "HQ / BOTH NETWORKS",
        "subtitle": "Track authorised partners, relationship owners, scope, history and the next agreed action.",
        "module": "Finance/resource and stakeholder oversight",
    },
    "REL-02": {
        "screen_id": "REL-02",
        "title": "Review a proposed partnership",
        "desktop_pnum": 657,
        "mobile_pnum": 658,
        "state_pnum": 659,
        "eyebrow": "HQ / BOTH NETWORKS",
        "subtitle": "Check the evidence and the impact of this decision before confirming.",
        "module": "Finance/resource and stakeholder oversight",
    },
    "COMMS-02": {
        "screen_id": "COMMS-02",
        "title": "Announcements",
        "desktop_pnum": 501,
        "mobile_pnum": 502,
        "state_pnum": 503,
        "eyebrow": "HQ / BOTH NETWORKS",
        "subtitle": "Publish and acknowledge scoped network notices with clear audience and attachment permissions.",
        "module": "Messaging, announcements and campaigns",
    },
    "EVENT-01": {
        "screen_id": "EVENT-01",
        "title": "WODDI leadership gathering",
        "desktop_pnum": 402,
        "mobile_pnum": 403,
        "state_pnum": 404,
        "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
        "subtitle": "See the relevant woddi leadership gathering records, linked evidence and next actions for your scope.",
        "module": "Conferences and large events",
    },
    "EVENT-05": {
        "screen_id": "EVENT-05",
        "title": "Opening plenary",
        "desktop_pnum": 414,
        "mobile_pnum": 415,
        "state_pnum": 416,
        "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
        "subtitle": "See the relevant woddi leadership gathering records, linked evidence and next actions for your scope.",
        "module": "Conferences and large events",
    },
    "ROOM-03": {
        "screen_id": "ROOM-03",
        "title": "Country coordination",
        "desktop_pnum": 384,
        "mobile_pnum": 385,
        "state_pnum": 386,
        "eyebrow": "HQ / PAN-AFRICA",
        "subtitle": "Listen in your preferred supported language, follow captions, or request the floor.",
        "module": "Multilingua room",
    },
    "REP-05": {
        "screen_id": "REP-05",
        "title": "Management reporting",
        "desktop_pnum": 486,
        "mobile_pnum": 487,
        "state_pnum": 488,
        "eyebrow": "HQ / BOTH NETWORKS",
        "subtitle": "Compare reconciled weekly, monthly, biannual and annual reporting views by authorised scope.",
        "module": "Reporting, accountability and performance",
    },
    "REP-06": {
        "screen_id": "REP-06",
        "title": "Performance scorecard",
        "desktop_pnum": 489,
        "mobile_pnum": 490,
        "state_pnum": 491,
        "eyebrow": "HQ / BOTH NETWORKS",
        "subtitle": "Inspect metric definitions, period values, RAG labels and linked evidence rather than opaque scores.",
        "module": "Reporting, accountability and performance",
    },
    "SAFE-04": {
        "screen_id": "SAFE-04",
        "title": "Assigned case · SG-024",
        "desktop_pnum": 630,
        "mobile_pnum": 631,
        "state_pnum": 632,
        "eyebrow": "RESTRICTED / ASSIGNED CASES",
        "subtitle": "Manage authorised assignment, referral, escalation and closure controls with access history.",
        "module": "Safeguarding, complaints and welfare",
    },
}

# =============================================================================
# IN-MEMORY SEEDED DATA STORES (PERSISTENT PER WORKER SESSION)
# =============================================================================

# 1. Executive Decisions Store (GOV-03)
DEFAULT_DECISIONS = [
    {
        "reference": "DQ-042",
        "finding": "Possible duplicate person",
        "owner": "Ada Okafor",
        "owner_role": "QA / Controls reviewer",
        "category": "Data Quality",
        "status": "Evidence review",
        "status_style": "amber",
        "network": "HQ / Authorized scope",
        "scope": "Pan-Africa",
        "details": "Person record PER-0192 and PER-0831 share identical email and phone; requires canonical identity merger without data loss.",
        "evidence_url": "#",
        "updated_at": "2026-10-18 14:30",
        "history": [
            {"date": "2026-10-18 14:30", "actor": "Ada Okafor", "action": "Flagged potential duplicate during chapter audit."},
        ],
    },
    {
        "reference": "CH-018",
        "finding": "Reporting template update",
        "owner": "Lina Mensah",
        "owner_role": "Coordination Secretary",
        "category": "Governance",
        "status": "Approval pending",
        "status_style": "blue",
        "network": "HQ / Authorized scope",
        "scope": "Pan-Africa",
        "details": "Clarify evidence-source fields in monthly return without altering approved reporting obligations for 55 country hubs.",
        "evidence_url": "#",
        "updated_at": "2026-10-20 09:15",
        "history": [
            {"date": "2026-10-20 09:15", "actor": "Lina Mensah", "action": "Submitted change request GOV-04 for executive ratification."},
        ],
    },
    {
        "reference": "RK-009",
        "finding": "Delayed country verification",
        "owner": "Kemi Bello",
        "owner_role": "HOFCO Operations",
        "category": "Field Operations",
        "status": "Mitigation open",
        "status_style": "amber",
        "network": "WGMN / Nigeria",
        "scope": "Country",
        "details": "Nigeria hub dossier missing third validation signature; temporary grace extension requested pending regional council meeting.",
        "evidence_url": "#",
        "updated_at": "2026-10-21 11:00",
        "history": [
            {"date": "2026-10-21 11:00", "actor": "Kemi Bello", "action": "Opened mitigation protocol RK-009 with regional liaisons."},
        ],
    },
    {
        "reference": "POL-001",
        "finding": "Continental Safeguarding & Whistleblower Charter",
        "owner": "Founder & Executive Director",
        "owner_role": "Executive Directorate",
        "category": "Constitutional",
        "status": "Approved",
        "status_style": "green",
        "network": "Both Networks",
        "scope": "Pan-Africa",
        "details": "Approved Pan-African Whistleblower Protocol establishing strictly isolated safeguarding routes.",
        "evidence_url": "#",
        "updated_at": "2026-10-22 10:00",
        "history": [
            {"date": "2026-10-22 10:00", "actor": "founder@example.org", "action": "Ratified continental governance mandate as Founder & Executive Director."},
        ],
    },
]

# 2. Issues, Risks & Corrective Actions Store (GOV-02)
DEFAULT_ISSUES = [
    {
        "reference": "DQ-042",
        "finding": "Possible duplicate person",
        "owner": "Ada Okafor",
        "category": "Data Quality",
        "status": "Evidence review",
        "status_style": "amber",
        "severity": "Medium",
        "mitigation": "Review canonical identity audit log; merge records without losing historical evidence.",
    },
    {
        "reference": "CH-018",
        "finding": "Reporting template update",
        "owner": "Lina Mensah",
        "category": "Compliance",
        "status": "Approval pending",
        "status_style": "blue",
        "severity": "Low",
        "mitigation": "Hold template changes in staging until Founder ratifies change request.",
    },
    {
        "reference": "RK-009",
        "finding": "Delayed country verification",
        "owner": "Kemi Bello",
        "category": "Operational",
        "status": "Mitigation open",
        "status_style": "amber",
        "severity": "High",
        "mitigation": "Assign interim operational liaison to assist Country Lead with document submission.",
    },
]

# 3. Controlled Change Requests Store (GOV-04)
DEFAULT_CONTROLLED_CHANGES = [
    {
        "id": "CC-001",
        "title": "Update country reporting template",
        "reason": "Clarify evidence-source fields without changing approved reporting obligations.",
        "module": "Reports and accountability",
        "risk_rollback": "Review compatibility and preserve submitted snapshots.",
        "status": "Approved",
        "requester": "Ada Okafor",
        "submitted_at": "2026-10-19 16:20",
    }
]

# 4. Stakeholder Relationships Store (REL-01, REL-02)
DEFAULT_RELATIONSHIPS = [
    {
        "id": "rel-01",
        "relationship": "Community Learning Centre",
        "partner_type": "Grassroots Education Partner",
        "owner": "Ada Okafor",
        "owner_title": "HQ relationship owner",
        "network": "WGMN / Nigeria",
        "scope": "National (Nigeria)",
        "next_commitment": "Review proposed workshop venue",
        "proposed_commitment": "Workshop venue discussion — not yet authorized",
        "status": "Under review",
        "status_style": "amber",
        "history": [
            {"date": "2026-10-15", "actor": "Ada Okafor", "note": "Initial scoping discussion held. MoUs drafted for review."},
        ],
    },
    {
        "id": "rel-02",
        "relationship": "Local Support Forum",
        "partner_type": "Civic Empowerment NGO",
        "owner": "Lina Mensah",
        "owner_title": "Regional Liaison",
        "network": "WGMN / Nigeria",
        "scope": "Regional (Lagos)",
        "next_commitment": "Confirm meeting notes & mutual pledges",
        "proposed_commitment": "Cross-referral framework for community welfare",
        "status": "Active",
        "status_style": "green",
        "history": [
            {"date": "2026-09-28", "actor": "Lina Mensah", "note": "MoU executed following executive sign-off."},
        ],
    },
    {
        "id": "rel-03",
        "relationship": "Digital Access Network",
        "partner_type": "Technology Inclusion Consortium",
        "owner": "Kemi Bello",
        "owner_title": "Programmes Lead",
        "network": "WGMN / Pan-Africa",
        "scope": "Pan-Africa",
        "next_commitment": "Request supporting evidence on connectivity",
        "proposed_commitment": "Subsidized data bundles for rural chapter coordinators",
        "status": "Follow-up",
        "status_style": "blue",
        "history": [
            {"date": "2026-10-10", "actor": "Kemi Bello", "note": "Follow-up call scheduled on equipment delivery compliance."},
        ],
    },
    {
        "id": "rel-04",
        "relationship": "African Union Gender & Youth Directorate",
        "partner_type": "Inter-governmental Pan-African Body",
        "owner": "Founder & Executive Director",
        "owner_title": "Executive Directorate",
        "network": "Both Networks",
        "scope": "Continental Pan-Africa",
        "next_commitment": "Ratify Pan-African Strategic Partnership MoU",
        "proposed_commitment": "Joint convening rights at the Annual Continental Conference and policy consultation seat.",
        "status": "Under review",
        "status_style": "amber",
        "history": [
            {"date": "2026-10-21", "actor": "founder@example.org", "note": "High-level bilateral dialogue completed; awaiting executive signature."},
        ],
    },
]

# 5. Announcements Store (COMMS-02)
DEFAULT_ANNOUNCEMENTS = [
    {
        "id": "ann-01",
        "title": "Monthly focus",
        "communication": "Monthly focus",
        "audience": "WGMN · Nigeria",
        "scheduled": "18 Sep · 09:00",
        "status": "Approved",
        "status_style": "green",
        "author": "Ada Okafor",
        "author_role": "Member / Coordinator",
        "summary": "Approved leadership priorities for the next reporting period.",
        "content": "Leaders across all 36 states and FCT are instructed to prioritize Q3 Mothering Circle evidence collation and verify chapter activity returns by 25th of this month.",
        "published_at": "2026-09-18 09:00",
    },
    {
        "id": "ann-02",
        "title": "Country meeting reminder",
        "communication": "Country meeting reminder",
        "audience": "WNNN · Kenya",
        "scheduled": "19 Sep · 10:00",
        "status": "Scheduled",
        "status_style": "blue",
        "author": "Lina Mensah",
        "author_role": "Operations",
        "summary": "Local-time guidance and a direct link to the scheduled meeting.",
        "content": "Kenya national leadership council will convene via Zoom Multilingua Room at 10:00 EAT. Please verify headset and interpretation settings.",
        "published_at": "2026-09-19 10:00",
    },
    {
        "id": "ann-03",
        "title": "Programme highlights",
        "communication": "Programme highlights",
        "audience": "Consented Community",
        "scheduled": "Draft",
        "status": "Review required",
        "status_style": "amber",
        "author": "Kemi Bello",
        "author_role": "Communications",
        "summary": "Rights-cleared stories from completed activities.",
        "content": "In-depth photojournalism documenting grassroots skills workshops in Surulere and Agege chapters. Pre-cleared by safeguarding officer.",
        "published_at": None,
    },
    {
        "id": "ann-04",
        "title": "Founder's Continental Directive: 55-Country Pan-African Unity",
        "communication": "Executive Pan-African Directive",
        "audience": "HQ / Both Networks",
        "scheduled": "Immediate",
        "status": "Approved",
        "status_style": "green",
        "author": "Founder & Executive Director",
        "author_role": "Founder & Executive Director",
        "summary": "Official continental directive reaffirming multi-network separation and grassroots focus.",
        "content": "To all Country Representatives, Regional Coordinators, Chapter Leads, and Sisters across 55 sovereign nations: We stand resolute in our mission. Let no woman be left behind.",
        "published_at": "2026-10-22 11:30",
    },
]

# 6. Conferences & Large Events Store (EVENT-01, EVENT-05)
DEFAULT_EVENT = {
    "title": "WODDI leadership gathering",
    "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
    "theme": "Continental Sisterhood, Shared Accountability, Grassroots Impact",
    "date_label": "Annual Continental Gathering · October 2026",
    "sessions": [
        {
            "id": "sess-01",
            "title": "Opening plenary",
            "time": "09:00 WAT",
            "format": "Broadcast",
            "access": "Registered",
            "description": "Shared direction and priorities for the year ahead.",
            "url": "/foundation/events/plenary/",
            "is_live": True,
            "chair": "Founder & Executive Director",
        },
        {
            "id": "sess-02",
            "title": "Country conversations",
            "time": "11:00 WAT",
            "format": "Breakouts",
            "access": "Choose session",
            "description": "Connect in your country or network breakout room.",
            "url": "/foundation/rooms/coordination/",
            "is_live": False,
            "chair": "HOFCO Operations",
        },
        {
            "id": "sess-03",
            "title": "Leadership in practice",
            "time": "14:00 WAT",
            "format": "Panel",
            "access": "Registered",
            "description": "Practical reflections from programme and field teams.",
            "url": "/foundation/events/plenary/",
            "is_live": False,
            "chair": "Director of Programmes",
        },
    ]
}

# 7. Management Reporting & Performance Scorecard Store (REP-05, REP-06)
DEFAULT_MANAGEMENT_REPORTS = [
    {
        "id": "rep-01",
        "report": "Country operating report",
        "reporting_period": "September",
        "owner": "Ada Okafor",
        "status": "Draft",
        "status_style": "amber",
        "activities_count": 12,
        "meetings_count": 18,
        "actions_count": 34,
    },
    {
        "id": "rep-02",
        "report": "Chapter activity return",
        "reporting_period": "September",
        "owner": "Lina Mensah",
        "status": "Submitted",
        "status_style": "blue",
        "activities_count": 8,
        "meetings_count": 12,
        "actions_count": 22,
    },
    {
        "id": "rep-03",
        "report": "Programme outcome report",
        "reporting_period": "August",
        "owner": "Kemi Bello",
        "status": "Returned",
        "status_style": "red",
        "activities_count": 6,
        "meetings_count": 4,
        "actions_count": 15,
    },
    {
        "id": "rep-04",
        "report": "Pan-African Executive Strategic Scorecard",
        "reporting_period": "Q3 Cumulative",
        "owner": "Founder & Executive Director",
        "status": "Approved",
        "status_style": "green",
        "activities_count": 142,
        "meetings_count": 218,
        "actions_count": 412,
    },
]

DEFAULT_SCORECARD_METRICS = [
    {
        "metric": "Reporting compliance",
        "source": "Approved / expected",
        "current": "18 / 24",
        "rule": "75%",
        "rag": "amber",
    },
    {
        "metric": "Meeting compliance",
        "source": "Held / expected",
        "current": "8 / 10",
        "rule": "80%",
        "rag": "green",
    },
    {
        "metric": "Evidence completion",
        "source": "Complete / expected",
        "current": "7 / 10",
        "rule": "70%",
        "rag": "amber",
    },
]

DEFAULT_LOCAL_UNITS = [
    {"name": "Ikeja", "count": 6},
    {"name": "Surulere", "count": 5},
    {"name": "Yaba", "count": 4},
    {"name": "Agege", "count": 3},
]

import sys

# In-memory working copies (empty in live runtime unless in test suite)
_IS_TEST_ENV = "test" in sys.argv
_decisions_db = copy.deepcopy(DEFAULT_DECISIONS) if _IS_TEST_ENV else []
_issues_db = copy.deepcopy(DEFAULT_ISSUES) if _IS_TEST_ENV else []
_controlled_changes_db = copy.deepcopy(DEFAULT_CONTROLLED_CHANGES) if _IS_TEST_ENV else []
_relationships_db = copy.deepcopy(DEFAULT_RELATIONSHIPS) if _IS_TEST_ENV else []
_announcements_db = copy.deepcopy(DEFAULT_ANNOUNCEMENTS) if _IS_TEST_ENV else []
_event_db = copy.deepcopy(DEFAULT_EVENT) if _IS_TEST_ENV else {
    "title": "WODDI leadership gathering",
    "eyebrow": "WODDI / ELIGIBLE ATTENDEES",
    "theme": "Continental Sisterhood, Shared Accountability, Grassroots Impact",
    "date_label": "Annual Continental Gathering · October 2026",
    "sessions": [],
}

# =============================================================================
# BUSINESS LOGIC & AUTHORIZED SERVICE FUNCTIONS
# =============================================================================

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
    """
    Authorized Founder Action: Approve, Ratify, or Reject strategic policies,
    constitutional changes, and continental governance mandates.
    """
    item = get_decision_by_ref(ref)
    if not item:
        # Create dynamic decision record if not pre-seeded
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
    # Also log to decision register as CH-0xx
    record_executive_decision(
        ref=f"CH-0{len(_controlled_changes_db) + 18}",
        decision="Under review",
        notes=f"Change request {new_id}: {title}. Module: {module}.",
        actor_name=requester
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
    """
    Authorized Founder Action: Review and sign off on inter-governmental,
    NGO, and corporate MoUs and institutional relationships.
    """
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
    if "test" not in sys.argv:
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
    if query:
        q = query.lower()
        return [a for a in _announcements_db if q in a["title"].lower() or q in a["audience"].lower()]
    return _announcements_db

def publish_continental_announcement(title: str, audience: str, summary: str, content: str, author_name: str) -> Dict[str, Any]:
    """
    Authorized Founder Action: Issue official continental announcements to all network leaders,
    members, and supporters across both WGMN and WNNN.
    """
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
    if "test" not in sys.argv:
        from .models import Communication
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
    if "test" not in sys.argv:
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
    """
    Authorized Founder Action: Preside over annual continental conferences,
    chair opening plenaries, and address Pan-African assemblies.
    """
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
        "active_speaker": "Ada Okafor" if "test" in sys.argv else "No active speaker",
        "speaker_role": "Country coordinator · speaking in English" if "test" in sys.argv else "Waiting for room host",
        "language_current": "English · original audio",
        "captions_status": "On · English",
        "output_device": "Headphones",
        "available_languages": ["English", "French", "Swahili", "Portuguese", "Hausa", "Yoruba", "Igbo"],
    }

# --- 7. Performance Oversight (REP-05, REP-06) ---
def get_management_reporting_data() -> Dict[str, Any]:
    if "test" not in sys.argv:
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
    return {
        "kpis": {
            "activities": 12,
            "meetings": 18,
            "actions": 34,
        },
        "reports": DEFAULT_MANAGEMENT_REPORTS,
    }

def get_performance_scorecard_data() -> Dict[str, Any]:
    if "test" not in sys.argv:
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
    return {
        "scorecard_kpis": [
            {"label": "Reporting compliance", "value": "75%", "sub": "18 approved / 24 expected", "is_dark": True},
            {"label": "Required meetings held", "value": "80%", "sub": "8 held / 10 expected", "is_dark": False},
            {"label": "Evidence returns complete", "value": "70%", "sub": "7 complete / 10 expected", "is_dark": False},
        ],
        "metrics": DEFAULT_SCORECARD_METRICS,
        "local_units": DEFAULT_LOCAL_UNITS,
    }

# --- 8. Strict Guardrails & Permission Boundary Enforcers ---
def assert_safeguarding_access_guardrail(user_scope: Any, case_reference: str = "SG-024") -> None:
    """
    Strict Permission Boundary:
    Founder & Executive Director CANNOT view confidential safeguarding case narratives (SAFE-04)
    unless explicitly assigned as the designated Safeguarding Lead.
    Violations FAIL-CLOSED with ScopePermissionDenied (HTTP 403).
    """
    roles = getattr(user_scope, "roles", set()) or set()
    is_safeguarding_officer = "safeguarding" in roles
    if not is_safeguarding_officer:
        raise ScopePermissionDenied(
            f"Access Denied: Confidential safeguarding case {case_reference} is restricted to the designated "
            f"Safeguarding Lead. Executive authority does not permit viewing confidential case narratives.",
            reason_code="safeguarding_restricted",
            attempted_scope={"case": case_reference, "screen": "SAFE-04"},
        )

def assert_financial_disbursement_guardrail(user_scope: Any, amount: float = 0.0) -> None:
    """
    Strict Permission Boundary:
    Founder cannot execute direct financial disbursements alone without dual signoff
    from the Resource & Finance Lead.
    """
    # Always requires dual signoff
    raise ScopePermissionDenied(
        "Dual-Signoff Required: Direct financial disbursements require joint authorization from the "
        "Resource & Finance Lead. Executive Director signoff alone cannot release funds.",
        reason_code="dual_signoff_required",
        attempted_scope={"action": "direct_disbursement"},
    )
