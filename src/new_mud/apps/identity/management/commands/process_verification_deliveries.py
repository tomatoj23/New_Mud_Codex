from __future__ import annotations

import secrets

from django.core.management.base import BaseCommand, CommandError, CommandParser

from ...verification_config import VerificationServiceUnavailable
from ...verification_crypto import CiphertextInvalid, KeyUnavailable
from ...verification_delivery import DeliveryOutcome, deliver_one_verification


class Command(BaseCommand):
    help = "Process durable verification-delivery outbox tasks."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--worker-id", default=None)

    def handle(self, *args, **options) -> None:
        limit = 1 if options["once"] else options["limit"]
        if not isinstance(limit, int) or limit < 1:
            raise CommandError("--limit must be a positive integer")
        worker_id = options["worker_id"] or f"verification-worker-{secrets.token_hex(8)}"
        counts = {
            DeliveryOutcome.DELIVERED: 0,
            DeliveryOutcome.DELIVERY_FAILED: 0,
            DeliveryOutcome.RETRY_SCHEDULED: 0,
        }
        processed = 0
        try:
            for _ in range(limit):
                outcome = deliver_one_verification(worker_id=worker_id)
                if outcome == DeliveryOutcome.NO_WORK:
                    break
                processed += 1
                if outcome in counts:
                    counts[outcome] += 1
        except (VerificationServiceUnavailable, KeyUnavailable, CiphertextInvalid) as error:
            raise CommandError("verification delivery is unavailable") from error
        self.stdout.write(
            "processed="
            f"{processed} delivered={counts[DeliveryOutcome.DELIVERED]} "
            f"failed={counts[DeliveryOutcome.DELIVERY_FAILED]} "
            f"retried={counts[DeliveryOutcome.RETRY_SCHEDULED]}"
        )
