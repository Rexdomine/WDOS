from django import forms
from django.contrib.auth.password_validation import validate_password


class EmailForm(forms.Form):
    email = forms.EmailField(label='Email address', max_length=254, widget=forms.EmailInput(attrs={'autocomplete':'email'}))


class RegisterForm(EmailForm):
    name = forms.CharField(label='Full name', max_length=150, widget=forms.TextInput(attrs={'autocomplete':'name'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}), min_length=12, max_length=128)
    field_order = ['name','email','password']

    def clean_password(self):
        value = self.cleaned_data['password']
        validate_password(value)
        return value


class LoginForm(EmailForm):
    password = forms.CharField(widget=forms.PasswordInput(attrs={'autocomplete':'current-password'}), max_length=128)
    remember = forms.BooleanField(label='Keep me signed in', required=False)


class VerifyForm(EmailForm):
    code = forms.RegexField(r'^\d{6}$', label='Verification code', widget=forms.TextInput(attrs={'inputmode':'numeric','autocomplete':'one-time-code','maxlength':'6'}))


class ResetForm(forms.Form):
    proof = forms.CharField(widget=forms.HiddenInput, max_length=200)
    password = forms.CharField(label='New password', widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}), min_length=12, max_length=128)
    confirm = forms.CharField(label='Confirm password', widget=forms.PasswordInput(attrs={'autocomplete':'new-password'}), max_length=128)

    def clean(self):
        data = super().clean()
        if data.get('password') != data.get('confirm'):
            self.add_error('confirm', 'Passwords must match.')
        return data


class MFAForm(forms.Form):
    code = forms.CharField(label='One-time code or recovery code', max_length=32, widget=forms.TextInput(attrs={'autocomplete':'one-time-code'}))


class InvitationForm(EmailForm):
    code = forms.CharField(label='Invitation code', max_length=128)
