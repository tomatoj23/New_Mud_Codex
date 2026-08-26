from __future__ import annotations

import os

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason="requires the PostgreSQL contract-test service",
    ),
]

VERIFICATION_TABLES = {
    "identity_verificationchallenge",
    "identity_verificationdeliveryoutbox",
    "identity_verificationratelimitbucket",
    "identity_verificationrequestrecord",
    "identity_verifiedcontactmethod",
}
VERIFICATION_GUARD_TRIGGERS = {
    "identity_verification_challenge_guard_trigger",
    "identity_verification_delivery_guard_trigger",
    "identity_verification_request_guard_trigger",
    "identity_verified_contact_guard_trigger",
    "identity_verification_limit_guard_trigger",
}


def migrate_identity_to(name: str) -> None:
    MigrationExecutor(connection).migrate([("identity", name)])


def verification_guard_triggers() -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT trigger_name
              FROM information_schema.triggers
             WHERE trigger_schema = current_schema()
               AND trigger_name LIKE 'identity_verification_%_guard_trigger'
                OR (
                    trigger_schema = current_schema()
                    AND trigger_name = 'identity_verified_contact_guard_trigger'
                )
            """
        )
        return {row[0] for row in cursor.fetchall()}


def test_verification_migrations_round_trip_from_0003_to_0006() -> None:
    try:
        migrate_identity_to("0003_identity_immutability_guards")
        assert VERIFICATION_TABLES.isdisjoint(connection.introspection.table_names())

        migrate_identity_to("0006_verification_immutability_guards")
        assert set(connection.introspection.table_names()) >= VERIFICATION_TABLES
        assert verification_guard_triggers() == VERIFICATION_GUARD_TRIGGERS

        migrate_identity_to("0003_identity_immutability_guards")
        assert VERIFICATION_TABLES.isdisjoint(connection.introspection.table_names())
    finally:
        migrate_identity_to("0006_verification_immutability_guards")

    assert set(connection.introspection.table_names()) >= VERIFICATION_TABLES
    assert verification_guard_triggers() == VERIFICATION_GUARD_TRIGGERS
