from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum


def run_worker_loop[Outcome: StrEnum](
    *,
    process_one: Callable[[], Outcome],
    no_work: Outcome,
    limit: int,
    watch: bool,
    poll_interval: float,
    sleep: Callable[[float], None],
    write: Callable[[str], None],
) -> None:
    try:
        while True:
            counts = {
                "delivered": 0,
                "delivery_failed": 0,
                "retry_scheduled": 0,
            }
            processed = 0
            for _ in range(limit):
                outcome = process_one()
                if outcome == no_work:
                    break
                processed += 1
                if outcome.value in counts:
                    counts[outcome.value] += 1
            write(
                "processed="
                f"{processed} delivered={counts['delivered']} "
                f"failed={counts['delivery_failed']} "
                f"retried={counts['retry_scheduled']}"
            )
            if not watch:
                return
            if processed < limit:
                sleep(poll_interval)
    except KeyboardInterrupt:
        return
