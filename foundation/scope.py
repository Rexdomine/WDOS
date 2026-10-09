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
    chapter_code: Optional[str] = None
    chapter_name: Optional[str] = None

    def can_access_network(self, network: str) -> bool:
        if not network or network.upper() in ("*", "ALL"):
            return True
        if self.is_management_or_admin or "*" in self.allowed_networks:
            return True
        return network.upper() in [n.upper() for n in self.allowed_networks]

    def can_access_country(self, country_code: str) -> bool:
        if not country_code or country_code.upper() in ("*", "ALL"):
            return True
        if self.is_management_or_admin or "*" in self.allowed_countries:
            return True
        code = country_code.upper()
        return code in [c.upper() for c in self.allowed_countries]

    def can_access_confidential(self) -> bool:
        return self.is_management_or_admin or bool(self.roles.intersection({"management", "it_admin", "reviewer", "founder", "operations"}))

    def can_access_role(self, role: str) -> bool:
        if not role:
            return False
        role = role.lower().strip()
        if self.is_management_or_admin or "founder" in self.roles or "hq" in self.roles or "it_admin" in self.roles:
            return True
        if role in self.roles or role == self.primary_role:
            return True
        if role == "member" and (self.account.person and hasattr(self.account.person, "membership") or self.leadership_tier <= 5):
            return True
        if role == "community":
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
    is_management_or_admin = False

    # Check staff / superuser status
    if account.user.is_superuser or account.user.is_staff:
        is_management_or_admin = True
        roles.add("it_admin")

    # Inspect active AccessGrants
    active_grants = AccessGrant.objects.filter(
        account=account,
        revoked_at__isnull=True,
        expires_at__gt=now,
    )
    for grant in active_grants:
        roles.add(grant.role)
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
                else:
                    chap = Chapter.objects.filter(code=grant.geography).first() or Chapter.objects.filter(name__icontains=grant.geography).first()
                    if chap:
                        allowed_countries.add(chap.country)
                    else:
                        allowed_countries.add(geo)

    # Inspect Membership
    membership = None
    if account.person:
        membership = Membership.objects.filter(person=account.person).first()
    if not membership:
        membership = Membership.objects.filter(draft__account=account).first()
    if membership:
        if membership.network:
            allowed_networks.add(membership.network.upper())
        home_country = (membership.home or {}).get("country")
        if home_country:
            c_info = get_country(home_country)
            if c_info:
                allowed_countries.add(c_info["code"])
            else:
                allowed_countries.add(home_country.upper())

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

    # Determine chapter affiliation
    chapter_code = None
    chapter_name = None
    if membership and membership.home:
        chapter_code = membership.home.get("code")
        chapter_name = membership.home.get("label") or membership.home.get("name")
    for grant in active_grants:
        if grant.role in ("chapter_lead", "chapter") and grant.geography:
            chap = Chapter.objects.filter(code=grant.geography).first() or Chapter.objects.filter(name__icontains=grant.geography).first()
            if chap:
                chapter_code = chapter_code or chap.code
                chapter_name = chapter_name or chap.name
            else:
                chapter_name = chapter_name or grant.geography

    # Determine leadership tier & level & primary role
    leadership_level = "member"
    leadership_tier = 5
    primary_role = "member"

    if "founder" in roles or "hq" in roles:
        leadership_level = "founder"
        leadership_tier = 1
        primary_role = "founder"
    elif "management" in roles or account.user.is_superuser:
        leadership_level = "global_executive"
        leadership_tier = 1
        primary_role = "founder"
    elif "it_admin" in roles:
        leadership_level = "it_admin"
        leadership_tier = 1
        primary_role = "founder"
    elif "operations" in roles:
        leadership_level = "operations"
        leadership_tier = 2
        primary_role = "operations"
    elif "regional_coordinator" in roles or "country_director" in roles or "country_lead" in roles or "field_lead" in roles:
        leadership_level = "country_lead"
        leadership_tier = 3
        primary_role = "country_lead"
    elif "chapter_lead" in roles or "chapter" in roles:
        leadership_level = "chapter_lead"
        leadership_tier = 4
        primary_role = "chapter_lead"
    elif "reviewer" in roles:
        leadership_level = "reviewer"
        leadership_tier = 4
        primary_role = "operations"
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

    # Active role determination
    active_role = None
    if session:
        active_role = session.get("wdos_active_role")
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
        chapter_code=chapter_code,
        chapter_name=chapter_name,
    )


def assert_role_authorized(user_scope: UserScope, role: str):
    """Ensure user is authorized to view the requested role dashboard view."""
    if not user_scope.can_access_role(role):
        raise ScopePermissionDenied(
            message=f"Access Denied: You do not have authorization to view the {role.title()} dashboard.",
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
        c_name = get_country_display_name(country)
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
        return {
            "total_members": total_members,
            "active_chapters": total_chaps,
            "active_alerts": alert_qs.count(),
            "scheduled_meetings": meet_qs.count(),
            "published_reports": rep_qs.count(),
            "wgmn_members": Membership.objects.filter(network="WGMN").count(),
            "wnnn_members": Membership.objects.filter(network="WNNN").count(),
            "wgmn_chapters": Chapter.objects.filter(network="WGMN", status="active").count(),
            "wnnn_chapters": Chapter.objects.filter(network="WNNN", status="active").count(),
        }
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
):
    """
    Raise ScopePermissionDenied if the requested scope is outside the user's authorization.
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
    WDOS → Network Workspace → Country Hub → Leadership Level → Individual Profile
    """
    crumbs = []

    # Level 1: WDOS Root
    crumbs.append({
        "label": "WDOS",
        "url": "/foundation/",
        "is_current": not network and not page_name,
        "tier": "root",
    })

    # Page overlay without network hierarchy (e.g. Work Queue, Notifications, Settings, Privacy)
    if page_name and not network:
        crumbs.append({
            "label": page_name,
            "url": None,
            "is_current": True,
            "tier": "page",
        })
        return crumbs

    # Level 2: Network Workspace
    if network:
        net_is_current = not country and not level and not profile_name and not page_name
        crumbs.append({
            "label": f"{network} Workspace",
            "url": f"/foundation/network/{network}/",
            "is_current": net_is_current,
            "tier": "network",
        })

    # Level 3: Country Hub
    if network and country:
        country_name = get_country_display_name(country)
        country_is_current = not level and not profile_name and not page_name
        crumbs.append({
            "label": f"{country_name} Hub",
            "url": f"/foundation/network/{network}/country/{country}/",
            "is_current": country_is_current,
            "tier": "country",
        })

    # Level 4: Leadership Level
    if network and country and level:
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
