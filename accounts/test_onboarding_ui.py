import io
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from . import test_flows as helpers
from .test_onboarding_submission import TEST_POLICY

@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class OnboardingUITests(TestCase):
    password=helpers.AuthFlows.password
    create=helpers.AuthFlows.create
    login=helpers.AuthFlows.login

    def setUp(self):
        self.account=self.create(); self.login(self.account)

    def test_supported_locale_renders_onboarding_copy_direction_and_persists(self):
        from .locale import LANGUAGES, catalog
        for lang in ('en', 'fr', 'pt', 'ar', 'sw'):
            response = self.client.get('/onboarding/1/?lang=' + lang)
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'lang="' + lang + '"')
            self.assertContains(response, 'dir="' + LANGUAGES[lang]['dir'] + '"')
            self.assertContains(response, catalog(lang)['onb_title_1'])
            self.assertNotContains(response, 'Make WDOS feel like home' if lang != 'en' else '\\x00')
            session = self.client.session
            self.assertEqual(session.get('wdos_language'), lang)

    def test_form_labels_and_choices_render_localized_across_supported_locales(self):
        from .locale import catalog
        expectations = {
            'fr': ('Nom d’usage', 'Photo de profil', 'Texte standard'),
            'pt': ('Nome preferido', 'Foto do perfil', 'Texto padrão'),
            'ar': ('الاسم المفضل', 'صورة الملف الشخصي', 'نص عادي'),
            'sw': ('Jina unalopendelea', 'Picha ya wasifu', 'Maandishi ya kawaida'),
        }
        for lang in ('en', 'fr', 'pt', 'ar', 'sw'):
            response = self.client.get('/onboarding/2/?lang=' + lang)
            self.assertEqual(response.status_code, 200)
            c = catalog(lang)
            self.assertContains(response, c['preferred_name'])
            self.assertContains(response, c['profile_photo'])
            if lang != 'en':
                self.assertNotContains(response, 'Preferred name')
                self.assertNotContains(response, 'Profile photo')
                self.assertContains(response, expectations[lang][0])
                self.assertContains(response, expectations[lang][1])
        response = self.client.get('/onboarding/1/?lang=fr')
        self.assertContains(response, catalog('fr')['reading_standard'])
        self.assertNotContains(response, 'Standard text')

    def test_step_one_language_overwrites_existing_english_cookie_on_redirect(self):
        self.client.cookies['wdos_language'] = 'en'
        response = self.client.post('/onboarding/1/', {
            'revision': 0, 'language': 'fr', 'timezone': 'UTC', 'reading': 'standard',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.cookies['wdos_language'].value, 'fr')
        follow = self.client.get(response['Location'])
        self.assertContains(follow, 'Parlez-nous de vous')


    def test_onboarding_invalid_submission_localizes_error(self):
        self.client.cookies['wdos_language'] = 'fr'
        response = self.client.post('/onboarding/2/', {'revision': 0, 'full_name': ''})
        self.assertEqual(response.status_code, 422)
        self.assertContains(response, 'Ce champ est obligatoire.', status_code=422)

    def test_review_shows_real_summary_and_confirmation(self):
        self.client.post('/onboarding/2/', {'revision':0,'full_name':'Amara Ézè','preferred_name':'Amara'})
        response=self.client.get('/onboarding/7/')
        self.assertContains(response, 'Amara Ézè')
        self.assertContains(response, 'Local home')
        self.assertContains(response, 'Decision context')

    def test_profile_photo_is_private_and_persists(self):
        image=io.BytesIO(); Image.new('RGB',(24,24),'green').save(image,format='PNG')
        response=self.client.post('/onboarding/2/', {'revision':0,'full_name':'Amara Ézè','photo':SimpleUploadedFile('photo.png',image.getvalue(),content_type='image/png')})
        self.assertEqual(response.status_code,302)
        photo=self.client.get('/onboarding/photo/')
        self.assertEqual(photo.status_code,200)
        self.assertEqual(photo['Content-Type'],'image/png')
        self.assertEqual(photo['Cache-Control'],'no-store, private')
        self.client.logout()
        self.assertEqual(self.client.get('/onboarding/photo/').status_code,403)

    def test_invalid_photo_retains_profile_without_storing_file(self):
        response=self.client.post('/onboarding/2/', {'revision':0,'full_name':'Amara Ézè','photo':SimpleUploadedFile('photo.png',b'not an image',content_type='image/png')})
        self.assertEqual(response.status_code,422)
        self.assertEqual(self.client.get('/onboarding/2/').context['form'].initial['full_name'],'Amara Ézè')
        self.assertEqual(self.client.get('/onboarding/photo/').status_code,404)

    @override_settings(WDOS_ONBOARDING_POLICY=TEST_POLICY)
    def test_configured_consent_notice_is_readable_not_just_a_checkbox(self):
        response=self.client.get('/onboarding/privacy/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,TEST_POLICY['privacy_notice'])
        self.assertContains(self.client.get('/onboarding/6/'),'/onboarding/privacy/')

    def test_history_tab_uses_real_saved_history(self):
        self.client.post('/onboarding/2/', {'revision':0,'full_name':'Amara Ézè'})
        response=self.client.get('/onboarding/2/?tab=history')
        self.assertContains(response,'Saved for later')
        self.assertContains(response,'data-history-event=')

    def test_authenticated_status_exposes_onboarding_entry(self):
        self.assertContains(self.client.get('/auth/status/'),'/onboarding/')

    def test_post_back_from_review_never_submits(self):
        response=self.client.post('/onboarding/7/',{'revision':0,'action':'back'})
        self.assertRedirects(response,'/onboarding/6/')

    def test_get_first_use_never_accepts_or_grants_membership(self):
        self.assertRedirects(self.client.get('/onboarding/8/'),'/onboarding/1/')
        self.assertEqual(self.account.accessgrant_set.count(),0)

    def test_partial_and_shell_use_catalog_translations(self):
        from .locale import catalog
        self.client.cookies['wdos_language'] = 'fr'
        review = self.client.get('/onboarding/7/')
        self.assertContains(review, catalog('fr')['onb_review_membership'])
        self.assertContains(review, catalog('fr')['onb_before_continue'])
        history = self.client.get('/onboarding/2/?tab=history')
        self.assertContains(history, catalog('fr')['onb_history'])
        shell = self.client.get('/onboarding/1/')
        self.assertContains(shell, catalog('fr')['onb_workspace'])
        self.assertContains(shell, catalog('fr')['onb_search'])
        self.assertNotContains(shell, 'Search WDOS')
