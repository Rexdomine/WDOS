from django.test import SimpleTestCase
from .forms import ResetForm
from .locale import BASE, C, catalog, localize_form, translate


class LocaleCatalogTests(SimpleTestCase):
    def test_all_catalog_keys_are_present_and_distinct(self):
        for lang in ('fr', 'pt', 'ar', 'sw'):
            self.assertEqual(set(BASE), set(C[lang]))
            self.assertTrue(all(C[lang][key] != BASE[key] for key in BASE))
            self.assertFalse(any(value.startswith('[') for value in C[lang].values()))

    def test_static_literals_translate(self):
        literals = ('Welcome back', 'Create account', 'Please wait before trying again.',
                    'Passwords must match.', 'Creating an account does not grant a leadership or HQ role.')
        for lang in ('fr', 'pt', 'ar', 'sw'):
            for text in literals:
                self.assertNotEqual(translate(lang, text), text)

    def test_form_labels_preserve_code_semantics(self):
        form = localize_form(ResetForm(), 'fr')
        self.assertEqual(form.fields['password'].label, catalog('fr')['new_password'])
        self.assertEqual(form.fields['confirm'].label, catalog('fr')['confirm'])
        self.assertNotEqual(form.fields['password'].label, catalog('fr')['password_label'])

    def test_form_errors_are_localized_with_parameters(self):
        from .forms import EmailForm, RegisterForm, MFAForm, VerifyForm, InvitationForm
        for lang in ('fr', 'pt', 'ar', 'sw'):
            c = catalog(lang)
            empty = localize_form(EmailForm({'email': ''}), lang)
            self.assertEqual(list(empty.errors['email']), [c['required_field']])
            invalid = localize_form(EmailForm({'email': 'not-an-email'}), lang)
            self.assertEqual(list(invalid.errors['email']), [c['invalid_email']])
            short = localize_form(RegisterForm({'name': 'Example', 'email': 'a@example.org', 'password': 'a'}), lang)
            self.assertIn(c['too_short'] % {'limit_value': 12, 'show_value': 1}, short.errors['password'])
            for cls, key in ((MFAForm, 'mfa_code'), (VerifyForm, 'code'), (InvitationForm, 'invitation_code')):
                self.assertEqual(localize_form(cls(), lang)['code'].label, c[key])

    def test_user_content_is_not_translated(self):
        self.assertEqual(translate('fr', 'A user supplied name'), 'A user supplied name')
