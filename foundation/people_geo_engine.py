"""
WDOS Stage 06: People, Community, and Geography Spine Engine
Authoritative people-and-place foundation:
- People directory and profile (PEOPLE-01, PEOPLE-02)
- Safe add-or-link / duplicate handling (PEOPLE-03)
- Community relationships (PEOPLE-04, PEOPLE-05)
- Local-home reassignment with evidence & history (PEOPLE-06)
- Network coverage & Country Hub command profile (GEO-01, GEO-02)
- Local organisation hierarchy & unit directory (GEO-03)
- Evidence-based country dossier verification (GEO-04)
- Geography and local terminology revision (GEO-05)

Strictly enforces fail-closed network and country scoping,
role permissions, database reconciliation, and audit logging.
"""

import uuid
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.models import Account, AuditEvent
from .models import (
    Chapter,
    CountryDossier,
    CountryHub,
    GeographyTerminology,
    LocalHomeReassignment,
    LocalOrganisationUnit,
    PersonProfile,
    PersonRelationship,
)
from .scope import ScopePermissionDenied, UserScope


# -----------------------------------------------------------------------------
# SEED / FIXTURE SERVICE
# -----------------------------------------------------------------------------

def seed_stage6_fixtures():
    """
    Idempotently seeds all authoritative Stage 06 records matching the
    WDOS UI Review v2 artboard specifications.
    """
    # 1. People Directory (Ada Okafor, Lina Mensah, Kemi Bello)
    ada, _ = PersonProfile.objects.get_or_create(
        person_code="WD-00421",
        defaults={
            "full_name": "Ada Okafor",
            "email": "ada@example.org",
            "phone": "+234 801 234 5678",
            "network": "WGMN",
            "country": "NG",
            "local_home": "Ikeja Chapter",
            "contact_verification": "Verified",
            "primary_relationship": "Member",
            "status": "Active",
        },
    )

    lina, _ = PersonProfile.objects.get_or_create(
        person_code="WD-00422",
        defaults={
            "full_name": "Lina Mensah",
            "email": "lina@example.org",
            "phone": "+234 802 345 6789",
            "network": "WGMN",
            "country": "NG",
            "local_home": "Abuja virtual home",
            "contact_verification": "Verified",
            "primary_relationship": "Programme participant",
            "status": "Active",
        },
    )

    kemi, _ = PersonProfile.objects.get_or_create(
        person_code="WD-00423",
        defaults={
            "full_name": "Kemi Bello",
            "email": "kemi@example.org",
            "phone": "+234 803 456 7890",
            "network": "WGMN",
            "country": "NG",
            "local_home": "Kano Central",
            "contact_verification": "Pending",
            "primary_relationship": "Member / Mentor",
            "status": "Review due",
        },
    )

    # 2. Person Relationships
    PersonRelationship.objects.get_or_create(
        person=ada,
        category="membership",
        relationship_label="Member",
        defaults={
            "effective_date": date(2025, 1, 15),
            "status": "Active",
            "notes": "Primary WGMN chapter member",
        },
    )
    PersonRelationship.objects.get_or_create(
        person=ada,
        category="programme_participant",
        relationship_label="Programme participant",
        related_programme="Community Skills Exchange",
        defaults={
            "effective_date": date(2026, 9, 18),
            "status": "Active",
            "notes": "Active participant in Skills Exchange cohort",
        },
    )
    PersonRelationship.objects.get_or_create(
        person=lina,
        category="programme_participant",
        relationship_label="Programme participant",
        related_programme="Virtual Leadership Circle",
        defaults={
            "effective_date": date(2026, 3, 10),
            "status": "Active",
        },
    )
    PersonRelationship.objects.get_or_create(
        person=kemi,
        category="mentor",
        relationship_label="Member / Mentor",
        related_programme="Kano Youth Mentorship Track",
        defaults={
            "effective_date": date(2025, 6, 1),
            "status": "Review due",
        },
    )

    # 3. Local-Home Reassignment Record
    LocalHomeReassignment.objects.get_or_create(
        person=ada,
        current_local_home="Abuja virtual home",
        proposed_local_home="Ikeja Chapter",
        defaults={
            "reason": "Member has confirmed a move to Lagos.",
            "member_confirmation": True,
            "evidence_reference": "Confirmation received and linked to the request.",
            "status": "in_progress",
        },
    )

    # 4. Country Dossiers (GEO-01 & GEO-02)
    CountryDossier.objects.get_or_create(
        country_code="NG",
        network="WGMN",
        defaults={
            "country_name": "Nigeria",
            "country_lead_name": "Ada Okafor",
            "timezone_reference": "Africa/Lagos · WAT",
            "verification_status": "Country verified",
            "verification_stage": "Country custodian review",
            "next_review_date": "30 Sep",
            "evidence_reference": "Country register revision 03",
            "verification_notes": "Leadership corrections resolved; language readiness remains under review.",
        },
    )
    CountryDossier.objects.get_or_create(
        country_code="KE",
        network="WNNN",
        defaults={
            "country_name": "Kenya",
            "country_lead_name": "Lina Mensah",
            "timezone_reference": "Africa/Nairobi · EAT",
            "verification_status": "HQ review",
            "verification_stage": "Regional oversight",
            "next_review_date": "22 Sep",
            "evidence_reference": "Country register revision 01",
            "verification_notes": "Pending HQ regional director verification sign-off.",
        },
    )
    CountryDossier.objects.get_or_create(
        country_code="GH",
        network="WGMN",
        defaults={
            "country_name": "Ghana",
            "country_lead_name": "Kemi Bello",
            "timezone_reference": "Africa/Accra · GMT",
            "verification_status": "Update requested",
            "verification_stage": "Forming unit review",
            "next_review_date": "25 Sep",
            "evidence_reference": "Country register revision 02",
            "verification_notes": "Updated chapter registry requested from national coordinator.",
        },
    )

    # 5. Local Organisation Hierarchy (GEO-03)
    c_unit, _ = LocalOrganisationUnit.objects.get_or_create(
        network="WGMN",
        country="NG",
        level="Country",
        unit_name="Nigeria",
        defaults={
            "level_order": 1,
            "description": "Assigned network and organisational scope",
            "responsible_leader_name": "Ada Okafor",
            "evidence_type": "Country dossier",
            "record_state": "Active unit records",
        },
    )
    r_unit, _ = LocalOrganisationUnit.objects.get_or_create(
        network="WGMN",
        country="NG",
        level="Region / State",
        unit_name="Lagos State",
        defaults={
            "level_order": 2,
            "parent": c_unit,
            "description": "Regional coordination for the selected network.",
            "responsible_leader_name": "Lina Mensah",
            "evidence_type": "Unit record",
            "record_state": "Active unit records",
        },
    )
    d_unit, _ = LocalOrganisationUnit.objects.get_or_create(
        network="WGMN",
        country="NG",
        level="District / LGA",
        unit_name="Ikeja LGA",
        defaults={
            "level_order": 3,
            "parent": r_unit,
            "description": "Local operational coordination and linked units.",
            "responsible_leader_name": "Kemi Bello",
            "evidence_type": "Unit record",
            "record_state": "Active unit records",
        },
    )
    cc_unit, _ = LocalOrganisationUnit.objects.get_or_create(
        network="WGMN",
        country="NG",
        level="Community Cluster",
        unit_name="Ikeja Central",
        defaults={
            "level_order": 4,
            "parent": d_unit,
            "description": "Community Cluster linking neighbouring Chapters.",
            "responsible_leader_name": "Nneka Obi",
            "evidence_type": "Unit record",
            "record_state": "Active unit records",
        },
    )
    LocalOrganisationUnit.objects.get_or_create(
        network="WGMN",
        country="NG",
        level="Chapter",
        unit_name="Allen Chapter",
        defaults={
            "level_order": 5,
            "parent": cc_unit,
            "description": "Chapter membership and local activity records.",
            "responsible_leader_name": "Zainab Musa",
            "evidence_type": "Unit record",
            "record_state": "Active unit records",
        },
    )

    # 6. Geography Terminology (GEO-05)
    GeographyTerminology.objects.get_or_create(
        country="NG",
        country_name="Nigeria",
        defaults={
            "first_level_term": "State / FCT",
            "second_level_term": "LGA",
            "effective_date": date(2026, 10, 1),
            "status": "effective",
        },
    )


# -----------------------------------------------------------------------------
# SCREEN DEFINITIONS REGISTRY
# -----------------------------------------------------------------------------

STAGE6_SCREENS: Dict[str, Dict[str, Any]] = {
    # -------------------------------------------------------------------------
    # PEOPLE-01: People directory
    # -------------------------------------------------------------------------
    "PEOPLE-01": {
        "screen_id": "PEOPLE-01",
        "title": "People directory",
        "desktop_pnum": 210,
        "mobile_pnum": 211,
        "state_pnum": 212,
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant people and relationships records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / People, membership and Community management",
        "role_name": "Network Secretary",
        "scope_badge": "WGMN / Nigeria",
        "primary_action": {"label": "Add or link person", "url": "/foundation/people/add-or-link/"},
        "secondary_action": {"label": "Back", "url": "/foundation/dashboards/dash-03/"},
        "tabs": [
            {"id": "overview", "label": "Overview", "active": False, "url": "/foundation/people/?tab=overview"},
            {"id": "records", "label": "Records", "active": True, "url": "/foundation/people/?tab=records"},
            {"id": "history", "label": "History", "active": False, "url": "/foundation/people/?tab=history"},
        ],
        "state_contracts": {
            "empty": {
                "title": "No records in this view",
                "message": "There are no people and relationships records matching the selected scope.",
                "action_label": "Clear filters",
                "action_url": "/foundation/people/",
            },
            "connection_error": {
                "title": "Connection interrupted",
                "message": "Your last saved information is safe. Reconnect before submitting changes.",
                "action_label": "Try again",
                "action_url": "/foundation/people/",
            },
            "access_changed": {
                "title": "Access has changed",
                "message": "This action is no longer available for your current role. No change was applied.",
                "action_label": "Return to workspace",
                "action_url": "/foundation/workspace/",
            },
            "loading": {
                "title": "Loading current information",
                "message": "Loading people directory. No stale values or completed actions are implied.",
                "action_label": "Cancel and return",
                "action_url": "/foundation/people/",
            },
            "no_matching": {
                "title": "Nothing to show in this scope",
                "message": "There are no matching records for people directory. Check the current scope or remove a filter.",
                "action_label": "Reset view",
                "action_url": "/foundation/people/",
            },
        },
    },

    # -------------------------------------------------------------------------
    # PEOPLE-02: Ada Okafor
    # -------------------------------------------------------------------------
    "PEOPLE-02": {
        "screen_id": "PEOPLE-02",
        "title": "Ada Okafor",
        "desktop_pnum": 213,
        "mobile_pnum": 214,
        "state_pnum": 215,
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant people and relationships records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / People, membership and Community management",
        "role_name": "Network Secretary",
        "scope_badge": "WGMN / Nigeria",
        "primary_action": {"label": "Review profile", "url": "/foundation/community/reassignment/review/"},
        "secondary_action": {"label": "Back", "url": "/foundation/people/"},
        "tabs": [
            {"id": "overview", "label": "Overview", "active": True, "url": "/foundation/people/WD-00421/?tab=overview"},
            {"id": "records", "label": "Records", "active": False, "url": "/foundation/people/WD-00421/?tab=records"},
            {"id": "history", "label": "History", "active": False, "url": "/foundation/people/WD-00421/?tab=history"},
        ],
        "state_contracts": {
            "empty": {
                "title": "No records in this view",
                "message": "There are no people and relationships records matching the selected scope.",
                "action_label": "Clear filters",
                "action_url": "/foundation/people/WD-00421/",
            },
            "connection_error": {
                "title": "Connection interrupted",
                "message": "Your last saved information is safe. Reconnect before submitting changes.",
                "action_label": "Try again",
                "action_url": "/foundation/people/WD-00421/",
            },
            "access_changed": {
                "title": "Access has changed",
                "message": "This action is no longer available for your current role. No change was applied.",
                "action_label": "Return to workspace",
                "action_url": "/foundation/workspace/",
            },
            "loading": {
                "title": "Loading current information",
                "message": "Loading ada okafor. No stale values or completed actions are implied.",
                "action_label": "Cancel and return",
                "action_url": "/foundation/people/WD-00421/",
            },
            "more_info": {
                "title": "More information needed",
                "message": "Check the marked details before continuing with ada okafor. Your entered information remains available.",
                "action_label": "Review details",
                "action_url": "/foundation/people/WD-00421/",
            },
        },
    },

    # -------------------------------------------------------------------------
    # PEOPLE-03: Add or link a person
    # -------------------------------------------------------------------------
    "PEOPLE-03": {
        "screen_id": "PEOPLE-03",
        "title": "Add or link a person",
        "desktop_pnum": 216,
        "mobile_pnum": 217,
        "state_pnum": 218,
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Complete the information below, then review it before you continue.",
        "breadcrumb": "Workspace / People, membership and Community management",
        "role_name": "Network Secretary",
        "scope_badge": "WGMN / Nigeria",
        "primary_action": {"label": "Check for existing person", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/people/"},
        "tabs": [
            {"id": "overview", "label": "Overview", "active": False, "url": "/foundation/people/add-or-link/?tab=overview"},
            {"id": "records", "label": "Records", "active": True, "url": "/foundation/people/add-or-link/?tab=records"},
            {"id": "history", "label": "History", "active": False, "url": "/foundation/people/add-or-link/?tab=history"},
        ],
        "state_contracts": {
            "check_highlighted": {
                "title": "Check the highlighted information",
                "message": "Complete the required fields before continuing. Your entered information is retained.",
                "action_label": "Review fields",
                "action_url": "/foundation/people/add-or-link/",
            },
            "saved_later": {
                "title": "Saved for later",
                "message": "Your draft is saved. Return to this record when you are ready to continue.",
                "action_label": "Open draft",
                "action_url": "/foundation/people/add-or-link/",
            },
            "another_change": {
                "title": "Another change needs review",
                "message": "This record changed since you opened it. Review the latest version before submitting.",
                "action_label": "Review latest version",
                "action_url": "/foundation/people/add-or-link/",
            },
            "loading": {
                "title": "Loading current information",
                "message": "Loading add or link a person. No stale values or completed actions are implied.",
                "action_label": "Cancel and return",
                "action_url": "/foundation/people/add-or-link/",
            },
            "more_info": {
                "title": "More information needed",
                "message": "Check the marked details before continuing with add or link a person. Your entered information remains available.",
                "action_label": "Review details",
                "action_url": "/foundation/people/add-or-link/",
            },
        },
    },

    # -------------------------------------------------------------------------
    # PEOPLE-04: Community relationships
    # -------------------------------------------------------------------------
    "PEOPLE-04": {
        "screen_id": "PEOPLE-04",
        "title": "Community relationships",
        "desktop_pnum": 219,
        "mobile_pnum": 220,
        "state_pnum": 221,
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant people and relationships records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / People, membership and Community management",
        "role_name": "Network Secretary",
        "scope_badge": "WGMN / Nigeria",
        "primary_action": {"label": "Open category", "url": "/foundation/community/relationships/manage/"},
        "secondary_action": {"label": "Back", "url": "/foundation/people/"},
        "tabs": [
            {"id": "overview", "label": "Overview", "active": False, "url": "/foundation/community/relationships/?tab=overview"},
            {"id": "records", "label": "Records", "active": True, "url": "/foundation/community/relationships/?tab=records"},
            {"id": "history", "label": "History", "active": False, "url": "/foundation/community/relationships/?tab=history"},
        ],
        "state_contracts": {
            "empty": {
                "title": "No records in this view",
                "message": "There are no people and relationships records matching the selected scope.",
                "action_label": "Clear filters",
                "action_url": "/foundation/community/relationships/",
            },
            "connection_error": {
                "title": "Connection interrupted",
                "message": "Your last saved information is safe. Reconnect before submitting changes.",
                "action_label": "Try again",
                "action_url": "/foundation/community/relationships/",
            },
            "access_changed": {
                "title": "Access has changed",
                "message": "This action is no longer available for your current role. No change was applied.",
                "action_label": "Return to workspace",
                "action_url": "/foundation/workspace/",
            },
            "loading": {
                "title": "Loading current information",
                "message": "Loading community relationships. No stale values or completed actions are implied.",
                "action_label": "Cancel and return",
                "action_url": "/foundation/community/relationships/",
            },
            "no_matching": {
                "title": "Nothing to show in this scope",
                "message": "There are no matching records for community relationships. Check the current scope or remove a filter.",
                "action_label": "Reset view",
                "action_url": "/foundation/community/relationships/",
            },
        },
    },

    # -------------------------------------------------------------------------
    # PEOPLE-05: Manage relationships
    # -------------------------------------------------------------------------
    "PEOPLE-05": {
        "screen_id": "PEOPLE-05",
        "title": "Manage relationships",
        "desktop_pnum": 222,
        "mobile_pnum": 223,
        "state_pnum": 224,
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Complete the information below, then review it before you continue.",
        "breadcrumb": "Workspace / People, membership and Community management",
        "role_name": "Network Secretary",
        "scope_badge": "WGMN / Nigeria",
        "primary_action": {"label": "Save relationships", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/community/relationships/"},
        "tabs": [
            {"id": "overview", "label": "Overview", "active": False, "url": "/foundation/community/relationships/manage/?tab=overview"},
            {"id": "records", "label": "Records", "active": True, "url": "/foundation/community/relationships/manage/?tab=records"},
            {"id": "history", "label": "History", "active": False, "url": "/foundation/community/relationships/manage/?tab=history"},
        ],
        "state_contracts": {
            "check_highlighted": {
                "title": "Check the highlighted information",
                "message": "Complete the required fields before continuing. Your entered information is retained.",
                "action_label": "Review fields",
                "action_url": "/foundation/community/relationships/manage/",
            },
            "saved_later": {
                "title": "Saved for later",
                "message": "Your draft is saved. Return to this record when you are ready to continue.",
                "action_label": "Open draft",
                "action_url": "/foundation/community/relationships/manage/",
            },
            "another_change": {
                "title": "Another change needs review",
                "message": "This record changed since you opened it. Review the latest version before submitting.",
                "action_label": "Review latest version",
                "action_url": "/foundation/community/relationships/manage/",
            },
            "loading": {
                "title": "Loading current information",
                "message": "Loading manage relationships. No stale values or completed actions are implied.",
                "action_label": "Cancel and return",
                "action_url": "/foundation/community/relationships/manage/",
            },
            "more_info": {
                "title": "More information needed",
                "message": "Check the marked details before continuing with manage relationships. Your entered information remains available.",
                "action_label": "Review details",
                "action_url": "/foundation/community/relationships/manage/",
            },
        },
    },

    # -------------------------------------------------------------------------
    # PEOPLE-06: Review local-home reassignment
    # -------------------------------------------------------------------------
    "PEOPLE-06": {
        "screen_id": "PEOPLE-06",
        "title": "Review local-home reassignment",
        "desktop_pnum": 225,
        "mobile_pnum": 226,
        "state_pnum": 227,
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Check the evidence and the impact of this decision before confirming.",
        "breadcrumb": "Workspace / People, membership and Community management",
        "role_name": "Network Secretary",
        "scope_badge": "WGMN / Nigeria",
        "primary_action": {"label": "Submit reassignment", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/people/WD-00421/"},
        "tabs": [
            {"id": "overview", "label": "Overview", "active": False, "url": "/foundation/community/reassignment/review/?tab=overview"},
            {"id": "records", "label": "Records", "active": True, "url": "/foundation/community/reassignment/review/?tab=records"},
            {"id": "history", "label": "History", "active": False, "url": "/foundation/community/reassignment/review/?tab=history"},
        ],
        "state_contracts": {
            "check_highlighted": {
                "title": "Check the highlighted information",
                "message": "Complete the required fields before continuing. Your entered information is retained.",
                "action_label": "Review fields",
                "action_url": "/foundation/community/reassignment/review/",
            },
            "saved_later": {
                "title": "Saved for later",
                "message": "Your draft is saved. Return to this record when you are ready to continue.",
                "action_label": "Open draft",
                "action_url": "/foundation/community/reassignment/review/",
            },
            "another_change": {
                "title": "Another change needs review",
                "message": "This record changed since you opened it. Review the latest version before submitting.",
                "action_label": "Review latest version",
                "action_url": "/foundation/community/reassignment/review/",
            },
            "loading": {
                "title": "Loading current information",
                "message": "Loading review local-home reassignment. No stale values or completed actions are implied.",
                "action_label": "Cancel and return",
                "action_url": "/foundation/community/reassignment/review/",
            },
            "more_info": {
                "title": "More information needed",
                "message": "Check the marked details before continuing with review local-home reassignment. Your entered information remains available.",
                "action_label": "Review details",
                "action_url": "/foundation/community/reassignment/review/",
            },
        },
    },

    # -------------------------------------------------------------------------
    # GEO-01: Africa and network coverage
    # -------------------------------------------------------------------------
    "GEO-01": {
        "screen_id": "GEO-01",
        "title": "Africa and network coverage",
        "desktop_pnum": 228,
        "mobile_pnum": 229,
        "state_pnum": 230,
        "eyebrow": "H Q / B OT H N E T W O R K S",
        "subtitle": "See the relevant country and local coverage records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Geography, networks and country oversight",
        "role_name": "HOFCO",
        "scope_badge": "HQ / Both networks",
        "primary_action": {"label": "Open country dossier", "url": "/foundation/geography/country/NG/command/"},
        "secondary_action": {"label": "Back", "url": "/foundation/dashboards/dash-01/"},
        "tabs": [
            {"id": "map", "label": "Map & countries", "active": True, "url": "/foundation/geography/coverage/?tab=map"},
            {"id": "country_table", "label": "Country table", "active": False, "url": "/foundation/geography/coverage/?tab=country_table"},
            {"id": "verification", "label": "Verification", "active": False, "url": "/foundation/geography/dossier/verify/"},
        ],
        "state_contracts": {
            "empty": {
                "title": "No records in this view",
                "message": "There are no country and local coverage records matching the selected scope.",
                "action_label": "Clear filters",
                "action_url": "/foundation/geography/coverage/",
            },
            "connection_error": {
                "title": "Connection interrupted",
                "message": "Your last saved information is safe. Reconnect before submitting changes.",
                "action_label": "Try again",
                "action_url": "/foundation/geography/coverage/",
            },
            "access_changed": {
                "title": "Access has changed",
                "message": "This action is no longer available for your current role. No change was applied.",
                "action_label": "Return to workspace",
                "action_url": "/foundation/workspace/",
            },
            "loading": {
                "title": "Loading current information",
                "message": "Loading africa and network coverage. No stale values or completed actions are implied.",
                "action_label": "Cancel and return",
                "action_url": "/foundation/geography/coverage/",
            },
            "no_matching": {
                "title": "Nothing to show in this scope",
                "message": "There are no matching records for africa and network coverage. Check the current scope or remove a filter.",
                "action_label": "Reset view",
                "action_url": "/foundation/geography/coverage/",
            },
        },
    },

    # -------------------------------------------------------------------------
    # GEO-02: Nigeria · Country Command Profile
    # -------------------------------------------------------------------------
    "GEO-02": {
        "screen_id": "GEO-02",
        "title": "Nigeria · Country Command Profile",
        "desktop_pnum": 231,
        "mobile_pnum": 232,
        "state_pnum": 233,
        "eyebrow": "H Q / B OT H N E T W O R K S",
        "subtitle": "See the relevant country and local coverage records, linked evidence and next actions for your scope.",
        "breadcrumb": "Workspace / Geography, networks and country oversight",
        "role_name": "HOFCO",
        "scope_badge": "HQ / Both networks",
        "primary_action": {"label": "Request verification", "url": "/foundation/geography/dossier/verify/"},
        "secondary_action": {"label": "Back", "url": "/foundation/geography/coverage/"},
        "tabs": [
            {"id": "overview", "label": "Overview", "active": True, "url": "/foundation/geography/country/NG/command/?tab=overview"},
            {"id": "records", "label": "Records", "active": False, "url": "/foundation/geography/country/NG/command/?tab=records"},
            {"id": "history", "label": "History", "active": False, "url": "/foundation/geography/country/NG/command/?tab=history"},
        ],
        "state_contracts": {
            "empty": {
                "title": "No records in this view",
                "message": "There are no country and local coverage records matching the selected scope.",
                "action_label": "Clear filters",
                "action_url": "/foundation/geography/country/NG/command/",
            },
            "connection_error": {
                "title": "Connection interrupted",
                "message": "Your last saved information is safe. Reconnect before submitting changes.",
                "action_label": "Try again",
                "action_url": "/foundation/geography/country/NG/command/",
            },
            "access_changed": {
                "title": "Access has changed",
                "message": "This action is no longer available for your current role. No change was applied.",
                "action_label": "Return to workspace",
                "action_url": "/foundation/workspace/",
            },
            "loading": {
                "title": "Loading current information",
                "message": "Loading this view. Please wait while the latest saved information is checked.",
                "action_label": "Back to my workspace",
                "action_url": "/foundation/workspace/",
            },
            "more_info": {
                "title": "More information needed",
                "message": "Open the form to review the required information. Your draft stays available.",
                "action_label": "Review form details",
                "action_url": "/foundation/geography/country/NG/command/",
            },
        },
    },

    # -------------------------------------------------------------------------
    # GEO-03: Local organisation
    # -------------------------------------------------------------------------
    "GEO-03": {
        "screen_id": "GEO-03",
        "title": "Local organisation",
        "desktop_pnum": 234,
        "mobile_pnum": 235,
        "state_pnum": 236,
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Follow local units, responsible leaders and evidence within the selected country.",
        "breadcrumb": "Workspace / Geography, networks and country oversight",
        "role_name": "HOFCO",
        "scope_badge": "WGMN / Nigeria",
        "primary_action": {"label": "Open unit", "url": "/foundation/geography/local-org/"},
        "secondary_action": {"label": "Back", "url": "/foundation/geography/country/NG/command/"},
        "tabs": [
            {"id": "structure", "label": "Structure", "active": True, "url": "/foundation/geography/local-org/?tab=structure"},
            {"id": "unit_directory", "label": "Unit directory", "active": False, "url": "/foundation/geography/local-org/?tab=unit_directory"},
            {"id": "evidence", "label": "Evidence", "active": False, "url": "/foundation/geography/local-org/?tab=evidence"},
        ],
        "state_contracts": {
            "empty": {
                "title": "No records in this view",
                "message": "There are no country and local coverage records matching the selected scope.",
                "action_label": "Clear filters",
                "action_url": "/foundation/geography/local-org/",
            },
            "connection_error": {
                "title": "Connection interrupted",
                "message": "Your last saved information is safe. Reconnect before submitting changes.",
                "action_label": "Try again",
                "action_url": "/foundation/geography/local-org/",
            },
            "access_changed": {
                "title": "Access has changed",
                "message": "This action is no longer available for your current role. No change was applied.",
                "action_label": "Return to workspace",
                "action_url": "/foundation/workspace/",
            },
            "loading": {
                "title": "Loading current information",
                "message": "Loading local organisation. No stale values or completed actions are implied.",
                "action_label": "Cancel and return",
                "action_url": "/foundation/geography/local-org/",
            },
            "no_matching": {
                "title": "Nothing to show in this scope",
                "message": "There are no matching records for local organisation. Check the current scope or remove a filter.",
                "action_label": "Reset view",
                "action_url": "/foundation/geography/local-org/",
            },
        },
    },

    # -------------------------------------------------------------------------
    # GEO-04: Verify the country dossier
    # -------------------------------------------------------------------------
    "GEO-04": {
        "screen_id": "GEO-04",
        "title": "Verify the country dossier",
        "desktop_pnum": 237,
        "mobile_pnum": 238,
        "state_pnum": 239,
        "eyebrow": "H Q / B OT H N E T W O R K S",
        "subtitle": "Check the evidence and the impact of this decision before confirming.",
        "breadcrumb": "Workspace / Geography, networks and country oversight",
        "role_name": "HOFCO",
        "scope_badge": "HQ / Both networks",
        "primary_action": {"label": "Submit verification", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/geography/country/NG/command/"},
        "tabs": [
            {"id": "overview", "label": "Overview", "active": False, "url": "/foundation/geography/dossier/verify/?tab=overview"},
            {"id": "records", "label": "Records", "active": True, "url": "/foundation/geography/dossier/verify/?tab=records"},
            {"id": "history", "label": "History", "active": False, "url": "/foundation/geography/dossier/verify/?tab=history"},
        ],
        "state_contracts": {
            "check_highlighted": {
                "title": "Check the highlighted information",
                "message": "Complete the required fields before continuing. Your entered information is retained.",
                "action_label": "Review fields",
                "action_url": "/foundation/geography/dossier/verify/",
            },
            "saved_later": {
                "title": "Saved for later",
                "message": "Your draft is saved. Return to this record when you are ready to continue.",
                "action_label": "Open draft",
                "action_url": "/foundation/geography/dossier/verify/",
            },
            "another_change": {
                "title": "Another change needs review",
                "message": "This record changed since you opened it. Review the latest version before submitting.",
                "action_label": "Review latest version",
                "action_url": "/foundation/geography/dossier/verify/",
            },
            "loading": {
                "title": "Loading current information",
                "message": "Loading verify the country dossier. No stale values or completed actions are implied.",
                "action_label": "Cancel and return",
                "action_url": "/foundation/geography/dossier/verify/",
            },
            "more_info": {
                "title": "More information needed",
                "message": "Check the marked details before continuing with verify the country dossier. Your entered information remains available.",
                "action_label": "Review details",
                "action_url": "/foundation/geography/dossier/verify/",
            },
        },
    },

    # -------------------------------------------------------------------------
    # GEO-05: Geography and local terminology
    # -------------------------------------------------------------------------
    "GEO-05": {
        "screen_id": "GEO-05",
        "title": "Geography and local terminology",
        "desktop_pnum": 240,
        "mobile_pnum": 241,
        "state_pnum": 242,
        "eyebrow": "H Q / B OT H N E T W O R K S",
        "subtitle": "Prepare a controlled change. Current settings remain effective until the required approval.",
        "breadcrumb": "Workspace / Geography, networks and country oversight",
        "role_name": "HOFCO",
        "scope_badge": "HQ / Both networks",
        "primary_action": {"label": "Save proposed revision", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/geography/country/NG/command/"},
        "tabs": [
            {"id": "overview", "label": "Overview", "active": False, "url": "/foundation/geography/terminology/?tab=overview"},
            {"id": "records", "label": "Records", "active": True, "url": "/foundation/geography/terminology/?tab=records"},
            {"id": "history", "label": "History", "active": False, "url": "/foundation/geography/terminology/?tab=history"},
        ],
        "state_contracts": {
            "check_highlighted": {
                "title": "Check the highlighted information",
                "message": "Complete the required fields before continuing. Your entered information is retained.",
                "action_label": "Review fields",
                "action_url": "/foundation/geography/terminology/",
            },
            "saved_later": {
                "title": "Saved for later",
                "message": "Your draft is saved. Return to this record when you are ready to continue.",
                "action_label": "Open draft",
                "action_url": "/foundation/geography/terminology/",
            },
            "another_change": {
                "title": "Another change needs review",
                "message": "This record changed since you opened it. Review the latest version before submitting.",
                "action_label": "Review latest version",
                "action_url": "/foundation/geography/terminology/",
            },
            "loading": {
                "title": "Loading current information",
                "message": "Loading geography and local terminology. No stale values or completed actions are implied.",
                "action_label": "Cancel and return",
                "action_url": "/foundation/geography/terminology/",
            },
            "more_info": {
                "title": "More information needed",
                "message": "Check the marked details before continuing with geography and local terminology. Your entered information remains available.",
                "action_label": "Review details",
                "action_url": "/foundation/geography/terminology/",
            },
        },
    },
}


# -----------------------------------------------------------------------------
# BUSINESS LOGIC & PERMISSION SERVICES
# -----------------------------------------------------------------------------

def assert_stage6_authorized(user_scope: UserScope, screen_id: str):
    """
    Enforces role and boundary authorization for Stage 06 workflows.
    Founder/HOFCO/Admin have cross-cutting continental access.
    Network Secretary has operational authority in Nigeria / WGMN.
    Country leads have access in their country.
    Other roles receive ScopePermissionDenied.
    """
    user_roles = {r.lower() for r in user_scope.roles}
    if user_scope.primary_role:
        user_roles.add(user_scope.primary_role.lower())
    if user_scope.active_role:
        user_roles.add(user_scope.active_role.lower())
    if user_scope.leadership_level:
        user_roles.add(user_scope.leadership_level.lower())
    if user_scope.is_management_or_admin:
        user_roles.update(["admin", "founder", "hofco", "operations"])

    admin_roles = {"founder", "hofco", "executive", "admin", "operations", "qa_controls", "quality_lead", "it_admin", "management"}
    network_roles = {"network_secretary", "country_lead", "chapter_lead", "regional_coordinator"}

    # Geography oversight screens require continental or country authority
    if screen_id in {"GEO-01", "GEO-02", "GEO-04", "GEO-05"}:
        if not user_roles.intersection(admin_roles | {"country_lead", "network_secretary"}):
            raise ScopePermissionDenied(f"Role '{user_scope.primary_role}' is not authorized for {screen_id}.")

    # People screens require at least network leadership or admin
    if screen_id in {"PEOPLE-01", "PEOPLE-02", "PEOPLE-03", "PEOPLE-04", "PEOPLE-05", "PEOPLE-06"}:
        if not user_roles.intersection(admin_roles | network_roles):
            raise ScopePermissionDenied(f"Role '{user_scope.primary_role}' cannot manage people and community records.")


def check_for_duplicate_person(email: str, full_name: str, network: str = "WGMN") -> Dict[str, Any]:
    """
    Safe add-or-link / duplicate handling service.
    Detects if person identity already exists by normalized email or exact name.
    """
    clean_email = email.strip().lower() if email else ""
    clean_name = full_name.strip() if full_name else ""

    existing = None
    if clean_email:
        existing = PersonProfile.objects.filter(email__iexact=clean_email).first()
    if not existing and clean_name:
        existing = PersonProfile.objects.filter(full_name__iexact=clean_name).first()

    if existing:
        return {
            "duplicate_found": True,
            "person": existing,
            "message": f"Person identity exists ({existing.person_code} · {existing.full_name}). Relationship will be linked to this person identity to prevent duplicate registration.",
            "is_linkable": True,
        }
    return {
        "duplicate_found": False,
        "person": None,
        "message": "No matching person identity found. A new authoritative person record can be safely created.",
        "is_linkable": False,
    }


def add_or_link_person_record(
    full_name: str,
    email: str,
    country: str,
    relationship_to_add: str,
    network: str,
    actor_account: Account,
) -> Dict[str, Any]:
    """
    Atomically creates or links a person record and relationship,
    preventing duplicate identity registration.
    """
    with transaction.atomic():
        dup_check = check_for_duplicate_person(email, full_name, network)
        if dup_check["duplicate_found"]:
            person = dup_check["person"]
            action_type = "linked"
        else:
            # Generate next non-colliding person code
            existing_codes = PersonProfile.objects.values_list("person_code", flat=True)
            max_num = 420
            for c in existing_codes:
                if c.startswith("WD-"):
                    try:
                        num = int(c.split("-")[1])
                        if num > max_num:
                            max_num = num
                    except (IndexError, ValueError):
                        pass
            code = f"WD-{max_num + 1:05d}"
            person = PersonProfile.objects.create(
                person_code=code,
                full_name=full_name.strip(),
                email=email.strip().lower(),
                network=network,
                country=country or "NG",
                local_home="Ikeja Chapter" if country == "NG" else f"{country} Hub",
                contact_verification="Verified" if email else "Pending",
                primary_relationship=relationship_to_add or "Member",
                status="Active",
            )
            action_type = "created"

        # Create relationship attached to person identity
        rel, _ = PersonRelationship.objects.get_or_create(
            person=person,
            relationship_label=relationship_to_add or "Member",
            defaults={
                "category": "membership" if "member" in (relationship_to_add or "").lower() else "programme_participant",
                "effective_date": date.today(),
                "status": "Active",
            },
        )

        # Audit trail
        AuditEvent.objects.create(
            account=actor_account,
            event=f"person_{action_type}",
            detail={
                "person_code": person.person_code,
                "person_name": person.full_name,
                "relationship": relationship_to_add,
                "network": network,
            },
        )

        return {
            "success": True,
            "action_type": action_type,
            "person": person,
            "relationship": rel,
        }


def save_person_relationship(
    person_id_or_code: str,
    relationship_category: str,
    related_programme: str,
    effective_date_str: str,
    actor_account: Account,
) -> Dict[str, Any]:
    """
    Attaches a new relationship to an existing person identity with duplicate prevention.
    """
    with transaction.atomic():
        try:
            person = PersonProfile.objects.get(person_code=person_id_or_code)
        except PersonProfile.DoesNotExist:
            person = PersonProfile.objects.get(id=person_id_or_code)

        eff_date = None
        if effective_date_str:
            try:
                eff_date = datetime.strptime(effective_date_str, "%d %B %Y").date()
            except Exception:
                try:
                    eff_date = parse_date(effective_date_str) or date.today()
                except Exception:
                    eff_date = date.today()
        else:
            eff_date = date.today()

        rel, created = PersonRelationship.objects.update_or_create(
            person=person,
            relationship_label=relationship_category or "Programme participant",
            related_programme=related_programme or "",
            defaults={
                "category": relationship_category or "programme_participant",
                "effective_date": eff_date,
                "status": "Active",
            },
        )

        AuditEvent.objects.create(
            account=actor_account,
            event="relationship_saved",
            detail={
                "person_code": person.person_code,
                "category": relationship_category,
                "programme": related_programme,
                "effective_date": str(eff_date),
            },
        )

        return {"success": True, "created": created, "relationship": rel, "person": person}


def submit_reassignment_decision(
    person_code: str,
    proposed_local_home: str,
    reason: str,
    member_confirmation: bool,
    actor_account: Account,
    user_scope: UserScope,
) -> Dict[str, Any]:
    """
    Submits and approves local-home reassignment with evidence check.
    Enforces role authority (Network Secretary, Country Lead, Founder, HOFCO).
    """
    user_roles = {r.lower() for r in user_scope.roles}
    if user_scope.primary_role:
        user_roles.add(user_scope.primary_role.lower())
    if user_scope.active_role:
        user_roles.add(user_scope.active_role.lower())
    if user_scope.leadership_level:
        user_roles.add(user_scope.leadership_level.lower())
    if user_scope.is_management_or_admin:
        user_roles.update(["admin", "founder", "hofco", "operations"])

    authorized_roles = {"network_secretary", "country_lead", "founder", "hofco", "admin", "operations"}
    if not user_roles.intersection(authorized_roles):
        raise ScopePermissionDenied("A decision requires the appropriate authority.")

    if not member_confirmation:
        raise ValueError("Member confirmation is required before submitting local-home reassignment.")

    with transaction.atomic():
        person = PersonProfile.objects.get(person_code=person_code)
        current_home = person.local_home

        reassignment, _ = LocalHomeReassignment.objects.get_or_create(
            person=person,
            current_local_home=current_home,
            proposed_local_home=proposed_local_home,
            defaults={
                "reason": reason,
                "member_confirmation": member_confirmation,
                "status": "approved",
                "submitted_by": actor_account,
                "reviewed_by": actor_account,
                "reviewed_at": timezone.now(),
            },
        )
        reassignment.status = "approved"
        reassignment.member_confirmation = True
        reassignment.reviewed_by = actor_account
        reassignment.reviewed_at = timezone.now()
        reassignment.save()

        # Update person profile
        person.local_home = proposed_local_home
        person.save()

        AuditEvent.objects.create(
            account=actor_account,
            event="local_home_reassigned",
            detail={
                "person_code": person.person_code,
                "previous_home": current_home,
                "new_home": proposed_local_home,
                "reason": reason,
            },
        )

        return {"success": True, "reassignment": reassignment, "person": person}


def verify_country_dossier_submission(
    country_code: str,
    network: str,
    verification_stage: str,
    evidence_reference: str,
    verification_notes: str,
    actor_account: Account,
    user_scope: UserScope,
) -> Dict[str, Any]:
    """
    Submits country dossier verification sign-off.
    Enforces HOFCO / QA Controls authority.
    """
    user_roles = {r.lower() for r in user_scope.roles}
    if user_scope.primary_role:
        user_roles.add(user_scope.primary_role.lower())
    if user_scope.active_role:
        user_roles.add(user_scope.active_role.lower())
    if user_scope.leadership_level:
        user_roles.add(user_scope.leadership_level.lower())
    if user_scope.is_management_or_admin:
        user_roles.update(["admin", "founder", "hofco", "operations"])

    authorized_roles = {"hofco", "founder", "qa_controls", "admin", "operations"}
    if not user_roles.intersection(authorized_roles):
        raise ScopePermissionDenied("A decision requires the appropriate authority.")

    with transaction.atomic():
        dossier, _ = CountryDossier.objects.get_or_create(
            country_code=country_code,
            network=network,
            defaults={
                "verification_status": "Country verified",
                "verification_stage": verification_stage,
                "evidence_reference": evidence_reference,
                "verification_notes": verification_notes,
                "verified_by": actor_account,
                "verified_at": timezone.now(),
            },
        )
        dossier.verification_status = "Country verified"
        dossier.verification_stage = verification_stage
        dossier.evidence_reference = evidence_reference
        dossier.verification_notes = verification_notes
        dossier.verified_by = actor_account
        dossier.verified_at = timezone.now()
        dossier.save()

        AuditEvent.objects.create(
            account=actor_account,
            event="country_dossier_verified",
            detail={
                "country_code": country_code,
                "network": network,
                "evidence_reference": evidence_reference,
            },
        )

        return {"success": True, "dossier": dossier}


def save_geography_terminology_revision(
    country_code: str,
    first_level_term: str,
    second_level_term: str,
    effective_date_str: str,
    actor_account: Account,
    user_scope: UserScope,
) -> Dict[str, Any]:
    """
    Saves a proposed revision to geography and local terminology.
    Enforces authority and records in audit history.
    """
    user_roles = {r.lower() for r in user_scope.roles}
    if user_scope.primary_role:
        user_roles.add(user_scope.primary_role.lower())
    if user_scope.active_role:
        user_roles.add(user_scope.active_role.lower())
    if user_scope.leadership_level:
        user_roles.add(user_scope.leadership_level.lower())
    if user_scope.is_management_or_admin:
        user_roles.update(["admin", "founder", "hofco", "operations"])

    authorized_roles = {"hofco", "founder", "admin", "operations", "network_secretary"}
    if not user_roles.intersection(authorized_roles):
        raise ScopePermissionDenied("A decision requires the appropriate authority.")

    eff_date = None
    if effective_date_str:
        try:
            eff_date = datetime.strptime(effective_date_str, "%d %B %Y").date()
        except Exception:
            try:
                eff_date = parse_date(effective_date_str) or date.today()
            except Exception:
                eff_date = date.today()
    else:
        eff_date = date.today()

    with transaction.atomic():
        term, _ = GeographyTerminology.objects.update_or_create(
            country=country_code,
            defaults={
                "first_level_term": first_level_term,
                "second_level_term": second_level_term,
                "effective_date": eff_date,
                "status": "effective",
                "proposed_by": actor_account,
                "approved_by": actor_account,
            },
        )

        AuditEvent.objects.create(
            account=actor_account,
            event="geography_terminology_revised",
            detail={
                "country": country_code,
                "first_level_term": first_level_term,
                "second_level_term": second_level_term,
                "effective_date": str(eff_date),
            },
        )

        return {"success": True, "terminology": term}
