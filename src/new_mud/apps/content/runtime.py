from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from functools import cache
from importlib import resources
from pathlib import Path

from django.db.utils import DatabaseError

from new_mud.contracts.generated import RegistryErrorsContentRelease
from new_mud.mudlibs.jinyong_core.manifest import (
    MANIFEST_VERSION,
    MUDLIB_KEY,
    SEED_BUNDLE_ID,
    TARGET_CONTENT_RELEASE,
)
from new_mud.mudlibs.jinyong_core.registry import build_registry_catalog

from .registry import RegistryCatalog, RegistryError
from .seed_artifact import (
    SeedArtifactExpectation,
    bootstrap_seed_artifact,
    load_seed_artifact,
)
from .startup import (
    ContentReleaseIdentity,
    ContentStartupError,
    ContentStartupStatus,
    verify_seed_bundle,
)


class ContentRuntimeStatus(StrEnum):
    READY = "ready"
    NOT_READY = "not_ready"


@dataclass(frozen=True, slots=True)
class ContentRuntimeSnapshot:
    status: ContentRuntimeStatus
    startup_status: ContentStartupStatus | None = None
    artifact_hash: str | None = None
    identity: ContentReleaseIdentity | None = None
    error_code: str | None = None
    error_message: str | None = None

    def as_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"status": self.status}
        if self.startup_status is not None:
            payload["startup_status"] = self.startup_status
        if self.artifact_hash is not None:
            payload["artifact_hash"] = self.artifact_hash
        if self.identity is not None:
            payload.update(
                {
                    "mudlib_key": MUDLIB_KEY,
                    "seed_bundle_id": self.identity.seed_bundle_id,
                    "target_content_release": TARGET_CONTENT_RELEASE,
                    "release_head_id": str(self.identity.release_head_id),
                    "batch_id": str(self.identity.batch_id),
                    "release_version": self.identity.release_version,
                    "release_hash": self.identity.release_hash,
                    "blueprint_count": self.identity.blueprint_count,
                }
            )
        if self.error_code is not None:
            payload["error"] = {
                "code": self.error_code,
                "message": self.error_message or "",
            }
        return payload


class ContentRuntime:
    def __init__(
        self,
        *,
        instance_id: str,
        artifact_path: str | Path | None = None,
        registry_catalog: RegistryCatalog | None = None,
    ) -> None:
        self._instance_id = instance_id
        self._artifact_path = Path(artifact_path) if artifact_path is not None else None
        self._registry_catalog = registry_catalog or build_registry_catalog()

    def _packaged_artifact(self):
        if self._artifact_path is not None:
            return self._artifact_path
        return resources.files("new_mud.mudlibs.jinyong_core").joinpath("seed/content-seed-v1.json")

    def start(self) -> ContentRuntimeSnapshot:
        packaged_artifact = self._packaged_artifact()
        expectation = SeedArtifactExpectation(
            mudlib_key=MUDLIB_KEY,
            seed_bundle_id=SEED_BUNDLE_ID,
            target_content_release=TARGET_CONTENT_RELEASE,
            manifest_version=MANIFEST_VERSION,
        )
        try:
            with resources.as_file(packaged_artifact) as artifact_path:
                result = bootstrap_seed_artifact(
                    instance_id=self._instance_id,
                    expectation=expectation,
                    artifact_path=artifact_path,
                    registry_catalog=self._registry_catalog,
                )
        except (ContentStartupError, RegistryError) as error:
            return ContentRuntimeSnapshot(
                status=ContentRuntimeStatus.NOT_READY,
                error_code=error.code,
                error_message=str(error),
            )
        except DatabaseError:
            return ContentRuntimeSnapshot(
                status=ContentRuntimeStatus.NOT_READY,
                error_code=RegistryErrorsContentRelease.CONTENT_RELEASE_VALIDATION_FAILED,
                error_message="content database is unavailable",
            )
        return ContentRuntimeSnapshot(
            status=ContentRuntimeStatus.READY,
            startup_status=result.startup.status,
            artifact_hash=result.artifact.artifact_hash,
            identity=result.startup.identity,
        )

    def readiness(self) -> ContentRuntimeSnapshot:
        packaged_artifact = self._packaged_artifact()
        expectation = SeedArtifactExpectation(
            mudlib_key=MUDLIB_KEY,
            seed_bundle_id=SEED_BUNDLE_ID,
            target_content_release=TARGET_CONTENT_RELEASE,
            manifest_version=MANIFEST_VERSION,
        )
        artifact_hash: str | None = None
        try:
            with resources.as_file(packaged_artifact) as artifact_path:
                artifact = load_seed_artifact(
                    artifact_path,
                    expectation=expectation,
                    registry_catalog=self._registry_catalog,
                )
            artifact_hash = artifact.artifact_hash
            startup = verify_seed_bundle(
                instance_id=self._instance_id,
                mudlib_key=MUDLIB_KEY,
                bundle=artifact.bundle,
                registry_catalog=self._registry_catalog,
            )
        except (ContentStartupError, RegistryError) as error:
            return ContentRuntimeSnapshot(
                status=ContentRuntimeStatus.NOT_READY,
                artifact_hash=artifact_hash,
                error_code=error.code,
                error_message=str(error),
            )
        except DatabaseError:
            return ContentRuntimeSnapshot(
                status=ContentRuntimeStatus.NOT_READY,
                artifact_hash=artifact_hash,
                error_code=RegistryErrorsContentRelease.CONTENT_RELEASE_VALIDATION_FAILED,
                error_message="content database is unavailable",
            )
        return ContentRuntimeSnapshot(
            status=ContentRuntimeStatus.READY,
            startup_status=startup.status,
            artifact_hash=artifact.artifact_hash,
            identity=startup.identity,
        )


@cache
def get_content_runtime(instance_id: str) -> ContentRuntime:
    """Return the process-scoped runtime registered during ASGI startup."""
    return ContentRuntime(instance_id=instance_id)
