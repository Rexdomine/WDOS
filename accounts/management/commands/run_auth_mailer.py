"""Durable outbox polling process, supervised with the web server."""
import signal
import threading
from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from io import StringIO


class Command(BaseCommand):
    help = 'Poll committed authentication email intents; no email on request threads.'

    def add_arguments(self,parser):
        parser.add_argument('--once',action='store_true')

    def handle(self,*args,**options):
        stopped=threading.Event()
        if not options['once']:
            for sig in (signal.SIGTERM,signal.SIGINT):
                signal.signal(sig,lambda *_:stopped.set())
        while not stopped.is_set():
            close_old_connections()
            call_command('recover_auth_email',stdout=StringIO())
            if options['once']:
                return
            stopped.wait(10)
