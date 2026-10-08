"""Utility script to create development and admin users for testing locally and on Render.

Creates:
  1. member@example.org (DevMember@2026!Wdos) - Active member, no MFA required
  2. admin@example.org (DevAdmin@2026!Wdos) - Superuser/Staff with preconfigured TOTP MFA
"""
import os
import sys
import uuid
import time
import argparse
import pyotp
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wdos_project.settings")
import django
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.conf import settings
from accounts.models import Account, Person
from accounts.services import encrypt

User = get_user_model()
DEFAULT_DEV_SECRET = "JBSWY3DPEHPK3PXP"


def get_or_create_dev_user(email, password, display_name, is_staff=False, is_superuser=False, mfa_secret_key=None):
    email = email.strip().lower()
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        user = User.objects.create(
            username=uuid.uuid4().hex,
            email=email,
            first_name=display_name,
            is_staff=is_staff,
            is_superuser=is_superuser,
            is_active=True,
        )
        user.set_password(password)
        user.save()
        print(f"[+] Created Django user: {email}")
    else:
        user.first_name = display_name
        user.is_staff = is_staff
        user.is_superuser = is_superuser
        user.is_active = True
        user.set_password(password)
        user.save()
        print(f"[*] Updated Django user: {email}")

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
            mfa_secret=encrypt(mfa_secret_key) if mfa_secret_key else "",
            mfa_pending_secret="",
            mfa_pending_until=None,
        )
        print(f"[+] Created active Account: {email}")
    else:
        account.status = "active"
        if not account.verified_at:
            account.verified_at = timezone.now()
        if mfa_secret_key:
            account.mfa_secret = encrypt(mfa_secret_key)
            account.mfa_pending_secret = ""
            account.mfa_pending_until = None
        account.security_version += 1
        account.save()
        print(f"[*] Updated active Account: {email}")

    return user, account


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or update development & admin users.")
    parser.add_argument("--email", default="admin@example.org", help="Admin email")
    parser.add_argument("--password", default="DevAdmin@2026!Wdos", help="Admin password")
    parser.add_argument("--name", default="Dev Admin", help="Admin display name")
    parser.add_argument("--secret", default=DEFAULT_DEV_SECRET, help="Base32 TOTP secret")
    args = parser.parse_args()

    print("Setting up development & admin accounts...")
    get_or_create_dev_user(
        email="member@example.org",
        password="DevMember@2026!Wdos",
        display_name="Dev Member",
        is_staff=False,
        is_superuser=False,
    )
    get_or_create_dev_user(
        email=args.email,
        password=args.password,
        display_name=args.name,
        is_staff=True,
        is_superuser=True,
        mfa_secret_key=args.secret,
    )

    totp = pyotp.TOTP(args.secret)
    current_code = totp.now()
    remaining = 30 - (int(time.time()) % 30)

    origin = getattr(settings, "WDOS_PUBLIC_ORIGIN", "http://127.0.0.1:8080").rstrip("/")

    print("\n" + "=" * 64)
    print("  ACCOUNTS READY:")
    print("  Standard User: member@example.org / DevMember@2026!Wdos")
    print(f"  Admin User:    {args.email} / {args.password}")
    print(f"  TOTP Secret:   {args.secret}")
    print(f"  Current Code:  {current_code} (valid for ~{remaining}s)")
    print("-" * 64)
    print(f"  Login at:      {origin}/auth/login/")
    print(f"  Admin at:      {origin}/admin/")
    print("=" * 64 + "\n")
