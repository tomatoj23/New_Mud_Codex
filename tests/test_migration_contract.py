from __future__ import annotations

from importlib import import_module


def test_initial_migration_contains_postgresql_contract_guards() -> None:
    migration = import_module("new_mud.apps.content.migrations.0001_initial")
    sql = migration.POSTGRES_CONTRACT_SQL

    expected_foreign_keys = {
        "content_revision_head_key_fk",
        "content_revision_source_head_fk",
        "content_head_draft_revision_fk",
        "content_head_published_revision_fk",
        "content_dependency_target_head_key_fk",
        "content_dependency_target_revision_fk",
        "content_release_head_active_batch_fk",
        "content_release_batch_parent_fk",
        "content_release_item_batch_fk",
        "content_release_item_head_key_fk",
        "content_release_item_revision_head_fk",
    }
    for constraint_name in expected_foreign_keys:
        assert f"ADD CONSTRAINT {constraint_name}" in sql

    assert sql.count("FOREIGN KEY") == 11
    assert sql.count("CREATE CONSTRAINT TRIGGER") == 5
    assert sql.count("DEFERRABLE INITIALLY DEFERRED") == 16
    assert sql.count("EXECUTE FUNCTION content_reject_immutable_update()") == 5


def test_initial_migration_has_reversible_custom_sql() -> None:
    migration = import_module("new_mud.apps.content.migrations.0001_initial")
    reverse_sql = migration.POSTGRES_CONTRACT_REVERSE_SQL

    assert reverse_sql.count("DROP CONSTRAINT") == 11
    assert reverse_sql.count("DROP TRIGGER") == 10
    assert reverse_sql.count("DROP FUNCTION") == 6


def test_verification_immutability_migration_has_complete_reverse_sql() -> None:
    migration = import_module(
        "new_mud.apps.identity.migrations.0006_verification_immutability_guards"
    )
    reverse_sql = migration.POSTGRES_VERIFICATION_GUARDS_REVERSE_SQL

    expected_triggers = {
        "identity_verification_challenge_guard_trigger",
        "identity_verification_delivery_guard_trigger",
        "identity_verification_request_guard_trigger",
        "identity_verified_contact_guard_trigger",
        "identity_verification_limit_guard_trigger",
    }
    expected_functions = {
        "identity_guard_verification_challenge",
        "identity_guard_verification_delivery",
        "identity_reject_verification_request_update",
        "identity_guard_verified_contact",
        "identity_guard_verification_limit_bucket",
    }

    assert reverse_sql.count("DROP TRIGGER") == len(expected_triggers)
    assert reverse_sql.count("DROP FUNCTION") == len(expected_functions)
    for trigger_name in expected_triggers:
        assert f"DROP TRIGGER IF EXISTS {trigger_name}" in reverse_sql
    for function_name in expected_functions:
        assert f"DROP FUNCTION IF EXISTS {function_name}()" in reverse_sql
