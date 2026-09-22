"""Small server-only Brevo transport. Acceptance is not mailbox-delivery proof."""
import json
import urllib.error
import urllib.request
from django.conf import settings


class BrevoFailure(Exception):
    def __init__(self, state, code):
        self.state, self.code = state, code
        super().__init__(code)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def send(payload):
    if not settings.BREVO_API_KEY or not settings.WDOS_EMAIL_FROM:
        raise BrevoFailure('blocked', 'not_configured')
    body = dict(payload, sender={'email':settings.WDOS_EMAIL_FROM, 'name':'WODDI Digital Operating System'})
    request = urllib.request.Request('https://api.brevo.com/v3/smtp/email', data=json.dumps(body).encode(), headers={'api-key':settings.BREVO_API_KEY, 'Content-Type':'application/json', 'Accept':'application/json'}, method='POST')
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=10) as response:
            data = json.loads(response.read(65536))
            message_id = data.get('messageId')
            if response.status != 201 or not isinstance(message_id, str) or not message_id or len(message_id)>255:
                raise BrevoFailure('unknown','invalid_response')
            return message_id
    except urllib.error.HTTPError as exc:
        # Do not log/read provider bodies: they can echo recipient or message secrets.
        raise BrevoFailure('failed' if 400 <= exc.code < 500 else 'unknown', 'http_'+str(exc.code)) from None
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, TypeError, AttributeError):
        raise BrevoFailure('unknown','transport_unknown') from None
