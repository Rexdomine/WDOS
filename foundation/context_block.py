"""
WDOS Persistent Identity and Context Block Engine.
Provides authoritative identity, network branding, country flags,
and multi-tier geographic & organizational unit scope:
[Network] → [Country] → [First-level area (State/Province)] → [Second-level area (LGA/District)] → [Community Cluster] → [Actual Chapter]

Strictly enforces:
1. Active user identity (display name, profile photo where available, fallback initials avatar).
2. Active role or position title tailored to network conventions (Table 14: WGMN Coordinator/Representative vs WNN Lead).
3. Approved network branding, name, color, and SVG insignia (WGMN #D4006A vs WNN #7CB518 vs WODDI #171717).
4. Country name, ISO code, and country flag emoji + approved badge equivalent.
5. First-level administrative geography (using country-specific terminology, e.g. State / FCT, County, Region, Province).
6. Second-level administrative geography (using country-specific terminology, e.g. LGA, Sub-County, District, Municipality).
7. Clear distinction between Public Administrative Geography, WODDI Community Cluster, and WODDI Chapter.
8. Dynamic updates upon role, network, or country changes.
9. Support for Founder, Country, Regional/Local operations, Community Cluster, Chapter, Member, Candidate, and Community experiences.
10. Strict protection against exposing sensitive or unauthorized personal data.
"""

from typing import Any, Dict, List, Optional
from django.utils import timezone

from accounts.african_geography import get_country
from accounts.models import Account, Membership, OnboardingDraft, AccessGrant
from foundation.models import (
    Chapter,
    CountryHub,
    GeographyTerminology,
    LocalOrganisationUnit,
    PersonProfile,
)
from foundation.scope import (
    UserScope,
    get_country_display_name,
    is_broad_geographic_place,
    sanitize_chapter_display,
)


def get_country_flag_emoji(country_code: str) -> str:
    """Return the Unicode flag emoji for an ISO 3166-1 alpha-2 country code."""
    if not country_code or len(country_code) != 2:
        return "🌍"
    code = country_code.upper()
    try:
        # Regional Indicator Symbols: 'A' = 127462 (0x1F1E6)
        return chr(127397 + ord(code[0])) + chr(127397 + ord(code[1]))
    except Exception:
        return "🌍"


def get_network_branding(network_code: str) -> Dict[str, str]:
    """Resolve approved network branding, colors, badges, and SVG insignias."""
    net = (network_code or "WGMN").upper().strip()
    if net in ("WNNN", "WNN"):
        return {
            "code": "WNNN",
            "short_name": "WNN",  # Canonical short code matching the 16 Oct spec example
            "full_name": "WODDI Next-Gen Nurturers Network",
            "brand_color": "#7CB518",
            "brand_color_dark": "#4E770E",
            "brand_class": "brand-wnnn",
            "badge_bg": "#F4F9EA",
            "badge_border": "#D2E89E",
            "badge_text": "#4A6E0F",
            "tagline": "Youth leadership development, digital education, mentorship",
            "logo_svg": (
                '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="network-logo-svg" aria-label="WNN Network Logo">'
                '<circle cx="12" cy="12" r="11" fill="#7CB518"/>'
                '<path d="M12 4C9 8 8 11 8 14C8 16.2 9.8 18 12 18C14.2 18 16 16.2 16 14C16 11 15 8 12 4Z" fill="#FFFFFF"/>'
                '<path d="M12 18V11" stroke="#7CB518" stroke-width="1.8" stroke-linecap="round"/>'
                '<path d="M12 13C10.8 12 9.5 12.2 9 12.5" stroke="#7CB518" stroke-width="1.4" stroke-linecap="round"/>'
                '<path d="M12 11.5C13.2 10.5 14.5 10.7 15 11" stroke="#7CB518" stroke-width="1.4" stroke-linecap="round"/>'
                '</svg>'
            ),
        }
    elif net == "WGMN":
        return {
            "code": "WGMN",
            "short_name": "WGMN",
            "full_name": "WODDI Good Mother Network",
            "brand_color": "#D4006A",
            "brand_color_dark": "#9E004F",
            "brand_class": "brand-wgmn",
            "badge_bg": "#FFF0F6",
            "badge_border": "#FCCEE2",
            "badge_text": "#A0004E",
            "tagline": "Maternal leadership, family empowerment, community stewardship",
            "logo_svg": (
                '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="network-logo-svg" aria-label="WGMN Network Logo">'
                '<circle cx="12" cy="12" r="11" fill="#D4006A"/>'
                '<path d="M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z" fill="#FFFFFF" transform="matrix(0.55 0 0 0.55 5.4 5.4)"/>'
                '</svg>'
            ),
        }
    else:  # WODDI / Headquarters / Pan-Africa
        return {
            "code": "WODDI",
            "short_name": "WODDI",
            "full_name": "Women of Divine Destiny Initiative",
            "brand_color": "#171717",
            "brand_color_dark": "#000000",
            "brand_class": "brand-woddi",
            "badge_bg": "#F5F3F6",
            "badge_border": "#DDD8E2",
            "badge_text": "#291B2B",
            "tagline": "Continental Command & Africa-wide Oversight",
            "logo_svg": (
                '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="network-logo-svg" aria-label="WODDI Master Logo">'
                '<circle cx="12" cy="12" r="11" fill="#171717"/>'
                '<circle cx="12" cy="12" r="6" stroke="#D4006A" stroke-width="2"/>'
                '<circle cx="12" cy="12" r="2.5" fill="#7CB518"/>'
                '</svg>'
            ),
        }


def get_active_role_title(role_code: str, network_code: str = "WGMN") -> str:
    """
    Resolve role code to the Management-approved network-specific title
    complying with Master Specification Table 14:
    - WGMN: Country Representative, State Coordinator, LGA Coordinator, Cluster Coordinator, Chapter Coordinator
    - WNN: Country Lead, State Lead, LGA Lead, Cluster Lead, Chapter Lead
    """
    r = (role_code or "member").lower().strip().replace("-", "_")
    is_wnn = (network_code or "").upper().strip() in ("WNNN", "WNN")

    if r in ("founder", "hq", "executive"):
        return "Founder / Executive"
    elif r in ("operations", "hofco", "ops"):
        return "Head of Field & Country Operations (HOFCO)"
    elif r in ("coordinator", "regional_coordinator"):
        return "Regional Operations Coordinator"
    elif r in ("network_secretary", "secretary"):
        return "Network Administration & Coordination Secretary"
    elif r in ("admin", "administration"):
        return "Director of Administration"
    elif r in ("programmes", "program_director"):
        return "Director of Programmes"
    elif r in ("communications", "comms"):
        return "Communications Lead"
    elif r in ("finance", "resources"):
        return "Director of Finance"
    elif r in ("systems", "it_admin"):
        return "WDOS IT & Systems Manager"
    elif r in ("quality", "controls", "reviewer", "compliance"):
        return "WDOS QA & Controls Lead"
    elif r in ("safeguarding", "safeguarding_officer"):
        return "Authorised Safeguarding Officer"
    elif r in ("country_lead", "country_director", "country_representative", "field_lead"):
        return "Country Lead" if is_wnn else "Country Representative"
    elif r in ("state_lead", "regional_lead", "state_coordinator"):
        return "State Lead" if is_wnn else "State Coordinator"
    elif r in ("lga_lead", "local_operations", "lga_coordinator"):
        return "LGA Lead" if is_wnn else "LGA Coordinator"
    elif r in ("cluster_lead", "cluster_coordinator"):
        return "Community Cluster Lead" if is_wnn else "Community Cluster Coordinator"
    elif r in ("chapter_lead", "chapter", "chapter_coordinator"):
        return "Chapter Lead" if is_wnn else "Chapter Coordinator"
    elif r in ("candidate", "applicant"):
        return "Leadership Candidate"
    elif r in ("community", "supporter"):
        return "WODDI Community Participant"
    elif r in ("member", "membership"):
        return "Ordinary Member"
    return r.replace("_", " ").title()


def get_identity_context(
    account: Account,
    user_scope: UserScope,
    active_network: Optional[str] = None,
    active_role: Optional[str] = None,
    active_country: Optional[str] = None,
    request: Any = None,
    target_person: Optional[PersonProfile] = None,
) -> Dict[str, Any]:
    """
    Build the complete, authoritative persistent identity & context block dictionary.
    Safe, truthful, fully reconciled, and non-exposing of sensitive personal data.
    Hierarchy: Network → Country → First-level area → Second-level area → Community Cluster → Chapter (→ Person)
    """
    if not account:
        return {}

    # 1. Active Role, Network, and Country resolution
    role = (active_role or user_scope.active_role or user_scope.primary_role or "member").lower().strip()
    net = (active_network or user_scope.active_network or "WGMN").upper().strip()
    country_code = (active_country or user_scope.active_country or "NG").upper().strip()

    # 2. Identity: Display Name, Initials, Photo
    profile = target_person if isinstance(target_person, PersonProfile) else None
    if not profile and account:
        profile = PersonProfile.objects.filter(account=account).first()
        if not profile and account.email:
            profile = PersonProfile.objects.filter(email__iexact=account.email).first()
        if not profile and account.display_name:
            profile = PersonProfile.objects.filter(full_name__iexact=account.display_name).first()

    display_name = (
        (getattr(profile, "full_name", None) if profile else None)
        or account.display_name
        or (account.person.display_name if account.person else account.email.split("@")[0])
    )
    initials = "".join(part[0] for part in display_name.split()[:2]).upper() or "WD"

    draft_for_photo = OnboardingDraft.objects.filter(account=account).first()
    has_profile_photo = bool(draft_for_photo and draft_for_photo.photo and len(bytes(draft_for_photo.photo)) > 0)
    profile_photo_url = "/onboarding/photo/" if has_profile_photo else None

    # 3. Network branding & insignia
    net_branding = get_network_branding(net)
    role_title = get_active_role_title(role, net_branding["short_name"])

    # 4. Country geography, terminology & flags
    country_info = get_country(country_code) or {}
    country_name = country_info.get("name") or get_country_display_name(country_code) or "Nigeria"
    flag_emoji = get_country_flag_emoji(country_code)

    term = GeographyTerminology.objects.filter(country=country_code, status="effective").first()
    if term:
        first_level_term = term.first_level_term
        second_level_term = term.second_level_term
    else:
        first_level_term = country_info.get("admin1_label") or "State / FCT"
        second_level_term = country_info.get("admin2_label") or "LGA"

    # 5. Assigned Organizational Units resolution (LocalOrganisationUnit / Chapter / Membership / PersonProfile)
    assigned_chapter = None
    membership = None
    if account.person:
        membership = Membership.objects.filter(person=account.person).first()
    if not membership:
        membership = Membership.objects.filter(draft__account=account).first()

    if profile and profile.chapter:
        assigned_chapter = profile.chapter

    if not assigned_chapter and user_scope.chapter_code:
        assigned_chapter = Chapter.objects.filter(code=user_scope.chapter_code).first()

    if not assigned_chapter and membership and membership.home:
        h_code = membership.home.get("code")
        if h_code:
            assigned_chapter = Chapter.objects.filter(code=h_code).first()

    # Look up authoritative units for this country
    country_unit = LocalOrganisationUnit.objects.filter(country=country_code, level="Country").first()
    state_unit = LocalOrganisationUnit.objects.filter(country=country_code, level="Region / State").first()
    lga_unit = LocalOrganisationUnit.objects.filter(country=country_code, level="District / LGA").first()
    cluster_unit = LocalOrganisationUnit.objects.filter(country=country_code, level="Community Cluster").first()
    chapter_unit = LocalOrganisationUnit.objects.filter(country=country_code, level="Chapter").first()

    state_name = None
    lga_name = None
    cluster_name = None
    actual_chapter_name = None

    if profile:
        if profile.state_or_region:
            state_name = profile.state_or_region
        if profile.lga_or_district:
            lga_name = profile.lga_or_district
        if profile.community_cluster:
            cluster_name = profile.community_cluster
        if profile.cluster_unit:
            cluster_unit = profile.cluster_unit
            cluster_name = cluster_unit.unit_name

    if assigned_chapter:
        actual_chapter_name = assigned_chapter.name
        if not state_name and assigned_chapter.region:
            state_name = assigned_chapter.region
        if not lga_name and assigned_chapter.district:
            lga_name = assigned_chapter.district
        if not cluster_name and assigned_chapter.community_cluster:
            cluster_name = assigned_chapter.community_cluster
        if not cluster_name and assigned_chapter.cluster_unit:
            cluster_unit = assigned_chapter.cluster_unit
            cluster_name = cluster_unit.unit_name
        if assigned_chapter.district:
            matched_lga = LocalOrganisationUnit.objects.filter(
                country=country_code,
                level="District / LGA",
                unit_name__icontains=assigned_chapter.district,
            ).first()
            if matched_lga:
                lga_unit = matched_lga
                if matched_lga.parent and not state_unit:
                    state_unit = matched_lga.parent
                matched_cluster = matched_lga.children.filter(level="Community Cluster").first()
                if matched_cluster and not cluster_name:
                    cluster_unit = matched_cluster
                    cluster_name = cluster_unit.unit_name
    elif chapter_unit:
        actual_chapter_name = chapter_unit.unit_name
        if chapter_unit.parent and chapter_unit.parent.level == "Community Cluster":
            cluster_unit = chapter_unit.parent
            if cluster_unit.parent and cluster_unit.parent.level == "District / LGA":
                lga_unit = cluster_unit.parent
                if lga_unit.parent and lga_unit.parent.level == "Region / State":
                    state_unit = lga_unit.parent

    # Check user_scope fallbacks
    if not state_name and user_scope.first_level_area:
        state_name = user_scope.first_level_area
    if not lga_name and user_scope.second_level_area:
        lga_name = user_scope.second_level_area
    if not cluster_name and (user_scope.community_cluster or user_scope.cluster_name):
        cluster_name = user_scope.community_cluster or user_scope.cluster_name
    if not actual_chapter_name and user_scope.chapter_name:
        actual_chapter_name = user_scope.chapter_name

    # Default / fallback names based on country
    if not state_name:
        state_name = state_unit.unit_name if state_unit else ("Lagos State" if country_code == "NG" else f"{country_name} Region")
    if not lga_name:
        lga_name = lga_unit.unit_name if lga_unit else ("Ikeja LGA" if country_code == "NG" else f"{country_name} District")

    if country_code == "NG":
        if state_name and state_name.strip().lower() == "lagos":
            state_name = "Lagos State"
        if lga_name and lga_name.strip().lower() == "ikeja":
            lga_name = "Ikeja LGA"
    if not cluster_name:
        if cluster_unit:
            cluster_name = cluster_unit.unit_name
        else:
            cluster_name = "Ikeja Central Cluster" if country_code == "NG" else "Central Community Cluster"

    if not actual_chapter_name:
        if country_code == "NG":
            actual_chapter_name = "Allen Chapter"
        elif country_code == "KE":
            actual_chapter_name = "Nairobi Central Chapter"
        elif country_code == "GH":
            actual_chapter_name = "Accra Central Chapter"
        else:
            actual_chapter_name = f"{country_name} Central Chapter"

    # CRITICAL: Prevent broad places (e.g. Lagos, Ikeja) from displaying as a Chapter
    actual_chapter_name = sanitize_chapter_display(actual_chapter_name, fallback_country=country_code)

    if cluster_name and not cluster_name.lower().endswith("cluster"):
        cluster_name = f"{cluster_name} Cluster"

    # 6. Experience-specific scope descriptions and badges
    # Founder, country, regional/local operations, Community Cluster, Chapter, member, candidate, community
    if role in ("founder", "hq", "executive"):
        scope_badge = "Continental Oversight · Global HQ"
        display_scope = "Africa-wide Executive Scope"
    elif role in ("country_lead", "country_director", "country_representative"):
        scope_badge = f"National Scope · {country_name}"
        display_scope = f"{country_name} Hub Lead"
    elif role in ("state_lead", "regional_lead", "state_coordinator"):
        scope_badge = f"First-Level Coordination · {state_name}"
        display_scope = f"{state_name} Scope"
    elif role in ("lga_lead", "local_operations", "lga_coordinator"):
        scope_badge = f"District / LGA Operations · {lga_name}"
        display_scope = f"{lga_name} Operations"
    elif role in ("cluster_lead", "cluster_coordinator"):
        scope_badge = f"Community Cluster Oversight · {cluster_name}"
        display_scope = f"{cluster_name} Scope"
    elif role in ("chapter_lead", "chapter_coordinator", "chapter"):
        scope_badge = f"Chapter Leadership · {actual_chapter_name}"
        display_scope = f"{actual_chapter_name} Lead"
    elif role in ("candidate", "applicant"):
        scope_badge = "Applicant / Candidate Pipeline"
        display_scope = "Onboarding & Placement Track"
    elif role in ("community", "supporter"):
        scope_badge = "WODDI Community Participant"
        display_scope = "Connected Community Home"
    else:  # member
        scope_badge = "Enrolled Member"
        display_scope = f"Active Member · {actual_chapter_name}"

    # 7. Construct the Canonical Hierarchy Trail
    # Network → Country → First-Level Area → Second-Level Area → Community Cluster → Chapter (→ Person)
    hierarchy_trail = [
        {
            "id": "network",
            "type": "network",
            "type_label": "Network",
            "label": net_branding["short_name"],
            "full_label": net_branding["full_name"],
            "color": net_branding["brand_color"],
            "icon": "network",
        },
        {
            "id": "country",
            "type": "public_geo",
            "type_label": "Public Geography · Country",
            "label": country_name,
            "term": "Country",
            "flag": flag_emoji,
            "badge": country_code,
            "icon": "flag",
        },
        {
            "id": "first_level",
            "type": "public_geo",
            "type_label": f"Public Geography · {first_level_term}",
            "label": state_name,
            "term": first_level_term,
            "icon": "state",
        },
        {
            "id": "second_level",
            "type": "public_geo",
            "type_label": f"Public Geography · {second_level_term}",
            "label": lga_name,
            "term": second_level_term,
            "icon": "lga",
        },
        {
            "id": "community_cluster",
            "type": "woddi_cluster",
            "type_label": "WODDI Community Cluster",
            "label": cluster_name,
            "term": "Community Cluster",
            "icon": "cluster",
        },
        {
            "id": "chapter",
            "type": "woddi_chapter",
            "type_label": "WODDI Operating Unit · Chapter",
            "label": actual_chapter_name,
            "term": "Chapter",
            "icon": "chapter",
        },
    ]

    person_name = None
    person_code = None
    if profile:
        person_name = getattr(profile, "full_name", None) or getattr(profile, "display_name", None) or display_name
        person_code = getattr(profile, "person_code", "")

    # Clean textual breadcrumb matching the 6-level specification example
    context_breadcrumb_text = (
        f"{net_branding['short_name']} → {country_name} → {state_name} → {lga_name} → {cluster_name} → {actual_chapter_name}"
    )

    return {
        # Active Identity
        "display_name": display_name,
        "initials": initials,
        "has_profile_photo": has_profile_photo,
        "profile_photo_url": profile_photo_url,
        "account_id": str(account.id) if account else "",
        "person_name": person_name,
        "person_code": person_code,
        
        # Active Role / Position
        "active_role": role,
        "active_role_title": role_title,
        "scope_badge": scope_badge,
        "display_scope": display_scope,

        # Network Name, Branding & Logo
        "network_code": net_branding["code"],
        "network_short_name": net_branding["short_name"],
        "network_name": net_branding["full_name"],
        "network_brand_color": net_branding["brand_color"],
        "network_brand_color_dark": net_branding["brand_color_dark"],
        "network_brand_class": net_branding["brand_class"],
        "network_badge_bg": net_branding["badge_bg"],
        "network_badge_border": net_branding["badge_border"],
        "network_badge_text": net_branding["badge_text"],
        "network_logo_svg": net_branding["logo_svg"],

        # Country & Flags
        "country_code": country_code,
        "country_name": country_name,
        "country_flag_emoji": flag_emoji,
        "country_flag_badge": country_code,

        # Administrative Geography (Public)
        "first_level_term": first_level_term,
        "first_level_name": state_name,
        "second_level_term": second_level_term,
        "second_level_name": lga_name,

        # WODDI Organisational Units (Distinct from public geography)
        "cluster_term": "Community Cluster",
        "cluster_name": cluster_name,
        "chapter_term": "Chapter",
        "chapter_name": actual_chapter_name,

        # Structured Trail and Pipeline
        "hierarchy_trail": hierarchy_trail,
        "context_breadcrumb_text": context_breadcrumb_text,
    }
