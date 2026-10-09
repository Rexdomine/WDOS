"""
Management command to approve an onboarding draft for testing.
Sets draft.state='accepted' and provisions the Membership record so the user
can immediately click 'Open my dashboard' and access their workspace.
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from accounts.models import (
    AccessGrant,
    Account,
    Membership,
    OnboardingConsent,
    OnboardingDraft,
    OnboardingEvent,
    Person,
)
from foundation.models import Chapter


class Command(BaseCommand):
    help = "Approve a user's onboarding draft so they can access their dashboard."

    def add_arguments(self, parser):
        parser.add_argument("email", help="Email of the account to approve")
        parser.add_argument("--network", default=None, help="Network override (e.g. WGMN, WNNN)")
        parser.add_argument("--chapter", default=None, help="Chapter code or label")

    def handle(self, *args, **options):
        email = options["email"].strip().lower()
        account = Account.objects.filter(email=email).first()
        if not account:
            self.stderr.write(self.style.ERROR(f"No account found with email '{email}'."))
            return

        draft = OnboardingDraft.objects.filter(account=account).first()
        if not draft:
            self.stderr.write(self.style.ERROR(f"No onboarding draft found for '{email}'."))
            return

        if draft.state == "accepted" and Membership.objects.filter(draft=draft).exists():
            self.stdout.write(self.style.SUCCESS(f"Account '{email}' is already approved with an active membership!"))
            return

        # Ensure Person exists
        person = account.person
        if not person:
            display_name = (draft.data or {}).get("full_name") or account.display_name or email.split("@")[0]
            person = Person.objects.create(display_name=display_name)
            account.person = person
            account.status = "active"
            account.verified_at = account.verified_at or timezone.now()
            account.save()

        # Determine network and home
        data = draft.data or {}
        network = options["network"] or data.get("network") or "WGMN"
        country = data.get("country") or "NG"
        chapter_code = options["chapter"] or data.get("district") or data.get("chapter_code") or "NG-LOS-01"

        chap = Chapter.objects.filter(code=chapter_code).first()
        chapter_label = chap.name if chap else (data.get("district") or "Lagos Central Chapter")

        home = {
            "code": chapter_code,
            "country": country,
            "label": chapter_label,
        }

        # Consent
        consent = OnboardingConsent.objects.filter(draft=draft).order_by("-id").first()
        if not consent:
            consent = OnboardingConsent.objects.create(
                draft=draft,
                revision=draft.revision,
                version="1.0",
                notice="Standard Privacy Notice",
                digest="consent_digest",
                approval_reference="WDOS-AUTO-APPROVAL",
                privacy_ack=True,
                channel="web",
            )

        # Create or update Membership
        Membership.objects.update_or_create(
            draft=draft,
            defaults={
                "person": person,
                "network": network,
                "home": home,
                "consent": consent,
                "policy_digest": "policy_digest_active",
                "approved_by": account,
            },
        )

        draft.state = "accepted"
        draft.next_step = 8
        draft.revision += 1
        draft.save(update_fields=["state", "next_step", "revision", "updated_at"])

        OnboardingEvent.objects.create(
            draft=draft,
            actor=account,
            revision=draft.revision,
            event="accepted",
            detail={"home": chapter_code, "note": "Approved via approve_onboarding command"},
        )

        self.stdout.write(self.style.SUCCESS(f"Successfully approved onboarding for '{email}'!"))
        self.stdout.write(self.style.NOTICE(f"  Network: {network}"))
        self.stdout.write(self.style.NOTICE(f"  Chapter: {chapter_label} ({chapter_code})"))
        self.stdout.write(self.style.NOTICE(f"  Dashboard: http://127.0.0.1:8008/foundation/ (or refresh /onboarding/8/ and click 'Open my dashboard')"))
