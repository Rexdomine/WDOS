"""Stage 2 presentation-only localization; never translate identity data."""
import json
from pathlib import Path
from django.core.exceptions import ValidationError

LANGUAGES = {
    'en': {'name': 'English', 'dir': 'ltr'},
    'fr': {'name': 'Français', 'dir': 'ltr'},
    'pt': {'name': 'Português', 'dir': 'ltr'},
    'ar': {'name': 'العربية', 'dir': 'rtl'},
    'sw': {'name': 'Kiswahili', 'dir': 'ltr'},
}
C = json.loads(Path(__file__).with_name('locales.json').read_text(encoding='utf-8'))
BASE = C['en']
_KEYS = {value: key for key, value in BASE.items()}
_VALIDATOR_ATTRIBUTE_KEYS = {
    'email': 'email',
    'email address': 'email',
    'first name': 'name',
    'last name': 'name',
    'full name': 'name',
}


def logout_preserving_language(request):
    from django.contrib.auth import logout
    lang = request.session.get('wdos_language', 'en')
    logout(request)
    request.session['wdos_language'] = lang if lang in LANGUAGES else 'en'


def catalog(lang):
    return C.get(lang, BASE)


def translate(lang, text):
    """Call only for application-owned literals, never names or identifiers."""
    return catalog(lang).get(_KEYS.get(text), text)


def _translate_validator_attribute(lang, value):
    """Map Django validator field metadata to an approved localized label."""
    key = _VALIDATOR_ATTRIBUTE_KEYS.get(str(value).strip().lower())
    return catalog(lang).get(key, value) if key else translate(lang, str(value).capitalize())


def localize_form(form, lang):
    if lang == 'en':
        return form
    c = catalog(lang)
    for bound in form:
        # Preserve semantic distinctions between verification/MFA/invitation codes.
        bound.label = translate(lang, bound.label)
        bound.field.label = bound.label
        bound.help_text = translate(lang, str(bound.help_text))
    error_keys = {
        'required': 'required_field', 'invalid': 'invalid_field',
        'min_length': 'too_short', 'max_length': 'too_long',
        'password_too_short': 'password_too_short',
        'password_too_common': 'password_too_common',
        'password_entirely_numeric': 'password_entirely_numeric',
        'password_too_similar': 'password_too_similar',
        'password_reused': 'password_reused',
    }
    for name, errors in form.errors.items():
        translated = []
        for error in errors.as_data():
            key = error_keys.get(error.code)
            if error.code == 'invalid' and name == 'email':
                key = 'invalid_email'
            message = c[key] if key else translate(lang, str(error.message))
            params = dict(error.params or {})
            if 'verbose_name' in params:
                params['verbose_name'] = _translate_validator_attribute(lang, params['verbose_name'])
            translated.append(ValidationError(message, code=error.code, params=params))
        errors.data[:] = translated
    return form
