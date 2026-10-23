from datetime import timedelta
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.contrib.auth import get_user_model
from django.utils import timezone
from accounts.models import Account, Person, Membership, OnboardingDraft, OnboardingConsent, AccessGrant
from foundation.models import UserPreference
from foundation.recruitment_engine import seed_stage8_fixtures

User = get_user_model()


class Command(BaseCommand):
    help = "Seed Stage 08 Recruitment, Referrals, Activation, and Selection data and personas"

    def handle(self, *args, **options):
        call_command("seed_stage7_data")
        seed_stage8_fixtures()

        # Ensure Recruitment Reviewer persona (reviewer.ng@example.org) and Candidate persona (candidate.ng@example.org) exist
        personas = [
            ("reviewer.ng@example.org", "recruitment_reviewer_ng", "Ada Okafor", "recruitment_reviewer", "WGMN", "NG"),
            ("candidate.ng@example.org", "candidate_ada_ng", "Ada Okafor", "candidate", "WGMN", "NG"),
        ]
        for email, username, display_name, role_name, net, country in personas:
            acc = Account.objects.filter(email=email).first()
            if not acc:
                u = User.objects.filter(email=email).first()
                if not u:
                    u = User.objects.create(
                        username=username,
                        email=email,
                        first_name=display_name,
                        is_active=True,
                    )
                u.set_password("WDOSPassphrase2026!")
                u.save()
                p = Person.objects.create(display_name=display_name)
                acc = Account.objects.create(
                    user=u,
                    email=email,
                    person=p,
                    status="active",
                    display_name=display_name,
                    security_version=1,
                )
            else:
                acc.status = "active"
                acc.save()

            draft, _ = OnboardingDraft.objects.update_or_create(
                account=acc,
                defaults={"state": "accepted", "data": {"language": "en"}},
            )
            membership = Membership.objects.filter(person=acc.person).first()
            if not membership:
                consent, _ = OnboardingConsent.objects.get_or_create(
                    draft=draft,
                    revision=0,
                    defaults={
                        "version": "v1",
                        "notice": "Privacy notice",
                        "digest": "digest_v1",
                        "approval_reference": "REF-2026",
                        "privacy_ack": True,
                        "optional_updates": False,
                        "channel": "web",
                    },
                )
                membership = Membership.objects.create(
                    draft=draft,
                    person=acc.person,
                    network=net,
                    consent=consent,
                    approved_by=acc,
                    policy_digest="policy_digest_active",
                    home={"state": "Lagos", "lga": "Ikeja", "chapter": "Ikeja Chapter"},
                )

            AccessGrant.objects.filter(account=acc, role=role_name).delete()
            AccessGrant.objects.create(
                account=acc,
                network=net,
                geography=country,
                role=role_name,
                function="all",
                expires_at=timezone.now() + timedelta(days=365),
                revoked_at=None,
            )

            pref, _ = UserPreference.objects.get_or_create(account=acc)
            pref.active_network = net
            pref.active_country = country
            pref.active_role = role_name
            pref.save()

        self.stdout.write(self.style.SUCCESS("Stage 08 recruitment, referrals, activation, and selection fixtures seeded successfully."))
