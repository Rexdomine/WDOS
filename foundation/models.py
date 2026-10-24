import uuid
from django.db import models
from django.utils import timezone



class Role(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    description = models.TextField(blank=True)
    is_system = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["code"]

    def __str__(self):
        return self.code


class CountryHub(models.Model):
    code = models.CharField(max_length=8, unique=True)  # e.g., 'NG', 'GH', 'KE'
    name = models.CharField(max_length=100)
    region = models.CharField(max_length=64, blank=True)
    status = models.CharField(
        max_length=16,
        default="active",
        choices=[("active", "Active"), ("forming", "Forming"), ("inactive", "Inactive")],
    )
    lead_name = models.CharField(max_length=150, blank=True)
    lead_email = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} ({self.code})"


class LeadershipLevel(models.Model):
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=128)
    tier = models.PositiveSmallIntegerField(
        default=5,
        help_text="1: Global/Network, 2: Regional, 3: Country, 4: Chapter/Local, 5: Member",
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["tier", "name"]

    def __str__(self):
        return f"{self.name} (Tier {self.tier})"


class WorkItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    summary = models.TextField(blank=True)
    category = models.CharField(
        max_length=32,
        default="general",
        choices=[
            ("review", "Review"),
            ("membership", "Membership"),
            ("approval", "Approval"),
            ("incident", "Incident"),
            ("privacy", "Privacy Request"),
            ("onboarding", "Onboarding"),
            ("general", "General"),
        ],
    )
    network = models.CharField(
        max_length=8,
        choices=[("WGMN", "WGMN"), ("WNNN", "WNNN")],
    )
    country = models.CharField(max_length=8)  # CountryHub ISO code, e.g. 'NG'
    leadership_level = models.ForeignKey(
        LeadershipLevel,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="work_items",
    )
    required_role = models.CharField(max_length=64, default="member")
    assigned_to = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_work_items",
    )
    status = models.CharField(
        max_length=24,
        default="pending",
        choices=[
            ("pending", "Pending"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("blocked", "Blocked"),
        ],
    )
    priority = models.CharField(
        max_length=16,
        default="normal",
        choices=[
            ("urgent", "Urgent"),
            ("high", "High"),
            ("normal", "Normal"),
            ("low", "Low"),
        ],
    )
    confidential = models.BooleanField(default=False)
    target_url = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_work_items",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-priority", "-created_at"]
        indexes = [
            models.Index(fields=["network", "country", "status"]),
            models.Index(fields=["assigned_to", "status"]),
        ]

    def __str__(self):
        return f"[{self.network}/{self.country}] {self.title} ({self.status})"


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    network = models.CharField(max_length=8, blank=True)
    country = models.CharField(max_length=8, blank=True)
    title = models.CharField(max_length=200)
    message = models.TextField()
    category = models.CharField(
        max_length=32,
        default="system",
        choices=[
            ("work_queue", "Work Queue"),
            ("security", "Security"),
            ("system", "System"),
            ("privacy", "Privacy Request"),
            ("activity", "Activity"),
        ],
    )
    target_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    delivery_status = models.CharField(
        max_length=16,
        default="delivered",
        choices=[
            ("delivered", "Delivered"),
            ("failed", "Failed"),
            ("pending", "Pending"),
        ],
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["account", "is_read"]),
            models.Index(fields=["account", "network"]),
        ]

    def __str__(self):
        return f"Notification({self.account_id}, {self.title}, read={self.is_read})"


class UserPreference(models.Model):
    account = models.OneToOneField(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="preferences",
    )
    language = models.CharField(max_length=8, default="en")
    high_contrast = models.BooleanField(default=False)
    reduced_motion = models.BooleanField(default=False)
    font_size = models.CharField(
        max_length=16,
        default="standard",
        choices=[
            ("standard", "Standard"),
            ("large", "Large"),
            ("xlarge", "Extra Large"),
        ],
    )
    email_notifications = models.BooleanField(default=True)
    in_app_notifications = models.BooleanField(default=True)
    activity_digest = models.CharField(
        max_length=16,
        default="daily",
        choices=[
            ("realtime", "Real-time"),
            ("daily", "Daily Digest"),
            ("weekly", "Weekly Digest"),
            ("none", "None"),
        ],
    )
    active_network = models.CharField(max_length=8, blank=True)
    active_country = models.CharField(max_length=8, blank=True)
    reminder_preference = models.CharField(
        max_length=64,
        default="inside_wdos",
        choices=[
            ("inside_wdos", "Keep reminders inside WDOS"),
            ("browser", "Send browser notifications"),
            ("none", "Do not send reminders"),
        ],
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"UserPreference({self.account_id}, lang={self.language})"


class DeviceSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="device_sessions",
    )
    session_key = models.CharField(max_length=64, blank=True)
    device_name = models.CharField(max_length=128, default="This device")
    browser_info = models.CharField(max_length=128, default="Chrome · Lagos")
    ip_address = models.CharField(max_length=64, default="127.0.0.1")
    is_current = models.BooleanField(default=False)
    last_active = models.DateTimeField(auto_now=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-last_active"]

    def __str__(self):
        return f"DeviceSession({self.account_id}, {self.device_name}, current={self.is_current})"


class PrivacyRequest(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="privacy_requests",
    )
    reference = models.CharField(max_length=32, default="PR-DEMO-01")
    request_type = models.CharField(
        max_length=64,
        default="Correct my information",
    )
    details = models.TextField(blank=True)
    safe_reply_route = models.CharField(max_length=64, default="Reply in my account")
    current_step = models.CharField(max_length=64, default="Identity check required")
    next_action = models.CharField(max_length=128, default="Confirm through the approved verification route")
    identity_check_status = models.CharField(max_length=32, default="Not checked")
    decision = models.CharField(max_length=64, default="More information needed")
    reason_and_retention = models.TextField(blank=True)
    timeline = models.JSONField(default=list, blank=True)
    status = models.CharField(
        max_length=32,
        default="Waiting for review",
    )
    reason = models.TextField(blank=True)
    resolution_notes = models.TextField(blank=True)
    export_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PrivacyRequest({self.account_id}, {self.reference}, {self.status})"


class NetworkTransition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(
        "accounts.Account",
        on_delete=models.CASCADE,
        related_name="network_transitions",
    )
    current_relationship = models.CharField(max_length=128, default="WNNN membership")
    requested_transition = models.CharField(max_length=128, default="WGMN membership review")
    age_evidence_method = models.CharField(max_length=128, default="Approved re-attestation")
    consent_confirmed = models.BooleanField(default=False)
    status = models.CharField(max_length=32, default="in_progress")
    step = models.PositiveSmallIntegerField(default=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"NetworkTransition({self.account_id}, {self.requested_transition})"


class Chapter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=150)
    network = models.CharField(max_length=8, choices=[("WGMN", "WGMN"), ("WNNN", "WNNN")])
    country = models.CharField(max_length=8)  # ISO code like 'NG', 'KE', 'GH'
    region = models.CharField(max_length=100)
    district = models.CharField(max_length=100, blank=True)
    community_cluster = models.CharField(max_length=150, blank=True)
    cluster_unit = models.ForeignKey(
        "LocalOrganisationUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="chapters",
    )
    status = models.CharField(
        max_length=16,
        default="active",
        choices=[("active", "Active"), ("forming", "Forming"), ("inactive", "Inactive")],
    )
    lead_name = models.CharField(max_length=150, blank=True)
    lead_email = models.CharField(max_length=150, blank=True)
    member_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["network", "country"]),
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.network}/{self.country})"


class DashboardAlert(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    message = models.TextField()
    severity = models.CharField(
        max_length=16,
        default="info",
        choices=[("info", "Info"), ("warning", "Warning"), ("critical", "Critical")],
    )
    category = models.CharField(
        max_length=32,
        default="operations",
        choices=[
            ("governance", "Governance"),
            ("operations", "Operations"),
            ("compliance", "Compliance"),
            ("verification", "Verification"),
            ("chapter", "Chapter"),
        ],
    )
    network = models.CharField(
        max_length=8,
        choices=[("WGMN", "WGMN"), ("WNNN", "WNNN"), ("ALL", "All Networks")],
        default="ALL",
    )
    country = models.CharField(max_length=8, default="ALL")
    geography = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    action_url = models.CharField(max_length=255, blank=True)
    acknowledged_by = models.ManyToManyField("accounts.Account", blank=True, related_name="acknowledged_alerts")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["network", "country", "is_active"]),
        ]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.title}"


class DashboardActivity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    activity_type = models.CharField(max_length=48)
    network = models.CharField(max_length=8, choices=[("WGMN", "WGMN"), ("WNNN", "WNNN")])
    country = models.CharField(max_length=8)
    geography = models.CharField(max_length=100, blank=True)
    actor_name = models.CharField(max_length=150, blank=True)
    actor = models.ForeignKey("accounts.Account", null=True, blank=True, on_delete=models.SET_NULL)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["network", "country"]),
        ]

    def __str__(self):
        return f"[{self.network}/{self.country}] {self.title}"


class DashboardReport(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    report_type = models.CharField(
        max_length=48,
        choices=[
            ("executive_summary", "Executive Summary"),
            ("operational_pulse", "Operational Pulse"),
            ("country_health", "Country Health"),
            ("chapter_assessment", "Chapter Assessment"),
            ("onboarding_throughput", "Onboarding Throughput"),
            ("compliance_audit", "Compliance Audit"),
        ],
    )
    network = models.CharField(max_length=8, choices=[("WGMN", "WGMN"), ("WNNN", "WNNN"), ("ALL", "All Networks")], default="ALL")
    country = models.CharField(max_length=8, default="ALL")
    geography = models.CharField(max_length=100, blank=True)
    period = models.CharField(max_length=64)
    summary = models.TextField()
    metrics = models.JSONField(default=dict, blank=True)
    status = models.CharField(
        max_length=24,
        default="published",
        choices=[("published", "Published"), ("draft", "Draft"), ("archived", "Archived")],
    )
    author_name = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["network", "country", "status"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.period})"


class ScheduledMeeting(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    meeting_type = models.CharField(
        max_length=48,
        default="country_assembly",
        choices=[
            ("strategic_hq", "Strategic HQ Council"),
            ("operational_sync", "Operational Sync"),
            ("country_assembly", "Country Assembly"),
            ("chapter_meetup", "Chapter Meetup"),
            ("orientation", "Candidate Orientation"),
            ("community_open", "Community Open Session"),
        ],
    )
    network = models.CharField(max_length=8, choices=[("WGMN", "WGMN"), ("WNNN", "WNNN"), ("ALL", "All Networks")], default="ALL")
    country = models.CharField(max_length=8, default="ALL")
    geography = models.CharField(max_length=100, blank=True)
    scheduled_at = models.DateTimeField(default=timezone.now)
    duration_minutes = models.PositiveIntegerField(default=60)
    location = models.CharField(max_length=255, blank=True)
    attendees_count = models.PositiveIntegerField(default=0)
    target_role = models.CharField(max_length=48, default="all")
    organizer_name = models.CharField(max_length=150, blank=True)
    host_profile = models.ForeignKey(
        "PersonProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hosted_scheduled_meetings",
    )
    rsvp_accounts = models.ManyToManyField("accounts.Account", blank=True, related_name="rsvpd_meetings")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_at"]
        indexes = [
            models.Index(fields=["network", "country", "scheduled_at"]),
        ]

    def __init__(self, *args, **kwargs):
        scheduled_start = kwargs.pop("scheduled_start", None)
        network_scope = kwargs.pop("network_scope", None)
        super().__init__(*args, **kwargs)
        if scheduled_start is not None:
            self.scheduled_at = scheduled_start
        if network_scope is not None:
            self.network_scope = network_scope

    @property
    def scheduled_start(self):
        return self.scheduled_at

    @scheduled_start.setter
    def scheduled_start(self, value):
        self.scheduled_at = value

    @property
    def network_scope(self) -> str:
        return self.network if self.network != "ALL" else "WGMN"

    @network_scope.setter
    def network_scope(self, value: str):
        val = (value or "").strip()
        if val in ("WGMN", "WNNN", "ALL"):
            self.network = val
        elif "WNNN" in val.upper():
            self.network = "WNNN"
        elif "WGMN" in val.upper():
            self.network = "WGMN"

    def __str__(self):
        return f"{self.title} ({self.scheduled_at.strftime('%Y-%m-%d %H:%M')})"



class Communication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subject = models.CharField(max_length=200)
    body = models.TextField()
    sender_name = models.CharField(max_length=150, default="Headquarters")
    network = models.CharField(max_length=8, choices=[("WGMN", "WGMN"), ("WNNN", "WNNN"), ("ALL", "All Networks")], default="ALL")
    country = models.CharField(max_length=8, default="ALL")
    target_role = models.CharField(max_length=48, default="all")
    priority = models.CharField(
        max_length=16,
        default="normal",
        choices=[("normal", "Normal"), ("high", "High"), ("urgent", "Urgent")],
    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["network", "country", "target_role"]),
        ]

    def __str__(self):
        return self.subject


class PersonProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person_code = models.CharField(max_length=32, unique=True, default="WD-00421")
    full_name = models.CharField(max_length=150)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=32, blank=True)
    network = models.CharField(max_length=8, choices=[("WGMN", "WGMN"), ("WNNN", "WNNN"), ("BOTH", "Both Networks")], default="WGMN")
    country = models.CharField(max_length=8, default="NG")
    state_or_region = models.CharField(max_length=100, blank=True)
    lga_or_district = models.CharField(max_length=100, blank=True)
    community_cluster = models.CharField(max_length=150, blank=True)
    cluster_unit = models.ForeignKey(
        "LocalOrganisationUnit",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="person_cluster_members",
    )
    local_home = models.CharField(max_length=150, default="Ikeja Chapter")
    chapter = models.ForeignKey(Chapter, null=True, blank=True, on_delete=models.SET_NULL, related_name="members")
    account = models.ForeignKey("accounts.Account", null=True, blank=True, on_delete=models.SET_NULL, related_name="person_profiles")
    user = models.OneToOneField(
        "auth.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="direct_person_profile",
    )
    contact_verification = models.CharField(max_length=32, default="Verified", choices=[("Verified", "Verified"), ("Pending", "Pending"), ("Unverified", "Unverified")])
    primary_relationship = models.CharField(max_length=100, default="Member")
    status = models.CharField(max_length=32, default="Active", choices=[("Active", "Active"), ("Review due", "Review due"), ("Inactive", "Inactive")])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __init__(self, *args, **kwargs):
        primary_network = kwargs.pop("primary_network", None)
        super().__init__(*args, **kwargs)
        if primary_network is not None:
            self.network = primary_network

    @property
    def primary_network(self) -> str:
        return self.network

    @primary_network.setter
    def primary_network(self, value: str):
        self.network = value

    def save(self, *args, **kwargs):
        if self.user_id and not self.account_id:
            from accounts.models import Account
            linked_acc = Account.objects.filter(user_id=self.user_id).first()
            if linked_acc:
                self.account = linked_acc
        if not self.person_code or (
            self.person_code == "WD-00421"
            and PersonProfile.objects.exclude(pk=self.pk).filter(person_code="WD-00421").exists()
        ):
            self.person_code = f"WD-{str(self.id or uuid.uuid4())[:6].upper()}"
        super().save(*args, **kwargs)


    @property
    def chapter_name(self):
        if self.chapter:
            return self.chapter.name
        return self.local_home or ""

    @property
    def region(self):
        return self.state_or_region or ""

    @property
    def district(self):
        return self.lga_or_district or ""

    @property
    def hierarchy_path(self):
        return getattr(self, "_hierarchy_path", None) or self.get_hierarchy_path()

    @hierarchy_path.setter
    def hierarchy_path(self, val):
        self._hierarchy_path = val

    def get_hierarchy_path(self):
        """
        Returns the authoritative 6-tier hierarchy path:
        Country → State/first-level area equivalent → Local government/LGA/district equivalent → Community Cluster → Chapter → Person
        using country-specific terminology.
        """
        from .context_block import get_country_flag_emoji
        from accounts.african_geography import get_country

        c_code = (self.country or "NG").upper()
        term = GeographyTerminology.objects.filter(country=c_code, status="effective").first()
        c_info = get_country(c_code) or {}
        c_name = c_info.get("name") or (term.country_name if term else "Nigeria")
        c_flag = get_country_flag_emoji(c_code)

        first_term = term.first_level_term if term else (c_info.get("admin1_label") or "State / FCT")
        second_term = term.second_level_term if term else (c_info.get("admin2_label") or "LGA")

        # Resolve state/first-level
        first_name = self.state_or_region
        if not first_name:
            if self.chapter and self.chapter.region:
                first_name = self.chapter.region
            elif c_code == "NG":
                first_name = "Lagos State"
            else:
                first_name = f"{c_name} Region"

        # Resolve LGA/second-level
        second_name = self.lga_or_district
        if not second_name:
            if self.chapter and self.chapter.district:
                second_name = self.chapter.district
            elif c_code == "NG":
                second_name = "Ikeja LGA"
            else:
                second_name = f"{c_name} District"

        # Resolve Community Cluster (WODDI organisational unit)
        cluster_name = self.community_cluster
        if not cluster_name and self.cluster_unit:
            cluster_name = self.cluster_unit.unit_name
        if not cluster_name and self.chapter and self.chapter.community_cluster:
            cluster_name = self.chapter.community_cluster
        if not cluster_name:
            c_unit = LocalOrganisationUnit.objects.filter(country=c_code, level="Community Cluster").first()
            if c_unit:
                cluster_name = c_unit.unit_name
            else:
                cluster_name = "Ikeja Central Cluster" if c_code == "NG" else "Central Community Cluster"

        if cluster_name and not cluster_name.lower().endswith("cluster"):
            cluster_name = f"{cluster_name} Cluster"

        # Resolve Chapter (WODDI operating unit)
        chap_name = self.chapter.name if self.chapter else ""
        if not chap_name:
            raw_home = (self.local_home or "").strip()
            # Prevent bare broad place names like "Lagos" or "Ikeja" from being treated as chapter
            if raw_home and raw_home.lower() not in {"lagos", "ikeja", "abuja", "kano", "nairobi", "accra"}:
                chap_name = raw_home
            else:
                ch_unit = LocalOrganisationUnit.objects.filter(country=c_code, level="Chapter").first()
                if ch_unit:
                    chap_name = ch_unit.unit_name
                else:
                    chap_name = "Allen Chapter" if c_code == "NG" else f"{c_name} Central Chapter"

        path_steps = [
            {"level": "country", "term": "Country", "name": c_name, "flag": c_flag, "code": c_code, "type": "public_geo"},
            {"level": "first_level", "term": first_term, "name": first_name, "type": "public_geo"},
            {"level": "second_level", "term": second_term, "name": second_name, "type": "public_geo"},
            {"level": "cluster", "term": "Community Cluster", "name": cluster_name, "type": "woddi_cluster"},
            {"level": "chapter", "term": "Chapter", "name": chap_name, "type": "woddi_chapter"},
            {"level": "person", "term": "Person", "name": self.full_name, "code": self.person_code, "type": "person"},
        ]

        breadcrumb = f"{c_name} → {first_name} → {second_name} → {cluster_name} → {chap_name} → {self.full_name}"

        path_nodes = [
            {"tier": s["level"], "term": s["term"], "name": s["name"], "badge_type": s["type"]}
            for s in path_steps
        ]

        return {
            "country_code": c_code,
            "country_name": c_name,
            "country_flag": c_flag,
            "first_level_term": first_term,
            "first_level_name": first_name,
            "second_level_term": second_term,
            "second_level_name": second_name,
            "cluster_term": "Community Cluster",
            "cluster_name": cluster_name,
            "cluster_code": getattr(self.cluster_unit, "code", "") if self.cluster_unit else "",
            "chapter_term": "Chapter",
            "chapter_name": chap_name,
            "chapter_code": getattr(self.chapter, "code", "") if self.chapter else "",
            "person_code": self.person_code,
            "person_name": self.full_name,
            "path_steps": path_steps,
            "path_nodes": path_nodes,
            "path_display": breadcrumb,
            "breadcrumb": breadcrumb,
        }

    @property
    def chapter_name(self) -> str:
        if self.chapter and self.chapter.name:
            return self.chapter.name
        return self.get_hierarchy_path()["chapter_name"]

    @chapter_name.setter
    def chapter_name(self, value: str):
        if not value:
            return
        chap = Chapter.objects.filter(name__iexact=value).first()
        if chap:
            self.chapter = chap
        self.local_home = value

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["network", "country", "status"]),
            models.Index(fields=["person_code"]),
        ]

    def __str__(self):
        return f"{self.full_name} ({self.person_code})"


class PersonRelationship(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(PersonProfile, on_delete=models.CASCADE, related_name="relationships")
    category = models.CharField(max_length=64, default="membership")
    relationship_label = models.CharField(max_length=100, default="Member")
    related_programme = models.CharField(max_length=150, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=32, default="Active", choices=[("Active", "Active"), ("Review due", "Review due"), ("Former", "Former")])
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.person.full_name} - {self.relationship_label}"


class LocalHomeReassignment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    person = models.ForeignKey(PersonProfile, on_delete=models.CASCADE, related_name="reassignments")
    current_local_home = models.CharField(max_length=150)
    proposed_local_home = models.CharField(max_length=150)
    reason = models.TextField()
    member_confirmation = models.BooleanField(default=False)
    evidence_reference = models.CharField(max_length=150, blank=True)
    status = models.CharField(
        max_length=32,
        default="in_progress",
        choices=[
            ("draft", "Draft"),
            ("in_progress", "In progress"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
    )
    submitted_by = models.ForeignKey("accounts.Account", null=True, blank=True, on_delete=models.SET_NULL, related_name="submitted_reassignments")
    reviewed_by = models.ForeignKey("accounts.Account", null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_reassignments")
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Reassignment for {self.person.full_name} ({self.current_local_home} -> {self.proposed_local_home})"


class CountryDossier(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    country_code = models.CharField(max_length=8, default="NG")
    country_name = models.CharField(max_length=100, default="Nigeria")
    network = models.CharField(max_length=8, choices=[("WGMN", "WGMN"), ("WNNN", "WNNN")], default="WGMN")
    country_lead_name = models.CharField(max_length=150, default="Ada Okafor")
    country_lead = models.ForeignKey("accounts.Account", null=True, blank=True, on_delete=models.SET_NULL, related_name="lead_dossiers")
    timezone_reference = models.CharField(max_length=100, default="Africa/Lagos · WAT")
    verification_status = models.CharField(
        max_length=48,
        default="Country verified",
        choices=[
            ("Country verified", "Country verified"),
            ("HQ review", "HQ review"),
            ("Update requested", "Update requested"),
            ("Pending review", "Pending review"),
        ],
    )
    verification_stage = models.CharField(max_length=100, default="Country custodian review")
    next_review_date = models.CharField(max_length=32, default="30 Sep")
    evidence_reference = models.CharField(max_length=150, default="Country register revision 03")
    verification_notes = models.TextField(
        default="Leadership corrections resolved; language readiness remains under review."
    )
    verified_by = models.ForeignKey("accounts.Account", null=True, blank=True, on_delete=models.SET_NULL, related_name="verified_dossiers")
    verified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["country_name", "network"]
        indexes = [
            models.Index(fields=["network", "country_code"]),
        ]

    def __str__(self):
        return f"{self.network} · {self.country_name} ({self.verification_status})"


class LocalOrganisationUnit(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    network = models.CharField(max_length=8, choices=[("WGMN", "WGMN"), ("WNNN", "WNNN")], default="WGMN")
    country = models.CharField(max_length=8, default="NG")
    unit_name = models.CharField(max_length=150)
    level = models.CharField(
        max_length=64,
        choices=[
            ("Country", "Country"),
            ("Region / State", "Region / State"),
            ("District / LGA", "District / LGA"),
            ("Community Cluster", "Community Cluster"),
            ("Chapter", "Chapter"),
        ],
    )
    level_order = models.PositiveSmallIntegerField(default=1)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="children")
    description = models.TextField(blank=True)
    responsible_leader_name = models.CharField(max_length=150)
    responsible_leader = models.ForeignKey("accounts.Account", null=True, blank=True, on_delete=models.SET_NULL, related_name="led_org_units")
    evidence_type = models.CharField(max_length=64, default="Unit record")
    record_state = models.CharField(max_length=64, default="Active unit records")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["level_order", "unit_name"]
        indexes = [
            models.Index(fields=["network", "country", "level_order"]),
        ]

    def __str__(self):
        return f"{self.unit_name} ({self.level})"


class GeographyTerminology(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    country = models.CharField(max_length=8, default="NG")
    country_name = models.CharField(max_length=100, default="Nigeria")
    first_level_term = models.CharField(max_length=100, default="State / FCT")
    second_level_term = models.CharField(max_length=100, default="LGA")
    effective_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=32, default="effective", choices=[("effective", "Effective"), ("proposed", "Proposed"), ("archived", "Archived")])
    proposed_by = models.ForeignKey("accounts.Account", null=True, blank=True, on_delete=models.SET_NULL, related_name="proposed_terminologies")
    approved_by = models.ForeignKey("accounts.Account", null=True, blank=True, on_delete=models.SET_NULL, related_name="approved_terminologies")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["country_name"]

    def __str__(self):
        return f"{self.country_name}: {self.first_level_term} / {self.second_level_term}"


# -----------------------------------------------------------------------------
# STAGE 07: LEADERSHIP STRUCTURE, VACANCIES, APPOINTMENTS, AND HANDOVER
# -----------------------------------------------------------------------------

class PositionMaster(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    position_code = models.CharField(max_length=64, unique=True)
    wgmn_title = models.CharField(max_length=120)
    wnnn_title = models.CharField(max_length=120)
    logical_level = models.CharField(max_length=64, default="Region / State")
    tier = models.CharField(max_length=32, default="regional")
    reports_to_code = models.CharField(max_length=64, default="COUNTRY_REPRESENTATIVE")
    reports_to_label = models.CharField(max_length=150, default="Country principal")
    is_deputy = models.BooleanField(default=False)
    status = models.CharField(
        max_length=32,
        default="effective",
        choices=[("effective", "Effective"), ("proposed", "Proposed"), ("archived", "Archived")],
    )
    proposed_wgmn_title = models.CharField(max_length=120, blank=True)
    proposed_wnnn_title = models.CharField(max_length=120, blank=True)
    proposed_reports_to_label = models.CharField(max_length=150, blank=True)
    updated_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_positions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position_code"]

    def display_title_for_network(self, network: str = "WGMN") -> str:
        if (network or "").upper() == "WNNN":
            return self.wnnn_title
        return self.wgmn_title

    def __str__(self):
        return f"{self.position_code} ({self.wgmn_title} / {self.wnnn_title})"


class LeadershipSeat(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seat_code = models.CharField(max_length=64, unique=True)
    position = models.ForeignKey(PositionMaster, on_delete=models.PROTECT, related_name="seats")
    position_title = models.CharField(max_length=120)
    network = models.CharField(max_length=8, choices=[("WGMN", "WGMN"), ("WNNN", "WNNN")], default="WGMN")
    country = models.CharField(max_length=8, default="NG")
    unit_name = models.CharField(max_length=150)
    unit_label = models.CharField(max_length=150, blank=True)
    org_unit = models.ForeignKey(
        LocalOrganisationUnit,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leadership_seats",
    )
    parent_seat = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subordinate_seats",
    )
    holder_person = models.ForeignKey(
        PersonProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="held_seats",
    )
    holder_name = models.CharField(max_length=150, default="Unfilled")
    status = models.CharField(max_length=48, default="Vacant")
    reports_to_label = models.CharField(max_length=150, default="Country Representative · Nigeria")
    is_approved_seat = models.BooleanField(default=True)
    vacancy_reason = models.CharField(
        max_length=255,
        blank=True,
        default="An approved deputy seat needs a candidate referral.",
    )
    summary_note = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["network", "country", "seat_code"]
        indexes = [
            models.Index(fields=["network", "country", "status"]),
        ]

    def __str__(self):
        return f"{self.unit_name} · {self.position_title} ({self.holder_name} - {self.status})"


class CandidateReferral(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seat = models.ForeignKey(LeadershipSeat, on_delete=models.CASCADE, related_name="referrals")
    candidate_person = models.ForeignKey(
        PersonProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leadership_referrals",
    )
    candidate_name = models.CharField(max_length=150)
    candidate_email = models.EmailField(blank=True)
    suitability_notes = models.TextField(blank=True)
    status = models.CharField(
        max_length=32,
        default="Referred",
        choices=[
            ("Referred", "Referred"),
            ("Under review", "Under review"),
            ("Selected", "Selected"),
            ("Declined", "Declined"),
        ],
    )
    referred_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="submitted_referrals",
    )
    reviewed_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_referrals",
    )
    idempotency_key = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.candidate_name} -> {self.seat.position_title} ({self.status})"


class AppointmentRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment_code = models.CharField(max_length=48, unique=True)
    seat = models.ForeignKey(LeadershipSeat, on_delete=models.CASCADE, related_name="appointments")
    person = models.ForeignKey(
        PersonProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="appointments",
    )
    account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="leadership_appointments",
    )
    appointee_name = models.CharField(max_length=150)
    position_title = models.CharField(max_length=120)
    unit_name = models.CharField(max_length=150, default="Ikeja")
    network = models.CharField(max_length=8, default="WGMN")
    country = models.CharField(max_length=8, default="NG")
    stage = models.CharField(max_length=48, default="Acceptance pending")
    next_action = models.CharField(max_length=100, default="View offer")
    reporting_line = models.CharField(max_length=150, default="Assigned Cluster Coordinator")
    official_identity_status = models.CharField(max_length=100, default="Provisioning review pending")
    letter_reference = models.CharField(max_length=150, default="Open issued appointment letter")
    acceptance_confirmed = models.BooleanField(default=True)
    commitment_confirmed = models.BooleanField(default=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_reason = models.TextField(blank=True)
    onboarding_step_1 = models.BooleanField(default=True)
    onboarding_step_2 = models.BooleanField(default=False)
    onboarding_step_3 = models.BooleanField(default=True)
    onboarding_step_4 = models.BooleanField(default=True)
    onboarding_completed_at = models.DateTimeField(null=True, blank=True)
    milestone_30_completed = models.BooleanField(default=True)
    milestone_60_completed = models.BooleanField(default=False)
    milestone_90_completed = models.BooleanField(default=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_until = models.DateField(null=True, blank=True)
    appointed_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="issued_appointments",
    )
    decision_reason = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["appointment_code"]
        indexes = [
            models.Index(fields=["network", "country", "stage"]),
        ]

    def __str__(self):
        return f"{self.appointee_name} · {self.position_title} ({self.stage})"


class SeatHistory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seat = models.ForeignKey(LeadershipSeat, on_delete=models.CASCADE, related_name="history_entries")
    person = models.ForeignKey(
        PersonProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="seat_history",
    )
    holder_name = models.CharField(max_length=150)
    position_title = models.CharField(max_length=120)
    unit_name = models.CharField(max_length=150)
    network = models.CharField(max_length=8, default="WGMN")
    country = models.CharField(max_length=8, default="NG")
    outcome_or_stage = models.CharField(max_length=64, default="Former holder")
    service_period = models.CharField(max_length=100, default="2024 – 2026")
    transition_reason = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recorded_seat_histories",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.holder_name} ({self.position_title} · {self.unit_name}) [{self.service_period}]"


class LeadershipReview(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(AppointmentRecord, on_delete=models.CASCADE, related_name="reviews")
    review_point = models.CharField(
        max_length=32,
        default="30 days",
        choices=[("30 days", "30 days"), ("60 days", "60 days"), ("90 days", "90 days")],
    )
    outcome = models.CharField(max_length=64, default="On track")
    evidence_notes = models.TextField(default="Record evidence and agreed support.")
    reviewer_confirmed = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_leadership_reviews",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.appointment.appointee_name} · {self.review_point} ({self.outcome})"


class LeadershipStatusChange(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(AppointmentRecord, on_delete=models.CASCADE, related_name="status_changes")
    requested_status = models.CharField(max_length=48, default="On leave")
    effective_period = models.CharField(max_length=100, default="01–15 October 2026")
    reason_and_cover_plan = models.TextField(default="Record the approved reason and temporary support arrangement.")
    decision_status = models.CharField(
        max_length=32,
        default="Approved",
        choices=[("Pending", "Pending"), ("Approved", "Approved"), ("Rejected", "Rejected")],
    )
    requested_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="requested_status_changes",
    )
    approved_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_status_changes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.appointment.appointee_name} -> {self.requested_status} ({self.effective_period})"


class LeadershipTransitionPlan(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(AppointmentRecord, on_delete=models.CASCADE, related_name="transition_plans")
    outgoing_appointment_label = models.CharField(max_length=150, default="Kemi Bello · LGA Coordinator")
    transition_type = models.CharField(max_length=48, default="Transfer")
    effective_date = models.CharField(max_length=64, default="01 October 2026")
    access_and_handover_notes = models.TextField(
        default="Official records, groups and outstanding actions require review."
    )
    status = models.CharField(
        max_length=32,
        default="In review",
        choices=[("Draft", "Draft"), ("In review", "In review"), ("Completed", "Completed")],
    )
    successor_person = models.ForeignKey(
        PersonProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="incoming_transitions",
    )
    successor_name = models.CharField(max_length=150, blank=True, default="Ada Okafor")
    planned_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="planned_leadership_transitions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.outgoing_appointment_label} ({self.transition_type} · {self.effective_date})"


class HandoverAssetTask(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(
        AppointmentRecord,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="handover_tasks",
    )
    transition_plan = models.ForeignKey(
        LeadershipTransitionPlan,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="handover_tasks",
    )
    asset_or_task = models.CharField(max_length=150)
    from_actor = models.CharField(max_length=150)
    to_actor = models.CharField(max_length=150)
    due_date = models.CharField(max_length=32, default="2026-10-01")
    access_action = models.CharField(max_length=64, default="Transfer ownership")
    status = models.CharField(
        max_length=32,
        default="Open",
        choices=[("Open", "Open"), ("Completed", "Completed")],
    )
    network = models.CharField(max_length=8, default="WGMN")
    country = models.CharField(max_length=8, default="NG")
    completed_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="completed_handover_tasks",
    )
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.asset_or_task} ({self.from_actor} -> {self.to_actor} · {self.access_action})"


# -----------------------------------------------------------------------------
# STAGE 08: RECRUITMENT, REFERRALS, ACTIVATION, AND SELECTION MODELS
# -----------------------------------------------------------------------------


class RecruitmentRouteConfig(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    route_code = models.CharField(max_length=48, unique=True)
    route_name = models.CharField(max_length=120, default="Open call · Activation")
    duration_days = models.PositiveSmallIntegerField(default=7)
    duration_label = models.CharField(max_length=32, default="7 days")
    route_timezone = models.CharField(max_length=64, default="Africa/Lagos")
    content_version = models.CharField(max_length=80, default="Activation pack v2")
    network = models.CharField(max_length=8, default="WGMN")
    country = models.CharField(max_length=8, default="NG")
    status = models.CharField(max_length=32, default="Active")
    proposed_duration_label = models.CharField(max_length=32, blank=True)
    proposed_timezone = models.CharField(max_length=64, blank=True)
    proposed_content_version = models.CharField(max_length=80, blank=True)
    updated_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="updated_recruitment_routes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["route_code"]

    def __str__(self):
        return f"{self.route_name} ({self.duration_label} · {self.content_version})"


class VolunteerOpportunity(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    opportunity_code = models.CharField(max_length=48, unique=True)
    title = models.CharField(max_length=150)
    seat = models.ForeignKey(
        LeadershipSeat,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="volunteer_opportunities",
    )
    unit_name = models.CharField(max_length=150, default="Ikeja")
    network = models.CharField(max_length=8, default="WGMN")
    country = models.CharField(max_length=8, default="NG")
    route_type = models.CharField(max_length=32, default="7-day open call")
    status = models.CharField(max_length=32, default="Open")
    description = models.TextField(
        blank=True,
        default="Open-call recruits complete Activation. Referred candidates review the Leadership Pack.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["opportunity_code"]

    def __str__(self):
        return f"{self.title} ({self.network} / {self.country})"


class ReferralLink(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referral_code = models.CharField(max_length=48, unique=True)
    seat = models.ForeignKey(
        LeadershipSeat,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stage8_referral_links",
    )
    proposed_seat_title = models.CharField(max_length=150, default="Chapter Coordinator · Ikeja")
    person = models.ForeignKey(
        PersonProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stage8_referrals",
    )
    candidate_name = models.CharField(max_length=150, default="Ada Okafor")
    candidate_email = models.EmailField(blank=True)
    network = models.CharField(max_length=8, default="WGMN")
    country = models.CharField(max_length=8, default="NG")
    unit_name = models.CharField(max_length=150, default="Ikeja")
    contact_confirmed = models.BooleanField(default=True)
    status = models.CharField(max_length=32, default="In progress")
    referred_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_referral_links",
    )
    idempotency_key = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["referral_code"]

    def __str__(self):
        return f"{self.referral_code}: {self.candidate_name} -> {self.proposed_seat_title}"


class CandidateApplication(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application_code = models.CharField(max_length=48, unique=True)
    person = models.ForeignKey(
        PersonProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="candidate_applications",
    )
    account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="candidate_applications",
    )
    seat = models.ForeignKey(
        LeadershipSeat,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="candidate_applications",
    )
    opportunity = models.ForeignKey(
        VolunteerOpportunity,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applications",
    )
    referral_link = models.ForeignKey(
        ReferralLink,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="applications",
    )
    candidate_name = models.CharField(max_length=150)
    candidate_email = models.EmailField(blank=True)
    network = models.CharField(max_length=8, default="WGMN")
    country = models.CharField(max_length=8, default="NG")
    unit_name = models.CharField(max_length=150, default="Ikeja")
    seat_label = models.CharField(max_length=150, default="Chapter Coordinator · Ikeja")
    route = models.CharField(max_length=64, default="7-day open call")
    current_stage = models.CharField(max_length=64, default="Day 4 of 7")
    next_action = models.CharField(max_length=64, default="Review evidence")
    experience_notes = models.TextField(default="Describe your community coordination experience.")
    availability = models.CharField(max_length=100, default="Select your availability")
    contact_confirmed = models.BooleanField(default=True)
    activation_day = models.PositiveSmallIntegerField(default=4)
    activation_step_1_done = models.BooleanField(default=True)
    activation_step_2_done = models.BooleanField(default=False)
    activation_step_3_done = models.BooleanField(default=False)
    activation_step_4_done = models.BooleanField(default=False)
    activation_reflection = models.TextField(
        blank=True,
        default="Participated in local chapter coordination and community outreach reflections.",
    )
    pack_day = models.PositiveSmallIntegerField(default=2)
    pack_step_1_done = models.BooleanField(default=True)
    pack_step_2_done = models.BooleanField(default=False)
    pack_step_3_done = models.BooleanField(default=False)
    pack_step_4_done = models.BooleanField(default=False)
    pack_question = models.CharField(
        max_length=255,
        default="How would you raise a concern outside your authority?",
    )
    pack_answer = models.TextField(default="Describe the safe reporting and escalation route.")
    pack_declaration_confirmed = models.BooleanField(default=True)
    deadline_reached = models.BooleanField(default=False)
    reopened_by_reviewer = models.BooleanField(default=False)
    evidence_assessment = models.CharField(max_length=80, default="Request human decision")
    reviewer_notes = models.TextField(default="Record the evidence supporting your recommendation.")
    clarification_requested = models.BooleanField(default=False)
    clarification_note = models.TextField(blank=True)
    recommended_decision = models.CharField(max_length=80, default="Selected — appointment pending")
    decision_status = models.CharField(max_length=80, default="Pending human decision")
    decision_reason = models.TextField(
        default="Explain how the approved criteria and evidence support this choice."
    )
    override_reason = models.TextField(blank=True)
    consequence_confirmed = models.BooleanField(default=False)
    disclosed_outcome = models.CharField(max_length=80, default="An alternative role is available")
    alternative_opportunity_title = models.CharField(
        max_length=150,
        default="Chapter support opportunity",
    )
    alternative_local_scope = models.CharField(max_length=100, default="Ikeja")
    alternative_next_action = models.CharField(max_length=80, default="Review offer")
    candidate_offer_response = models.CharField(max_length=64, blank=True)
    in_reserve_pool = models.BooleanField(default=False)
    reserve_consent = models.BooleanField(default=True)
    decided_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="decided_candidate_applications",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    idempotency_key = models.CharField(max_length=64, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["application_code"]
        indexes = [
            models.Index(fields=["network", "country", "route"]),
            models.Index(fields=["network", "country", "current_stage"]),
        ]

    def __str__(self):
        return f"{self.candidate_name} · {self.route} ({self.current_stage} -> {self.next_action})"


class CandidateRubricScore(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    application = models.ForeignKey(
        CandidateApplication,
        on_delete=models.CASCADE,
        related_name="rubric_scores",
    )
    criterion = models.CharField(max_length=120)
    evidence_status = models.CharField(max_length=64, default="Meets evidence")
    reviewer_note = models.CharField(max_length=255, default="Verified against submitted record")
    required_followup = models.CharField(max_length=80, default="None")
    scored_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="scored_candidate_rubrics",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.application.candidate_name} · {self.criterion} ({self.evidence_status})"


# =============================================================================
# WDOS STAGE 09: TASKS, CALENDAR, AND MEETING ADMINISTRATION MODELS
# =============================================================================

class MeetingSeries(models.Model):
    """
    Stage 09 (MTG-01 through MTG-06):
    Canonical meeting & recurring series record with local timezone awareness,
    RSVP tracking, attendance verification, versioned minutes, and open follow-up actions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting_code = models.CharField(max_length=48, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="Agree the agenda, review national follow-through and assign next actions.")
    agenda = models.TextField(default="Country updates, reporting follow-through and support needs.")
    network = models.CharField(max_length=16, default="WGMN", db_index=True)
    country = models.CharField(max_length=8, default="NG", db_index=True)
    scope_label = models.CharField(max_length=160, default="WGMN · Nigeria")
    unit_name = models.CharField(max_length=160, default="WGMN · Nigeria country team")
    host_name = models.CharField(max_length=160, default="Ada Okafor")
    host_account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="hosted_meeting_series",
    )
    local_time_label = models.CharField(max_length=80, default="18 Sep · 10:00 WAT")
    full_start_time_label = models.CharField(max_length=120, default="18 September 2026 · 10:00")
    scheduled_at = models.DateTimeField(null=True, blank=True)
    timezone_name = models.CharField(max_length=80, default="Africa/Lagos (WAT)")
    invitees_label = models.CharField(max_length=200, default="WGMN · Nigeria country team")
    repeats_frequency = models.CharField(max_length=48, default="Weekly")
    ends_date_label = models.CharField(max_length=64, default="31 December 2026")
    next_occurrence_label = models.CharField(max_length=80, default="18 October 2026 · 10:00 WAT")
    edit_scope = models.CharField(max_length=80, default="Edit this and future meetings")
    cancellation_status = models.CharField(max_length=80, default="Keep series active")
    missed_occurrence_note = models.TextField(blank=True, default="")
    status = models.CharField(max_length=64, default="Attending", db_index=True)
    attendance_summary = models.CharField(max_length=80, default="4 of 5 present")
    minutes_version = models.CharField(max_length=48, default="v2 · reviewed")
    minutes_draft_label = models.CharField(max_length=48, default="v2 · draft")
    minutes_status = models.CharField(max_length=48, default="Reviewed")
    minutes_text = models.TextField(
        blank=True,
        default="Confirm monthly follow-up plan, leadership vacancy follow-up, and upload of corrected activity evidence.",
    )
    minutes_frozen = models.BooleanField(default=False)
    open_actions_label = models.CharField(max_length=48, default="3 open")
    invitation_delivery_state = models.CharField(max_length=48, default="Delivered")
    failed_recipient_count = models.PositiveSmallIntegerField(default=0)
    linked_scheduled_meeting = models.ForeignKey(
        ScheduledMeeting,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stage9_series",
    )
    idempotency_key = models.CharField(max_length=128, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["meeting_code"]

    @property
    def has_online_room(self) -> bool:
        sm = self.linked_scheduled_meeting
        if sm and sm.location and sm.location.startswith("In-Person ·"):
            return False
        return True

    @property
    def meeting_format_label(self) -> str:
        sm = self.linked_scheduled_meeting
        if sm and sm.location:
            if sm.location.startswith("In-Person ·"):
                return "In-Person"
            if sm.location.startswith("Hybrid ·"):
                return "Hybrid"
        return "Online"

    @property
    def venue_label(self) -> str:
        sm = self.linked_scheduled_meeting
        if sm and sm.location:
            clean_loc = (
                sm.location.replace(" · Public Link", "")
                .replace(" · WDOS Only", "")
                .replace(" · Bypass Lobby", "")
                .replace(" · Wait in Lobby", "")
            )
            if clean_loc.startswith("In-Person ·"):
                return clean_loc.replace("In-Person ·", "").strip() or self.unit_name
            if clean_loc.startswith("Hybrid ·"):
                return clean_loc.replace("Hybrid ·", "").strip() or f"{self.unit_name} + Online Room"
            return clean_loc
        return "Online Meeting Room"

    @property
    def allow_guest_access(self) -> bool:
        if not self.has_online_room:
            return False
        sm = self.linked_scheduled_meeting
        if sm and sm.location and "Public Link" in sm.location:
            return True
        room = self.room_sessions.first()
        if room and room.allow_guest_access:
            return True
        return False

    @property
    def access_policy_label(self) -> str:
        return "Anyone with the link" if self.allow_guest_access else "WDOS accounts only"

    @property
    def bypass_lobby(self) -> bool:
        if not self.has_online_room:
            return False
        room = self.room_sessions.first()
        if room and room.provider_session_id and "lobby:" in room.provider_session_id:
            return "lobby:bypass" in room.provider_session_id
        sm = self.linked_scheduled_meeting
        if sm and sm.location and "Bypass Lobby" in sm.location:
            return True
        if room and room.bypass_lobby:
            return True
        return False

    @property
    def lobby_policy_label(self) -> str:
        return "Bypass lobby" if self.bypass_lobby else "Wait in lobby"

    def __str__(self):
        return f"{self.meeting_code}: {self.title} ({self.local_time_label})"


class MissionControlTask(models.Model):
    """
    Stage 09 (TASK-01 through TASK-04):
    Mission Control task record with linked work queue synchronization,
    scoped board placement, and full lifecycle states:
    Not started -> In progress -> Submitted -> Reviewed -> Verified -> Closed
    plus Returned for correction, Reopened, Blocked, Overdue, Escalated.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task_code = models.CharField(max_length=48, unique=True, db_index=True)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    network = models.CharField(max_length=16, default="WGMN", db_index=True)
    country = models.CharField(max_length=8, default="NG", db_index=True)
    unit_name = models.CharField(max_length=160, default="Lagos Central Chapter")
    owner_person = models.ForeignKey(
        PersonProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mission_control_tasks",
    )
    owner_account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="assigned_mission_control_tasks",
    )
    owner_name = models.CharField(max_length=160, default="Ada Okafor")
    assigned_by_account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_mission_control_tasks",
    )
    assigned_by_name = models.CharField(max_length=160, default="Lina Mensah")
    reviewer_name = models.CharField(max_length=160, default="Assigned reviewer")
    reviewer_account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reviewed_mission_control_tasks",
    )
    board_column = models.CharField(max_length=32, default="To do", db_index=True)
    status = models.CharField(max_length=48, default="In progress", db_index=True)
    priority = models.CharField(max_length=24, default="High")
    due_date_label = models.CharField(max_length=64, default="18 September 2026")
    due_short_label = models.CharField(max_length=32, default="18 Sep")
    due_date = models.DateField(null=True, blank=True)
    next_action = models.CharField(max_length=120, default="Submit evidence")
    required_evidence = models.TextField(default="Attach the agreed agenda and note any unresolved questions.")
    evidence_file = models.CharField(max_length=200, blank=True, default="chapter-agenda-v2.pdf")
    evidence_checked = models.BooleanField(default=False)
    current_version = models.PositiveIntegerField(default=2)
    blocker_reason = models.TextField(blank=True, default="")
    return_or_reopen_reason = models.TextField(blank=True, default="")
    escalation_note = models.TextField(blank=True, default="")
    escalated_to = models.CharField(max_length=160, blank=True, default="")
    source_type = models.CharField(max_length=64, default="Mission Control")
    source_reference = models.CharField(max_length=160, blank=True, default="")
    source_meeting = models.ForeignKey(
        MeetingSeries,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="linked_tasks",
    )
    linked_work_item = models.ForeignKey(
        WorkItem,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mission_control_tasks",
    )
    idempotency_key = models.CharField(max_length=128, null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["task_code"]

    def __str__(self):
        return f"{self.task_code}: {self.title} ({self.status})"


class TaskLifecycleEntry(models.Model):
    """
    Stage 09 (TASK-03-LIFECYCLE & TASK-04):
    Immutable audit & lifecycle trail for a MissionControlTask across
    Not Started, In Progress, Submitted, Reviewed, Verified, Closed,
    Returned for correction, Reopened, Blocked, and Escalated steps.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    task = models.ForeignKey(
        MissionControlTask,
        on_delete=models.CASCADE,
        related_name="lifecycle_entries",
    )
    step_order = models.PositiveSmallIntegerField(default=1)
    step_name = models.CharField(max_length=80)
    actor_or_evidence = models.CharField(max_length=200)
    result_label = models.CharField(max_length=160)
    version_number = models.PositiveIntegerField(default=1)
    reason_note = models.TextField(blank=True, default="")
    actor_account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="task_lifecycle_entries",
    )
    is_canonical_step = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["step_order", "created_at"]

    def __str__(self):
        return f"{self.task.task_code} · {self.step_name} ({self.result_label})"


class MeetingParticipantRecord(models.Model):
    """
    Stage 09 (MTG-04, MTG-05-RECORD, MTG-06):
    Individual participant RSVP, verified attendance, attendance correction audit,
    and recoverable invitation/reminder delivery status.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(
        MeetingSeries,
        on_delete=models.CASCADE,
        related_name="participant_records",
    )
    person = models.ForeignKey(
        PersonProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="meeting_participations",
    )
    account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stage9_meeting_participations",
    )
    participant_name = models.CharField(max_length=160)
    role_or_title = models.CharField(max_length=120, default="Chapter Lead")
    rsvp_status = models.CharField(max_length=32, default="Attending")
    attendance_status = models.CharField(max_length=32, default="Present")
    previous_attendance_value = models.CharField(max_length=80, blank=True, default="")
    detail_note = models.CharField(max_length=200, default="Host-verified")
    correction_reason = models.TextField(blank=True, default="")
    correction_review_outcome = models.CharField(max_length=80, blank=True, default="")
    corrected_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="attendance_corrections_made",
    )
    corrected_at = models.DateTimeField(null=True, blank=True)
    invitation_delivery_status = models.CharField(max_length=32, default="delivered")
    reminder_delivery_status = models.CharField(max_length=32, default="delivered")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.meeting.meeting_code} · {self.participant_name} ({self.attendance_status})"


class MeetingDecisionAction(models.Model):
    """
    Stage 09 (MTG-05, MTG-05-RECORD):
    Recorded meeting decisions and follow-up action items that can be converted
    into linked MissionControlTask records (idempotently once per action).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    meeting = models.ForeignKey(
        MeetingSeries,
        on_delete=models.CASCADE,
        related_name="decisions_and_actions",
    )
    record_code = models.CharField(max_length=48)
    record_type = models.CharField(max_length=24, default="Action")
    owner_label = models.CharField(max_length=160)
    owner_person = models.ForeignKey(
        PersonProfile,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="meeting_actions",
    )
    deadline_or_version = models.CharField(max_length=80)
    detail_text = models.CharField(max_length=255)
    converted_task = models.ForeignKey(
        MissionControlTask,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="source_meeting_actions",
    )
    is_converted = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="created_meeting_decisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["record_code", "created_at"]

    def __str__(self):
        return f"{self.meeting.meeting_code} · {self.record_code}: {self.detail_text}"


# =============================================================================
# WDOS STAGE 10: MULTILINGUA MEETING, TRANSLATION, AND LARGE EVENTS MODELS
# =============================================================================

class MeetingRoomSession(models.Model):
    """
    Stage 10 (ROOM-01 through ROOM-08):
    Tracks the real-time state of a WDOS Multilingua Room, linking to both
    ScheduledMeeting and Stage 09 MeetingSeries for end-to-end continuity.
    """
    STATUS_CHOICES = [
        ("INITIALIZING", "Initializing Room"),
        ("WAITING", "Waiting for Host"),
        ("LIVE", "Live in Progress"),
        ("COMPLETED", "Session Completed"),
        ("TERMINATED", "Terminated / Closed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room_code = models.CharField(max_length=48, unique=True, db_index=True, blank=True, default="")
    scheduled_meeting = models.OneToOneField(
        ScheduledMeeting,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="room_session",
    )
    meeting_series = models.ForeignKey(
        MeetingSeries,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="room_sessions",
    )
    session_name = models.CharField(max_length=128, unique=True, db_index=True)
    title = models.CharField(max_length=200, default="Country coordination")
    network = models.CharField(max_length=16, default="WGMN", db_index=True)
    country = models.CharField(max_length=8, default="NG", db_index=True)
    scope_label = models.CharField(max_length=160, default="Country coordination · WGMN Nigeria")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="WAITING")
    active_host_profile = models.ForeignKey(
        "PersonProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hosted_rooms",
    )
    host_name = models.CharField(max_length=160, default="Ada Okafor")
    active_speaker_name = models.CharField(max_length=160, default="Ada Okafor")
    active_speaker_role = models.CharField(max_length=160, default="Country coordinator · speaking in English")

    # Provider Metadata
    video_provider = models.CharField(max_length=32, default="zoom")
    translation_provider = models.CharField(max_length=32, default="azure")
    provider_session_id = models.CharField(max_length=255, blank=True, null=True)

    # Timestamps
    opened_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.session_name:
            self.session_name = f"wdos-room-{str(self.id or uuid.uuid4())[:12]}"
        if not self.room_code:
            self.room_code = f"ROOM-{self.country or 'NG'}-{str(self.id or uuid.uuid4())[:6].upper()}"
        if self.scheduled_meeting_id and self.scheduled_meeting:
            if not self.title or self.title == "Country coordination":
                self.title = self.scheduled_meeting.title
            if self.scheduled_meeting.network in ("WGMN", "WNNN"):
                self.network = self.scheduled_meeting.network
            if self.scheduled_meeting.country and self.scheduled_meeting.country != "ALL":
                self.country = self.scheduled_meeting.country
        super().save(*args, **kwargs)

    def is_live(self) -> bool:
        return self.status == "LIVE"

    @property
    def allow_guest_access(self) -> bool:
        if self.provider_session_id and "anyone_with_link" in self.provider_session_id:
            return True
        if self.scheduled_meeting_id and self.scheduled_meeting and self.scheduled_meeting.location:
            if "Public Link" in self.scheduled_meeting.location:
                return True
        return False

    @property
    def access_policy_label(self) -> str:
        return "Anyone with the link" if self.allow_guest_access else "WDOS accounts only"

    @property
    def bypass_lobby(self) -> bool:
        if self.provider_session_id and "lobby:" in self.provider_session_id:
            return "lobby:bypass" in self.provider_session_id
        if self.scheduled_meeting_id and self.scheduled_meeting and self.scheduled_meeting.location:
            if "Bypass Lobby" in self.scheduled_meeting.location:
                return True
        return False

    @property
    def lobby_policy_label(self) -> str:
        return "Bypass lobby" if self.bypass_lobby else "Wait in lobby"

    def __str__(self):
        return f"{self.room_code}: {self.title} ({self.status})"


class RoomParticipantSession(models.Model):
    """
    Stage 10 (ROOM-01 through ROOM-07):
    Tracks individual participant admission, floor permissions, language lanes,
    and real-time audio/network telemetry inside a MeetingRoomSession.
    """
    ADMISSION_CHOICES = [
        ("WAITING_ROOM", "In Waiting Room"),
        ("ADMITTED", "Admitted to Room"),
        ("DENIED", "Denied Entry"),
        ("LEFT", "Left Voluntarily"),
        ("REMOVED", "Removed by Host"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room_session = models.ForeignKey(
        MeetingRoomSession,
        on_delete=models.CASCADE,
        related_name="participants",
    )
    person_profile = models.ForeignKey(
        "PersonProfile",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="room_participations",
    )
    account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="room_participations",
    )
    participant_name = models.CharField(max_length=160, default="Ada Okafor")
    meeting_role = models.CharField(max_length=48, default="Listener")
    admission_status = models.CharField(max_length=20, choices=ADMISSION_CHOICES, default="WAITING_ROOM")

    # Language & Audio Preferences (ROOM-01, ROOM-06)
    speaking_language = models.CharField(max_length=16, default="en-US")
    listening_language = models.CharField(max_length=16, default="fr-FR")
    caption_language = models.CharField(max_length=32, default="French")
    audio_input_device = models.CharField(max_length=120, default="Default microphone · test input")
    audio_output_device = models.CharField(max_length=120, default="Headphones")
    show_translated_captions = models.BooleanField(default=True)

    # Floor & Media Permissions (ROOM-03, ROOM-04, ROOM-05)
    is_speaker = models.BooleanField(default=False)
    is_muted = models.BooleanField(default=True)
    has_video = models.BooleanField(default=False)
    hand_raised = models.BooleanField(default=False)
    connection_status = models.CharField(max_length=48, default="Connected")

    # Telemetry & Diagnostics (ROOM-07, ROOM-08)
    latency_ms = models.IntegerField(default=42)
    packet_loss_pct = models.FloatField(default=0.0)
    audio_degraded = models.BooleanField(default=False)

    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["joined_at", "participant_name"]

    def save(self, *args, **kwargs):
        if self.person_profile_id and self.person_profile and (not self.participant_name or self.participant_name == "Ada Okafor"):
            self.participant_name = self.person_profile.full_name
        super().save(*args, **kwargs)

    @property
    def speaking_language_display(self) -> str:
        mapping = {
            "en-US": "English",
            "fr-FR": "French",
            "pt-BR": "Portuguese",
            "ar-EG": "Arabic",
            "sw-KE": "Swahili",
            "ha-NG": "Hausa",
            "yo-NG": "Yoruba",
            "ig-NG": "Igbo",
        }
        return mapping.get(self.speaking_language, self.speaking_language)

    @property
    def listening_language_display(self) -> str:
        mapping = {
            "en-US": "English",
            "fr-FR": "French",
            "pt-BR": "Portuguese",
            "ar-EG": "Arabic",
            "sw-KE": "Swahili",
            "ha-NG": "Hausa",
            "yo-NG": "Yoruba",
            "ig-NG": "Igbo",
        }
        return mapping.get(self.listening_language, self.listening_language)

    def __str__(self):
        return f"{self.participant_name} ({self.meeting_role} · {self.admission_status})"


class LiveTranscriptSegment(models.Model):
    """
    Stage 10 (ROOM-03, ROOM-04, MTG-05 Bridge):
    Stores real-time speech-to-text and translated segments so late joiners see
    context and MTG-05 (Minutes & Decisions) is automatically populated at session end.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room_session = models.ForeignKey(
        MeetingRoomSession,
        on_delete=models.CASCADE,
        related_name="transcript_segments",
    )
    speaker_profile = models.ForeignKey(
        "PersonProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    speaker_name = models.CharField(max_length=150)
    original_language = models.CharField(max_length=16, default="en-US")
    original_text = models.TextField()
    translations = models.JSONField(default=dict)  # e.g., {"fr": "Bonjour...", "pt": "Olá..."}
    timestamp = models.DateTimeField(auto_now_add=True)
    sequence_number = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ["sequence_number", "timestamp"]

    def __str__(self):
        return f"#{self.sequence_number} {self.speaker_name}: {self.original_text[:48]}"


class RoomDiagnosticLane(models.Model):
    """
    Stage 10 (ROOM-08):
    Tracks speech input, translation, and voice output lane evidence and verification state.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    room_session = models.ForeignKey(
        MeetingRoomSession,
        on_delete=models.CASCADE,
        related_name="diagnostic_lanes",
    )
    lane_name = models.CharField(max_length=80)
    language_label = models.CharField(max_length=80)
    evidence_summary = models.CharField(max_length=200)
    state_label = models.CharField(max_length=48, default="Review")
    latency_ms = models.PositiveIntegerField(default=42)
    packet_loss_pct = models.FloatField(default=0.0)
    notes = models.TextField(blank=True, default="")
    sort_order = models.PositiveSmallIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["sort_order", "lane_name"]

    def __str__(self):
        return f"{self.lane_name} ({self.language_label}): {self.state_label}"


class ConferenceEvent(models.Model):
    """
    Stage 10 (EVENT-01 through EVENT-10):
    Canonical conference and large-event record supporting multi-track plenary broadcasts,
    controlled breakouts, Q&A moderation, post-event reflections, and live ops monitoring.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_code = models.CharField(max_length=48, unique=True, db_index=True)
    title = models.CharField(max_length=200, default="WODDI leadership gathering")
    eyebrow = models.CharField(max_length=120, default="WODDI / ELIGIBLE ATTENDEES")
    subtitle = models.TextField(
        default="Review the event schedule, confirm your registration, and join assigned plenary or breakout rooms."
    )
    network = models.CharField(max_length=16, default="WGMN", db_index=True)
    country = models.CharField(max_length=8, default="NG", db_index=True)
    date_and_timezone = models.CharField(max_length=120, default="20 October 2026 · Africa/Lagos")
    eligibility_label = models.CharField(max_length=160, default="Approved member and leader audience")
    session_model = models.CharField(max_length=160, default="Plenary broadcast with controlled breakouts")
    checked_in_count = models.PositiveIntegerField(default=248)
    live_sessions_count = models.PositiveIntegerField(default=3)
    support_requests_count = models.PositiveIntegerField(default=4)
    status = models.CharField(max_length=48, default="In progress")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event_code"]

    def __str__(self):
        return f"{self.event_code}: {self.title}"


class EventSessionTrack(models.Model):
    """
    Stage 10 (EVENT-01, EVENT-03, EVENT-04, EVENT-05, EVENT-06, EVENT-08, EVENT-10):
    Individual plenary, breakout, or panel session track within a ConferenceEvent.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        ConferenceEvent,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    session_code = models.CharField(max_length=48, db_index=True)
    title = models.CharField(max_length=200)
    local_time_label = models.CharField(max_length=80)
    format_label = models.CharField(max_length=80)
    access_status = models.CharField(max_length=80, default="Registered")
    description = models.TextField(default="Country updates, shared reflections and practical guidance.")
    is_plenary = models.BooleanField(default=False)
    is_breakout = models.BooleanField(default=False)
    linked_room_session = models.ForeignKey(
        MeetingRoomSession,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="event_tracks",
    )
    resource_title = models.CharField(max_length=200, blank=True, default="")
    sort_order = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ["sort_order", "session_code"]

    def __str__(self):
        return f"{self.event.event_code} · {self.title} ({self.local_time_label})"


class EventRegistration(models.Model):
    """
    Stage 10 (EVENT-02, EVENT-03, EVENT-04, EVENT-06, EVENT-08):
    Attendee registration, language & access support preferences, selected breakout room,
    and post-event reflection/feedback record.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        ConferenceEvent,
        on_delete=models.CASCADE,
        related_name="registrations",
    )
    account = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="event_registrations",
    )
    person_profile = models.ForeignKey(
        "PersonProfile",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="event_registrations",
    )
    attendee_name = models.CharField(max_length=160, default="Ada Okafor")
    network = models.CharField(max_length=16, default="WGMN")
    country = models.CharField(max_length=8, default="NG")
    listening_language = models.CharField(max_length=48, default="English")
    access_support = models.TextField(blank=True, default="Tell us about any support you may need.")
    selected_breakout = models.CharField(max_length=160, blank=True, default="Country conversations")
    registration_status = models.CharField(max_length=48, default="Confirmed")
    checked_in = models.BooleanField(default=True)
    reflection_text = models.TextField(blank=True, default="")
    feedback_rating = models.CharField(max_length=48, blank=True, default="Helpful")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.attendee_name} -> {self.event.title} ({self.registration_status})"


class EventModerationQuestion(models.Model):
    """
    Stage 10 (EVENT-05, EVENT-07):
    Audience Q&A submission and host/moderator approval queue.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        ConferenceEvent,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    session_track = models.ForeignKey(
        EventSessionTrack,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="questions",
    )
    author_name = models.CharField(max_length=160, default="Ada Okafor")
    author_role = models.CharField(max_length=120, default="Chapter Lead")
    question_text = models.TextField()
    host_reply = models.TextField(blank=True, default="")
    moderation_state = models.CharField(max_length=32, default="Pending")
    reviewed_by = models.ForeignKey(
        "accounts.Account",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="moderated_event_questions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"[{self.moderation_state}] {self.author_name}: {self.question_text[:48]}"


def _resolve_user_person_profile(user_obj):
    if not user_obj or not getattr(user_obj, "is_authenticated", False):
        return None
    direct = PersonProfile.objects.filter(user=user_obj).first()
    if direct:
        return direct
    from accounts.models import Account
    acc = Account.objects.filter(user=user_obj).first()
    if acc:
        return PersonProfile.objects.filter(account=acc).first()
    return None


from django.contrib.auth import get_user_model as _get_user_model
_UserModel = _get_user_model()
if not hasattr(_UserModel, "person_profile"):
    _UserModel.add_to_class("person_profile", property(_resolve_user_person_profile))






