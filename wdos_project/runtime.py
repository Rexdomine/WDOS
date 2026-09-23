"""Small fail-together supervisor for WDOS web and durable auth outbox processes.

No background child is detached. A child failure stops its sibling and exits
nonzero so the deployment platform restarts the complete service.
"""
import os
import signal
import subprocess
import sys
import threading


def supervise(commands, stop=None):
    stop = stop or threading.Event()
    children=[]
    try:
        for command in commands:
            children.append(subprocess.Popen(command))
        while not stop.wait(0.25):
            if any(child.poll() is not None for child in children):
                return 1
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                child.terminate()
        for child in children:
            try:
                child.wait(timeout=15)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait(timeout=5)


def main():
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'wdos_project.settings')
    from django.conf import settings
    if os.getenv('WDOS_ENVIRONMENT') in ('staging', 'production'):
        if len(settings.SECRET_KEY) < 32 or settings.SECRET_KEY == 'wdos-local-development-only':
            raise RuntimeError('A strong deployment-specific DJANGO_SECRET_KEY is required.')
        if '*' in settings.ALLOWED_HOSTS or not settings.WDOS_PUBLIC_ORIGIN.startswith('https://'):
            raise RuntimeError('Explicit deployment hosts and an HTTPS public origin are required.')
        if not settings.SESSION_COOKIE_SECURE or settings.DEBUG:
            raise RuntimeError('Deployment requires secure cookies and DEBUG disabled.')
    # Database upgrade and roles finish before either long-running process starts.
    for command in [['migrate','--noinput'],['seed_roles']]:
        subprocess.run([sys.executable,'manage.py',*command],check=True)
    stop=threading.Event()
    for sig in (signal.SIGTERM,signal.SIGINT):
        signal.signal(sig,lambda *_:stop.set())
    return supervise([
        [sys.executable,'-m','gunicorn','wdos_project.wsgi:application','--bind','0.0.0.0:'+os.getenv('PORT','8000'),'--workers','2','--access-logfile','-'],
        [sys.executable,'manage.py','run_auth_mailer'],
    ],stop)


if __name__=='__main__':
    sys.exit(main())
