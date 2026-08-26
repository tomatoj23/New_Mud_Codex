from __future__ import annotations

import hashlib
from dataclasses import dataclass

from django.core.cache import cache


@dataclass(frozen=True)
class RateLimitSubject:
    scope: str
    value: object
    limit: int


def consume_rate_limit(
    *, namespace: str, window_seconds: int, subjects: tuple[RateLimitSubject, ...]
) -> bool:
    """Consume every bucket without exposing which subject reached its limit."""
    results = [
        _consume_bucket(
            namespace=namespace,
            window_seconds=window_seconds,
            subject=subject,
        )
        for subject in subjects
    ]
    return all(results)


def _consume_bucket(*, namespace: str, window_seconds: int, subject: RateLimitSubject) -> bool:
    digest = hashlib.sha256(str(subject.value).encode("utf-8")).hexdigest()
    key = f"new-mud:rate-limit:{namespace}:{subject.scope}:{digest}"
    if cache.add(key, 1, timeout=window_seconds):
        count = 1
    else:
        try:
            count = cache.incr(key)
        except ValueError:
            # The bucket may expire between add and incr. Retrying add starts
            # the next fixed window without accepting an uncounted request.
            count = 1 if cache.add(key, 1, timeout=window_seconds) else cache.incr(key)
    return count <= subject.limit
