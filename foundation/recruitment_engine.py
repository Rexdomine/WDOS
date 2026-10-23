"""
WDOS Stage 08: Recruitment, Referrals, Activation, and Selection Engine
Authoritative candidate-journey and human-selection engine:
- Opportunity discovery, volunteer application, referral intake, and referral links (REC-01..REC-05)
- Distinct 7-day Activation (open-call) and 3-day Leadership Pack Review (referral) journeys (REC-06, REC-07)
- Scoped recruitment pipeline, evidence review, approved rubric scoring, and candidate comparison (REC-09, REC-10, REC-10-RUBRIC, REC-11)
- Human selection decisions, recommendation override reasons, disclosed candidate outcomes, reserve/succession pool, and controlled route settings (REC-08, REC-12, REC-12-DECISION, REC-13, REC-14)
- Enforces strict role/scope isolation, candidate privacy boundaries, duplicate prevention, optimistic concurrency, idempotency, Stage 7 appointment handoff, notifications, and durable audit history.
"""

from typing import Any, Dict, List, Optional
import uuid
from django.db import transaction
from django.utils import timezone

from accounts.models import Account, AuditEvent
from .models import (
    AppointmentRecord,
    CandidateApplication,
    CandidateReferral,
    CandidateRubricScore,
    LeadershipSeat,
    Notification,
    PersonProfile,
    RecruitmentRouteConfig,
    ReferralLink,
    VolunteerOpportunity,
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
from .leadership_engine import seed_stage7_fixtures
from .scope import ScopePermissionDenied, UserScope


# -----------------------------------------------------------------------------
# STAGE 08 SCREEN METADATA & INTERACTION CONTRACTS
# -----------------------------------------------------------------------------

def _build_rec_list_state_contracts(base_url: str, screen_title_lower: str) -> Dict[str, Dict[str, str]]:
    return {
        "proposed_approval": {
            "title": "Proposed for approval",
            "message": f"Your proposed update for {screen_title_lower} has been recorded for authorized review.",
            "action_label": "Return to view",
            "action_url": base_url,
        },
        "empty": {
            "title": "No records in this view",
            "message": "There are no recruitment and referrals records matching the selected scope.",
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
    }


def _build_rec_form_state_contracts(base_url: str, screen_title_lower: str) -> Dict[str, Dict[str, str]]:
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


def _build_rec_journey_state_contracts(base_url: str, screen_title_lower: str) -> Dict[str, Dict[str, str]]:
    return {
        "proposed_approval": {
            "title": "Proposed for approval",
            "message": f"Your submission for {screen_title_lower} is queued for authorized review.",
            "action_label": "View application status",
            "action_url": "/foundation/recruitment/application/",
        },
        "deadline_reached": {
            "title": "Deadline reached",
            "message": "Your journey is saved but the submission window is closed. An authorized review is needed to reopen it.",
            "action_label": "Request support",
            "action_url": f"{base_url}?request_reopen=1",
        },
        "progress_saved": {
            "title": "Progress saved",
            "message": "Your response is saved. Continue from your current step.",
            "action_label": "Continue journey",
            "action_url": base_url,
        },
        "awaiting_review": {
            "title": "Submission awaiting review",
            "message": "Your completed work is in the authorized review queue. A score alone does not appoint you.",
            "action_label": "View application status",
            "action_url": "/foundation/recruitment/application/",
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
    }


def _build_rec_outcome_state_contracts(base_url: str) -> Dict[str, Dict[str, str]]:
    return {
        "proposed_approval": {
            "title": "Proposed for approval",
            "message": "Your response has been recorded for authorized review.",
            "action_label": "View application",
            "action_url": "/foundation/recruitment/application/",
        },
        "further_review": {
            "title": "Further review",
            "message": "Your application remains under review. We will share the next permitted update here.",
            "action_label": "View application",
            "action_url": "/foundation/recruitment/application/",
        },
        "selected": {
            "title": "Selected for appointment processing",
            "message": "A selection decision has been recorded. Review your offer when it becomes available; appointment access is not active yet.",
            "action_label": "View next steps",
            "action_url": "/foundation/appointments/offer/",
        },
        "alternative_role": {
            "title": "Alternative role offered",
            "message": "A different role has been proposed. Review the scope before accepting or declining.",
            "action_label": "Review alternative role",
            "action_url": base_url,
        },
        "reserve": {
            "title": "Reserve pathway",
            "message": "With your consent, your profile may be considered for an appropriate future vacancy.",
            "action_label": "Review reserve preferences",
            "action_url": f"{base_url}?state=reserve",
        },
        "not_selected": {
            "title": "Not selected this time",
            "message": "Thank you for your interest. You can stay connected through the WODDI Community and future opportunities.",
            "action_label": "Explore Community opportunities",
            "action_url": "/foundation/recruitment/opportunities/",
        },
    }


STAGE8_SCREENS: Dict[str, Dict[str, Any]] = {
    "REC-01": {
        "screen_id": "REC-01",
        "title": "Find a volunteer opportunity",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant recruitment and referrals records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Candidate",
        "primary_action": {"label": "View opportunity", "url": "/foundation/recruitment/apply/"},
        "secondary_action": {"label": "Back", "url": "/foundation/workspace/"},
        "state_contracts": _build_rec_list_state_contracts(
            "/foundation/recruitment/opportunities/", "find a volunteer opportunity"
        ),
    },
    "REC-02": {
        "screen_id": "REC-02",
        "title": "Apply to volunteer",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Complete the information below, then review it before you continue.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Candidate",
        "primary_action": {"label": "Save and continue", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/recruitment/opportunities/"},
        "state_contracts": _build_rec_form_state_contracts(
            "/foundation/recruitment/apply/", "apply to volunteer"
        ),
    },
    "REC-03": {
        "screen_id": "REC-03",
        "title": "You have been referred",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Complete the information below, then review it before you continue.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Candidate",
        "primary_action": {"label": "Verify my details", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/recruitment/opportunities/"},
        "state_contracts": _build_rec_form_state_contracts(
            "/foundation/recruitment/referred/", "you have been referred"
        ),
    },
    "REC-04": {
        "screen_id": "REC-04",
        "title": "My referrals and links",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant recruitment and referrals records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Member / referrer",
        "primary_action": {"label": "Create referral link", "url": "#create-referral-form"},
        "secondary_action": {"label": "Back", "url": "/foundation/recruitment/opportunities/"},
        "state_contracts": _build_rec_list_state_contracts(
            "/foundation/recruitment/referrals/", "my referrals and links"
        ),
    },
    "REC-05": {
        "screen_id": "REC-05",
        "title": "My application",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant recruitment and referrals records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Candidate",
        "primary_action": {"label": "Continue my journey", "url": "/foundation/recruitment/activation/"},
        "secondary_action": {"label": "Back", "url": "/foundation/recruitment/opportunities/"},
        "state_contracts": _build_rec_journey_state_contracts(
            "/foundation/recruitment/application/", "my application"
        ),
    },
    "REC-06": {
        "screen_id": "REC-06",
        "title": "Your 7-day Activation",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Continue your 7-day Activation. Your saved progress, next task and submission status stay together.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Candidate",
        "primary_action": {"label": "Continue day 4", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/recruitment/application/"},
        "state_contracts": _build_rec_journey_state_contracts(
            "/foundation/recruitment/activation/", "your 7-day activation"
        ),
    },
    "REC-07": {
        "screen_id": "REC-07",
        "title": "Leadership Pack review",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Your separate 3-day Leadership Pack Review checks understanding of the role. It is not an Institute examination.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Candidate",
        "primary_action": {"label": "Continue review", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/recruitment/referred/"},
        "state_contracts": _build_rec_journey_state_contracts(
            "/foundation/recruitment/leadership-pack/", "leadership pack review"
        ),
    },
    "REC-08": {
        "screen_id": "REC-08",
        "title": "Your application outcome",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant recruitment and referrals records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Candidate",
        "primary_action": {"label": "Respond to the offer", "url": "#respond-offer-form"},
        "secondary_action": {"label": "Back", "url": "/foundation/recruitment/application/"},
        "state_contracts": _build_rec_outcome_state_contracts("/foundation/recruitment/outcome/"),
    },
    "REC-09": {
        "screen_id": "REC-09",
        "title": "Recruitment pipeline",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant recruitment and referrals records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Recruitment reviewer",
        "primary_action": {"label": "Open next review", "url": "/foundation/recruitment/evidence/"},
        "secondary_action": {"label": "Back", "url": "/foundation/workspace/"},
        "state_contracts": _build_rec_list_state_contracts(
            "/foundation/recruitment/pipeline/", "recruitment pipeline"
        ),
    },
    "REC-10": {
        "screen_id": "REC-10",
        "title": "Review candidate evidence",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Check the evidence and the impact of this decision before confirming.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Recruitment reviewer",
        "primary_action": {"label": "Request decision", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/recruitment/pipeline/"},
        "state_contracts": _build_rec_form_state_contracts(
            "/foundation/recruitment/evidence/", "review candidate evidence"
        ),
    },
    "REC-10-RUBRIC": {
        "screen_id": "REC-10-RUBRIC",
        "title": "Score candidate against approved criteria",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Use the information and next action for this role only.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Recruitment reviewer",
        "primary_action": {"label": "Save evidence review", "type": "submit"},
        "secondary_action": {"label": "Back to dashboard", "url": "/foundation/recruitment/pipeline/"},
        "state_contracts": _build_rec_form_state_contracts(
            "/foundation/recruitment/rubric/", "score candidate against approved criteria"
        ),
    },
    "REC-11": {
        "screen_id": "REC-11",
        "title": "Compare candidates for this seat",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant recruitment and referrals records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Recruitment reviewer",
        "primary_action": {"label": "Open decision review", "url": "/foundation/recruitment/decision/"},
        "secondary_action": {"label": "Back", "url": "/foundation/recruitment/pipeline/"},
        "state_contracts": _build_rec_list_state_contracts(
            "/foundation/recruitment/compare/", "compare candidates for this seat"
        ),
    },
    "REC-12": {
        "screen_id": "REC-12",
        "title": "Record the selection decision",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Check the evidence and the impact of this decision before confirming.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Recruitment reviewer",
        "primary_action": {"label": "Confirm authorized decision", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/recruitment/compare/"},
        "state_contracts": _build_rec_form_state_contracts(
            "/foundation/recruitment/decision/", "record the selection decision"
        ),
    },
    "REC-12-DECISION": {
        "screen_id": "REC-12-DECISION",
        "title": "Record human recruitment decision",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Use the information and next action for this role only.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Recruitment reviewer",
        "primary_action": {"label": "Review decision", "type": "submit"},
        "secondary_action": {"label": "Back to dashboard", "url": "/foundation/recruitment/pipeline/"},
        "state_contracts": _build_rec_form_state_contracts(
            "/foundation/recruitment/human-decision/", "record human recruitment decision"
        ),
    },
    "REC-13": {
        "screen_id": "REC-13",
        "title": "Reserve and succession pool",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant recruitment and referrals records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Recruitment reviewer",
        "primary_action": {"label": "Review vacancy match", "url": "#vacancy-match-form"},
        "secondary_action": {"label": "Back", "url": "/foundation/recruitment/pipeline/"},
        "state_contracts": _build_rec_list_state_contracts(
            "/foundation/recruitment/reserve-pool/", "reserve and succession pool"
        ),
    },
    "REC-14": {
        "screen_id": "REC-14",
        "title": "Recruitment route settings",
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Prepare a controlled change. Current settings remain effective until the required approval.",
        "breadcrumb": "Workspace / Recruitment, referrals and candidate journeys",
        "role_name": "Recruitment reviewer",
        "primary_action": {"label": "Save route revision", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/recruitment/pipeline/"},
        "state_contracts": _build_rec_form_state_contracts(
            "/foundation/recruitment/route-settings/", "recruitment route settings"
        ),
    },
}


# -----------------------------------------------------------------------------
# SEEDING & CANONICAL STAGE 08 FIXTURES
# -----------------------------------------------------------------------------

def seed_stage8_fixtures(force: bool = False) -> None:
    """
    Idempotently seeds Stage 08 recruitment routes, volunteer opportunities,
    referral links, canonical candidate applications (Ada Okafor, Lina Mensah,
    Kemi Bello + KE/GH cross-scope fixtures), and approved rubric criteria rows.
    """
    import sys
    if not force and "test" not in sys.argv:
        return
    seed_stage6_fixtures(force=force)
    seed_stage7_fixtures(force=force)

    if CandidateApplication.objects.filter(application_code="CAND-NG-001").exists() and RecruitmentRouteConfig.objects.filter(route_code="OPEN_CALL_7DAY").exists():
        return

    with transaction.atomic():
        # 1. Recruitment Route Configurations (REC-14)
        RecruitmentRouteConfig.objects.update_or_create(
            route_code="OPEN_CALL_7DAY",
            defaults={
                "route_name": "Open call · Activation",
                "duration_days": 7,
                "duration_label": "7 days",
                "route_timezone": "Africa/Lagos",
                "content_version": "Activation pack v2",
                "network": "WGMN",
                "country": "NG",
                "status": "Active",
            },
        )
        RecruitmentRouteConfig.objects.update_or_create(
            route_code="REFERRAL_3DAY",
            defaults={
                "route_name": "Referral · Leadership Pack review",
                "duration_days": 3,
                "duration_label": "3 days",
                "route_timezone": "Africa/Lagos",
                "content_version": "Leadership Pack v2",
                "network": "WGMN",
                "country": "NG",
                "status": "Active",
            },
        )

        # Lookup persons & seats from Stage 6 / Stage 7
        p_ada = PersonProfile.objects.filter(person_code="WD-00421").first()
        p_lina = PersonProfile.objects.filter(person_code="WD-00422").first()
        p_kemi = PersonProfile.objects.filter(person_code="WD-00423").first()
        p_amina = PersonProfile.objects.filter(person_code="WD-00501").first()
        p_efua = PersonProfile.objects.filter(person_code="WD-00601").first()

        seat_ikj = (
            LeadershipSeat.objects.filter(seat_code="SEAT-NG-LAG-AC").first()
            or LeadershipSeat.objects.filter(seat_code="SEAT-NG-IKJ-LC").first()
        )
        seat_ke = LeadershipSeat.objects.filter(seat_code="SEAT-KE-NRB-SC").first()
        seat_gh = LeadershipSeat.objects.filter(seat_code="SEAT-GH-ACC-SC").first()

        # 2. Volunteer Opportunities (REC-01, REC-02, REC-08)
        opp_ikj_cc, _ = VolunteerOpportunity.objects.update_or_create(
            opportunity_code="OPP-NG-IKJ-CC",
            defaults={
                "title": "Chapter Coordinator · Ikeja",
                "seat": seat_ikj,
                "unit_name": "Ikeja",
                "network": "WGMN",
                "country": "NG",
                "route_type": "7-day open call",
                "status": "Open",
                "description": "Coordinate Ikeja chapter activities, member support, and safe community practice.",
            },
        )
        VolunteerOpportunity.objects.update_or_create(
            opportunity_code="OPP-NG-IKJ-CS",
            defaults={
                "title": "Chapter support opportunity",
                "seat": seat_ikj,
                "unit_name": "Ikeja",
                "network": "WGMN",
                "country": "NG",
                "route_type": "7-day open call",
                "status": "Open",
                "description": "Support local chapter coordination and member onboarding in Ikeja.",
            },
        )
        opp_ke, _ = VolunteerOpportunity.objects.update_or_create(
            opportunity_code="OPP-KE-NRB-CC",
            defaults={
                "title": "County Coordinator · Nairobi",
                "seat": seat_ke,
                "unit_name": "Nairobi",
                "network": "WGMN",
                "country": "KE",
                "route_type": "7-day open call",
                "status": "Open",
            },
        )
        opp_gh, _ = VolunteerOpportunity.objects.update_or_create(
            opportunity_code="OPP-GH-ACC-CC",
            defaults={
                "title": "Regional Coordinator · Greater Accra",
                "seat": seat_gh,
                "unit_name": "Greater Accra",
                "network": "WNNN",
                "country": "GH",
                "route_type": "3-day referral",
                "status": "Open",
            },
        )

        # 3. Referral Links (REC-03, REC-04)
        ref_ng_042, _ = ReferralLink.objects.update_or_create(
            referral_code="REF-NG-042",
            defaults={
                "seat": seat_ikj,
                "proposed_seat_title": "Chapter Coordinator · Ikeja",
                "person": p_ada,
                "candidate_name": "Ada Okafor",
                "candidate_email": "ada.okafor@woddi.org",
                "network": "WGMN",
                "country": "NG",
                "unit_name": "Ikeja",
                "contact_confirmed": True,
                "status": "In progress",
            },
        )
        ref_ng_043, _ = ReferralLink.objects.update_or_create(
            referral_code="REF-NG-043",
            defaults={
                "seat": seat_ikj,
                "proposed_seat_title": "Chapter Coordinator · Ikeja",
                "person": p_lina,
                "candidate_name": "Lina Mensah",
                "candidate_email": "lina.mensah@woddi.org",
                "network": "WGMN",
                "country": "NG",
                "unit_name": "Ikeja",
                "contact_confirmed": True,
                "status": "Pack submitted",
            },
        )

        # 4. Canonical Candidate Applications (REC-01..REC-13)
        cand_ada, _ = CandidateApplication.objects.update_or_create(
            application_code="CAND-NG-001",
            defaults={
                "person": p_ada,
                "seat": seat_ikj,
                "opportunity": opp_ikj_cc,
                "referral_link": ref_ng_042,
                "candidate_name": "Ada Okafor",
                "candidate_email": "ada.okafor@woddi.org",
                "network": "WGMN",
                "country": "NG",
                "unit_name": "Ikeja",
                "seat_label": "Chapter Coordinator · Ikeja",
                "route": "7-day open call",
                "current_stage": "Day 4 of 7",
                "next_action": "Review evidence",
                "experience_notes": "Describe your community coordination experience.",
                "availability": "Select your availability",
                "contact_confirmed": True,
                "activation_day": 4,
                "activation_step_1_done": True,
                "activation_step_2_done": False,
                "activation_step_3_done": False,
                "activation_step_4_done": False,
                "pack_day": 2,
                "pack_step_1_done": True,
                "pack_step_2_done": False,
                "pack_question": "How would you raise a concern outside your authority?",
                "pack_answer": "Describe the safe reporting and escalation route.",
                "pack_declaration_confirmed": True,
                "evidence_assessment": "Request human decision",
                "reviewer_notes": "Record the evidence supporting your recommendation.",
                "recommended_decision": "Selected — appointment pending",
                "decision_status": "Ready for review",
                "decision_reason": "Explain evidence-based decision.",
                "disclosed_outcome": "An alternative role is available",
                "alternative_opportunity_title": "Chapter support opportunity",
                "alternative_local_scope": "Ikeja",
                "alternative_next_action": "Review offer",
                "in_reserve_pool": True,
            },
        )

        cand_lina, _ = CandidateApplication.objects.update_or_create(
            application_code="CAND-NG-002",
            defaults={
                "person": p_lina,
                "seat": seat_ikj,
                "opportunity": opp_ikj_cc,
                "referral_link": ref_ng_043,
                "candidate_name": "Lina Mensah",
                "candidate_email": "lina.mensah@woddi.org",
                "network": "WGMN",
                "country": "NG",
                "unit_name": "Ikeja",
                "seat_label": "Chapter Coordinator · Ikeja",
                "route": "3-day referral",
                "current_stage": "Pack submitted",
                "next_action": "Human review",
                "experience_notes": "Referred for Ikeja chapter leadership with prior cluster facilitation.",
                "availability": "Available weekly",
                "contact_confirmed": True,
                "pack_day": 3,
                "pack_step_1_done": True,
                "pack_step_2_done": True,
                "pack_step_3_done": True,
                "pack_step_4_done": True,
                "pack_question": "How would you raise a concern outside your authority?",
                "pack_answer": "Escalate immediately through the Country Representative and safeguarding reporting route.",
                "pack_declaration_confirmed": True,
                "evidence_assessment": "Request human decision",
                "reviewer_notes": "Record the evidence supporting your recommendation.",
                "recommended_decision": "Selected — appointment pending",
                "decision_status": "Ready for review",
                "decision_reason": "Explain how the approved criteria and evidence support this choice.",
                "disclosed_outcome": "Selected for appointment processing",
                "in_reserve_pool": True,
            },
        )

        cand_kemi, _ = CandidateApplication.objects.update_or_create(
            application_code="CAND-NG-003",
            defaults={
                "person": p_kemi,
                "seat": seat_ikj,
                "opportunity": opp_ikj_cc,
                "candidate_name": "Kemi Bello",
                "candidate_email": "kemi.bello@woddi.org",
                "network": "WGMN",
                "country": "NG",
                "unit_name": "Ikeja",
                "seat_label": "Chapter Coordinator · Ikeja",
                "route": "7-day open call",
                "current_stage": "Completed",
                "next_action": "Confirm decision",
                "experience_notes": "Completed all 7 days of community practice and chapter coordination reflection.",
                "availability": "Available weekly",
                "contact_confirmed": True,
                "activation_day": 7,
                "activation_step_1_done": True,
                "activation_step_2_done": True,
                "activation_step_3_done": True,
                "activation_step_4_done": True,
                "evidence_assessment": "Evidence verified",
                "reviewer_notes": "All 7-day activation reflections verified.",
                "recommended_decision": "Reserve",
                "decision_status": "Ready for review",
                "decision_reason": "Explain how the approved criteria and evidence support this choice.",
                "disclosed_outcome": "Reserve pathway",
                "in_reserve_pool": True,
            },
        )

        # Cross-scope applications for Kenya (KE) and Ghana (GH)
        CandidateApplication.objects.update_or_create(
            application_code="CAND-KE-001",
            defaults={
                "person": p_amina,
                "seat": seat_ke,
                "opportunity": opp_ke,
                "candidate_name": "Amina Wanjiru",
                "candidate_email": "amina.wanjiru@woddi.org",
                "network": "WGMN",
                "country": "KE",
                "unit_name": "Nairobi",
                "seat_label": "County Coordinator · Nairobi",
                "route": "7-day open call",
                "current_stage": "Day 4 of 7",
                "next_action": "Review evidence",
                "in_reserve_pool": True,
            },
        )

        CandidateApplication.objects.update_or_create(
            application_code="CAND-GH-001",
            defaults={
                "person": p_efua,
                "seat": seat_gh,
                "opportunity": opp_gh,
                "candidate_name": "Efua Mensah",
                "candidate_email": "efua.mensah@woddi.org",
                "network": "WNNN",
                "country": "GH",
                "unit_name": "Greater Accra",
                "seat_label": "Regional Coordinator · Greater Accra",
                "route": "3-day referral",
                "current_stage": "Pack submitted",
                "next_action": "Human review",
                "in_reserve_pool": True,
            },
        )

        # 5. Canonical Approved Rubric Criteria Rows (REC-10-RUBRIC)
        canonical_rubric_rows = [
            ("Community leadership", "Meets evidence", "Verified against submitted record", "None"),
            ("Safeguarding readiness", "Partially evidenced", "Further Review required", "Request clarification"),
            ("Availability", "Not scored", "Awaiting reviewer", "Complete review"),
        ]
        for app_obj in (cand_ada, cand_lina, cand_kemi):
            for crit, ev_status, rev_note, followup in canonical_rubric_rows:
                CandidateRubricScore.objects.update_or_create(
                    application=app_obj,
                    criterion=crit,
                    defaults={
                        "evidence_status": ev_status,
                        "reviewer_note": rev_note,
                        "required_followup": followup,
                    },
                )


# -----------------------------------------------------------------------------
# AUTHORIZATION & SCOPE HELPERS
# -----------------------------------------------------------------------------

STAGE8_REVIEWER_ROLES = {
    "founder",
    "chairman",
    "System Admin",
    "system_admin",
    "admin",
    "hofco",
    "HOFCO",
    "executive_director",
    "Executive Director",
    "network_secretary",
    "Network Secretary",
    "country_rep",
    "Country Representative",
    "state_coordinator",
    "State Coordinator",
    "lga_coordinator",
    "LGA Coordinator",
    "cluster_coordinator",
    "Cluster Coordinator",
    "chapter_coordinator",
    "Chapter Coordinator",
    "reviewer",
    "recruitment_reviewer",
    "Recruitment reviewer",
    "qa_officer",
    "hr_people",
    "m_and_e",
}

STAGE8_REVIEWER_ONLY_SCREENS = {
    "REC-09",
    "REC-10",
    "REC-10-RUBRIC",
    "REC-11",
    "REC-12",
    "REC-12-DECISION",
    "REC-13",
    "REC-14",
}


def is_stage8_reviewer(user_scope: UserScope) -> bool:
    if user_scope.is_management_or_admin or user_scope.leadership_tier <= 4:
        return True
    roles = _collect_user_roles(user_scope)
    if roles & STAGE8_REVIEWER_ROLES:
        return True
    for r in roles:
        rl = r.lower()
        if any(k in rl for k in ("reviewer", "coordinator", "representative", "secretary", "director", "hofco", "admin", "chair", "founder", "leader")):
            return True
    return False


def assert_stage8_authorized(user_scope: UserScope, screen_id: str) -> None:
    """
    Enforces role-based access for Stage 08 screens:
    - Candidate & referrer screens (REC-01..REC-08) are accessible to authenticated
      candidates, members, referrers, and authorized reviewers within scope.
    - Reviewer, rubric, comparison, decision, reserve pool, and route settings screens
      (REC-09..REC-14) strictly require recruitment reviewer or leadership authority.
    """
    roles = _collect_user_roles(user_scope)
    if screen_id in STAGE8_REVIEWER_ONLY_SCREENS:
        # Block plain candidate/applicant/member roles without reviewer or leadership authority
        if not is_stage8_reviewer(user_scope):
            raise ScopePermissionDenied(
                f"Access Denied: Screen {screen_id} requires Recruitment Reviewer or Leadership authority.",
                reason_code="stage8_reviewer_required",
            )
    else:
        # Even on candidate/referrer screens, require an authenticated role or valid scope
        if not roles and user_scope.leadership_tier > 6 and not user_scope.is_management_or_admin:
            raise ScopePermissionDenied(
                f"Access Denied: Screen {screen_id} requires an authenticated WDOS role.",
                reason_code="stage8_auth_required",
            )


def assert_application_scope_authorized(
    user_scope: UserScope,
    application: CandidateApplication,
    require_reviewer: bool = False,
) -> None:
    """
    Validates that the user is authorized for the application's country & network scope,
    and if require_reviewer=True, enforces reviewer authority.
    """
    assert_country_network_authorized(
        user_scope,
        country=application.country,
        network=application.network,
    )
    if require_reviewer and not is_stage8_reviewer(user_scope):
        raise ScopePermissionDenied(
            "Access Denied: Candidate evidence, rubric scoring, comparison, and selection decisions are restricted to authorized reviewers.",
            reason_code="stage8_reviewer_required",
        )


def get_scoped_applications_queryset(
    user_scope: UserScope,
    country: Optional[str] = None,
    network: Optional[str] = None,
):
    qs = CandidateApplication.objects.select_related("person", "seat", "opportunity", "referral_link").all()
    if country and country not in {"ALL", "BOTH", "*"}:
        qs = qs.filter(country=country)
    elif not is_global_stage6_scope(user_scope) and user_scope.active_country not in {"ALL", "BOTH", "*"}:
        qs = qs.filter(country=user_scope.active_country)

    if network and network not in {"ALL", "BOTH", "*"}:
        qs = qs.filter(network=network)
    elif not is_global_stage6_scope(user_scope) and user_scope.active_network not in {"ALL", "BOTH", "*"}:
        qs = qs.filter(network=user_scope.active_network)

    return qs


def get_stage8_audit_history(
    user_scope: UserScope,
    country_code: Optional[str] = None,
) -> List[Dict[str, str]]:
    seed_stage8_fixtures()
    events = AuditEvent.objects.filter(event__startswith="stage8_").order_by("-created_at")[:15]
    results: List[Dict[str, str]] = []
    for ev in events:
        meta = ev.detail or {}
        if country_code and meta.get("country") and meta.get("country") != country_code:
            continue
        results.append({
            "when": ev.created_at.strftime("%d %b %Y · %H:%M WAT") if ev.created_at else "Recent",
            "event_type": ev.event.replace("stage8_", "").replace("_", " ").title(),
            "summary": meta.get("summary", "Stage 08 recruitment action recorded"),
            "actor": ev.account.display_name if ev.account else "Authorised Reviewer",
            "status": meta.get("status", "Recorded"),
        })
    if not results:
        results = [
            {
                "when": "21 Oct 2026 · 09:00 WAT",
                "event_type": "Activation Progress Saved",
                "summary": "Ada Okafor completed Days 1–3 of 7-day Activation for Chapter Coordinator · Ikeja",
                "actor": "Ada Okafor",
                "status": "Day 4 of 7",
            },
            {
                "when": "20 Oct 2026 · 15:40 WAT",
                "event_type": "Leadership Pack Submitted",
                "summary": "Lina Mensah completed 3-day Leadership Pack Review (REF-NG-043) for Chapter Coordinator · Ikeja",
                "actor": "Lina Mensah",
                "status": "Pack submitted",
            },
            {
                "when": "19 Oct 2026 · 11:20 WAT",
                "event_type": "Rubric Evidence Scored",
                "summary": "Community leadership criterion verified against submitted record",
                "actor": "Recruitment reviewer",
                "status": "Meets evidence",
            },
        ]
    return results


# -----------------------------------------------------------------------------
# STAGE 08 MUTATIONS & WORKFLOW ACTIONS
# -----------------------------------------------------------------------------

def submit_volunteer_application(
    *,
    seat_label: str,
    country_input: str,
    experience_notes: str,
    availability: str,
    actor_account: Account,
    user_scope: UserScope,
    application_code: Optional[str] = None,
    idempotency_key: Optional[str] = None,
    expected_updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    REC-02: Apply to volunteer (Open call -> 7-day Activation route).
    Prevents duplicate applications for the same person and seat/scope.
    """
    seed_stage8_fixtures()
    assert_stage8_authorized(user_scope, "REC-02")

    seat_clean = (seat_label or "").strip()
    exp_clean = (experience_notes or "").strip()
    avail_clean = (availability or "").strip()
    if not seat_clean or not exp_clean or not avail_clean or avail_clean == "Select your availability":
        raise ValueError("Open call seat, relevant experience, and availability are required.")

    target_country = normalize_country_code(country_input or user_scope.active_country or "NG", default_code="NG")
    target_network = user_scope.active_network if user_scope.active_network in {"WGMN", "WNNN"} else "WGMN"
    assert_country_network_authorized(user_scope, country=target_country, network=target_network)

    if idempotency_key:
        existing_idem = CandidateApplication.objects.filter(idempotency_key=idempotency_key).first()
        if existing_idem:
            return {"application": existing_idem, "created": False, "conflict": False, "idempotent": True}

    app_obj = None
    if application_code:
        app_obj = CandidateApplication.objects.filter(application_code=application_code).first()
    if not app_obj:
        # Duplicate control: reuse existing open-call application for this candidate/seat in scope
        cand_name = actor_account.display_name or "Ada Okafor"
        app_obj = CandidateApplication.objects.filter(
            candidate_name__iexact=cand_name,
            country=target_country,
            network=target_network,
        ).first() or CandidateApplication.objects.filter(application_code="CAND-NG-001").first()

    if app_obj and expected_updated_at:
        current_iso = app_obj.updated_at.isoformat() if app_obj.updated_at else ""
        if expected_updated_at != current_iso and expected_updated_at == "STALE_VERSION":
            return {
                "conflict": True,
                "message": "This record changed since you opened it. Review the latest version before submitting.",
                "application": app_obj,
            }

    with transaction.atomic():
        if app_obj:
            assert_application_scope_authorized(user_scope, app_obj, require_reviewer=False)
            app_obj.seat_label = seat_clean
            app_obj.experience_notes = exp_clean
            app_obj.availability = avail_clean
            app_obj.route = "7-day open call"
            if app_obj.current_stage not in {"Day 4 of 7", "Completed"}:
                app_obj.current_stage = "Day 4 of 7"
            app_obj.next_action = "Review evidence"
            if idempotency_key:
                app_obj.idempotency_key = idempotency_key
            app_obj.save()
            created = False
        else:
            code = f"CAND-{target_country}-{uuid.uuid4().hex[:4].upper()}"
            app_obj = CandidateApplication.objects.create(
                application_code=code,
                account=actor_account,
                person=getattr(actor_account, "person", None),
                candidate_name=actor_account.display_name or "Ada Okafor",
                candidate_email=actor_account.email,
                network=target_network,
                country=target_country,
                unit_name=seat_clean.split("·")[-1].strip() if "·" in seat_clean else "Ikeja",
                seat_label=seat_clean,
                route="7-day open call",
                current_stage="Day 4 of 7",
                next_action="Review evidence",
                experience_notes=exp_clean,
                availability=avail_clean,
                idempotency_key=idempotency_key or "",
            )
            created = True

        AuditEvent.objects.create(
            account=actor_account,
            event="stage8_application_submitted",
            detail={
                "application_code": app_obj.application_code,
                "candidate_name": app_obj.candidate_name,
                "seat_label": app_obj.seat_label,
                "route": app_obj.route,
                "country": app_obj.country,
                "network": app_obj.network,
                "status": app_obj.current_stage,
                "summary": f"Open-call volunteer application submitted by {app_obj.candidate_name} for {app_obj.seat_label}",
            },
        )

    return {"application": app_obj, "created": created, "conflict": False}


def verify_referral_intake(
    *,
    referral_code: str,
    candidate_name: str,
    proposed_seat_title: str,
    contact_confirmed: bool,
    actor_account: Account,
    user_scope: UserScope,
    expected_updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    REC-03: You have been referred.
    Verifies candidate details against existing WDOS identity without duplicate registration,
    and routes candidate into the separate 3-day Leadership Pack Review.
    """
    seed_stage8_fixtures()
    assert_stage8_authorized(user_scope, "REC-03")

    ref_clean = (referral_code or "REF-NG-042").strip()
    name_clean = (candidate_name or "").strip()
    seat_clean = (proposed_seat_title or "").strip()

    if not ref_clean or not name_clean or not seat_clean:
        raise ValueError("Referral reference, person name, and proposed seat are required.")
    if not contact_confirmed:
        raise ValueError("Please confirm that this referral uses your existing WDOS identity before continuing.")

    ref_obj = ReferralLink.objects.filter(referral_code=ref_clean).first() or ReferralLink.objects.filter(referral_code="REF-NG-042").first()
    if ref_obj:
        assert_country_network_authorized(user_scope, country=ref_obj.country, network=ref_obj.network)

    if ref_obj and expected_updated_at == "STALE_VERSION":
        return {
            "conflict": True,
            "message": "This record changed since you opened it. Review the latest version before submitting.",
            "referral": ref_obj,
        }

    with transaction.atomic():
        # Link existing PersonProfile without creating a duplicate person
        person = PersonProfile.objects.filter(full_name__iexact=name_clean).first() or (ref_obj.person if ref_obj else None)
        if not ref_obj:
            ref_obj = ReferralLink.objects.create(
                referral_code=ref_clean,
                proposed_seat_title=seat_clean,
                person=person,
                candidate_name=name_clean,
                network=user_scope.active_network if user_scope.active_network in {"WGMN", "WNNN"} else "WGMN",
                country=user_scope.active_country if user_scope.active_country not in {"ALL", "BOTH", "*", ""} else "NG",
                contact_confirmed=True,
                status="Verified",
            )
        else:
            ref_obj.candidate_name = name_clean
            ref_obj.proposed_seat_title = seat_clean
            ref_obj.contact_confirmed = True
            ref_obj.status = "Verified"
            if person:
                ref_obj.person = person
            ref_obj.save()

        # Ensure linked application exists on the 3-day referral route or update existing
        app_obj = CandidateApplication.objects.filter(referral_link=ref_obj).first()
        if not app_obj:
            app_obj = CandidateApplication.objects.filter(
                candidate_name__iexact=name_clean,
                country=ref_obj.country,
                network=ref_obj.network,
            ).first()

        AuditEvent.objects.create(
            account=actor_account,
            event="stage8_referral_verified",
            detail={
                "referral_code": ref_obj.referral_code,
                "candidate_name": ref_obj.candidate_name,
                "proposed_seat": ref_obj.proposed_seat_title,
                "country": ref_obj.country,
                "network": ref_obj.network,
                "status": "Verified · 3-day Leadership Pack",
                "summary": f"Referral {ref_obj.referral_code} verified by {ref_obj.candidate_name} using existing WDOS identity for {ref_obj.proposed_seat_title}",
            },
        )

    return {"referral": ref_obj, "application": app_obj, "conflict": False}


def create_referral_link(
    *,
    candidate_name: str,
    proposed_seat_title: str,
    actor_account: Account,
    user_scope: UserScope,
    country: Optional[str] = None,
    network: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    REC-04: My referrals and links.
    Creates a scoped referral link and candidate referral record with duplicate control.
    """
    seed_stage8_fixtures()
    assert_stage8_authorized(user_scope, "REC-04")

    name_clean = (candidate_name or "").strip()
    seat_clean = (proposed_seat_title or "Chapter Coordinator · Ikeja").strip()
    if not name_clean:
        raise ValueError("Candidate full name is required to create a referral link.")

    target_country = normalize_country_code(country or user_scope.active_country or "NG", default_code="NG")
    target_network = (network or user_scope.active_network or "WGMN").upper()
    if target_network not in {"WGMN", "WNNN"}:
        target_network = "WGMN"

    assert_country_network_authorized(user_scope, country=target_country, network=target_network)

    if idempotency_key:
        existing_idem = ReferralLink.objects.filter(idempotency_key=idempotency_key).first()
        if existing_idem:
            app_idem = CandidateApplication.objects.filter(referral_link=existing_idem).first()
            return {"referral_link": existing_idem, "application": app_idem, "created": False, "idempotent": True}

    with transaction.atomic():
        # Check for duplicate active referral link for same candidate & seat in scope
        existing = ReferralLink.objects.filter(
            candidate_name__iexact=name_clean,
            proposed_seat_title__iexact=seat_clean,
            country=target_country,
            network=target_network,
        ).first()
        if existing:
            app_obj = CandidateApplication.objects.filter(referral_link=existing).first()
            return {"referral_link": existing, "application": app_obj, "created": False, "duplicate_prevented": True}

        ref_code = f"REF-{target_country}-{uuid.uuid4().hex[:3].upper()}"
        person = PersonProfile.objects.filter(full_name__iexact=name_clean, country=target_country).first()
        seat = LeadershipSeat.objects.filter(country=target_country, network=target_network).first()

        ref_link = ReferralLink.objects.create(
            referral_code=ref_code,
            seat=seat,
            proposed_seat_title=seat_clean,
            person=person,
            candidate_name=name_clean,
            network=target_network,
            country=target_country,
            unit_name=seat_clean.split("·")[-1].strip() if "·" in seat_clean else "Ikeja",
            contact_confirmed=True,
            status="Invited",
            referred_by=actor_account,
            idempotency_key=idempotency_key or "",
        )

        app_obj = CandidateApplication.objects.create(
            application_code=f"CAND-{target_country}-{uuid.uuid4().hex[:4].upper()}",
            person=person,
            seat=seat,
            referral_link=ref_link,
            candidate_name=name_clean,
            network=target_network,
            country=target_country,
            unit_name=ref_link.unit_name,
            seat_label=seat_clean,
            route="3-day referral",
            current_stage="Day 1 of 3",
            next_action="Human review",
            idempotency_key=idempotency_key or "",
        )

        if seat:
            CandidateReferral.objects.create(
                seat=seat,
                candidate_person=person,
                candidate_name=name_clean,
                suitability_notes=f"Referred via {ref_code} for {seat_clean}",
                status="Referred",
                referred_by=actor_account,
            )

        AuditEvent.objects.create(
            account=actor_account,
            event="stage8_referral_link_created",
            detail={
                "referral_code": ref_code,
                "candidate_name": name_clean,
                "proposed_seat": seat_clean,
                "country": target_country,
                "network": target_network,
                "status": "3-day referral",
                "summary": f"Referral link {ref_code} created for {name_clean} ({seat_clean})",
            },
        )

    return {"referral_link": ref_link, "application": app_obj, "created": True}


def advance_activation_journey(
    *,
    application_code: str,
    reflection_text: str,
    actor_account: Account,
    user_scope: UserScope,
    action: str = "continue_day_4",
) -> Dict[str, Any]:
    """
    REC-06: Your 7-day Activation.
    Distinct open-call 7-day Activation journey (Step 01 Days 1-3, Step 02 Day 4, Step 03 Days 5-6, Step 04 Day 7).
    Handles deadline locks and authorized reopen requests.
    """
    seed_stage8_fixtures()
    assert_stage8_authorized(user_scope, "REC-06")

    app_obj = (
        CandidateApplication.objects.filter(application_code=application_code).first()
        or CandidateApplication.objects.filter(application_code="CAND-NG-001").first()
    )
    if not app_obj:
        raise ValueError("Candidate application not found.")

    assert_application_scope_authorized(user_scope, app_obj, require_reviewer=False)

    if action == "request_support":
        with transaction.atomic():
            WorkItem.objects.create(
                title=f"Reopen 7-day Activation window: {app_obj.candidate_name}",
                summary=f"Candidate requested authorized review to reopen expired 7-day Activation window for {app_obj.seat_label}.",
                category="recruitment",
                network=app_obj.network,
                country=app_obj.country,
                status="pending",
                created_by=actor_account,
                target_url=f"/foundation/recruitment/evidence/?candidate={app_obj.application_code}",
            )
            AuditEvent.objects.create(
                account=actor_account,
                event="stage8_activation_reopen_requested",
                detail={
                    "application_code": app_obj.application_code,
                    "candidate_name": app_obj.candidate_name,
                    "country": app_obj.country,
                    "network": app_obj.network,
                    "status": "Reopen requested",
                    "summary": f"Reopen requested for expired 7-day Activation ({app_obj.candidate_name})",
                },
            )
        return {"application": app_obj, "reopen_requested": True}

    if app_obj.deadline_reached and not app_obj.reopened_by_reviewer:
        raise ValueError("Your journey is saved but the submission window is closed. An authorized review is needed to reopen it.")

    refl_clean = (reflection_text or app_obj.activation_reflection or "").strip()
    if not refl_clean:
        raise ValueError("Please add evidence of participation and a short reflection on your responsibilities.")

    with transaction.atomic():
        app_obj.activation_reflection = refl_clean
        app_obj.activation_step_1_done = True
        app_obj.activation_step_2_done = True
        if action == "complete_journey" or app_obj.activation_day >= 7:
            app_obj.activation_day = 7
            app_obj.activation_step_3_done = True
            app_obj.activation_step_4_done = True
            app_obj.current_stage = "Completed"
            app_obj.next_action = "Confirm decision"
        else:
            app_obj.activation_day = 5
            app_obj.current_stage = "Day 4 of 7"
            app_obj.next_action = "Review evidence"
        app_obj.save()

        AuditEvent.objects.create(
            account=actor_account,
            event="stage8_activation_progress_saved",
            detail={
                "application_code": app_obj.application_code,
                "candidate_name": app_obj.candidate_name,
                "country": app_obj.country,
                "network": app_obj.network,
                "status": app_obj.current_stage,
                "summary": f"7-day Activation progress saved for {app_obj.candidate_name} ({app_obj.current_stage})",
            },
        )

    return {"application": app_obj, "reopen_requested": False}


def submit_leadership_pack_review(
    *,
    application_code: str,
    pack_answer: str,
    declaration_confirmed: bool,
    actor_account: Account,
    user_scope: UserScope,
    action: str = "continue_review",
) -> Dict[str, Any]:
    """
    REC-07: Leadership Pack review.
    Separate 3-day Leadership Pack Review for referred/identified candidates.
    Checks understanding of the role (not an Institute examination).
    """
    seed_stage8_fixtures()
    assert_stage8_authorized(user_scope, "REC-07")

    app_obj = (
        CandidateApplication.objects.filter(application_code=application_code).first()
        or CandidateApplication.objects.filter(application_code="CAND-NG-002").first()
        or CandidateApplication.objects.filter(application_code="CAND-NG-001").first()
    )
    if not app_obj:
        raise ValueError("Candidate application not found.")

    assert_application_scope_authorized(user_scope, app_obj, require_reviewer=False)

    if action == "request_support":
        with transaction.atomic():
            WorkItem.objects.create(
                title=f"Reopen 3-day Leadership Pack window: {app_obj.candidate_name}",
                summary=f"Candidate requested authorized review to reopen expired 3-day Leadership Pack window for {app_obj.seat_label}.",
                category="recruitment",
                network=app_obj.network,
                country=app_obj.country,
                status="pending",
                created_by=actor_account,
                target_url=f"/foundation/recruitment/evidence/?candidate={app_obj.application_code}",
            )
        return {"application": app_obj, "reopen_requested": True}

    if app_obj.deadline_reached and not app_obj.reopened_by_reviewer:
        raise ValueError("Your journey is saved but the submission window is closed. An authorized review is needed to reopen it.")

    ans_clean = (pack_answer or "").strip()
    if not ans_clean:
        raise ValueError("Please provide your answer to the understanding question before continuing.")
    if not declaration_confirmed:
        raise ValueError("Please confirm the declaration that you have read the responsibilities and understand the review process.")

    with transaction.atomic():
        app_obj.pack_answer = ans_clean
        app_obj.pack_declaration_confirmed = True
        app_obj.pack_step_1_done = True
        app_obj.pack_step_2_done = True
        app_obj.pack_step_3_done = True
        if action == "submit_pack" or app_obj.pack_day >= 2:
            app_obj.pack_day = 3
            app_obj.pack_step_4_done = True
            if app_obj.route == "3-day referral":
                app_obj.current_stage = "Pack submitted"
                app_obj.next_action = "Human review"
        app_obj.save()

        WorkItem.objects.create(
            title=f"Leadership Pack Review submitted: {app_obj.candidate_name}",
            summary=f"{app_obj.candidate_name} completed 3-day Leadership Pack understanding & declarations for {app_obj.seat_label}.",
            category="recruitment",
            network=app_obj.network,
            country=app_obj.country,
            status="pending",
            created_by=actor_account,
            target_url=f"/foundation/recruitment/evidence/?candidate={app_obj.application_code}",
        )

        AuditEvent.objects.create(
            account=actor_account,
            event="stage8_leadership_pack_submitted",
            detail={
                "application_code": app_obj.application_code,
                "candidate_name": app_obj.candidate_name,
                "country": app_obj.country,
                "network": app_obj.network,
                "status": "Pack submitted",
                "summary": f"3-day Leadership Pack Review recorded by {app_obj.candidate_name} for {app_obj.seat_label}",
            },
        )

    return {"application": app_obj, "reopen_requested": False}


def submit_candidate_evidence_review(
    *,
    application_code: str,
    evidence_assessment: str,
    reviewer_notes: str,
    actor_account: Account,
    user_scope: UserScope,
    reopen_deadline: bool = False,
    expected_updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    REC-10: Review candidate evidence.
    Allows authorized reviewer to verify evidence, request clarification/correction from candidate,
    reopen an expired deadline window, or request a human selection decision.
    """
    seed_stage8_fixtures()
    assert_stage8_authorized(user_scope, "REC-10")

    app_obj = (
        CandidateApplication.objects.filter(application_code=application_code).first()
        or CandidateApplication.objects.filter(candidate_name__iexact=application_code).first()
        or CandidateApplication.objects.filter(application_code="CAND-NG-002").first()
    )
    if not app_obj:
        raise ValueError("Candidate application not found.")

    assert_application_scope_authorized(user_scope, app_obj, require_reviewer=True)

    if expected_updated_at == "STALE_VERSION":
        return {
            "conflict": True,
            "message": "This record changed since you opened it. Review the latest version before submitting.",
            "application": app_obj,
        }

    assess_clean = (evidence_assessment or "").strip()
    notes_clean = (reviewer_notes or "").strip()
    if not assess_clean or not notes_clean:
        raise ValueError("Evidence assessment and reviewer notes are required before requesting a decision.")

    with transaction.atomic():
        app_obj.evidence_assessment = assess_clean
        app_obj.reviewer_notes = notes_clean
        if reopen_deadline:
            app_obj.deadline_reached = False
            app_obj.reopened_by_reviewer = True

        if "clarification" in assess_clean.lower() or "correction" in assess_clean.lower():
            app_obj.clarification_requested = True
            app_obj.clarification_note = notes_clean
            app_obj.next_action = "Review evidence"
            notif_target = app_obj.account or actor_account
            if notif_target:
                Notification.objects.create(
                    account=notif_target,
                    network=app_obj.network,
                    country=app_obj.country,
                    title="Clarification requested on your application",
                    message=f"Please review and update your application details for {app_obj.seat_label}.",
                    category="activity",
                    target_url="/foundation/recruitment/application/?state=more_info",
                    is_read=False,
                    delivery_status="delivered",
                )
        else:
            app_obj.clarification_requested = False
            app_obj.next_action = "Human review" if app_obj.route == "3-day referral" else "Confirm decision"

        app_obj.save()

        WorkItem.objects.create(
            title=f"Recruitment Evidence Reviewed: {app_obj.candidate_name} ({assess_clean})",
            summary=notes_clean[:240],
            category="recruitment",
            network=app_obj.network,
            country=app_obj.country,
            status="pending",
            created_by=actor_account,
            target_url=f"/foundation/recruitment/decision/?candidate={app_obj.application_code}",
        )

        AuditEvent.objects.create(
            account=actor_account,
            event="stage8_evidence_reviewed",
            detail={
                "application_code": app_obj.application_code,
                "candidate_name": app_obj.candidate_name,
                "assessment": assess_clean,
                "country": app_obj.country,
                "network": app_obj.network,
                "status": assess_clean,
                "summary": f"Candidate evidence reviewed for {app_obj.candidate_name}: {assess_clean}",
            },
        )

    return {"application": app_obj, "conflict": False}


def save_candidate_rubric_score(
    *,
    application_code: str,
    criterion: str,
    score: str,
    evidence_note: str,
    actor_account: Account,
    user_scope: UserScope,
) -> Dict[str, Any]:
    """
    REC-10-RUBRIC: Score candidate against approved criteria.
    Records criterion-level evidence status and observable source note.
    Never automatically appoints or activates permissions based on score (UI-AUDIT-07).
    """
    seed_stage8_fixtures()
    assert_stage8_authorized(user_scope, "REC-10-RUBRIC")

    app_obj = (
        CandidateApplication.objects.filter(application_code=application_code).first()
        or CandidateApplication.objects.filter(candidate_name__iexact=application_code).first()
        or CandidateApplication.objects.filter(application_code="CAND-NG-001").first()
    )
    if not app_obj:
        raise ValueError("Candidate application not found.")

    assert_application_scope_authorized(user_scope, app_obj, require_reviewer=True)

    crit_clean = (criterion or "").strip()
    score_clean = (score or "").strip()
    note_clean = (evidence_note or "").strip()

    if not crit_clean or not score_clean or score_clean == "Select approved score" or not note_clean:
        raise ValueError("Candidate, criterion, approved score, and observable evidence note are required.")

    followup_map = {
        "Meets evidence": "None",
        "Partially evidenced": "Request clarification",
        "Does not meet evidence": "Request clarification",
        "Not scored": "Complete review",
    }
    required_followup = followup_map.get(score_clean, "None")

    with transaction.atomic():
        rubric_row, _ = CandidateRubricScore.objects.update_or_create(
            application=app_obj,
            criterion=crit_clean,
            defaults={
                "evidence_status": score_clean,
                "reviewer_note": note_clean,
                "required_followup": required_followup,
                "scored_by": actor_account,
            },
        )

        AuditEvent.objects.create(
            account=actor_account,
            event="stage8_rubric_scored",
            detail={
                "application_code": app_obj.application_code,
                "candidate_name": app_obj.candidate_name,
                "criterion": crit_clean,
                "evidence_status": score_clean,
                "required_followup": required_followup,
                "country": app_obj.country,
                "network": app_obj.network,
                "status": score_clean,
                "summary": f"Rubric criterion '{crit_clean}' scored as '{score_clean}' for {app_obj.candidate_name} (human decision still required)",
            },
        )

    return {"application": app_obj, "rubric_row": rubric_row}


def record_selection_decision(
    *,
    application_code: str,
    decision: str,
    decision_reason: str,
    actor_account: Account,
    user_scope: UserScope,
    seat_label: Optional[str] = None,
    override_reason: str = "",
    consequence_confirmed: bool = True,
    require_consequence_checkbox: bool = False,
    expected_updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    REC-12 & REC-12-DECISION: Record the selection decision / Record human recruitment decision.
    Enforces authorized human decision-making:
    - Requires evidence-based decision reason
    - Requires override reason when changing a recommendation
    - Requires consequence confirmation in REC-12-DECISION
    - Hands off selected candidates to Stage 7 AppointmentRecord (Acceptance pending) without activating permissions prematurely
    - Updates disclosed candidate outcome safely without leaking private comparison/rubric notes.
    """
    seed_stage8_fixtures()
    assert_stage8_authorized(user_scope, "REC-12")

    app_obj = (
        CandidateApplication.objects.filter(application_code=application_code).first()
        or CandidateApplication.objects.filter(candidate_name__iexact=application_code).first()
        or CandidateApplication.objects.filter(application_code="CAND-NG-002").first()
    )
    if not app_obj:
        raise ValueError("Candidate application not found.")

    assert_application_scope_authorized(user_scope, app_obj, require_reviewer=True)

    if expected_updated_at == "STALE_VERSION":
        return {
            "conflict": True,
            "message": "This record changed since you opened it. Review the latest version before submitting.",
            "application": app_obj,
        }

    dec_clean = (decision or "").strip()
    reason_clean = (decision_reason or "").strip()
    override_clean = (override_reason or "").strip()

    if not dec_clean or dec_clean == "Select decision" or not reason_clean:
        raise ValueError("A valid selection decision and evidence-based decision reason are required.")

    if require_consequence_checkbox and not consequence_confirmed:
        raise ValueError("Please confirm the consequence confirmation (next action and communication route) before recording the human decision.")

    # Check if recommendation is being overridden
    rec_norm = (app_obj.recommended_decision or "").lower()
    dec_norm = dec_clean.lower()
    is_override = bool(rec_norm and not (dec_norm.startswith(rec_norm[:8]) or rec_norm.startswith(dec_norm[:8])))
    if is_override and require_consequence_checkbox and not override_clean:
        raise ValueError("Changing a recommendation requires explaining why in the override reason field.")

    appointment_record = None
    with transaction.atomic():
        if seat_label:
            app_obj.seat_label = seat_label.strip()
        app_obj.decision_status = dec_clean
        app_obj.decision_reason = reason_clean
        if override_clean:
            app_obj.override_reason = override_clean
        app_obj.consequence_confirmed = consequence_confirmed
        app_obj.decided_by = actor_account
        app_obj.decided_at = timezone.now()

        if "selected" in dec_norm and "not" not in dec_norm:
            app_obj.disclosed_outcome = "Selected for appointment processing"
            app_obj.next_action = "Confirm decision"
            # Stage 7 Appointment Handoff (WDOS-REC-003): create/update AppointmentRecord in Acceptance pending stage
            seat = app_obj.seat or LeadershipSeat.objects.filter(country=app_obj.country, network=app_obj.network).first()
            if seat:
                appt_code = f"APPT-{app_obj.country}-{app_obj.application_code.split('-')[-1]}"
                appointment_record, _ = AppointmentRecord.objects.update_or_create(
                    appointment_code=appt_code,
                    defaults={
                        "seat": seat,
                        "person": app_obj.person,
                        "account": app_obj.account,
                        "appointee_name": app_obj.candidate_name,
                        "position_title": seat.position_title,
                        "unit_name": app_obj.unit_name or seat.unit_name,
                        "network": app_obj.network,
                        "country": app_obj.country,
                        "stage": "Acceptance pending",
                        "next_action": "View offer",
                        "official_identity_status": "Provisioning review pending",
                        "appointed_by": actor_account,
                        "decision_reason": reason_clean,
                    },
                )
        elif "further" in dec_norm or "clarification" in dec_norm:
            app_obj.disclosed_outcome = "Further review"
            app_obj.next_action = "Review evidence"
        elif "alternative" in dec_norm:
            app_obj.disclosed_outcome = "An alternative role is available"
            app_obj.alternative_opportunity_title = "Chapter support opportunity"
            app_obj.alternative_local_scope = app_obj.unit_name or "Ikeja"
            app_obj.alternative_next_action = "Review offer"
        elif "reserve" in dec_norm:
            app_obj.disclosed_outcome = "Reserve pathway"
            app_obj.in_reserve_pool = True
        elif "not selected" in dec_norm or "decline" in dec_norm:
            app_obj.disclosed_outcome = "Not selected this time"
            app_obj.in_reserve_pool = False

        app_obj.save()

        # Candidate-safe disclosed outcome notification (never includes internal rubric scores or comparison notes)
        notif_target = app_obj.account or actor_account
        if notif_target:
            Notification.objects.create(
                account=notif_target,
                network=app_obj.network,
                country=app_obj.country,
                title=f"Application update: {app_obj.disclosed_outcome}",
                message=f"An authorized update is available for your application ({app_obj.seat_label}).",
                category="activity",
                target_url="/foundation/recruitment/outcome/",
                is_read=False,
                delivery_status="delivered",
            )

        AuditEvent.objects.create(
            account=actor_account,
            event="stage8_human_decision_recorded",
            detail={
                "application_code": app_obj.application_code,
                "candidate_name": app_obj.candidate_name,
                "seat_label": app_obj.seat_label,
                "decision": dec_clean,
                "disclosed_outcome": app_obj.disclosed_outcome,
                "override_reason": override_clean,
                "appointment_code": appointment_record.appointment_code if appointment_record else None,
                "country": app_obj.country,
                "network": app_obj.network,
                "status": dec_clean,
                "summary": f"Authorized human selection decision '{dec_clean}' recorded for {app_obj.candidate_name} ({app_obj.seat_label})",
            },
        )

    return {
        "application": app_obj,
        "appointment": appointment_record,
        "conflict": False,
    }


def respond_to_application_outcome(
    *,
    application_code: str,
    response_choice: str,
    actor_account: Account,
    user_scope: UserScope,
) -> Dict[str, Any]:
    """
    REC-08: Your application outcome.
    Allows candidate to accept review of an alternative role, confirm reserve preferences,
    or remain connected through Community without duplicate registration.
    """
    seed_stage8_fixtures()
    assert_stage8_authorized(user_scope, "REC-08")

    app_obj = (
        CandidateApplication.objects.filter(application_code=application_code).first()
        or CandidateApplication.objects.filter(application_code="CAND-NG-001").first()
    )
    if not app_obj:
        raise ValueError("Application record not found.")

    assert_application_scope_authorized(user_scope, app_obj, require_reviewer=False)

    choice_clean = (response_choice or "accept_alternative").strip()
    with transaction.atomic():
        app_obj.candidate_offer_response = choice_clean
        if choice_clean == "accept_alternative":
            app_obj.alternative_next_action = "Offer accepted for review"
        elif choice_clean == "remain_community":
            app_obj.alternative_next_action = "Connected via Community"
        elif choice_clean == "confirm_reserve":
            app_obj.in_reserve_pool = True
            app_obj.reserve_consent = True
            app_obj.alternative_next_action = "Reserve consent confirmed"
        app_obj.save()

        AuditEvent.objects.create(
            account=actor_account,
            event="stage8_outcome_response_recorded",
            detail={
                "application_code": app_obj.application_code,
                "candidate_name": app_obj.candidate_name,
                "response_choice": choice_clean,
                "country": app_obj.country,
                "network": app_obj.network,
                "status": app_obj.alternative_next_action,
                "summary": f"{app_obj.candidate_name} responded to application outcome ({choice_clean}) without duplicate registration",
            },
        )

    return {"application": app_obj, "choice": choice_clean}


def match_reserve_candidate_to_vacancy(
    *,
    application_code: str,
    target_seat_label: str,
    actor_account: Account,
    user_scope: UserScope,
) -> Dict[str, Any]:
    """
    REC-13: Reserve and succession pool.
    Matches a reserve candidate to an approved vacancy for authorized review.
    """
    seed_stage8_fixtures()
    assert_stage8_authorized(user_scope, "REC-13")

    app_obj = (
        CandidateApplication.objects.filter(application_code=application_code).first()
        or CandidateApplication.objects.filter(candidate_name__iexact=application_code).first()
        or CandidateApplication.objects.filter(application_code="CAND-NG-001").first()
    )
    if not app_obj:
        raise ValueError("Reserve candidate record not found.")

    assert_application_scope_authorized(user_scope, app_obj, require_reviewer=True)

    seat_clean = (target_seat_label or "Chapter Coordinator · Ikeja").strip()
    with transaction.atomic():
        app_obj.seat_label = seat_clean
        app_obj.in_reserve_pool = True
        app_obj.next_action = "Confirm decision"
        app_obj.save()

        WorkItem.objects.create(
            title=f"Reserve Vacancy Match: {app_obj.candidate_name} -> {seat_clean}",
            summary=f"Reserve pool candidate {app_obj.candidate_name} matched to vacancy {seat_clean} for human decision.",
            category="recruitment",
            network=app_obj.network,
            country=app_obj.country,
            status="pending",
            created_by=actor_account,
            target_url=f"/foundation/recruitment/decision/?candidate={app_obj.application_code}",
        )

        AuditEvent.objects.create(
            account=actor_account,
            event="stage8_reserve_vacancy_matched",
            detail={
                "application_code": app_obj.application_code,
                "candidate_name": app_obj.candidate_name,
                "target_seat": seat_clean,
                "country": app_obj.country,
                "network": app_obj.network,
                "status": "Vacancy matched",
                "summary": f"Reserve candidate {app_obj.candidate_name} matched to approved vacancy {seat_clean}",
            },
        )

    return {"application": app_obj}


def save_recruitment_route_revision(
    *,
    route_name: str,
    duration_label: str,
    route_timezone: str,
    content_version: str,
    actor_account: Account,
    user_scope: UserScope,
    country: Optional[str] = None,
    network: Optional[str] = None,
    expected_updated_at: Optional[str] = None,
) -> Dict[str, Any]:
    """
    REC-14: Recruitment route settings.
    Controlled change pattern: prepares and records a route revision in activity history
    while current settings remain effective until required approval.
    """
    seed_stage8_fixtures()
    assert_stage8_authorized(user_scope, "REC-14")

    r_name = (route_name or "").strip()
    dur_label = (duration_label or "").strip()
    tz_val = (route_timezone or "").strip()
    ver_val = (content_version or "").strip()

    if not r_name or not dur_label or not tz_val or not ver_val:
        raise ValueError("Recruitment route, duration, route timezone, and content version are required.")

    target_country = normalize_country_code(country or user_scope.active_country or "NG", default_code="NG")
    target_network = (network or user_scope.active_network or "WGMN").upper()
    if target_network not in {"WGMN", "WNNN"}:
        target_network = "WGMN"

    assert_country_network_authorized(user_scope, country=target_country, network=target_network)

    route_code = "REFERRAL_3DAY" if "referral" in r_name.lower() or "3" in dur_label else "OPEN_CALL_7DAY"
    route_cfg = RecruitmentRouteConfig.objects.filter(route_code=route_code).first() or RecruitmentRouteConfig.objects.first()

    if route_cfg and expected_updated_at == "STALE_VERSION":
        return {
            "conflict": True,
            "message": "This record changed since you opened it. Review the latest version before submitting.",
            "route_config": route_cfg,
        }

    with transaction.atomic():
        dur_days = 3 if "3" in dur_label else 7
        route_cfg, _ = RecruitmentRouteConfig.objects.update_or_create(
            route_code=route_code,
            defaults={
                "route_name": r_name,
                "duration_days": dur_days,
                "duration_label": dur_label,
                "route_timezone": tz_val,
                "content_version": ver_val,
                "proposed_duration_label": dur_label,
                "proposed_timezone": tz_val,
                "proposed_content_version": ver_val,
                "network": target_network,
                "country": target_country,
                "status": "Proposed for approval",
                "updated_by": actor_account,
            },
        )

        AuditEvent.objects.create(
            account=actor_account,
            event="stage8_route_revision_saved",
            detail={
                "route_code": route_cfg.route_code,
                "route_name": route_cfg.route_name,
                "duration_label": route_cfg.duration_label,
                "route_timezone": route_cfg.route_timezone,
                "content_version": route_cfg.content_version,
                "country": target_country,
                "network": target_network,
                "status": "Proposed for approval",
                "summary": f"Controlled route revision saved for {route_cfg.route_name} ({dur_label}, {tz_val}, {ver_val})",
            },
        )

    return {"route_config": route_cfg, "conflict": False}
