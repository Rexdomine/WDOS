import uuid
from django.db import models


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
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    location = models.CharField(max_length=255, blank=True)
    attendees_count = models.PositiveIntegerField(default=0)
    target_role = models.CharField(max_length=48, default="all")
    organizer_name = models.CharField(max_length=150, blank=True)
    rsvp_accounts = models.ManyToManyField("accounts.Account", blank=True, related_name="rsvpd_meetings")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_at"]
        indexes = [
            models.Index(fields=["network", "country", "scheduled_at"]),
        ]

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
    contact_verification = models.CharField(max_length=32, default="Verified", choices=[("Verified", "Verified"), ("Pending", "Pending"), ("Unverified", "Unverified")])
    primary_relationship = models.CharField(max_length=100, default="Member")
    status = models.CharField(max_length=32, default="Active", choices=[("Active", "Active"), ("Review due", "Review due"), ("Inactive", "Inactive")])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

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


