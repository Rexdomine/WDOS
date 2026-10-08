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

