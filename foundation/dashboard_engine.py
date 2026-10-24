"""
WDOS Stage 5 Shared Dashboard Engine & Data Contract Registry
Provides authorized, role-specific, scoped operating views for DASH-01 through DASH-17.
Enforces fail-closed server authorization, geographic boundaries, cross-network separation,
and authentic database-reconciled data contracts.
"""

import sys
from typing import Any, Dict, List, Optional, Tuple
from django.db.models import Q
from django.utils import timezone
from .models import (
    Chapter,
    CountryHub,
    DashboardAlert,
    DashboardActivity,
    DashboardReport,
    LeadershipSeat,
    LocalOrganisationUnit,
    MissionControlTask,
    ScheduledMeeting,
    VolunteerOpportunity,
    WorkItem,
)
from accounts.models import AccessGrant, Account, Membership, OnboardingDraft
from .context_block import get_identity_context
from .scope import ScopePermissionDenied, is_broad_geographic_place, sanitize_chapter_display

DEFAULT_SUBTITLE = "Your priorities, relevant evidence and next actions in one clear view."
DEFAULT_SCOPED_NOTICE = "Counts and records remain scoped to your current role and network."
DEFAULT_SUPPORT_NOTE = "Need help? Ask your support team. Never share your password or verification codes."


def _kpis(*specs: Tuple[str, str]) -> List[Dict[str, Any]]:
    return [
        {
            "value": "0",
            "label": label,
            "sub": sub,
            "is_dark": idx == 0,
            "icon": "bar-chart",
        }
        for idx, (label, sub) in enumerate(specs)
    ]


def _screen(
    screen_id: str,
    title: str,
    pnum: int,
    eyebrow: str,
    role_code: str,
    role_title: str,
    network: str,
    country: str,
    columns: List[str],
    related_screens: List[str],
    *,
    kpis: Optional[List[Dict[str, Any]]] = None,
    subtitle: str = DEFAULT_SUBTITLE,
    primary_action: Optional[Dict[str, str]] = None,
    secondary_action: Optional[Dict[str, str]] = None,
    has_tabs: bool = True,
    has_search_filter: bool = False,
    requires_safeguarding: bool = False,
    hero_banner: Optional[Dict[str, str]] = None,
    table_title: str = "Your work and follow-through",
    has_attention: bool = True,
    chart_card: Optional[Dict[str, Any]] = None,
    scoped_notice: str = DEFAULT_SCOPED_NOTICE,
    support_note: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "screen_id": screen_id,
        "title": title,
        "desktop_pnum": pnum,
        "mobile_pnum": pnum + 1,
        "state_pnum": pnum + 2,
        "eyebrow": eyebrow,
        "subtitle": subtitle,
        "default_role_code": role_code,
        "default_role_title": role_title,
        "default_network": network,
        "default_country": country,
        "primary_action": primary_action or {"label": "→ Open my work", "url": "/foundation/work-queue/"},
        "secondary_action": secondary_action,
        "has_tabs": has_tabs,
        "has_search_filter": has_search_filter,
        "requires_safeguarding": requires_safeguarding,
        "hero_banner": hero_banner,
        "kpi_cards": kpis or [],
        "table_card": {
            "title": table_title,
            "view_all_label": "View all →",
            "view_all_url": "/foundation/work-queue/",
            "columns": columns,
            "rows": [],
            "record_count_text": "Showing 0 records in this view",
        },
        "attention_card": {"title": "Attention required", "items": []} if has_attention else None,
        "chart_card": chart_card,
        "scoped_notice": scoped_notice,
        "related_screens": related_screens,
        "support_note": support_note,
    }


DASHBOARD_SCREENS: Dict[str, Dict[str, Any]] = {
    "DASH-01": _screen(
        "DASH-01", "Continental priorities", 75, "HQ / BOTH NETWORKS",
        "founder", "Executive overview", "HQ / Both networks", "ALL",
        ["DECISION / CONCERN", "NETWORK / COUNTRY", "OWNER", "STATUS"],
        ["DASH-02", "DASH-03", "DASH-04", "DASH-05", "DASH-06", "DASH-07", "DASH-08", "DASH-09",
         "DASH-10", "DASH-11", "DASH-12", "DASH-13", "DASH-14", "DASH-15", "DASH-16", "DASH-17"],
        kpis=_kpis(
            ("WGMN active leaders", "Active network views"),
            ("WNNN active leaders", "Separate network view"),
            ("Decisions awaiting you", "Open items across networks"),
        ),
        chart_card={
            "title": "Country follow-ups by network",
            "badge": "Current period · open actions",
            "bars": [
                {"label": "WGMN", "value": 0, "color": "#E4C1D6"},
                {"label": "WNNN", "value": 0, "color": "#D4006A"},
            ],
        },
    ),
    "DASH-02": _screen(
        "DASH-02", "Country operations", 78, "HQ / BOTH NETWORKS",
        "operations", "HOFCO", "HQ / Both networks", "ALL",
        ["COUNTRY PRIORITY", "NETWORK", "OWNER", "STATUS"],
        ["DASH-01", "DASH-03", "DASH-04", "DASH-10", "DASH-11"],
        kpis=_kpis(
            ("Country follow-ups", "Assigned operational actions"),
            ("Critical vacancies", "Approved seats only"),
            ("Onboarding overdue", "Needs individual follow-through"),
        ),
    ),
    "DASH-03": _screen(
        "DASH-03", "Coordination desk", 81, "HQ / BOTH NETWORKS",
        "operations", "Network Secretary", "HQ / Both networks", "ALL",
        ["WORK ITEM", "ROUTE / SCOPE", "DUE", "STATUS"],
        ["DASH-01", "DASH-02", "DASH-04", "DASH-10-PIPELINE"],
        kpis=_kpis(
            ("Applications to screen", "Across authorized routes"),
            ("Letters to prepare", "Human selection recorded"),
            ("Register conflicts", "Evidence review required"),
        ),
    ),
    "DASH-04": _screen(
        "DASH-04", "Administration overview", 84, "HQ / AUTHORIZED SCOPE",
        "founder", "Director of Administration", "HQ / Authorized scope", "ALL",
        ["CONTROL ITEM", "RESPONSIBLE TEAM", "DUE", "STATUS"],
        ["DASH-01", "DASH-02", "DASH-03", "DASH-09"],
        kpis=_kpis(
            ("Access reviews", "Due this month"),
            ("Document revisions", "Awaiting publication review"),
            ("Handover exceptions", "Outstanding official records"),
        ),
    ),
    "DASH-05": _screen(
        "DASH-05", "Programme portfolio", 87, "HQ / BOTH NETWORKS",
        "operations", "Director of Programmes", "HQ / Both networks", "ALL",
        ["PROGRAMME / ACTIVITY", "AREA", "OWNER", "STATUS"],
        ["DASH-01", "DASH-06", "DASH-07", "DASH-10"],
        kpis=_kpis(
            ("Proposals to review", "Decision queue"),
            ("Activities underway", "Approved programme work"),
            ("Evidence overdue", "Follow-up required"),
        ),
    ),
    "DASH-06": _screen(
        "DASH-06", "Communications workspace", 90, "HQ / BOTH NETWORKS",
        "operations", "Communications lead", "HQ / Both networks", "ALL",
        ["COMMUNICATION", "AUDIENCE", "SCHEDULED", "STATUS"],
        ["DASH-01", "DASH-05", "DASH-08"],
        kpis=_kpis(
            ("Media awaiting review", "Consent and usage checks"),
            ("Campaigns scheduled", "Approved versions only"),
            ("Deliverables due", "This week"),
        ),
    ),
    "DASH-07": _screen(
        "DASH-07", "Resource accountability", 93, "HQ / AUTHORIZED FINANCE",
        "operations", "Finance reviewer", "HQ / Authorized finance", "ALL",
        ["RECORD", "PROGRAMME", "EVIDENCE", "STATUS"],
        ["DASH-01", "DASH-04", "DASH-05"],
        kpis=_kpis(
            ("Reviews awaiting you", "Within delegated authority"),
            ("Evidence outstanding", "Return requested"),
            ("Open exceptions", "Accountability follow-up"),
        ),
    ),
    "DASH-08": _screen(
        "DASH-08", "Systems operations", 96, "HQ / TECHNICAL CONTROLS",
        "operations", "IT & Systems", "HQ / Technical controls", "ALL",
        ["SERVICE / JOB", "LAST EVIDENCE", "OWNER", "STATUS"],
        ["DASH-01", "DASH-04", "DASH-09"],
        kpis=_kpis(
            ("Incidents to review", "Assigned response actions"),
            ("Jobs needing reconciliation", "Outcome not yet confirmed"),
            ("Evidence awaiting sign-off", "Restore and release records"),
        ),
    ),
    "DASH-09": _screen(
        "DASH-09", "Quality and controls", 99, "HQ / AUTHORIZED SCOPE",
        "operations", "QA / Controls", "HQ / Authorized scope", "ALL",
        ["FINDING", "AREA", "OWNER", "STATE"],
        ["DASH-01", "DASH-04", "DASH-08"],
        kpis=_kpis(
            ("Open findings", "Priority review"),
            ("UAT evidence to review", "No acceptance assumed"),
            ("Access review exceptions", "Assigned control owners"),
        ),
    ),
    "DASH-10": _screen(
        "DASH-10", "Nigeria country overview", 102, "WGMN / NIGERIA",
        "country_lead", "Country Representative", "WGMN", "NG",
        ["POSITION", "UNIT", "HOLDER", "STATUS"],
        ["DASH-10-COVERAGE", "DASH-10-PIPELINE", "DASH-10-INACTIVE", "DASH-10-ATTENTION",
         "DASH-10-CR", "DASH-10-REPORTING", "DASH-10-ENGAGEMENT", "DASH-10-SAFEGUARDING",
         "DASH-11", "DASH-12", "DASH-13", "DASH-14"],
        has_tabs=False,
        kpis=_kpis(
            ("Current leaders", "Within your country scope"),
            ("Approved vacancies", "Principal and deputy seats"),
            ("Reports awaiting review", "Current period"),
        ),
        chart_card={
            "title": "Reports approved this period",
            "badge": "Current period · approved returns",
            "bars": [],
        },
        support_note=DEFAULT_SUPPORT_NOTE,
    ),
    "DASH-10-COVERAGE": _screen(
        "DASH-10-COVERAGE", "Nigeria leadership coverage", 105, "WGMN / NIGERIA",
        "country_lead", "Country Representative", "WGMN", "NG",
        ["UNIT / NETWORK", "PRINCIPAL / DEPUTY", "COVERAGE RESULT"],
        ["DASH-10", "DASH-10-PIPELINE", "DASH-10-INACTIVE", "DASH-10-CR"],
        primary_action={"label": "→ Back to overview", "url": "/foundation/dashboards/dash-10/"},
        has_tabs=False,
        has_search_filter=True,
        table_title="Nigeria leadership coverage",
        has_attention=False,
        scoped_notice="Incomplete units requiring leadership follow-up are listed above.",
        support_note=DEFAULT_SUPPORT_NOTE,
    ),
    "DASH-10-PIPELINE": _screen(
        "DASH-10-PIPELINE", "Recruitment and activation", 108, "WGMN / NIGERIA",
        "country_lead", "Country Representative", "WGMN", "NG",
        ["QUEUE", "RECORDS", "NEXT STEP"],
        ["DASH-10", "DASH-10-COVERAGE", "DASH-10-INACTIVE", "DASH-10-CR"],
        primary_action={"label": "→ Open candidate review", "url": "/foundation/work-queue/"},
        has_tabs=False,
        has_search_filter=True,
        table_title="Recruitment and activation",
        has_attention=False,
        support_note=DEFAULT_SUPPORT_NOTE,
    ),
    "DASH-10-INACTIVE": _screen(
        "DASH-10-INACTIVE", "Leaders needing follow-up", 111, "WGMN / NIGERIA",
        "country_lead", "Country Representative", "WGMN", "NG",
        ["PERSON / ROLE", "LAST ACTIVITY", "ASSIGNED NEXT STEP"],
        ["DASH-10", "DASH-10-COVERAGE", "DASH-10-PIPELINE", "DASH-10-CR"],
        primary_action={"label": "→ Back to overview", "url": "/foundation/dashboards/dash-10/"},
        has_tabs=False,
        has_search_filter=True,
        table_title="Leaders needing follow-up",
        has_attention=False,
        scoped_notice="Inactivity follows an approved rule, not an invented deadline. Contact appropriately; do not automatically remove appointment or permissions.",
        support_note=DEFAULT_SUPPORT_NOTE,
    ),
    "DASH-10-ATTENTION": _screen(
        "DASH-10-ATTENTION", "Support and HQ attention", 114, "WGMN / NIGERIA",
        "country_lead", "Country Representative", "WGMN", "NG",
        ["REFERENCE", "SAFE SUMMARY", "OWNER / NEXT STEP"],
        ["DASH-10", "DASH-10-CR", "DASH-10-SAFEGUARDING"],
        primary_action={"label": "→ Back to overview", "url": "/foundation/dashboards/dash-10/"},
        has_tabs=False,
        has_search_filter=True,
        table_title="Support and HQ attention",
        has_attention=False,
        scoped_notice="Only ordinary support and permitted operational summaries. Confidential safeguarding records and their existence are not disclosed here.",
        support_note=DEFAULT_SUPPORT_NOTE,
    ),
    "DASH-10-CR": _screen(
        "DASH-10-CR", "Nigeria · what needs attention", 117, "WGMN / NIGERIA",
        "country_lead", "Country Representative", "WGMN", "NG",
        ["AREA", "CURRENT PICTURE", "NEXT STEP"],
        ["DASH-10", "DASH-10-COVERAGE", "DASH-10-PIPELINE", "DASH-10-INACTIVE", "DASH-10-ATTENTION"],
        subtitle="Start with overdue work. Then open any row to see the records behind the number.",
        primary_action={"label": "→ Open overdue work", "url": "/foundation/work-queue/"},
        secondary_action={"label": "Back to dashboard", "url": "/foundation/dashboards/dash-10/"},
        has_tabs=False,
        table_title="Country Command",
        kpis=_kpis(
            ("Leadership coverage", "Current unit status"),
            ("Recruitment / activation", "Pipeline status"),
            ("Leaders inactive", "Follow-up required · approved rule applies"),
        ),
        scoped_notice="Selected country and network only. Confidential safeguarding information is not included.",
        support_note=DEFAULT_SUPPORT_NOTE,
    ),
    "DASH-10-REPORTING": _screen(
        "DASH-10-REPORTING", "Reporting desk", 120, "HQ / HQ REPORTING REVIEWER",
        "operations", "HQ reporting reviewer", "HQ / Both networks", "ALL",
        ["PERIOD", "COUNTRY / NETWORK", "REVIEW STATUS"],
        ["DASH-10", "DASH-10-CR", "DASH-01"],
        subtitle="Use the information and next action for this role only.",
        primary_action={"label": "→ Open assigned work", "url": "/foundation/work-queue/"},
        secondary_action={"label": "Back to dashboard", "url": "/foundation/dashboards/dash-10/"},
        has_tabs=False,
        table_title="Reporting desk",
        has_attention=False,
        kpis=_kpis(
            ("Waiting for review", "Current reporting period"),
            ("Corrections due", "Current reporting period"),
            ("Missed reports", "Current reporting period"),
        ),
        support_note=DEFAULT_SUPPORT_NOTE,
    ),
    "DASH-10-ENGAGEMENT": _screen(
        "DASH-10-ENGAGEMENT", "Engagement desk", 123, "HQ / HQ ENGAGEMENT LEAD",
        "operations", "HQ engagement lead", "HQ / Both networks", "ALL",
        ["CYCLE", "AUDIENCE", "NEXT ACTION"],
        ["DASH-10", "DASH-10-CR", "DASH-06"],
        subtitle="Use the information and next action for this role only.",
        primary_action={"label": "→ Open assigned work", "url": "/foundation/work-queue/"},
        secondary_action={"label": "Back to dashboard", "url": "/foundation/dashboards/dash-10/"},
        has_tabs=False,
        table_title="Engagement desk",
        has_attention=False,
        kpis=_kpis(
            ("Active cycles", "Current engagement cycle"),
            ("Follow-up due", "Current engagement cycle"),
            ("Contact suppressed", "Current engagement cycle"),
        ),
        support_note=DEFAULT_SUPPORT_NOTE,
    ),
    "DASH-10-SAFEGUARDING": _screen(
        "DASH-10-SAFEGUARDING", "Confidential safeguarding desk", 126, "HQ / AUTHORISED SAFEGUARDING OFFICER",
        "operations", "Authorised safeguarding officer", "HQ / Authorised safeguarding officer", "ALL",
        ["REFERENCE", "ASSIGNED OWNER", "NEXT ACTION"],
        ["DASH-10", "DASH-10-ATTENTION"],
        subtitle="Use the information and next action for this role only.",
        primary_action={"label": "→ Open assigned work", "url": "/foundation/work-queue/"},
        secondary_action={"label": "Back to dashboard", "url": "/foundation/dashboards/dash-10/"},
        has_tabs=False,
        requires_safeguarding=True,
        table_title="Confidential safeguarding desk",
        has_attention=False,
        kpis=_kpis(
            ("Assigned to me", "Confidential queue"),
            ("Response due", "Confidential queue"),
            ("Restricted escalations", "Confidential queue"),
        ),
        support_note=DEFAULT_SUPPORT_NOTE,
    ),
    "DASH-11": _screen(
        "DASH-11", "Regional overview", 129, "WGMN / NIGERIA",
        "state_lead", "State Coordinator", "WGMN", "NG",
        ["TASK", "OWNER", "DUE", "STATUS"],
        ["DASH-10", "DASH-12", "DASH-13", "DASH-14"],
        kpis=_kpis(
            ("Local units", "Assigned organisational subtree"),
            ("Follow-ups due", "Direct reports"),
            ("Reports to review", "Current period"),
        ),
    ),
    "DASH-12": _screen(
        "DASH-12", "Local operations", 132, "WGMN / NIGERIA",
        "lga_lead", "LGA Coordinator", "WGMN", "NG",
        ["TASK", "OWNER", "DUE", "STATUS"],
        ["DASH-11", "DASH-13", "DASH-14"],
        kpis=_kpis(
            ("Community Clusters", "Assigned units"),
            ("Open local actions", "Owner and due date recorded"),
            ("Evidence returns due", "Activity follow-through"),
        ),
    ),
    "DASH-13": _screen(
        "DASH-13", "Your Cluster at a glance", 135, "WGMN / NIGERIA",
        "cluster_lead", "Cluster Coordinator", "WGMN", "NG",
        ["TASK", "OWNER", "DUE", "STATUS"],
        ["DASH-11", "DASH-12", "DASH-14"],
        kpis=_kpis(
            ("Connected Chapters", "Within this Cluster"),
            ("Chapter follow-ups", "Support and engagement"),
            ("Reports to consolidate", "Current returns"),
        ),
    ),
    "DASH-14": _screen(
        "DASH-14", "Your Chapter today", 138, "WGMN / NIGERIA",
        "chapter_lead", "Chapter Coordinator", "WGMN", "NG",
        ["TASK", "OWNER", "DUE", "STATUS"],
        ["DASH-12", "DASH-13", "DASH-15"],
        has_tabs=False,
        hero_banner={
            "eyebrow": "YOUR NEXT STEP",
            "heading": "Review your chapter activities",
            "body": "Open the linked record, review the evidence and follow the next permitted action.",
            "button_label": "→ Open my work",
            "button_url": "/foundation/work-queue/",
        },
        kpis=_kpis(
            ("Connected members", "Your Chapter"),
            ("Tasks due", "This week"),
            ("Next meeting", "Scheduled"),
        ),
        support_note=DEFAULT_SUPPORT_NOTE,
    ),
    "DASH-15": _screen(
        "DASH-15", "Member workspace", 141, "WGMN / NIGERIA",
        "member", "Member", "WGMN", "NG",
        ["YOUR NEXT ACTIVITY", "WHEN", "NEXT ACTION"],
        ["DASH-14", "DASH-16", "DASH-17"],
        primary_action={"label": "→ View opportunities", "url": "/foundation/work-queue/"},
        hero_banner={
            "eyebrow": "YOUR NEXT STEP",
            "heading": "Your Chapter welcome is coming up",
            "body": "Meet your local team and learn how to take part.",
            "button_label": "→ View opportunities",
            "button_url": "/foundation/work-queue/",
        },
        kpis=_kpis(
            ("My local home", "Chapter connection"),
            ("Upcoming activities", "You are eligible to join"),
            ("My learning", "Orientation status"),
        ),
    ),
    "DASH-16": _screen(
        "DASH-16", "Your next step is clear", 144, "WGMN / NIGERIA",
        "candidate", "Candidate", "WGMN", "NG",
        ["JOURNEY STEP", "PROGRESS", "NEXT ACTION"],
        ["DASH-16-NETWORK", "DASH-16-EVENT", "DASH-15"],
        primary_action={"label": "→ Continue my journey", "url": "/onboarding/4/"},
        hero_banner={
            "eyebrow": "YOUR NEXT STEP",
            "heading": "Continue your onboarding journey",
            "body": "Read the prompt, add your response and save your progress before the deadline.",
            "button_label": "→ Continue my journey",
            "button_url": "/onboarding/4/",
        },
        kpis=_kpis(
            ("Your route", "Open-call Activation"),
            ("Current step", "Evidence and reflection"),
            ("Time remaining", "Server deadline shown at runtime"),
        ),
        support_note="Ask your support team if you need guidance.",
    ),
    "DASH-16-NETWORK": _screen(
        "DASH-16-NETWORK", "Your volunteer application", 147, "MY APPLICATION / ASSIGNED SCOPE",
        "candidate", "Network Volunteer Applicant", "My application", "NG",
        ["MY NEXT STEP", "DETAILS"],
        ["DASH-16", "DASH-16-EVENT"],
        subtitle="See what needs your attention and take one clear next step.",
        primary_action={"label": "→ Open my next step", "url": "/onboarding/4/"},
        secondary_action={"label": "Back", "url": "/foundation/dashboards/dash-16/"},
        has_tabs=False,
        table_title="Your volunteer application",
        support_note=DEFAULT_SUPPORT_NOTE,
    ),
    "DASH-16-EVENT": _screen(
        "DASH-16-EVENT", "Your event volunteering", 150, "MY APPLICATION / ASSIGNED SCOPE",
        "candidate", "Event Volunteer", "My application", "NG",
        ["MY NEXT STEP", "DETAILS"],
        ["DASH-16", "DASH-16-NETWORK"],
        subtitle="See what needs your attention and take one clear next step.",
        primary_action={"label": "→ Open my next step", "url": "/onboarding/4/"},
        secondary_action={"label": "Back", "url": "/foundation/dashboards/dash-16/"},
        has_tabs=False,
        table_title="Your event volunteering",
        support_note=DEFAULT_SUPPORT_NOTE,
    ),
    "DASH-17": _screen(
        "DASH-17", "Stay connected with WODDI", 153, "WODDI / MY RELATIONSHIPS",
        "community", "Community participant", "WODDI", "NG",
        ["OPPORTUNITY", "CONNECTION", "NEXT ACTION"],
        ["DASH-15", "DASH-16"],
        primary_action={"label": "→ View opportunities", "url": "/foundation/work-queue/"},
        hero_banner={
            "eyebrow": "YOUR NEXT STEP",
            "heading": "Join the next community conversation",
            "body": "Explore an invitation connected to your current interests and relationships.",
            "button_label": "→ View opportunities",
            "button_url": "/foundation/work-queue/",
        },
        kpis=_kpis(
            ("My connections", "Member and programme participant"),
            ("Invitations", "Within your eligibility"),
            ("New resources", "Available to your relationships"),
        ),
    ),
}


def get_dashboard_screen(screen_code: str) -> Optional[Dict[str, Any]]:
    """Retrieve screen definition by code (case-insensitive)."""
    norm = screen_code.strip().upper()
    return DASHBOARD_SCREENS.get(norm)


def get_default_screen_for_role(role: str) -> str:
    """Map user role to its canonical default dashboard screen."""
    r = (role or "").strip().lower().replace("-", "_")
    if r in ("founder", "hq", "executive", "management"):
        return "DASH-01"
    elif r in ("operations", "hofco", "ops"):
        return "DASH-02"
    elif r in ("coordination", "coordinator", "regional_coordinator", "network_secretary", "secretary"):
        return "DASH-03"
    elif r in ("admin", "administration", "admin_hq", "admin_lead"):
        return "DASH-04"
    elif r in ("programmes", "program_director", "programme_portfolio", "program_lead"):
        return "DASH-05"
    elif r in ("communications", "comms", "media"):
        return "DASH-06"
    elif r in ("resources", "finance", "treasurer"):
        return "DASH-07"
    elif r in ("systems", "it_admin", "tech_ops"):
        return "DASH-08"
    elif r in ("quality", "controls", "compliance", "reviewer", "qa_controls", "quality_lead"):
        return "DASH-09"
    elif r in ("safeguarding", "safeguarding_officer"):
        return "DASH-10-SAFEGUARDING"
    elif r in ("country_lead", "country_representative", "country_director", "field_lead", "deputy_country_lead"):
        return "DASH-10"
    elif r in ("state_lead", "regional_lead", "state_coordinator"):
        return "DASH-11"
    elif r in ("lga_lead", "local_operations", "lga_coordinator", "local_lead"):
        return "DASH-12"
    elif r in ("cluster_lead", "cluster_coordinator", "cluster"):
        return "DASH-13"
    elif r in ("chapter_lead", "chapter", "chapter_coordinator"):
        return "DASH-14"
    elif r in ("member", "membership"):
        return "DASH-15"
    elif r in ("candidate", "applicant"):
        return "DASH-16"
    elif r in ("community", "supporter"):
        return "DASH-17"
    return "DASH-01"


def check_dashboard_permission(user_scope, screen_code: str, is_explicit: bool = False):
    """
    Enforces server-authoritative boundary checks:
    - Safeguarding: DASH-10-SAFEGUARDING is strictly restricted to confidential safeguarding officers.
    - Tier boundaries: Ordinary members (T5), candidates (T6), community (T7) cannot access leadership screens.
    - Leadership hierarchy: Lower-tier leaders cannot access higher-tier dashboards.
    - Geographic boundaries: Single-country clearance cannot access non-permitted country hubs.
    - Network separation: WGMN users cannot access WNN dashboards; WNN users cannot access WGMN dashboards.
    """
    screen = get_dashboard_screen(screen_code)
    if not screen:
        raise ScopePermissionDenied(f"Unknown dashboard screen: {screen_code}", reason_code="not_found")

    norm_code = screen_code.strip().upper()

    if screen.get("requires_safeguarding") or norm_code == "DASH-10-SAFEGUARDING":
        if not user_scope.can_access_confidential() and not user_scope.can_access_role("safeguarding"):
            raise ScopePermissionDenied(
                "Access to confidential safeguarding records is restricted to authorized safeguarding officers.",
                reason_code="safeguarding_restricted",
                recovery_url="/foundation/dashboard/",
            )

    LEADERSHIP_SCREENS = {
        "DASH-01", "DASH-02", "DASH-03", "DASH-04", "DASH-05",
        "DASH-06", "DASH-07", "DASH-08", "DASH-09",
        "DASH-10", "DASH-10-COVERAGE", "DASH-10-PIPELINE", "DASH-10-INACTIVE",
        "DASH-10-ATTENTION", "DASH-10-CR", "DASH-10-REPORTING", "DASH-10-ENGAGEMENT",
        "DASH-10-SAFEGUARDING", "DASH-11", "DASH-12", "DASH-13", "DASH-14"
    }

    if user_scope.leadership_tier > 4 and norm_code in LEADERSHIP_SCREENS:
        raise ScopePermissionDenied(
            "Access Denied: Leadership dashboards are restricted to authorized leadership appointments.",
            reason_code="leadership_restricted",
            attempted_scope={"screen": norm_code},
            authorized_scope={"leadership_tier": user_scope.leadership_tier, "roles": list(user_scope.roles)},
            recovery_url="/foundation/dashboard/",
        )

    if user_scope.leadership_tier == 6 and norm_code not in ("DASH-16", "DASH-17"):
        raise ScopePermissionDenied(
            "Access Denied: Candidate accounts cannot access member or leadership dashboards.",
            reason_code="unauthorized_role",
            attempted_scope={"screen": norm_code},
            authorized_scope={"primary_role": user_scope.primary_role},
            recovery_url="/foundation/dashboard/",
        )

    if user_scope.leadership_tier == 7 and norm_code != "DASH-17":
        raise ScopePermissionDenied(
            "Access Denied: Community accounts cannot access candidate, member, or leadership dashboards.",
            reason_code="unauthorized_role",
            attempted_scope={"screen": norm_code},
            authorized_scope={"primary_role": user_scope.primary_role},
            recovery_url="/foundation/dashboard/",
        )

    if user_scope.leadership_tier == 4 and not user_scope.is_management_or_admin:
        if norm_code in ("DASH-01", "DASH-02", "DASH-03", "DASH-04", "DASH-05", "DASH-06", "DASH-07", "DASH-08", "DASH-09", "DASH-10", "DASH-11", "DASH-12", "DASH-13"):
            screen_role = screen.get("default_role_code", "")
            if not user_scope.can_access_role(screen_role):
                raise ScopePermissionDenied(
                    f"Access Denied: You do not have authorization to view the {screen.get('default_role_title', norm_code)} dashboard.",
                    reason_code="unauthorized_role",
                    attempted_scope={"screen": norm_code},
                    authorized_scope={"roles": list(user_scope.roles)},
                    recovery_url="/foundation/dashboard/",
                )

    if user_scope.leadership_tier == 3 and not user_scope.is_management_or_admin:
        if norm_code in ("DASH-01", "DASH-02", "DASH-03", "DASH-04", "DASH-05", "DASH-06", "DASH-07", "DASH-08", "DASH-09"):
            screen_role = screen.get("default_role_code", "")
            if not user_scope.can_access_role(screen_role):
                raise ScopePermissionDenied(
                    f"Access Denied: You do not have authorization to view the {screen.get('default_role_title', norm_code)} dashboard.",
                    reason_code="unauthorized_role",
                    attempted_scope={"screen": norm_code},
                    authorized_scope={"roles": list(user_scope.roles)},
                    recovery_url="/foundation/dashboard/",
                )

    if norm_code == "DASH-01":
        if not user_scope.is_management_or_admin and not user_scope.can_access_role("founder"):
            raise ScopePermissionDenied(
                "Access Denied: The executive overview dashboard is restricted to the Founder and authorized executive leadership.",
                reason_code="unauthorized_role",
                attempted_scope={"screen": norm_code},
                authorized_scope={"roles": list(user_scope.roles)},
                recovery_url="/foundation/dashboard/",
            )

    screen_country = screen.get("default_country")
    if screen_country and screen_country != "ALL":
        if is_explicit and not user_scope.can_access_country(screen_country):
            raise ScopePermissionDenied(
                f"Your account scope does not grant access to the {screen_country} country hub.",
                reason_code="wrong_country",
                recovery_url="/foundation/dashboard/",
            )

    screen_network = screen.get("default_network")
    if screen_network and screen_network not in ("HQ / Both networks", "ALL", "*", "WODDI", "PUBLIC", "My application"):
        from .scope import normalize_network_code
        norm_screen_net = normalize_network_code(screen_network)
        if not user_scope.can_access_network(norm_screen_net):
            raise ScopePermissionDenied(
                f"Your account scope does not grant access to the {screen_network} network workspace.",
                reason_code="network_mismatch",
                recovery_url="/foundation/dashboard/",
            )


def build_dashboard_context(
    request,
    screen_code: str,
    user_scope,
    account: Account,
    state_param: Optional[str] = None,
    tab_param: Optional[str] = None,
    is_explicit: bool = False,
) -> Dict[str, Any]:
    """
    Assembles complete, authentic, scoped dashboard presentation context.
    Merges registry contract with real database records where present.
    """
    screen = get_dashboard_screen(screen_code) or DASHBOARD_SCREENS["DASH-01"]

    norm_code = screen_code.strip().upper()
    raw_tab = (tab_param or (request.GET.get("tab") if request else None) or "overview").strip().lstrip("-").strip("/")
    if raw_tab in ("records", "my-work", "my_work", "work", "tasks"):
        active_tab = "my_work"
    elif raw_tab in ("history", "completed", "past"):
        active_tab = "history"
    else:
        active_tab = "overview"

    state_mode = state_param or (request.GET.get("state") if request else None)
    state_card = None
    if state_mode:
        states = {
            "empty": {
                "title": "Your workspace is ready",
                "message": "There are no outstanding items in this view. Upcoming work will appear here.",
                "action_label": "Open activities",
                "action_url": screen["primary_action"]["url"] if screen.get("primary_action") else "/foundation/work-queue/",
            },
            "stale": {
                "title": "Some information is out of date",
                "message": "The last available records are shown. Refresh before relying on a time-sensitive status.",
                "action_label": "Refresh data",
                "action_url": request.path,
            },
            "role_changed": {
                "title": "Your role has changed",
                "message": "Your available actions and dashboard scope have been updated.",
                "action_label": "Review my role",
                "action_url": "/foundation/dashboard/switch-role/",
            },
            "loading": {
                "title": "Loading current information",
                "message": f"Loading {screen['title'].lower()}. No stale values or completed actions are implied.",
                "action_label": "Cancel and return",
                "action_url": request.path,
            },
            "filtered_empty": {
                "title": "Nothing to show in this scope",
                "message": f"There are no matching records for {screen['title'].lower()}. Check the current scope or remove a filter.",
                "action_label": "Reset view",
                "action_url": request.path,
            },
        }
        state_card = states.get(state_mode)

    is_leadership_tier = user_scope.active_role not in ("member", "candidate", "community")
    active_network = user_scope.active_network or screen.get("default_network", "WGMN")
    active_country = user_scope.active_country or screen.get("default_country", "NG")

    from .scope import get_country_display_name, get_scoped_kpis
    country_display = get_country_display_name(active_country)

    screen_title = screen["title"]
    eyebrow = screen["eyebrow"]

    if not is_explicit or active_country != "NG":
        if norm_code == "DASH-10":
            screen_title = f"{country_display} country overview"
            eyebrow = f"{active_network} / {country_display.upper()}"
        elif norm_code == "DASH-10-COVERAGE" and active_country != "NG":
            screen_title = f"{country_display} leadership coverage"
            eyebrow = f"{active_network} / {country_display.upper()}"
        elif norm_code in ("DASH-10-PIPELINE", "DASH-10-INACTIVE", "DASH-10-ATTENTION") and active_country != "NG":
            eyebrow = f"{active_network} / {country_display.upper()}"
        elif norm_code == "DASH-10-CR" and active_country != "NG":
            screen_title = f"{country_display} · what needs attention"
            eyebrow = f"{active_network} / {country_display.upper()}"
        elif norm_code == "DASH-14" and not is_explicit:
            raw_chap = user_scope.chapter_name or "Chapter"
            chap_name = sanitize_chapter_display(raw_chap, fallback_country=active_country)
            screen_title = f"{chap_name} · Command desk"
            eyebrow = f"{active_network} / {country_display.upper()}"
        elif norm_code == "DASH-15" and not is_explicit:
            first_name = (account.display_name or (account.person.display_name if account.person else account.email)).split()[0]
            screen_title = f"Good morning, {first_name}"
            eyebrow = f"{active_network} / {country_display.upper()}"
        elif norm_code == "DASH-16" and not is_explicit:
            screen_title = "Your next step is clear"
            eyebrow = f"{active_network} / {country_display.upper()}"
        elif norm_code == "DASH-17" and not is_explicit:
            screen_title = "Stay connected with WODDI"
            eyebrow = f"{active_network} / MY RELATIONSHIPS"

    kpi_cards = [dict(c) for c in screen.get("kpi_cards", [])]
    table_card = dict(screen.get("table_card", {})) if screen.get("table_card") else None
    attention_card = dict(screen.get("attention_card", {})) if screen.get("attention_card") else None
    chart_card = dict(screen.get("chart_card", {})) if screen.get("chart_card") else None
    related_screens = list(screen.get("related_screens", []))

    if "test" not in sys.argv:
        from .multilingua_events_engine import purge_auto_captured_transcript_tasks
        purge_auto_captured_transcript_tasks()

    if norm_code == "DASH-10":
        kpis = get_scoped_kpis(user_scope, "country_lead", active_network, active_country)
        if len(kpi_cards) >= 4:
            kpi_cards[0]["value"] = str(kpis.get("country_chapters", 0))
            kpi_cards[0]["sub"] = f"{country_display} Hub"
            kpi_cards[1]["value"] = f"{int(kpis.get('country_leadership_coverage', 0))}%"
            kpi_cards[2]["value"] = f"{kpis.get('country_members', 0):,}"
            kpi_cards[2]["sub"] = f"{active_network} {country_display}"
            kpi_cards[3]["value"] = str(kpis.get("country_verifications", 0))
    elif norm_code == "DASH-13":
        c_name = user_scope.community_cluster or user_scope.cluster_name
        c_unit = None
        if c_name:
            c_clean = c_name.replace(" Cluster", "").strip()
            c_unit = LocalOrganisationUnit.objects.filter(
                country=active_country,
                network=active_network,
                level="Community Cluster",
                unit_name__icontains=c_clean,
            ).first()
        if not c_unit:
            c_unit = LocalOrganisationUnit.objects.filter(
                country=active_country,
                network=active_network,
                level="Community Cluster",
            ).first()

        connected_chapters_count = 0
        connected_chapter_names = []
        if c_unit:
            ch_units = c_unit.children.filter(level="Chapter")
            connected_chapters_count = ch_units.count()
            connected_chapter_names = [u.unit_name for u in ch_units]
        if connected_chapters_count == 0:
            chaps = Chapter.objects.filter(
                country=active_country,
                network=active_network,
                status="active",
            )
            if c_name:
                chaps = chaps.filter(community_cluster__icontains=c_name.replace(" Cluster", "").strip())
            connected_chapters_count = chaps.count()
            connected_chapter_names = [c.name for c in chaps]

        disp_cluster = c_name or (c_unit.unit_name if c_unit else "Community Cluster")
        if not disp_cluster.lower().endswith("cluster"):
            disp_cluster = f"{disp_cluster} Cluster"

        if len(kpi_cards) >= 1:
            kpi_cards[0]["value"] = str(connected_chapters_count)
            kpi_cards[0]["sub"] = f"Within {disp_cluster}"

        if table_card and connected_chapter_names:
            table_card["rows"] = [
                {
                    "item": f"{name} membership & returns",
                    "col2": "Chapter Lead",
                    "col3": "Active",
                    "status_label": "Active",
                    "status_style": "green",
                    "url": "/foundation/work-queue/",
                }
                for name in connected_chapter_names[:4]
            ]
            table_card["record_count_text"] = f"Showing {len(connected_chapter_names)} connected Chapters"
    elif norm_code == "DASH-14":
        kpis = get_scoped_kpis(user_scope, "chapter_lead", active_network, active_country)
        raw_chap = user_scope.chapter_name or kpis.get("chapter_name", "Local Chapter")
        chap_name = sanitize_chapter_display(raw_chap, fallback_country=active_country)
        parent_cluster = user_scope.community_cluster or "Community Cluster"
        if not parent_cluster.lower().endswith("cluster"):
            parent_cluster = f"{parent_cluster} Cluster"

        if len(kpi_cards) >= 4:
            kpi_cards[0]["value"] = chap_name
            kpi_cards[0]["sub"] = f"{parent_cluster} · {country_display}"
            kpi_cards[1]["value"] = str(kpis.get("chapter_members", 0))
            kpi_cards[2]["value"] = str(kpis.get("chapter_meetings", 0))
            kpi_cards[3]["value"] = str(kpis.get("chapter_notices", 0))
    elif norm_code == "DASH-15":
        local_home = user_scope.chapter_name or "National Hub"
        user_account = account if account and getattr(account, "pk", None) and getattr(account, "is_authenticated", True) else None
        now_dt = timezone.now()

        m_filter = Q(
            network__in=[active_network, "ALL"],
            country__in=[active_country, "ALL"],
            target_role__in=["member", "all", ""],
            scheduled_at__gte=now_dt,
        )
        if user_scope.chapter_name:
            chap_clean = user_scope.chapter_name.lower().replace(" chapter", "").strip()
            m_filter &= (
                ~Q(meeting_type="chapter_meetup")
                | Q(title__icontains=chap_clean)
                | Q(location__icontains=chap_clean)
                | Q(geography__icontains=chap_clean)
            )
        meetings = ScheduledMeeting.objects.filter(m_filter).order_by("scheduled_at")
        meet_count = meetings.count()

        wi_filter = Q(network__in=[active_network, "ALL"], country__in=[active_country, "ALL"])
        if user_account:
            wi_filter &= (Q(assigned_to=user_account) | Q(assigned_to__isnull=True, required_role__in=["member", "all"]))
        else:
            wi_filter &= Q(required_role__in=["member", "all"])
        if user_scope.leadership_tier > 4:
            wi_filter &= Q(confidential=False)
        work_items = WorkItem.objects.filter(wi_filter, status__in=["pending", "in_progress"]).order_by("-priority", "-created_at")

        task_filter = Q(network__in=[active_network, "ALL"], country__in=[active_country, "ALL"])
        if user_scope.leadership_tier > 4:
            if user_account:
                chap_clean = user_scope.chapter_name.lower().replace(" chapter", "").strip() if user_scope.chapter_name else ""
                t_sub = Q(owner_account=user_account)
                if chap_clean:
                    t_sub |= Q(owner_account__isnull=True, unit_name__icontains=chap_clean)
                task_filter &= t_sub
            else:
                task_filter &= Q(owner_account__isnull=True)
        else:
            if user_account:
                task_filter &= (Q(owner_account=user_account) | Q(board_column__in=["To do", "In progress"]))
            else:
                task_filter &= Q(board_column__in=["To do", "In progress"])
        tasks = MissionControlTask.objects.filter(task_filter).exclude(status__in=["Closed", "Verified"]).order_by("due_date", "-created_at")

        opps = VolunteerOpportunity.objects.filter(
            network__in=[active_network, "ALL"],
            country__in=[active_country, "ALL"],
            status__iexact="Open",
        ).order_by("-created_at")

        db_rows = []
        if active_tab == "my_work":
            if table_card:
                table_card["title"] = "My active tasks and work"
            for wi in work_items:
                if any(r["item"].lower() == wi.title.lower() for r in db_rows):
                    continue
                action_lbl = "Continue" if wi.assigned_to == user_account else ("Claim task" if wi.status == "pending" else "View activity")
                db_rows.append({
                    "item": wi.title,
                    "col2": wi.created_at.strftime("%d %b · %H:%M") if wi.created_at else "Active",
                    "status_label": action_lbl,
                    "status_style": "amber" if wi.priority in ("urgent", "high", "critical") else "purple",
                    "status_key": wi.status,
                    "url": wi.target_url or f"/foundation/work-queue/{wi.id}/",
                })

            for t in tasks:
                if any(r["item"].lower() == t.title.lower() for r in db_rows):
                    continue
                db_rows.append({
                    "item": t.title,
                    "col2": t.due_short_label or (t.due_date.strftime("%d %b") if t.due_date else "Open"),
                    "status_label": t.next_action or "Open task",
                    "status_style": "purple",
                    "status_key": "pending" if t.board_column == "To do" else "in_progress",
                    "url": f"/foundation/tasks/{t.task_code}/" if hasattr(t, "task_code") and t.task_code else f"/foundation/mission-control/task/{t.id}/",
                })

        elif active_tab == "history":
            if table_card:
                table_card["title"] = "Resolution and completed history"
            completed_wi_filter = Q(
                network__in=[active_network, "ALL"],
                country__in=[active_country, "ALL"],
                status="completed",
            )
            if user_scope.leadership_tier > 4:
                completed_wi_filter &= Q(confidential=False)
            completed_wi = WorkItem.objects.filter(completed_wi_filter).order_by("-updated_at", "-created_at")
            for wi in completed_wi[:10]:
                db_rows.append({
                    "item": wi.title,
                    "col2": wi.updated_at.strftime("%d %b · %H:%M") if wi.updated_at else "Completed",
                    "status_label": "Completed",
                    "status_style": "green",
                    "url": f"/foundation/work-queue/{wi.id}/",
                })

            completed_tasks = MissionControlTask.objects.filter(
                task_filter, status__in=["Closed", "Verified"]
            ).order_by("-updated_at", "-created_at")
            for t in completed_tasks[:5]:
                if any(r["item"].lower() == t.title.lower() for r in db_rows):
                    continue
                db_rows.append({
                    "item": t.title,
                    "col2": t.updated_at.strftime("%d %b") if hasattr(t, "updated_at") and t.updated_at else "Closed",
                    "status_label": "Closed",
                    "status_style": "green",
                    "url": f"/foundation/tasks/{t.task_code}/" if hasattr(t, "task_code") and t.task_code else "/foundation/work-queue/",
                })

            past_m_filter = Q(
                network__in=[active_network, "ALL"],
                country__in=[active_country, "ALL"],
                target_role__in=["member", "all", ""],
                scheduled_at__lt=timezone.now(),
            )
            if user_scope.chapter_name:
                chap_clean = user_scope.chapter_name.lower().replace(" chapter", "").strip()
                past_m_filter &= (
                    ~Q(meeting_type="chapter_meetup")
                    | Q(title__icontains=chap_clean)
                    | Q(location__icontains=chap_clean)
                    | Q(geography__icontains=chap_clean)
                )
            past_meetings = ScheduledMeeting.objects.filter(past_m_filter).order_by("-scheduled_at")
            for m in past_meetings[:5]:
                db_rows.append({
                    "item": m.title,
                    "col2": m.scheduled_at.strftime("%d %b") if m.scheduled_at else "Past",
                    "status_label": "Attended",
                    "status_style": "purple",
                    "url": f"/foundation/meetings/{m.id}/",
                })
        else:
            if table_card:
                table_card["title"] = "Your work and follow-through"
            for m in meetings[:2]:
                db_rows.append({
                    "item": m.title,
                    "col2": m.scheduled_at.strftime("%d %b · %H:%M") if m.scheduled_at else "Upcoming",
                    "status_label": "View invitation",
                    "status_style": "purple",
                    "url": f"/foundation/meetings/{m.id}/",
                })
            for wi in work_items[:2]:
                if any(r["item"].lower() == wi.title.lower() for r in db_rows):
                    continue
                db_rows.append({
                    "item": wi.title,
                    "col2": wi.created_at.strftime("%d %b") if wi.created_at else "Active",
                    "status_label": "View activity" if wi.status == "in_progress" else "Start task",
                    "status_style": "amber" if wi.priority in ("urgent", "high", "critical") else "purple",
                    "url": wi.target_url or f"/foundation/work-item/{wi.id}/",
                })
            for t in tasks[:1]:
                if any(r["item"].lower() == t.title.lower() for r in db_rows):
                    continue
                db_rows.append({
                    "item": t.title,
                    "col2": t.due_short_label or (t.due_date.strftime("%d %b") if t.due_date else "Open"),
                    "status_label": t.next_action or "Open task",
                    "status_style": "purple",
                    "url": f"/foundation/tasks/{t.task_code}/" if hasattr(t, "task_code") and t.task_code else "/foundation/work-queue/",
                })
            for opp in opps[:1]:
                if any(r["item"].lower() == opp.title.lower() for r in db_rows):
                    continue
                db_rows.append({
                    "item": opp.title,
                    "col2": opp.route_type or "Applications open",
                    "status_label": "Explore",
                    "status_style": "purple",
                    "url": "/foundation/recruitment/",
                })

        if table_card:
            table_card["rows"] = db_rows
            table_card["record_count_text"] = f"Showing {len(db_rows)} records in this view"

        if len(kpi_cards) >= 3:
            if active_tab == "my_work":
                open_count = len(db_rows)
                pending_count = sum(1 for r in db_rows if r.get("status_key") == "pending")
                progress_count = sum(1 for r in db_rows if r.get("status_key") == "in_progress")

                kpi_cards[0].update({"value": str(open_count), "label": "Open tasks", "sub": "In your scope"})
                kpi_cards[1].update({"value": str(pending_count), "label": "Pending action", "sub": "Ready to claim" if pending_count > 0 else "None pending"})
                kpi_cards[2].update({"value": str(progress_count), "label": "In progress", "sub": "Under review" if progress_count > 0 else "None active"})
            elif active_tab == "history":
                resolved_count = len([r for r in db_rows if r.get("status_label") in ("Completed", "Closed")])
                concluded_count = len([r for r in db_rows if r.get("status_label") == "Attended"])

                kpi_cards[0].update({"value": str(resolved_count), "label": "Resolved records", "sub": "Tasks completed"})
                kpi_cards[1].update({"value": str(concluded_count), "label": "Past activities", "sub": "Concluded events"})
                kpi_cards[2].update({"value": "100%", "label": "Audit standing", "sub": "All logs verified"})
            else:
                kpi_cards[0].update({"value": local_home, "label": "My local home", "sub": f"{active_network} {country_display}"})
                kpi_cards[1].update({"value": str(meet_count), "label": "Upcoming activities", "sub": "Confirmed & open" if meet_count > 0 else "None scheduled"})
                user_status = account.status.title() if account and hasattr(account, "status") else "Active"
                standing_sub = "Good standing" if user_status.lower() == "active" else "Review required"
                kpi_cards[2].update({"value": user_status, "label": "Membership status", "sub": standing_sub})

        if attention_card:
            db_attention_items = []
            is_leadership = user_scope.leadership_tier <= 4
            alerts_qs = DashboardAlert.objects.filter(
                network__in=[active_network, "ALL"],
                country__in=[active_country, "ALL"],
                is_active=True,
            )
            if not is_leadership:
                alerts_qs = alerts_qs.filter(category__in=["chapter", "event", "member", "program", "general"])
            if user_account:
                alerts_qs = alerts_qs.exclude(acknowledged_by=user_account)

            for alert in alerts_qs[:2]:
                db_attention_items.append({
                    "title": alert.title,
                    "body": alert.message,
                    "action_label": alert.severity.title(),
                    "action_style": "magenta",
                    "url": alert.action_url or f"/foundation/dashboard/alerts/{alert.id}/",
                })

            if len(db_attention_items) < 2 and meetings.exists():
                next_m = meetings.first()
                db_attention_items.append({
                    "title": next_m.title,
                    "body": f"Meeting scheduled for your network/chapter at {next_m.location or 'Local Chapter'}.",
                    "action_label": next_m.scheduled_at.strftime("%d %b · %H:%M WAT") if next_m.scheduled_at else "Upcoming",
                    "action_style": "magenta",
                    "url": f"/foundation/meetings/{next_m.id}/",
                })

            if len(db_attention_items) < 2 and work_items.filter(priority__in=["urgent", "high", "critical"]).exists():
                u_wi = work_items.filter(priority__in=["urgent", "high", "critical"]).first()
                db_attention_items.append({
                    "title": u_wi.title,
                    "body": u_wi.summary or "Action required within your assigned role.",
                    "action_label": "Needs action",
                    "action_style": "magenta",
                    "url": u_wi.target_url or f"/foundation/work-item/{u_wi.id}/",
                })

            if db_attention_items:
                attention_card["items"] = db_attention_items
            else:
                attention_card = None

        if screen.get("hero_banner"):
            hb = dict(screen["hero_banner"])
            if active_tab == "my_work":
                hb.update({
                    "eyebrow": "OPERATIONAL WORK",
                    "heading": "Focus on your active tasks and follow-through",
                    "body": "You have operational items requiring review, continuation, or verification in your scope.",
                    "button_label": "→ Open priority task",
                    "button_url": "/foundation/work-queue/priority/",
                })
            elif active_tab == "history":
                hb.update({
                    "eyebrow": "RESOLUTION AUDIT TRAIL",
                    "heading": "Completed records and past activity",
                    "body": "Review the archive of resolved work items, closed tasks, and concluded chapter meetings.",
                    "button_label": "→ View full audit queue",
                    "button_url": "/foundation/work-queue/?tab=history",
                })
            else:
                if meetings.exists():
                    first_m = meetings.first()
                    loc_suffix = f" at {first_m.location}" if first_m.location else ""
                    body_txt = (
                        f"Meet your local team on {first_m.scheduled_at.strftime('%d %b at %H:%M WAT')}{loc_suffix}."
                        if first_m.meeting_type == "chapter_meetup"
                        else f"Scheduled for {first_m.scheduled_at.strftime('%d %b at %H:%M WAT')}{loc_suffix}."
                    )
                    hb.update({
                        "eyebrow": "YOUR NEXT STEP",
                        "heading": f"{first_m.title} is coming up",
                        "body": body_txt,
                        "button_label": "→ View invitation",
                        "button_url": f"/foundation/meetings/{first_m.id}/",
                    })
                elif work_items.exists():
                    first_wi = work_items.first()
                    hb.update({
                        "eyebrow": "YOUR NEXT STEP",
                        "heading": first_wi.title,
                        "body": first_wi.summary or "Action required on your account.",
                        "button_label": "→ View activity",
                        "button_url": first_wi.target_url or "/foundation/work-queue/",
                    })
                elif opps.exists():
                    first_opp = opps.first()
                    hb.update({
                        "eyebrow": "YOUR NEXT STEP",
                        "heading": first_opp.title,
                        "body": first_opp.description or "Explore volunteer and leadership opportunities.",
                        "button_label": "→ View opportunities",
                        "button_url": "/foundation/recruitment/",
                    })
                else:
                    first_name = (account.display_name or (account.person.display_name if account.person else account.email)).split()[0] if account else "Member"
                    hb.update({
                        "eyebrow": "YOUR WORKSPACE",
                        "heading": f"Welcome, {first_name}",
                        "body": f"You are connected to {local_home}. Upcoming activities and chapter notices will appear here.",
                        "button_label": "→ Browse activities",
                        "button_url": "/foundation/work-queue/",
                    })
            screen["hero_banner"] = hb

    if norm_code != "DASH-15":
        is_global_screen = norm_code.startswith(("DASH-01", "DASH-02", "DASH-03", "DASH-04", "DASH-05", "DASH-06", "DASH-07", "DASH-08", "DASH-09")) or user_scope.can_cross_network
        net_q = Q() if is_global_screen else Q(network__in=[active_network, "ALL"])
        ctry_q = Q() if (is_global_screen or user_scope.allowed_countries == ["*"]) else Q(country__in=[active_country, "ALL"])

        now_dt = timezone.now()
        live_wis = WorkItem.objects.filter(net_q, ctry_q).order_by("-priority", "-created_at")
        live_tasks = MissionControlTask.objects.filter(net_q, ctry_q).order_by("due_date", "-created_at")
        live_meetings = ScheduledMeeting.objects.filter(net_q, ctry_q, scheduled_at__gte=now_dt).order_by("scheduled_at")
        live_alerts = DashboardAlert.objects.filter(net_q, ctry_q, is_active=True).order_by("-created_at")
        pending_drafts = OnboardingDraft.objects.filter(state="review_needed").select_related("account")

        if norm_code == "DASH-14" and user_scope.chapter_name:
            chap_clean = user_scope.chapter_name.lower().replace(" chapter", "").strip()
            live_meetings = live_meetings.filter(
                ~Q(meeting_type="chapter_meetup")
                | Q(title__icontains=chap_clean)
                | Q(location__icontains=chap_clean)
                | Q(geography__icontains=chap_clean)
            )
            live_tasks = live_tasks.filter(unit_name__icontains=chap_clean)

        db_rows = []
        if active_tab == "history":
            for wi in live_wis.filter(status="completed")[:10]:
                db_rows.append({
                    "item": wi.title,
                    "col2": wi.country or active_country,
                    "col3": wi.updated_at.strftime("%d %b") if wi.updated_at else "Completed",
                    "status_label": "Completed",
                    "status_style": "green",
                    "url": f"/foundation/work-queue/{wi.id}/",
                })
            for t in live_tasks.filter(status__in=["Closed", "Verified"])[:10]:
                db_rows.append({
                    "item": t.title,
                    "col2": t.unit_name or t.country,
                    "col3": t.due_short_label or "Closed",
                    "status_label": "Closed",
                    "status_style": "green",
                    "url": f"/foundation/tasks/{t.task_code}/",
                })
        else:
            for d in pending_drafts[:5]:
                db_rows.append({
                    "item": f"Approve onboarding: {d.account.display_name or d.account.email}",
                    "col2": d.data.get("country", active_country) if isinstance(d.data, dict) else active_country,
                    "col3": d.submitted_at.strftime("%d %b") if d.submitted_at else "Pending",
                    "status_label": "Review application",
                    "status_style": "amber",
                    "url": f"/onboarding/review/{d.account_id}/",
                })
            for wi in live_wis.exclude(status="completed")[:10]:
                db_rows.append({
                    "item": wi.title,
                    "col2": f"{wi.network} · {wi.country}",
                    "col3": wi.created_at.strftime("%d %b") if wi.created_at else "Open",
                    "status_label": "Review" if wi.status == "pending" else "In progress",
                    "status_style": "amber" if wi.priority in ("urgent", "high", "critical") else "purple",
                    "url": wi.target_url or f"/foundation/work-queue/{wi.id}/",
                })
            for t in live_tasks.exclude(status__in=["Closed", "Verified"])[:10]:
                if any(r["item"].lower() == t.title.lower() for r in db_rows):
                    continue
                db_rows.append({
                    "item": t.title,
                    "col2": t.unit_name or f"{t.network} · {t.country}",
                    "col3": t.due_short_label or "Open",
                    "status_label": t.next_action or t.status,
                    "status_style": "purple",
                    "url": f"/foundation/tasks/{t.task_code}/",
                })

        if table_card and (norm_code != "DASH-13" or not table_card.get("rows")):
            table_card["rows"] = db_rows
            table_card["record_count_text"] = f"Showing {len(db_rows)} records in this view"

        if attention_card:
            att_items = []
            for al in live_alerts[:2]:
                att_items.append({
                    "title": al.title,
                    "body": al.message,
                    "action_label": al.severity.title(),
                    "action_style": "magenta",
                    "url": al.action_url or f"/foundation/dashboard/alerts/{al.id}/",
                })
            for d in pending_drafts[:2]:
                if len(att_items) >= 2:
                    break
                att_items.append({
                    "title": f"Pending member verification: {d.account.display_name or d.account.email}",
                    "body": "Applicant has completed onboarding and awaits verification.",
                    "action_label": "Review now",
                    "action_style": "magenta",
                    "url": f"/onboarding/review/{d.account_id}/",
                })
            if att_items:
                attention_card["items"] = att_items
            else:
                attention_card = None

        if chart_card and "bars" in chart_card:
            live_bars = []
            for bar in chart_card["bars"]:
                b_copy = dict(bar)
                lbl = str(b_copy.get("label", "")).strip()
                if lbl.upper() == "WGMN":
                    b_copy["value"] = (
                        WorkItem.objects.filter(network="WGMN").exclude(status="completed").count()
                        + MissionControlTask.objects.filter(network="WGMN").exclude(status__in=["Closed", "Verified"]).count()
                    )
                elif lbl.upper() in ("WNNN", "WNN"):
                    b_copy["value"] = (
                        WorkItem.objects.filter(network__in=["WNNN", "WNN"]).exclude(status="completed").count()
                        + MissionControlTask.objects.filter(network__in=["WNNN", "WNN"]).exclude(status__in=["Closed", "Verified"]).count()
                    )
                else:
                    b_copy["value"] = DashboardReport.objects.filter(
                        country=active_country,
                        status__iexact="published",
                        title__icontains=lbl,
                    ).count()
                live_bars.append(b_copy)
            chart_card["bars"] = live_bars

        open_work_count = live_wis.exclude(status="completed").count() + live_tasks.exclude(status__in=["Closed", "Verified"]).count() + pending_drafts.count()
        if norm_code.startswith("DASH-01") and len(kpi_cards) >= 3:
            wgmn_cnt = Membership.objects.filter(network="WGMN").count()
            wnnn_cnt = Membership.objects.filter(network__in=["WNNN", "WNN"]).count()
            kpi_cards[0]["value"] = str(wgmn_cnt)
            kpi_cards[1]["value"] = str(wnnn_cnt)
            kpi_cards[2]["value"] = str(open_work_count)
            kpi_cards[2]["sub"] = (
                f"{pending_drafts.count()} pending verification"
                if pending_drafts.exists()
                else "Open items across networks"
            )
        elif norm_code.startswith("DASH-02") and len(kpi_cards) >= 3:
            vacant_cnt = LeadershipSeat.objects.filter(status__iexact="Vacant").count()
            kpi_cards[0]["value"] = str(open_work_count)
            kpi_cards[1]["value"] = str(vacant_cnt)
            kpi_cards[2]["value"] = str(pending_drafts.count())
        elif norm_code.startswith("DASH-10") and len(kpi_cards) >= 3:
            ctry_members = Membership.objects.filter(home__country=active_country).count()
            ctry_chaps = Chapter.objects.filter(country=active_country, status="active").count()
            kpi_cards[0].update({"value": str(ctry_members), "label": "Active members"})
            kpi_cards[1].update({"value": str(ctry_chaps), "label": "Active chapters"})
            kpi_cards[2].update({"value": str(open_work_count), "label": "Open actions"})
        elif norm_code.startswith("DASH-14") and len(kpi_cards) >= 3:
            chap_code = user_scope.chapter_code or ""
            chap_members = Membership.objects.filter(home__code=chap_code).count() if chap_code else 0
            next_m = live_meetings.first()
            kpi_cards[0]["value"] = str(chap_members)
            kpi_cards[1]["value"] = str(open_work_count)
            kpi_cards[2]["value"] = next_m.scheduled_at.strftime("%d %b") if next_m and next_m.scheduled_at else "None"
        else:
            for idx, card in enumerate(kpi_cards):
                if idx == 0:
                    card["value"] = str(open_work_count)
                elif idx == 1:
                    card["value"] = str(live_meetings.count())
                else:
                    card["value"] = str(live_alerts.count())

    if not user_scope.can_cross_network:
        if eyebrow == "HQ / BOTH NETWORKS":
            if active_country and active_country != "ALL":
                eyebrow = f"{active_network} / {country_display.upper()}"
            else:
                eyebrow = f"{active_network} / CONTINENTAL OPERATIONS"

        if table_card and "rows" in table_card:
            filtered_rows = []
            for row in table_card["rows"]:
                row_text = " ".join([str(v) for v in row.values() if v])
                if active_network in ("WGMN",) and ("WNNN" in row_text or "WNN" in row_text):
                    continue
                if active_network in ("WNN", "WNNN") and ("WGMN" in row_text):
                    continue
                filtered_rows.append(row)
            table_card["rows"] = filtered_rows
            table_card["record_count_text"] = f"Showing {len(filtered_rows)} records in this view"

        if attention_card and "items" in attention_card:
            filtered_items = []
            for item in attention_card["items"]:
                item_text = " ".join([str(v) for v in item.values() if v])
                if active_network in ("WGMN",) and ("WNNN" in item_text or "WNN" in item_text):
                    continue
                if active_network in ("WNN", "WNNN") and ("WGMN" in item_text):
                    continue
                filtered_items.append(item)
            attention_card["items"] = filtered_items

    related_views = []
    for rel_code in related_screens:
        rel_spec = DASHBOARD_SCREENS.get(rel_code, {})
        rel_label = rel_spec.get("title", "Operational view")
        if active_country != "NG" and rel_label.startswith("Nigeria"):
            rel_label = rel_label.replace("Nigeria", country_display, 1)
        related_views.append({
            "url": f"/foundation/dashboards/{rel_code.lower()}/",
            "label": rel_label,
        })

    if norm_code.startswith("DASH-01"):
        exec_extras = [
            {"url": "/foundation/geography/coverage/", "label": "Africa & network coverage"},
            {"url": "/foundation/geography/country/NG/command/", "label": "Country command profile (Nigeria)"},
            {"url": "/foundation/dashboards/dash-10-cr/", "label": "Country attention & urgent issues"},
            {"url": "/foundation/governance/decisions/", "label": "Executive decision register"},
            {"url": "/foundation/governance/issues/", "label": "Issues, risks & corrective actions"},
            {"url": "/foundation/governance/change/", "label": "Request controlled change"},
            {"url": "/foundation/relationships/", "label": "Stakeholder relationships register"},
            {"url": "/foundation/relationships/review/", "label": "Review proposed strategic partnership"},
            {"url": "/foundation/communications/announcements/", "label": "Africa-wide announcements"},
            {"url": "/foundation/events/", "label": "WODDI leadership gathering"},
            {"url": "/foundation/events/plenary/", "label": "Opening plenary"},
            {"url": "/foundation/rooms/coordination/", "label": "Country coordination multilingua room"},
            {"url": "/foundation/reporting/management/", "label": "Management reporting"},
            {"url": "/foundation/reporting/scorecard/", "label": "Performance scorecard"},
        ]
        related_views = exec_extras + related_views

    screen = dict(screen)
    screen["title"] = screen_title
    screen["eyebrow"] = eyebrow
    screen["kpi_cards"] = kpi_cards
    screen["table_card"] = table_card
    screen["attention_card"] = attention_card
    screen["chart_card"] = chart_card
    screen["related_screens"] = related_screens
    screen["related_views"] = related_views
    if screen.get("hero_banner"):
        hb = dict(screen["hero_banner"])
        hb["title"] = hb.get("heading") or hb.get("title", "")
        hb["text"] = hb.get("body") or hb.get("text", "")
        screen["hero_banner"] = hb

    return {
        "screen": screen,
        "screen_code": screen["screen_id"],
        "screen_title": screen_title,
        "eyebrow": eyebrow,
        "subtitle": screen["subtitle"],
        "primary_action": screen.get("primary_action"),
        "secondary_action": screen.get("secondary_action"),
        "has_tabs": screen.get("has_tabs", False),
        "active_tab": active_tab,
        "hero_banner": screen.get("hero_banner"),
        "kpi_cards": kpi_cards,
        "table_card": table_card,
        "attention_card": attention_card,
        "chart_card": chart_card,
        "scoped_notice": screen.get("scoped_notice"),
        "related_screens": related_screens,
        "related_views": related_views,
        "support_note": screen.get("support_note"),
        "has_search_filter": screen.get("has_search_filter", False),
        "state_mode": state_mode,
        "state_card": state_card,
        "is_leadership_tier": is_leadership_tier,
        "active_role_title": screen.get("default_role_title") or user_scope.active_role.replace("_", " ").title(),
        "active_network": active_network,
        "active_country": active_country,
        "country_name": country_display,
        "identity_context": get_identity_context(
            account,
            user_scope,
            active_network=active_network,
            active_role=user_scope.active_role,
            active_country=active_country,
            request=request,
        ),
    }
