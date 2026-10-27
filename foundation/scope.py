"""
Scope, authorization, breadcrumbs, and confidentiality boundaries for WDOS Stage 4.
Enforces WGMN/WNNN network separation, Country Hub geographic boundary,
server-side permission checks across navigation, APIs, search, notifications, and deep links.
"""
from dataclasses import dataclass, field
from datetime import timedelta
from typing import List, Optional, Set
from django.core.exceptions import PermissionDenied
from django.utils import timezone

from accounts.models import AccessGrant, Account, Membership, OnboardingDraft
from accounts.african_geography import AFRICAN_COUNTRIES, get_country
from .models import Chapter, CountryHub, LeadershipLevel, UserPreference


class ScopePermissionDenied(PermissionDenied):
    """Specific permission denied error with audit context and safe recovery URL."""
    def __init__(
        self,
        message: str,
        reason_code: str = "forbidden",
        attempted_scope: Optional[dict] = None,
        authorized_scope: Optional[dict] = None,
        recovery_url: str = "/foundation/",
    ):
        super().__init__(message)
        self.message = message
        self.reason_code = reason_code
        self.attempted_scope = attempted_scope or {}
        self.authorized_scope = authorized_scope or {}
        self.recovery_url = recovery_url


def normalize_network_code(network: Optional[str]) -> str:
    """Normalize network code (WNN and WNNN are treated synonymously)."""
    if not network:
        return ""
    code = network.strip().upper()
    if code in ("WNN", "WNNN"):
        return "WNNN"
    return code


KNOWN_BROAD_PLACES = {
    # Nigeria States & LGAs
    "lagos", "ikeja", "surulere", "alimosho", "kano", "rivers", "port harcourt", "fct", "abuja",
    "kaduna", "oyo", "ibadan", "enugu", "delta", "warri", "benin", "edo",
    # Kenya Counties & Sub-Counties
    "nairobi", "westlands", "kilimani", "mombasa", "kisumu", "nakuru", "eldoret",
    # Ghana Regions & Districts
    "greater accra", "accra", "accra metro", "tema", "ashanti", "kumasi",
    # Angola Provinces & Municipalities
    "luanda", "ingombota", "benguela", "huambo",
    # Ethiopia Regions & Sub-Cities
    "addis ababa", "bole", "kirkos", "oromia", "amhara",
    # South Africa & Rwanda
    "gauteng", "johannesburg", "kigali", "gasabo",
}


def is_broad_geographic_place(name: Optional[str], country_code: Optional[str] = None) -> bool:
    """
    Check if a string represents a broad administrative geography (Country, State/Region, LGA/District)
    rather than an authoritative WDOS organizational Chapter.
    """
    if not name:
        return False
    norm = name.strip().lower()
    administrative_suffixes = (
        "state", "lga", "region", "province", "county", "district",
        "sub-county", "municipality", "sub-city", "woreda", "fct", "metropolitan"
    )
    for suffix in administrative_suffixes:
        if norm.endswith(suffix):
            return True

    if norm in KNOWN_BROAD_PLACES:
        return True

    # Check if a synthesized "... chapter" phrase was passed (e.g. "Lagos Chapter", "Ikeja Chapter")
    if norm.endswith(" chapter"):
        base_core = norm[:-8].strip()
        if base_core in KNOWN_BROAD_PLACES or any(base_core.endswith(s) for s in administrative_suffixes):
            return True

    try:
        from accounts.african_geography import get_country, get_regions_for_country
        if country_code:
            regions = get_regions_for_country(country_code)
            for r_code, r_name in regions:
                r_norm = r_name.strip().lower()
                if norm == r_norm or norm.startswith(r_norm):
                    return True
        c_info = get_country(country_code or "NG")
        if c_info and norm == (c_info.get("name") or "").strip().lower():
            return True
    except Exception:
        pass

    return False


def is_authoritative_chapter(name: Optional[str]) -> bool:
    """
    Check if a name is explicitly defined as an authoritative Chapter in WDOS data.
    """
    if not name:
        return False
    from .models import Chapter, LocalOrganisationUnit
    c_name = name.strip()
    if Chapter.objects.filter(name__iexact=c_name).exists():
        return True
    if LocalOrganisationUnit.objects.filter(level="Chapter", unit_name__iexact=c_name).exists():
        return True
    return False


def sanitize_chapter_display(raw_name: Optional[str], fallback_country: str = "NG") -> str:
    """
    Prevent broad places such as Lagos or Ikeja from being displayed as a Chapter
    unless the authoritative WDOS data explicitly defines them that way.
    """
    if not raw_name:
        return "Allen Chapter" if fallback_country == "NG" else f"{fallback_country} Central Chapter"
    cleaned = raw_name.strip()

    # If the raw name is already an authoritative chapter in DB, allow it
    if is_authoritative_chapter(cleaned):
        return cleaned

    base_name = cleaned
    if cleaned.lower().endswith("chapter"):
        base_name = cleaned[:-7].strip()

    # If it's a broad place (e.g. Lagos, Ikeja, Surulere, Nairobi)
    if is_broad_geographic_place(cleaned, fallback_country) or is_broad_geographic_place(base_name, fallback_country):
        from .models import Chapter, LocalOrganisationUnit
        chap = Chapter.objects.filter(district__iexact=base_name).first() or Chapter.objects.filter(region__iexact=base_name).first()
        if chap:
            return chap.name
        unit = LocalOrganisationUnit.objects.filter(level="Chapter", parent__unit_name__icontains=base_name).first()
        if unit:
            return unit.unit_name
        return f"{base_name} Chapter (Pending Allocation)" if fallback_country == "NG" else f"{fallback_country} Central Chapter"

    if not cleaned.lower().endswith("chapter") and not cleaned.lower().endswith("hub"):
        cleaned = f"{cleaned} Chapter"
    return cleaned


@dataclass
class UserScope:
    account: Account
    allowed_networks: List[str] = field(default_factory=list)
    allowed_countries: List[str] = field(default_factory=list)  # ISO codes, or ['*'] for all
    leadership_level: str = "member"
    leadership_tier: int = 5
    roles: Set[str] = field(default_factory=set)
    is_management_or_admin: bool = False
    active_network: str = "WGMN"
    active_country: str = "NG"
    primary_role: str = "member"
    active_role: str = "member"
    first_level_area: Optional[str] = None
    second_level_area: Optional[str] = None
    community_cluster: Optional[str] = None
    cluster_name: Optional[str] = None
    cluster_code: Optional[str] = None
    chapter_code: Optional[str] = None
    chapter_name: Optional[str] = None

    @property
    def switchable_roles(self) -> List[str]:
        """Return the ordered list of distinct roles this user is authorized to switch between."""
        alias_to_canon = {
            "membership": "member",
            "applicant": "candidate",
            "supporter": "community",
            "hq": "founder",
            "executive": "founder",
            "ops": "operations",
            "hofco": "operations",
            "country_director": "country_lead",
            "country_representative": "country_lead",
            "field_lead": "country_lead",
            "regional_lead": "state_lead",
            "state_coordinator": "state_lead",
            "lga_coordinator": "lga_lead",
            "cluster_coordinator": "cluster_lead",
            "chapter_coordinator": "chapter_lead",
            "chapter": "chapter_lead",
        }
        primary = alias_to_canon.get(
            (self.primary_role or "member").lower().strip().replace("-", "_"),
            (self.primary_role or "member").lower().strip().replace("-", "_"),
        )
        ordered: List[str] = [primary]

        for r in sorted(self.roles):
            norm = alias_to_canon.get(r.lower().strip().replace("-", "_"), r.lower().strip().replace("-", "_"))
            if norm and norm not in ordered:
                ordered.append(norm)

        if self.is_management_or_admin or bool(self.roles.intersection({"founder", "hq", "it_admin", "management"})):
            for r in ("founder", "operations", "country_lead", "state_lead", "lga_lead", "cluster_lead", "chapter_lead", "member"):
                if r not in ordered:
                    ordered.append(r)
        elif self.leadership_tier <= 4:
            # Leadership tiers can switch between their leadership role(s), subordinate leadership roles, and member view
            for r in ("country_lead", "state_lead", "lga_lead", "cluster_lead", "chapter_lead", "member"):
                if r not in ordered and self.can_access_role(r):
                    ordered.append(r)

        return ordered

    @property
    def has_multiple_roles(self) -> bool:
        """Return True only when the user holds more than one switchable role."""
        return len(self.switchable_roles) > 1

    @property
    def can_cross_network(self) -> bool:
        return (
            self.is_management_or_admin
            or bool(self.roles.intersection({"founder", "hq", "it_admin"}))
            or "*" in self.allowed_networks
            or "ALL" in self.allowed_networks
            or len(set(self.allowed_networks).intersection({"WGMN", "WNNN", "BOTH"})) > 1
        )

    @property
    def can_access_wgmn(self) -> bool:
        return self.can_access_network("WGMN")

    def can_access_network(self, network: str) -> bool:
        if not network:
            return True
        norm_req = normalize_network_code(network)
        if norm_req in ("*", "ALL", "HQ / BOTH NETWORKS", "BOTH"):
            return (
                self.is_management_or_admin
                or bool(self.roles.intersection({"founder", "hofco", "operations", "executive", "hq", "it_admin"}))
                or bool({"*", "ALL", "BOTH", "HQ / BOTH NETWORKS"}.intersection({normalize_network_code(n) for n in self.allowed_networks}))
            )
        if (
            self.is_management_or_admin
            or bool(self.roles.intersection({"founder", "hofco", "operations", "executive", "hq", "it_admin"}))
            or bool({"*", "ALL", "BOTH", "HQ / BOTH NETWORKS"}.intersection({normalize_network_code(n) for n in self.allowed_networks}))
        ):
            return True
        allowed = [normalize_network_code(n) for n in self.allowed_networks]
        return norm_req in allowed

    def can_access_country(self, country_code: str) -> bool:
        if not country_code:
            return True
        code = country_code.strip().upper()
        if code in ("*", "ALL", "HQ / ALL"):
            return self.is_management_or_admin or bool(self.roles.intersection({"founder", "hq", "it_admin", "operations"})) or "*" in self.allowed_countries
        if self.is_management_or_admin or "*" in self.allowed_countries:
            return True
        return code in [c.upper() for c in self.allowed_countries]

    def can_access_confidential(self) -> bool:
        return self.is_management_or_admin or bool(self.roles.intersection({"management", "it_admin", "reviewer", "founder", "operations", "safeguarding"}))

    def can_access_first_level(self, first_level: str) -> bool:
        if not first_level or self.is_management_or_admin or "*" in self.allowed_countries:
            return True
        if self.leadership_tier <= 3 and not self.first_level_area:
            return True
        if self.first_level_area:
            f_norm = first_level.strip().lower()
            m_norm = self.first_level_area.strip().lower()
            return f_norm in m_norm or m_norm in f_norm
        return True

    def can_access_second_level(self, second_level: str) -> bool:
        if not second_level or self.is_management_or_admin or "*" in self.allowed_countries:
            return True
        if self.leadership_tier <= 3 and not self.second_level_area:
            return True
        if self.second_level_area:
            s_norm = second_level.strip().lower()
            m_norm = self.second_level_area.strip().lower()
            return s_norm in m_norm or m_norm in s_norm
        return True

    def can_access_cluster(self, cluster: str) -> bool:
        if not cluster or self.is_management_or_admin or "*" in self.allowed_countries:
            return True
        if self.leadership_tier <= 4 and not self.community_cluster:
            return True
        if self.community_cluster:
            c_clean = cluster.strip().lower().replace(" cluster", "")
            my_c_clean = self.community_cluster.strip().lower().replace(" cluster", "")
            return c_clean in my_c_clean or my_c_clean in c_clean
        if self.chapter_code or self.chapter_name:
            from .models import Chapter
            chap = Chapter.objects.filter(code=self.chapter_code).first() if self.chapter_code else Chapter.objects.filter(name__icontains=self.chapter_name).first()
            if chap and chap.community_cluster:
                return chap.community_cluster.strip().lower() in cluster.strip().lower() or cluster.strip().lower() in chap.community_cluster.strip().lower()
        return True

    def can_access_chapter(self, chapter: str) -> bool:
        if not chapter or self.is_management_or_admin or "*" in self.allowed_countries:
            return True
        if self.leadership_tier < 4:
            return True
        if self.community_cluster:
            from .models import Chapter, LocalOrganisationUnit
            chap = Chapter.objects.filter(code=chapter).first() or Chapter.objects.filter(name__icontains=chapter).first()
            if chap and chap.community_cluster:
                my_c = self.community_cluster.strip().lower().replace(" cluster", "")
                return my_c in chap.community_cluster.strip().lower()
            unit = LocalOrganisationUnit.objects.filter(level="Chapter", unit_name__icontains=chapter).first()
            if unit and unit.parent:
                my_c = self.community_cluster.strip().lower().replace(" cluster", "")
                return my_c in unit.parent.unit_name.strip().lower()
        if self.chapter_code and (chapter.strip().upper() == self.chapter_code.upper()):
            return True
        if self.chapter_name and (self.chapter_name.strip().lower() in chapter.strip().lower() or chapter.strip().lower() in self.chapter_name.strip().lower()):
            return True
        return False

    def can_access_role(self, role: str) -> bool:
        if not role:
            return False
        role = role.lower().strip().replace("-", "_")

        # Top-tier governance and IT administration can access all role views
        if self.is_management_or_admin or bool(self.roles.intersection({"founder", "hq", "it_admin"})):
            return True

        # Ordinary members, candidates, and community users cannot access leadership-only roles
        if self.leadership_tier > 4 and role not in ("member", "membership", "candidate", "applicant", "community", "supporter"):
            return False

        # Candidate can only access candidate or community
        if self.leadership_tier == 6 and role not in ("candidate", "applicant", "community", "supporter"):
            return False

        # Community can only access community
        if self.leadership_tier == 7 and role not in ("community", "supporter"):
            return False

        # Check explicit roles assigned via AccessGrant or primary role
        normalized_roles = {r.lower().strip().replace("-", "_") for r in self.roles}
        normalized_primary = (self.primary_role or "").lower().strip().replace("-", "_")
        if role in normalized_roles or role == normalized_primary:
            return True

        # Role aliases mapping
        role_aliases = {
            "country_lead": {"country_lead", "country_director", "country_representative", "field_lead", "deputy_country_lead"},
            "state_lead": {"state_lead", "regional_lead", "state_coordinator"},
            "lga_lead": {"local_operations", "lga_lead", "lga_coordinator", "district_lead"},
            "cluster_lead": {"cluster_lead", "cluster_coordinator", "cluster"},
            "chapter_lead": {"chapter_lead", "chapter_coordinator", "chapter"},
            "operations": {"operations", "ops", "hofco", "coordinator", "coordination", "regional_coordinator", "programmes", "program_director", "communications", "comms", "resources", "finance", "systems", "quality", "reviewer", "compliance", "safeguarding"},
            "founder": {"founder", "hq", "executive"},
            "admin": {"admin", "administration", "admin_hq"},
            "member": {"member", "membership"},
            "candidate": {"candidate", "applicant"},
            "community": {"community", "supporter"},
            "network_secretary": {"network_secretary", "secretary"},
        }

        # Check exact alias match
        for canon, aliases in role_aliases.items():
            if role in aliases:
                if canon in normalized_roles or canon == normalized_primary:
                    return True
                if normalized_roles.intersection(aliases):
                    return True

        # Hierarchical role inheritance: Higher-tier leaders can access subordinate local roles
        tier_subordinates = {
            "country_lead": {"state_lead", "lga_lead", "cluster_lead", "chapter_lead", "member", "community"},
            "state_lead": {"lga_lead", "cluster_lead", "chapter_lead", "member", "community"},
            "lga_lead": {"cluster_lead", "chapter_lead", "member", "community"},
            "cluster_lead": {"chapter_lead", "member", "community"},
            "chapter_lead": {"member", "community"},
            "operations": {"country_lead", "state_lead", "lga_lead", "cluster_lead", "chapter_lead", "member", "community"},
        }
        for parent_role, subs in tier_subordinates.items():
            parent_aliases = role_aliases.get(parent_role, {parent_role})
            if normalized_roles.intersection(parent_aliases) or normalized_primary in parent_aliases:
                for sub in subs:
                    sub_aliases = role_aliases.get(sub, {sub})
                    if role in sub_aliases:
                        return True

        # Member role accessibility: authorized if account has a membership or is leadership tier <= 5
        if role in ("member", "membership"):
            has_mem = bool(
                (self.account.person and hasattr(self.account.person, "membership"))
                or (hasattr(self.account, "onboardingdraft") and getattr(self.account.onboardingdraft, "membership", None))
            )
            if has_mem or self.leadership_tier <= 5:
                return True

        # Community role accessibility: public/community views available to all authenticated participants
        if role in ("community", "supporter"):
            return True

        return False


def get_user_scope(account: Account, session=None) -> UserScope:
    """
    Derive the authoritative user scope from active account, membership,
    and unexpired, unrevoked AccessGrants.
    """
    if not account or account.status != "active":
        return UserScope(account=account, allowed_networks=[], allowed_countries=[])

    now = timezone.now()
    roles: Set[str] = set()
    allowed_networks: Set[str] = set()
    allowed_countries: Set[str] = set()
    grant_countries: Set[str] = set()
    has_safeguarding_grant = False
    is_management_or_admin = False

    # Inspect active AccessGrants first so explicit role grants are not shadowed by generic staff flag
    active_grants = list(
        AccessGrant.objects.filter(
            account=account,
            revoked_at__isnull=True,
            expires_at__gt=now,
        )
    )

    # Check staff / superuser status
    if account.user.is_superuser or account.user.is_staff:
        is_management_or_admin = True
        if not active_grants:
            roles.add("it_admin")

    for grant in active_grants:
        roles.add(grant.role)
        if getattr(grant, "function", "") == "safeguarding" or grant.role == "safeguarding":
            has_safeguarding_grant = True
            roles.add("safeguarding")
        if grant.role in ("it_admin", "management"):
            is_management_or_admin = True

        if grant.network:
            if grant.network in ("*", "all"):
                allowed_networks.update(["WGMN", "WNNN"])
            else:
                allowed_networks.add(grant.network.upper())

        if grant.geography:
            if grant.geography in ("*", "all"):
                allowed_countries.add("*")
            else:
                # Normalize country code or name
                geo = grant.geography.strip().upper()
                c_info = get_country(geo)
                if c_info:
                    allowed_countries.add(c_info["code"])
                    grant_countries.add(c_info["code"])
                else:
                    chap = Chapter.objects.filter(code=grant.geography).first() or Chapter.objects.filter(name__icontains=grant.geography).first()
                    if chap:
                        allowed_countries.add(chap.country)
                        grant_countries.add(chap.country)
                    else:
                        from .models import LocalOrganisationUnit
                        geo_clean = grant.geography.strip().replace(" Cluster", "").replace(" Chapter", "")
                        l_unit = LocalOrganisationUnit.objects.filter(unit_name__icontains=geo_clean).first()
                        if l_unit:
                            allowed_countries.add(l_unit.country)
                            grant_countries.add(l_unit.country)
                        else:
                            c_prefix = geo.split("-")[0]
                            if get_country(c_prefix):
                                allowed_countries.add(c_prefix)
                                grant_countries.add(c_prefix)
                            else:
                                allowed_countries.add(geo)
                                grant_countries.add(geo)

    # Inspect Membership
    membership = None
    if account.person:
        membership = Membership.objects.filter(person=account.person).first()
    if not membership:
        membership = Membership.objects.filter(draft__account=account).first()
    if membership:
        if membership.network and not allowed_networks:
            allowed_networks.add(membership.network.upper())
        home_country = (membership.home or {}).get("country")
        if home_country:
            c_info = get_country(home_country)
            norm_home_country = c_info["code"] if c_info else home_country.upper()
            # Only add membership country if there are no explicit country grants, or if it matches
            if not grant_countries or norm_home_country in grant_countries:
                allowed_countries.add(norm_home_country)
            elif len(grant_countries) == 1:
                # Auto-heal stale membership country if an explicit single-country AccessGrant exists
                auth_ctry = next(iter(grant_countries))
                default_chaps = {
                    "KE": ("KE-NBO-01", "Nairobi Central Chapter"),
                    "GH": ("GH-ACC-02", "Accra Next-Gen Hub"),
                    "AO": ("AO-LUA-01", "Luanda Central Chapter"),
                    "ET": ("ET-ADD-01", "Addis Ababa Central Chapter"),
                    "NG": ("NG-LOS-01", "Lagos Central Chapter"),
                }
                c_code, c_label = default_chaps.get(auth_ctry, (f"{auth_ctry}-01", f"{auth_ctry} Central Chapter"))
                membership.home = {"code": c_code, "country": auth_ctry, "label": c_label}
                membership.save(update_fields=["home"])

    # Fallback to draft data if membership record is forming
    if not allowed_networks or not allowed_countries:
        draft = OnboardingDraft.objects.filter(account=account, state="accepted").first()
        if draft and draft.data:
            if not allowed_networks and draft.data.get("network"):
                allowed_networks.add(draft.data["network"].upper())
            if not allowed_countries and draft.data.get("country"):
                c_info = get_country(draft.data["country"])
                if c_info:
                    allowed_countries.add(c_info["code"])
                else:
                    allowed_countries.add(draft.data["country"].upper())

    if is_management_or_admin:
        allowed_networks.update(["WGMN", "WNNN"])
        allowed_countries.add("*")

    # If user still has no network, default safe fallback to WGMN
    if not allowed_networks:
        allowed_networks.add("WGMN")
    if not allowed_countries:
        allowed_countries.add("NG")

    # Determine geographic hierarchy and organizational unit affiliation
    first_level_area = None
    second_level_area = None
    community_cluster = None
    cluster_name = None
    cluster_code = None
    chapter_code = None
    chapter_name = None

    # 1. Inspect PersonProfile if present
    from foundation.models import PersonProfile
    profile = PersonProfile.objects.filter(account=account).first()
    if profile:
        first_level_area = getattr(profile, "state_or_region", None) or None
        second_level_area = getattr(profile, "lga_or_district", None) or None
        community_cluster = getattr(profile, "community_cluster", None) or None
        if profile.cluster_unit:
            cluster_name = profile.cluster_unit.unit_name
            cluster_code = getattr(profile.cluster_unit, "unit_code", profile.cluster_unit.unit_name)
            community_cluster = community_cluster or profile.cluster_unit.unit_name
        if profile.chapter:
            chapter_code = profile.chapter.code
            chapter_name = profile.chapter.name
            community_cluster = community_cluster or getattr(profile.chapter, "community_cluster", None)
            if not cluster_name and profile.chapter.cluster_unit:
                cluster_name = profile.chapter.cluster_unit.unit_name
                cluster_code = getattr(profile.chapter.cluster_unit, "unit_code", profile.chapter.cluster_unit.unit_name)
                community_cluster = community_cluster or profile.chapter.cluster_unit.unit_name
            first_level_area = first_level_area or profile.chapter.region
            second_level_area = second_level_area or profile.chapter.district

    # 2. Inspect Membership home
    if membership and membership.home:
        h_code = membership.home.get("code")
        h_label = membership.home.get("label") or membership.home.get("name")
        if h_code:
            chap = Chapter.objects.filter(code=h_code).first()
            if chap:
                chapter_code = chapter_code or chap.code
                chapter_name = chapter_name or chap.name
                community_cluster = community_cluster or chap.community_cluster
                if not cluster_name and chap.cluster_unit:
                    cluster_name = chap.cluster_unit.unit_name
                    cluster_code = getattr(chap.cluster_unit, "unit_code", chap.cluster_unit.unit_name)
                    community_cluster = community_cluster or chap.cluster_unit.unit_name
                first_level_area = first_level_area or chap.region
                second_level_area = second_level_area or chap.district
            else:
                chapter_code = chapter_code or h_code

        if isinstance(membership.home, dict):
            first_level_area = first_level_area or membership.home.get("state") or membership.home.get("region")
            second_level_area = second_level_area or membership.home.get("lga") or membership.home.get("district")
            community_cluster = community_cluster or membership.home.get("cluster") or membership.home.get("community_cluster")
            if not chapter_name and membership.home.get("label"):
                if not is_broad_geographic_place(membership.home["label"], next(iter(allowed_countries)) if allowed_countries else "NG"):
                    chapter_name = membership.home["label"]

        if h_label and not chapter_name:
            if not is_broad_geographic_place(h_label, next(iter(allowed_countries)) if allowed_countries else "NG"):
                chapter_name = h_label
            else:
                # Broad place (e.g. Lagos, Ikeja) must NOT be chapter_name
                if not first_level_area:
                    first_level_area = h_label
                elif not second_level_area and h_label != first_level_area:
                    second_level_area = h_label

    # Fallback to OnboardingDraft data if local area details remain unresolved
    if not (first_level_area and second_level_area and community_cluster):
        draft_record = OnboardingDraft.objects.filter(account=account).first()
        if draft_record and draft_record.data:
            d = draft_record.data
            first_level_area = first_level_area or d.get("region_name") or d.get("region")
            second_level_area = second_level_area or d.get("district_name") or (d.get("district") if d.get("district") and not str(d.get("district")).startswith("NG-") else None)
            d_cluster = d.get("community_cluster")
            if d_cluster:
                community_cluster = community_cluster or d_cluster
                cluster_name = cluster_name or d_cluster
            if not chapter_name and second_level_area:
                chapter_name = f"{second_level_area} Chapter"

    # 3. Inspect AccessGrants
    for grant in active_grants:
        if grant.geography:
            geo = grant.geography.strip()
            if grant.role in ("state_lead", "regional_lead"):
                first_level_area = first_level_area or geo
            elif grant.role in ("lga_lead", "local_operations"):
                second_level_area = second_level_area or geo
            elif grant.role in ("cluster_lead", "cluster_coordinator"):
                community_cluster = community_cluster or geo
                cluster_name = cluster_name or geo
            elif grant.role in ("chapter_lead", "chapter"):
                chap = Chapter.objects.filter(code=geo).first() or Chapter.objects.filter(name__icontains=geo).first()
                if chap:
                    chapter_code = chapter_code or chap.code
                    chapter_name = chapter_name or chap.name
                    community_cluster = community_cluster or chap.community_cluster
                    first_level_area = first_level_area or chap.region
                    second_level_area = second_level_area or chap.district
                else:
                    if is_broad_geographic_place(geo, next(iter(allowed_countries)) if allowed_countries else "NG"):
                        if not first_level_area:
                            first_level_area = geo
                        elif not second_level_area and geo != first_level_area:
                            second_level_area = geo
                    else:
                        chapter_name = chapter_name or geo

    # Prevent broad place names from persisting as chapter_name
    if chapter_name and is_broad_geographic_place(chapter_name, next(iter(allowed_countries)) if allowed_countries else "NG"):
        chapter_name = None

    if cluster_name and not community_cluster:
        community_cluster = cluster_name
    if community_cluster and not cluster_name:
        cluster_name = community_cluster

    # Determine leadership tier & level & primary role
    leadership_level = "member"
    leadership_tier = 5
    primary_role = "member"

    if "founder" in roles or "hq" in roles:
        leadership_level = "founder"
        leadership_tier = 1
        primary_role = "founder"
    elif has_safeguarding_grant or "safeguarding" in roles:
        leadership_level = "operations"
        leadership_tier = 2
        primary_role = "safeguarding"
    elif "operations" in roles or "hofco" in roles or "ops" in roles:
        leadership_level = "operations"
        leadership_tier = 2
        primary_role = "operations"
    elif "coordination" in roles or "coordinator" in roles or "regional_coordinator" in roles:
        leadership_level = "operations"
        leadership_tier = 2
        primary_role = "coordinator"
    elif "network_secretary" in roles:
        leadership_level = "network_secretary"
        leadership_tier = 2
        primary_role = "network_secretary"
    elif "admin" in roles or "administration" in roles or "secretary" in roles:
        leadership_level = "founder"
        leadership_tier = 1
        primary_role = "admin"
    elif "programmes" in roles or "program_director" in roles:
        leadership_level = "operations"
        leadership_tier = 2
        primary_role = "programmes"
    elif "communications" in roles or "comms" in roles:
        leadership_level = "operations"
        leadership_tier = 2
        primary_role = "comms"
    elif "resources" in roles or "finance" in roles:
        leadership_level = "operations"
        leadership_tier = 2
        primary_role = "resources"
    elif "systems" in roles or "it_admin" in roles:
        leadership_level = "it_admin"
        leadership_tier = 1
        primary_role = "systems"
    elif "quality" in roles or "controls" in roles or "compliance" in roles or "reviewer" in roles:
        leadership_level = "reviewer"
        leadership_tier = 2
        primary_role = "quality"
    elif "country_director" in roles or "country_lead" in roles or "field_lead" in roles:
        leadership_level = "country_lead"
        leadership_tier = 3
        primary_role = "country_lead"
    elif "state_lead" in roles or "regional_lead" in roles or "state_coordinator" in roles:
        leadership_level = "country_lead"
        leadership_tier = 3
        primary_role = "state_lead"
    elif "local_operations" in roles or "lga_lead" in roles or "lga_coordinator" in roles:
        leadership_level = "chapter_lead"
        leadership_tier = 4
        primary_role = "local_operations"
    elif "cluster_lead" in roles or "cluster_coordinator" in roles:
        leadership_level = "chapter_lead"
        leadership_tier = 4
        primary_role = "cluster_lead"
    elif "chapter_lead" in roles or "chapter" in roles:
        leadership_level = "chapter_lead"
        leadership_tier = 4
        primary_role = "chapter_lead"
    elif "management" in roles or account.user.is_superuser:
        leadership_level = "global_executive"
        leadership_tier = 1
        primary_role = "founder"
    elif "candidate" in roles:
        leadership_level = "candidate"
        leadership_tier = 6
        primary_role = "candidate"
    elif "community" in roles:
        leadership_level = "community"
        leadership_tier = 7
        primary_role = "community"
    elif membership:
        leadership_level = "member"
        leadership_tier = 5
        primary_role = "member"
    else:
        # Check onboarding draft
        draft = OnboardingDraft.objects.filter(account=account).first()
        if draft and draft.state in ("draft", "review_needed"):
            primary_role = "candidate"
            leadership_level = "candidate"
            leadership_tier = 6
        else:
            primary_role = "community"
            leadership_level = "community"
            leadership_tier = 7

    # Determine active network and active country from session or preferences
    pref = get_user_preferences(account)
    active_network = None
    active_country = None

    if session:
        active_network = session.get("wdos_active_network")
        active_country = session.get("wdos_active_country")

    if not active_network and pref and pref.active_network:
        active_network = pref.active_network
    if not active_country and pref and pref.active_country:
        active_country = pref.active_country

    if not active_network or active_network not in allowed_networks:
        active_network = sorted(list(allowed_networks))[0]

    if not active_country or ("*" not in allowed_countries and active_country not in allowed_countries):
        active_country = "NG" if "*" in allowed_countries else sorted(list(allowed_countries))[0]
        if pref and pref.active_country != active_country[:8]:
            pref.active_country = active_country[:8]
            pref.save(update_fields=["active_country"])

    # Active role determination
    temp_scope = UserScope(
        account=account,
        allowed_networks=sorted(list(allowed_networks)),
        allowed_countries=sorted(list(allowed_countries)),
        leadership_level=leadership_level,
        leadership_tier=leadership_tier,
        roles=roles,
        is_management_or_admin=is_management_or_admin,
        primary_role=primary_role,
        first_level_area=first_level_area,
        second_level_area=second_level_area,
        community_cluster=community_cluster,
        cluster_name=cluster_name,
        cluster_code=cluster_code,
        chapter_code=chapter_code,
        chapter_name=chapter_name,
    )
    active_role = None
    if session:
        cand_role = session.get("wdos_active_role")
        if cand_role and temp_scope.can_access_role(cand_role):
            active_role = cand_role
        elif session.get("wdos_active_role") is not None:
            session["wdos_active_role"] = primary_role
    if not active_role:
        active_role = primary_role

    return UserScope(
        account=account,
        allowed_networks=sorted(list(allowed_networks)),
        allowed_countries=sorted(list(allowed_countries)),
        leadership_level=leadership_level,
        leadership_tier=leadership_tier,
        roles=roles,
        is_management_or_admin=is_management_or_admin,
        active_network=active_network,
        active_country=active_country,
        primary_role=primary_role,
        active_role=active_role,
        first_level_area=first_level_area,
        second_level_area=second_level_area,
        community_cluster=community_cluster,
        cluster_name=cluster_name,
        cluster_code=cluster_code,
        chapter_code=chapter_code,
        chapter_name=chapter_name,
    )


def assert_role_authorized(user_scope: UserScope, role: str):
    """Ensure user is authorized to view the requested role dashboard view."""
    if not user_scope.can_access_role(role):
        raise ScopePermissionDenied(
            message=f"Access Denied: You do not have authorization to view the {role.replace('_', ' ').title()} dashboard.",
            reason_code="unauthorized_role",
            attempted_scope={"role": role},
            authorized_scope={"roles": list(user_scope.roles), "primary_role": user_scope.primary_role},
            recovery_url="/foundation/",
        )


def get_scoped_kpis(user_scope: UserScope, role: str, network: str, country: str) -> dict:
    """Calculate truthful, non-decorative KPIs reconciling directly with database models."""
    from .models import Chapter, DashboardAlert, DashboardActivity, DashboardReport, ScheduledMeeting, WorkItem
    from accounts.models import Membership, OnboardingDraft
    from django.db.models import Sum

    now = timezone.now()

    # Enforce user_scope boundaries if user is not cross-network / global
    is_cross_net = user_scope.is_management_or_admin or bool(user_scope.roles.intersection({"founder", "hq"})) or "*" in user_scope.allowed_networks
    is_cross_geo = user_scope.is_management_or_admin or bool(user_scope.roles.intersection({"founder", "hq"})) or "*" in user_scope.allowed_countries

    if not is_cross_net:
        if not network or network in ("ALL", "*"):
            network = user_scope.active_network
        elif not user_scope.can_access_network(network):
            network = user_scope.active_network

    if not is_cross_geo:
        if not country or country in ("ALL", "*"):
            country = user_scope.active_country
        elif not user_scope.can_access_country(country):
            country = user_scope.active_country

    # Base queries
    mem_qs = Membership.objects.all()
    chap_qs = Chapter.objects.filter(status="active")
    alert_qs = DashboardAlert.objects.filter(is_active=True)
    meet_qs = ScheduledMeeting.objects.filter(scheduled_at__gte=now)
    rep_qs = DashboardReport.objects.filter(status="published")
    act_qs = DashboardActivity.objects.all()
    draft_qs = OnboardingDraft.objects.filter(state="review_needed", membership__isnull=True)
    work_qs = WorkItem.objects.filter(status__in=["pending", "in_progress"])

    # Network scoping (unless 'ALL' / '*')
    if network and network not in ("ALL", "*"):
        mem_qs = mem_qs.filter(network=network)
        chap_qs = chap_qs.filter(network=network)
        alert_qs = alert_qs.filter(network__in=[network, "ALL"])
        meet_qs = meet_qs.filter(network__in=[network, "ALL"])
        rep_qs = rep_qs.filter(network__in=[network, "ALL"])
        act_qs = act_qs.filter(network=network)
        draft_qs = draft_qs.filter(data__network=network)
        work_qs = work_qs.filter(network=network)

    # Country scoping (unless 'ALL' / '*')
    if country and country not in ("ALL", "*"):
        chap_qs = chap_qs.filter(country=country)
        alert_qs = alert_qs.filter(country__in=[country, "ALL"])
        meet_qs = meet_qs.filter(country__in=[country, "ALL"])
        rep_qs = rep_qs.filter(country__in=[country, "ALL"])
        act_qs = act_qs.filter(country=country)
        work_qs = work_qs.filter(country=country)

    if role in ("founder", "hq"):
        total_chaps = chap_qs.count()
        total_mems = mem_qs.count()
        chapter_member_sum = chap_qs.aggregate(total=Sum("member_count"))["total"] or 0
        total_members = max(total_mems, chapter_member_sum)
        res = {
            "total_members": total_members,
            "active_chapters": total_chaps,
            "active_alerts": alert_qs.count(),
            "scheduled_meetings": meet_qs.count(),
            "published_reports": rep_qs.count(),
        }
        # Multi-network comparison only for founder / authorized management
        if is_cross_net:
            res.update({
                "wgmn_members": Membership.objects.filter(network="WGMN").count(),
                "wnnn_members": Membership.objects.filter(network="WNNN").count(),
                "wgmn_chapters": Chapter.objects.filter(network="WGMN", status="active").count(),
                "wnnn_chapters": Chapter.objects.filter(network="WNNN", status="active").count(),
            })
        return res
    elif role == "operations":
        return {
            "pending_verifications": draft_qs.count(),
            "open_work_items": work_qs.count(),
            "urgent_work_items": work_qs.filter(priority="urgent").count(),
            "operational_alerts": alert_qs.filter(category="operations").count(),
            "scheduled_meetings": meet_qs.count(),
            "active_chapters": chap_qs.count(),
        }
    elif role in ("country_lead", "country_director", "field_lead"):
        country_chaps = chap_qs.count()
        country_mems = chap_qs.aggregate(total=Sum("member_count"))["total"] or 0
        if country_mems == 0:
            country_mems = mem_qs.count()
        return {
            "country_members": country_mems,
            "country_chapters": country_chaps,
            "country_verifications": draft_qs.count(),
            "country_meetings": meet_qs.count(),
            "country_alerts": alert_qs.count(),
            "country_reports": rep_qs.count(),
        }
    elif role in ("chapter_lead", "chapter"):
        user_chap = None
        if user_scope.chapter_code:
            user_chap = Chapter.objects.filter(code=user_scope.chapter_code).first()
        if not user_chap and user_scope.chapter_name:
            user_chap = Chapter.objects.filter(name__icontains=user_scope.chapter_name).first()
        if not user_chap:
            user_chap = chap_qs.first()
        chap_member_count = user_chap.member_count if user_chap else mem_qs.count()
        return {
            "chapter_members": chap_member_count,
            "chapter_meetings": meet_qs.count(),
            "chapter_notices": alert_qs.filter(category__in=["chapter", "operations"]).count(),
            "chapter_activities": act_qs.count(),
            "chapter_name": user_chap.name if user_chap else "Local Chapter",
            "chapter_code": user_chap.code if user_chap else "CH-01",
        }
    elif role == "member":
        return {
            "upcoming_meetings": meet_qs.count(),
            "active_alerts": alert_qs.count(),
            "chapter_activities": act_qs.count(),
        }
    elif role == "candidate":
        draft = OnboardingDraft.objects.filter(account=user_scope.account).first()
        step = draft.next_step if draft else 1
        state = draft.state if draft else "draft"
        return {
            "current_step": step,
            "application_state": state,
            "orientation_sessions": meet_qs.filter(meeting_type="orientation").count(),
            "open_bulletins": alert_qs.count(),
        }
    elif role == "community":
        return {
            "open_events": meet_qs.filter(target_role__in=["community", "all"]).count(),
            "total_chapters": chap_qs.count(),
            "country_hubs_count": CountryHub.objects.filter(status="active").count(),
        }

    return {}


def assert_scope_authorized(
    user_scope: UserScope,
    network: Optional[str] = None,
    country: Optional[str] = None,
    level: Optional[str] = None,
    confidential: bool = False,
    first_level: Optional[str] = None,
    second_level: Optional[str] = None,
    cluster: Optional[str] = None,
    chapter: Optional[str] = None,
):
    """
    Raise ScopePermissionDenied if the requested scope is outside the user's authorization.
    Supports network, country, leadership level, confidentiality,
    first-level area, second-level area, community cluster, and chapter.
    """
    if network and not user_scope.can_access_network(network):
        recovery_net = user_scope.allowed_networks[0] if user_scope.allowed_networks else "WGMN"
        raise ScopePermissionDenied(
            message=f"Access Denied: Your account is authorized for {', '.join(user_scope.allowed_networks)}. Access to {network} is prohibited.",
            reason_code="wrong_network",
            attempted_scope={"network": network},
            authorized_scope={"allowed_networks": user_scope.allowed_networks},
            recovery_url=f"/foundation/network/{recovery_net}/",
        )

    if country and not user_scope.can_access_country(country):
        country_name = get_country_display_name(country)
        recovery_country = user_scope.allowed_countries[0] if user_scope.allowed_countries and user_scope.allowed_countries != ["*"] else "NG"
        current_net = network or user_scope.active_network
        raise ScopePermissionDenied(
            message=f"Access Denied: You do not have permission to access the {country_name} Country Hub with your current geographic authorization.",
            reason_code="wrong_country",
            attempted_scope={"network": network, "country": country},
            authorized_scope={"allowed_countries": user_scope.allowed_countries},
            recovery_url=f"/foundation/network/{current_net}/country/{recovery_country}/",
        )

    if first_level and not user_scope.can_access_first_level(first_level):
        raise ScopePermissionDenied(
            message=f"Access Denied: You do not have authorization to view records for {first_level}.",
            reason_code="wrong_first_level",
            attempted_scope={"first_level": first_level},
            authorized_scope={"first_level_area": user_scope.first_level_area},
            recovery_url="/foundation/dashboard/",
        )

    if second_level and not user_scope.can_access_second_level(second_level):
        raise ScopePermissionDenied(
            message=f"Access Denied: You do not have authorization to view records for {second_level}.",
            reason_code="wrong_second_level",
            attempted_scope={"second_level": second_level},
            authorized_scope={"second_level_area": user_scope.second_level_area},
            recovery_url="/foundation/dashboard/",
        )

    if cluster and not user_scope.can_access_cluster(cluster):
        raise ScopePermissionDenied(
            message=f"Access Denied: You do not have authorization to view records for Community Cluster '{cluster}'.",
            reason_code="wrong_cluster",
            attempted_scope={"cluster": cluster},
            authorized_scope={"community_cluster": user_scope.community_cluster},
            recovery_url="/foundation/dashboard/",
        )

    if chapter and not user_scope.can_access_chapter(chapter):
        raise ScopePermissionDenied(
            message=f"Access Denied: You do not have authorization to view records for Chapter '{chapter}'.",
            reason_code="wrong_chapter",
            attempted_scope={"chapter": chapter},
            authorized_scope={"chapter_code": user_scope.chapter_code, "chapter_name": user_scope.chapter_name},
            recovery_url="/foundation/dashboard/",
        )

    if level:
        level_clean = level.lower().strip().replace("-", "_")
        target_lvl = LeadershipLevel.objects.filter(code=level_clean).first()
        target_tier = target_lvl.tier if target_lvl else 5
        # Ordinary members, candidates, community cannot access leadership levels (tier 1..4)
        if target_tier <= 4 and user_scope.leadership_tier > 4:
            raise ScopePermissionDenied(
                f"Access Denied: Leadership level '{level}' is restricted to authorized leadership appointments.",
                reason_code="leadership_restricted",
                attempted_scope={"level": level},
                authorized_scope={"leadership_tier": user_scope.leadership_tier, "roles": list(user_scope.roles)},
                recovery_url="/foundation/dashboard/",
            )
        # Leadership hierarchy: lower-tier leader cannot access higher tier levels
        if not user_scope.is_management_or_admin and user_scope.leadership_tier > target_tier and not user_scope.can_access_role(level_clean):
            raise ScopePermissionDenied(
                f"Access Denied: You do not have authorization to view leadership tier {target_tier}.",
                reason_code="leadership_restricted",
                attempted_scope={"level": level},
                authorized_scope={"leadership_tier": user_scope.leadership_tier, "roles": list(user_scope.roles)},
                recovery_url="/foundation/dashboard/",
            )

    if confidential and not user_scope.can_access_confidential():
        raise ScopePermissionDenied(
            message="Access Denied: This record contains confidential information restricted to authorized leadership and compliance roles.",
            reason_code="confidential",
            recovery_url="/foundation/work-queue/",
        )


def get_user_preferences(account: Account) -> UserPreference:
    """Safe retrieval of UserPreference, automatically recovering from missing records."""
    if not account:
        return UserPreference(
            language="en",
            high_contrast=False,
            reduced_motion=False,
            font_size="standard",
        )
    try:
        draft = OnboardingDraft.objects.filter(account=account).first()
        draft_data = (draft.data or {}) if (draft and draft.data) else {}
        draft_lang = draft_data.get("language")
        init_lang = draft_lang if draft_lang in ("en", "fr", "pt", "ar", "sw") else "en"
        init_font_size = draft_data.get("reading") if draft_data.get("reading") in ("standard", "large", "xlarge") else "standard"
        init_reduced_motion = bool(draft_data.get("reduce_motion"))

        # Align activity digest with Step 6 optional updates choice
        init_digest = "daily"
        if "optional_updates" in draft_data:
            init_digest = "daily" if draft_data.get("optional_updates") else "none"
        elif draft:
            last_consent = draft.consents.order_by("-revision").first()
            if last_consent:
                init_digest = "daily" if last_consent.optional_updates else "none"

        pref, created = UserPreference.objects.get_or_create(
            account=account,
            defaults={
                "language": init_lang,
                "high_contrast": False,
                "reduced_motion": init_reduced_motion,
                "font_size": init_font_size,
                "email_notifications": True,
                "in_app_notifications": True,
                "activity_digest": init_digest,
            },
        )
        if not created and draft_data:
            updated_fields = []
            if draft_lang in ("en", "fr", "pt", "ar", "sw") and pref.language == "en" and draft_lang != "en":
                pref.language = draft_lang
                updated_fields.append("language")
            if init_font_size != "standard" and pref.font_size == "standard":
                pref.font_size = init_font_size
                updated_fields.append("font_size")
            if init_reduced_motion and not pref.reduced_motion:
                pref.reduced_motion = True
                updated_fields.append("reduced_motion")
            if ("optional_updates" in draft_data or (draft and draft.consents.exists())) and init_digest == "none" and pref.activity_digest == "daily":
                pref.activity_digest = "none"
                updated_fields.append("activity_digest")
            if updated_fields:
                pref.save(update_fields=updated_fields)

        return pref
    except Exception:
        # Fallback in-memory default if database read fails
        return UserPreference(
            account=account,
            language="en",
            high_contrast=False,
            reduced_motion=False,
            font_size="standard",
        )


def get_country_display_name(code_or_name: str) -> str:
    """Resolve ISO country code to clean display name."""
    if not code_or_name:
        return ""
    c_info = get_country(code_or_name)
    if c_info:
        return c_info["name"]
    return code_or_name


def get_leadership_display_name(level_code: str) -> str:
    """Resolve leadership level code to title."""
    mapping = {
        "global_executive": "Global Executive",
        "it_admin": "IT Administrator",
        "regional_coordinator": "Regional Coordinator",
        "country_director": "Country Director",
        "chapter_lead": "Chapter Lead",
        "reviewer": "Onboarding Reviewer",
        "member": "Individual Member",
    }
    return mapping.get(level_code, level_code.replace("_", " ").title())


def get_breadcrumbs(
    user_scope: UserScope,
    network: Optional[str] = None,
    country: Optional[str] = None,
    level: Optional[str] = None,
    profile_name: Optional[str] = None,
    page_name: Optional[str] = None,
) -> List[dict]:
    """
    Construct the scoped breadcrumbs trail following the canonical hierarchy:
    Network Workspace → Country Hub → Leadership Level → Individual Profile
    (WDOS root is removed; standalone overlays begin with Home)
    """
    crumbs = []

    # Standalone page overlay without network hierarchy (e.g. Work Queue, Notifications, Settings, Privacy)
    if not network:
        crumbs.append({
            "label": "Home",
            "url": "/foundation/dashboard/",
            "is_current": not page_name,
            "tier": "root",
        })
        if page_name:
            crumbs.append({
                "label": page_name,
                "url": None,
                "is_current": True,
                "tier": "page",
            })
        return crumbs

    # Network hierarchy: WDOS root is removed, begins with Network Workspace
    net_is_current = not country and not level and not profile_name and not page_name
    crumbs.append({
        "label": f"{network} Workspace",
        "url": f"/foundation/network/{network}/",
        "is_current": net_is_current,
        "tier": "network",
    })

    # Level 2: Country Hub
    if country:
        country_name = get_country_display_name(country)
        country_is_current = not level and not profile_name and not page_name
        crumbs.append({
            "label": f"{country_name} Hub",
            "url": f"/foundation/network/{network}/country/{country}/",
            "is_current": country_is_current,
            "tier": "country",
        })

    # Level 3: Leadership Level
    if country and level:
        level_name = get_leadership_display_name(level)
        level_is_current = not profile_name and not page_name
        crumbs.append({
            "label": level_name,
            "url": f"/foundation/network/{network}/country/{country}/leadership/{level}/",
            "is_current": level_is_current,
            "tier": "leadership",
        })

    # Level 5: Individual Profile
    if profile_name:
        crumbs.append({
            "label": profile_name,
            "url": None,
            "is_current": not page_name,
            "tier": "profile",
        })

    # Additional page name inside hierarchy (e.g. Work Item inside Country Hub)
    if page_name and network:
        crumbs.append({
            "label": page_name,
            "url": None,
            "is_current": True,
            "tier": "page",
        })

    return crumbs
