from __future__ import annotations

import secrets

from django.core.management.base import BaseCommand, CommandError, CommandParser

from ...security_notifications import (
    SecurityNotificationOutcome,
    deliver_one_security_notification,
)
from ...verification_config import VerificationServiceUnavailable
from ...verification_crypto import CiphertextInvalid, KeyUnavailable


class Command(BaseCommand):
    help = "Process durable security-notification outbox tasks."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--once", action="store_true")
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--worker-id", default=None)

    def handle(self, *args, **options) -> None:
        limit = 1 if options["once"] else options["limit"]
        if not isinstance(limit, int) or limit < 1:
            raise CommandError("--limit must be a positive integer")
        worker_id = options["worker_id"] or f"security-notification-worker-{secrets.token_hex(8)}"
        counts = {
            SecurityNotificationOutcome.DELIVERED: 0,
            SecurityNotificationOutcome.DELIVERY_FAILED: 0,
            SecurityNotificationOutcome.RETRY_SCHEDULED: 0,
        }
        processed = 0
        try:
            for _ in range(limit):
                outcome = deliver_one_security_notification(worker_id=worker_id)
                if outcome == SecurityNotificationOutcome.NO_WORK:
                    break
                processed += 1
                if outcome in counts:
                    counts[outcome] += 1
        except (VerificationServiceUnavailable, KeyUnavailable, CiphertextInvalid) as error:
            raise CommandError("security notification delivery is unavailable") from error
        self.stdout.write(
            "processed="
            f"{processed} delivered={counts[SecurityNotificationOutcome.DELIVERED]} "
            f"failed={counts[SecurityNotificationOutcome.DELIVERY_FAILED]} "
            f"retried={counts[SecurityNotificationOutcome.RETRY_SCHEDULED]}"
        )
