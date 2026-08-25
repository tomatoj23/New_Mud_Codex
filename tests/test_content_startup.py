from __future__ import annotations

from dataclasses import replace

import pytest
from django.db import transaction

from new_mud.apps.content.models import (
    BlueprintHead,
    BlueprintRevision,
    ContentReleaseBatch,
    ContentReleaseHead,
    ContentReleaseItem,
    ResolvedRegistryDependency,
)
from new_mud.apps.content.registry import (
    RegistryCatalog,
    RegistryDefinition,
    RegistryReference,
)
from new_mud.apps.content.resolver import ContentResolutionError, ContentResolver
from new_mud.apps.content.startup import (
    ContentStartupError,
    ContentStartupStatus,
    SeedBundle,
    _verify_published_revision,
    bootstrap_seed_bundle,
)

pytestmark = pytest.mark.django_db(transaction=True)


def build_room_bundle(*, behavior_profile_keys: tuple[str, ...] = ()) -> SeedBundle:
    return SeedBundle.build(
        seed_bundle_id="test.seed.v1",
        target_content_release="test.release",
        manifest_version="1.0.0",
        compiler_contract_version="blueprint-compiler/1",
        blueprints=(
            {
                "blueprint_key": "room.test.start",
                "kind": "room",
                "version": "1.0.0",
                "parent_keys": [],
                "source_type": "file",
                "tags": [],
                "behavior_profile_keys": list(behavior_profile_keys),
                "spawn_policy": {"update_mode": "new_only"},
                "data": {"spawn_entries": [], "external_exit_boundaries": []},
            },
        ),
    )


def build_registry_catalog() -> RegistryCatalog:
    handler = RegistryDefinition.build(
        registry_kind="handler",
        registry_key="handler.room",
        registry_version="1.0.0",
        summary="Room handler",
        source_module="tests.registry",
        declaration={
            "callable_path": "operator.add",
            "input_schema": {},
            "result_schema_version": "1.0.0",
            "idempotency": "idempotent",
        },
        artifact_hash="a" * 64,
    )
    profile = RegistryDefinition.build(
        registry_kind="behavior_profile",
        registry_key="profile.room.default",
        registry_version="1.0.0",
        summary="Default room profile",
        source_module="tests.registry",
        declaration={"entity_kinds": ["room"]},
        dependencies=(RegistryReference.from_definition(handler),),
    )
    return RegistryCatalog.from_definitions((handler, profile))


def test_first_start_bootstraps_one_complete_active_release() -> None:
    bundle = build_room_bundle()

    result = bootstrap_seed_bundle(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        bundle=bundle,
    )

    assert result.status is ContentStartupStatus.BOOTSTRAPPED
    assert result.identity.release_version == 1
    assert result.identity.seed_bundle_id == "test.seed.v1"
    assert result.identity.blueprint_count == 1
    assert len(result.identity.release_hash) == 64


def test_repeated_start_verifies_existing_release_without_creating_rows() -> None:
    bundle = build_room_bundle()
    first = bootstrap_seed_bundle(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        bundle=bundle,
    )

    second = bootstrap_seed_bundle(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        bundle=bundle,
    )

    assert second.status is ContentStartupStatus.VERIFIED
    assert second.identity == first.identity
    assert BlueprintHead.objects.count() == 1
    assert BlueprintRevision.objects.count() == 1
    assert ContentReleaseBatch.objects.count() == 1
    assert ContentReleaseItem.objects.count() == 1


def test_active_resolver_reads_the_revision_fixed_by_the_active_batch() -> None:
    bundle = build_room_bundle()
    startup = bootstrap_seed_bundle(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        bundle=bundle,
    )

    resolved = ContentResolver.resolve_active(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        target_content_release="test.release",
        blueprint_key="room.test.start",
    )

    assert resolved.batch_id == startup.identity.batch_id
    assert resolved.blueprint_key == "room.test.start"
    assert resolved.compiled_payload["resolved_data"] == {
        "spawn_entries": [],
        "external_exit_boundaries": [],
    }


def test_pinned_resolver_keeps_the_historical_revision_after_batch_switch() -> None:
    bundle = build_room_bundle()
    bootstrap_seed_bundle(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        bundle=bundle,
    )
    original = ContentResolver.resolve_active(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        target_content_release="test.release",
        blueprint_key="room.test.start",
    )
    release_head = ContentReleaseHead.objects.get(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        target_content_release="test.release",
    )
    blueprint_head = BlueprintHead.objects.get(blueprint_key="room.test.start")
    original_revision = BlueprintRevision.objects.get(pk=original.revision_id)

    with transaction.atomic():
        next_batch = ContentReleaseBatch.objects.create(
            release_head=release_head,
            release_version=2,
            parent_batch=release_head.active_batch,
            manifest_version="1.1.0",
            release_hash="9" * 64,
            created_by="contract-test",
        )
        assert isinstance(original_revision.compiled_payload, dict)
        next_payload = {**original_revision.compiled_payload, "version": "1.1.0"}
        next_revision = BlueprintRevision.objects.create(
            head=blueprint_head,
            blueprint_key=blueprint_head.blueprint_key,
            revision_kind=BlueprintRevision.RevisionKind.PUBLISHED,
            source_revision=original_revision,
            raw_payload={**original_revision.raw_payload, "version": "1.1.0"},
            compiled_payload=next_payload,
            content_hash="6" * 64,
            compiled_hash="7" * 64,
            resolved_dependency_hash="8" * 64,
            compiler_contract_version="blueprint-compiler/1",
            publication_reason=BlueprintRevision.PublicationReason.CONTENT_PUBLISH,
            created_in_batch=next_batch,
            created_by="contract-test",
        )
        ContentReleaseItem.objects.create(
            batch=next_batch,
            release_head=release_head,
            blueprint_head=blueprint_head,
            blueprint_key=blueprint_head.blueprint_key,
            published_revision=next_revision,
        )
        BlueprintHead.objects.filter(pk=blueprint_head.pk).update(published_revision=next_revision)
        ContentReleaseHead.objects.filter(pk=release_head.pk).update(
            active_batch=next_batch,
            release_version=2,
        )

    pinned = ContentResolver.resolve_pinned(revision_id=original.revision_id)

    assert pinned.revision_id == original.revision_id
    assert pinned.compiled_payload["version"] == "1.0.0"


def test_tampered_seed_bundle_is_rejected_before_initialization() -> None:
    tampered = replace(build_room_bundle(), content_hash="0" * 64)

    with pytest.raises(ContentStartupError) as captured:
        bootstrap_seed_bundle(
            instance_id="test-instance",
            mudlib_key="test-mudlib",
            bundle=tampered,
        )

    assert captured.value.code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert BlueprintHead.objects.count() == 0
    assert ContentReleaseBatch.objects.count() == 0


def test_unsupported_compiler_contract_is_rejected_before_initialization() -> None:
    unsupported = SeedBundle.build(
        seed_bundle_id="test.seed.v1",
        target_content_release="test.release",
        manifest_version="1.0.0",
        compiler_contract_version="blueprint-compiler/999",
        blueprints=build_room_bundle().blueprints,
    )

    with pytest.raises(ContentStartupError) as captured:
        bootstrap_seed_bundle(
            instance_id="test-instance",
            mudlib_key="test-mudlib",
            bundle=unsupported,
        )

    assert captured.value.code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert BlueprintHead.objects.count() == 0


def test_seed_bootstrap_persists_and_resolves_exact_parent_dependency() -> None:
    parent = build_room_bundle().blueprints[0]
    child = {
        **parent,
        "blueprint_key": "room.test.child",
        "parent_keys": ["room.test.start"],
    }
    bundle = SeedBundle.build(
        seed_bundle_id="test.seed.parents.v1",
        target_content_release="test.release",
        manifest_version="1.0.0",
        compiler_contract_version="blueprint-compiler/1",
        blueprints=(parent, child),
    )
    bootstrap_seed_bundle(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        bundle=bundle,
    )

    resolved = ContentResolver.resolve_active(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        target_content_release="test.release",
        blueprint_key="room.test.child",
    )

    assert len(resolved.blueprint_dependencies) == 1
    dependency = resolved.blueprint_dependencies[0]
    assert dependency.path == "/parent_keys/0"
    assert dependency.kind == "parent"
    assert dependency.target_blueprint_key == "room.test.start"
    assert dependency.target_revision_id != resolved.revision_id


def test_registry_dependency_is_persisted_and_resolved_exactly() -> None:
    catalog = build_registry_catalog()
    bundle = build_room_bundle(behavior_profile_keys=("profile.room.default",))

    bootstrap_seed_bundle(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        bundle=bundle,
        registry_catalog=catalog,
    )

    resolved = ContentResolver.resolve_active(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        target_content_release="test.release",
        blueprint_key="room.test.start",
        registry_catalog=catalog,
    )

    assert len(resolved.registry_dependencies) == 1
    dependency = resolved.registry_dependencies[0]
    assert dependency.path == "/behavior_profile_keys/0"
    assert dependency.registry_kind == "behavior_profile"
    assert dependency.registry_key == "profile.room.default"
    assert dependency.registry_version == "1.0.0"
    assert (
        dependency.definition_hash
        == catalog.resolve_active("behavior_profile", "profile.room.default").definition_hash
    )
    assert ResolvedRegistryDependency.objects.count() == 1
    assert (
        resolved.compiled_payload["resolved_registry_dependencies"][0]["definition_hash"]
        == dependency.definition_hash
    )


def test_pinned_registry_dependency_uses_compatibility_definition() -> None:
    old_catalog = build_registry_catalog()
    bundle = build_room_bundle(behavior_profile_keys=("profile.room.default",))
    bootstrap_seed_bundle(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        bundle=bundle,
        registry_catalog=old_catalog,
    )
    original = ContentResolver.resolve_active(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        target_content_release="test.release",
        blueprint_key="room.test.start",
        registry_catalog=old_catalog,
    )

    new_handler = RegistryDefinition.build(
        registry_kind="handler",
        registry_key="handler.room",
        registry_version="2.0.0",
        summary="Room handler v2",
        source_module="tests.registry",
        declaration={
            "callable_path": "operator.sub",
            "input_schema": {},
            "result_schema_version": "1.0.0",
            "idempotency": "idempotent",
        },
        artifact_hash="b" * 64,
    )
    new_profile = RegistryDefinition.build(
        registry_kind="behavior_profile",
        registry_key="profile.room.default",
        registry_version="2.0.0",
        summary="Default room profile v2",
        source_module="tests.registry",
        declaration={"entity_kinds": ["room"], "variant": 2},
        dependencies=(RegistryReference.from_definition(new_handler),),
    )
    current_catalog = RegistryCatalog.from_definitions(
        (new_handler, new_profile),
        compatibility_definitions=old_catalog.definitions,
    )

    pinned = ContentResolver.resolve_pinned(
        revision_id=original.revision_id,
        registry_catalog=current_catalog,
    )

    assert (
        pinned.registry_dependencies[0].definition_hash
        == original.registry_dependencies[0].definition_hash
    )


def test_active_registry_drift_fails_closed_while_pinned_uses_compatibility() -> None:
    old_catalog = build_registry_catalog()
    bundle = build_room_bundle(behavior_profile_keys=("profile.room.default",))
    bootstrap_seed_bundle(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        bundle=bundle,
        registry_catalog=old_catalog,
    )
    new_handler = RegistryDefinition.build(
        registry_kind="handler",
        registry_key="handler.room",
        registry_version="2.0.0",
        summary="Room handler v2",
        source_module="tests.registry",
        declaration={
            "callable_path": "operator.sub",
            "input_schema": {},
            "result_schema_version": "1.0.0",
            "idempotency": "idempotent",
        },
        artifact_hash="b" * 64,
    )
    new_profile = RegistryDefinition.build(
        registry_kind="behavior_profile",
        registry_key="profile.room.default",
        registry_version="2.0.0",
        summary="Default room profile v2",
        source_module="tests.registry",
        declaration={"entity_kinds": ["room"], "variant": 2},
        dependencies=(RegistryReference.from_definition(new_handler),),
    )
    current_catalog = RegistryCatalog.from_definitions(
        (new_handler, new_profile),
        compatibility_definitions=old_catalog.definitions,
    )

    with pytest.raises(ContentResolutionError) as captured:
        ContentResolver.resolve_active(
            instance_id="test-instance",
            mudlib_key="test-mudlib",
            target_content_release="test.release",
            blueprint_key="room.test.start",
            registry_catalog=current_catalog,
        )

    assert captured.value.code == "BLUEPRINT_REGISTRY_VERSION_UNAVAILABLE"


def test_existing_start_rejects_tampered_compiled_payload() -> None:
    bundle = build_room_bundle()
    bootstrap_seed_bundle(
        instance_id="test-instance",
        mudlib_key="test-mudlib",
        bundle=bundle,
    )
    revision = BlueprintRevision.objects.get(blueprint_key="room.test.start")
    assert isinstance(revision.compiled_payload, dict)
    revision.compiled_payload = {**revision.compiled_payload, "version": "9.9.9"}

    with pytest.raises(ContentStartupError) as captured:
        _verify_published_revision(
            revision,
            registry_catalog=RegistryCatalog.empty(),
            active_registry=True,
        )

    assert captured.value.code == "BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH"


def test_non_string_behavior_profile_reference_is_schema_error() -> None:
    bundle = build_room_bundle(behavior_profile_keys=("profile.room.default",))
    invalid = SeedBundle.build(
        seed_bundle_id=bundle.seed_bundle_id,
        target_content_release=bundle.target_content_release,
        manifest_version=bundle.manifest_version,
        compiler_contract_version=bundle.compiler_contract_version,
        blueprints=(
            {
                **bundle.blueprints[0],
                "behavior_profile_keys": [123],
            },
        ),
    )

    with pytest.raises(ContentStartupError) as captured:
        bootstrap_seed_bundle(
            instance_id="test-instance",
            mudlib_key="test-mudlib",
            bundle=invalid,
            registry_catalog=build_registry_catalog(),
        )

    assert captured.value.code == "BLUEPRINT_SCHEMA_INVALID"


def test_registry_reference_version_conflict_has_stable_error() -> None:
    base = build_room_bundle().blueprints[0]
    bundle = SeedBundle.build(
        seed_bundle_id="test.seed.registry-version.v1",
        target_content_release="test.release",
        manifest_version="1.0.0",
        compiler_contract_version="blueprint-compiler/1",
        blueprints=(
            {
                **base,
                "registry_refs": [
                    {
                        "path": "/data/room_handler",
                        "registry_kind": "handler",
                        "registry_key": "handler.room",
                        "registry_version": "2.0.0",
                    }
                ],
            },
        ),
    )

    with pytest.raises(ContentStartupError) as captured:
        bootstrap_seed_bundle(
            instance_id="test-instance",
            mudlib_key="test-mudlib",
            bundle=bundle,
            registry_catalog=build_registry_catalog(),
        )

    assert captured.value.code == "BLUEPRINT_REGISTRY_VERSION_UNAVAILABLE"


def test_missing_registry_dependency_fails_closed_before_persistence() -> None:
    bundle = build_room_bundle(behavior_profile_keys=("profile.missing",))

    with pytest.raises(ContentStartupError) as captured:
        bootstrap_seed_bundle(
            instance_id="test-instance",
            mudlib_key="test-mudlib",
            bundle=bundle,
            registry_catalog=RegistryCatalog.empty(),
        )

    assert captured.value.code == "BLUEPRINT_PROFILE_NOT_FOUND"
    assert BlueprintHead.objects.count() == 0
    assert ResolvedRegistryDependency.objects.count() == 0
