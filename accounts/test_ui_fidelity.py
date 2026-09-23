import hashlib
from pathlib import Path

from django.test import SimpleTestCase

from .forms import InvitationForm, LoginForm, VerifyForm


class AuthUiFidelityTests(SimpleTestCase):
    root = Path(__file__).resolve().parent.parent
    template = root / 'templates/accounts/auth.html'
    refinements = root / 'accounts/static/accounts/refinements.css'
    canonical_refinements_sha256 = '23a71ec9a1706e503322c68a4979e5350adab5767936ef6d7794d745f9a90326'

    def test_shared_shell_contains_reference_structure(self):
        html = self.template.read_text(encoding='utf-8')
        for text in (
                'network-line', '>WGMN<', '>WNNN<', 'language-picker', 'cream-notice',
                'footer_privacy', 'footer_terms', 'footer_help', 'csrf_token',
                'woddi-logo.png', 'welcome-actions'):
            self.assertIn(text, html)
        self.assertIn("{% url 'accounts:privacy' %}", html)
        self.assertIn("{% url 'accounts:terms' %}", html)
        self.assertIn("{% url 'accounts:help' %}", html)
        self.assertNotIn('Stage 2 review', html)
        self.assertNotIn('AUTH-10', html)
        self.assertNotIn('AUTH-11', html)
        self.assertNotIn('AUTH-12', html)

    def test_reference_refinements_are_not_overridden_by_review_leftovers(self):
        self.assertEqual(
            hashlib.sha256(self.refinements.read_bytes()).hexdigest(),
            self.canonical_refinements_sha256,
        )

    def test_explicit_navigation_avoids_login_self_link_and_restores_registration_link(self):
        html = self.template.read_text(encoding='utf-8')
        login_branch = html.split("{% if screen == 'AUTH-02' %}", 1)[1].split('{% elif', 1)[0]
        self.assertIn("accounts:register", login_branch)
        self.assertNotIn("accounts:login", login_branch)
        registration_branch = html.split("{% elif screen == 'AUTH-03' %}", 1)[1].split('{% elif', 1)[0]
        self.assertIn("accounts:login", registration_branch)
        self.assertIn('already_sign_in', registration_branch)

    def test_invitation_field_order_and_contact_label_match_reference(self):
        form = InvitationForm()
        self.assertEqual(form.field_order, ['code', 'email'])
        self.assertEqual(list(form.fields), ['code', 'email'])
        self.assertEqual(form['email'].label, 'Email on invitation')

    def test_login_remember_and_verification_forms_have_exact_fields(self):
        login = LoginForm()
        self.assertEqual(login.fields['remember'].widget.input_type, 'checkbox')
        self.assertEqual(login.fields['remember'].label, 'Keep me signed in')
        self.assertEqual(list(VerifyForm().fields), ['code'])

    def test_every_primary_control_has_a_leading_arrow_icon(self):
        html = self.template.read_text(encoding='utf-8')
        primary_openings = html.count('class="btn primary')
        self.assertEqual(html.count("{% include 'accounts/arrow.html' %}"), primary_openings)
        self.assertNotIn('→', html)
