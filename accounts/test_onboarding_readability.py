"""Readability, contrast, typography scale, keyboard focus, and responsive reflow tests.

Verifies WCAG contrast, touch target dimensions, font scaling across desktop and mobile,
and error/helper message presentation across Stage 3 onboarding and shared foundation UI.
"""
from pathlib import Path
import re
from django.conf import settings
from django.test import TestCase, override_settings
from . import test_flows as helpers


def srgb_channel_to_linear(c):
    c_norm = c / 255.0
    return c_norm / 12.92 if c_norm <= 0.03928 else ((c_norm + 0.055) / 1.055) ** 2.4


def relative_luminance(hex_str):
    hex_str = hex_str.lstrip('#')
    if len(hex_str) == 3:
        hex_str = ''.join([ch * 2 for ch in hex_str])
    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)
    return (
        0.2126 * srgb_channel_to_linear(r)
        + 0.7152 * srgb_channel_to_linear(g)
        + 0.0722 * srgb_channel_to_linear(b)
    )


def contrast_ratio(hex1, hex2):
    l1 = relative_luminance(hex1)
    l2 = relative_luminance(hex2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


@override_settings(
    PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'],
    STORAGES={'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}},
)
class OnboardingReadabilityTests(TestCase):
    password = helpers.AuthFlows.password
    create = helpers.AuthFlows.create
    login = helpers.AuthFlows.login

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        static_dir = Path(settings.BASE_DIR) / 'accounts' / 'static' / 'accounts'
        cls.design_css = (static_dir / 'design.css').read_text(encoding='utf-8')
        cls.onboarding_css = (static_dir / 'onboarding.css').read_text(encoding='utf-8')

    def setUp(self):
        self.account = self.create()
        self.login(self.account)

    def test_shared_design_tokens_defined_in_root(self):
        """Tokens establish consistent typography, colors, and controls on :root."""
        required_tokens = [
            '--pink:#d4006a',
            '--green:#7cb518',
            '--ink:#1e1822',
            '--muted:#524956',
            '--color-ink:#1e1822',
            '--color-body:#2d2531',
            '--color-muted:#524956',
            '--color-label:#1e1822',
            '--color-border:#dfd9e2',
            '--color-error:#9b164b',
            '--color-error-bg:#fff0f3',
            '--color-error-border:#f8ccd7',
            '--color-focus:#7cb518',
            '--font-size-base:0.875rem',
            '--line-height-normal:1.5',
            '--control-min-height:44px',
            '--focus-ring:3px solid #7cb518',
        ]
        for token in required_tokens:
            self.assertIn(token, self.design_css, f"Expected design token '{token}' in design.css :root")

    def test_color_contrast_meets_wcag_standards(self):
        """Colors used for text, labels, errors, and muted helpers meet WCAG standards."""
        # Body / ink on white background (WCAG AAA requires >= 7:1)
        ink_contrast = contrast_ratio('#1e1822', '#ffffff')
        self.assertGreater(ink_contrast, 7.0, f"Ink contrast {ink_contrast:.2f}:1 is below 7:1")

        # Muted helper text on white background (WCAG AAA requires >= 7:1)
        muted_contrast = contrast_ratio('#524956', '#ffffff')
        self.assertGreater(muted_contrast, 7.0, f"Muted contrast {muted_contrast:.2f}:1 is below 7:1")

        # Validation error message on error background (#fff0f3) (WCAG AA requires >= 4.5:1)
        error_contrast = contrast_ratio('#9b164b', '#fff0f3')
        self.assertGreater(error_contrast, 4.5, f"Error contrast {error_contrast:.2f}:1 is below 4.5:1")

        # Disabled text on disabled input background (#f2eff3)
        disabled_contrast = contrast_ratio('#5a505e', '#f2eff3')
        self.assertGreater(disabled_contrast, 4.5, f"Disabled contrast {disabled_contrast:.2f}:1 is below 4.5:1")

        # Table header text (#433847) on table header background (#faf9fb)
        th_contrast = contrast_ratio('#433847', '#faf9fb')
        self.assertGreater(th_contrast, 7.0, f"Table header contrast {th_contrast:.2f}:1 is below 7:1")

    def test_body_text_maintains_comfortable_size_on_desktop_and_mobile(self):
        """Body text must remain 14px on both desktop and mobile viewports."""
        self.assertIn('body{margin:0;color:var(--ink);background:var(--canvas);font:14px/1.6', self.design_css)
        self.assertIn('@media(max-width:600px){body{font-size:14px', self.design_css)
        self.assertNotIn('body{font-size:13px}', self.design_css)

    def test_form_field_label_readability(self):
        """Form field labels must have font-size >= 13px, font-weight 650, and comfortable margin."""
        self.assertIn(
            '.field label{display:block;font-size:13px;font-weight:650;margin-bottom:8px;line-height:1.4;color:var(--color-ink,#1e1822)}',
            self.design_css,
        )
        self.assertIn('.field label{display:block;font-size:13px;font-weight:650', self.onboarding_css)

    def test_helper_text_readability_and_contrast(self):
        """Helper text must be at least 12px with relaxed line-height and AAA contrast."""
        self.assertIn(
            '.field small{display:block;color:var(--muted,#524956);font-size:12px;margin-top:6px;line-height:1.5;font-weight:450;overflow-wrap:break-word}',
            self.onboarding_css,
        )

    def test_error_list_alert_box_styling(self):
        """Validation errors must render as accessible, distinct alert blocks."""
        self.assertIn('.errorlist{list-style:none;margin:8px 0 0;padding:8px 12px;background:#fff0f3;border:1px solid #f8ccd7', self.onboarding_css)
        self.assertIn('color:#9b164b;font-size:13px;font-weight:600;line-height:1.45', self.onboarding_css)
        self.assertIn('display:flex;flex-direction:column;gap:4px;overflow-wrap:break-word}', self.onboarding_css)

    def test_interactive_controls_touch_targets_and_font_sizes(self):
        """Inputs, dropdown triggers, and buttons must satisfy min-height 44px and comfortable font sizing."""
        # Standard input
        self.assertIn('.field input:not([type=checkbox]):not([type=file]){', self.onboarding_css)
        self.assertIn('min-height:44px;', self.onboarding_css)
        self.assertIn('font-size:13.5px;line-height:1.5', self.onboarding_css)
        # Searchable select trigger
        self.assertIn('.searchable-select-trigger{width:100%;min-height:44px', self.onboarding_css)
        self.assertIn('font-size:13.5px;line-height:1.5', self.onboarding_css)
        # Searchable select option
        self.assertIn('.searchable-select-option{display:flex;align-items:center;justify-content:space-between;padding:9px 12px;border-radius:6px;font-size:13px;color:#1e1822;cursor:pointer;user-select:none;transition:background-color 0.12s ease,color 0.12s ease;min-height:38px;box-sizing:border-box;line-height:1.4}', self.onboarding_css)
        # Buttons
        self.assertIn('.btn{display:inline-flex;justify-content:center;align-items:center;gap:8px;border:1px solid var(--line);background:white;border-radius:9px;min-height:44px;padding:10px 18px;color:var(--ink);font-weight:650;font-size:13px;line-height:1.4', self.design_css)

    def test_keyboard_focus_indicators_are_prominent_and_consistent(self):
        """All interactive elements must display the high-contrast 3px outline on :focus-visible."""
        self.assertIn(
            '.input:focus-visible,button:focus-visible,a:focus-visible,select:focus-visible,textarea:focus-visible,[tabindex]:focus-visible,.checkbox-control:focus-within{outline:3px solid #7cb518;outline-offset:2px}',
            self.onboarding_css,
        )
        self.assertIn(
            '.searchable-select-trigger:focus-visible,.searchable-select.is-open .searchable-select-trigger{outline:3px solid #7cb518;outline-offset:2px;background:#ffffff;border-color:#d4006a}',
            self.onboarding_css,
        )
        self.assertIn(
            '.field input:not([type=checkbox]):not([type=file]):not(:disabled):focus{outline:3px solid #7cb518;outline-offset:2px;background:#ffffff;border-color:#d4006a}',
            self.onboarding_css,
        )

    def test_disabled_fields_have_clear_state_and_readable_badge(self):
        """Disabled fields must display not-allowed cursor and high-contrast badge."""
        self.assertIn(
            '.field input:disabled,.field input[disabled]{background:#f2eff3 !important;border-color:#ded7e1 !important;color:#5a505e !important;cursor:not-allowed !important;opacity:0.95',
            self.onboarding_css,
        )
        self.assertIn(
            '.field-readonly-badge{display:inline-flex;align-items:center;gap:5px;font-size:11px;font-weight:600;color:#433947;background:#eee8f0;border:1px solid #d9d0dc;padding:2px 9px',
            self.onboarding_css,
        )

    def test_tables_typography_and_readability(self):
        """Table headers must be at least 11px uppercase and table cells at least 13px with relaxed line height."""
        self.assertIn(
            'th{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:#433847;text-align:left;padding:12px 12px;background:#faf9fb;font-weight:700;line-height:1.4}',
            self.design_css,
        )
        self.assertIn(
            'td{padding:14px 12px;border-bottom:1px solid #efedf1;font-size:13px;vertical-align:middle;overflow-wrap:break-word;line-height:1.55;color:#1e1822}',
            self.design_css,
        )

    def test_responsive_reflow_safeguards_at_narrow_viewports(self):
        """Form fields and containers must collapse gracefully without fixed overflow at 320px width."""
        self.assertIn('.field{min-width:0;overflow-wrap:break-word}', self.onboarding_css)
        self.assertIn('@media(max-width:600px)', self.onboarding_css)
        self.assertIn('.fields{grid-template-columns:1fr;gap:16px}', self.onboarding_css)

    def test_onboarding_screens_render_readability_improvements(self):
        """Verify rendered HTML on onboarding steps includes readable labels, helper texts, and error lists."""
        # Step 2: Profile Form
        response = self.client.get('/onboarding/2/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<label for="id_full_name">Full name</label>')
        self.assertContains(response, '<label for="id_email">Email address<span class="field-readonly-badge">')
        self.assertContains(response, 'Read-only')

        # Invalid submission produces styled error list
        error_resp = self.client.post('/onboarding/2/', {'revision': 0, 'full_name': ''})
        self.assertEqual(error_resp.status_code, 422)
        self.assertContains(error_resp, 'class="errorlist"', status_code=422)
        self.assertContains(error_resp, 'This field is required.', status_code=422)

        # Step 3: Network Form (Disabled verification basis)
        response_step3 = self.client.get('/onboarding/3/')
        self.assertEqual(response_step3.status_code, 200)
        self.assertContains(response_step3, '<label for="id_verification_basis">Verification basis<span class="field-readonly-badge">')
        self.assertContains(response_step3, 'id="id_verification_basis_helptext"')
        self.assertContains(response_step3, 'System assigned based on your selected eligibility tier. This field cannot be edited.')

        # Step 4: Geography Form (Disabled local home & editable community cluster)
        response_step4 = self.client.get('/onboarding/4/')
        self.assertEqual(response_step4.status_code, 200)
        self.assertContains(response_step4, '<label for="id_community_cluster">Community cluster</label>')
        self.assertContains(response_step4, 'id="id_community_cluster_helptext"')
        self.assertContains(response_step4, 'Your local community cluster or neighborhood')
        self.assertContains(response_step4, '<label for="id_local_home">Local connection<span class="field-readonly-badge">')
        self.assertContains(response_step4, 'Automatically assigned based on your location. This field cannot be edited.')
