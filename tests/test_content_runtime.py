from __future__ import annotations

import json
from pathlib import Path

import pytest

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
from new_mud.apps.content.resolver import ContentResolver
from new_mud.apps.content.runtime import ContentRuntime, ContentRuntimeStatus
from new_mud.apps.content.startup import ContentStartupStatus
from new_mud.mudlibs.jinyong_core.registry import build_registry_catalog

pytestmark = pytest.mark.django_db(transaction=True)


def test_content_runtime_start_is_repeatable_and_returns_release_identity() -> None:
    runtime = ContentRuntime(instance_id="runtime-instance")

    first = runtime.start()
    second = runtime.start()

    assert first.status is ContentRuntimeStatus.READY
    assert first.startup_status is ContentStartupStatus.BOOTSTRAPPED
    assert first.artifact_hash == (
        "073ac8cce19d4375a230de0b471e1ee2e58664645b34416de695f0b9ecdf8a24"
    )
    assert first.identity is not None
    assert first.identity.release_version == 1
    assert first.identity.blueprint_count == 1
    assert second.status is ContentRuntimeStatus.READY
    assert second.startup_status is ContentStartupStatus.VERIFIED
    assert second.identity == first.identity


def test_content_runtime_readiness_never_bootstraps_missing_content() -> None:
    runtime = ContentRuntime(instance_id="readiness-instance")

    readiness = runtime.readiness()
    startup = runtime.start()

    assert readiness.status is ContentRuntimeStatus.NOT_READY
    assert readiness.error_code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert readiness.identity is None
    assert startup.startup_status is ContentStartupStatus.BOOTSTRAPPED


def test_content_runtime_start_reports_partial_namespace_failure() -> None:
    BlueprintHead.objects.create(
        instance_id="partial-instance",
        mudlib_key="jinyong.core",
        blueprint_key="room.partial.start",
    )
    runtime = ContentRuntime(instance_id="partial-instance")

    failure = runtime.start()

    assert failure.status is ContentRuntimeStatus.NOT_READY
    assert failure.error_code == "CONTENT_RELEASE_SCOPE_MISMATCH"
    assert failure.error_message == "content namespace is partially initialized"
    assert failure.identity is None


def test_content_runtime_readiness_reports_missing_active_batch() -> None:
    runtime = ContentRuntime(instance_id="missing-active-instance")
    startup = runtime.start()
    assert startup.identity is not None
    ContentReleaseHead.objects.filter(release_head_id=startup.identity.release_head_id).update(
        active_batch=None, release_version=0
    )

    readiness = runtime.readiness()

    assert readiness.status is ContentRuntimeStatus.NOT_READY
    assert readiness.error_code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert readiness.error_message == "content release has no active batch"
    assert readiness.identity is None


def test_content_runtime_readiness_reports_active_release_hash_mismatch() -> None:
    runtime = ContentRuntime(instance_id="release-hash-instance")
    startup = runtime.start()
    assert startup.identity is not None
    release_head = ContentReleaseHead.objects.select_related("active_batch").get(
        release_head_id=startup.identity.release_head_id
    )
    active_item = ContentReleaseItem.objects.get(batch=release_head.active_batch)
    mismatched_batch = ContentReleaseBatch.objects.create(
        release_head=release_head,
        release_version=2,
        parent_batch=release_head.active_batch,
        manifest_version="1.0.0",
        release_hash="0" * 64,
        created_by="runtime-readiness-test",
    )
    ContentReleaseItem.objects.create(
        batch=mismatched_batch,
        release_head=release_head,
        blueprint_head=active_item.blueprint_head,
        blueprint_key=active_item.blueprint_key,
        published_revision=active_item.published_revision,
    )
    ContentReleaseHead.objects.filter(pk=release_head.pk).update(
        active_batch=mismatched_batch,
        release_version=2,
    )

    readiness = runtime.readiness()

    assert readiness.status is ContentRuntimeStatus.NOT_READY
    assert readiness.error_code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert readiness.error_message == "active content release hash does not match its items"


def test_content_runtime_readiness_reports_missing_registry_dependency() -> None:
    runtime = ContentRuntime(instance_id="missing-registry-instance")
    startup = runtime.start()
    assert startup.identity is not None
    ResolvedRegistryDependency.objects.all().delete()

    readiness = runtime.readiness()

    assert readiness.status is ContentRuntimeStatus.NOT_READY
    assert readiness.error_code == "BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH"
    assert readiness.error_message is not None
    assert readiness.error_message.startswith("compiled registry dependencies mismatch revision ")


def test_content_runtime_rejects_compiler_contract_mismatch(tmp_path: Path) -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "new_mud"
        / "mudlibs"
        / "jinyong_core"
        / "seed"
        / "content-seed-v1.json"
    )
    incompatible = json.loads(source.read_text(encoding="utf-8"))
    incompatible["compiler_contract_version"] = "blueprint-compiler/0"
    artifact_path = tmp_path / "incompatible-seed.json"
    artifact_path.write_text(json.dumps(incompatible), encoding="utf-8")
    runtime = ContentRuntime(
        instance_id="compiler-mismatch-instance",
        artifact_path=artifact_path,
    )

    startup = runtime.start()
    readiness = runtime.readiness()

    assert startup.status is ContentRuntimeStatus.NOT_READY
    assert startup.error_code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert readiness.status is ContentRuntimeStatus.NOT_READY
    assert readiness.error_code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert readiness.error_message is not None
    assert "compiler_contract_version" in readiness.error_message


def test_content_runtime_readiness_rejects_published_revision_compiler_mismatch() -> None:
    runtime = ContentRuntime(instance_id="published-compiler-instance")
    startup = runtime.start()
    assert startup.identity is not None
    release_head = ContentReleaseHead.objects.select_related("active_batch").get(
        release_head_id=startup.identity.release_head_id
    )
    active_item = ContentReleaseItem.objects.select_related("published_revision").get(
        batch=release_head.active_batch
    )
    original = active_item.published_revision
    incompatible_batch = ContentReleaseBatch.objects.create(
        release_head=release_head,
        release_version=2,
        parent_batch=release_head.active_batch,
        manifest_version="1.0.0",
        release_hash="0" * 64,
        created_by="runtime-readiness-test",
    )
    incompatible_revision = BlueprintRevision.objects.create(
        head=active_item.blueprint_head,
        blueprint_key=active_item.blueprint_key,
        revision_kind=BlueprintRevision.RevisionKind.PUBLISHED,
        source_revision=original,
        raw_payload=original.raw_payload,
        compiled_payload=original.compiled_payload,
        content_hash=original.content_hash,
        compiled_hash=original.compiled_hash,
        resolved_dependency_hash=original.resolved_dependency_hash,
        compiler_contract_version="blueprint-compiler/0",
        publication_reason=BlueprintRevision.PublicationReason.CONTENT_PUBLISH,
        created_in_batch=incompatible_batch,
        created_by="runtime-readiness-test",
    )
    ContentReleaseItem.objects.create(
        batch=incompatible_batch,
        release_head=release_head,
        blueprint_head=active_item.blueprint_head,
        blueprint_key=active_item.blueprint_key,
        published_revision=incompatible_revision,
    )
    ContentReleaseHead.objects.filter(pk=release_head.pk).update(
        active_batch=incompatible_batch,
        release_version=2,
    )

    readiness = runtime.readiness()

    assert readiness.status is ContentRuntimeStatus.NOT_READY
    assert readiness.error_code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert readiness.error_message is not None
    assert readiness.error_message.startswith("published revision compiler contract mismatch for ")


def test_content_runtime_readiness_rejects_active_registry_drift() -> None:
    old_catalog = build_registry_catalog()
    initial_runtime = ContentRuntime(
        instance_id="registry-drift-instance",
        registry_catalog=old_catalog,
    )
    startup = initial_runtime.start()
    assert startup.identity is not None
    next_handler = RegistryDefinition.build(
        registry_kind="handler",
        registry_key="handler.room.default",
        registry_version="2.0.0",
        summary="Default room behavior handler v2",
        source_module="tests.test_content_runtime",
        declaration={
            "callable_path": "operator.sub",
            "input_schema": {"type": "object"},
            "result_schema_version": "1.0.0",
            "idempotency": "idempotent",
        },
        artifact_hash="a" * 64,
    )
    next_profile = RegistryDefinition.build(
        registry_kind="behavior_profile",
        registry_key="profile.room.default",
        registry_version="2.0.0",
        summary="Default static room behavior profile v2",
        source_module="tests.test_content_runtime",
        declaration={"entity_kinds": ["room"], "variant": 2},
        dependencies=(RegistryReference.from_definition(next_handler),),
    )
    drifted_catalog = RegistryCatalog.from_definitions(
        (next_handler, next_profile),
        compatibility_definitions=old_catalog.definitions,
    )

    readiness = ContentRuntime(
        instance_id="registry-drift-instance",
        registry_catalog=drifted_catalog,
    ).readiness()

    assert readiness.status is ContentRuntimeStatus.NOT_READY
    assert readiness.error_code == "BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH"
    assert readiness.error_message == (
        "seed artifact Registry context differs from active definitions"
    )


def test_active_batch_switch_updates_readiness_without_moving_pinned_revision() -> None:
    runtime = ContentRuntime(instance_id="batch-switch-instance")
    startup = runtime.start()
    assert startup.identity is not None
    catalog = build_registry_catalog()
    original = ContentResolver.resolve_active(
        instance_id="batch-switch-instance",
        mudlib_key="jinyong.core",
        target_content_release="jinyong.release",
        blueprint_key="room.xiangyang.east_gate",
        registry_catalog=catalog,
    )
    release_head = ContentReleaseHead.objects.select_related("active_batch").get(
        release_head_id=startup.identity.release_head_id
    )
    active_item = ContentReleaseItem.objects.get(batch=release_head.active_batch)
    next_batch = ContentReleaseBatch.objects.create(
        release_head=release_head,
        release_version=2,
        parent_batch=release_head.active_batch,
        manifest_version="1.0.0",
        release_hash=startup.identity.release_hash,
        created_by="runtime-readiness-test",
    )
    ContentReleaseItem.objects.create(
        batch=next_batch,
        release_head=release_head,
        blueprint_head=active_item.blueprint_head,
        blueprint_key=active_item.blueprint_key,
        published_revision=active_item.published_revision,
    )
    ContentReleaseHead.objects.filter(pk=release_head.pk).update(
        active_batch=next_batch,
        release_version=2,
    )

    readiness = runtime.readiness()
    active = ContentResolver.resolve_active(
        instance_id="batch-switch-instance",
        mudlib_key="jinyong.core",
        target_content_release="jinyong.release",
        blueprint_key="room.xiangyang.east_gate",
        registry_catalog=catalog,
    )
    pinned = ContentResolver.resolve_pinned(
        revision_id=original.revision_id,
        registry_catalog=catalog,
    )

    assert readiness.status is ContentRuntimeStatus.READY
    assert readiness.identity is not None
    assert readiness.identity.batch_id == next_batch.batch_id
    assert readiness.identity.release_version == 2
    assert active.batch_id == next_batch.batch_id
    assert active.revision_id == original.revision_id
    assert pinned.batch_id == startup.identity.batch_id
    assert pinned.revision_id == original.revision_id
