"""
Seed comprehensive Stage 4 fixtures for all 7 role views:
- Founder/HQ
- Operations
- Country/Field Leadership
- Chapter Lead
- Member
- Candidate
- Community

Seeds realistic test accounts, CountryHubs, Chapters across networks and countries,
live Scoped KPIs records, Alerts, Reports, Meetings, Communications, and WorkItems.
Idempotent command.
"""
from datetime import timedelta
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import AccessGrant, Account, Membership, OnboardingConsent, OnboardingDraft, Person
from foundation.models import (
    Chapter,
    Communication,
    CountryHub,
    DashboardActivity,
    DashboardAlert,
    DashboardReport,
    LeadershipLevel,
    ScheduledMeeting,
    UserPreference,
    WorkItem,
)

User = get_user_model()

DEFAULT_PASSWORD = "WDOSPassphrase2026!"


class Command(BaseCommand):
    help = "Seed comprehensive Stage 4 multi-role fixtures and dashboard records."

    def handle(self, *args, **options):
        now = timezone.now()

        # ---------------------------------------------------------------------
        # 1. Country Hubs
        # ---------------------------------------------------------------------
        hubs_data = [
            ("NG", "Nigeria", "West Africa", "active", "Dr. Aisha Bello", "aisha.bello@example.org"),
            ("GH", "Ghana", "West Africa", "active", "Grace Mensah", "grace.mensah@example.org"),
            ("KE", "Kenya", "East Africa", "active", "Wanjiru Kariuki", "wanjiru.kariuki@example.org"),
            ("ZA", "South Africa", "Southern Africa", "active", "Nandi Khumalo", "nandi.khumalo@example.org"),
            ("RW", "Rwanda", "East Africa", "active", "Aline Uwase", "aline.uwase@example.org"),
            ("AO", "Angola", "Central Africa", "active", "Manuel dos Santos", "manuel.santos@example.org"),
            ("ET", "Ethiopia", "East Africa", "active", "Almaz Tadesse", "almaz.tadesse@example.org"),
        ]
        for code, name, region, status, lead_name, lead_email in hubs_data:
            CountryHub.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "region": region,
                    "status": status,
                    "lead_name": lead_name,
                    "lead_email": lead_email,
                },
            )
        self.stdout.write("Country hubs verified.")

        # ---------------------------------------------------------------------
        # 2. Chapters across Networks and Geography
        # ---------------------------------------------------------------------
        chapters_data = [
            # Nigeria - WGMN
            ("NG-LOS-01", "Lagos Central Chapter", "WGMN", "NG", "Lagos", "Ikeja", "Adaeze Okonkwo", "adaeze@example.org", 42),
            ("NG-ABJ-01", "Abuja FCT Chapter", "WGMN", "NG", "FCT", "Abuja Municipal", "Fatima Aliyu", "fatima@example.org", 28),
            ("NG-PHC-01", "Port Harcourt Chapter", "WGMN", "NG", "Rivers", "Port Harcourt", "Blessing Amadi", "blessing@example.org", 25),
            # Nigeria - WNNN
            ("NG-LOS-02", "Lagos Next-Gen Youth Hub", "WNNN", "NG", "Lagos", "Surulere", "Chinedu Eze", "chinedu@example.org", 35),
            ("NG-KAN-01", "Kano Youth Empowerment Hub", "WNNN", "NG", "Kano", "Kano Municipal", "Ibrahim Sani", "ibrahim@example.org", 18),
            # Kenya - WGMN & WNNN
            ("KE-NBO-01", "Nairobi Central Chapter", "WGMN", "KE", "Nairobi", "Kilimani", "Wanjiru Kariuki", "wanjiru.kariuki@example.org", 31),
            ("KE-NBO-02", "Nairobi Youth Tech Chapter", "WNNN", "KE", "Nairobi", "Westlands", "Brian Otieno", "brian@example.org", 24),
            ("KE-MSA-01", "Mombasa Coastal Chapter", "WGMN", "KE", "Coast", "Mombasa", "Halima Bakari", "halima@example.org", 15),
            # Ghana - WGMN & WNNN
            ("GH-ACC-01", "Accra Central Chapter", "WGMN", "GH", "Greater Accra", "Accra Metro", "Abena Osei", "abena@example.org", 19),
            ("GH-ACC-02", "Accra Next-Gen Hub", "WNNN", "GH", "Greater Accra", "Tema", "Kwame Asante", "kwame@example.org", 22),
            # South Africa & Rwanda
            ("ZA-JHB-01", "Johannesburg Chapter", "WGMN", "ZA", "Gauteng", "Johannesburg", "Thandiwe Molefe", "thandi@example.org", 27),
            ("RW-KGL-01", "Kigali Peace Chapter", "WGMN", "RW", "Kigali", "Gasabo", "Jeanette Mukamana", "jeanette@example.org", 18),
            # Angola & Ethiopia - WGMN
            ("AO-LUA-01", "Luanda Central Chapter", "WGMN", "AO", "Luanda", "Ingombota", "Mary David", "mary.david@example.org", 20),
            ("ET-ADD-01", "Addis Ababa Central Chapter", "WGMN", "ET", "Addis Ababa", "Bole", "Sarah Andres", "sarah.andres@example.org", 26),
        ]
        for code, name, net, country, region, district, lead, email, count in chapters_data:
            Chapter.objects.update_or_create(
                code=code,
                defaults={
                    "name": name,
                    "network": net,
                    "country": country,
                    "region": region,
                    "district": district,
                    "lead_name": lead,
                    "lead_email": email,
                    "member_count": count,
                    "status": "active",
                },
            )
        self.stdout.write("Chapters seeded across networks and countries.")

        # ---------------------------------------------------------------------
        # 3. Eight Distinct Test Accounts
        # ---------------------------------------------------------------------
        # Helper creator
        def ensure_user_account(email, display_name, is_staff=False, is_superuser=False):
            u = User.objects.filter(email=email).first()
            if not u:
                u = User.objects.filter(username=email.split("@")[0]).first()
            if not u:
                u = User.objects.create(
                    username=email.split("@")[0],
                    email=email,
                    is_staff=is_staff,
                    is_superuser=is_superuser,
                )
            u.set_password(DEFAULT_PASSWORD)
            u.is_staff = is_staff
            u.is_superuser = is_superuser
            u.save()

            acc = Account.objects.filter(user=u).first() or Account.objects.filter(email=email).first()
            if acc and acc.person:
                p = acc.person
                p.display_name = display_name
                p.save(update_fields=["display_name"])
            else:
                p = Person.objects.create(display_name=display_name)

            if not acc:
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
                acc.person = p
                acc.status = "active"
                if not acc.verified_at:
                    acc.verified_at = now
                acc.save()
            return u, acc, p

        # 3.1 Founder/HQ
        _, acc_founder, _ = ensure_user_account("founder@example.org", "Founder & Executive Director", is_staff=True, is_superuser=True)
        AccessGrant.objects.update_or_create(
            account=acc_founder,
            role="founder",
            defaults={"network": "*", "geography": "*", "function": "all", "expires_at": now + timedelta(days=365)},
        )

        # 3.2 Operations
        _, acc_ops, _ = ensure_user_account("ops@example.org", "Chief Operations Lead", is_staff=True)
        AccessGrant.objects.update_or_create(
            account=acc_ops,
            role="operations",
            defaults={"network": "*", "geography": "*", "function": "all", "expires_at": now + timedelta(days=365)},
        )

        # 3.3 Country Lead Nigeria
        _, acc_country_ng, person_country_ng = ensure_user_account("country.ng@example.org", "Dr. Aisha Bello (Nigeria Lead)")
        AccessGrant.objects.update_or_create(
            account=acc_country_ng,
            role="country_lead",
            defaults={"network": "*", "geography": "NG", "function": "all", "expires_at": now + timedelta(days=365)},
        )
        UserPreference.objects.update_or_create(
            account=acc_country_ng,
            defaults={"active_network": "WGMN", "active_country": "NG", "language": "en"},
        )

        # 3.4 Country Lead Kenya (Wanjiru Kariuki)
        _, acc_country_ke, person_country_ke = ensure_user_account("country.ke@example.org", "Wanjiru Kariuki (Kenya Lead)")
        AccessGrant.objects.update_or_create(
            account=acc_country_ke,
            role="country_lead",
            defaults={"network": "WGMN", "geography": "KE", "function": "all", "expires_at": now + timedelta(days=365)},
        )
        draft_ke, _ = OnboardingDraft.objects.get_or_create(
            account=acc_country_ke,
            defaults={"state": "accepted", "next_step": 8, "data": {"network": "WGMN", "country": "KE", "district": "KE-NBO-01", "language": "en"}},
        )
        draft_ke.state = "accepted"
        draft_ke.data = {"network": "WGMN", "country": "KE", "district": "KE-NBO-01", "language": "en"}
        draft_ke.save()
        consent_ke, _ = OnboardingConsent.objects.get_or_create(
            draft=draft_ke,
            revision=1,
            defaults={"version": "1.0", "notice": "Notice", "digest": "d", "approval_reference": "ref", "privacy_ack": True, "channel": "web"},
        )
        Membership.objects.update_or_create(
            draft=draft_ke,
            defaults={
                "person": person_country_ke,
                "network": "WGMN",
                "home": {"code": "KE-NBO-01", "country": "KE", "state": "Nairobi", "label": "Nairobi Central Chapter"},
                "consent": consent_ke,
                "policy_digest": "country_lead_digest",
                "approved_by": acc_founder,
            },
        )
        UserPreference.objects.update_or_create(
            account=acc_country_ke,
            defaults={"active_network": "WGMN", "active_country": "KE", "language": "en"},
        )

        # 3.5 Chapter Lead Lagos
        _, acc_chapter_lagos, person_chapter_lagos = ensure_user_account("chapter.lagos@example.org", "Adaeze Okonkwo (Lagos Lead)")
        AccessGrant.objects.update_or_create(
            account=acc_chapter_lagos,
            role="chapter_lead",
            defaults={"network": "WGMN", "geography": "NG-LOS-01", "function": "chapter", "expires_at": now + timedelta(days=365)},
        )
        draft_lead, _ = OnboardingDraft.objects.get_or_create(
            account=acc_chapter_lagos,
            defaults={"state": "accepted", "next_step": 8, "data": {"network": "WGMN", "country": "NG", "language": "en"}},
        )
        draft_lead.state = "accepted"
        draft_lead.save()
        consent_lead, _ = OnboardingConsent.objects.get_or_create(
            draft=draft_lead,
            revision=1,
            defaults={"version": "1.0", "notice": "Notice", "digest": "d", "approval_reference": "ref", "privacy_ack": True, "channel": "web"},
        )
        Membership.objects.update_or_create(
            draft=draft_lead,
            defaults={
                "person": person_chapter_lagos,
                "network": "WGMN",
                "home": {"code": "NG-LOS-01", "country": "NG", "state": "Lagos", "label": "Lagos Central Chapter"},
                "consent": consent_lead,
                "policy_digest": "chapter_lead_digest",
                "approved_by": acc_founder,
            },
        )
        UserPreference.objects.update_or_create(
            account=acc_chapter_lagos,
            defaults={"active_network": "WGMN", "active_country": "NG", "language": "en"},
        )

        # 3.6 Member Ada Okafor (WGMN, NG, Lagos)
        _, acc_member_ada, person_ada = ensure_user_account("member.ada@example.org", "Ada Okafor")
        draft_ada, _ = OnboardingDraft.objects.get_or_create(
            account=acc_member_ada,
            defaults={"state": "accepted", "next_step": 8, "data": {"network": "WGMN", "country": "NG", "language": "en"}},
        )
        draft_ada.state = "accepted"
        draft_ada.save()
        consent_ada, _ = OnboardingConsent.objects.get_or_create(
            draft=draft_ada,
            revision=1,
            defaults={"version": "1.0", "notice": "Notice", "digest": "d", "approval_reference": "ref", "privacy_ack": True, "channel": "web"},
        )
        Membership.objects.update_or_create(
            draft=draft_ada,
            defaults={
                "person": person_ada,
                "network": "WGMN",
                "home": {"code": "NG-LOS-01", "country": "NG", "state": "Lagos", "label": "Lagos Central Chapter"},
                "consent": consent_ada,
                "policy_digest": "policy_digest",
                "approved_by": acc_founder,
            },
        )
        UserPreference.objects.update_or_create(
            account=acc_member_ada,
            defaults={"active_network": "WGMN", "active_country": "NG", "language": "en"},
        )

        # 3.7 Member Mary David (WGMN, AO, Luanda)
        _, acc_mary, person_mary = ensure_user_account("mary.david@example.org", "Mary David")
        draft_mary, _ = OnboardingDraft.objects.get_or_create(
            account=acc_mary,
            defaults={"state": "accepted", "next_step": 8, "data": {"network": "WGMN", "country": "AO", "district": "AO-LUA-01", "language": "pt"}},
        )
        draft_mary.state = "accepted"
        draft_mary.save()
        consent_mary, _ = OnboardingConsent.objects.get_or_create(
            draft=draft_mary,
            revision=1,
            defaults={"version": "1.0", "notice": "Notice", "digest": "d", "approval_reference": "ref", "privacy_ack": True, "channel": "web"},
        )
        Membership.objects.update_or_create(
            draft=draft_mary,
            defaults={
                "person": person_mary,
                "network": "WGMN",
                "home": {"code": "AO-LUA-01", "country": "AO", "label": "Luanda Central Chapter"},
                "consent": consent_mary,
                "policy_digest": "policy_digest",
                "approved_by": acc_founder,
            },
        )
        UserPreference.objects.update_or_create(
            account=acc_mary,
            defaults={"active_network": "WGMN", "active_country": "AO", "language": "pt"},
        )

        # 3.8 Members Sarah Andres & Kemi Dare (WGMN, ET, Addis Ababa)
        for et_email, et_name in [("sarah.andres@example.org", "Sarah Andres"), ("kemi.dare@example.org", "Kemi Dare")]:
            _, acc_et, person_et = ensure_user_account(et_email, et_name)
            dr_et, _ = OnboardingDraft.objects.get_or_create(
                account=acc_et,
                defaults={"state": "accepted", "next_step": 8, "data": {"network": "WGMN", "country": "ET", "district": "ET-ADD-01", "language": "en"}},
            )
            dr_et.state = "accepted"
            dr_et.save()
            cons_et, _ = OnboardingConsent.objects.get_or_create(
                draft=dr_et,
                revision=1,
                defaults={"version": "1.0", "notice": "Notice", "digest": "d", "approval_reference": "ref", "privacy_ack": True, "channel": "web"},
            )
            Membership.objects.update_or_create(
                draft=dr_et,
                defaults={
                    "person": person_et,
                    "network": "WGMN",
                    "home": {"code": "ET-ADD-01", "country": "ET", "label": "Addis Ababa Central Chapter"},
                    "consent": cons_et,
                    "policy_digest": "policy_digest",
                    "approved_by": acc_founder,
                },
            )
            UserPreference.objects.update_or_create(
                account=acc_et,
                defaults={"active_network": "WGMN", "active_country": "ET", "language": "en"},
            )

        # 3.9 Member Efua Mensah (WNNN, GH, Accra)
        for gh_email in ["wnnn.member@example.org", "wnnn_member@example.org", "efua.mensah@example.org"]:
            _, acc_gh, person_gh = ensure_user_account(gh_email, "Efua Mensah")
            dr_gh, _ = OnboardingDraft.objects.get_or_create(
                account=acc_gh,
                defaults={"state": "accepted", "next_step": 8, "data": {"network": "WNNN", "country": "GH", "district": "GH-ACC-02", "language": "en"}},
            )
            dr_gh.state = "accepted"
            dr_gh.save()
            cons_gh, _ = OnboardingConsent.objects.get_or_create(
                draft=dr_gh,
                revision=1,
                defaults={"version": "1.0", "notice": "Notice", "digest": "d", "approval_reference": "ref", "privacy_ack": True, "channel": "web"},
            )
            Membership.objects.update_or_create(
                draft=dr_gh,
                defaults={
                    "person": person_gh,
                    "network": "WNNN",
                    "home": {"code": "GH-ACC-02", "country": "GH", "label": "Accra Next-Gen Hub"},
                    "consent": cons_gh,
                    "policy_digest": "policy_digest",
                    "approved_by": acc_founder,
                },
            )
            UserPreference.objects.update_or_create(
                account=acc_gh,
                defaults={"active_network": "WNNN", "active_country": "GH", "language": "en"},
            )

        # 3.10 Candidate John Kalu (review_needed)
        for cand_email in ["candidate.john@example.org", "john.kalu@example.org"]:
            _, acc_candidate, _ = ensure_user_account(cand_email, "John Kalu")
            draft_john, _ = OnboardingDraft.objects.get_or_create(
                account=acc_candidate,
                defaults={"state": "review_needed", "next_step": 6, "data": {"network": "WGMN", "country": "NG", "language": "en"}},
            )
            draft_john.state = "review_needed"
            draft_john.save()
            AccessGrant.objects.update_or_create(
                account=acc_candidate,
                role="candidate",
                defaults={"network": "WGMN", "geography": "NG", "expires_at": now + timedelta(days=30)},
            )
            UserPreference.objects.update_or_create(
                account=acc_candidate,
                defaults={"active_network": "WGMN", "active_country": "NG", "language": "en"},
            )

        # 3.11 Community Amara Diallo (Community access)
        for comm_email in ["community.amara@example.org", "amara.diallo@example.org"]:
            _, acc_community, _ = ensure_user_account(comm_email, "Amara Diallo")
            AccessGrant.objects.update_or_create(
                account=acc_community,
                role="community",
                defaults={"network": "WGMN", "geography": "NG", "expires_at": now + timedelta(days=90)},
            )
            UserPreference.objects.update_or_create(
                account=acc_community,
                defaults={"active_network": "WGMN", "active_country": "NG", "language": "en"},
            )

        self.stdout.write("Distinct test accounts established across all roles and countries.")

        # ---------------------------------------------------------------------
        # 4. Dashboard Alerts
        # ---------------------------------------------------------------------
        alerts_data = [
            ("SLA Verification Backlog: Nigeria Queue Exceeds 24h", "warning", "sla", "WGMN", "NG", "Twelve applicant dossiers have exceeded standard SLA review thresholds in the Nigeria corridor.", "/foundation/work-queue/"),
            ("Critical: Governance Compliance Audit Due for West Africa", "critical", "compliance", "WGMN", "ALL", "Mandatory quarterly continental governance filings required by October 15.", "/foundation/dashboard/drilldown/reports/"),
            ("Logistics Update: Nairobi Assembly Venue Confirmed", "info", "logistics", "WGMN", "KE", "The Nairobi National Assembly venue is finalized at the Kenyatta Conference Centre.", None),
            ("Digital Skills Course Review: Next-Gen Curriculum", "info", "program", "WNNN", "GH", "Accra Hub course review completed with 98% positive participant feedback.", None),
        ]
        for title, sev, cat, net, country, msg, action in alerts_data:
            DashboardAlert.objects.update_or_create(
                title=title,
                defaults={
                    "severity": sev,
                    "category": cat,
                    "network": net,
                    "country": country,
                    "message": msg,
                    "action_url": action or "",
                    "is_active": True,
                },
            )
        self.stdout.write("Dashboard alerts seeded.")

        # ---------------------------------------------------------------------
        # 5. Scheduled Meetings
        # ---------------------------------------------------------------------
        meetings_data = [
            ("Continental Executive Leadership Council", "strategic_hq", "ALL", "ALL", "all", now + timedelta(days=7), "Virtual Global Auditorium (https://meet.woddi.org/exec-council)", "Founder & Executive Director", 32),
            ("Nigeria National Leadership Assembly", "country_assembly", "WGMN", "NG", "country_lead", now + timedelta(days=3), "Eko Convention Hall, Lagos", "Dr. Aisha Bello", 18),
            ("Lagos Central Weekly Chapter Fellowship", "chapter_meetup", "WGMN", "NG", "member", now + timedelta(days=2), "Ikeja Community Center, Lagos", "Adaeze Okonkwo", 26),
            ("Next-Gen Digital Literacy Bootcamp", "community_open", "WNNN", "GH", "community", now + timedelta(days=5), "Virtual Classroom Alpha (https://meet.woddi.org/nextgen-gh)", "Kwame Asante", 45),
            ("East Africa New Member Orientation", "orientation", "WGMN", "KE", "candidate", now + timedelta(days=4), "Nairobi Hub Conference Room 2", "Wanjiru Kariuki", 14),
            ("Kenya Leadership Advisory Council", "country_assembly", "WGMN", "KE", "country_lead", now + timedelta(days=3), "Nairobi Central Executive Boardroom", "Wanjiru Kariuki", 16),
            ("Luanda Chapter Community Fellowship", "chapter_meetup", "WGMN", "AO", "member", now + timedelta(days=2), "Luanda City Center Hall", "Mary David", 20),
            ("Addis Ababa Monthly Chapter Assembly", "chapter_meetup", "WGMN", "ET", "member", now + timedelta(days=3), "Addis Ababa Central Pavilion", "Sarah Andres", 25),
            ("Accra Next-Gen Chapter Assembly", "chapter_meetup", "WNNN", "GH", "member", now + timedelta(days=2), "Accra Community Center", "Efua Mensah", 30),
        ]
        for title, m_type, net, country, target, dt, loc, org, count in meetings_data:
            m, _ = ScheduledMeeting.objects.update_or_create(
                title=title,
                defaults={
                    "meeting_type": m_type,
                    "network": net,
                    "country": country,
                    "target_role": target,
                    "scheduled_at": dt,
                    "location": loc,
                    "organizer_name": org,
                    "attendees_count": count,
                },
            )
            # Add founder/ops as RSVP
            m.rsvp_accounts.add(acc_founder)

        self.stdout.write("Scheduled meetings seeded.")

        # ---------------------------------------------------------------------
        # 6. Strategic Published Reports
        # ---------------------------------------------------------------------
        reports_data = [
            ("Q3 2026 Continental Impact & Growth Audit", "executive_summary", "WGMN", "ALL", "Q3 2026", "Comprehensive audit of 12 regional hubs, 200+ chapters, and community micro-grants across Africa.", {"total_enrolled": 1420, "chapters_active": 45, "grants_disbursed_usd": 125000, "governance_score": 99.4}, "Founder & Executive Director"),
            ("West Africa Regional Field Report", "country_health", "WGMN", "NG", "September 2026", "Operational summary covering Lagos, Abuja, and Port Harcourt chapter activities and health outreaches.", {"active_members": 520, "meetings_held": 24, "retention_rate": 96.2}, "Dr. Aisha Bello"),
            ("Next-Gen Youth Education Progress: Ghana", "onboarding_throughput", "WNNN", "GH", "Q3 2026", "Assessment of youth chapter activities, digital bootcamps, and high-school leadership mentorship.", {"youth_participants": 340, "workshops": 12, "completion_rate": 91.5}, "Chief Operations Lead"),
            ("East Africa Hub Progress Report", "country_health", "WGMN", "KE", "September 2026", "Regional evaluation of chapter growth, community health sessions, and membership expansion across Kenya.", {"active_members": 380, "meetings_held": 18, "retention_rate": 94.8}, "Wanjiru Kariuki"),
            ("Southern Africa Regional Field Report", "country_health", "WGMN", "AO", "September 2026", "Luanda chapter activity, member onboarding metrics, and health outreach.", {"active_members": 210, "meetings_held": 10, "retention_rate": 95.0}, "Mary David"),
            ("Horn of Africa Regional Field Report", "country_health", "WGMN", "ET", "September 2026", "Addis Ababa chapter programs, youth vocational training, and member welfare.", {"active_members": 290, "meetings_held": 14, "retention_rate": 93.5}, "Sarah Andres"),
        ]
        for title, r_type, net, country, period, summary, metrics, author in reports_data:
            DashboardReport.objects.update_or_create(
                title=title,
                defaults={
                    "report_type": r_type,
                    "network": net,
                    "country": country,
                    "period": period,
                    "summary": summary,
                    "metrics": metrics,
                    "author_name": author,
                    "status": "published",
                },
            )
        self.stdout.write("Dashboard reports seeded.")

        # ---------------------------------------------------------------------
        # 7. Communications / Circulars
        # ---------------------------------------------------------------------
        comms_data = [
            ("Notice of Executive Assembly 2026", "ALL", "ALL", "all", "All leadership and members are notified of the upcoming Continental Summit.", "Founder & Executive Director"),
            ("Field Guidelines: Micro-Grant Applications Q4", "WGMN", "NG", "member", "Detailed steps on submitting community initiative proposals through your local chapter lead.", "Dr. Aisha Bello"),
            ("Welcome to WDOS Community: Open Programs Calendar", "ALL", "ALL", "community", "Explore our dual networks, webinar schedule, and community action opportunities.", "Chief Operations Lead"),
        ]
        for subj, net, country, target, body, sender in comms_data:
            Communication.objects.update_or_create(
                subject=subj,
                defaults={
                    "network": net,
                    "country": country,
                    "target_role": target,
                    "body": body,
                    "sender_name": sender,
                    "priority": "normal",
                },
            )
        self.stdout.write("Communications seeded.")

        # ---------------------------------------------------------------------
        # 8. Operational Work Items
        # ---------------------------------------------------------------------
        work_items_data = [
            ("Verify Applicant: Fatima Garba (WGMN Nigeria)", "review", "WGMN", "NG", "operations", "high", "pending", False, acc_ops),
            ("Audit Chapter Roster: Lagos Central Chapter", "audit", "WGMN", "NG", "operations", "medium", "in_progress", False, acc_ops),
            ("Data Privacy Subject Access Request: #PR-8821", "privacy", "ALL", "NG", "it_admin", "urgent", "pending", True, acc_founder),
            ("Verify Applicant: Sharon Chebet (WGMN Kenya)", "review", "WGMN", "KE", "country_lead", "high", "pending", False, acc_ops),
            ("Audit Chapter Roster: Nairobi Central Chapter", "audit", "WGMN", "KE", "country_lead", "medium", "in_progress", False, acc_ops),
            ("Review Sub-County Leadership Nominees: Nairobi", "review", "WGMN", "KE", "country_lead", "urgent", "pending", False, acc_ops),
            ("Review Youth Digital Bootcamp Rosters: Accra", "review", "WNNN", "GH", "operations", "medium", "pending", False, acc_ops),
            ("Member Verification Batch: Luanda Central", "review", "WGMN", "AO", "operations", "normal", "in_progress", False, acc_ops),
            ("Community Health Outreach Planning: Addis Ababa", "review", "WGMN", "ET", "operations", "normal", "pending", False, acc_ops),
        ]
        for title, cat, net, country, req_role, prio, st, conf, creator in work_items_data:
            WorkItem.objects.update_or_create(
                title=title,
                defaults={
                    "category": cat,
                    "network": net,
                    "country": country,
                    "required_role": req_role,
                    "priority": prio,
                    "status": st,
                    "confidential": conf,
                    "created_by": creator,
                    "summary": f"Automated work queue task for {title}",
                },
            )
        self.stdout.write("Operational work items seeded.")

        # ---------------------------------------------------------------------
        # 9. Dashboard Activities
        # ---------------------------------------------------------------------
        activities_data = [
            ("Lagos Chapter Monthly Fellowship Concluded", "meeting", "WGMN", "NG", "Adaeze Okonkwo", "/foundation/dashboard/chapters/"),
            ("New Verification Batch Dispatched", "verification", "WGMN", "NG", "Chief Operations Lead", "/foundation/work-queue/"),
            ("Executive Strategic Audit Q3 Published", "report", "WGMN", "NG", "Founder & Executive Director", "/foundation/dashboard/drilldown/reports/"),
            ("Nairobi Central Monthly Fellowship Concluded", "meeting", "WGMN", "KE", "Wanjiru Kariuki", "/foundation/dashboard/chapters/"),
            ("Kenya Regional Verification Batch Dispatched", "verification", "WGMN", "KE", "Wanjiru Kariuki", "/foundation/work-queue/"),
            ("East Africa Hub Progress Report Published", "report", "WGMN", "KE", "Wanjiru Kariuki", "/foundation/dashboard/drilldown/reports/"),
            ("Accra Youth Tech Bootcamp Concluded", "meeting", "WNNN", "GH", "Efua Mensah", "/foundation/dashboard/chapters/"),
            ("Luanda Chapter Onboarding Completed", "verification", "WGMN", "AO", "Mary David", "/foundation/work-queue/"),
            ("Addis Ababa Fellowship Assembly Held", "meeting", "WGMN", "ET", "Sarah Andres", "/foundation/dashboard/chapters/"),
        ]
        for title, act_type, net, country, actor, url in activities_data:
            DashboardActivity.objects.update_or_create(
                title=title,
                network=net,
                country=country,
                defaults={
                    "activity_type": act_type,
                    "actor_name": actor,
                    "details": {"target_url": url},
                },
            )
        self.stdout.write("Dashboard activities seeded.")

        self.stdout.write(self.style.SUCCESS("All Stage 4 Dashboard fixtures successfully seeded."))
