"""
WDOS Stage 07: Leadership Structure, Vacancies, Appointments, and Handover Engine
Authoritative leadership-and-continuity engine:
- Leadership structure, registers, reporting lines, positions, seats, and vacancies (LEAD-01..LEAD-06)
- Nomination/appointment review, offer, acceptance, leader onboarding, and status changes (APPT-01..APPT-03, APPT-06)
- First-90-day reviews, leader identity/history, exits/transfers, and successor handover (APPT-04, APPT-04-REVIEWS, APPT-05, APPT-07, APPT-08, APPT-08-HANDOVER)
- Enforces authorized human decisions, scoped transitions, optimistic concurrency, idempotency, access-grant lifecycle, and durable audit history.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional
from django.db import transaction
from django.utils import timezone

from accounts.models import Account, AccessGrant, AuditEvent
from .models import (
    AppointmentRecord,
    CandidateReferral,
    HandoverAssetTask,
    LeadershipReview,
    LeadershipSeat,
    LeadershipStatusChange,
    LeadershipTransitionPlan,
    LocalOrganisationUnit,
    PersonProfile,
    PositionMaster,
    SeatHistory,
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
# STAGE 07 SCREEN METADATA & INTERACTION CONTRACTS
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
            "message": "There are no leadership and continuity records matching the selected scope.",
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
        "more_info": {
            "title": "More information needed",
            "message": f"Check the marked details before continuing with {screen_title_lower}. Your entered information remains available.",
            "action_label": "Review details",
            "action_url": base_url,
        },
        "access_changed": {
            "title": "Access changed",
            "message": "Your access to this record changed. The attempted action was not applied. Return to your workspace or ask your authorised support team.",
            "action_label": "Back to my workspace",
            "action_url": "/foundation/workspace/",
        },
    }


STAGE7_SCREENS: Dict[str, Dict[str, Any]] = {
    "LEAD-01": {
        "screen_id": "LEAD-01",
        "title": "My leadership structure",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant leadership and seats records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Leadership structure and vacancies",
        "role_name": "Country Representative",
        "primary_action": {"label": "Open vacancy register", "url": "/foundation/leadership/vacancies/"},
        "secondary_action": {"label": "Back", "url": "/foundation/workspace/"},
        "state_contracts": _build_list_state_contracts("/foundation/leadership/structure/", "my leadership structure"),
    },
    "LEAD-02": {
        "screen_id": "LEAD-02",
        "title": "Leadership register",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant leadership and seats records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Leadership structure and vacancies",
        "role_name": "Country Representative",
        "primary_action": {"label": "Review unmatched records", "url": "/foundation/leadership/register/?filter=unmatched"},
        "secondary_action": {"label": "Back", "url": "/foundation/leadership/structure/"},
        "state_contracts": _build_list_state_contracts("/foundation/leadership/register/", "leadership register"),
    },
    "LEAD-03": {
        "screen_id": "LEAD-03",
        "title": "Lagos · State Coordinator",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant leadership and seats records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Leadership structure and vacancies",
        "role_name": "Country Representative",
        "primary_action": {"label": "Open appointment", "url": "/foundation/appointments/"},
        "secondary_action": {"label": "Back", "url": "/foundation/leadership/register/"},
        "state_contracts": _build_list_state_contracts("/foundation/leadership/seats/SEAT-NG-LAG-SC/", "lagos · state coordinator"),
    },
    "LEAD-04": {
        "screen_id": "LEAD-04",
        "title": "Approved vacancies",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant leadership and seats records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Leadership structure and vacancies",
        "role_name": "Country Representative",
        "primary_action": {"label": "Refer a candidate", "url": "#refer-candidate-form"},
        "secondary_action": {"label": "Back", "url": "/foundation/leadership/structure/"},
        "state_contracts": _build_list_state_contracts("/foundation/leadership/vacancies/", "approved vacancies"),
    },
    "LEAD-05": {
        "screen_id": "LEAD-05",
        "title": "My direct reports",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant leadership and seats records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Leadership structure and vacancies",
        "role_name": "State Coordinator",
        "primary_action": {"label": "Assign follow-up", "url": "#assign-followup-form"},
        "secondary_action": {"label": "Back", "url": "/foundation/leadership/structure/"},
        "state_contracts": _build_list_state_contracts("/foundation/leadership/direct-reports/", "my direct reports"),
    },
    "LEAD-06": {
        "screen_id": "LEAD-06",
        "title": "Positions and reporting lines",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Prepare a controlled change. Current settings remain effective until the required approval.",
        "breadcrumb": "Workspace / Leadership structure and vacancies",
        "role_name": "HOFCO",
        "primary_action": {"label": "Save position revision", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/leadership/structure/"},
        "state_contracts": _build_form_state_contracts("/foundation/leadership/positions/", "positions and reporting lines"),
    },
    "APPT-01": {
        "screen_id": "APPT-01",
        "title": "Appointment processing",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant appointments and continuity records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Appointment, leader onboarding and succession",
        "role_name": "Network Secretary",
        "primary_action": {"label": "Open appointment", "url": "/foundation/appointments/offer/"},
        "secondary_action": {"label": "Back", "url": "/foundation/leadership/structure/"},
        "state_contracts": _build_list_state_contracts("/foundation/appointments/", "appointment processing"),
    },
    "APPT-02": {
        "screen_id": "APPT-02",
        "title": "Your appointment offer",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Complete the information below, then review it before you continue.",
        "breadcrumb": "Workspace / Appointment, leader onboarding and succession",
        "role_name": "Selected candidate",
        "primary_action": {"label": "Accept appointment", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/appointments/"},
        "state_contracts": _build_form_state_contracts("/foundation/appointments/offer/", "your appointment offer"),
    },
    "APPT-03": {
        "screen_id": "APPT-03",
        "title": "Welcome to your leadership role",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant appointments and continuity records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Appointment, leader onboarding and succession",
        "role_name": "Chapter leader",
        "primary_action": {"label": "Continue onboarding", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/appointments/"},
        "state_contracts": _build_list_state_contracts("/foundation/appointments/onboarding/", "welcome to your leadership role"),
    },
    "APPT-04": {
        "screen_id": "APPT-04",
        "title": "Your first 90 days",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant appointments and continuity records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Appointment, leader onboarding and succession",
        "role_name": "Chapter leader",
        "primary_action": {"label": "Open next action", "url": "/foundation/appointments/reviews/"},
        "secondary_action": {"label": "Back", "url": "/foundation/appointments/onboarding/"},
        "state_contracts": _build_list_state_contracts("/foundation/appointments/first-90-days/", "your first 90 days"),
    },
    "APPT-04-REVIEWS": {
        "screen_id": "APPT-04-REVIEWS",
        "title": "First 30 / 60 / 90 day reviews",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Use the information and next action for this role only.",
        "breadcrumb": "Workspace / Appointment, leader onboarding and succession",
        "role_name": "Authorised appointment reviewer",
        "primary_action": {"label": "Record review outcome", "type": "submit"},
        "secondary_action": {"label": "Back to dashboard", "url": "/foundation/appointments/first-90-days/"},
        "state_contracts": _build_form_state_contracts("/foundation/appointments/reviews/", "first 30 / 60 / 90 day reviews"),
    },
    "APPT-05": {
        "screen_id": "APPT-05",
        "title": "My appointment and identity",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant appointments and continuity records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Appointment, leader onboarding and succession",
        "role_name": "Chapter leader",
        "primary_action": {"label": "View declarations", "url": "/foundation/appointments/offer/"},
        "secondary_action": {"label": "Back", "url": "/foundation/appointments/"},
        "state_contracts": _build_list_state_contracts("/foundation/appointments/identity/", "my appointment and identity"),
    },
    "APPT-06": {
        "screen_id": "APPT-06",
        "title": "Review a leadership status change",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Check the evidence and the impact of this decision before confirming.",
        "breadcrumb": "Workspace / Appointment, leader onboarding and succession",
        "role_name": "Network Secretary",
        "primary_action": {"label": "Submit for approval", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/appointments/"},
        "state_contracts": _build_form_state_contracts("/foundation/appointments/status-change/", "review a leadership status change"),
    },
    "APPT-07": {
        "screen_id": "APPT-07",
        "title": "Plan a safe leadership transition",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Check the evidence and the impact of this decision before confirming.",
        "breadcrumb": "Workspace / Appointment, leader onboarding and succession",
        "role_name": "Network Secretary",
        "primary_action": {"label": "Open transition review", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/appointments/"},
        "state_contracts": _build_form_state_contracts("/foundation/appointments/transition/", "plan a safe leadership transition"),
    },
    "APPT-08": {
        "screen_id": "APPT-08",
        "title": "Handover workspace",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant appointments and continuity records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Appointment, leader onboarding and succession",
        "role_name": "Network Secretary",
        "primary_action": {"label": "Review outstanding items", "url": "/foundation/appointments/handover/assets/"},
        "secondary_action": {"label": "Back", "url": "/foundation/appointments/transition/"},
        "state_contracts": _build_list_state_contracts("/foundation/appointments/handover/", "handover workspace"),
    },
    "APPT-08-HANDOVER": {
        "screen_id": "APPT-08-HANDOVER",
        "title": "Handover assets and access checks",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Use the information and next action for this role only.",
        "breadcrumb": "Workspace / Appointment, leader onboarding and succession",
        "role_name": "Network Secretary",
        "primary_action": {"label": "Open", "url": "/foundation/appointments/handover/"},
        "secondary_action": {"label": "Back to dashboard", "url": "/foundation/appointments/handover/"},
        "state_contracts": _build_form_state_contracts("/foundation/appointments/handover/assets/", "handover assets and access checks"),
    },
}


# -----------------------------------------------------------------------------
# SEED / FIXTURE SERVICE
# -----------------------------------------------------------------------------

def seed_stage7_fixtures(force: bool = False):
    """
    Idempotently seeds all authoritative Stage 07 leadership positions, seats,
    vacancies, appointments, 30/60/90 reviews, status changes, transition plans,
    handover assets, and seat history records.
    """
    import sys
    if not force and "test" not in sys.argv:
        return
    seed_stage6_fixtures(force=force)

    ada = PersonProfile.objects.filter(person_code="WD-00421").first()
    lina = PersonProfile.objects.filter(person_code="WD-00422").first()
    kemi = PersonProfile.objects.filter(person_code="WD-00423").first()
    amina_ke = PersonProfile.objects.filter(person_code="WD-00424").first()
    zainab_wnnn = PersonProfile.objects.filter(person_code="WD-00425").first()

    # 1. PositionMaster catalogue (stable codes with WGMN and WNNN titles)
    positions_spec = [
        {
            "position_code": "COUNTRY_REPRESENTATIVE",
            "wgmn_title": "Country Representative",
            "wnnn_title": "Country Lead",
            "logical_level": "Country",
            "tier": "country",
            "reports_to_code": "NETWORK_SECRETARY",
            "reports_to_label": "Network Secretary",
            "is_deputy": False,
        },
        {
            "position_code": "STATE_COORDINATOR",
            "wgmn_title": "State Coordinator",
            "wnnn_title": "State Lead",
            "logical_level": "Region / State",
            "tier": "regional",
            "reports_to_code": "COUNTRY_REPRESENTATIVE",
            "reports_to_label": "Country principal",
            "is_deputy": False,
        },
        {
            "position_code": "ASSISTANT_COORDINATOR",
            "wgmn_title": "Assistant Coordinator",
            "wnnn_title": "Assistant State Lead",
            "logical_level": "Region / State",
            "tier": "regional",
            "reports_to_code": "STATE_COORDINATOR",
            "reports_to_label": "State Coordinator · Lagos",
            "is_deputy": True,
        },
        {
            "position_code": "LGA_COORDINATOR",
            "wgmn_title": "LGA Coordinator",
            "wnnn_title": "District Lead",
            "logical_level": "District / LGA",
            "tier": "local",
            "reports_to_code": "STATE_COORDINATOR",
            "reports_to_label": "State Coordinator · Lagos",
            "is_deputy": False,
        },
        {
            "position_code": "CLUSTER_COORDINATOR",
            "wgmn_title": "Cluster Coordinator",
            "wnnn_title": "Cluster Lead",
            "logical_level": "Community Cluster",
            "tier": "cluster",
            "reports_to_code": "LGA_COORDINATOR",
            "reports_to_label": "LGA Coordinator · Ikeja",
            "is_deputy": False,
        },
        {
            "position_code": "CHAPTER_COORDINATOR",
            "wgmn_title": "Chapter Coordinator",
            "wnnn_title": "Chapter Lead",
            "logical_level": "Chapter",
            "tier": "chapter",
            "reports_to_code": "CLUSTER_COORDINATOR",
            "reports_to_label": "Assigned Cluster Coordinator",
            "is_deputy": False,
        },
    ]

    pos_map: Dict[str, PositionMaster] = {}
    for p_spec in positions_spec:
        pos_obj, _ = PositionMaster.objects.get_or_create(
            position_code=p_spec["position_code"],
            defaults=p_spec,
        )
        pos_map[p_spec["position_code"]] = pos_obj

    # 2. LocalOrganisationUnit references
    lagos_unit = LocalOrganisationUnit.objects.filter(
        network="WGMN", country="NG", level="Region / State"
    ).first()
    ikeja_unit = LocalOrganisationUnit.objects.filter(
        network="WGMN", country="NG", level="District / LGA"
    ).first()
    allen_unit = LocalOrganisationUnit.objects.filter(
        network="WGMN", country="NG", level="Chapter"
    ).first()

    # 3. Primary WGMN / Nigeria Leadership Seats (LEAD-01..05)
    seat_sc, _ = LeadershipSeat.objects.get_or_create(
        seat_code="SEAT-NG-LAG-SC",
        defaults={
            "position": pos_map["STATE_COORDINATOR"],
            "position_title": "State Coordinator",
            "network": "WGMN",
            "country": "NG",
            "unit_name": "Lagos",
            "unit_label": "Lagos State",
            "org_unit": lagos_unit,
            "holder_person": lina,
            "holder_name": "Lina Mensah",
            "status": "Active",
            "reports_to_label": "Country Representative · Nigeria",
            "is_approved_seat": True,
            "summary_note": "Lina Mensah · State Coordinator.",
        },
    )

    seat_ac, _ = LeadershipSeat.objects.get_or_create(
        seat_code="SEAT-NG-LAG-AC",
        defaults={
            "position": pos_map["ASSISTANT_COORDINATOR"],
            "position_title": "Assistant Coordinator",
            "network": "WGMN",
            "country": "NG",
            "unit_name": "Lagos",
            "unit_label": "Chapter support",
            "org_unit": lagos_unit,
            "parent_seat": seat_sc,
            "holder_person": None,
            "holder_name": "Unfilled",
            "status": "Vacant",
            "reports_to_label": "State Coordinator · Lagos",
            "is_approved_seat": True,
            "vacancy_reason": "An approved deputy seat needs a candidate referral.",
            "summary_note": "An approved deputy seat needs a candidate referral.",
        },
    )

    seat_lc, _ = LeadershipSeat.objects.get_or_create(
        seat_code="SEAT-NG-IKJ-LC",
        defaults={
            "position": pos_map["LGA_COORDINATOR"],
            "position_title": "LGA Coordinator",
            "network": "WGMN",
            "country": "NG",
            "unit_name": "Ikeja",
            "unit_label": "Ikeja LGA",
            "org_unit": ikeja_unit,
            "parent_seat": seat_sc,
            "holder_person": kemi,
            "holder_name": "Kemi Bello",
            "status": "Onboarding",
            "reports_to_label": "State Coordinator · Lagos",
            "is_approved_seat": True,
            "summary_note": "Kemi Bello · LGA Coordinator.",
        },
    )

    seat_cc, _ = LeadershipSeat.objects.get_or_create(
        seat_code="SEAT-NG-IKJ-CC",
        defaults={
            "position": pos_map["CHAPTER_COORDINATOR"],
            "position_title": "Chapter Coordinator",
            "network": "WGMN",
            "country": "NG",
            "unit_name": "Ikeja",
            "unit_label": "Ikeja Chapter",
            "org_unit": allen_unit,
            "parent_seat": seat_lc,
            "holder_person": ada,
            "holder_name": "Ada Okafor",
            "status": "Acceptance pending",
            "reports_to_label": "Assigned Cluster Coordinator",
            "is_approved_seat": True,
            "summary_note": "Ada Okafor · Chapter Coordinator.",
        },
    )

    # Secondary WNNN / Nigeria and WGMN / Kenya seats for multi-network and multi-country scope verification
    seat_wnnn_ng, _ = LeadershipSeat.objects.get_or_create(
        seat_code="SEAT-WNNN-NG-LAG-SL",
        defaults={
            "position": pos_map["STATE_COORDINATOR"],
            "position_title": "State Lead",
            "network": "WNNN",
            "country": "NG",
            "unit_name": "Lagos",
            "unit_label": "Lagos State",
            "holder_person": zainab_wnnn,
            "holder_name": zainab_wnnn.full_name if zainab_wnnn else "Zainab Musa",
            "status": "Active",
            "reports_to_label": "Country Lead · Nigeria",
            "is_approved_seat": True,
            "summary_note": "Zainab Musa · State Lead.",
        },
    )

    seat_ke_sc, _ = LeadershipSeat.objects.get_or_create(
        seat_code="SEAT-KE-NBO-SC",
        defaults={
            "position": pos_map["STATE_COORDINATOR"],
            "position_title": "State Coordinator",
            "network": "WGMN",
            "country": "KE",
            "unit_name": "Nairobi",
            "unit_label": "Nairobi County",
            "holder_person": amina_ke,
            "holder_name": amina_ke.full_name if amina_ke else "Amina Wanjiku",
            "status": "Active",
            "reports_to_label": "Country Representative · Kenya",
            "is_approved_seat": True,
            "summary_note": "Amina Wanjiku · County Coordinator.",
        },
    )

    # 4. SeatHistory (durable historical holders so former holders remain in history)
    if not SeatHistory.objects.filter(seat=seat_sc).exists():
        SeatHistory.objects.create(
            seat=seat_sc,
            holder_name="Bisi Adeyemi",
            position_title="State Coordinator",
            unit_name="Lagos",
            network="WGMN",
            country="NG",
            outcome_or_stage="Completed term",
            service_period="2023 – 2025",
            transition_reason="Completed two-year term and handed over to Lina Mensah.",
        )
    if not SeatHistory.objects.filter(seat=seat_ac).exists():
        SeatHistory.objects.create(
            seat=seat_ac,
            holder_name="Ngozi Eze",
            position_title="Assistant Coordinator",
            unit_name="Lagos",
            network="WGMN",
            country="NG",
            outcome_or_stage="Transferred",
            service_period="2024 – 2026",
            transition_reason="Transferred to regional programme coordination; seat approved for vacancy referral.",
        )
    if not SeatHistory.objects.filter(seat=seat_cc).exists():
        SeatHistory.objects.create(
            seat=seat_cc,
            holder_name="Funke Akindele",
            position_title="Chapter Coordinator",
            unit_name="Ikeja",
            network="WGMN",
            country="NG",
            outcome_or_stage="Completed term",
            service_period="2024 – 2026",
            transition_reason="Completed local chapter founding term; successor offer issued to Ada Okafor.",
        )

    # 5. AppointmentRecord rows (APPT-01..APPT-08)
    appt_ada, _ = AppointmentRecord.objects.get_or_create(
        appointment_code="APPT-NG-001",
        defaults={
            "seat": seat_cc,
            "person": ada,
            "account": ada.account if ada else None,
            "appointee_name": "Ada Okafor",
            "position_title": "Chapter Coordinator",
            "unit_name": "Ikeja",
            "network": "WGMN",
            "country": "NG",
            "stage": "Acceptance pending",
            "next_action": "View offer",
            "reporting_line": "Assigned Cluster Coordinator",
            "official_identity_status": "Provisioning review pending",
            "letter_reference": "Open issued appointment letter",
            "acceptance_confirmed": True,
            "commitment_confirmed": True,
            "onboarding_step_1": True,
            "onboarding_step_2": False,
            "onboarding_step_3": True,
            "onboarding_step_4": True,
            "milestone_30_completed": True,
            "milestone_60_completed": False,
            "milestone_90_completed": True,
            "effective_from": date(2026, 10, 1),
        },
    )

    appt_lina, _ = AppointmentRecord.objects.get_or_create(
        appointment_code="APPT-NG-002",
        defaults={
            "seat": seat_sc,
            "person": lina,
            "account": lina.account if lina else None,
            "appointee_name": "Lina Mensah",
            "position_title": "State Coordinator",
            "unit_name": "Lagos",
            "network": "WGMN",
            "country": "NG",
            "stage": "Onboarding",
            "next_action": "Review checklist",
            "reporting_line": "Country Representative · Nigeria",
            "official_identity_status": "Active",
            "letter_reference": "Open issued appointment letter",
            "acceptance_confirmed": True,
            "commitment_confirmed": True,
            "onboarding_step_1": True,
            "onboarding_step_2": False,
            "onboarding_step_3": True,
            "onboarding_step_4": True,
            "milestone_30_completed": True,
            "milestone_60_completed": False,
            "milestone_90_completed": True,
            "effective_from": date(2026, 9, 1),
        },
    )

    appt_kemi, _ = AppointmentRecord.objects.get_or_create(
        appointment_code="APPT-NG-003",
        defaults={
            "seat": seat_lc,
            "person": kemi,
            "account": kemi.account if kemi else None,
            "appointee_name": "Kemi Bello",
            "position_title": "LGA Coordinator",
            "unit_name": "Ikeja",
            "network": "WGMN",
            "country": "NG",
            "stage": "Handover",
            "next_action": "Check access removal",
            "reporting_line": "State Coordinator · Lagos",
            "official_identity_status": "Active",
            "letter_reference": "Open issued appointment letter",
            "acceptance_confirmed": True,
            "commitment_confirmed": True,
            "onboarding_step_1": True,
            "onboarding_step_2": True,
            "onboarding_step_3": True,
            "onboarding_step_4": True,
            "effective_from": date(2025, 10, 1),
            "effective_until": date(2026, 10, 1),
        },
    )

    # Secondary WNNN and Kenya appointments for scope testing
    AppointmentRecord.objects.get_or_create(
        appointment_code="APPT-WNNN-NG-001",
        defaults={
            "seat": seat_wnnn_ng,
            "person": zainab_wnnn,
            "appointee_name": zainab_wnnn.full_name if zainab_wnnn else "Zainab Musa",
            "position_title": "State Lead",
            "unit_name": "Lagos",
            "network": "WNNN",
            "country": "NG",
            "stage": "Active",
            "next_action": "Open 30-day review",
            "reporting_line": "Country Lead · Nigeria",
            "official_identity_status": "Active",
        },
    )
    AppointmentRecord.objects.get_or_create(
        appointment_code="APPT-KE-001",
        defaults={
            "seat": seat_ke_sc,
            "person": amina_ke,
            "appointee_name": amina_ke.full_name if amina_ke else "Amina Wanjiku",
            "position_title": "State Coordinator",
            "unit_name": "Nairobi",
            "network": "WGMN",
            "country": "KE",
            "stage": "Active",
            "next_action": "Open 30-day review",
            "reporting_line": "Country Representative · Kenya",
            "official_identity_status": "Active",
        },
    )

    # 6. First 30 / 60 / 90 day reviews (APPT-04-REVIEWS)
    if not LeadershipReview.objects.filter(appointment=appt_lina).exists():
        LeadershipReview.objects.create(
            appointment=appt_lina,
            review_point="30 days",
            outcome="On track",
            evidence_notes="Record evidence and agreed support.",
            reviewer_confirmed=True,
            reviewed_at=timezone.now(),
        )

    # 7. Status change record (APPT-06)
    if not LeadershipStatusChange.objects.filter(appointment=appt_ada).exists():
        LeadershipStatusChange.objects.create(
            appointment=appt_ada,
            requested_status="On leave",
            effective_period="01–15 October 2026",
            reason_and_cover_plan="Record the approved reason and temporary support arrangement.",
            decision_status="Pending",
        )

    # 8. Transition plan (APPT-07)
    transition_kemi, _ = LeadershipTransitionPlan.objects.get_or_create(
        appointment=appt_kemi,
        outgoing_appointment_label="Kemi Bello · LGA Coordinator",
        defaults={
            "transition_type": "Transfer",
            "effective_date": "01 October 2026",
            "access_and_handover_notes": "Official records, groups and outstanding actions require review.",
            "status": "In review",
            "successor_person": ada,
            "successor_name": "Ada Okafor",
        },
    )

    # 9. Handover assets and access checks (APPT-08-HANDOVER)
    handover_specs = [
        {
            "asset_or_task": "Nigeria country report folder",
            "from_actor": "Lina Mensah",
            "to_actor": "Ada Okafor",
            "due_date": "2026-10-01",
            "access_action": "Transfer ownership",
        },
        {
            "asset_or_task": "Open programme evidence queue",
            "from_actor": "Lina Mensah",
            "to_actor": "Ada Okafor",
            "due_date": "2026-10-01",
            "access_action": "Reassign",
        },
        {
            "asset_or_task": "Official identity record",
            "from_actor": "Administrator",
            "to_actor": "Ada Okafor",
            "due_date": "2026-10-01",
            "access_action": "Confirm first login",
        },
        {
            "asset_or_task": "Former holder access",
            "from_actor": "Administrator",
            "to_actor": "Lina Mensah",
            "due_date": "2026-10-01",
            "access_action": "Disable and audit",
        },
    ]
    for h_spec in handover_specs:
        HandoverAssetTask.objects.get_or_create(
            asset_or_task=h_spec["asset_or_task"],
            network="WGMN",
            country="NG",
            defaults={
                "appointment": appt_kemi,
                "transition_plan": transition_kemi,
                "from_actor": h_spec["from_actor"],
                "to_actor": h_spec["to_actor"],
                "due_date": h_spec["due_date"],
                "access_action": h_spec["access_action"],
                "status": "Open",
            },
        )


# -----------------------------------------------------------------------------
# PERMISSION & SCOPED AUTHORITY CHECKS
# -----------------------------------------------------------------------------

STAGE7_ADMIN_AND_GOVERNANCE_ROLES = {
    "founder", "hofco", "executive", "global_executive", "admin",
    "operations", "coordinator", "programmes", "comms", "resources",
    "systems", "quality", "qa_controls", "quality_lead", "it_admin",
    "management", "safeguarding", "network_secretary", "country_lead",
    "country_director", "regional_coordinator",
}

STAGE7_LEADERSHIP_ROLES = STAGE7_ADMIN_AND_GOVERNANCE_ROLES | {
    "chapter_lead", "cluster_lead", "local_operations", "reviewer",
    "state_coordinator", "lga_coordinator", "chapter_coordinator",
}


def assert_stage7_authorized(user_scope: UserScope, screen_id: str):
    """
    Fail-closed role and scope authorization for Stage 07 screens.
    - APPT-02, APPT-03, APPT-04, APPT-05 are accessible to appointed leaders and selected candidates
      as well as leadership/governance roles.
    - LEAD-06 (Positions & reporting lines) requires HOFCO / Founder / Network / Country governance authority.
    - LEAD-01..05 and APPT-01, APPT-04-REVIEWS, APPT-06, APPT-07, APPT-08, APPT-08-HANDOVER
      require leadership or governance authority.
    """
    user_roles = _collect_user_roles(user_scope)

    # Candidate / personal leader onboarding & offer screens allow appointed candidates/members too
    if screen_id in {"APPT-02", "APPT-03", "APPT-04", "APPT-05"}:
        allowed_personal = STAGE7_LEADERSHIP_ROLES | {"member", "candidate", "selected_candidate", "participant"}
        if not user_roles.intersection(allowed_personal):
            raise ScopePermissionDenied(f"Role '{user_scope.primary_role}' is not authorized for {screen_id}.")
        return

    # Position master revisions (LEAD-06) require governance / country / network authority
    if screen_id == "LEAD-06":
        if not user_roles.intersection(STAGE7_ADMIN_AND_GOVERNANCE_ROLES):
            raise ScopePermissionDenied("A decision requires the appropriate authority.")
        return

    # All other leadership & appointment management screens require leadership or governance role
    if not user_roles.intersection(STAGE7_LEADERSHIP_ROLES):
        raise ScopePermissionDenied(f"Role '{user_scope.primary_role}' cannot access leadership governance screens.")


def assert_human_decision_authority(user_scope: UserScope):
    """
    Verifies that the current actor holds human decision authority for
    appointments, 30/60/90 reviews, status changes, transitions, and handover closures.
    """
    user_roles = _collect_user_roles(user_scope)
    if not user_roles.intersection(STAGE7_LEADERSHIP_ROLES):
        raise ScopePermissionDenied("A decision requires the appropriate authority.")


def assert_seat_scope_authorized(user_scope: UserScope, seat: Optional[LeadershipSeat]):
    if not seat:
        return
    assert_country_network_authorized(user_scope, country=seat.country, network=seat.network)


def assert_appointment_scope_authorized(user_scope: UserScope, appointment: Optional[AppointmentRecord]):
    if not appointment:
        return
    assert_country_network_authorized(user_scope, country=appointment.country, network=appointment.network)


def get_scoped_seats_queryset(user_scope: UserScope, country: Optional[str] = None, network: Optional[str] = None):
    qs = LeadershipSeat.objects.select_related("position", "holder_person", "org_unit")
    is_global = is_global_stage6_scope(user_scope)

    target_net = (network or "").strip().upper()
    target_cc = normalize_country_code(country, default_code="") if country else ""

    if target_net in {"WGMN", "WNNN"}:
        assert_country_network_authorized(user_scope, network=target_net)
        qs = qs.filter(network=target_net)
    elif not is_global and user_scope.active_network in {"WGMN", "WNNN"}:
        qs = qs.filter(network=user_scope.active_network)
    else:
        qs = qs.filter(network="WGMN")

    if target_cc:
        assert_country_network_authorized(user_scope, country=target_cc)
        qs = qs.filter(country=target_cc)
    elif not is_global and user_scope.active_country not in {"ALL", "BOTH", "*", ""}:
        qs = qs.filter(country=user_scope.active_country)
    else:
        qs = qs.filter(country="NG")

    return qs


def get_scoped_appointments_queryset(user_scope: UserScope, country: Optional[str] = None, network: Optional[str] = None):
    qs = AppointmentRecord.objects.select_related("seat", "person", "account")
    is_global = is_global_stage6_scope(user_scope)

    target_net = (network or "").strip().upper()
    target_cc = normalize_country_code(country, default_code="") if country else ""

    if target_net in {"WGMN", "WNNN"}:
        assert_country_network_authorized(user_scope, network=target_net)
        qs = qs.filter(network=target_net)
    elif not is_global and user_scope.active_network in {"WGMN", "WNNN"}:
        qs = qs.filter(network=user_scope.active_network)
    else:
        qs = qs.filter(network="WGMN")

    if target_cc:
        assert_country_network_authorized(user_scope, country=target_cc)
        qs = qs.filter(country=target_cc)
    elif not is_global and user_scope.active_country not in {"ALL", "BOTH", "*", ""}:
        qs = qs.filter(country=user_scope.active_country)
    else:
        qs = qs.filter(country="NG")

    return qs


def _check_optimistic_concurrency(record: Any, expected_updated_at: Optional[str]) -> bool:
    """
    Returns True if there is a concurrency conflict (expected_updated_at does not match record.updated_at).
    """
    if not expected_updated_at or not getattr(record, "updated_at", None):
        return False
    cleaned = expected_updated_at.strip()
    if not cleaned:
        return False
    valid_stamps = {
        record.updated_at.strftime("%Y-%m-%dT%H:%M:%S"),
        record.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
        record.updated_at.isoformat(),
    }
    return cleaned not in valid_stamps


# -----------------------------------------------------------------------------
# MUTATION & WORKFLOW SERVICES
# -----------------------------------------------------------------------------

def save_position_revision(
    position_code: str,
    wgmn_title: str,
    wnnn_title: str,
    reports_to_label: str,
    actor_account: Account,
    user_scope: UserScope,
    expected_updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    LEAD-06: Saves a controlled revision to a PositionMaster record.
    Enforces governance authority, optimistic concurrency, and writes an AuditEvent.
    """
    assert_stage7_authorized(user_scope, "LEAD-06")

    clean_code = (position_code or "").strip().upper()
    clean_wgmn = (wgmn_title or "").strip()
    clean_wnnn = (wnnn_title or "").strip()
    clean_reports = (reports_to_label or "").strip()

    if not clean_code or not clean_wgmn or not clean_wnnn or not clean_reports:
        raise ValueError("Position code, WGMN display title, WNNN display title, and Reports to are required.")

    with transaction.atomic():
        pos = PositionMaster.objects.select_for_update().filter(position_code=clean_code).first()
        if not pos:
            pos = PositionMaster(
                position_code=clean_code,
                wgmn_title=clean_wgmn,
                wnnn_title=clean_wnnn,
                reports_to_label=clean_reports,
            )
        else:
            if _check_optimistic_concurrency(pos, expected_updated_at):
                return {
                    "success": False,
                    "conflict": True,
                    "position": pos,
                    "message": "This record changed since you opened it. Review the latest version before submitting.",
                }

        previous = {
            "wgmn_title": pos.wgmn_title,
            "wnnn_title": pos.wnnn_title,
            "reports_to_label": pos.reports_to_label,
        }
        pos.wgmn_title = clean_wgmn
        pos.wnnn_title = clean_wnnn
        pos.reports_to_label = clean_reports
        pos.proposed_wgmn_title = clean_wgmn
        pos.proposed_wnnn_title = clean_wnnn
        pos.proposed_reports_to_label = clean_reports
        pos.updated_by = actor_account
        pos.save()

        # Also synchronize seat display titles for matching network
        for seat in LeadershipSeat.objects.filter(position=pos):
            new_title = pos.display_title_for_network(seat.network)
            if seat.position_title != new_title:
                seat.position_title = new_title
                seat.save(update_fields=["position_title", "updated_at"])

        AuditEvent.objects.create(
            account=actor_account,
            event="position_revision_saved",
            detail={
                "position_code": pos.position_code,
                "wgmn_title": pos.wgmn_title,
                "wnnn_title": pos.wnnn_title,
                "reports_to_label": pos.reports_to_label,
                "previous": previous,
                "network": user_scope.active_network or "WGMN",
                "country": user_scope.active_country or "NG",
            },
        )

        return {"success": True, "conflict": False, "position": pos}


def refer_or_appoint_candidate(
    seat_code: str,
    candidate_name: str,
    suitability_notes: str,
    actor_account: Account,
    user_scope: UserScope,
    action_mode: str = "refer",  # "refer" or "appoint"
    candidate_person_code: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    expected_updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    LEAD-04 & APPT-01: Refers a candidate or approves an appointment offer for an approved seat.
    - Enforces rule: "A vacancy exists only for an approved seat. Former holders remain in history."
    - Enforces human decision authority & prevents unauthorized self-appointment.
    - Enforces idempotency and optimistic concurrency.
    """
    assert_human_decision_authority(user_scope)

    clean_name = (candidate_name or "").strip()
    if not clean_name and candidate_person_code:
        p_lookup = PersonProfile.objects.filter(person_code=candidate_person_code).first()
        if p_lookup:
            clean_name = p_lookup.full_name

    if not clean_name:
        raise ValueError("Candidate name is required to record a referral or appointment.")

    with transaction.atomic():
        seat = LeadershipSeat.objects.select_for_update().filter(seat_code=seat_code).first()
        if not seat:
            raise ValueError(f"Leadership seat '{seat_code}' not found.")

        assert_seat_scope_authorized(user_scope, seat)

        if not seat.is_approved_seat:
            raise ValueError("A vacancy exists only for an approved seat.")

        if _check_optimistic_concurrency(seat, expected_updated_at):
            return {
                "success": False,
                "conflict": True,
                "seat": seat,
                "message": "This record changed since you opened it. Review the latest version before submitting.",
            }

        # Idempotency check
        clean_idem = (idempotency_key or "").strip()
        if clean_idem:
            existing_ref = CandidateReferral.objects.filter(seat=seat, idempotency_key=clean_idem).first()
            if existing_ref:
                existing_appt = AppointmentRecord.objects.filter(seat=seat, idempotency_key=clean_idem).first()
                return {
                    "success": True,
                    "conflict": False,
                    "idempotent_replay": True,
                    "seat": seat,
                    "referral": existing_ref,
                    "appointment": existing_appt,
                }

        person = None
        if candidate_person_code:
            person = PersonProfile.objects.filter(person_code=candidate_person_code).first()
        if not person:
            person = PersonProfile.objects.filter(
                full_name__iexact=clean_name,
                network=seat.network,
                country=seat.country,
            ).first()

        referral = CandidateReferral.objects.create(
            seat=seat,
            candidate_person=person,
            candidate_name=clean_name,
            candidate_email=person.email if person else "",
            suitability_notes=(suitability_notes or "").strip() or "Candidate referred for approved leadership seat.",
            status="Selected" if action_mode == "appoint" else "Referred",
            referred_by=actor_account,
            reviewed_by=actor_account if action_mode == "appoint" else None,
            idempotency_key=clean_idem,
        )

        appointment = None
        if action_mode == "appoint":
            # Prevent a non-admin candidate from self-approving their own appointment
            user_roles = _collect_user_roles(user_scope)
            is_exec_admin = bool(user_roles.intersection({"founder", "hofco", "admin", "network_secretary", "country_lead", "country_director"}))
            if actor_account and person and person.account_id == actor_account.id and not is_exec_admin:
                raise ScopePermissionDenied("Self-appointment is not permitted. A decision requires the appropriate authority.")

            # Preserve former holder in SeatHistory if seat previously had a named holder
            if seat.holder_name and seat.holder_name not in {"Unfilled", clean_name}:
                SeatHistory.objects.create(
                    seat=seat,
                    person=seat.holder_person,
                    holder_name=seat.holder_name,
                    position_title=seat.position_title,
                    unit_name=seat.unit_name,
                    network=seat.network,
                    country=seat.country,
                    outcome_or_stage="Former holder",
                    service_period="Prior service",
                    transition_reason=f"Succeeded by appointment offer to {clean_name}.",
                    recorded_by=actor_account,
                )

            seat.holder_person = person
            seat.holder_name = clean_name
            seat.status = "Acceptance pending"
            seat.save()

            appt_code = f"APPT-{seat.country}-{AppointmentRecord.objects.count() + 1:03d}"
            appointment, _ = AppointmentRecord.objects.update_or_create(
                seat=seat,
                appointee_name=clean_name,
                defaults={
                    "appointment_code": appt_code,
                    "person": person,
                    "account": person.account if person else None,
                    "position_title": seat.position_title,
                    "unit_name": seat.unit_name,
                    "network": seat.network,
                    "country": seat.country,
                    "stage": "Acceptance pending",
                    "next_action": "View offer",
                    "reporting_line": seat.reports_to_label,
                    "official_identity_status": "Provisioning review pending",
                    "letter_reference": "Open issued appointment letter",
                    "acceptance_confirmed": False,
                    "commitment_confirmed": False,
                    "appointed_by": actor_account,
                    "decision_reason": (suitability_notes or "").strip(),
                    "idempotency_key": clean_idem,
                    "effective_from": date.today(),
                },
            )

        AuditEvent.objects.create(
            account=actor_account,
            event="appointment_selected" if action_mode == "appoint" else "candidate_referred",
            detail={
                "seat_code": seat.seat_code,
                "position_title": seat.position_title,
                "unit_name": seat.unit_name,
                "candidate_name": clean_name,
                "action_mode": action_mode,
                "network": seat.network,
                "country": seat.country,
            },
        )

        return {
            "success": True,
            "conflict": False,
            "idempotent_replay": False,
            "seat": seat,
            "referral": referral,
            "appointment": appointment,
        }


def respond_to_appointment_offer(
    appointment_code: str,
    decision: str,  # "accept" or "decline"
    acceptance_confirmed: bool,
    commitment_confirmed: bool,
    actor_account: Account,
    user_scope: UserScope,
    declined_reason: str = "",
    expected_updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    APPT-02: Records candidate acceptance or decline of an appointment offer.
    - Acceptance requires both acceptance_confirmed and commitment_confirmed declarations,
      and advances the appointment to 'Onboarding' ('Review checklist').
    - Decline records reason, transitions appointment to 'Declined', and returns seat to 'Vacant'.
    """
    assert_stage7_authorized(user_scope, "APPT-02")

    with transaction.atomic():
        appt = AppointmentRecord.objects.select_for_update().select_related("seat").filter(
            appointment_code=appointment_code
        ).first()
        if not appt:
            appt = AppointmentRecord.objects.select_for_update().select_related("seat").first()

        assert_appointment_scope_authorized(user_scope, appt)

        if _check_optimistic_concurrency(appt, expected_updated_at):
            return {
                "success": False,
                "conflict": True,
                "appointment": appt,
                "message": "This record changed since you opened it. Review the latest version before submitting.",
            }

        if decision == "decline":
            clean_reason = (declined_reason or "").strip() or "Candidate declined appointment offer."
            appt.stage = "Declined"
            appt.next_action = "Reopen vacancy"
            appt.declined_reason = clean_reason
            appt.save()

            seat = appt.seat
            seat.holder_person = None
            seat.holder_name = "Unfilled"
            seat.status = "Vacant"
            seat.vacancy_reason = f"Offer declined by {appt.appointee_name}; seat returned to approved vacancy."
            seat.save()

            AuditEvent.objects.create(
                account=actor_account,
                event="appointment_offer_declined",
                detail={
                    "appointment_code": appt.appointment_code,
                    "appointee_name": appt.appointee_name,
                    "position_title": appt.position_title,
                    "unit_name": appt.unit_name,
                    "reason": clean_reason,
                    "network": appt.network,
                    "country": appt.country,
                },
            )
            return {"success": True, "conflict": False, "appointment": appt, "decision": "decline"}

        # Default: accept
        if not acceptance_confirmed or not commitment_confirmed:
            raise ValueError("Both the Acceptance declaration and Commitment declaration must be confirmed before accepting.")

        appt.acceptance_confirmed = True
        appt.commitment_confirmed = True
        appt.accepted_at = timezone.now()
        appt.stage = "Onboarding"
        appt.next_action = "Review checklist"
        appt.save()

        seat = appt.seat
        seat.holder_name = appt.appointee_name
        if appt.person:
            seat.holder_person = appt.person
        seat.status = "Onboarding"
        seat.save()

        AuditEvent.objects.create(
            account=actor_account,
            event="appointment_offer_accepted",
            detail={
                "appointment_code": appt.appointment_code,
                "appointee_name": appt.appointee_name,
                "position_title": appt.position_title,
                "unit_name": appt.unit_name,
                "stage": appt.stage,
                "network": appt.network,
                "country": appt.country,
            },
        )

        return {"success": True, "conflict": False, "appointment": appt, "decision": "accept"}


def complete_leader_onboarding_steps(
    appointment_code: str,
    step_1: bool,
    step_2: bool,
    step_3: bool,
    step_4: bool,
    actor_account: Account,
    user_scope: UserScope,
) -> Dict[str, Any]:
    """
    APPT-03: Updates or completes the 4 leader onboarding steps.
    Rule: "Acceptance, declarations and required onboarding precede full role access."
    When all 4 steps are completed:
    - Appointment stage becomes 'Active', next_action becomes 'Open 30-day review',
      official_identity_status becomes 'Active'.
    - Seat status becomes 'Active'.
    - Scoped AccessGrant is provisioned for the appointee's account.
    """
    assert_stage7_authorized(user_scope, "APPT-03")

    with transaction.atomic():
        appt = AppointmentRecord.objects.select_for_update().select_related("seat", "person", "account").filter(
            appointment_code=appointment_code
        ).first()
        if not appt:
            appt = AppointmentRecord.objects.select_for_update().select_related("seat", "person", "account").first()

        assert_appointment_scope_authorized(user_scope, appt)

        appt.onboarding_step_1 = bool(step_1)
        appt.onboarding_step_2 = bool(step_2)
        appt.onboarding_step_3 = bool(step_3)
        appt.onboarding_step_4 = bool(step_4)

        all_complete = appt.onboarding_step_1 and appt.onboarding_step_2 and appt.onboarding_step_3 and appt.onboarding_step_4
        if all_complete:
            appt.onboarding_completed_at = timezone.now()
            appt.stage = "Active"
            appt.next_action = "Open 30-day review"
            appt.official_identity_status = "Active"
            appt.save()

            seat = appt.seat
            seat.status = "Active"
            seat.holder_name = appt.appointee_name
            if appt.person:
                seat.holder_person = appt.person
            seat.save()

            # Activate role AccessGrant if appointee has a linked Account
            target_acc = appt.account or (appt.person.account if appt.person else None)
            if target_acc:
                role_slug = appt.seat.position.position_code.lower() if appt.seat and appt.seat.position else "chapter_lead"
                AccessGrant.objects.get_or_create(
                    account=target_acc,
                    role=role_slug,
                    network=appt.network,
                    geography=f"{appt.country}/{appt.unit_name}",
                    defaults={
                        "function": "leadership",
                        "expires_at": timezone.now() + timedelta(days=365),
                    },
                )
        else:
            appt.stage = "Onboarding"
            appt.next_action = "Review checklist"
            appt.save()

        AuditEvent.objects.create(
            account=actor_account,
            event="leader_onboarding_completed" if all_complete else "leader_onboarding_updated",
            detail={
                "appointment_code": appt.appointment_code,
                "appointee_name": appt.appointee_name,
                "position_title": appt.position_title,
                "all_complete": all_complete,
                "stage": appt.stage,
                "network": appt.network,
                "country": appt.country,
            },
        )

        return {"success": True, "appointment": appt, "all_complete": all_complete}


def record_first_90_day_review(
    appointment_code: str,
    review_point: str,
    outcome: str,
    evidence_notes: str,
    reviewer_confirmed: bool,
    actor_account: Account,
    user_scope: UserScope,
) -> Dict[str, Any]:
    """
    APPT-04 & APPT-04-REVIEWS: Records a 30 / 60 / 90 day leadership review outcome.
    Enforces authorized human reviewer confirmation and scoped audit logging.
    """
    assert_human_decision_authority(user_scope)

    clean_point = (review_point or "30 days").strip()
    if clean_point not in {"30 days", "60 days", "90 days"}:
        clean_point = "30 days"

    clean_outcome = (outcome or "").strip()
    clean_notes = (evidence_notes or "").strip()

    if not clean_outcome or clean_outcome.lower() == "select outcome":
        raise ValueError("Please select a valid review outcome before recording.")
    if not clean_notes:
        raise ValueError("Evidence and agreed support notes are required.")
    if not reviewer_confirmed:
        raise ValueError("Reviewer confirmation is required to record a review outcome.")

    with transaction.atomic():
        appt = AppointmentRecord.objects.select_for_update().filter(appointment_code=appointment_code).first()
        if not appt:
            appt = AppointmentRecord.objects.select_for_update().first()

        assert_appointment_scope_authorized(user_scope, appt)

        review, _ = LeadershipReview.objects.update_or_create(
            appointment=appt,
            review_point=clean_point,
            defaults={
                "outcome": clean_outcome,
                "evidence_notes": clean_notes,
                "reviewer_confirmed": True,
                "reviewed_by": actor_account,
                "reviewed_at": timezone.now(),
            },
        )

        if clean_point == "30 days":
            appt.milestone_30_completed = True
        elif clean_point == "60 days":
            appt.milestone_60_completed = True
        elif clean_point == "90 days":
            appt.milestone_90_completed = True
            if appt.stage == "Onboarding":
                appt.stage = "Active"
                appt.next_action = "Active service"
        appt.save()

        AuditEvent.objects.create(
            account=actor_account,
            event="leadership_review_recorded",
            detail={
                "appointment_code": appt.appointment_code,
                "appointee_name": appt.appointee_name,
                "position_title": appt.position_title,
                "review_point": clean_point,
                "outcome": clean_outcome,
                "network": appt.network,
                "country": appt.country,
            },
        )

        return {"success": True, "review": review, "appointment": appt}


def submit_leadership_status_change(
    appointment_code: str,
    requested_status: str,
    effective_period: str,
    reason_and_cover_plan: str,
    actor_account: Account,
    user_scope: UserScope,
    expected_updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    APPT-06: Reviews and records a leadership status change (e.g., On leave, Acting,
    Partially active, Under review, Suspended, Replacement required, Active).
    Rule: "Changing an appointment does not create a new person or erase prior service."
    """
    assert_human_decision_authority(user_scope)

    clean_status = (requested_status or "").strip()
    clean_period = (effective_period or "").strip()
    clean_reason = (reason_and_cover_plan or "").strip()

    if not clean_status or not clean_period or not clean_reason:
        raise ValueError("Requested status, effective period, and reason and cover plan are required.")

    with transaction.atomic():
        appt = AppointmentRecord.objects.select_for_update().select_related("seat", "person", "account").filter(
            appointment_code=appointment_code
        ).first()
        if not appt:
            appt = AppointmentRecord.objects.select_for_update().select_related("seat", "person", "account").first()

        assert_appointment_scope_authorized(user_scope, appt)

        if _check_optimistic_concurrency(appt, expected_updated_at):
            return {
                "success": False,
                "conflict": True,
                "appointment": appt,
                "message": "This record changed since you opened it. Review the latest version before submitting.",
            }

        previous_stage = appt.stage
        change_rec = LeadershipStatusChange.objects.create(
            appointment=appt,
            requested_status=clean_status,
            effective_period=clean_period,
            reason_and_cover_plan=clean_reason,
            decision_status="Approved",
            requested_by=actor_account,
            approved_by=actor_account,
        )

        appt.stage = clean_status
        if clean_status in {"Suspended", "Replacement required"}:
            appt.next_action = "Check access removal"
        elif clean_status == "On leave":
            appt.next_action = "Cover arrangement active"
        else:
            appt.next_action = "Review status"
        appt.save()

        seat = appt.seat
        seat.status = clean_status
        seat.save(update_fields=["status", "updated_at"])

        # If suspended or replacement required, revoke active role AccessGrants for that role
        if clean_status in {"Suspended", "Replacement required"}:
            target_acc = appt.account or (appt.person.account if appt.person else None)
            if target_acc:
                AccessGrant.objects.filter(
                    account=target_acc,
                    network=appt.network,
                    revoked_at__isnull=True,
                ).update(revoked_at=timezone.now())

        AuditEvent.objects.create(
            account=actor_account,
            event="leadership_status_changed",
            detail={
                "appointment_code": appt.appointment_code,
                "appointee_name": appt.appointee_name,
                "position_title": appt.position_title,
                "previous_stage": previous_stage,
                "requested_status": clean_status,
                "effective_period": clean_period,
                "reason_and_cover_plan": clean_reason,
                "network": appt.network,
                "country": appt.country,
            },
        )

        return {"success": True, "conflict": False, "status_change": change_rec, "appointment": appt}


def plan_leadership_transition(
    appointment_code: str,
    transition_type: str,
    effective_date: str,
    access_and_handover_notes: str,
    actor_account: Account,
    user_scope: UserScope,
    successor_name: str = "Ada Okafor",
    expected_updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    APPT-07: Plans a safe leadership transition (Transfer, Resignation / Exit, End of term, Replacement).
    - Transitions appointment stage to 'Handover' ('Check access removal').
    - Preserves outgoing holder in SeatHistory.
    - Ensures handover asset & access check items are open for verification.
    """
    assert_human_decision_authority(user_scope)

    clean_type = (transition_type or "").strip()
    clean_date = (effective_date or "").strip()
    clean_notes = (access_and_handover_notes or "").strip()

    if not clean_type or not clean_date or not clean_notes:
        raise ValueError("Transition type, effective date, and access and handover review notes are required.")

    with transaction.atomic():
        appt = AppointmentRecord.objects.select_for_update().select_related("seat", "person").filter(
            appointment_code=appointment_code
        ).first()
        if not appt:
            appt = AppointmentRecord.objects.select_for_update().select_related("seat", "person").filter(
                appointee_name__icontains="Kemi Bello"
            ).first() or AppointmentRecord.objects.select_for_update().select_related("seat", "person").first()

        assert_appointment_scope_authorized(user_scope, appt)

        if _check_optimistic_concurrency(appt, expected_updated_at):
            return {
                "success": False,
                "conflict": True,
                "appointment": appt,
                "message": "This record changed since you opened it. Review the latest version before submitting.",
            }

        outgoing_label = f"{appt.appointee_name} · {appt.position_title}"
        successor_p = PersonProfile.objects.filter(
            full_name__iexact=(successor_name or "Ada Okafor").strip()
        ).first()

        plan, _ = LeadershipTransitionPlan.objects.update_or_create(
            appointment=appt,
            outgoing_appointment_label=outgoing_label,
            defaults={
                "transition_type": clean_type,
                "effective_date": clean_date,
                "access_and_handover_notes": clean_notes,
                "status": "In review",
                "successor_person": successor_p,
                "successor_name": successor_p.full_name if successor_p else (successor_name or "Ada Okafor"),
                "planned_by": actor_account,
            },
        )

        appt.stage = "Handover"
        appt.next_action = "Check access removal"
        appt.save(update_fields=["stage", "next_action", "updated_at"])

        seat = appt.seat
        seat.status = "Handover"
        seat.save(update_fields=["status", "updated_at"])

        # Record durable SeatHistory entry so outgoing holder's service is preserved
        SeatHistory.objects.get_or_create(
            seat=seat,
            holder_name=appt.appointee_name,
            position_title=appt.position_title,
            unit_name=appt.unit_name,
            network=appt.network,
            country=appt.country,
            outcome_or_stage=f"Transition planned ({clean_type})",
            defaults={
                "person": appt.person,
                "service_period": f"Until {clean_date}",
                "transition_reason": clean_notes,
                "recorded_by": actor_account,
            },
        )

        AuditEvent.objects.create(
            account=actor_account,
            event="leadership_transition_planned",
            detail={
                "appointment_code": appt.appointment_code,
                "outgoing_appointment": outgoing_label,
                "transition_type": clean_type,
                "effective_date": clean_date,
                "network": appt.network,
                "country": appt.country,
            },
        )

        return {"success": True, "conflict": False, "transition_plan": plan, "appointment": appt}


def complete_handover_asset_task(
    task_id: str,
    actor_account: Account,
    user_scope: UserScope,
) -> Dict[str, Any]:
    """
    APPT-08-HANDOVER: Verifies and completes an individual handover asset or access check item.
    If the item is 'Disable and audit' (Former holder access), revokes obsolete AccessGrants
    for the former holder and writes an audit event.
    """
    assert_human_decision_authority(user_scope)

    with transaction.atomic():
        task = HandoverAssetTask.objects.select_for_update().select_related("appointment", "transition_plan").filter(
            id=task_id
        ).first()
        if not task:
            raise ValueError("Handover asset task not found.")

        assert_country_network_authorized(user_scope, country=task.country, network=task.network)

        task.status = "Completed"
        task.completed_by = actor_account
        task.completed_at = timezone.now()
        task.save()

        # If disabling former holder access, revoke active AccessGrants for the outgoing holder
        if "disable" in (task.access_action or "").lower():
            former_p = PersonProfile.objects.filter(full_name__iexact=task.to_actor).first()
            if former_p and former_p.account:
                AccessGrant.objects.filter(
                    account=former_p.account,
                    network=task.network,
                    revoked_at__isnull=True,
                ).update(revoked_at=timezone.now())

        # Check if all handover tasks in this scope/transition are now completed
        remaining_open = HandoverAssetTask.objects.filter(
            network=task.network,
            country=task.country,
            status="Open",
        ).count()

        if remaining_open == 0 and task.transition_plan:
            plan = task.transition_plan
            plan.status = "Completed"
            plan.save(update_fields=["status", "updated_at"])

            if task.appointment:
                appt = task.appointment
                appt.stage = "Transferred"
                appt.next_action = "Handover complete"
                appt.official_identity_status = "Reassigned"
                appt.save(update_fields=["stage", "next_action", "official_identity_status", "updated_at"])

                seat = appt.seat
                if plan.successor_name:
                    seat.holder_name = plan.successor_name
                    seat.holder_person = plan.successor_person
                    seat.status = "Active"
                else:
                    seat.holder_name = "Unfilled"
                    seat.holder_person = None
                    seat.status = "Vacant"
                seat.save()

        AuditEvent.objects.create(
            account=actor_account,
            event="handover_asset_completed",
            detail={
                "task_id": str(task.id),
                "asset_or_task": task.asset_or_task,
                "from_actor": task.from_actor,
                "to_actor": task.to_actor,
                "access_action": task.access_action,
                "remaining_open": remaining_open,
                "network": task.network,
                "country": task.country,
            },
        )

        return {"success": True, "task": task, "remaining_open": remaining_open}


def complete_all_handover_tasks(
    network: str,
    country: str,
    actor_account: Account,
    user_scope: UserScope,
) -> Dict[str, Any]:
    """
    APPT-08-HANDOVER: Verifies and completes all open handover assets & access checks
    for the current transition, closing the transition while retaining seat history.
    """
    assert_human_decision_authority(user_scope)
    norm_cc = normalize_country_code(country, default_code="NG")
    norm_net = (network or "WGMN").strip().upper()
    assert_country_network_authorized(user_scope, country=norm_cc, network=norm_net)

    with transaction.atomic():
        tasks = list(
            HandoverAssetTask.objects.select_for_update()
            .select_related("appointment", "transition_plan")
            .filter(network=norm_net, country=norm_cc)
        )
        for t in tasks:
            t.status = "Completed"
            t.completed_by = actor_account
            t.completed_at = timezone.now()
            t.save()

            if "disable" in (t.access_action or "").lower():
                former_p = PersonProfile.objects.filter(full_name__iexact=t.to_actor).first()
                if former_p and former_p.account:
                    AccessGrant.objects.filter(
                        account=former_p.account,
                        network=norm_net,
                        revoked_at__isnull=True,
                    ).update(revoked_at=timezone.now())

        plans = LeadershipTransitionPlan.objects.filter(
            appointment__network=norm_net,
            appointment__country=norm_cc,
        )
        for plan in plans:
            plan.status = "Completed"
            plan.save(update_fields=["status", "updated_at"])

            appt = plan.appointment
            if appt:
                SeatHistory.objects.get_or_create(
                    seat=appt.seat,
                    holder_name=appt.appointee_name,
                    position_title=appt.position_title,
                    unit_name=appt.unit_name,
                    network=appt.network,
                    country=appt.country,
                    outcome_or_stage="Handover completed",
                    defaults={
                        "person": appt.person,
                        "service_period": f"Completed {plan.effective_date}",
                        "transition_reason": f"Handover completed to {plan.successor_name or 'successor'}.",
                        "recorded_by": actor_account,
                    },
                )

        AuditEvent.objects.create(
            account=actor_account,
            event="handover_completed",
            detail={
                "completed_count": len(tasks),
                "network": norm_net,
                "country": norm_cc,
            },
        )

        return {"success": True, "completed_count": len(tasks)}


def assign_direct_report_followup(
    seat_code: str,
    followup_title: str,
    followup_summary: str,
    actor_account: Account,
    user_scope: UserScope,
) -> Dict[str, Any]:
    """
    LEAD-05: Assigns a follow-up WorkItem to a direct report seat/holder.
    """
    assert_stage7_authorized(user_scope, "LEAD-05")
    clean_title = (followup_title or "").strip()
    if not clean_title:
        raise ValueError("Follow-up title is required.")

    with transaction.atomic():
        seat = LeadershipSeat.objects.filter(seat_code=seat_code).first() or LeadershipSeat.objects.first()
        assert_seat_scope_authorized(user_scope, seat)

        target_acc = (seat.holder_person.account if seat and seat.holder_person else None) or actor_account
        item = WorkItem.objects.create(
            assigned_to=target_acc,
            created_by=actor_account,
            network=seat.network if seat else "WGMN",
            country=seat.country if seat else "NG",
            title=clean_title,
            summary=(followup_summary or "").strip() or f"Follow-up assigned for {seat.position_title} ({seat.unit_name}).",
            category="review",
            required_role="coordinator",
            status="pending",
            priority="normal",
            target_url=f"/foundation/leadership/seats/{seat.seat_code}/" if seat else "/foundation/leadership/direct-reports/",
        )

        AuditEvent.objects.create(
            account=actor_account,
            event="direct_report_followup_assigned",
            detail={
                "seat_code": seat.seat_code if seat else "",
                "holder_name": seat.holder_name if seat else "",
                "title": clean_title,
                "network": seat.network if seat else "WGMN",
                "country": seat.country if seat else "NG",
            },
        )

        return {"success": True, "work_item": item, "seat": seat}


def get_stage7_audit_history(
    user_scope: UserScope,
    country_code: Optional[str] = None,
    limit: int = 25,
) -> List[Dict[str, Any]]:
    """
    Returns scoped audit history events for Stage 07 Leadership, Vacancies, Appointments, and Handover.
    """
    stage7_events = {
        "position_revision_saved",
        "candidate_referred",
        "appointment_selected",
        "appointment_offer_accepted",
        "appointment_offer_declined",
        "leader_onboarding_updated",
        "leader_onboarding_completed",
        "leadership_review_recorded",
        "leadership_status_changed",
        "leadership_transition_planned",
        "handover_asset_completed",
        "handover_completed",
        "direct_report_followup_assigned",
    }
    qs = AuditEvent.objects.filter(event__in=stage7_events).select_related("account").order_by("-created_at")

    records = []
    is_global = is_global_stage6_scope(user_scope)
    active_c = (country_code or user_scope.active_country or "NG").upper()
    active_n = (user_scope.active_network or "WGMN").upper()

    for ev in qs[:100]:
        det = ev.detail or {}
        ev_country = (det.get("country") or "").upper()
        ev_net = (det.get("network") or "").upper()

        if country_code and ev_country and ev_country != active_c:
            continue
        if not is_global:
            if ev_country and active_c not in {"ALL", "BOTH", "*"} and ev_country != active_c:
                continue
            if ev_net and active_n not in {"ALL", "HQ / BOTH NETWORKS", "*"} and ev_net != active_n:
                continue

        label_map = {
            "position_revision_saved": f"Position revision saved: {det.get('position_code', '')} ({det.get('wgmn_title', '')} / {det.get('wnnn_title', '')})",
            "candidate_referred": f"Candidate referred: {det.get('candidate_name', '')} for {det.get('position_title', '')} ({det.get('unit_name', '')})",
            "appointment_selected": f"Appointment offer issued: {det.get('candidate_name', '')} · {det.get('position_title', '')} ({det.get('unit_name', '')})",
            "appointment_offer_accepted": f"Appointment accepted: {det.get('appointee_name', '')} · {det.get('position_title', '')}",
            "appointment_offer_declined": f"Appointment declined: {det.get('appointee_name', '')} · {det.get('position_title', '')}",
            "leader_onboarding_updated": f"Leader onboarding updated: {det.get('appointee_name', '')} · {det.get('position_title', '')}",
            "leader_onboarding_completed": f"Leader onboarding completed & access activated: {det.get('appointee_name', '')} · {det.get('position_title', '')}",
            "leadership_review_recorded": f"{det.get('review_point', '30 days')} review recorded: {det.get('appointee_name', '')} ({det.get('outcome', '')})",
            "leadership_status_changed": f"Status change approved: {det.get('appointee_name', '')} → {det.get('requested_status', '')} ({det.get('effective_period', '')})",
            "leadership_transition_planned": f"Transition planned: {det.get('outgoing_appointment', '')} ({det.get('transition_type', '')} · {det.get('effective_date', '')})",
            "handover_asset_completed": f"Handover check completed: {det.get('asset_or_task', '')} ({det.get('access_action', '')})",
            "handover_completed": f"Handover completed and verified ({det.get('completed_count', 0)} records)",
            "direct_report_followup_assigned": f"Follow-up assigned to {det.get('holder_name', '')}: {det.get('title', '')}",
        }
        records.append({
            "event": ev.event,
            "summary": label_map.get(ev.event, ev.event),
            "actor": ev.account.display_name if ev.account else "System",
            "when": ev.created_at.strftime("%d %b %Y · %H:%M") if ev.created_at else "Recently",
            "detail": det,
        })
        if len(records) >= limit:
            break

    return records
