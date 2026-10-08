"""Management command to set up or inspect an administrator account for Django admin.

Ensures:
1. Django auth_user exists with is_staff=True, is_superuser=True, is_active=True
2. WDOS Account exists with status='active', verified_at set, linked to Person
3. MFA is pre-configured with a TOTP secret so privileged login passes AccountSecurityMiddleware
4. Outputs current TOTP 6-digit code for instant sign-in locally and on Render.
"""
import pyotp
import time
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from accounts.models import Account, Person
from accounts.services import encrypt, decrypt

DEFAULT_DEV_SECRET = "JBSWY3DPEHPK3PXP"


class Command(BaseCommand):
    help = "Quickly provision or inspect a Django admin superuser with MFA configured."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            default="admin@example.org",
            help="Email address for the admin user (default: admin@example.org)",
        )
        parser.add_argument(
            "--password",
            default="DevAdmin@2026!Wdos",
            help="Password for the admin user (default: DevAdmin@2026!Wdos)",
        )
        parser.add_argument(
            "--name",
            default="Dev Admin",
            help="Display name for the admin user (default: Dev Admin)",
        )
        parser.add_argument(
            "--secret",
            default=DEFAULT_DEV_SECRET,
            help=f"Base32 TOTP secret key (default: {DEFAULT_DEV_SECRET})",
        )
        parser.add_argument(
            "--totp",
            action="store_true",
            help="Only print the current 6-digit TOTP code for the specified email without modifying the account.",
        )

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        secret = options["secret"].strip().replace(" ", "").upper()

        if options["totp"]:
            account = Account.objects.filter(email=email).first()
            if not account or not account.mfa_secret:
                self.stderr.write(self.style.ERROR(f"No MFA configured for account {email}."))
                return
            totp_secret = decrypt(account.mfa_secret)
            totp = pyotp.TOTP(totp_secret)
            remaining = 30 - (int(time.time()) % 30)
            code = totp.now()
            self.stdout.write(self.style.SUCCESS(f"Current TOTP code for {email}: {code} (valid for {remaining}s)"))
            return

        password = options["password"]
        display_name = options["name"]
        User = get_user_model()

        # 1. Django User
        user = User.objects.filter(email__iexact=email).first()
        if not user:
            user = User.objects.create(
                username=email,
                email=email,
                first_name=display_name,
                is_staff=True,
                is_superuser=True,
                is_active=True,
            )
            user.set_password(password)
            user.save()
            user_action = "Created"
        else:
            user.first_name = display_name
            user.is_staff = True
            user.is_superuser = True
            user.is_active = True
            user.set_password(password)
            user.save()
            user_action = "Updated"

        # 2. Person & Account
        account = Account.objects.filter(email=email).first()
        if not account:
            person = Person.objects.create(display_name=display_name)
            account = Account.objects.create(
                user=user,
                email=email,
                display_name=display_name,
                person=person,
                status="active",
                verified_at=timezone.now(),
                mfa_secret=encrypt(secret),
                mfa_pending_secret="",
                mfa_pending_until=None,
            )
            account_action = "Created"
        else:
            account.status = "active"
            if not account.verified_at:
                account.verified_at = timezone.now()
            account.mfa_secret = encrypt(secret)
            account.mfa_pending_secret = ""
            account.mfa_pending_until = None
            account.security_version += 1
            account.save()
            account_action = "Updated"

        # 3. Calculate current TOTP code
        totp = pyotp.TOTP(secret)
        current_code = totp.now()
        remaining = 30 - (int(time.time()) % 30)

        origin = getattr(settings, "WDOS_PUBLIC_ORIGIN", "http://127.0.0.1:8080").rstrip("/")
        login_url = f"{origin}/auth/login/"
        admin_url = f"{origin}/admin/"

        self.stdout.write("\n" + "=" * 64)
        self.stdout.write(self.style.SUCCESS("  WDOS DJANGO ADMIN ACCESS PROVISIONED"))
        self.stdout.write("=" * 64)
        self.stdout.write(f"  User Record:        {user_action} (is_staff=True, is_superuser=True)")
        self.stdout.write(f"  Account Record:     {account_action} (status=active, verified)")
        self.stdout.write("-" * 64)
        self.stdout.write(f"  Login URL:          {login_url}")
        self.stdout.write(f"  Admin URL:          {admin_url}")
        self.stdout.write(f"  Email:              {email}")
        self.stdout.write(f"  Password:           {password}")
        self.stdout.write(f"  TOTP Secret:        {secret}")
        self.stdout.write(self.style.WARNING(f"  Current 6-Digit Code: {current_code} (expires in ~{remaining}s)"))
        self.stdout.write("-" * 64)
        self.stdout.write("  HOW TO ACCESS:")
        self.stdout.write(f"  1. Navigate to: {login_url}")
        self.stdout.write("  2. Enter the Email and Password above.")
        self.stdout.write("  3. When prompted for 2FA, enter the 6-digit code shown above.")
        self.stdout.write(f"     (Or add '{secret}' to your Google Authenticator/Authy app)")
        self.stdout.write(f"  4. Navigate to: {admin_url}")
        self.stdout.write("=" * 64 + "\n")
