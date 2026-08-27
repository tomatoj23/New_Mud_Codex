from __future__ import annotations

import secrets
from functools import partial
from time import sleep

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError, CommandParser

from ...verification_config import VerificationServiceUnavailable
from ...verification_crypto import CiphertextInvalid, KeyUnavailable
from ...verification_delivery import DeliveryOutcome, deliver_one_verification
from ..worker_loop import run_worker_loop


class Command(BaseCommand):
    help = "Process durable verification-delivery outbox tasks."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--worker-id", default=None)
        parser.add_argument("--watch", action="store_true")
        parser.add_argument("--poll-interval", type=float, default=5.0)

    def handle(self, *args, **options) -> None:
        limit = 1 if options["once"] else options["limit"]
        if not isinstance(limit, int) or limit < 1:
            raise CommandError("--limit must be a positive integer")
        watch = options["watch"]
        if watch and options["once"]:
            raise CommandError("--watch and --once cannot be used together")
        poll_interval = options["poll_interval"]
        if watch and (
            not isinstance(poll_interval, (int, float))
            or poll_interval <= 0
            or poll_interval >= settings.AUTH_VERIFICATION_HEARTBEAT_MAX_AGE_SECONDS
        ):
            raise CommandError(
                "--poll-interval must be positive and shorter than the heartbeat max age"
            )
        worker_id = options["worker_id"] or f"verification-worker-{secrets.token_hex(8)}"
        try:
            run_worker_loop(
                process_one=partial(deliver_one_verification, worker_id=worker_id),
                no_work=DeliveryOutcome.NO_WORK,
                limit=limit,
                watch=watch,
                poll_interval=float(poll_interval),
                sleep=sleep,
                write=self.stdout.write,
            )
        except (VerificationServiceUnavailable, KeyUnavailable, CiphertextInvalid) as error:
            raise CommandError("verification delivery is unavailable") from error
