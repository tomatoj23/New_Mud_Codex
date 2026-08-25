from __future__ import annotations

import copy
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
from django.db import DatabaseError, close_old_connections, connection, transaction

from new_mud.apps.content.models import (
    BlueprintHead,
    BlueprintRevision,
    ContentReleaseBatch,
    ContentReleaseHead,
    ContentReleaseItem,
    ContentStartupFailure,
    ResolvedBlueprintDependency,
    ResolvedRegistryDependency,
)
from new_mud.apps.content.registry import canonical_sha256
from new_mud.apps.content.runtime import (
    ContentRuntime,
    ContentRuntimeSnapshot,
    ContentRuntimeStatus,
)
from new_mud.apps.content.startup import ContentStartupStatus, SeedBundle

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(
        os.getenv("RUN_POSTGRES_TESTS") != "1",
        reason="requires the PostgreSQL contract-test service",
    ),
]


def _install_release_head_insert_delay() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE FUNCTION test_delay_content_release_head_insert()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                PERFORM pg_sleep(0.25);
                RETURN NEW;
            END;
            $$
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER test_delay_content_release_head_insert
            BEFORE INSERT ON content_contentreleasehead
            FOR EACH ROW
            EXECUTE FUNCTION test_delay_content_release_head_insert()
            """
        )


def _remove_release_head_insert_delay() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DROP TRIGGER IF EXISTS test_delay_content_release_head_insert
            ON content_contentreleasehead
            """
        )
        cursor.execute("DROP FUNCTION IF EXISTS test_delay_content_release_head_insert()")


def _install_first_release_item_failure() -> None:
    with connection.cursor() as cursor:
        cursor.execute("CREATE SEQUENCE test_content_startup_failure_once")
        cursor.execute(
            """
            CREATE FUNCTION test_fail_first_content_release_item_insert()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                IF nextval('test_content_startup_failure_once') = 1 THEN
                    RAISE EXCEPTION 'injected first-contender startup failure';
                END IF;
                RETURN NEW;
            END;
            $$
            """
        )
        cursor.execute(
            """
            CREATE TRIGGER test_fail_first_content_release_item_insert
            BEFORE INSERT ON content_contentreleaseitem
            FOR EACH ROW
            EXECUTE FUNCTION test_fail_first_content_release_item_insert()
            """
        )


def _remove_first_release_item_failure() -> None:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            DROP TRIGGER IF EXISTS test_fail_first_content_release_item_insert
            ON content_contentreleaseitem
            """
        )
        cursor.execute("DROP FUNCTION IF EXISTS test_fail_first_content_release_item_insert()")
        cursor.execute("DROP SEQUENCE IF EXISTS test_content_startup_failure_once")


_FAILURE_STAGE_TARGETS = {
    "release_head": ("content_contentreleasehead", "INSERT"),
    "blueprint_head": ("content_blueprinthead", "INSERT"),
    "batch": ("content_contentreleasebatch", "INSERT"),
    "revision": ("content_blueprintrevision", "INSERT"),
    "blueprint_dependency": ("content_resolvedblueprintdependency", "INSERT"),
    "registry_dependency": ("content_resolvedregistrydependency", "INSERT"),
    "release_item": ("content_contentreleaseitem", "INSERT"),
    "active_pointer": ("content_contentreleasehead", "UPDATE OF active_batch_id"),
}


def _install_startup_stage_failure(stage: str) -> None:
    table, event = _FAILURE_STAGE_TARGETS[stage]
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            CREATE FUNCTION test_fail_content_startup_write()
            RETURNS trigger
            LANGUAGE plpgsql
            AS $$
            BEGIN
                RAISE EXCEPTION 'injected startup failure at {stage}';
            END;
            $$
            """
        )
        cursor.execute(
            f"""
            CREATE TRIGGER test_fail_content_startup_write
            BEFORE {event} ON {table}
            FOR EACH ROW
            EXECUTE FUNCTION test_fail_content_startup_write()
            """
        )


def _remove_startup_stage_failure(stage: str) -> None:
    table, _ = _FAILURE_STAGE_TARGETS[stage]
    with connection.cursor() as cursor:
        cursor.execute(
            f"""
            DROP TRIGGER IF EXISTS test_fail_content_startup_write
            ON {table}
            """
        )
        cursor.execute("DROP FUNCTION IF EXISTS test_fail_content_startup_write()")


def _write_dependency_seed_artifact(tmp_path: Path) -> Path:
    source = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "new_mud"
        / "mudlibs"
        / "jinyong_core"
        / "seed"
        / "content-seed-v1.json"
    )
    raw = json.loads(source.read_text(encoding="utf-8"))
    parent = copy.deepcopy(raw["blueprints"][0])
    parent["blueprint_key"] = "room.matrix.parent"
    parent["data"]["display_name"] = "Matrix Parent"
    child = copy.deepcopy(raw["blueprints"][0])
    child["blueprint_key"] = "room.matrix.child"
    child["parent_keys"] = ["room.matrix.parent"]
    child["data"]["display_name"] = "Matrix Child"
    raw["blueprints"] = [parent, child]
    bundle = SeedBundle.build(
        seed_bundle_id=raw["seed_bundle_id"],
        target_content_release=raw["target_content_release"],
        manifest_version=raw["manifest_version"],
        compiler_contract_version=raw["compiler_contract_version"],
        blueprints=raw["blueprints"],
    )
    raw["content_hash"] = bundle.content_hash
    raw["artifact_hash"] = canonical_sha256(
        {key: value for key, value in raw.items() if key != "artifact_hash"}
    )
    artifact_path = tmp_path / "dependency-seed.json"
    artifact_path.write_text(json.dumps(raw), encoding="utf-8")
    return artifact_path


def _assert_content_namespace_is_empty() -> None:
    assert ContentReleaseHead.objects.count() == 0
    assert BlueprintHead.objects.count() == 0
    assert ContentReleaseBatch.objects.count() == 0
    assert BlueprintRevision.objects.count() == 0
    assert ResolvedBlueprintDependency.objects.count() == 0
    assert ResolvedRegistryDependency.objects.count() == 0
    assert ContentReleaseItem.objects.count() == 0


def _start_content_runtime(barrier: Barrier) -> ContentRuntimeSnapshot:
    close_old_connections()
    try:
        barrier.wait(timeout=5)
        return ContentRuntime(instance_id="concurrent-startup-instance").start()
    finally:
        close_old_connections()


def test_concurrent_first_start_converges_on_one_release_identity() -> None:
    _install_release_head_insert_delay()
    barrier = Barrier(2)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(_start_content_runtime, barrier) for _ in range(2)]
            results = [future.result(timeout=10) for future in futures]
    finally:
        _remove_release_head_insert_delay()

    assert {result.status for result in results} == {ContentRuntimeStatus.READY}
    assert {result.startup_status for result in results} == {
        ContentStartupStatus.BOOTSTRAPPED,
        ContentStartupStatus.VERIFIED,
    }
    assert results[0].identity == results[1].identity
    assert ContentReleaseHead.objects.count() == 1
    assert ContentReleaseBatch.objects.count() == 1
    assert ContentReleaseItem.objects.count() == 1
    assert BlueprintRevision.objects.count() == 1


def test_concurrent_start_recovers_after_first_contender_rolls_back() -> None:
    _install_first_release_item_failure()
    barrier = Barrier(2)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(_start_content_runtime, barrier) for _ in range(2)]
            results = [future.result(timeout=10) for future in futures]
    finally:
        _remove_first_release_item_failure()

    assert sorted(result.status for result in results) == [
        ContentRuntimeStatus.NOT_READY,
        ContentRuntimeStatus.READY,
    ]
    success = next(result for result in results if result.status is ContentRuntimeStatus.READY)
    failure = next(result for result in results if result.status is ContentRuntimeStatus.NOT_READY)
    assert success.startup_status is ContentStartupStatus.BOOTSTRAPPED
    assert success.identity is not None
    assert failure.identity is None
    assert failure.error_code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert failure.error_message == "content bootstrap transaction failed"
    assert ContentReleaseHead.objects.count() == 1
    assert ContentReleaseBatch.objects.count() == 1
    assert ContentReleaseItem.objects.count() == 1
    assert BlueprintRevision.objects.count() == 1
    audit = ContentStartupFailure.objects.get()
    assert audit.error_code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert audit.error_message == "content release validation failed"


def test_late_write_failure_rolls_back_is_audited_and_retry_succeeds() -> None:
    runtime = ContentRuntime(instance_id="retry-after-write-failure-instance")
    _install_startup_stage_failure("release_item")
    try:
        failure = runtime.start()
    finally:
        _remove_startup_stage_failure("release_item")

    audit = ContentStartupFailure.objects.get()
    assert failure.status is ContentRuntimeStatus.NOT_READY
    assert failure.identity is None
    assert failure.error_code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert failure.error_message == "content bootstrap transaction failed"
    assert audit.instance_id == "retry-after-write-failure-instance"
    assert audit.artifact_hash == (
        "073ac8cce19d4375a230de0b471e1ee2e58664645b34416de695f0b9ecdf8a24"
    )
    assert audit.error_code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert audit.error_message == "content release validation failed"
    assert not hasattr(audit, "batch_id")
    assert ContentReleaseHead.objects.count() == 0
    assert BlueprintHead.objects.count() == 0
    assert ContentReleaseBatch.objects.count() == 0
    assert BlueprintRevision.objects.count() == 0
    assert ResolvedBlueprintDependency.objects.count() == 0
    assert ResolvedRegistryDependency.objects.count() == 0
    assert ContentReleaseItem.objects.count() == 0

    retry = runtime.start()

    assert retry.status is ContentRuntimeStatus.READY
    assert retry.startup_status is ContentStartupStatus.BOOTSTRAPPED
    assert ContentStartupFailure.objects.count() == 1
    assert ContentReleaseHead.objects.count() == 1
    assert ContentReleaseBatch.objects.count() == 1
    assert BlueprintRevision.objects.count() == 1
    assert ResolvedRegistryDependency.objects.count() == 1
    assert ContentReleaseItem.objects.count() == 1


@pytest.mark.parametrize("stage", tuple(_FAILURE_STAGE_TARGETS))
def test_each_startup_write_stage_rolls_back_the_complete_namespace(
    stage: str,
    tmp_path: Path,
) -> None:
    runtime = ContentRuntime(
        instance_id=f"failure-matrix-{stage}",
        artifact_path=_write_dependency_seed_artifact(tmp_path),
    )
    _install_startup_stage_failure(stage)
    try:
        failure = runtime.start()
    finally:
        _remove_startup_stage_failure(stage)

    assert failure.status is ContentRuntimeStatus.NOT_READY
    assert failure.error_code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert failure.error_message == "content bootstrap transaction failed"
    _assert_content_namespace_is_empty()
    audit = ContentStartupFailure.objects.get()
    assert audit.instance_id == f"failure-matrix-{stage}"
    assert audit.error_code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert audit.error_message == "content release validation failed"


def test_startup_failure_audit_rejects_update_and_delete() -> None:
    failure = ContentStartupFailure.objects.create(
        instance_id="immutable-audit-instance",
        mudlib_key="jinyong.core",
        target_content_release="jinyong.release",
        seed_bundle_id="jinyong.seed.v1",
        artifact_hash=None,
        error_code="CONTENT_RELEASE_VALIDATION_FAILED",
        error_message="original failure",
    )

    with pytest.raises(DatabaseError), transaction.atomic():
        ContentStartupFailure.objects.filter(pk=failure.pk).update(
            error_message="rewritten failure"
        )
    with pytest.raises(DatabaseError), transaction.atomic():
        ContentStartupFailure.objects.filter(pk=failure.pk).delete()

    failure.refresh_from_db()
    assert failure.error_message == "original failure"


def test_missing_blueprint_dependency_is_audited_without_replacing_release(
    tmp_path: Path,
) -> None:
    runtime = ContentRuntime(
        instance_id="missing-blueprint-dependency-instance",
        artifact_path=_write_dependency_seed_artifact(tmp_path),
    )
    startup = runtime.start()
    assert startup.status is ContentRuntimeStatus.READY
    assert startup.identity is not None
    ResolvedBlueprintDependency.objects.all().delete()

    failure = runtime.start()

    assert failure.status is ContentRuntimeStatus.NOT_READY
    assert failure.error_code == "BLUEPRINT_REFERENCE_NOT_FOUND"
    assert failure.error_message is not None
    assert failure.error_message.startswith("compiled blueprint dependencies mismatch revision ")
    audit = ContentStartupFailure.objects.get()
    assert audit.error_code == "BLUEPRINT_REFERENCE_NOT_FOUND"
    assert audit.error_message == "blueprint dependency validation failed"
    assert ContentReleaseHead.objects.count() == 1
    assert ContentReleaseBatch.objects.count() == 1
    assert BlueprintRevision.objects.count() == 2
    assert ResolvedBlueprintDependency.objects.count() == 0
    assert ResolvedRegistryDependency.objects.count() == 2
    assert ContentReleaseItem.objects.count() == 2
