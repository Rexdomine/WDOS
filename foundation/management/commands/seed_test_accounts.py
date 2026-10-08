"""
Management command to seed test accounts for local development and Render staging.

Creates 7 distinct test personas covering all roles, network scopes, and geographic hubs:
1. member.ada@example.org (Member Ada Okafor - WGMN Nigeria, 1-step login, No MFA)
2. wnnn.member@example.org (Member Efua Mensah - WNNN Ghana, 1-step login, No MFA)
3. chapter.lagos@example.org (Chapter Lead Adaeze Okonkwo - WGMN Lagos)
4. country.ng@example.org (Country Lead Dr. Aisha Bello - Nigeria Hub)
5. ops@example.org (Chief Operations Lead - Global Operations)
6. founder@example.org (Founder & Exec Director - Global Oversight & Privacy Reviewer)
7. candidate.john@example.org (Candidate John Kalu - Pending Verification)

Standard Password: WDOSPassphrase2026!
For privileged roles requiring 2FA:
- Pre-configured TOTP secret: JBSWY3DPEHPK3PXP
- Static backup recovery code: 12345678 (instantly accepts in 2FA prompt)
"""
import pyotp
import time
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import (
    AccessGrant,
    Account,
    Membership,
    OnboardingConsent,
    OnboardingDraft,
    Person,
    RecoveryCode,
)
from accounts.services import digest, encrypt
from foundation.models import (
    Chapter,
    CountryHub,
    DashboardAlert,
    DeviceSession,
    NetworkTransition,
    Notification,
    PrivacyRequest,
    Role,
    UserPreference,
    WorkItem,
)

User = get_user_model()

DEFAULT_PASSWORD = "WDOSPassphrase2026!"
DEFAULT_TOTP_SECRET = "JBSWY3DPEHPK3PXP"
DEFAULT_BACKUP_CODE = "12345678"


class Command(BaseCommand):
    help = "Seed test accounts with realistic credentials, scopes, and fixtures for local and staging."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=DEFAULT_PASSWORD,
            help=f"Default password for all test accounts (default: {DEFAULT_PASSWORD})",
        )
        parser.add_argument(
            "--totp-secret",
            default=DEFAULT_TOTP_SECRET,
            help=f"Base32 TOTP secret for privileged test accounts (default: {DEFAULT_TOTP_SECRET})",
        )

    def handle(self, *args, **options):
        password = options["password"]
        totp_secret = options["totp_secret"].strip().replace(" ", "").upper()
        now = timezone.now()

        self.stdout.write(self.style.NOTICE("Ensuring foundational roles and shell data exist..."))
        call_command("seed_roles", stdout=self.stdout)
        call_command("seed_shell_data", stdout=self.stdout)
        call_command("seed_dashboards", stdout=self.stdout)

        def setup_account(
            email,
            display_name,
            is_staff=False,
            is_superuser=False,
            with_mfa=False,
            backup_code=None,
            network="WGMN",
            country="NG",
            chapter_code="NG-LOS-01",
            chapter_name="Lagos Central Chapter",
            role_grant=None,
            grant_geography="*",
            grant_function="all",
            draft_state="accepted",
        ):
            username = email.split("@")[0]
            # 1. Django User & Account resolution
            acc = Account.objects.filter(email=email).first()
            if acc:
                u = acc.user
            else:
                # Find or create user dedicated to this email
                u = User.objects.filter(email=email).first()
                if u and hasattr(u, "account") and u.account.email != email:
                    u = None
                if not u:
                    u = User.objects.filter(username=username).first()
                    if u and hasattr(u, "account") and u.account.email != email:
                        u = None
                if not u:
                    candidate_uname = username
                    counter = 1
                    while User.objects.filter(username=candidate_uname).exists():
                        candidate_uname = f"{username}_{counter}"
                        counter += 1
                    u = User.objects.create(
                        username=candidate_uname,
                        email=email,
                        first_name=display_name,
                        is_staff=is_staff,
                        is_superuser=is_superuser,
                        is_active=True,
                    )

            u.email = email
            u.first_name = display_name
            u.is_staff = is_staff
            u.is_superuser = is_superuser
            u.is_active = True
            u.set_password(password)
            u.save()

            # 2. Account & Person
            if not acc:
                p = Person.objects.create(display_name=display_name)
                acc = Account.objects.create(
                    user=u,
                    email=email,
                    display_name=display_name,
                    person=p,
                    status="active",
                    verified_at=now,
                )
            else:
                acc.user = u
                acc.email = email
                acc.display_name = display_name
                acc.status = "active"
                if not acc.verified_at:
                    acc.verified_at = now
                if not acc.person:
                    acc.person = Person.objects.create(display_name=display_name)
                else:
                    acc.person.display_name = display_name
                    acc.person.save()
                acc.save()
            p = acc.person

            if with_mfa:
                acc.mfa_secret = encrypt(totp_secret)
                acc.mfa_pending_secret = ""
                acc.mfa_pending_until = None
                acc.security_version += 1
                acc.save()

                # Add deterministic backup recovery code for instant staging login
                RecoveryCode.objects.filter(account=acc).delete()
                if backup_code:
                    RecoveryCode.objects.create(account=acc, digest=digest(backup_code), used_at=None)
            else:
                acc.mfa_secret = ""
                acc.mfa_pending_secret = ""
                acc.mfa_pending_until = None
                acc.save()
                RecoveryCode.objects.filter(account=acc).delete()

            # 3. Onboarding Draft & Consent & Membership
            draft = OnboardingDraft.objects.filter(account=acc).first()
            if not draft:
                draft = OnboardingDraft.objects.create(
                    account=acc,
                    state=draft_state,
                    next_step=8 if draft_state == "accepted" else 6,
                    data={"network": network, "country": country, "language": "en"},
                )
            else:
                draft.state = draft_state
                draft.data = {"network": network, "country": country, "language": "en"}
                draft.save()

            consent = OnboardingConsent.objects.filter(draft=draft).first()
            if not consent:
                consent = OnboardingConsent.objects.create(
                    draft=draft,
                    revision=1,
                    version="1.0",
                    notice="Standard Privacy Notice",
                    digest="consent_digest",
                    approval_reference=f"REF-{email.split('@')[0].upper()}",
                    privacy_ack=True,
                    channel="web",
                )

            if draft_state == "accepted":
                Membership.objects.update_or_create(
                    draft=draft,
                    defaults={
                        "person": p,
                        "network": network,
                        "home": {
                            "code": chapter_code,
                            "country": country,
                            "label": chapter_name,
                        },
                        "consent": consent,
                        "policy_digest": "policy_digest_active",
                        "approved_by": acc,
                    },
                )

            # 4. Access Grant (if role is privileged)
            if role_grant:
                AccessGrant.objects.update_or_create(
                    account=acc,
                    role=role_grant,
                    defaults={
                        "network": network if network != "ALL" else "*",
                        "geography": grant_geography,
                        "function": grant_function,
                        "expires_at": now + timedelta(days=365),
                        "revoked_at": None,
                    },
                )
            else:
                # Remove stale grants if non-privileged
                AccessGrant.objects.filter(account=acc).delete()

            # 5. User Preferences
            UserPreference.objects.update_or_create(
                account=acc,
                defaults={
                    "language": "en",
                    "font_size": "standard",
                    "high_contrast": False,
                    "reduced_motion": False,
                    "active_network": network,
                    "active_country": country,
                    "reminder_preference": "inside_wdos",
                },
            )

            # 6. Device Session (Current Device)
            DeviceSession.objects.update_or_create(
                account=acc,
                device_name="Current Testing Browser",
                defaults={
                    "browser_info": "Chrome / Edge · Lagos Hub",
                    "ip_address": "127.0.0.1",
                    "is_current": True,
                },
            )

            return acc

        # =====================================================================
        # Provision the 7 Core Test Accounts
        # =====================================================================
        self.stdout.write(self.style.NOTICE("\nProvisioning test accounts..."))

        # 1. Everyday Member (Ada Okafor) - WGMN / Nigeria
        acc_ada = setup_account(
            email="member.ada@example.org",
            display_name="Ada Okafor",
            is_staff=False,
            is_superuser=False,
            with_mfa=False,  # 1-step login!
            network="WGMN",
            country="NG",
            chapter_code="NG-LOS-01",
            chapter_name="Lagos Central Chapter",
            role_grant=None,
        )

        # Also link member.ada alias if user logs in with ada@example.org
        setup_account(
            email="ada@example.org",
            display_name="Ada Okafor",
            is_staff=False,
            is_superuser=False,
            with_mfa=False,
            network="WGMN",
            country="NG",
            chapter_code="NG-LOS-01",
            chapter_name="Lagos Central Chapter",
            role_grant=None,
        )

        # 2. WNNN Member (Efua Mensah) - WNNN / Ghana
        acc_wnnn = setup_account(
            email="wnnn.member@example.org",
            display_name="Efua Mensah",
            is_staff=False,
            is_superuser=False,
            with_mfa=False,  # 1-step login!
            network="WNNN",
            country="GH",
            chapter_code="GH-ACC-01",
            chapter_name="Accra Next-Gen Hub",
            role_grant=None,
        )

        # Also provision wnnn_member alias if user enters underscore
        setup_account(
            email="wnnn_member@example.org",
            display_name="Efua Mensah",
            is_staff=False,
            is_superuser=False,
            with_mfa=False,
            network="WNNN",
            country="GH",
            chapter_code="GH-ACC-01",
            chapter_name="Accra Next-Gen Hub",
            role_grant=None,
        )

        # 3. Chapter Lead (Adaeze Okonkwo) - Lagos
        acc_chapter = setup_account(
            email="chapter.lagos@example.org",
            display_name="Adaeze Okonkwo (Lagos Lead)",
            is_staff=False,
            is_superuser=False,
            with_mfa=True,
            backup_code="11112222",
            network="WGMN",
            country="NG",
            chapter_code="NG-LOS-01",
            chapter_name="Lagos Central Chapter",
            role_grant="chapter_lead",
            grant_geography="NG-LOS-01",
            grant_function="chapter",
        )

        # 4. Country Director / Lead (Dr. Aisha Bello) - Nigeria
        acc_country = setup_account(
            email="country.ng@example.org",
            display_name="Dr. Aisha Bello (Nigeria Lead)",
            is_staff=False,
            is_superuser=False,
            with_mfa=True,
            backup_code="33334444",
            network="WGMN",
            country="NG",
            chapter_code="NG-LOS-01",
            chapter_name="Lagos Central Chapter",
            role_grant="country_lead",
            grant_geography="NG",
            grant_function="all",
        )

        # 5. Chief Operations Lead - Global Operations
        acc_ops = setup_account(
            email="ops@example.org",
            display_name="Chief Operations Lead",
            is_staff=True,
            is_superuser=False,
            with_mfa=True,
            backup_code="55556666",
            network="WGMN",
            country="NG",
            chapter_code="NG-LOS-01",
            chapter_name="Lagos Central Chapter",
            role_grant="operations",
            grant_geography="*",
            grant_function="all",
        )

        # 6. Founder & Executive Director - Global Governance & Privacy Reviewer
        acc_founder = setup_account(
            email="founder@example.org",
            display_name="Founder & Executive Director",
            is_staff=True,
            is_superuser=True,
            with_mfa=True,
            backup_code="77778888",
            network="WGMN",
            country="NG",
            chapter_code="NG-LOS-01",
            chapter_name="Lagos Central Chapter",
            role_grant="founder",
            grant_geography="*",
            grant_function="all",
        )

        # 7. Candidate (John Kalu) - Pending Application Review
        acc_candidate = setup_account(
            email="candidate.john@example.org",
            display_name="John Kalu",
            is_staff=False,
            is_superuser=False,
            with_mfa=False,
            network="WGMN",
            country="NG",
            draft_state="review_needed",
            role_grant="candidate",
            grant_geography="NG",
        )

        # =====================================================================
        # Seed Notifications
        # =====================================================================
        for acc, net, ctry, notifs in [
            (
                acc_ada,
                "WGMN",
                "NG",
                [
                    ("Welcome to WDOS Workspace", "Your WGMN Nigeria membership has been verified.", "work_queue", False, "/foundation/"),
                    ("Upcoming Chapter Fellowship", "Lagos Central Chapter meets on Thursday at 10:00 WAT.", "activity", False, "/foundation/#meetings"),
                    ("Security Checkup Passed", "Your account security status is healthy.", "security", True, "/foundation/account/security/"),
                ],
            ),
            (
                acc_wnnn,
                "WNNN",
                "GH",
                [
                    ("Transition to WGMN In Review", "Your network transition from WNNN to WGMN is being processed.", "privacy", False, "/foundation/network-transition/"),
                    ("Digital Skills Bootcamp RSVP Confirmed", "You are registered for Accra Youth Tech Chapter.", "activity", True, "/foundation/#meetings"),
                ],
            ),
            (
                acc_founder,
                "WGMN",
                "NG",
                [
                    ("Pending Privacy Request Review", "Privacy Request #PR-2026-081 requires officer determination.", "privacy", False, "/foundation/privacy-requests/review/"),
                    ("Quarterly Governance Audit", "Q3 continental governance reports are ready for review.", "system", False, "/foundation/dashboard/drilldown/reports/"),
                ],
            ),
        ]:
            for title, msg, cat, is_read, target in notifs:
                Notification.objects.update_or_create(
                    account=acc,
                    title=title,
                    defaults={
                        "network": net,
                        "country": ctry,
                        "message": msg,
                        "category": cat,
                        "is_read": is_read,
                        "target_url": target,
                        "delivery_status": "delivered",
                    },
                )

        # =====================================================================
        # Seed Privacy Requests & Transitions
        # =====================================================================
        PrivacyRequest.objects.update_or_create(
            reference="PR-2026-081",
            defaults={
                "account": acc_ada,
                "request_type": "Correct my information",
                "details": "Update verified home chapter and contact preferences.",
                "safe_reply_route": "Reply in my account",
                "current_step": "Officer review in progress",
                "next_action": "Awaiting Privacy Officer decision",
                "identity_check_status": "Verified",
                "decision": "Under Review",
                "status": "Waiting for review",
                "timeline": [
                    {"step": "Request Submitted", "date": (now - timedelta(days=2)).strftime("%d %b %Y"), "status": "completed"},
                    {"step": "Identity Verification", "date": (now - timedelta(days=1)).strftime("%d %b %Y"), "status": "completed"},
                    {"step": "Officer Review", "date": now.strftime("%d %b %Y"), "status": "active"},
                ],
            },
        )

        NetworkTransition.objects.update_or_create(
            account=acc_wnnn,
            defaults={
                "current_relationship": "WNNN Youth Membership (Ghana)",
                "requested_transition": "WGMN Adult Membership (West Africa)",
                "age_evidence_method": "Approved Government ID Attestation",
                "consent_confirmed": True,
                "status": "in_progress",
                "step": 2,
            },
        )

        # =====================================================================
        # Output Formatted Credentials Table
        # =====================================================================
        totp = pyotp.TOTP(totp_secret)
        current_code = totp.now()
        remaining = 30 - (int(time.time()) % 30)

        origin = getattr(settings, "WDOS_PUBLIC_ORIGIN", "http://127.0.0.1:8008").rstrip("/")

        self.stdout.write("\n" + "=" * 88)
        self.stdout.write(self.style.SUCCESS("  WDOS TEST ACCOUNTS SEEDED SUCCESSFULLY FOR LOCAL & STAGING"))
        self.stdout.write("=" * 88)
        self.stdout.write(f"  Login URL:            {origin}/auth/login/")
        self.stdout.write(f"  Shared Password:      {password}")
        self.stdout.write(f"  Shared TOTP Secret:   {totp_secret}  (Add to Google Authenticator/Authy)")
        self.stdout.write(self.style.NOTICE(f"  Live 6-Digit TOTP:    {current_code}  (Valid for ~{remaining}s)"))
        self.stdout.write("-" * 88)

        accounts_table = [
            ("member.ada@example.org", "Member (Ada Okafor)", "WGMN / Nigeria", "NO (1-Step Login)", "N/A"),
            ("wnnn.member@example.org", "Member (Efua Mensah)", "WNNN / Ghana", "NO (1-Step Login)", "N/A"),
            ("chapter.lagos@example.org", "Chapter Lead", "WGMN / Lagos", "Yes (TOTP)", "11112222"),
            ("country.ng@example.org", "Country Director", "Nigeria Hub (All)", "Yes (TOTP)", "33334444"),
            ("ops@example.org", "Operations Lead", "Global / Multi-Hub", "Yes (TOTP)", "55556666"),
            ("founder@example.org", "Founder & Exec Director", "Global / All", "Yes (TOTP)", "77778888"),
            ("candidate.john@example.org", "Candidate (John Kalu)", "WGMN / Nigeria", "NO (1-Step Login)", "N/A"),
        ]

        self.stdout.write(f"{'Email':<27} | {'Role / Persona':<24} | {'Scope':<18} | {'2FA Required?':<16} | {'Backup Code'}")
        self.stdout.write("-" * 88)
        for email, role, scope, mfa, backup in accounts_table:
            self.stdout.write(f"{email:<27} | {role:<24} | {scope:<18} | {mfa:<16} | {backup}")
        self.stdout.write("=" * 88 + "\n")
