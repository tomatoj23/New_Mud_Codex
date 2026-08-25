from __future__ import annotations

import json
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command

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
    canonical_sha256,
)
from new_mud.apps.content.seed_artifact import (
    SeedArtifactExpectation,
    bootstrap_seed_artifact,
    load_seed_artifact,
)
from new_mud.apps.content.startup import (
    ContentStartupError,
    ContentStartupStatus,
    SeedBundle,
)
from new_mud.mudlibs.jinyong_core.registry import build_registry_catalog

pytestmark = pytest.mark.django_db(transaction=True)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
REAL_SEED_ARTIFACT = (
    REPOSITORY_ROOT
    / "src"
    / "new_mud"
    / "mudlibs"
    / "jinyong_core"
    / "seed"
    / "content-seed-v1.json"
)


def expectation() -> SeedArtifactExpectation:
    return SeedArtifactExpectation(
        mudlib_key="jinyong.core",
        seed_bundle_id="jinyong.seed.v1",
        target_content_release="jinyong.release",
        manifest_version="1.0.0",
    )


def read_real_artifact() -> dict[str, Any]:
    return json.loads(REAL_SEED_ARTIFACT.read_text(encoding="utf-8"))


def write_artifact(path: Path, raw: dict[str, Any], *, rehash: bool = True) -> Path:
    if rehash:
        raw["artifact_hash"] = canonical_sha256(
            {key: value for key, value in raw.items() if key != "artifact_hash"}
        )
    path.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def assert_no_content_state() -> None:
    assert BlueprintHead.objects.count() == 0
    assert BlueprintRevision.objects.count() == 0
    assert ContentReleaseHead.objects.count() == 0
    assert ContentReleaseBatch.objects.count() == 0
    assert ContentReleaseItem.objects.count() == 0
    assert ResolvedRegistryDependency.objects.count() == 0


def test_real_frozen_seed_artifact_loads_and_bootstraps_atomically() -> None:
    catalog = build_registry_catalog()
    loaded = load_seed_artifact(
        REAL_SEED_ARTIFACT,
        expectation=expectation(),
        registry_catalog=catalog,
    )

    result = bootstrap_seed_artifact(
        instance_id="artifact-instance",
        expectation=expectation(),
        artifact_path=REAL_SEED_ARTIFACT,
        registry_catalog=catalog,
    )

    assert loaded.artifact_hash == (
        "073ac8cce19d4375a230de0b471e1ee2e58664645b34416de695f0b9ecdf8a24"
    )
    assert result.startup.status is ContentStartupStatus.BOOTSTRAPPED
    assert result.artifact == loaded
    assert BlueprintRevision.objects.count() == 1
    assert ContentReleaseItem.objects.count() == 1
    assert ResolvedRegistryDependency.objects.count() == 1
    release_head = ContentReleaseHead.objects.get()
    assert release_head.active_batch_id == result.startup.identity.batch_id


def test_repeated_real_artifact_bootstrap_is_idempotent() -> None:
    catalog = build_registry_catalog()
    first = bootstrap_seed_artifact(
        instance_id="artifact-instance",
        expectation=expectation(),
        artifact_path=REAL_SEED_ARTIFACT,
        registry_catalog=catalog,
    )
    second = bootstrap_seed_artifact(
        instance_id="artifact-instance",
        expectation=expectation(),
        artifact_path=REAL_SEED_ARTIFACT,
        registry_catalog=catalog,
    )

    assert second.startup.status is ContentStartupStatus.VERIFIED
    assert second.startup.identity == first.startup.identity
    assert BlueprintRevision.objects.count() == 1
    assert ContentReleaseBatch.objects.count() == 1


def test_management_command_is_a_repeatable_real_artifact_entrypoint() -> None:
    first_output = StringIO()
    second_output = StringIO()

    call_command(
        "bootstrap_content_seed", instance_id="command-instance", stdout=first_output
    )
    call_command(
        "bootstrap_content_seed", instance_id="command-instance", stdout=second_output
    )

    assert '"status": "bootstrapped"' in first_output.getvalue()
    assert '"status": "verified"' in second_output.getvalue()
    assert ContentReleaseBatch.objects.count() == 1


@pytest.mark.parametrize("failure_kind", ["missing", "invalid_json", "schema"])
def test_missing_or_corrupt_artifact_never_writes_partial_state(
    tmp_path: Path,
    failure_kind: str,
) -> None:
    artifact_path = tmp_path / "content-seed.json"
    if failure_kind == "invalid_json":
        artifact_path.write_text("{", encoding="utf-8")
    elif failure_kind == "schema":
        artifact_path.write_text("{}", encoding="utf-8")

    with pytest.raises(ContentStartupError) as captured:
        bootstrap_seed_artifact(
            instance_id="artifact-instance",
            expectation=expectation(),
            artifact_path=artifact_path,
        )

    assert captured.value.code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert_no_content_state()


def test_artifact_identity_mismatch_fails_before_database_writes() -> None:
    with pytest.raises(ContentStartupError) as captured:
        bootstrap_seed_artifact(
            instance_id="artifact-instance",
            expectation=SeedArtifactExpectation(
                mudlib_key="other.mudlib",
                seed_bundle_id="jinyong.seed.v1",
                target_content_release="jinyong.release",
                manifest_version="1.0.0",
            ),
            artifact_path=REAL_SEED_ARTIFACT,
        )

    assert captured.value.code == "CONTENT_RELEASE_SCOPE_MISMATCH"
    assert_no_content_state()


def test_artifact_and_content_hash_tampering_fail_before_writes(tmp_path: Path) -> None:
    artifact_tamper = read_real_artifact()
    artifact_tamper["blueprints"][0]["data"]["display_name"] = "篡改"
    artifact_path = write_artifact(
        tmp_path / "artifact-hash.json",
        artifact_tamper,
        rehash=False,
    )
    with pytest.raises(ContentStartupError) as artifact_error:
        bootstrap_seed_artifact(
            instance_id="artifact-instance",
            expectation=expectation(),
            artifact_path=artifact_path,
        )
    assert artifact_error.value.code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert_no_content_state()

    content_tamper = read_real_artifact()
    content_tamper["blueprints"][0]["data"]["display_name"] = "另一个篡改"
    content_path = write_artifact(tmp_path / "content-hash.json", content_tamper)
    with pytest.raises(ContentStartupError) as content_error:
        bootstrap_seed_artifact(
            instance_id="artifact-instance",
            expectation=expectation(),
            artifact_path=content_path,
        )
    assert content_error.value.code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert_no_content_state()


def test_registry_context_mismatch_fails_before_database_writes(tmp_path: Path) -> None:
    artifact_path = write_artifact(
        tmp_path / "registry-mismatch.json", read_real_artifact()
    )

    with pytest.raises(ContentStartupError) as captured:
        bootstrap_seed_artifact(
            instance_id="artifact-instance",
            expectation=expectation(),
            artifact_path=artifact_path,
            registry_catalog=RegistryCatalog.empty(),
        )

    assert captured.value.code == "BLUEPRINT_PROFILE_NOT_FOUND"
    assert_no_content_state()


def test_same_seed_id_with_different_content_is_rejected(tmp_path: Path) -> None:
    catalog = build_registry_catalog()
    bootstrap_seed_artifact(
        instance_id="artifact-instance",
        expectation=expectation(),
        artifact_path=REAL_SEED_ARTIFACT,
        registry_catalog=catalog,
    )
    changed = read_real_artifact()
    changed["blueprints"][0]["data"]["display_name"] = "改变后的内容"
    changed["content_hash"] = SeedBundle.build(
        seed_bundle_id=changed["seed_bundle_id"],
        target_content_release=changed["target_content_release"],
        manifest_version=changed["manifest_version"],
        compiler_contract_version=changed["compiler_contract_version"],
        blueprints=changed["blueprints"],
    ).content_hash
    changed_path = write_artifact(tmp_path / "changed-seed.json", changed)

    with pytest.raises(ContentStartupError) as captured:
        bootstrap_seed_artifact(
            instance_id="artifact-instance",
            expectation=expectation(),
            artifact_path=changed_path,
            registry_catalog=catalog,
        )

    assert captured.value.code == "CONTENT_RELEASE_VALIDATION_FAILED"
    assert BlueprintRevision.objects.count() == 1
    assert ContentReleaseBatch.objects.count() == 1
