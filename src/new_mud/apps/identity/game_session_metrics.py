from __future__ import annotations

import threading
from dataclasses import dataclass


@dataclass(frozen=True)
class GameWebSocketMetricsSnapshot:
    online_connections: int
    online_auth_sessions: int
    connections_total: int
    requests_total: int
    request_errors_total: int
    request_duration_ms_total: float
    request_duration_ms_max: float


class _GameWebSocketMetrics:
    """Small process-local collector for the single-ASGI-process deployment contract."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._online_connections = 0
        self._auth_session_bindings: dict[str, int] = {}
        self._connections_total = 0
        self._requests_total = 0
        self._request_errors_total = 0
        self._request_duration_ms_total = 0.0
        self._request_duration_ms_max = 0.0

    def _snapshot(self) -> GameWebSocketMetricsSnapshot:
        return GameWebSocketMetricsSnapshot(
            online_connections=self._online_connections,
            online_auth_sessions=len(self._auth_session_bindings),
            connections_total=self._connections_total,
            requests_total=self._requests_total,
            request_errors_total=self._request_errors_total,
            request_duration_ms_total=self._request_duration_ms_total,
            request_duration_ms_max=self._request_duration_ms_max,
        )

    def connection_opened(self) -> GameWebSocketMetricsSnapshot:
        with self._lock:
            self._online_connections += 1
            self._connections_total += 1
            return self._snapshot()

    def connection_closed(self) -> GameWebSocketMetricsSnapshot:
        with self._lock:
            self._online_connections = max(0, self._online_connections - 1)
            return self._snapshot()

    def auth_session_bound(self, auth_session_id: str) -> GameWebSocketMetricsSnapshot:
        with self._lock:
            self._auth_session_bindings[auth_session_id] = (
                self._auth_session_bindings.get(auth_session_id, 0) + 1
            )
            return self._snapshot()

    def auth_session_unbound(self, auth_session_id: str) -> GameWebSocketMetricsSnapshot:
        with self._lock:
            remaining = self._auth_session_bindings.get(auth_session_id, 0) - 1
            if remaining > 0:
                self._auth_session_bindings[auth_session_id] = remaining
            else:
                self._auth_session_bindings.pop(auth_session_id, None)
            return self._snapshot()

    def request_finished(
        self,
        *,
        duration_ms: float,
        failed: bool,
    ) -> GameWebSocketMetricsSnapshot:
        with self._lock:
            self._requests_total += 1
            self._request_errors_total += int(failed)
            self._request_duration_ms_total += duration_ms
            self._request_duration_ms_max = max(self._request_duration_ms_max, duration_ms)
            return self._snapshot()

    def snapshot(self) -> GameWebSocketMetricsSnapshot:
        with self._lock:
            return self._snapshot()


game_websocket_metrics = _GameWebSocketMetrics()
