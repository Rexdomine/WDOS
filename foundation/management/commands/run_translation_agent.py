"""
Server-side LiveKit Room Translation Agent supervisor process.
Runs alongside Gunicorn and `run_auth_mailer` inside `wdos_project.runtime`
(or standalone as a Render Background Worker).
"""
from __future__ import annotations

import asyncio
import logging
import signal
import sys

from asgiref.sync import async_to_sync
from django.core.management.base import BaseCommand
from django.db import close_old_connections

from foundation.multilingua.livekit_agent import TranslationAgentSupervisor

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run the server-side LiveKit real-time speech translation agent across active meeting rooms."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Run a single reconciliation pass and exit.",
        )

    def handle(self, *args, **options):
        once = bool(options.get("once"))
        async_to_sync(self._run_async)(once=once)

    async def _run_async(self, once: bool = False) -> None:
        stop_event = asyncio.Event()

        if not once:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGTERM, signal.SIGINT):
                try:
                    loop.add_signal_handler(sig, stop_event.set)
                except NotImplementedError:
                    # Windows ProactorEventLoop fallback
                    signal.signal(sig, lambda *_: stop_event.set())

        supervisor = TranslationAgentSupervisor()
        try:
            while not stop_event.is_set():
                try:
                    await supervisor.reconcile_once()
                except Exception as exc:
                    logger.warning("TranslationAgentSupervisor reconcile error: %s", exc)
                if once:
                    break
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    pass
        finally:
            await supervisor.shutdown()
            if "test" not in sys.argv:
                close_old_connections()
