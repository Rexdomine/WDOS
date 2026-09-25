"""Explicit policy-scoped human review. No implicit staff/superuser authority."""
from django.db import transaction
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from .models import Account, AccessGrant, Invitation, Person, Membership, OnboardingDraft, OnboardingEvent
from .onboarding_policy import current_policy
from .onboarding_forms import FORMS


def denied():
    return JsonResponse({'error': 'Access has changed'}, status=403)


@require_http_methods(['GET', 'POST'])
def review(request, account_id):
    actor = getattr(request, 'wdos_account', None)
    policy = current_policy()
    if not actor or actor.pk == account_id or not request.session.get('mfa_verified') or not policy:
        return denied()
    with transaction.atomic():
        # Lock complete actor/subject sets in global order; matches account -> person -> invitation.
        accounts = {a.pk: a for a in Account.objects.select_for_update().select_related('user').filter(pk__in=[actor.pk, account_id]).order_by('pk')}
        actor = accounts.get(actor.pk)
        target = accounts.get(account_id)
        if not actor or not target or actor.status != 'active' or not actor.user.is_active or actor.security_version != request.session.get('security_version'):
            return denied()
        draft = OnboardingDraft.objects.select_for_update().filter(account=target).first()
        if not draft:
            return denied()
        grants = list(AccessGrant.objects.select_for_update().filter(account=actor, role=policy['review_role'], function=policy['review_function'], network=draft.data.get('network', ''), geography=draft.data.get('country', ''), revoked_at=None))
        if not any(g.expires_at > timezone.now() for g in grants):
            return denied()
        if request.method == 'GET' and draft.state != 'review_needed':
            return JsonResponse({'error': 'More information needed'}, status=409)
        if target.status != 'active' or not target.user.is_active or not target.verified_at:
            return JsonResponse({'error': 'Access has changed'}, status=409)
        if request.method == 'GET':
            response = JsonResponse({'revision': draft.revision, 'state': draft.state, 'data': draft.data})
            response['Cache-Control'] = 'no-store, private'
            return response
        try:
            revision = int(request.POST.get('revision', ''))
        except (ValueError, TypeError):
            return JsonResponse({'error': 'Another change needs review'}, status=409)
        home_code = request.POST.get('home', '')
        evidence = request.POST.get('identity_evidence', '').strip()
        if draft.state == 'accepted':
            event = draft.events.filter(event='accepted').last()
            if event and event.revision == revision + 1 and event.actor_id == actor.pk and event.detail.get('home') == home_code and event.detail.get('identity_evidence') == evidence and request.POST.get('decision') == 'accept':
                return JsonResponse({'state': 'accepted', 'revision': draft.revision})
            return JsonResponse({'error': 'Another change needs review'}, status=409)
        if draft.state != 'review_needed' or revision != draft.revision:
            return JsonResponse({'error': 'Another change needs review'}, status=409)
        if request.POST.get('decision') != 'accept' or not evidence or len(evidence) > 1000:
            return JsonResponse({'error': 'More information needed'}, status=422)
        initial = {'email': target.email, 'full_name': target.display_name, **draft.data}
        if any(not FORMS[n](draft.data, initial=initial, account=target).is_valid() for n in range(1, 8)):
            return JsonResponse({'error': 'More information needed'}, status=422)
        consent = draft.consents.order_by('-id').first()
        if (
            not consent
            or consent.revision != draft.submission_revision
            or consent.revision != draft.revision - 1
            or not consent.privacy_ack
            or consent.digest != policy['digest']
            or consent.optional_updates != bool(draft.data.get('optional_updates'))
            or consent.channel != draft.data.get('channel')
        ):
            return JsonResponse({'error': 'More information needed'}, status=422)
        home = next((h for h in policy['homes'] if h['code'] == home_code and all(h[k] == draft.data.get(k) for k in ['network', 'country', 'region', 'district'])), None)
        if not home:
            return JsonResponse({'error': 'More information needed'}, status=422)
        # Lock the identity rows before checking invitations. Invitation issuance
        # takes the same email-account lock first, preventing a stranded identity.
        list(Invitation.objects.select_for_update().filter(email__iexact=target.email).order_by('pk'))
        if target.person_id:
            person = Person.objects.select_for_update().get(pk=target.person_id)
        else:
            # Includes expired invitations: expiry never means permission to duplicate a person.
            if Invitation.objects.filter(email__iexact=target.email).exists():
                return JsonResponse({'error': 'Another change needs review', 'next': '/auth/invitation/'}, status=409)
            person = Person.objects.create(display_name=draft.data['full_name'])
            target.person = person
            target.save(update_fields=['person'])
        if Membership.objects.filter(person=person).exists():
            return JsonResponse({'error': 'Another change needs review'}, status=409)
        Membership.objects.create(draft=draft, person=person, network=draft.data['network'], home=home, consent=consent, policy_digest=policy['digest'], approved_by=actor)
        draft.state = 'accepted'
        draft.revision += 1
        draft.save(update_fields=['state', 'revision', 'updated_at'])
        OnboardingEvent.objects.create(draft=draft, actor=actor, revision=draft.revision, event='accepted', detail={'home': home_code, 'identity_evidence': evidence, 'policy_digest': policy['digest']})
        return JsonResponse({'state': 'accepted', 'revision': draft.revision})
