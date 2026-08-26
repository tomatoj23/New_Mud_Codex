from __future__ import annotations

from importlib import import_module


def test_identity_contract_migration_contains_reversible_deferred_guards() -> None:
    migration = import_module("new_mud.apps.identity.migrations.0002_lifetime_contract_guards")

    expected_triggers = {
        "identity_session_contract_trigger",
        "identity_family_contract_trigger",
        "identity_family_credentials_trigger",
        "identity_credential_family_trigger",
    }
    for trigger_name in expected_triggers:
        assert f"CREATE CONSTRAINT TRIGGER {trigger_name}" in migration.POSTGRES_CONTRACT_SQL
        assert f"DROP TRIGGER IF EXISTS {trigger_name}" in migration.POSTGRES_CONTRACT_REVERSE_SQL

    assert migration.POSTGRES_CONTRACT_SQL.count("DEFERRABLE INITIALLY DEFERRED") == 4
    assert migration.POSTGRES_CONTRACT_REVERSE_SQL.count("DROP FUNCTION IF EXISTS") == 5


def test_identity_immutability_migration_guards_lifetime_identity_fields() -> None:
    migration = import_module("new_mud.apps.identity.migrations.0003_identity_immutability_guards")

    for field_name in (
        "auth_session_id",
        "absolute_expires_at",
        "family_id",
        "generation",
    ):
        assert field_name in migration.POSTGRES_IMMUTABILITY_SQL
    for trigger_name in (
        "identity_family_immutable_trigger",
        "identity_credential_immutable_trigger",
    ):
        assert f"CREATE TRIGGER {trigger_name}" in migration.POSTGRES_IMMUTABILITY_SQL
        assert (
            f"DROP TRIGGER IF EXISTS {trigger_name}" in migration.POSTGRES_IMMUTABILITY_REVERSE_SQL
        )
