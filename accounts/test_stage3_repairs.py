from django.test import TestCase, override_settings
from django.utils.html import escape
from pathlib import Path
import json

import pyotp

from . import services
from .locale import catalog
from .models import Membership, OnboardingConsent, OnboardingDraft, Person


@override_settings(PASSWORD_HASHERS=['django.contrib.auth.hashers.MD5PasswordHasher'])
class Stage3RepairTests(TestCase):
    password = 'a genuinely long WDOS example passphrase!'

    def create_active(self, email):
        account = services.register('Stage Three', email, self.password)
        token, code = services.issue_token(account, 'verify')
        self.assertTrue(services.verify_contact(account.pk, code))
        account.refresh_from_db()
        return account

    def login(self, account):
        return self.client.post('/auth/login/', {'email': account.email, 'password': self.password})

    def test_foundation_uses_persisted_language_when_browser_has_no_locale_cookie(self):
        account = self.create_active('persisted-language@example.org')
        draft = OnboardingDraft.objects.create(
            account=account, state='accepted', next_step=6, data={'language': 'fr'}
        )
        person = Person.objects.create(display_name='Persisted Language Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        self.client.cookies.pop('wdos_language', None)
        session = self.client.session
        session.pop('wdos_language', None)
        session.save()
        response = self.client.get('/foundation/')
        self.assertContains(response, 'lang="fr"')
        self.assertContains(response, catalog('fr')['onb_workspace_title'])

    def test_accepted_membership_login_and_root_open_foundation_shell(self):
        account = self.create_active('accepted-nav@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Accepted Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        response = self.login(account)
        self.assertRedirects(response, '/foundation/')
        foundation = self.client.get('/')
        self.assertRedirects(foundation, '/foundation/')
        shell = self.client.get('/foundation/')
        self.assertContains(shell, 'action="/auth/logout/"')
        self.assertContains(shell, 'method="post"')
        self.assertContains(shell, 'name="csrfmiddlewaretoken"')
        self.assertContains(shell, 'Home')
        self.assertContains(shell, 'My activities')
        self.assertContains(shell, 'Records')
        self.assertContains(shell, 'record-tabs')
        self.assertContains(shell, 'class="actions"')
        self.assertContains(shell, 'overflow-x: hidden')

    def test_foundation_response_is_private_and_uncacheable(self):
        account = self.create_active('foundation-cache@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Cached Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        response = self.client.get('/foundation/')
        self.assertEqual(response['Cache-Control'], 'no-store, private')
        self.assertEqual(response['Referrer-Policy'], 'same-origin')

    def test_foundation_shell_has_styled_layout_and_bound_profile_menu(self):
        account = self.create_active('foundation-controls@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Foundation Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        html = self.client.get('/foundation/').content.decode()
        self.assertIn('data-profile-menu', html)
        self.assertIn('data-profile-trigger', html)
        self.assertIn('data-profile-panel', html)
        self.assertIn('aria-expanded="false"', html)
        self.assertIn('hidden', html)
        self.assertIn('/static/accounts/onboarding.', html)
        css = (Path(__file__).parent / 'static' / 'accounts' / 'design.css').read_text()
        self.assertIn('.foundation-shell', css)
        self.assertIn('.foundation-shell .content', css)

    def test_foundation_rtl_desktop_content_offsets_away_from_right_sidebar(self):
        css = (Path(__file__).parent / 'static' / 'accounts' / 'design.css').read_text()
        self.assertIn('@media(min-width:601px){[dir="rtl"] .foundation-shell .content{margin-left:0;margin-right:232px}}', css)
        self.assertIn('position:fixed;bottom:0;left:0;right:0', css)
        self.assertIn('.foundation-shell .mobile-nav{display:grid', css)

    def test_localization_evidence_commits_current_head_desktop_and_mobile_comparisons(self):
        evidence = Path(__file__).parents[1] / 'docs' / 'stage-03-delivery-evidence.md'
        text = evidence.read_text()
        self.assertIn('7ddcca2e48bca29d9f31b49585093f94b5315485', text)
        for locale in ('en', 'fr', 'pt', 'ar', 'sw'):
            for viewport in ('desktop', 'mobile'):
                capture = evidence.parents[0] / 'stage-03-evidence' / 'captures' / f'foundation-localized-{locale}-{viewport}-7ddcca2.png'
                comparison = evidence.parents[0] / 'stage-03-evidence' / 'comparisons' / f'foundation-localized-{locale}-{viewport}-7ddcca2.png'
                self.assertTrue(capture.is_file(), capture)
                self.assertTrue(comparison.is_file(), comparison)

    def test_foundation_shell_matches_core01_page_hierarchy_without_duplicate_sections(self):
        account = self.create_active('foundation-core01-hierarchy@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='CORE-01 Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Ikeja Chapter'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        html = self.client.get('/foundation/').content.decode()
        self.assertIn('class="pagehead"', html)
        self.assertIn('class="actions"', html)
        self.assertIn('class="tabs"', html)
        self.assertIn('class="grid"', html)
        self.assertIn('class="panel"', html)
        self.assertIn('class="record-summary"', html)
        self.assertIn('related-information-panel', html)
        self.assertNotIn('class="hero-card"', html)
        self.assertNotIn('id="next-action"', html)
        self.assertNotIn('id="support-links"', html)

    def test_foundation_record_tabs_have_keyboard_and_panel_contract(self):
        account = self.create_active('foundation-record-tabs@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Tab Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        html = self.client.get('/foundation/').content.decode()
        self.assertIn('data-record-tab', html)
        self.assertIn('aria-controls="overview-panel"', html)
        self.assertIn('aria-controls="records-panel"', html)
        self.assertIn('aria-controls="history-panel"', html)
        self.assertIn('id="overview-panel"', html)
        self.assertIn('id="records-panel"', html)
        self.assertIn('id="history-panel"', html)
        script = (Path(__file__).parent / 'static' / 'accounts' / 'onboarding.js').read_text()
        self.assertIn('initializeRecordTabs', script)
        self.assertIn('ArrowRight', script)
        self.assertIn('aria-selected', script)

    def test_foundation_navigation_maps_home_and_named_controls_to_matching_states(self):
        script = (Path(__file__).parent / 'static' / 'accounts' / 'onboarding.js').read_text()
        template = (Path(__file__).parents[1] / 'templates' / 'foundation' / 'app_shell.html').read_text()
        self.assertIn("window.location.hash === '#workspace-home'", script)
        for target in ('meetings-panel', 'messages-panel', 'settings-panel', 'help-panel'):
            self.assertIn(f'id=\"{target}\"', template)
            self.assertIn(f'data-workspace-target=\"{target}\"', template)
        self.assertIn('data-workspace-panel', template)

    def test_foundation_named_panels_have_a_real_hidden_display_override(self):
        css = (Path(__file__).parent / 'static' / 'accounts' / 'design.css').read_text()
        self.assertIn('.foundation-shell [hidden]{display:none !important}', css)

    def test_foundation_navigation_syncs_selection_for_named_and_keyboard_states(self):
        script = (Path(__file__).parent / 'static' / 'accounts' / 'onboarding.js').read_text()
        self.assertIn('syncWorkspaceNavigation', script)
        self.assertIn('syncWorkspaceNavigation(panel.id)', script)
        self.assertIn("syncWorkspaceNavigation(tab.getAttribute('aria-controls') ===", script)
        self.assertIn("window.history.replaceState({}, '', tabs[next].hash)", script)

    def test_foundation_tab_evidence_is_bound_to_current_interaction_candidate(self):
        evidence = Path(__file__).parents[1] / 'docs' / 'stage-03-delivery-evidence.md'
        text = evidence.read_text()
        self.assertIn('## Current exact-head tab interaction evidence', text)
        section = text.split('## Current exact-head tab interaction evidence', 1)[1]
        self.assertNotIn('ee70048fe84e06854001e399d92b32ee5f55b2b2', section.split('## ', 1)[0])
        self.assertIn('Implementation candidate:', section)

    def test_foundation_navigation_evidence_contains_distinct_auditable_states(self):
        manifest = Path(__file__).parents[1] / 'docs' / 'stage-03-evidence' / 'manifests' / 'foundation-navigation-ecaa21b.json'
        data = json.loads(manifest.read_text())
        self.assertEqual(data['candidate'], 'ecaa21bdf8fa76a2e3c9a019ffee6faa95b22831')
        self.assertEqual({row['state'] for row in data['captures']}, {'meetings', 'messages', 'home-reset'})
        self.assertEqual(len(data['captures']), 9)
        self.assertEqual(len({row['sha256'] for row in data['captures']}), 9)
        for row in data['captures']:
            self.assertTrue((Path(__file__).parents[1] / row['path']).is_file())

    def test_foundation_navigation_evidence_is_bound_to_final_candidate_and_comparisons(self):
        evidence_root = Path(__file__).parents[1]
        text = (evidence_root / 'docs' / 'stage-03-delivery-evidence.md').read_text()
        section = text.split('### Exact implementation-candidate interaction recapture', 1)[1].split('## Release status', 1)[0]
        self.assertIn('ecaa21bdf8fa76a2e3c9a019ffee6faa95b22831', section)
        for name in (
            'foundation-nav-en-desktop-meetings-ecaa21b.png',
            'foundation-nav-en-desktop-messages-ecaa21b.png',
            'foundation-nav-en-desktop-home-ecaa21b.png',
            'foundation-nav-en-mobile-meetings-ecaa21b.png',
            'foundation-nav-en-mobile-messages-ecaa21b.png',
            'foundation-nav-en-mobile-home-ecaa21b.png',
            'foundation-nav-ar-mobile-meetings-ecaa21b.png',
        ):
            self.assertIn(name, section)
            self.assertTrue((evidence_root / 'docs' / 'stage-03-evidence' / 'captures' / name).is_file(), name)
        for name in (
            'foundation-nav-en-desktop-meetings-ecaa21b.png',
            'foundation-nav-en-mobile-meetings-ecaa21b.png',
            'foundation-nav-ar-mobile-meetings-ecaa21b.png',
        ):
            self.assertTrue((evidence_root / 'docs' / 'stage-03-evidence' / 'comparisons' / name).is_file(), name)

    def test_foundation_record_shortcuts_activate_tabs_and_preserve_overview_related_information(self):
        account = self.create_active('foundation-record-shortcuts@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Shortcut Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        html = self.client.get('/foundation/').content.decode()
        script = (Path(__file__).parent / 'static' / 'accounts' / 'onboarding.js').read_text()
        self.assertIn('window.addEventListener(\"hashchange\"', script)
        self.assertIn('data-record-target', html)
        self.assertIn('data-record-target=\"records-panel\"', html)
        self.assertIn('data-workspace-target=\"meetings-panel\"', html)
        self.assertIn('data-workspace-target=\"messages-panel\"', html)
        self.assertNotIn('id=\"records-panel\" role=\"tabpanel\" aria-labelledby=\"records-tab\" tabindex=\"0\" hidden', html)

    def test_foundation_shell_contains_core01_workspace_hierarchy(self):
        account = self.create_active('foundation-hierarchy@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Hierarchy Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        html = self.client.get('/foundation/').content.decode()
        for landmark in ('overview-panel', 'records-panel', 'history-panel', 'record-tabs'):
            self.assertIn(f'id="{landmark}"', html)

    def test_foundation_shell_does_not_fabricate_unmodeled_workspace_state(self):
        account = self.create_active('foundation-honest-state@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Honest State Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        response = self.client.get('/foundation/')
        self.assertContains(response, 'Active membership')
        self.assertContains(response, 'No activities are recorded yet')
        self.assertNotContains(response, 'Active and in good standing')
        self.assertNotContains(response, '>Available<')

    def test_foundation_shell_uses_approved_two_column_workspace_composition(self):
        account = self.create_active('foundation-two-column@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Two Column Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        html = self.client.get('/foundation/').content.decode()
        self.assertIn('class="grid"', html)
        self.assertIn('class="record-summary"', html)
        self.assertIn('related-information-panel', html)
        self.assertIn('Record tabs', html)

    def test_foundation_mobile_shell_contains_approved_navigation_controls(self):
        account = self.create_active('foundation-mobile-nav@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Mobile Navigation Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        html = self.client.get('/foundation/').content.decode()
        for label, href in (
            ('Home', '#workspace-home'), ('My work', '#records-panel'),
            ('Meetings', '#history-panel'), ('Messages', '#history-panel'), ('More', '#records-panel'),
        ):
            self.assertIn(f'href="{href}"', html)
            self.assertIn(f'>{label}<', html)
        self.assertIn('class="mobile-nav"', html)
        for target in ('workspace-home', 'records-panel', 'history-panel'):
            self.assertIn(f'id="{target}"', html)

    def test_foundation_desktop_navigation_controls_have_matching_destinations(self):
        account = self.create_active('foundation-desktop-nav@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Desktop Navigation Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        html = self.client.get('/foundation/').content.decode()
        for label, href, target in (
            ('My activities', '#records-panel', 'records-panel'),
            ('Meetings &amp; events', '#history-panel', 'history-panel'),
            ('Messages', '#history-panel', 'history-panel'),
            ('Help &amp; support', '#records-panel', 'records-panel'),
            ('Settings', '#records-panel', 'records-panel'),
        ):
            self.assertIn(f'href="{href}"', html)
            self.assertIn(f'>{label}<', html)
            self.assertIn(f'id="{target}"', html)

    def test_foundation_shell_renders_persisted_local_home_label(self):
        account = self.create_active('foundation-local-home@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Local Home Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Lagos Central Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        html = self.client.get('/foundation/').content.decode()
        self.assertIn('Lagos Central Home', html)
        self.assertNotIn('WGMN / Workspace</strong>', html)

    def test_foundation_workspace_actions_have_real_targets(self):
        account = self.create_active('foundation-actions@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Action Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        html = self.client.get('/foundation/').content.decode()
        self.assertIn('id="records-panel"', html)
        self.assertIn('id="history-panel"', html)
        self.assertIn('href="#records-panel"', html)
        self.assertIn('href="#history-panel"', html)

    def test_foundation_logout_uses_persisted_locale_and_direction(self):
        account = self.create_active('accepted-locale@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Localized Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        expected = {'fr': ('fr', 'ltr', 'Se déconnecter'), 'pt': ('pt', 'ltr', 'Terminar sessão'),
                    'ar': ('ar', 'rtl', 'تسجيل الخروج'), 'sw': ('sw', 'ltr', 'Ondoka')}
        for lang, (html_lang, direction, label) in expected.items():
            self.client.cookies['wdos_language'] = lang
            shell = self.client.get('/foundation/')
            self.assertContains(shell, f'<html lang="{html_lang}" dir="{direction}">')
            self.assertContains(shell, f'<span lang="{html_lang}" dir="{direction}">{label}</span>')

    def test_foundation_sidebar_links_preserve_approved_decoration(self):
        css = (Path(__file__).parent / 'static' / 'accounts' / 'design.css').read_text()
        self.assertIn('.foundation-shell .sidebar .navitem{text-decoration:none;', css)

    def test_authenticated_foundation_workspace_copy_uses_each_supported_catalog(self):
        account = self.create_active('localized-foundation@example.org')
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Localized Workspace Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.login(account)
        workspace_keys = (
            'onb_member', 'onb_workspace', 'onb_home', 'onb_activities',
            'onb_records', 'onb_overview', 'onb_history',
            'onb_messages', 'onb_help',
            'onb_workspace_title',
            'onb_support_text', 'onb_my_work', 'onb_meetings_short',
            'onb_more', 'onb_local_connection',
        )
        for lang in ('en', 'fr', 'pt', 'ar', 'sw'):
            self.client.cookies['wdos_language'] = lang
            response = self.client.get('/foundation/')
            html = response.content.decode()
            self.assertContains(response, f'<html lang="{lang}"')
            for key in workspace_keys:
                self.assertIn(escape(catalog(lang)[key]), html, msg=f'{lang} missing {key}')
            if lang != 'en':
                self.assertNotIn('Your workspace', html)
                self.assertNotIn('Your workspace', html)

    def test_status_explainer_is_localized_and_does_not_leak_restricted_identity(self):
        account = self.create_active('private-status@example.org')
        self.login(account)
        for lang in ('en', 'fr', 'pt', 'ar', 'sw'):
            response = self.client.get('/auth/status/?lang=' + lang)
            self.assertContains(response, 'data-status-explainer')
            self.assertContains(response, response.context['status_text'])
            self.assertNotContains(response, account.email)

    def test_status_explainer_accessible_label_uses_each_catalog(self):
        account = self.create_active('localized-status-label@example.org')
        self.login(account)
        for lang in ('en', 'fr', 'pt', 'ar', 'sw'):
            response = self.client.get('/auth/status/?lang=' + lang)
            expected = {
                'en': 'Why am I seeing this status?',
                'fr': 'Pourquoi est-ce que je vois ce statut ?',
                'pt': 'Por que estou vendo este status?',
                'ar': 'لماذا أرى هذه الحالة؟',
                'sw': 'Kwa nini ninaona hali hii?',
            }
            self.assertContains(response, f'aria-label="{expected[lang]}"')

    def test_status_explainer_copy_is_distinct_for_each_supported_locale(self):
        account = self.create_active('distinct-status-explainer@example.org')
        self.login(account)
        for lang in ('en', 'fr', 'pt', 'ar', 'sw'):
            response = self.client.get('/auth/status/?lang=' + lang)
            self.assertNotEqual(
                response.context['status_explainer_text'],
                response.context['lede'],
            )
            self.assertNotEqual(
                response.context['status_explainer_text'],
                response.context['status_text'],
            )

    def test_status_explainer_uses_localized_next_step_for_linked_active_account(self):
        account = self.create_active('linked-active-next-step@example.org')
        account.person = Person.objects.create(display_name='Linked Active Member')
        account.save(update_fields=['person'])
        self.login(account)
        for lang in ('en', 'fr', 'pt', 'ar', 'sw'):
            response = self.client.get('/auth/status/?lang=' + lang)
            self.assertContains(response, catalog(lang)['continue_account'])
            self.assertIsNone(response.context['status_action'])

    def test_status_explainer_contains_distinct_context_from_status_sentence(self):
        account = self.create_active('status-explainer-context@example.org')
        self.login(account)
        response = self.client.get('/auth/status/')
        html = response.content.decode()
        popup = html.split('<div class="status-explainer-popup" role="note">', 1)[1].split('</div>', 1)[0]
        self.assertNotEqual(popup, response.context['status_text'])

    def test_enrolled_mfa_success_uses_current_workspace_destination(self):
        account = self.create_active('mfa-destination@example.org')
        secret = pyotp.random_base32()
        account.mfa_secret = services.encrypt(secret)
        account.save(update_fields=['mfa_secret'])
        self.login(account)
        response = self.client.post('/auth/mfa/', {'code': pyotp.TOTP(secret).now()})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/onboarding/1/')

    def test_onboarding_profile_menu_has_csrf_post_logout_for_desktop_and_mobile(self):
        account = self.create_active('menu@example.org')
        self.login(account)
        response = self.client.get('/onboarding/1/')
        self.assertContains(response, 'data-profile-menu')
        self.assertContains(response, 'action="/auth/logout/"')
        self.assertContains(response, 'method="post"')
        self.assertGreaterEqual(response.content.decode().count('name="csrfmiddlewaretoken"'), 2)
        self.assertContains(response, 'aria-haspopup="menu"')
        html = response.content.decode()
        mobile_head = html.split('<div class="mobile-head">', 1)[1].split('</div><div class="mobile-scope">', 1)[0]
        self.assertIn('data-profile-menu', mobile_head)

    def test_onboarding_script_rebinds_profile_menus_after_document_replacement(self):
        script = (Path(__file__).parent / 'static' / 'accounts' / 'onboarding.js').read_text()
        self.assertIn('function initializeProfileMenus()', script)
        self.assertIn('initializeProfileMenus();', script)

    def test_mfa_setup_recovery_codes_continue_to_current_workspace(self):
        account = self.create_active('mfa-setup-destination@example.org')
        account.user.is_staff = True
        account.user.save(update_fields=['is_staff'])
        draft = OnboardingDraft.objects.create(account=account, state='accepted', next_step=6)
        person = Person.objects.create(display_name='Accepted Setup Member')
        consent = OnboardingConsent.objects.create(
            draft=draft, revision=0, version='v1', notice='notice', digest='d',
            approval_reference='ref', privacy_ack=True, channel='web',
        )
        Membership.objects.create(
            draft=draft, person=person, network='WGMN', home={'label': 'Home'},
            consent=consent, policy_digest='p', approved_by=account,
        )
        self.assertRedirects(self.login(account), '/auth/mfa/')
        setup = self.client.post('/auth/mfa/', {'begin': '1'})
        self.assertEqual(setup.status_code, 200)
        account.refresh_from_db()
        secret = services.decrypt(account.mfa_pending_secret)
        recovery = self.client.post('/auth/mfa/', {'code': pyotp.TOTP(secret).now()})
        self.assertEqual(recovery.status_code, 200)
        self.assertContains(recovery, 'href="/foundation/"')

    def test_profile_menu_preserves_avatar_fill_and_rtl_label_alignment(self):
        css = (Path(__file__).parent / 'static' / 'accounts' / 'onboarding.css').read_text()
        self.assertNotIn('.profile-trigger{border:0;background:transparent', css)
        self.assertIn('.profile-menu-panel{position:absolute;inset-inline-end:0;', css)
        self.assertNotIn('.profile-menu-panel{position:absolute;right:0;', css)
        self.assertIn('.profile-menu-panel button{width:100%;padding:9px;border:0;background:transparent;text-align:start;', css)
