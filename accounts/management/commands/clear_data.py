"""
Management command to completely wipe all dynamic, operational, meeting, task,
activity, and member account records, returning the system to a clean slate
ready for fresh onboarding while preserving required geographical catalogues
(CountryCatalogue, AdministrativeDivision, Chapter, CountryHub, Role, LeadershipLevel)
and preserving a single clean administrator account for Django Admin.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from foundation.models import (
    EventModerationQuestion,
    EventRegistration,
    EventSessionTrack,
    ConferenceEvent,
    RoomDiagnosticLane,
    LiveTranscriptSegment,
    RoomParticipantSession,
    MeetingRoomSession,
    MeetingDecisionAction,
    MeetingParticipantRecord,
    TaskLifecycleEntry,
    MissionControlTask,
    MeetingSeries,
    CandidateRubricScore,
    CandidateApplication,
    ReferralLink,
    CandidateReferral,
    VolunteerOpportunity,
    RecruitmentRouteConfig,
    HandoverAssetTask,
    LeadershipTransitionPlan,
    LeadershipStatusChange,
    LeadershipReview,
    SeatHistory,
    AppointmentRecord,
    LeadershipSeat,
    PositionMaster,
    LocalHomeReassignment,
    PersonRelationship,
    PersonProfile,
    Communication,
    ScheduledMeeting,
    DashboardReport,
    DashboardActivity,
    DashboardAlert,
    NetworkTransition,
    PrivacyRequest,
    DeviceSession,
    UserPreference,
    Notification,
    WorkItem,
    LocalOrganisationUnit,
    CountryDossier,
    GeographyTerminology,
)
from accounts.models import (
    EmailIntent,
    ActionToken,
    AuditEvent,
    Throttle,
    Membership,
    OnboardingConsent,
    OnboardingEvent,
    OnboardingDraft,
    AccessGrant,
    DataImprovementFlag,
    Invitation,
    RecoveryCode,
    Account,
    Person,
)


class Command(BaseCommand):
    help = "Clears all operational and user data, preserving only onboarding catalogues and admin."

    def handle(self, *args, **options):
        self.stdout.write("Wiping operational records...")

        # 1. Operational & Stage records
        EventModerationQuestion.objects.all().delete()
        EventRegistration.objects.all().delete()
        EventSessionTrack.objects.all().delete()
        ConferenceEvent.objects.all().delete()
        RoomDiagnosticLane.objects.all().delete()
        LiveTranscriptSegment.objects.all().delete()
        RoomParticipantSession.objects.all().delete()
        MeetingRoomSession.objects.all().delete()
        MeetingDecisionAction.objects.all().delete()
        MeetingParticipantRecord.objects.all().delete()
        TaskLifecycleEntry.objects.all().delete()
        MissionControlTask.objects.all().delete()
        MeetingSeries.objects.all().delete()
        CandidateRubricScore.objects.all().delete()
        CandidateApplication.objects.all().delete()
        ReferralLink.objects.all().delete()
        CandidateReferral.objects.all().delete()
        VolunteerOpportunity.objects.all().delete()
        RecruitmentRouteConfig.objects.all().delete()
        HandoverAssetTask.objects.all().delete()
        LeadershipTransitionPlan.objects.all().delete()
        LeadershipStatusChange.objects.all().delete()
        LeadershipReview.objects.all().delete()
        SeatHistory.objects.all().delete()
        AppointmentRecord.objects.all().delete()
        LeadershipSeat.objects.all().delete()
        PositionMaster.objects.all().delete()
        LocalHomeReassignment.objects.all().delete()
        PersonRelationship.objects.all().delete()
        PersonProfile.objects.all().delete()
        Communication.objects.all().delete()
        ScheduledMeeting.objects.all().delete()
        DashboardReport.objects.all().delete()
        DashboardActivity.objects.all().delete()
        DashboardAlert.objects.all().delete()
        NetworkTransition.objects.all().delete()
        PrivacyRequest.objects.all().delete()
        DeviceSession.objects.all().delete()
        UserPreference.objects.all().delete()
        Notification.objects.all().delete()
        WorkItem.objects.all().delete()
        LocalOrganisationUnit.objects.all().delete()
        CountryDossier.objects.all().delete()
        GeographyTerminology.objects.all().delete()

        self.stdout.write("Wiping account sessions, drafts, and memberships...")

        # 2. Account tokens, drafts, memberships
        EmailIntent.objects.all().delete()
        ActionToken.objects.all().delete()
        AuditEvent.objects.all().delete()
        Throttle.objects.all().delete()
        Membership.objects.all().delete()
        OnboardingConsent.objects.all().delete()
        OnboardingEvent.objects.all().delete()
        OnboardingDraft.objects.all().delete()
        AccessGrant.objects.all().delete()
        DataImprovementFlag.objects.all().delete()
        Invitation.objects.all().delete()
        RecoveryCode.objects.all().delete()

        self.stdout.write("Purging non-admin users and accounts...")

        # 3. Purge non-admin accounts and users
        from datetime import timedelta
        from django.utils import timezone

        User = get_user_model()
        keep_emails = ["admin@example.org", "founder@example.org"]
        keep_accs = list(Account.objects.filter(email__in=keep_emails))
        keep_person_ids = [a.person_id for a in keep_accs if a.person_id]

        Account.objects.exclude(email__in=keep_emails).delete()
        User.objects.exclude(email__in=keep_emails).delete()
        if keep_person_ids:
            Person.objects.exclude(id__in=keep_person_ids).delete()
        else:
            Person.objects.all().delete()

        # Ensure single admin superuser exists
        admin_user = User.objects.filter(email="admin@example.org").first()
        if not admin_user:
            admin_user = User.objects.create_superuser("admin@example.org", "admin@example.org", "WDOSPassphrase2026!")
            admin_user.first_name = "Dev"
            admin_user.last_name = "Admin"
            admin_user.save()
        else:
            admin_user.set_password("WDOSPassphrase2026!")
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.is_active = True
            admin_user.save()

        admin_person, _ = Person.objects.get_or_create(display_name="Dev Admin")
        admin_acc, _ = Account.objects.get_or_create(
            email="admin@example.org",
            defaults={
                "user": admin_user,
                "person": admin_person,
                "display_name": "Dev Admin",
                "status": "active",
                "security_version": 1,
            },
        )
        admin_acc.user = admin_user
        admin_acc.person = admin_person
        admin_acc.status = "active"
        admin_acc.save()

        # Ensure Tier 1 Founder account exists cleanly
        founder_user = User.objects.filter(email="founder@example.org").first()
        if not founder_user:
            founder_user = User.objects.create_superuser("founder", "founder@example.org", "WDOSPassphrase2026!")
            founder_user.first_name = "Founder"
            founder_user.last_name = "Executive Director"
            founder_user.save()
        else:
            founder_user.set_password("WDOSPassphrase2026!")
            founder_user.is_staff = True
            founder_user.is_superuser = True
            founder_user.is_active = True
            founder_user.save()

        founder_person, _ = Person.objects.get_or_create(display_name="Founder & Executive Director")
        founder_acc, _ = Account.objects.get_or_create(
            email="founder@example.org",
            defaults={
                "user": founder_user,
                "person": founder_person,
                "display_name": "Founder & Executive Director",
                "status": "active",
                "security_version": 1,
            },
        )
        founder_acc.user = founder_user
        founder_acc.person = founder_person
        founder_acc.status = "active"
        founder_acc.save()

        AccessGrant.objects.update_or_create(
            account=founder_acc,
            role="founder",
            defaults={
                "network": "*",
                "geography": "*",
                "function": "governance",
                "expires_at": timezone.now() + timedelta(days=365),
                "revoked_at": None,
            },
        )

        self.stdout.write(self.style.SUCCESS("All operational and test data cleared. Onboarding catalogues preserved."))
