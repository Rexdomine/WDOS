from django.contrib import admin
from .models import (
    Account,
    Person,
    AccessGrant,
    ActionToken,
    Invitation,
    RecoveryCode,
    EmailIntent,
    Throttle,
    AuditEvent,
    OnboardingDraft,
    OnboardingConsent,
    OnboardingEvent,
    Membership,
    CountryCatalogue,
    AdministrativeDivision,
    DataImprovementFlag,
)


@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = ("email", "display_name", "status", "verified_at", "security_version", "is_staff_user", "created_at")
    list_filter = ("status", "user__is_staff", "user__is_superuser")
    search_fields = ("email", "display_name")
    readonly_fields = ("created_at",)

    def is_staff_user(self, obj):
        return obj.user.is_staff if obj.user else False
    is_staff_user.boolean = True
    is_staff_user.short_description = "Staff"


@admin.register(Person)
class PersonAdmin(admin.ModelAdmin):
    list_display = ("id", "display_name", "created_at")
    search_fields = ("display_name",)


@admin.register(AccessGrant)
class AccessGrantAdmin(admin.ModelAdmin):
    list_display = ("account", "role", "network", "geography", "function", "expires_at", "revoked_at")
    list_filter = ("role", "network", "function")
    search_fields = ("account__email", "role", "geography")


@admin.register(Membership)
class MembershipAdmin(admin.ModelAdmin):
    list_display = ("person", "network", "approved_by", "created_at")
    list_filter = ("network",)
    search_fields = ("person__display_name", "network")


@admin.register(OnboardingDraft)
class OnboardingDraftAdmin(admin.ModelAdmin):
    list_display = ("account", "state", "next_step", "revision", "updated_at", "submitted_at")
    list_filter = ("state", "next_step")
    search_fields = ("account__email",)


@admin.register(CountryCatalogue)
class CountryCatalogueAdmin(admin.ModelAdmin):
    list_display = ("iso3", "iso2", "name", "admin1_label", "admin2_label", "level2_reliable", "last_verified_date")
    list_filter = ("level2_reliable",)
    search_fields = ("name", "iso3", "iso2")


@admin.register(AdministrativeDivision)
class AdministrativeDivisionAdmin(admin.ModelAdmin):
    list_display = ("id", "display_name", "country", "level", "local_unit_type", "last_verified_date")
    list_filter = ("level", "country")
    search_fields = ("display_name", "id")


@admin.register(DataImprovementFlag)
class DataImprovementFlagAdmin(admin.ModelAdmin):
    list_display = ("unlisted_subdivision", "country_iso3", "region_name", "status", "created_at")
    list_filter = ("status", "country_iso3")
    search_fields = ("unlisted_subdivision", "region_name")


@admin.register(EmailIntent)
class EmailIntentAdmin(admin.ModelAdmin):
    list_display = ("account", "state", "message_id", "created_at", "expires_at")
    list_filter = ("state",)
    search_fields = ("account__email", "message_id")


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("account", "event", "created_at")
    list_filter = ("event",)
    search_fields = ("account__email", "event")
