import os
import io
from django.core.wsgi import get_wsgi_application
from .upload_handlers import MAX_REQUEST_BYTES


class _LimitedInput:
    def __init__(self, stream, environ, limit):
        self.stream = stream
        self.environ = environ
        self.remaining = limit

    def read(self, size=-1):
        if self.remaining <= 0:
            extra = self.stream.read(1)
            if extra:
                self.environ['wdos.raw_body_rejected'] = True
            return b''
        wanted = self.remaining + 1 if size < 0 else min(size, self.remaining + 1)
        data = self.stream.read(wanted)
        if len(data) > self.remaining:
            self.environ['wdos.raw_body_rejected'] = True
            data = data[:self.remaining]
        self.remaining -= len(data)
        return data

    def readline(self, size=-1):
        return self.read(size)

    def readinto(self, buffer):
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)

    def __getattr__(self, name):
        return getattr(self.stream, name)


class RawBodyLimitMiddleware:
    """Cap request bytes before Django/CSRF/multipart parsing at WSGI."""
    def __init__(self, app, limit=MAX_REQUEST_BYTES):
        self.app = app
        self.limit = limit

    def __call__(self, environ, start_response):
        environ.setdefault('wdos.raw_body_rejected', False)
        try:
            declared = int(environ.get('CONTENT_LENGTH') or 0)
        except (TypeError, ValueError):
            declared = 0
        if declared > self.limit:
            environ['wdos.raw_body_rejected'] = True
            environ['wsgi.input'] = io.BytesIO()
        else:
            environ['wsgi.input'] = _LimitedInput(environ['wsgi.input'], environ, self.limit)
        return self.app(environ, start_response)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "wdos_project.settings")
application = RawBodyLimitMiddleware(get_wsgi_application())
