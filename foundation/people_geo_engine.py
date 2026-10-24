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

from datetime import date, datetime
from typing import Any, Dict, List, Optional
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date

from accounts.models import Account, AuditEvent
from .models import (
    Chapter,
    CountryDossier,
    GeographyTerminology,
    LocalHomeReassignment,
    LocalOrganisationUnit,
    PersonProfile,
    PersonRelationship,
)
from .scope import ScopePermissionDenied, UserScope


def seed_stage6_fixtures(force: bool = False) -> None:
    return


# -----------------------------------------------------------------------------
# SCREEN DEFINITIONS REGISTRY
# -----------------------------------------------------------------------------

def _std_tabs(base_url: str, active_id: str = "records") -> List[Dict[str, Any]]:
    return [
        {"id": "overview", "label": "Overview", "active": active_id == "overview", "url": f"{base_url}?tab=overview"},
        {"id": "records", "label": "Records", "active": active_id == "records", "url": f"{base_url}?tab=records"},
        {"id": "history", "label": "History", "active": active_id == "history", "url": f"{base_url}?tab=history"},
    ]


def _list_contracts(url: str, title_lower: str, domain_msg: str, use_more_info: bool = False) -> Dict[str, Dict[str, str]]:
    contracts = {
        "empty": {
            "title": "No records in this view",
            "message": f"There are no {domain_msg} records matching the selected scope.",
            "action_label": "Clear filters",
            "action_url": url,
        },
        "connection_error": {
            "title": "Connection interrupted",
            "message": "Your last saved information is safe. Reconnect before submitting changes.",
            "action_label": "Try again",
            "action_url": url,
        },
        "access_changed": {
            "title": "Access has changed",
            "message": "This action is no longer available for your current role. No change was applied.",
            "action_label": "Return to workspace",
            "action_url": "/foundation/workspace/",
        },
        "loading": {
            "title": "Loading current information",
            "message": f"Loading {title_lower}. No stale values or completed actions are implied.",
            "action_label": "Cancel and return",
            "action_url": url,
        },
    }
    if use_more_info:
        contracts["more_info"] = {
            "title": "More information needed",
            "message": f"Check the marked details before continuing with {title_lower}. Your entered information remains available.",
            "action_label": "Review details",
            "action_url": url,
        }
    else:
        contracts["no_matching"] = {
            "title": "Nothing to show in this scope",
            "message": f"There are no matching records for {title_lower}. Check the current scope or remove a filter.",
            "action_label": "Reset view",
            "action_url": url,
        }
    return contracts


def _form_contracts(url: str, title_lower: str) -> Dict[str, Dict[str, str]]:
    return {
        "check_highlighted": {
            "title": "Check the highlighted information",
            "message": "Complete the required fields before continuing. Your entered information is retained.",
            "action_label": "Review fields",
            "action_url": url,
        },
        "saved_later": {
            "title": "Saved for later",
            "message": "Your draft is saved. Return to this record when you are ready to continue.",
            "action_label": "Open draft",
            "action_url": url,
        },
        "another_change": {
            "title": "Another change needs review",
            "message": "This record changed since you opened it. Review the latest version before submitting.",
            "action_label": "Review latest version",
            "action_url": url,
        },
        "loading": {
            "title": "Loading current information",
            "message": f"Loading {title_lower}. No stale values or completed actions are implied.",
            "action_label": "Cancel and return",
            "action_url": url,
        },
        "more_info": {
            "title": "More information needed",
            "message": f"Check the marked details before continuing with {title_lower}. Your entered information remains available.",
            "action_label": "Review details",
            "action_url": url,
        },
    }


PEOPLE_BC = "Workspace / People, membership and Community management"
GEO_BC = "Workspace / Geography, networks and country oversight"

STAGE6_SCREENS: Dict[str, Dict[str, Any]] = {
    "PEOPLE-01": {
        "screen_id": "PEOPLE-01",
        "title": "People directory",
        "desktop_pnum": 210, "mobile_pnum": 211, "state_pnum": 212,
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant people and relationships records, linked evidence and next actions for your scope.",
        "breadcrumb": PEOPLE_BC,
        "role_name": "Network Secretary",
        "scope_badge": "WGMN / Nigeria",
        "primary_action": {"label": "Add or link person", "url": "/foundation/people/add-or-link/"},
        "secondary_action": {"label": "Back", "url": "/foundation/dashboards/dash-03/"},
        "tabs": _std_tabs("/foundation/people/", "records"),
        "state_contracts": _list_contracts("/foundation/people/", "people directory", "people and relationships"),
    },
    "PEOPLE-02": {
        "screen_id": "PEOPLE-02",
        "title": "Person Profile",
        "desktop_pnum": 213, "mobile_pnum": 214, "state_pnum": 215,
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant people and relationships records, linked evidence and next actions for your scope.",
        "breadcrumb": PEOPLE_BC,
        "role_name": "Network Secretary",
        "scope_badge": "WGMN / Nigeria",
        "primary_action": {"label": "Review profile", "url": "/foundation/community/reassignment/review/"},
        "secondary_action": {"label": "Back", "url": "/foundation/people/"},
        "tabs": _std_tabs("/foundation/people/", "overview"),
        "state_contracts": _list_contracts("/foundation/people/", "person profile", "people and relationships", use_more_info=True),
    },
    "PEOPLE-03": {
        "screen_id": "PEOPLE-03",
        "title": "Add or link a person",
        "desktop_pnum": 216, "mobile_pnum": 217, "state_pnum": 218,
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Complete the information below, then review it before you continue.",
        "breadcrumb": PEOPLE_BC,
        "role_name": "Network Secretary",
        "scope_badge": "WGMN / Nigeria",
        "primary_action": {"label": "Check for existing person", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/people/"},
        "tabs": _std_tabs("/foundation/people/add-or-link/", "records"),
        "state_contracts": _form_contracts("/foundation/people/add-or-link/", "add or link a person"),
    },
    "PEOPLE-04": {
        "screen_id": "PEOPLE-04",
        "title": "Community relationships",
        "desktop_pnum": 219, "mobile_pnum": 220, "state_pnum": 221,
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "See the relevant people and relationships records, linked evidence and next actions for your scope.",
        "breadcrumb": PEOPLE_BC,
        "role_name": "Network Secretary",
        "scope_badge": "WGMN / Nigeria",
        "primary_action": {"label": "Open category", "url": "/foundation/community/relationships/manage/"},
        "secondary_action": {"label": "Back", "url": "/foundation/people/"},
        "tabs": _std_tabs("/foundation/community/relationships/", "records"),
        "state_contracts": _list_contracts("/foundation/community/relationships/", "community relationships", "people and relationships"),
    },
    "PEOPLE-05": {
        "screen_id": "PEOPLE-05",
        "title": "Manage relationships",
        "desktop_pnum": 222, "mobile_pnum": 223, "state_pnum": 224,
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Complete the information below, then review it before you continue.",
        "breadcrumb": PEOPLE_BC,
        "role_name": "Network Secretary",
        "scope_badge": "WGMN / Nigeria",
        "primary_action": {"label": "Save relationships", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/community/relationships/"},
        "tabs": _std_tabs("/foundation/community/relationships/manage/", "records"),
        "state_contracts": _form_contracts("/foundation/community/relationships/manage/", "manage relationships"),
    },
    "PEOPLE-06": {
        "screen_id": "PEOPLE-06",
        "title": "Review local-home reassignment",
        "desktop_pnum": 225, "mobile_pnum": 226, "state_pnum": 227,
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Check the evidence and the impact of this decision before confirming.",
        "breadcrumb": PEOPLE_BC,
        "role_name": "Network Secretary",
        "scope_badge": "WGMN / Nigeria",
        "primary_action": {"label": "Submit reassignment", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/people/"},
        "tabs": _std_tabs("/foundation/community/reassignment/review/", "records"),
        "state_contracts": _form_contracts("/foundation/community/reassignment/review/", "review local-home reassignment"),
    },
    "GEO-01": {
        "screen_id": "GEO-01",
        "title": "Africa and network coverage",
        "desktop_pnum": 228, "mobile_pnum": 229, "state_pnum": 230,
        "eyebrow": "H Q / B OT H N E T W O R K S",
        "subtitle": "See the relevant country and local coverage records, linked evidence and next actions for your scope.",
        "breadcrumb": GEO_BC,
        "role_name": "HOFCO",
        "scope_badge": "HQ / Both networks",
        "primary_action": {"label": "Open country dossier", "url": "/foundation/geography/country/NG/command/"},
        "secondary_action": {"label": "Back", "url": "/foundation/dashboards/dash-01/"},
        "tabs": [
            {"id": "map", "label": "Map & countries", "active": True, "url": "/foundation/geography/coverage/?tab=map"},
            {"id": "country_table", "label": "Country table", "active": False, "url": "/foundation/geography/coverage/?tab=country_table"},
            {"id": "verification", "label": "Verification", "active": False, "url": "/foundation/geography/dossier/verify/"},
        ],
        "state_contracts": _list_contracts("/foundation/geography/coverage/", "africa and network coverage", "country and local coverage"),
    },
    "GEO-02": {
        "screen_id": "GEO-02",
        "title": "Nigeria · Country Command Profile",
        "desktop_pnum": 231, "mobile_pnum": 232, "state_pnum": 233,
        "eyebrow": "H Q / B OT H N E T W O R K S",
        "subtitle": "See the relevant country and local coverage records, linked evidence and next actions for your scope.",
        "breadcrumb": GEO_BC,
        "role_name": "HOFCO",
        "scope_badge": "HQ / Both networks",
        "primary_action": {"label": "Request verification", "url": "/foundation/geography/dossier/verify/"},
        "secondary_action": {"label": "Back", "url": "/foundation/geography/coverage/"},
        "tabs": _std_tabs("/foundation/geography/country/NG/command/", "overview"),
        "state_contracts": _list_contracts("/foundation/geography/country/NG/command/", "country command profile", "country and local coverage", use_more_info=True),
    },
    "GEO-03": {
        "screen_id": "GEO-03",
        "title": "Local organisation",
        "desktop_pnum": 234, "mobile_pnum": 235, "state_pnum": 236,
        "eyebrow": "W G M N / N I G E R I A",
        "subtitle": "Follow local units, responsible leaders and evidence within the selected country.",
        "breadcrumb": GEO_BC,
        "role_name": "HOFCO",
        "scope_badge": "WGMN / Nigeria",
        "primary_action": {"label": "Open unit", "url": "/foundation/geography/local-org/"},
        "secondary_action": {"label": "Back", "url": "/foundation/geography/country/NG/command/"},
        "tabs": [
            {"id": "structure", "label": "Structure", "active": True, "url": "/foundation/geography/local-org/?tab=structure"},
            {"id": "unit_directory", "label": "Unit directory", "active": False, "url": "/foundation/geography/local-org/?tab=unit_directory"},
            {"id": "evidence", "label": "Evidence", "active": False, "url": "/foundation/geography/local-org/?tab=evidence"},
        ],
        "state_contracts": _list_contracts("/foundation/geography/local-org/", "local organisation", "country and local coverage"),
    },
    "GEO-04": {
        "screen_id": "GEO-04",
        "title": "Verify the country dossier",
        "desktop_pnum": 237, "mobile_pnum": 238, "state_pnum": 239,
        "eyebrow": "H Q / B OT H N E T W O R K S",
        "subtitle": "Check the evidence and the impact of this decision before confirming.",
        "breadcrumb": GEO_BC,
        "role_name": "HOFCO",
        "scope_badge": "HQ / Both networks",
        "primary_action": {"label": "Submit verification", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/geography/country/NG/command/"},
        "tabs": _std_tabs("/foundation/geography/dossier/verify/", "records"),
        "state_contracts": _form_contracts("/foundation/geography/dossier/verify/", "verify the country dossier"),
    },
    "GEO-05": {
        "screen_id": "GEO-05",
        "title": "Geography and local terminology",
        "desktop_pnum": 240, "mobile_pnum": 241, "state_pnum": 242,
        "eyebrow": "H Q / B OT H N E T W O R K S",
        "subtitle": "Prepare a controlled change. Current settings remain effective until the required approval.",
        "breadcrumb": GEO_BC,
        "role_name": "HOFCO",
        "scope_badge": "HQ / Both networks",
        "primary_action": {"label": "Save proposed revision", "type": "submit"},
        "secondary_action": {"label": "Back", "url": "/foundation/geography/country/NG/command/"},
        "tabs": _std_tabs("/foundation/geography/terminology/", "records"),
        "state_contracts": _form_contracts("/foundation/geography/terminology/", "geography and local terminology"),
    },
}


# -----------------------------------------------------------------------------
# BUSINESS LOGIC & PERMISSION SERVICES
# -----------------------------------------------------------------------------

COUNTRY_CODE_MAP = {
    "NG": "Nigeria",
    "NIGERIA": "NG",
    "KE": "Kenya",
    "KENYA": "KE",
    "GH": "Ghana",
    "GHANA": "GH",
    "AO": "Angola",
    "ANGOLA": "AO",
    "ET": "Ethiopia",
    "ETHIOPIA": "ET",
    "ZA": "South Africa",
    "SOUTH AFRICA": "ZA",
    "RW": "Rwanda",
    "RWANDA": "RW",
}

COUNTRY_DEFAULT_HOME = {
    "NG": "Ikeja Chapter",
    "KE": "Nairobi Central Chapter",
    "GH": "Accra Central Chapter",
    "AO": "Luanda Central Chapter",
    "ET": "Addis Ababa Bole Chapter",
    "ZA": "Johannesburg Chapter",
    "RW": "Kigali Central Chapter",
}


def normalize_country_code(country_input: str, default_code: str = "NG") -> str:
    if not country_input:
        return default_code
    cleaned = country_input.strip().upper()
    if cleaned in {"NG", "KE", "GH", "AO", "ET", "ZA", "RW"}:
        return cleaned
    return COUNTRY_CODE_MAP.get(cleaned, default_code)


def get_country_name_for_code(code: str) -> str:
    return COUNTRY_CODE_MAP.get((code or "NG").strip().upper(), code or "Nigeria")


def _collect_user_roles(user_scope: UserScope) -> set:
    user_roles = {r.lower() for r in user_scope.roles}
    if user_scope.primary_role:
        user_roles.add(user_scope.primary_role.lower())
    if user_scope.active_role:
        user_roles.add(user_scope.active_role.lower())
    if user_scope.leadership_level:
        user_roles.add(user_scope.leadership_level.lower())
    if user_scope.is_management_or_admin:
        user_roles.update(["admin", "founder", "hofco", "operations"])
    return user_roles


def is_global_stage6_scope(user_scope: UserScope) -> bool:
    user_roles = _collect_user_roles(user_scope)
    global_roles = {
        "founder", "hofco", "executive", "global_executive", "admin",
        "operations", "coordinator", "programmes", "comms", "resources",
        "systems", "quality", "qa_controls", "quality_lead", "it_admin",
        "management", "safeguarding",
    }
    if user_roles.intersection(global_roles):
        return True
    if "*" in user_scope.allowed_countries or "ALL" in user_scope.allowed_countries:
        return True
    return False


def assert_country_network_authorized(
    user_scope: UserScope,
    country: Optional[str] = None,
    network: Optional[str] = None,
):
    """
    Fail-closed scope boundary verification for Stage 06 records.
    Ensures a user can only view or mutate records within their permitted
    network and geographic area.
    """
    if network and network not in {"ALL", "BOTH", "*", "HQ / Both networks"}:
        from .scope import normalize_network_code
        norm_net = normalize_network_code(network)
        if not user_scope.can_access_network(norm_net):
            raise ScopePermissionDenied(
                f"Access restricted: Record belongs to network '{network}', outside your permitted network scope ({user_scope.active_network}).",
                reason_code="network_mismatch",
            )

    if country and country not in {"ALL", "BOTH", "*"}:
        if not is_global_stage6_scope(user_scope):
            norm_c = normalize_country_code(country, country.upper())
            if not user_scope.can_access_country(norm_c):
                raise ScopePermissionDenied(
                    f"Access restricted: Record belongs to country '{get_country_name_for_code(norm_c)}', outside your permitted geographic area ({get_country_name_for_code(user_scope.active_country)}).",
                    reason_code="country_mismatch",
                )


def assert_person_scope_authorized(user_scope: UserScope, person: PersonProfile):
    """Verifies that the given PersonProfile is inside the user's permitted network and country."""
    if not person:
        return
    assert_country_network_authorized(user_scope, country=person.country, network=person.network)


def assert_stage6_authorized(user_scope: UserScope, screen_id: str):
    """
    Enforces role and boundary authorization for Stage 06 workflows.
    Founder/HOFCO/Admin/Operations have cross-cutting continental access.
    Network Secretary, Country Leads, Cluster Leads, Chapter Leads, and Local Coordinators
    have operational authority within their permitted network and country.
    Unauthorized roles receive ScopePermissionDenied.
    """
    user_roles = _collect_user_roles(user_scope)

    admin_roles = {
        "founder", "hofco", "executive", "global_executive", "admin",
        "operations", "coordinator", "programmes", "comms", "resources",
        "systems", "quality", "qa_controls", "quality_lead", "it_admin",
        "management", "safeguarding",
    }
    network_roles = {
        "network_secretary", "country_lead", "country_director",
        "chapter_lead", "cluster_lead", "local_operations",
        "regional_coordinator", "reviewer",
    }

    if screen_id in {"GEO-01", "GEO-02", "GEO-04", "GEO-05"}:
        if not user_roles.intersection(admin_roles | {"country_lead", "country_director", "network_secretary", "regional_coordinator"}):
            raise ScopePermissionDenied(f"Role '{user_scope.primary_role}' is not authorized for {screen_id}.")

    if screen_id in {"GEO-03", "PEOPLE-01", "PEOPLE-02", "PEOPLE-03", "PEOPLE-04", "PEOPLE-05", "PEOPLE-06"}:
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
    user_scope: Optional[UserScope] = None,
    local_home: Optional[str] = None,
    phone: Optional[str] = None,
    state_or_region: Optional[str] = None,
    lga_or_district: Optional[str] = None,
    community_cluster: Optional[str] = None,
    chapter_id: Optional[str] = None,
    cluster_unit_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Atomically creates or links a person record and relationship,
    distinguishing public geography from Community Cluster and actual Chapter,
    preventing duplicate identity registration and enforcing scope boundaries.
    """
    norm_country = normalize_country_code(country, default_code="NG")
    norm_network = network if network in {"WGMN", "WNNN"} else "WGMN"

    if user_scope is not None:
        assert_country_network_authorized(user_scope, country=norm_country, network=norm_network)

    with transaction.atomic():
        chap_obj = None
        if chapter_id:
            chap_obj = Chapter.objects.filter(id=chapter_id).first()
        elif local_home:
            chap_obj = Chapter.objects.filter(name__iexact=local_home.strip()).first()

        cluster_obj = None
        if cluster_unit_id:
            cluster_obj = LocalOrganisationUnit.objects.filter(id=cluster_unit_id, level="Community Cluster").first()
        elif chap_obj and chap_obj.cluster_unit:
            cluster_obj = chap_obj.cluster_unit
        elif community_cluster:
            cluster_obj = LocalOrganisationUnit.objects.filter(
                unit_name__icontains=community_cluster.replace(" Cluster", "").strip(),
                level="Community Cluster",
            ).first()

        resolved_cluster = community_cluster or (cluster_obj.unit_name if cluster_obj else (chap_obj.community_cluster if chap_obj else ""))
        resolved_state = state_or_region or (chap_obj.region if chap_obj else "")
        resolved_lga = lga_or_district or (chap_obj.district if chap_obj else "")
        resolved_home = (local_home or "").strip() or (chap_obj.name if chap_obj else "") or COUNTRY_DEFAULT_HOME.get(norm_country, f"{norm_country} Hub")

        dup_check = check_for_duplicate_person(email, full_name, norm_network)
        if dup_check["duplicate_found"]:
            person = dup_check["person"]
            if user_scope is not None:
                assert_person_scope_authorized(user_scope, person)
            updated = False
            if resolved_state and not person.state_or_region:
                person.state_or_region = resolved_state
                updated = True
            if resolved_lga and not person.lga_or_district:
                person.lga_or_district = resolved_lga
                updated = True
            if resolved_cluster and not person.community_cluster:
                person.community_cluster = resolved_cluster
                updated = True
            if cluster_obj and not person.cluster_unit:
                person.cluster_unit = cluster_obj
                updated = True
            if chap_obj and not person.chapter:
                person.chapter = chap_obj
                updated = True
            if updated:
                person.save()
            action_type = "linked"
        else:
            existing_codes = PersonProfile.objects.values_list("person_code", flat=True)
            max_num = 431
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
                phone=(phone or "").strip(),
                network=norm_network,
                country=norm_country,
                state_or_region=resolved_state,
                lga_or_district=resolved_lga,
                community_cluster=resolved_cluster,
                cluster_unit=cluster_obj,
                chapter=chap_obj,
                local_home=resolved_home,
                contact_verification="Verified" if email else "Pending",
                primary_relationship=relationship_to_add or "Member",
                status="Active",
            )
            action_type = "created"

        rel, _ = PersonRelationship.objects.get_or_create(
            person=person,
            relationship_label=relationship_to_add or "Member",
            defaults={
                "category": "membership" if "member" in (relationship_to_add or "").lower() else "programme_participant",
                "effective_date": date.today(),
                "status": "Active",
            },
        )

        AuditEvent.objects.create(
            account=actor_account,
            event=f"person_{action_type}",
            detail={
                "person_code": person.person_code,
                "person_name": person.full_name,
                "relationship": relationship_to_add,
                "network": person.network,
                "country": person.country,
                "community_cluster": person.community_cluster,
                "chapter": person.local_home,
            },
        )

        return {
            "success": True,
            "action_type": action_type,
            "person": person,
            "relationship": rel,
        }


def update_person_profile_record(
    person_code: str,
    full_name: str,
    email: str,
    phone: str,
    local_home: str,
    contact_verification: str,
    primary_relationship: str,
    status: str,
    actor_account: Account,
    user_scope: UserScope,
    expected_updated_at: Optional[str] = None,
    state_or_region: Optional[str] = None,
    lga_or_district: Optional[str] = None,
    community_cluster: Optional[str] = None,
    chapter_name: Optional[str] = None,
    cluster_unit_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Updates a PersonProfile within the user's permitted network and geographic scope.
    Performs optimistic concurrency check if expected_updated_at is provided,
    and writes a durable AuditEvent.
    """
    assert_stage6_authorized(user_scope, "PEOPLE-02")

    with transaction.atomic():
        person = PersonProfile.objects.select_for_update().get(person_code=person_code)
        assert_person_scope_authorized(user_scope, person)

        if expected_updated_at and person.updated_at:
            current_stamp = person.updated_at.strftime("%Y-%m-%dT%H:%M:%S")
            if expected_updated_at.strip() not in {current_stamp, person.updated_at.isoformat()}:
                return {
                    "success": False,
                    "conflict": True,
                    "person": person,
                    "message": "This record changed since you opened it. Review the latest version before submitting.",
                }

        changes = {}
        if full_name and full_name.strip() != person.full_name:
            changes["full_name"] = {"from": person.full_name, "to": full_name.strip()}
            person.full_name = full_name.strip()
        if email is not None and email.strip().lower() != person.email:
            changes["email"] = {"from": person.email, "to": email.strip().lower()}
            person.email = email.strip().lower()
        if phone is not None and phone.strip() != person.phone:
            changes["phone"] = {"from": person.phone, "to": phone.strip()}
            person.phone = phone.strip()
        if local_home and local_home.strip() != person.local_home:
            changes["local_home"] = {"from": person.local_home, "to": local_home.strip()}
            person.local_home = local_home.strip()
        if contact_verification and contact_verification.strip() != person.contact_verification:
            changes["contact_verification"] = {"from": person.contact_verification, "to": contact_verification.strip()}
            person.contact_verification = contact_verification.strip()
        if primary_relationship and primary_relationship.strip() != person.primary_relationship:
            changes["primary_relationship"] = {"from": person.primary_relationship, "to": primary_relationship.strip()}
            person.primary_relationship = primary_relationship.strip()
        if status and status.strip() != person.status:
            changes["status"] = {"from": person.status, "to": status.strip()}
            person.status = status.strip()

        if state_or_region is not None and state_or_region.strip() != person.state_or_region:
            changes["state_or_region"] = {"from": person.state_or_region, "to": state_or_region.strip()}
            person.state_or_region = state_or_region.strip()

        if lga_or_district is not None and lga_or_district.strip() != person.lga_or_district:
            changes["lga_or_district"] = {"from": person.lga_or_district, "to": lga_or_district.strip()}
            person.lga_or_district = lga_or_district.strip()

        if community_cluster is not None and community_cluster.strip() != person.community_cluster:
            changes["community_cluster"] = {"from": person.community_cluster, "to": community_cluster.strip()}
            person.community_cluster = community_cluster.strip()

        if cluster_unit_id:
            c_unit = LocalOrganisationUnit.objects.filter(id=cluster_unit_id, level="Community Cluster").first()
            if c_unit and person.cluster_unit != c_unit:
                changes["cluster_unit"] = {"from": str(person.cluster_unit), "to": str(c_unit)}
                person.cluster_unit = c_unit

        target_chapter_name = chapter_name or local_home
        if target_chapter_name:
            chap = Chapter.objects.filter(name__iexact=target_chapter_name.strip()).first()
            if chap and person.chapter != chap:
                changes["chapter"] = {"from": str(person.chapter), "to": str(chap)}
                person.chapter = chap

        person.save()

        AuditEvent.objects.create(
            account=actor_account,
            event="person_profile_updated",
            detail={
                "person_code": person.person_code,
                "person_name": person.full_name,
                "network": person.network,
                "country": person.country,
                "changes": changes,
            },
        )

        return {"success": True, "conflict": False, "person": person, "changes": changes}


def save_person_relationship(
    person_id_or_code: str,
    relationship_category: str,
    related_programme: str,
    effective_date_str: str,
    actor_account: Account,
    user_scope: Optional[UserScope] = None,
) -> Dict[str, Any]:
    """
    Attaches a new relationship to an existing person identity with duplicate prevention
    and scope boundary verification.
    """
    with transaction.atomic():
        try:
            person = PersonProfile.objects.get(person_code=person_id_or_code)
        except PersonProfile.DoesNotExist:
            person = PersonProfile.objects.get(id=person_id_or_code)

        if user_scope is not None:
            assert_person_scope_authorized(user_scope, person)

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

        cat_slug = "programme_participant"
        low_cat = (relationship_category or "").lower()
        if "member" in low_cat and "mentor" not in low_cat:
            cat_slug = "membership"
        elif "mentor" in low_cat:
            cat_slug = "mentor"
        elif "lead" in low_cat:
            cat_slug = "leadership"
        elif "community" in low_cat:
            cat_slug = "community_supporter"

        rel, created = PersonRelationship.objects.update_or_create(
            person=person,
            relationship_label=relationship_category or "Programme participant",
            related_programme=related_programme or "",
            defaults={
                "category": cat_slug,
                "effective_date": eff_date,
                "status": "Active",
            },
        )

        AuditEvent.objects.create(
            account=actor_account,
            event="relationship_saved",
            detail={
                "person_code": person.person_code,
                "person_name": person.full_name,
                "category": relationship_category,
                "programme": related_programme,
                "effective_date": str(eff_date),
                "network": person.network,
                "country": person.country,
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
    proposed_cluster: Optional[str] = None,
    proposed_state: Optional[str] = None,
    proposed_lga: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Submits and approves local-home reassignment with evidence check.
    Enforces role authority and network/country scope boundaries,
    updating both the actual chapter and the community cluster.
    """
    user_roles = _collect_user_roles(user_scope)

    authorized_roles = {
        "network_secretary", "country_lead", "country_director",
        "chapter_lead", "cluster_lead", "local_operations", "regional_coordinator",
        "founder", "hofco", "executive", "global_executive", "admin",
        "operations", "coordinator", "programmes", "quality", "qa_controls",
    }
    if not user_roles.intersection(authorized_roles):
        raise ScopePermissionDenied("A decision requires the appropriate authority.")

    if not member_confirmation:
        raise ValueError("Member confirmation is required before submitting local-home reassignment.")

    with transaction.atomic():
        person = PersonProfile.objects.get(person_code=person_code)
        assert_person_scope_authorized(user_scope, person)
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
        reassignment.reason = reason
        reassignment.status = "approved"
        reassignment.member_confirmation = True
        reassignment.reviewed_by = actor_account
        reassignment.reviewed_at = timezone.now()
        reassignment.save()

        person.local_home = proposed_local_home

        if proposed_cluster:
            person.community_cluster = proposed_cluster.strip()
            c_unit = LocalOrganisationUnit.objects.filter(
                unit_name__icontains=proposed_cluster.replace(" Cluster", "").strip(),
                level="Community Cluster",
            ).first()
            if c_unit:
                person.cluster_unit = c_unit
        if proposed_state:
            person.state_or_region = proposed_state.strip()
        if proposed_lga:
            person.lga_or_district = proposed_lga.strip()

        target_chap = Chapter.objects.filter(name__iexact=proposed_local_home.strip()).first()
        if target_chap:
            person.chapter = target_chap
            if not proposed_cluster and target_chap.community_cluster:
                person.community_cluster = target_chap.community_cluster
            if not person.cluster_unit and target_chap.cluster_unit:
                person.cluster_unit = target_chap.cluster_unit
            if not proposed_state and target_chap.region:
                person.state_or_region = target_chap.region
            if not proposed_lga and target_chap.district:
                person.lga_or_district = target_chap.district

        person.save()

        AuditEvent.objects.create(
            account=actor_account,
            event="local_home_reassigned",
            detail={
                "person_code": person.person_code,
                "person_name": person.full_name,
                "previous_home": current_home,
                "new_home": proposed_local_home,
                "community_cluster": person.community_cluster,
                "reason": reason,
                "network": person.network,
                "country": person.country,
            },
        )

        return {"success": True, "reassignment": reassignment, "person": person}


def save_local_organisation_unit(
    network: str,
    country: str,
    level: str,
    unit_name: str,
    responsible_leader_name: str,
    description: str = "",
    evidence_type: str = "Charter record",
    record_state: str = "Active unit records",
    actor_account: Optional[Account] = None,
    user_scope: Optional[UserScope] = None,
    parent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Creates or updates a LocalOrganisationUnit in the hierarchy within
    the user's permitted network and country scope, supporting explicit parent_id,
    and records an AuditEvent.
    """
    assert_stage6_authorized(user_scope, "GEO-03")
    norm_country = normalize_country_code(country, default_code=user_scope.active_country or "NG")
    norm_network = network if network in {"WGMN", "WNNN"} else (user_scope.active_network if user_scope.active_network in {"WGMN", "WNNN"} else "WGMN")
    assert_country_network_authorized(user_scope, country=norm_country, network=norm_network)

    level_order_map = {
        "Country": 1,
        "Region / State": 2,
        "District / LGA": 3,
        "Community Cluster": 4,
        "Chapter": 5,
    }
    l_order = level_order_map.get(level, 5)

    with transaction.atomic():
        parent_unit = None
        if parent_id:
            try:
                parent_unit = LocalOrganisationUnit.objects.get(id=parent_id)
            except (LocalOrganisationUnit.DoesNotExist, ValueError):
                pass

        if not parent_unit and l_order > 1:
            parent_unit = LocalOrganisationUnit.objects.filter(
                network=norm_network,
                country=norm_country,
                level_order=l_order - 1,
            ).first()

        unit, created = LocalOrganisationUnit.objects.update_or_create(
            network=norm_network,
            country=norm_country,
            level=level,
            unit_name=unit_name.strip(),
            defaults={
                "level_order": l_order,
                "parent": parent_unit,
                "description": (description or "").strip() or f"{level} operational coordination and records.",
                "responsible_leader_name": (responsible_leader_name or "").strip() or "Assigned Coordinator",
                "evidence_type": (evidence_type or "").strip() or "Unit record",
                "record_state": (record_state or "").strip() or "Active unit records",
            },
        )

        if level == "Chapter":
            c_cluster = parent_unit.unit_name if parent_unit and parent_unit.level == "Community Cluster" else ""
            c_dist = ""
            c_reg = ""
            if parent_unit and parent_unit.parent and parent_unit.parent.level == "District / LGA":
                c_dist = parent_unit.parent.unit_name
                if parent_unit.parent.parent and parent_unit.parent.parent.level == "Region / State":
                    c_reg = parent_unit.parent.parent.unit_name

            chap, _ = Chapter.objects.get_or_create(
                network=norm_network,
                country=norm_country,
                name=unit_name.strip(),
                defaults={
                    "code": f"{norm_country}-{unit_name[:3].upper()}-01",
                    "status": "active",
                    "community_cluster": c_cluster,
                    "cluster_unit": parent_unit if parent_unit and parent_unit.level == "Community Cluster" else None,
                    "region": c_reg,
                    "district": c_dist,
                },
            )
            if c_cluster and not chap.community_cluster:
                chap.community_cluster = c_cluster
                chap.cluster_unit = parent_unit if parent_unit and parent_unit.level == "Community Cluster" else None
                chap.save(update_fields=["community_cluster", "cluster_unit"])

        AuditEvent.objects.create(
            account=actor_account,
            event="local_unit_saved",
            detail={
                "unit_name": unit.unit_name,
                "level": unit.level,
                "leader": unit.responsible_leader_name,
                "network": norm_network,
                "country": norm_country,
                "created": created,
            },
        )

        return {"success": True, "created": created, "unit": unit}


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
    Enforces HOFCO / QA Controls / Country / Executive authority.
    """
    user_roles = _collect_user_roles(user_scope)

    authorized_roles = {
        "hofco", "founder", "executive", "global_executive",
        "qa_controls", "quality", "quality_lead", "admin",
        "operations", "coordinator", "country_lead", "country_director",
    }
    if not user_roles.intersection(authorized_roles):
        raise ScopePermissionDenied("A decision requires the appropriate authority.")

    norm_country = normalize_country_code(country_code, default_code="NG")
    assert_country_network_authorized(user_scope, country=norm_country, network=network)

    with transaction.atomic():
        dossier, _ = CountryDossier.objects.get_or_create(
            country_code=norm_country,
            network=network,
            defaults={
                "country_name": get_country_name_for_code(norm_country),
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
                "country_code": norm_country,
                "country_name": dossier.country_name,
                "network": network,
                "verification_stage": verification_stage,
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
    user_roles = _collect_user_roles(user_scope)

    authorized_roles = {
        "hofco", "founder", "executive", "global_executive",
        "admin", "operations", "coordinator", "network_secretary",
        "country_lead", "country_director", "quality", "qa_controls",
    }
    if not user_roles.intersection(authorized_roles):
        raise ScopePermissionDenied("A decision requires the appropriate authority.")

    norm_country = normalize_country_code(country_code, default_code="NG")
    assert_country_network_authorized(user_scope, country=norm_country)

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
            country=norm_country,
            defaults={
                "country_name": get_country_name_for_code(norm_country),
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
                "country": norm_country,
                "country_name": term.country_name,
                "first_level_term": first_level_term,
                "second_level_term": second_level_term,
                "effective_date": str(eff_date),
            },
        )

        return {"success": True, "terminology": term}


def get_stage6_audit_history(
    user_scope: UserScope,
    person_code: Optional[str] = None,
    country_code: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """
    Returns scoped audit history events for Stage 06 People, Community, and Geography actions.
    """
    stage6_events = {
        "person_created",
        "person_linked",
        "person_profile_updated",
        "relationship_saved",
        "local_home_reassigned",
        "local_unit_saved",
        "country_dossier_verified",
        "geography_terminology_revised",
    }
    qs = AuditEvent.objects.filter(event__in=stage6_events).select_related("account").order_by("-created_at")

    records = []
    is_global = is_global_stage6_scope(user_scope)
    active_c = (country_code or user_scope.active_country or "NG").upper()
    active_n = (user_scope.active_network or "WGMN").upper()

    for ev in qs[:100]:
        det = ev.detail or {}
        ev_country = (det.get("country") or det.get("country_code") or "").upper()
        ev_net = (det.get("network") or "").upper()
        ev_pcode = det.get("person_code") or ""

        if person_code and ev_pcode != person_code:
            continue
        if country_code and ev_country and ev_country != active_c:
            continue
        if not is_global:
            if ev_country and ev_country != active_c:
                continue
            if ev_net and active_n not in {"ALL", "HQ / BOTH NETWORKS", "*"} and ev_net != active_n:
                continue

        label_map = {
            "person_created": f"New person created: {det.get('person_name', '')} ({ev_pcode})",
            "person_linked": f"Existing identity linked: {det.get('person_name', '')} ({ev_pcode})",
            "person_profile_updated": f"Profile updated: {det.get('person_name', '')} ({ev_pcode})",
            "relationship_saved": f"Relationship saved: {det.get('category', '')} · {det.get('programme', '')} ({ev_pcode})",
            "local_home_reassigned": f"Local home reassigned: {det.get('previous_home', '')} → {det.get('new_home', '')} ({ev_pcode})",
            "local_unit_saved": f"Local unit updated: {det.get('unit_name', '')} ({det.get('level', '')})",
            "country_dossier_verified": f"Country dossier verified: {det.get('country_name', ev_country)} · {ev_net} ({det.get('evidence_reference', '')})",
            "geography_terminology_revised": f"Terminology revised ({ev_country}): {det.get('first_level_term', '')} / {det.get('second_level_term', '')}",
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
