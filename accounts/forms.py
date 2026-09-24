from django import forms
from django.contrib.auth.password_validation import validate_password


class EmailForm(forms.Form):
    email = forms.EmailField(label='Email address', max_length=254, widget=forms.EmailInput(attrs={'autocomplete': 'email', 'type': 'email'}))


class RegisterForm(EmailForm):
    name = forms.CharField(label='Full name', max_length=150, widget=forms.TextInput(attrs={'autocomplete': 'name', 'type': 'text'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'type': 'password'}), min_length=12, max_length=128, help_text='Use at least 12 characters. A long, unique passphrase is best.')
    field_order = ['name', 'email', 'password']

    def clean_password(self):
        value = self.cleaned_data['password']
        name = self.cleaned_data.get('name', '')
        user = None
        if name:
            from django.contrib.auth import get_user_model
            user = get_user_model()(first_name=name)
        validate_password(value, user)
        return value


class LoginForm(EmailForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete': 'current-password', 'type': 'password'}), max_length=128)
    remember = forms.BooleanField(label='Keep me signed in', required=False, widget=forms.CheckboxInput(attrs={'type': 'checkbox'}))


class VerifyForm(forms.Form):
    code = forms.RegexField(r'^\d{6}$', label='Verification code', widget=forms.TextInput(attrs={'inputmode': 'numeric', 'autocomplete': 'one-time-code', 'maxlength': '6', 'type': 'text'}))


class ResetForm(forms.Form):
    password = forms.CharField(label='New password', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'type': 'password'}), min_length=12, max_length=128)
    confirm = forms.CharField(label='Confirm password', widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'type': 'password'}), max_length=128)

    def clean(self):
        data = super().clean()
        if data.get('password') != data.get('confirm'):
            self.add_error('confirm', 'Passwords must match.')
        return data


class MFAForm(forms.Form):
    code = forms.CharField(label='One-time code or recovery code', max_length=32, widget=forms.TextInput(attrs={'autocomplete': 'one-time-code', 'type': 'text'}))


class InvitationForm(EmailForm):
    code = forms.CharField(label='Invitation code', max_length=128, widget=forms.TextInput(attrs={'autocomplete': 'off', 'type': 'text'}))
    email = forms.EmailField(label='Email on invitation', max_length=254, widget=forms.EmailInput(attrs={'autocomplete': 'email', 'type': 'email'}))
    field_order = ['code', 'email']
