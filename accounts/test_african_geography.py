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
        self.assertEqual(cleaned["country_id"], "KEN")
        self.assertEqual(cleaned["country_iso3"], "KEN")
        self.assertEqual(cleaned["country_iso2"], "KE")
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
        self.assertEqual(draft.data["country_id"], "KEN")
        self.assertEqual(draft.data["country_iso3"], "KEN")
        self.assertEqual(draft.data["country_iso2"], "KE")
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
        self.assertEqual(draft.data["country_id"], "ZAF")
        self.assertEqual(draft.data["country_iso3"], "ZAF")
        self.assertEqual(draft.data["country_iso2"], "ZA")
        self.assertEqual(draft.data["region"], "Gauteng")
        self.assertEqual(draft.data["region_id"], "ZA-GP")
        self.assertEqual(draft.data["community_cluster"], "Johannesburg Central")

    def test_step_4_back_and_forward_saves_and_preserves_lga(self):
        # Steps 1 to 3
        self.save(1, {"language": "en", "timezone": "Africa/Lagos", "reading": "standard"}, revision=0)
        self.save(2, {"full_name": "Funmilayo Ransome-Kuti", "preferred_name": "Funmilayo"}, revision=1)
        self.save(3, {"network": "WGMN", "eligibility": "pending", "eligibility_confirmed": "on"}, revision=2)

        # On Step 4, user selects Country, State, and LGA, then navigates back to Step 3
        back_res = self.client.post("/onboarding/4/", {
            "revision": 3,
            "action": "back",
            "country": "Nigeria",
            "region": "Delta",
            "district": "Aniocha North",
            "community_cluster": "Delta West Cluster",
        })
        self.assertRedirects(back_res, "/onboarding/3/")

        # Verify draft preserved the LGA and all fields
        draft = OnboardingDraft.objects.get(account=self.account)
        self.assertEqual(draft.data.get("district"), "Aniocha North")
        self.assertEqual(draft.data.get("region"), "Delta")
        self.assertEqual(draft.data.get("country"), "Nigeria")
        self.assertEqual(draft.data.get("community_cluster"), "Delta West Cluster")

        # Now navigate forward from Step 3 to Step 4
        forward_step3 = self.client.post("/onboarding/3/", {
            "revision": draft.revision,
            "action": "continue",
            "network": "WGMN",
            "eligibility": "pending",
            "eligibility_confirmed": "on",
        })
        self.assertRedirects(forward_step3, "/onboarding/4/")

        # GET Step 4 and verify LGA is pre-populated in the HTML form
        page4 = self.client.get("/onboarding/4/")
        self.assertEqual(page4.status_code, 200)
        self.assertContains(page4, 'value="Aniocha North" selected')

        # Now save and continue to Step 5
        draft.refresh_from_db()
        cont_res = self.client.post("/onboarding/4/", {
            "revision": draft.revision,
            "action": "continue",
            "country": "Nigeria",
            "region": "Delta",
            "district": "Aniocha North",
            "community_cluster": "Delta West Cluster",
        })
        self.assertRedirects(cont_res, "/onboarding/5/")

        # On Step 5, navigate back to Step 4
        draft.refresh_from_db()
        back_step5 = self.client.post("/onboarding/5/", {
            "revision": draft.revision,
            "action": "back",
        })
        self.assertRedirects(back_step5, "/onboarding/4/")

        # Step 4 still preserves the LGA
        draft.refresh_from_db()
        self.assertEqual(draft.data.get("district"), "Aniocha North")
        page4_again = self.client.get("/onboarding/4/")
        self.assertContains(page4_again, 'value="Aniocha North" selected')

    def test_kaduna_giwa_advances_when_policy_has_unrelated_chapters(self):
        # Policy with only Lagos Ikeja chapter (mimicking staging environment)
        staging_policy = {
            'version': 'staging-v1', 'approval_reference': 'STAGING-APP',
            'privacy_notice': 'Notice', 'review_role': 'reviewer', 'review_function': 'onboarding',
            'eligibility': [{'code': 'adult', 'label': 'Adult', 'network': 'WGMN', 'basis': 'Attestation'}],
            'homes': [
                {'code': 'chapter-1', 'label': 'Lagos Chapter (Ikeja)', 'network': 'WGMN', 'country': 'Nigeria', 'region': 'Lagos', 'district': 'Ikeja', 'kind': 'chapter'},
            ],
        }
        with self.settings(WDOS_ONBOARDING_POLICY=staging_policy):
            # Steps 1 to 3
            self.save(1, {"language": "en", "timezone": "Africa/Lagos", "reading": "standard"}, revision=0)
            self.save(2, {"full_name": "Amina Mohammed", "preferred_name": "Amina"}, revision=1)
            self.save(3, {"network": "WGMN", "eligibility": "pending", "eligibility_confirmed": "on"}, revision=2)

            # Step 4: Valid LGA in Kaduna (Giwa) advances without "More information needed"
            res = self.client.post("/onboarding/4/", {
                "revision": 3,
                "action": "continue",
                "country": "Nigeria",
                "region": "Kaduna",
                "district": "Giwa",
                "community_cluster": "Giwa Central",
            })
            self.assertRedirects(res, "/onboarding/5/")

            draft = OnboardingDraft.objects.get(account=self.account)
            self.assertEqual(draft.data.get("country"), "Nigeria")
            self.assertEqual(draft.data.get("region"), "Kaduna")
            self.assertEqual(draft.data.get("district"), "Giwa")

            # Invalid LGA in Kaduna fails validation
            invalid_res = self.client.post("/onboarding/4/", {
                "revision": draft.revision,
                "action": "continue",
                "country": "Nigeria",
                "region": "Kaduna",
                "district": "NonexistentDistrict",
            })
            self.assertEqual(invalid_res.status_code, 422)
            self.assertContains(invalid_res, "More information needed", status_code=422)

    def test_local_connection_and_verification_basis_are_disabled_with_clear_readonly_states(self):
        # Step 3 check: verification_basis is disabled, has read-only badge and explanatory help text
        page3 = self.client.get("/onboarding/3/")
        self.assertEqual(page3.status_code, 200)
        form3 = page3.context["form"]
        self.assertTrue(form3.fields["verification_basis"].disabled)
        self.assertIn("System assigned based on your selected eligibility tier", form3.fields["verification_basis"].help_text)
        self.assertContains(page3, 'id="id_verification_basis"')
        self.assertContains(page3, 'name="verification_basis"')
        self.assertContains(page3, 'disabled')
        self.assertContains(page3, "field-readonly-badge")
        self.assertContains(page3, "Read-only")
        self.assertContains(page3, "System assigned based on your selected eligibility tier")

        # Step 4 check: local_home is disabled, has read-only badge and explanatory help text
        page4 = self.client.get("/onboarding/4/")
        self.assertEqual(page4.status_code, 200)
        form4 = page4.context["form"]
        self.assertTrue(form4.fields["local_home"].disabled)
        self.assertIn("Automatically assigned based on your location", form4.fields["local_home"].help_text)
        self.assertContains(page4, 'id="id_local_home"')
        self.assertContains(page4, 'name="local_home"')
        self.assertContains(page4, 'disabled')
        self.assertContains(page4, "field-readonly-badge")
        self.assertContains(page4, "Read-only")
        self.assertContains(page4, "Automatically assigned based on your location")

    def test_all_nigerian_states_and_774_lgas_present_in_locations_and_geo_data(self):
        from .onboarding_forms import NIGERIA_LOCATIONS, get_nigeria_lgas
        from .african_geography import AFRICAN_COUNTRIES
        ng_regions = [r[1] for r in AFRICAN_COUNTRIES["Nigeria"]["regions"]]
        self.assertEqual(len(ng_regions), 37)
        for state in ng_regions:
            lgas = get_nigeria_lgas(state)
            self.assertTrue(len(lgas) > 0, f"State {state} should have LGAs")

        # Verify Akwa Ibom has 31 LGAs including Uyo, Eket, Ikot Ekpene
        akwa_ibom_lgas = get_nigeria_lgas("Akwa Ibom")
        self.assertEqual(len(akwa_ibom_lgas), 31)
        self.assertIn("Uyo", akwa_ibom_lgas)
        self.assertIn("Eket", akwa_ibom_lgas)
        self.assertIn("Ikot Ekpene", akwa_ibom_lgas)

        # Total canonical LGAs across all 37 regions must be 774
        canonical_states = [r[1] for r in AFRICAN_COUNTRIES["Nigeria"]["regions"]]
        total_lgas = sum(len(NIGERIA_LOCATIONS[s]) for s in canonical_states)
        self.assertEqual(total_lgas, 774)

        # GET /onboarding/4/ contains Nigeria districts with Akwa Ibom in geo-data
        page4 = self.client.get("/onboarding/4/")
        self.assertEqual(page4.status_code, 200)
        self.assertContains(page4, "Akwa Ibom")
        self.assertContains(page4, "Uyo")

    def test_step_4_akwa_ibom_populates_lgas_and_saves_valid_submission(self):
        # Steps 1 to 3
        self.save(1, {"language": "en", "timezone": "Africa/Lagos", "reading": "standard"}, revision=0)
        self.save(2, {"full_name": "Idris Elba", "preferred_name": "Idris"}, revision=1)
        self.save(3, {"network": "WGMN", "eligibility": "pending", "eligibility_confirmed": "on"}, revision=2)

        # GET Step 4 with Akwa Ibom initial data
        from .onboarding_forms import GeographyForm
        form = GeographyForm(initial={"country": "Nigeria", "region": "Akwa Ibom"})
        district_choices = [c[0] for c in form.fields["district"].choices]
        self.assertIn("Uyo", district_choices)
        self.assertIn("Eket", district_choices)

        # Step 4 save with Nigeria + Akwa Ibom + Uyo
        draft = OnboardingDraft.objects.get(account=self.account)
        response = self.save(
            4,
            {
                "country": "Nigeria",
                "region": "Akwa Ibom",
                "district": "Uyo",
                "community_cluster": "Uyo Central Cluster",
            },
            revision=draft.revision,
        )
        self.assertRedirects(response, "/onboarding/5/")

        # Verify draft saved Akwa Ibom and Uyo without 422 error
        draft.refresh_from_db()
        self.assertEqual(draft.data["country"], "Nigeria")
        self.assertEqual(draft.data["region"], "Akwa Ibom")
        self.assertEqual(draft.data["district"], "Uyo")
        self.assertEqual(draft.data["community_cluster"], "Uyo Central Cluster")

        # Navigate back from Step 5 to Step 4
        back_res = self.client.post("/onboarding/5/", {
            "revision": draft.revision,
            "action": "back",
        })
        self.assertRedirects(back_res, "/onboarding/4/")

        # Verify LGA is preserved in draft and in pre-populated HTML
        draft.refresh_from_db()
        self.assertEqual(draft.data.get("district"), "Uyo")
        page4 = self.client.get("/onboarding/4/")
        self.assertEqual(page4.status_code, 200)
        self.assertContains(page4, 'value="Uyo" selected')

    def test_geography_catalogue_completeness_and_validation(self):
        from .geography_catalogue import check_geography_completeness, AFRICAN_GEOGRAPHY_CATALOGUE
        result = check_geography_completeness()
        self.assertTrue(result["valid"], f"Geography catalogue completeness errors: {result['errors']}")
        self.assertEqual(result["country_count"], 55)
        self.assertEqual(len(result["errors"]), 0)
        self.assertGreaterEqual(result["total_level1"], 800)
        self.assertGreaterEqual(result["total_level2"], 900)

        # Check metadata for specific sources
        self.assertEqual(AFRICAN_GEOGRAPHY_CATALOGUE["NGA"]["source"], "UN OCHA/HDX COD-AB")
        self.assertEqual(AFRICAN_GEOGRAPHY_CATALOGUE["DZA"]["source"], "geoBoundaries gbOpen")
        self.assertEqual(AFRICAN_GEOGRAPHY_CATALOGUE["CPV"]["source"], "GeoNames")

    def test_catalogue_database_import_and_models(self):
        from .geography_catalogue import import_catalogue_to_database
        from .models import CountryCatalogue, AdministrativeDivision
        stats = import_catalogue_to_database()
        self.assertEqual(stats["total_countries"], 55)
        self.assertEqual(CountryCatalogue.objects.count(), 55)
        self.assertGreaterEqual(AdministrativeDivision.objects.filter(level=1).count(), 800)
        self.assertGreaterEqual(AdministrativeDivision.objects.filter(level=2).count(), 900)

        nga = CountryCatalogue.objects.get(iso3="NGA")
        self.assertEqual(nga.name, "Nigeria")
        self.assertEqual(nga.admin1_label, "State / FCT")
        self.assertEqual(nga.admin2_label, "Local Government Area (LGA)")
        self.assertTrue(nga.level2_reliable)

    def test_unlisted_subdivision_saves_and_flags_data_improvement(self):
        # Steps 1 to 3
        self.save(1, {"language": "en", "timezone": "Africa/Nairobi", "reading": "standard"}, revision=0)
        self.save(2, {"full_name": "Wangari Muta", "preferred_name": "Wangari"}, revision=1)
        self.save(3, {"network": "WGMN", "eligibility": "pending", "eligibility_confirmed": "on"}, revision=2)

        draft = OnboardingDraft.objects.get(account=self.account)
        from .models import DataImprovementFlag

        # Submit Step 4 with explicit "Not listed, I will type it" and custom subdivision name
        res = self.client.post("/onboarding/4/", {
            "revision": draft.revision,
            "action": "continue",
            "country": "Kenya",
            "region": "Uasin Gishu",
            "district": "__not_listed__",
            "district_custom": "Sergoit Rural Sub-County",
            "district_not_listed": "true",
            "community_cluster": "Eldoret Cluster",
        })
        self.assertRedirects(res, "/onboarding/5/")

        # Verify draft metadata
        draft.refresh_from_db()
        self.assertEqual(draft.data["country"], "Kenya")
        self.assertEqual(draft.data["country_iso3"], "KEN")
        self.assertEqual(draft.data["region"], "Uasin Gishu")
        self.assertEqual(draft.data["region_id"], "KE-44")
        self.assertEqual(draft.data["district"], "Sergoit Rural Sub-County")
        self.assertEqual(draft.data["district_not_listed"], True)
        self.assertEqual(draft.data["data_improvement_flag"], True)
        self.assertIn("Sergoit Rural Sub-County", draft.data.get("data_improvement_note", ""))
        self.assertEqual(draft.data["geography_source"], "UN OCHA/HDX COD-AB")

        # Verify DataImprovementFlag database record
        flags = DataImprovementFlag.objects.filter(country_iso3="KEN", unlisted_subdivision="Sergoit Rural Sub-County")
        self.assertTrue(flags.exists())
        flag = flags.first()
        self.assertEqual(flag.region_name, "Uasin Gishu")
        self.assertEqual(flag.region_id, "KE-44")
        self.assertEqual(flag.unit_type, "Sub-county")
        self.assertEqual(flag.status, "pending")

    def test_step_4_reliable_level2_choices_for_multiple_african_countries(self):
        from .onboarding_forms import GeographyForm
        # Kenya Nairobi has subcounties like Westlands, Kibra, Lang'ata
        ke_form = GeographyForm(initial={"country": "Kenya", "region": "Nairobi"})
        ke_choices = [c[0] for c in ke_form.fields["district"].choices]
        self.assertIn("Westlands", ke_choices)
        self.assertIn("Langata", ke_choices)
        self.assertIn("__not_listed__", ke_choices)

        # South Africa Gauteng has City of Johannesburg, City of Tshwane
        za_form = GeographyForm(initial={"country": "South Africa", "region": "Gauteng"})
        za_choices = [c[0] for c in za_form.fields["district"].choices]
        self.assertIn("City of Johannesburg", za_choices)
        self.assertIn("City of Tshwane", za_choices)
        self.assertIn("__not_listed__", za_choices)

        # Ghana Greater Accra has Accra Metropolitan, Tema Metropolitan
        gh_form = GeographyForm(initial={"country": "Ghana", "region": "Greater Accra"})
        gh_choices = [c[0] for c in gh_form.fields["district"].choices]
        self.assertIn("Accra Metropolitan", gh_choices)
        self.assertIn("Tema Metropolitan", gh_choices)
        self.assertIn("__not_listed__", gh_choices)




