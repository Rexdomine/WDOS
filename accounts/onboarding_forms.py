"""Forms map to approved v1 ONB controls; sample policy values are not defaults."""
from zoneinfo import available_timezones
from django import forms
from .onboarding_policy import current_policy


class BaseForm(forms.Form):
    def __init__(self, *args, account=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.account = account
        for field in self.fields.values():
            field.widget.attrs['class'] = 'input'


class WelcomeForm(BaseForm):
    language = forms.ChoiceField(label='Interface language', choices=[('en', 'English')])
    timezone = forms.ChoiceField(label='Your timezone', choices=[(s, s) for s in sorted(available_timezones())], initial='UTC')
    reading = forms.ChoiceField(label='Reading preference', choices=[('standard', 'Standard text'), ('large', 'Large text')], initial='standard')
    reduce_motion = forms.BooleanField(label='Motion preference', required=False, help_text='Reduce non-essential motion')


class ProfileForm(BaseForm):
    full_name = forms.CharField(label='Full name', max_length=150)
    preferred_name = forms.CharField(label='Preferred name', max_length=150, required=False)
    email = forms.EmailField(label='Email address', disabled=True)
    photo = forms.FileField(label='Profile photo', required=False, disabled=True)


class NetworkForm(BaseForm):
    eligibility = forms.ChoiceField(label='Age eligibility', choices=[('pending', 'More information needed')])
    network = forms.ChoiceField(label='Proposed network', choices=[('', '—'), ('WGMN', 'WGMN — Good Mother Network'), ('WNNN', 'WNNN')])
    verification_basis = forms.CharField(label='Verification basis', disabled=True, required=False, initial='Pending review')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        policy = current_policy()
        if policy:
            self.fields['eligibility'].choices = [('', '—')] + [(r['code'], r['label']) for r in policy['eligibility']]

    def clean(self):
        data = super().clean()
        policy = current_policy()
        if policy and not any(r['code'] == data.get('eligibility') and r['network'] == data.get('network') for r in policy['eligibility']):
            self.add_error('eligibility', 'More information needed')
        return data
    eligibility_confirmed = forms.BooleanField(label='Confirm eligibility', help_text='I confirm this information is accurate.')


class GeographyForm(BaseForm):
    country = forms.CharField(label='Country', max_length=100)
    region = forms.CharField(label='State / FCT', max_length=100)
    district = forms.CharField(label='LGA', max_length=100)
    local_home = forms.CharField(label='Local connection', max_length=150, required=False, disabled=True, initial='Pending assignment')


class InterestsForm(BaseForm):
    interests = forms.CharField(label='Interests', max_length=1000, required=False)
    skills = forms.CharField(label='Skills to share', max_length=1000, required=False)
    community_connection = forms.CharField(label='Community connection', max_length=250, required=False)
    availability = forms.CharField(label='Availability', max_length=250, required=False)


class ConsentForm(BaseForm):
    privacy_ack = forms.BooleanField(label='Privacy notice', help_text='I have read the current privacy notice.', required=False, disabled=True)
    essential_messages = forms.CharField(label='Essential account messages', initial='Account and service notifications', disabled=True, required=False)
    optional_updates = forms.BooleanField(label='Optional updates', help_text='Programme and community invitations', required=False)
    channel = forms.ChoiceField(label='Preferred channel', choices=[('email', 'Email')])
    notice_digest = forms.CharField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        policy = current_policy()
        if policy:
            self.fields['privacy_ack'].disabled = False
            self.fields['privacy_ack'].required = True
            self.initial['notice_digest'] = policy['digest']

    def clean(self):
        data = super().clean()
        policy = current_policy()
        if policy and data.get('notice_digest') != policy['digest']:
            self.add_error('privacy_ack', 'Another change needs review')
        return data


class ReviewForm(BaseForm):
    review_confirmed = forms.BooleanField(label='Review confirmation', help_text='My details and communication choices are correct.')


FORMS = {1: WelcomeForm, 2: ProfileForm, 3: NetworkForm, 4: GeographyForm, 5: InterestsForm, 6: ConsentForm, 7: ReviewForm}
