"""Stage 3 views: account-owned, versioned drafts, never client-owned identity."""
from django.db import transaction
from django.http import Http404, JsonResponse
from django.utils import timezone
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods
from .models import Account, OnboardingDraft, OnboardingEvent, OnboardingConsent
from .onboarding_policy import current_policy
from .onboarding_forms import FORMS

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
CONFLICT = {'title': 'Another change needs review', 'body': 'This record changed since you opened it. Review the latest version before submitting.'}
INVALID = {'title': 'Check the highlighted information', 'body': 'Complete the required fields before continuing. Your entered information is retained.'}


def initial_data(account, draft):
    return {'full_name': account.display_name, 'email': account.email, 'language': 'en', 'timezone': 'UTC', 'reading': 'standard', **(draft.data if draft else {})}


def render_step(request, number, draft, form, notice=None, status=200):
    account = request.wdos_account
    response = render(request, 'onboarding/wizard.html', {
        'account': account, 'form': form, 'step': number,
        'revision': draft.revision if draft else 0,
        'lang': 'en', 'direction': 'ltr', 'screen_id': f'ONB-{number:02d}',
        'initials': ''.join(n[0] for n in account.display_name.split()[:2]),
        'scope_label': 'Membership', 'state_label': 'More information needed' if draft and draft.state == 'review_needed' else 'In progress',
        'draft': draft, 'policy': current_policy(),
        'title': TITLES[number][0], 'notice': notice,
        'subtitle': 'Complete the information below, then review it before you continue.',
        'action_label': TITLES[number][1],
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
    draft = OnboardingDraft.objects.filter(account=account).first()
    if step == 8:
        if not draft or draft.state == 'draft':
            return redirect('onboarding:step', step=draft.next_step if draft else 1)
        notice = {'title': 'More information needed', 'body': 'Your progress and next action remain available here.'} if draft.state == 'review_needed' else None
        return render_step(request, step, draft, None, notice)
    form_class = FORMS[step]
    form = form_class(request.POST if request.method == 'POST' else None, initial=initial_data(account, draft), account=account)
    if request.method == 'GET':
        return render_step(request, step, draft, form)
    try:
        revision = int(request.POST.get('revision', ''))
    except (TypeError, ValueError):
        return render_step(request, step, draft, form, CONFLICT, 409)
    # Same account lock as the auth/identity services, then draft; never inverse order.
    with transaction.atomic():
        locked = Account.objects.select_for_update().select_related('user').get(pk=account.pk)
        if locked.status != 'active' or not locked.user.is_active or locked.security_version != request.session.get('security_version'):
            return redirect('accounts:login')
        draft = OnboardingDraft.objects.select_for_update().filter(account=locked).first()
        if step == 7 and draft and draft.state != 'draft' and draft.submission_revision == revision:
            return redirect('onboarding:step', step=8)
        if revision != (draft.revision if draft else 0) or (draft and draft.state == 'accepted'):
            return render_step(request, step, draft, form, CONFLICT, 409)
        valid = form.is_valid()
        if step == 7:
            for previous in range(1, 7):
                saved = FORMS[previous](draft.data if draft else {}, initial=initial_data(locked, draft), account=locked)
                if not saved.is_valid():
                    form.add_error(None, TITLES[previous][0])
                    valid = False
            if not valid:
                return render_step(request, step, draft, form, INVALID, 422)
        if not draft:
            draft = OnboardingDraft(account=locked)
        # Partial drafts retain validated fields only. Browser-supplied role/person/email are not writable.
        changes = {key: value for key, value in form.cleaned_data.items() if not form.fields[key].disabled and key != 'photo'}
        draft.data = {**draft.data, **changes}
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
            return render_step(request, step, draft, form, INVALID, 422)
    return redirect('onboarding:step', step=draft.next_step)
