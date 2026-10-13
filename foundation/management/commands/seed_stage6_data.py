from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import Account, Person, Membership, OnboardingDraft, AccessGrant
from foundation.models import UserPreference
from foundation.people_geo_engine import seed_stage6_fixtures

User = get_user_model()

class Command(BaseCommand):
    help = "Seed Stage 06 People, Community, and Geography Spine data and test personas"

    def handle(self, *args, **options):
        # 1. Seed models and data fixtures
        seed_stage6_fixtures()
        self.stdout.write(self.style.SUCCESS("Stage 06 fixtures seeded successfully."))

        # 2. Ensure ada.secretary@example.org test user exists
        email = "ada.secretary@example.org"
        acc = Account.objects.filter(email=email).first()
        if not acc:
            u = User.objects.filter(email=email).first()
            if not u:
                u = User.objects.create(
                    username="ada_secretary",
                    email=email,
                    first_name="Ada Okafor",
                    is_active=True,
                )
            u.set_password("WDOSPassphrase2026!")
            u.save()

            p = Person.objects.create(display_name="Ada Okafor")
            acc = Account.objects.create(
                user=u,
                email=email,
                person=p,
                status="active",
                display_name="Ada Okafor",
                security_version=1,
            )
        else:
            acc.status = "active"
            acc.save()

        draft = OnboardingDraft.objects.filter(account=acc).first()
        if not draft:
            draft = OnboardingDraft.objects.create(
                account=acc,
                state="accepted",
                data={"language": "en"},
            )
        else:
            draft.state = "accepted"
            draft.save()

        membership = Membership.objects.filter(person=acc.person).first()
        if not membership:
            membership = Membership.objects.create(
                draft=draft,
                person=acc.person,
                network="WGMN",
                policy_digest="policy_digest_active",
                home={"state": "Lagos", "lga": "Ikeja", "chapter": "Ikeja Chapter"},
            )
        draft.membership = membership
        draft.save()

        # Grant network_secretary privileges
        AccessGrant.objects.filter(account=acc, role="network_secretary").delete()
        AccessGrant.objects.create(
            account=acc,
            network="WGMN",
            geography="NG",
            role="network_secretary",
            function="all",
            expires_at=timezone.now() + timedelta(days=365),
            revoked_at=None,
        )

        pref, _ = UserPreference.objects.get_or_create(account=acc)
        pref.active_network = "WGMN"
        pref.active_country = "NG"
        pref.active_role = "network_secretary"
        pref.save()

        # Also ensure founder@example.org has hofco access
        founder_acc = Account.objects.filter(email="founder@example.org").first()
        if founder_acc:
            AccessGrant.objects.update_or_create(
                account=founder_acc,
                role="hofco",
                defaults={
                    "network": "*",
                    "geography": "*",
                    "function": "all",
                    "expires_at": timezone.now() + timedelta(days=365),
                    "revoked_at": None,
                }
            )

        self.stdout.write(self.style.SUCCESS("Network Secretary persona (ada.secretary@example.org) configured."))
