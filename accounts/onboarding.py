"""Stage 3 views: account-owned, versioned drafts, never client-owned identity."""
from django.db import transaction
from django.http import Http404, HttpResponse
from django.utils import timezone
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from .models import Account, OnboardingDraft, OnboardingEvent, OnboardingConsent
from .onboarding_policy import current_policy
from .onboarding_forms import FORMS
from .locale import LANGUAGES, catalog, localize_form, translate

TITLES = {
    1: ('Make WDOS feel like home', 'Continue'),
    2: ('Tell us about yourself', 'Save and continue'),
    3: ('Find your network', 'Confirm membership'),
    4: ('Connect with your local community', 'Confirm local home'),
    5: ('What matters to you?', 'Save interests'),
    6: ('Your preferences, your choice', 'Save preferences'),
    7: ('Review your membership', 'Complete registration'),
    8: ('Your first steps in WDOS', 'Open my dashboard'),
}
CONFLICT_KEYS = ('onb_notice_title', 'onb_notice_body')
INVALID_KEYS = ('onb_invalid_title', 'onb_invalid_body')


def localized_notice(catalogue, keys):
    return {'title': catalogue[keys[0]], 'body': catalogue[keys[1]]}


def initial_data(account, draft, language='en'):
    return {'full_name': account.display_name, 'email': account.email, 'timezone': 'UTC', 'reading': 'standard', **(draft.data if draft else {}), 'language': language}


def render_step(request, number, draft, form, notice=None, status=200):
    account = request.wdos_account
    tab = request.GET.get('tab', 'overview')
    if tab not in ('overview', 'records', 'history'):
        raise Http404
    membership = getattr(draft, 'membership', None) if draft else None
    lang = request.GET.get('lang') or request.COOKIES.get('wdos_language') or request.session.get('wdos_language', 'en')
    lang = lang if lang in LANGUAGES else 'en'
    request.session['wdos_language'] = lang
    if form is not None:
        localize_form(form, lang)
    c = catalog(lang)
    response = render(request, 'onboarding/wizard.html', {
        'account': account, 'form': form, 'step': number,
        'revision': draft.revision if draft else 0,
        'lang': lang, 'direction': LANGUAGES[lang]['dir'], 'screen_id': f'ONB-{number:02d}',
        'initials': ''.join(n[0] for n in account.display_name.split()[:2]),
        'scope_label': c['onb_membership'], 'state_label': c['onb_more_needed'] if draft and draft.state == 'review_needed' else c['onb_ready'] if draft and draft.state == 'accepted' else c['onb_in_progress'],
        'draft': draft, 'policy': current_policy(), 'tab': tab,
        'events': draft.events.order_by('-id')[:100] if draft and tab == 'history' else [],
        'consents': draft.consents.order_by('-id')[:100] if draft and tab == 'history' else [],
        'profile_name': (draft.data.get('full_name') or account.display_name) if draft else account.display_name,
        'network': draft.data.get('network', '—') if draft else '—',
        'local_home': membership.home['label'] if membership else c['onb_pending'],
        'title': c[f'onb_title_{number}'], 'notice': notice,
        'subtitle': c['onb_subtitle'],
        'action_label': c[f'onb_action_{number}'],
        'ui': c,
    }, status=status)
    response['Cache-Control'] = 'no-store, private'
    response['Referrer-Policy'] = 'same-origin'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    return response


@require_http_methods(['GET'])
def start(request):
    if not request.wdos_account:
        return redirect('accounts:login')
    draft = OnboardingDraft.objects.filter(account=request.wdos_account).first()
    return redirect('onboarding:step', step=draft.next_step if draft else 1)


@require_http_methods(['GET', 'POST'])
def step(request, step):
    if not request.wdos_account:
        return redirect('accounts:login')
    if step not in TITLES:
        raise Http404
    account = request.wdos_account
    lang = request.GET.get('lang') or request.COOKIES.get('wdos_language') or request.session.get('wdos_language', 'en')
    lang = lang if lang in LANGUAGES else 'en'
    c = catalog(lang)
    draft = OnboardingDraft.objects.filter(account=account).first()
    if step == 8:
        if not draft or draft.state == 'draft':
            return redirect('onboarding:step', step=draft.next_step if draft else 1)
        notice = {'title': c['onb_more_needed'], 'body': c['onb_more_body']} if draft.state == 'review_needed' else None
        return render_step(request, step, draft, None, notice)
    form_class = FORMS[step]
    form = form_class(request.POST if request.method == 'POST' else None, request.FILES if request.method == 'POST' else None, initial=initial_data(account, draft, lang), account=account)
    if request.method == 'GET':
        return render_step(request, step, draft, form)
    if getattr(request, '_wdos_upload_rejected', False):
        # The photo belongs only to the profile step.  Never manufacture a
        # photo field error on another step when a multipart body is capped.
        upload_error = c['onb_upload_too_large']
        form.add_error('photo' if step == 2 else None, upload_error)
        return render_step(request, step, draft, form, localized_notice(c, INVALID_KEYS), 422 if step == 2 else 400)
    try:
        revision = int(request.POST.get('revision', ''))
    except (TypeError, ValueError):
        return render_step(request, step, draft, form, localized_notice(c, CONFLICT_KEYS), 409)
    # Same account lock as the auth/identity services, then draft; never inverse order.
    with transaction.atomic():
        locked = Account.objects.select_for_update().select_related('user').get(pk=account.pk)
        if locked.status != 'active' or not locked.user.is_active or locked.security_version != request.session.get('security_version'):
            return redirect('accounts:login')
        draft = OnboardingDraft.objects.select_for_update().filter(account=locked).first()
        if step == 7 and draft and draft.state != 'draft' and revision in (draft.submission_revision, draft.revision):
            return redirect('onboarding:step', step=8)
        if revision != (draft.revision if draft else 0) or (draft and draft.state == 'accepted'):
            return render_step(request, step, draft, form, localized_notice(c, CONFLICT_KEYS), 409)
        if request.POST.get('action') == 'back':
            if step == 1:
                return redirect('accounts:status')
            return redirect('onboarding:step', step=step - 1)
        valid = form.is_valid()
        if step == 7:
            for previous in range(1, 7):
                saved = FORMS[previous](draft.data if draft else {}, initial=initial_data(locked, draft), account=locked)
                if not saved.is_valid():
                    form.add_error(None, TITLES[previous][0])
                    valid = False
            if not valid:
                return render_step(request, step, draft, form, localized_notice(c, INVALID_KEYS), 422)
        if not draft:
            draft = OnboardingDraft(account=locked)
        # Partial drafts retain validated fields only. Browser-supplied role/person/email are not writable.
        changes = {key: value for key, value in form.cleaned_data.items() if not form.fields[key].disabled and key != 'photo'}
        unchanged = bool(draft) and draft.data == {**draft.data, **changes} and not (
            step == 2 and form.cleaned_data.get('photo') is not None
        )
        if step == 6:
            unchanged = unchanged and draft.consents.filter(revision=draft.revision).exists()
        if unchanged:
            if not valid:
                return render_step(request, step, draft, form, localized_notice(c, INVALID_KEYS), 422)
            return redirect('onboarding:step', step=draft.next_step)
        draft.data = {**draft.data, **changes}
        if step == 1 and form.cleaned_data.get('language') in LANGUAGES:
            request.session['wdos_language'] = form.cleaned_data['language']
        if step == 2 and form.cleaned_data.get('photo') is not None:
            draft.photo = form.cleaned_data['photo']
        draft.revision += 1
        if valid:
            draft.next_step = max(1, step - 1) if request.POST.get('action') == 'back' else min(step + 1, 7)
        if step < 7:
            draft.state = 'draft'
            draft.submission_revision = None
            draft.submitted_at = None
        else:
            draft.state = 'review_needed'
            draft.submission_revision = revision
            draft.submitted_at = timezone.now()
            draft.next_step = 8
        draft.save()
        OnboardingEvent.objects.create(draft=draft, actor=locked, event='draft_saved' if step < 7 else 'submitted', revision=draft.revision, detail={'step': step, 'fields': sorted(changes)})
        if step == 6 and valid:
            policy = current_policy()
            if policy:
                OnboardingConsent.objects.create(draft=draft, revision=draft.revision, version=policy['version'], notice=policy['privacy_notice'], digest=policy['digest'], approval_reference=policy['approval_reference'], privacy_ack=form.cleaned_data['privacy_ack'], optional_updates=form.cleaned_data['optional_updates'], channel=form.cleaned_data['channel'])
        if not valid:
            return render_step(request, step, draft, form, localized_notice(c, INVALID_KEYS), 422)
    response = redirect('onboarding:step', step=draft.next_step)
    if step == 1 and form.cleaned_data.get('language') in LANGUAGES:
        response.set_cookie('wdos_language', form.cleaned_data['language'], max_age=31536000, samesite='Lax')
    return response


@require_http_methods(['GET'])
def photo(request):
    if not request.wdos_account:
        return HttpResponse(status=403)
    draft = OnboardingDraft.objects.filter(account=request.wdos_account).first()
    if not draft or not draft.photo:
        raise Http404
    response = HttpResponse(bytes(draft.photo), content_type='image/png')
    response['Cache-Control'] = 'no-store, private'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@require_http_methods(['GET'])
def privacy(request):
    if not request.wdos_account:
        return redirect('accounts:login')
    from .views import page
    policy = current_policy()
    return page(request, 'PRIVACY', 'Privacy notice', policy['privacy_notice'] if policy else 'More information needed', policy_page=True)
