from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import timedelta

from django.db import connection

from .models import VerificationRateLimitBucket


@dataclass(frozen=True)
class PersistentLimit:
    scope: str
    subject_digest: str
    window_seconds: int
    limit: int


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int


def _lock_key(value: str) -> int:
    return int.from_bytes(hashlib.sha256(value.encode()).digest()[:8], signed=True)


def advisory_transaction_lock(value: str) -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [_lock_key(value)])


def consume_persistent_limits(
    *,
    namespace: str,
    limits: tuple[PersistentLimit, ...],
    now,
) -> RateLimitDecision:
    ordered = sorted(
        limits,
        key=lambda item: (item.scope, item.subject_digest, item.window_seconds),
    )
    for item in ordered:
        advisory_transaction_lock(
            f"verification-limit:{namespace}:{item.scope}:"
            f"{item.subject_digest}:{item.window_seconds}"
        )

    decisions: list[tuple[bool, int]] = []
    for item in ordered:
        bucket, _ = VerificationRateLimitBucket.objects.select_for_update().get_or_create(
            namespace=namespace,
            scope=item.scope,
            subject_digest=item.subject_digest,
            window_seconds=item.window_seconds,
            defaults={"window_started_at": now},
        )
        window_end = bucket.window_started_at + timedelta(seconds=item.window_seconds)
        if now >= window_end:
            bucket.window_started_at = now
            bucket.request_count = 0
            window_end = now + timedelta(seconds=item.window_seconds)
        bucket.request_count += 1
        bucket.version += 1
        bucket.save(update_fields=("window_started_at", "request_count", "version"))
        decisions.append(
            (
                bucket.request_count <= item.limit,
                max(1, int((window_end - now).total_seconds())),
            )
        )
    denied_retry = [retry for allowed, retry in decisions if not allowed]
    return RateLimitDecision(
        allowed=not denied_retry,
        retry_after=max(denied_retry, default=0),
    )
