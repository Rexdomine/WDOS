"""Safe, reusable transactional email presentation for WDOS."""
from django.conf import settings
from django.template.loader import render_to_string
from django.templatetags.static import static
from urllib.parse import urljoin


def render_email(template, context):
    values = dict(context)
    values['logo_url'] = urljoin(
        settings.WDOS_PUBLIC_ORIGIN.rstrip('/') + '/',
        static('accounts/assets/woddi-logo.png'),
    )
    return render_to_string(f"email/{template}.html", values)
