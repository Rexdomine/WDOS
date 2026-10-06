"""
Tests for 55 African countries geography, first-level admin divisions,
dynamic labels, stable ID persistence, and Community Cluster free-text field.
"""
from django.test import TestCase, override_settings
from .african_geography import (
    AFRICAN_COUNTRIES,
    get_country,
    get_african_countries_choices,
    get_country_regions,
    find_region_in_country,
)
from .onboarding_forms import GeographyForm
from .models import OnboardingDraft
from . import test_flows as helpers


class AfricanGeographyDataTests(TestCase):
    def test_all_55_african_countries_present(self):
        self.assertEqual(len(AFRICAN_COUNTRIES), 55)

    def test_all_55_countries_have_required_fields(self):
        for name, data in AFRICAN_COUNTRIES.items():
            self.assertIn("code", data, f"Missing code for {name}")
            self.assertIn("name", data, f"Missing name for {name}")
            self.assertIn("admin_label", data, f"Missing admin_label for {name}")
            self.assertIn("local_label", data, f"Missing local_label for {name}")
            self.assertIn("regions", data, f"Missing regions for {name}")

            self.assertEqual(len(data["code"]), 2, f"Code for {name} must be 2 letters")
            self.assertTrue(data["code"].isupper(), f"Code for {name} must be uppercase")
            self.assertTrue(len(data["admin_label"]) > 0, f"admin_label for {name} cannot be empty")
            self.assertTrue(len(data["local_label"]) > 0, f"local_label for {name} cannot be empty")
            self.assertTrue(len(data["regions"]) > 0, f"{name} must have at least one region")

            # Check region tuple structure
            for region in data["regions"]:
                self.assertIsInstance(region, tuple, f"Region {region} in {name} must be a tuple")
                self.assertEqual(len(region), 2, f"Region {region} in {name} must have (code, name)")
                self.assertTrue(len(region[0]) > 0, f"Region code in {name} cannot be empty")
                self.assertTrue(len(region[1]) > 0, f"Region name in {name} cannot be empty")

    def test_country_appropriate_labels(self):
        # Verify specific country-appropriate admin labels
        self.assertEqual(get_country("KE")["admin_label"], "County")
        self.assertEqual(get_country("KE")["local_label"], "Sub-county")

        self.assertEqual(get_country("ZA")["admin_label"], "Province")
        self.assertEqual(get_country("ZA")["local_label"], "District / Municipality")

        self.assertEqual(get_country("GH")["admin_label"], "Region")
        self.assertEqual(get_country("GH")["local_label"], "District")

        self.assertEqual(get_country("EG")["admin_label"], "Governorate")
        self.assertEqual(get_country("EG")["local_label"], "Markaz / District")

        self.assertEqual(get_country("NG")["admin_label"], "State / FCT")
        self.assertEqual(get_country("NG")["local_label"], "Local Government Area (LGA)")

    def test_helper_lookups(self):
        # By ISO code
        ke = get_country("KE")
        self.assertIsNotNone(ke)
        self.assertEqual(ke["name"], "Kenya")

        # By lower ISO code
        ng = get_country("ng")
        self.assertIsNotNone(ng)
        self.assertEqual(ng["name"], "Nigeria")

        # By full name
        za = get_country("South Africa")
        self.assertIsNotNone(za)
        self.assertEqual(za["code"], "ZA")

        # Choices list
        choices = get_african_countries_choices()
        self.assertEqual(len(choices), 55)
        self.assertEqual(choices[0][0], choices[0][1])

        # Country regions helper
        ke_regions = get_country_regions("KE")
        self.assertEqual(len(ke_regions), 47)
        self.assertIn(("Nairobi", "Nairobi"), ke_regions)

        # Find region in country helper
        nairobi = find_region_in_country("KE", "Nairobi")
        self.assertIsNotNone(nairobi)
        self.assertEqual(nairobi["code"], "KE-30")
        self.assertEqual(nairobi["name"], "Nairobi")

        # By region code
        nairobi_code = find_region_in_country("KE", "KE-30")
        self.assertIsNotNone(nairobi_code)
        self.assertEqual(nairobi_code["name"], "Nairobi")

        # Invalid region in Kenya
        invalid = find_region_in_country("KE", "Lagos")
        self.assertIsNone(invalid)


class GeographyFormTests(TestCase):
    def test_form_country_choices_contain_all_55_african_countries(self):
        form = GeographyForm()
        country_choices = [c[0] for c in form.fields["country"].choices if c[0]]
        self.assertGreaterEqual(len(country_choices), 55)
        for country in AFRICAN_COUNTRIES.values():
            self.assertIn(country["name"], country_choices)

    def test_dynamic_labels_and_regions_on_init(self):
        form = GeographyForm(initial={"country": "Kenya"})
        self.assertEqual(form.fields["region"].label, "County")
        self.assertEqual(form.fields["district"].label, "Sub-county")
        region_choices = [r[0] for r in form.fields["region"].choices if r[0]]
        self.assertEqual(len(region_choices), 47)
        self.assertIn("Nairobi", region_choices)
        self.assertIn("Mombasa", region_choices)

    def test_valid_african_country_and_region_clean(self):
        data = {
            "country": "Kenya",
            "region": "Nairobi",
            "community_cluster": "Kilimani Cluster",
        }
        form = GeographyForm(data)
        self.assertTrue(form.is_valid(), form.errors)
        cleaned = form.cleaned_data
        self.assertEqual(cleaned["country"], "Kenya")
        self.assertEqual(cleaned["country_id"], "KE")
        self.assertEqual(cleaned["country_name"], "Kenya")
        self.assertEqual(cleaned["region"], "Nairobi")
        self.assertEqual(cleaned["region_id"], "KE-30")
        self.assertEqual(cleaned["region_name"], "Nairobi")
        self.assertEqual(cleaned["community_cluster"], "Kilimani Cluster")

    def test_mismatched_region_fails_validation(self):
        data = {
            "country": "Kenya",
            "region": "Lagos",
            "community_cluster": "Central Cluster",
        }
        form = GeographyForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("region", form.errors)

    def test_community_cluster_validation_strip_and_length(self):
        # Valid free text with whitespace stripping
        form = GeographyForm({"country": "Ghana", "region": "Greater Accra", "community_cluster": "  Accra Central Cluster  "})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["community_cluster"], "Accra Central Cluster")

        # Blank / omitted community_cluster is allowed
        form_blank = GeographyForm({"country": "Ghana", "region": "Greater Accra", "community_cluster": ""})
        self.assertTrue(form_blank.is_valid(), form_blank.errors)
        self.assertEqual(form_blank.cleaned_data["community_cluster"], "")

        # Less than 2 chars rejected
        form_short = GeographyForm({"country": "Ghana", "region": "Greater Accra", "community_cluster": "A"})
        self.assertFalse(form_short.is_valid())
        self.assertIn("community_cluster", form_short.errors)

        # Characters < or > rejected
        form_xss = GeographyForm({"country": "Ghana", "region": "Greater Accra", "community_cluster": "<cluster>"})
        self.assertFalse(form_xss.is_valid())
        self.assertIn("community_cluster", form_xss.errors)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class OnboardingGeographyIntegrationTests(TestCase):
    password = helpers.AuthFlows.password
    create = helpers.AuthFlows.create
    login = helpers.AuthFlows.login

    def setUp(self):
        self.account = self.create()
        self.login(self.account)

    def save(self, step, data, revision=0):
        return self.client.post(f"/onboarding/{step}/", {"revision": revision, "action": "continue", **data})

    def test_step_4_renders_all_55_countries_and_geo_data(self):
        from django.utils.html import escape
        response = self.client.get("/onboarding/4/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="geo-data"')
        self.assertContains(response, 'name="community_cluster"')
        for country in AFRICAN_COUNTRIES.values():
            self.assertContains(response, f'value="{escape(country["name"])}"')

    def test_step_4_persists_african_geography_stable_ids_and_cluster(self):
        # Step 1-3 setup
        self.save(1, {"language": "en", "timezone": "Africa/Nairobi", "reading": "standard"})
        self.save(2, {"full_name": "Wangari Maathai", "preferred_name": "Wangari"}, revision=1)
        self.save(3, {"network": "WGMN", "eligibility": "pending", "eligibility_confirmed": "on"}, revision=2)

        # Step 4 save with Kenya + Nairobi + Community Cluster
        response = self.save(
            4,
            {
                "country": "Kenya",
                "region": "Nairobi",
                "community_cluster": "Kilimani Community Cluster",
            },
            revision=3,
        )
        self.assertRedirects(response, "/onboarding/5/")

        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.data["country"], "Kenya")
        self.assertEqual(draft.data["country_id"], "KE")
        self.assertEqual(draft.data["country_name"], "Kenya")
        self.assertEqual(draft.data["region"], "Nairobi")
        self.assertEqual(draft.data["region_id"], "KE-30")
        self.assertEqual(draft.data["region_name"], "Nairobi")
        self.assertEqual(draft.data["community_cluster"], "Kilimani Community Cluster")

        # Resume Step 4: check initial form fields and dynamic labels
        page = self.client.get("/onboarding/4/")
        self.assertEqual(page.status_code, 200)
        form = page.context["form"]
        self.assertEqual(form.initial["country"], "Kenya")
        self.assertEqual(form.initial["region"], "Nairobi")
        self.assertEqual(form.initial["community_cluster"], "Kilimani Community Cluster")
        self.assertEqual(form.fields["region"].label, "County")
        self.assertEqual(form.fields["district"].label, "Sub-county")

    def test_step_4_mismatched_region_fails_validation(self):
        response = self.save(
            4,
            {
                "country": "Kenya",
                "region": "Lagos",
                "community_cluster": "Invalid Region Test",
            },
            revision=0,
        )
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "Check the highlighted information", status_code=422)

    def test_step_4_invalid_community_cluster_fails_validation(self):
        response = self.save(
            4,
            {
                "country": "South Africa",
                "region": "Gauteng",
                "community_cluster": "<invalid>",
            },
            revision=0,
        )
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, "Check the highlighted information", status_code=422)

    def test_full_onboarding_pipeline_with_african_geography(self):
        # Steps 1 to 6
        self.save(1, {"language": "en", "timezone": "Africa/Johannesburg", "reading": "standard"}, revision=0)
        self.save(2, {"full_name": "Albertina Sisulu", "preferred_name": "Albertina"}, revision=1)
        self.save(3, {"network": "WGMN", "eligibility": "pending", "eligibility_confirmed": "on"}, revision=2)
        self.save(4, {"country": "South Africa", "region": "Gauteng", "community_cluster": "Johannesburg Central"}, revision=3)
        self.save(5, {"interests": "Community leadership", "skills": "Advocacy", "community_connection": "Local organizer", "availability": "Regular"}, revision=4)
        self.save(6, {"channel": "email"}, revision=5)

        # Step 7 review
        page7 = self.client.get("/onboarding/7/")
        self.assertEqual(page7.status_code, 200)

        # Submit registration
        submit_res = self.client.post("/onboarding/7/", {"revision": 6, "review_confirmed": "on", "action": "continue"})
        self.assertRedirects(submit_res, "/onboarding/8/")

        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.state, "review_needed")
        self.assertEqual(draft.data["country"], "South Africa")
        self.assertEqual(draft.data["country_id"], "ZA")
        self.assertEqual(draft.data["region"], "Gauteng")
        self.assertEqual(draft.data["region_id"], "ZA-GP")
        self.assertEqual(draft.data["community_cluster"], "Johannesburg Central")

