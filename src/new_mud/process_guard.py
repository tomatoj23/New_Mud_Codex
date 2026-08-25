from __future__ import annotations

import atexit
import threading
from contextlib import suppress
from typing import Any

import psycopg
from django.db import connections
from django.db.utils import DatabaseError

_LOCK_NAMESPACE = int.from_bytes(b"NMUD", byteorder="big", signed=True)
_LOCK_ID = int.from_bytes(b"ASGI", byteorder="big", signed=True)
_lease: psycopg.Connection[Any] | None = None
_leases_lock = threading.Lock()


class ProcessLeaseError(RuntimeError):
    pass


def single_process_lease_key() -> tuple[int, int]:
    return _LOCK_NAMESPACE, _LOCK_ID


def acquire_single_process_lease() -> None:
    global _lease
    with _leases_lock:
        if _lease is not None:
            try:
                with _lease.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                return
            except psycopg.Error:
                _lease.close()
                _lease = None
        database = connections["default"]
        try:
            database.ensure_connection()
        except DatabaseError as error:
            raise ProcessLeaseError("PostgreSQL process lease is unavailable") from error
        if database.connection is None:
            raise ProcessLeaseError("PostgreSQL process lease is unavailable")
        try:
            lease = psycopg.connect(
                database.connection.info.dsn,
                password=database.settings_dict["PASSWORD"],
                autocommit=True,
            )
        except psycopg.Error as error:
            raise ProcessLeaseError("PostgreSQL process lease is unavailable") from error
        try:
            with lease.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_try_advisory_lock(%s, %s)",
                    single_process_lease_key(),
                )
                acquired = cursor.fetchone()
        except psycopg.Error as error:
            with suppress(psycopg.Error):
                lease.close()
            raise ProcessLeaseError("PostgreSQL process lease is unavailable") from error
        if acquired != (True,):
            lease.close()
            raise ProcessLeaseError("another ASGI process already owns the deployment lease")
        _lease = lease


def release_single_process_leases() -> None:
    global _lease
    with _leases_lock:
        if _lease is not None:
            _lease.close()
            _lease = None


atexit.register(release_single_process_leases)
