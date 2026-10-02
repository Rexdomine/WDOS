"""Utility script to create development users for local testing.

Creates:
  1. member@example.org (DevMember@2026!Wdos) - Active member, no MFA required
  2. admin@example.org (DevAdmin@2026!Wdos) - Superuser/Staff
"""
import os
import sys
import uuid
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wdos_project.settings")
import django
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import Account, Person

User = get_user_model()


def get_or_create_dev_user(email, password, display_name, is_staff=False, is_superuser=False):
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
        )
        print(f"[+] Created active Account: {email}")
    else:
        account.status = "active"
        if not account.verified_at:
            account.verified_at = timezone.now()
        account.save()
        print(f"[*] Updated active Account: {email}")

    return user, account


if __name__ == "__main__":
    print("Setting up local development accounts...")
    get_or_create_dev_user(
        email="member@example.org",
        password="DevMember@2026!Wdos",
        display_name="Dev Member",
        is_staff=False,
        is_superuser=False,
    )
    get_or_create_dev_user(
        email="admin@example.org",
        password="DevAdmin@2026!Wdos",
        display_name="Dev Admin",
        is_staff=True,
        is_superuser=True,
    )
    print("\nLocal accounts ready:")
    print("  Standard User: member@example.org / DevMember@2026!Wdos")
    print("  Staff / Admin: admin@example.org  / DevAdmin@2026!Wdos")
