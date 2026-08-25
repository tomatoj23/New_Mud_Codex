from __future__ import annotations

from dataclasses import replace

import pytest

from new_mud.apps.content.registry import (
    RegistryCatalog,
    RegistryDefinition,
    RegistryError,
    RegistryReference,
)


def definition(
    *,
    key: str,
    version: str = "1.0.0",
    dependencies: tuple[RegistryReference, ...] = (),
    definition_hash: str | None = None,
) -> RegistryDefinition:
    return RegistryDefinition.build(
        registry_kind="rule",
        registry_key=key,
        registry_version=version,
        summary=key,
        source_module="tests.registry",
        declaration={
            "handler_key": "handler.rule",
            "input_schema": {},
            "output_schema": {},
            "determinism": "deterministic",
        },
        dependencies=dependencies,
        definition_hash=definition_hash,
    )


def test_active_registry_key_cannot_have_two_versions() -> None:
    with pytest.raises(RegistryError) as captured:
        RegistryCatalog.from_definitions(
            (
                definition(key="rule.movement", version="1.0.0"),
                definition(key="rule.movement", version="2.0.0"),
            )
        )

    assert captured.value.code == "REGISTRY_DUPLICATE_KEY"


def test_registry_reference_cycle_is_rejected() -> None:
    first = definition(
        key="rule.first",
        dependencies=(RegistryReference("rule", "rule.second", "1.0.0"),),
    )
    second = definition(
        key="rule.second",
        dependencies=(RegistryReference("rule", "rule.first", "1.0.0"),),
    )

    with pytest.raises(RegistryError) as captured:
        RegistryCatalog.from_definitions((first, second))

    assert captured.value.code == "REGISTRY_REFERENCE_CYCLE"


def test_definition_hash_must_match_transitive_declaration() -> None:
    invalid = definition(key="rule.invalid", definition_hash="0" * 64)

    with pytest.raises(RegistryError) as captured:
        RegistryCatalog.from_definitions((invalid,))

    assert captured.value.code == "REGISTRY_VERSION_CONTENT_MISMATCH"


def test_definition_hash_changes_when_transitive_dependency_changes() -> None:
    dependency_v1 = definition(key="rule.dependency", version="1.0.0")
    root_v1 = definition(
        key="rule.root",
        dependencies=(RegistryReference.from_definition(dependency_v1),),
    )
    first_catalog = RegistryCatalog.from_definitions((dependency_v1, root_v1))

    dependency_v2 = definition(key="rule.dependency", version="2.0.0")
    root_v2 = definition(
        key="rule.root",
        dependencies=(RegistryReference("rule", "rule.dependency", "2.0.0"),),
    )
    second_catalog = RegistryCatalog.from_definitions((dependency_v2, root_v2))

    first_hash = first_catalog.resolve_active("rule", "rule.root").definition_hash
    second_hash = second_catalog.resolve_active("rule", "rule.root").definition_hash
    assert first_hash != second_hash


def test_registry_identity_type_errors_are_stable_schema_errors() -> None:
    invalid = RegistryDefinition.build(
        registry_kind="rule",
        registry_key="rule.invalid",
        registry_version="1.0.0",
        summary="invalid",
        source_module="tests.registry",
        declaration={
            "handler_key": "handler.rule",
            "input_schema": {},
            "output_schema": {},
            "determinism": "deterministic",
        },
    )
    invalid = replace(invalid, registry_key=123)  # type: ignore[arg-type]

    with pytest.raises(RegistryError) as captured:
        RegistryCatalog.from_definitions((invalid,))

    assert captured.value.code == "REGISTRY_SCHEMA_INVALID"


def test_exact_registry_resolution_reports_missing_and_hash_mismatch() -> None:
    catalog = RegistryCatalog.from_definitions((definition(key="rule.exact"),))

    with pytest.raises(RegistryError) as missing:
        catalog.resolve_exact(RegistryReference("rule", "rule.other", "1.0.0", "a" * 64))
    assert missing.value.code == "REGISTRY_COMPAT_DEFINITION_MISSING"

    with pytest.raises(RegistryError) as mismatch:
        catalog.resolve_exact(RegistryReference("rule", "rule.exact", "1.0.0", "a" * 64))
    assert mismatch.value.code == "REGISTRY_VERSION_CONTENT_MISMATCH"
