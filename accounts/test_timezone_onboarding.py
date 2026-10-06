"""
Tests for automatic time-zone handling in Stage 3 onboarding.
Covers:
- Default timezone application on country selection for all 55 African countries.
- Multi-timezone country definitions and behavior (specifically DRC / CD).
- Manual override preservation vs deterministic updates on country/region change.
- Persistence across save/resume in onboarding drafts.
- Consistent time zone activation for displayed dates, history events, and reminders.
"""
import zoneinfo
from datetime import datetime, timezone as dt_tz
from django.test import TestCase, override_settings
from django.utils import timezone

from .african_geography import (
    AFRICAN_COUNTRIES,
    DEFAULT_COUNTRY_TIMEZONES,
    MULTI_TIMEZONE_COUNTRIES,
    format_user_datetime,
    get_country_default_timezone,
    get_country_timezones,
    is_multi_timezone_country,
    resolve_timezone_for_location,
)
from .onboarding import get_draft_timezone
from .onboarding_forms import GeographyForm
from .models import OnboardingDraft, OnboardingEvent, OnboardingConsent
from . import test_flows as helpers


class AfricanTimezoneGeographyTests(TestCase):
    def test_all_55_countries_have_valid_iana_timezones(self):
        available = zoneinfo.available_timezones()
        for name, data in AFRICAN_COUNTRIES.items():
            code = data["code"]
            tz_by_code = get_country_default_timezone(code)
            tz_by_name = get_country_default_timezone(name)

            self.assertIsNotNone(tz_by_code, f"Missing default timezone for code {code}")
            self.assertIsNotNone(tz_by_name, f"Missing default timezone for name {name}")
            self.assertEqual(tz_by_code, tz_by_name)
            self.assertIn(tz_by_code, available, f"Timezone {tz_by_code} for {name} is not a valid IANA zone")

    def test_country_default_timezones(self):
        self.assertEqual(get_country_default_timezone("NG"), "Africa/Lagos")
        self.assertEqual(get_country_default_timezone("Nigeria"), "Africa/Lagos")
        self.assertEqual(get_country_default_timezone("KE"), "Africa/Nairobi")
        self.assertEqual(get_country_default_timezone("Kenya"), "Africa/Nairobi")
        self.assertEqual(get_country_default_timezone("GH"), "Africa/Accra")
        self.assertEqual(get_country_default_timezone("Ghana"), "Africa/Accra")
        self.assertEqual(get_country_default_timezone("ZA"), "Africa/Johannesburg")
        self.assertEqual(get_country_default_timezone("South Africa"), "Africa/Johannesburg")
        self.assertEqual(get_country_default_timezone("EG"), "Africa/Cairo")
        self.assertEqual(get_country_default_timezone("Egypt"), "Africa/Cairo")

    def test_multi_timezone_country_identification(self):
        # DRC is multi-timezone
        self.assertTrue(is_multi_timezone_country("CD"))
        self.assertTrue(is_multi_timezone_country("Congo (Democratic Republic of the)"))
        # Other AU countries are single-timezone
        self.assertFalse(is_multi_timezone_country("NG"))
        self.assertFalse(is_multi_timezone_country("KE"))
        self.assertFalse(is_multi_timezone_country("ZA"))
        self.assertFalse(is_multi_timezone_country("GH"))

        # Timezones list for DRC contains both IANA zones
        cd_tzs = get_country_timezones("CD")
        self.assertEqual(cd_tzs, ["Africa/Kinshasa", "Africa/Lubumbashi"])

        # Single timezone countries return list with their default
        self.assertEqual(get_country_timezones("NG"), ["Africa/Lagos"])

    def test_multi_timezone_drc_behavior(self):
        # DRC with no region defaults to Africa/Kinshasa
        self.assertEqual(resolve_timezone_for_location("CD"), "Africa/Kinshasa")
        self.assertEqual(resolve_timezone_for_location("Congo (Democratic Republic of the)"), "Africa/Kinshasa")

        # Western provinces (UTC+1 -> Africa/Kinshasa)
        western_provinces = [
            "Kinshasa", "Kongo Central", "Kwango", "Kwilu",
            "Mai-Ndombe", "Équateur", "Mongala", "Nord-Ubangi", "Sud-Ubangi", "Tshuapa",
            "CD-KN", "CD-BC", "CD-EQ"
        ]
        for prov in western_provinces:
            tz = resolve_timezone_for_location("CD", prov)
            self.assertEqual(tz, "Africa/Kinshasa", f"Failed for western province {prov}")

        # Eastern provinces (UTC+2 -> Africa/Lubumbashi)
        eastern_provinces = [
            "Haut-Katanga", "Haut-Lomami", "Ituri", "Kasaï", "Kasaï-Central", "Kasaï-Oriental",
            "Lomami", "Lualaba", "Maniema", "Nord-Kivu", "Sud-Kivu", "Tanganyika", "Tshopo",
            "Bas-Uélé", "Haut-Uélé", "Sankuru",
            "CD-HK", "CD-NK", "CD-IT", "CD-TO"
        ]
        for prov in eastern_provinces:
            tz = resolve_timezone_for_location("CD", prov)
            self.assertEqual(tz, "Africa/Lubumbashi", f"Failed for eastern province {prov}")

    def test_manual_override_preservation_in_resolver(self):
        # When has_manual_override is True, explicit user choice is preserved
        self.assertEqual(
            resolve_timezone_for_location("Nigeria", "Lagos", current_timezone="Europe/London", has_manual_override=True),
            "Europe/London"
        )
        self.assertEqual(
            resolve_timezone_for_location("CD", "Haut-Katanga", current_timezone="UTC", has_manual_override=True),
            "UTC"
        )

        # When has_manual_override is False, country/region default is deterministically returned
        self.assertEqual(
            resolve_timezone_for_location("Nigeria", "Lagos", current_timezone="Europe/London", has_manual_override=False),
            "Africa/Lagos"
        )
        self.assertEqual(
            resolve_timezone_for_location("CD", "Haut-Katanga", current_timezone="UTC", has_manual_override=False),
            "Africa/Lubumbashi"
        )

    def test_format_user_datetime(self):
        fixed_dt = datetime(2026, 10, 6, 12, 0, 0, tzinfo=dt_tz.utc)

        # Lagos (UTC+1)
        lagos_formatted = format_user_datetime(fixed_dt, "Africa/Lagos")
        self.assertIn("+01:00", lagos_formatted)

        # Nairobi (UTC+3)
        nairobi_formatted = format_user_datetime(fixed_dt, "Africa/Nairobi")
        self.assertIn("+03:00", nairobi_formatted)

        # Lubumbashi (UTC+2)
        lubumbashi_formatted = format_user_datetime(fixed_dt, "Africa/Lubumbashi")
        self.assertIn("+02:00", lubumbashi_formatted)


class OnboardingTimezoneFormTests(TestCase):
    def test_geography_form_applies_country_default_timezone(self):
        form = GeographyForm(data={
            "country": "Nigeria",
            "region": "Lagos",
            "district": "Ikeja",
            "community_cluster": "Victoria Island Cluster",
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["timezone"], "Africa/Lagos")
        self.assertFalse(form.cleaned_data["timezone_override"])

    def test_geography_form_drc_western_province_timezone(self):
        form = GeographyForm(data={
            "country": "Congo (Democratic Republic of the)",
            "region": "Kinshasa",
            "community_cluster": "Gombe Cluster",
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["timezone"], "Africa/Kinshasa")

    def test_geography_form_drc_eastern_province_timezone(self):
        form = GeographyForm(data={
            "country": "Congo (Democratic Republic of the)",
            "region": "Haut-Katanga",
            "community_cluster": "Lubumbashi Cluster",
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["timezone"], "Africa/Lubumbashi")

    def test_geography_form_preserves_explicit_manual_override(self):
        # User manually specifies a timezone with override flag
        form = GeographyForm(data={
            "country": "Nigeria",
            "region": "Lagos",
            "district": "Ikeja",
            "timezone": "America/New_York",
            "timezone_override": "true",
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["timezone"], "America/New_York")
        self.assertTrue(form.cleaned_data["timezone_override"])

    def test_geography_form_preserves_override_from_initial_data(self):
        # Draft already had manual override set
        form = GeographyForm(
            data={
                "country": "Kenya",
                "region": "Nairobi",
            },
            initial={
                "timezone": "Europe/London",
                "timezone_override": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["timezone"], "Europe/London")
        self.assertTrue(form.cleaned_data["timezone_override"])

    def test_geography_form_updates_deterministically_when_override_cleared(self):
        # User explicitly clears override
        form = GeographyForm(
            data={
                "country": "Kenya",
                "region": "Nairobi",
                "timezone_override": False,
            },
            initial={
                "timezone": "Europe/London",
                "timezone_override": True,
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["timezone"], "Africa/Nairobi")
        self.assertFalse(form.cleaned_data["timezone_override"])


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class OnboardingTimezoneFlowIntegrationTests(TestCase):
    password = helpers.AuthFlows.password
    create = helpers.AuthFlows.create
    login = helpers.AuthFlows.login

    def setUp(self):
        self.account = self.create("onb-tz-member@example.org")
        self.login(self.account)

    def save_step(self, step, payload):
        draft = OnboardingDraft.objects.filter(account=self.account).first()
        rev = draft.revision if draft else 0
        return self.client.post(f"/onboarding/{step}/", {"revision": rev, "action": "continue", **payload})

    def test_country_selection_applies_configured_default_timezone(self):
        # Step 1: Continue with initial UTC (no manual override)
        resp1 = self.save_step(1, {"language": "en", "timezone": "UTC", "reading": "standard"})
        self.assertEqual(resp1.status_code, 302)

        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertFalse(draft.data.get("timezone_override", False))

        # Step 2: Profile
        self.save_step(2, {"full_name": "Kofi Mensah"})

        # Step 3: Network
        self.save_step(3, {"network": "WGMN", "eligibility": "pending", "eligibility_confirmed": "on"})

        # Step 4: Select Nigeria
        resp4 = self.save_step(4, {
            "country": "Nigeria",
            "region": "Lagos",
            "district": "Ikeja",
            "community_cluster": "Ikeja Cluster",
        })
        self.assertEqual(resp4.status_code, 302)

        draft.refresh_from_db()
        self.assertEqual(draft.data.get("timezone"), "Africa/Lagos")
        self.assertFalse(draft.data.get("timezone_override", False))

    def test_country_change_updates_timezone_deterministically(self):
        # User selects Nigeria first
        self.save_step(1, {"language": "en", "timezone": "UTC", "reading": "standard"})
        self.save_step(2, {"full_name": "Amina Diop"})
        self.save_step(3, {"network": "WGMN", "eligibility": "pending", "eligibility_confirmed": "on"})
        self.save_step(4, {"country": "Nigeria", "region": "Lagos", "district": "Ikeja"})

        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.data.get("timezone"), "Africa/Lagos")

        # Now user changes country to Kenya on Step 4
        resp4_change = self.save_step(4, {"country": "Kenya", "region": "Nairobi", "community_cluster": "Kilimani"})
        self.assertEqual(resp4_change.status_code, 302)

        draft.refresh_from_db()
        self.assertEqual(draft.data.get("timezone"), "Africa/Nairobi")

    def test_multi_timezone_drc_province_selection_and_switch(self):
        self.save_step(1, {"language": "en", "timezone": "UTC", "reading": "standard"})
        self.save_step(2, {"full_name": "Patrice Lumumba"})
        self.save_step(3, {"network": "WGMN", "eligibility": "pending", "eligibility_confirmed": "on"})

        # Select DRC with eastern province (Haut-Katanga)
        self.save_step(4, {
            "country": "Congo (Democratic Republic of the)",
            "region": "Haut-Katanga",
            "community_cluster": "Lubumbashi Centre",
        })
        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.data.get("timezone"), "Africa/Lubumbashi")

        # Change to western province (Kinshasa)
        self.save_step(4, {
            "country": "Congo (Democratic Republic of the)",
            "region": "Kinshasa",
            "community_cluster": "Gombe",
        })
        draft.refresh_from_db()
        self.assertEqual(draft.data.get("timezone"), "Africa/Kinshasa")

    def test_explicit_manual_choice_is_preserved_on_country_change(self):
        # Step 1: User explicitly picks a non-default timezone (e.g. America/New_York)
        self.save_step(1, {"language": "en", "timezone": "America/New_York", "reading": "standard"})
        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.data.get("timezone"), "America/New_York")
        self.assertTrue(draft.data.get("timezone_override"))

        self.save_step(2, {"full_name": "Global Member"})
        self.save_step(3, {"network": "WGMN", "eligibility": "pending", "eligibility_confirmed": "on"})

        # Step 4: User selects Nigeria -> manual override is preserved!
        self.save_step(4, {"country": "Nigeria", "region": "Lagos", "district": "Ikeja"})
        draft.refresh_from_db()
        self.assertEqual(draft.data.get("timezone"), "America/New_York")

        # User changes country to Kenya -> manual override is STILL preserved!
        self.save_step(4, {"country": "Kenya", "region": "Nairobi"})
        draft.refresh_from_db()
        self.assertEqual(draft.data.get("timezone"), "America/New_York")

    def test_timezone_survives_save_and_resume(self):
        self.save_step(1, {"language": "en", "timezone": "UTC", "reading": "standard"})
        self.save_step(2, {"full_name": "Kwame Nkrumah"})
        self.save_step(3, {"network": "WGMN", "eligibility": "pending", "eligibility_confirmed": "on"})
        self.save_step(4, {"country": "Ghana", "region": "Greater Accra"})

        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.data.get("timezone"), "Africa/Accra")

        # Log out and log back in (simulate session resumption)
        self.client.post("/auth/logout/")
        self.login(self.account)

        # Resume from start
        start_resp = self.client.get("/onboarding/")
        self.assertEqual(start_resp.status_code, 302)

        # Step 1 form reflects the persisted timezone
        step1_page = self.client.get("/onboarding/1/")
        self.assertEqual(step1_page.context["form"].initial["timezone"], "Africa/Accra")

        # Records tab displays the persisted timezone
        records_page = self.client.get("/onboarding/4/?tab=records")
        self.assertEqual(records_page.context["user_timezone"], "Africa/Accra")
        self.assertContains(records_page, "Africa/Accra")

    def test_history_timeline_dates_use_active_timezone(self):
        # Set up a draft with Africa/Nairobi (UTC+3)
        self.save_step(1, {"language": "en", "timezone": "UTC", "reading": "standard"})
        self.save_step(2, {"full_name": "Wangari Maathai"})
        self.save_step(3, {"network": "WGMN", "eligibility": "pending", "eligibility_confirmed": "on"})
        self.save_step(4, {"country": "Kenya", "region": "Nairobi"})

        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.data.get("timezone"), "Africa/Nairobi")

        # Request history tab
        history_page = self.client.get("/onboarding/4/?tab=history")
        self.assertEqual(history_page.status_code, 200)

        # All events rendered in history tab must show the +03:00 offset (EAT)
        self.assertContains(history_page, "+03:00")
        self.assertNotContains(history_page, "+00:00")
