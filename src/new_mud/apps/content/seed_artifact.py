from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from django.db import DatabaseError
from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError, ValidationError

from new_mud.contracts.generated import (
    RegistryErrorsBlueprint,
    RegistryErrorsContentRelease,
)

from .models import ContentStartupFailure
from .registry import RegistryCatalog, canonical_sha256
from .startup import (
    COMPILER_CONTRACT_VERSION,
    ContentStartupError,
    ContentStartupResult,
    SeedBundle,
    bootstrap_seed_bundle,
    seed_registry_context,
)

logger = logging.getLogger(__name__)

_SAFE_FAILURE_MESSAGES: dict[str, str] = {
    RegistryErrorsContentRelease.CONTENT_RELEASE_CONFLICT: "content release conflict",
    RegistryErrorsContentRelease.CONTENT_RELEASE_SCOPE_MISMATCH: ("content release scope mismatch"),
    RegistryErrorsContentRelease.CONTENT_RELEASE_VALIDATION_FAILED: (
        "content release validation failed"
    ),
    RegistryErrorsBlueprint.BLUEPRINT_PARENT_NOT_FOUND: ("blueprint dependency validation failed"),
    RegistryErrorsBlueprint.BLUEPRINT_REFERENCE_KIND_MISMATCH: (
        "blueprint dependency validation failed"
    ),
    RegistryErrorsBlueprint.BLUEPRINT_REFERENCE_NOT_FOUND: (
        "blueprint dependency validation failed"
    ),
    RegistryErrorsBlueprint.BLUEPRINT_PROFILE_NOT_FOUND: ("registry dependency validation failed"),
    RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH: (
        "registry dependency validation failed"
    ),
    RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_REFERENCE_NOT_FOUND: (
        "registry dependency validation failed"
    ),
    RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_VERSION_UNAVAILABLE: (
        "registry dependency validation failed"
    ),
}

_SHA256_PATTERN = "^[0-9a-f]{64}$"
_REGISTRY_KEY_PATTERN = "^[a-z][a-z0-9_.-]{2,63}$"
_SEMVER_PATTERN = "^(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)$"

SEED_ARTIFACT_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$id": "https://new-mud.local/content-seed-artifact.schema.json",
    "type": "object",
    "additionalProperties": False,
    "required": [
        "contract_version",
        "artifact_type",
        "mudlib_key",
        "seed_bundle_id",
        "target_content_release",
        "manifest_version",
        "compiler_contract_version",
        "canonicalization",
        "hash_algorithm",
        "blueprints",
        "registry_context",
        "registry_context_hash",
        "content_hash",
        "artifact_hash",
    ],
    "properties": {
        "contract_version": {"const": "1"},
        "artifact_type": {"const": "content_seed_bundle"},
        "mudlib_key": {"type": "string", "pattern": _REGISTRY_KEY_PATTERN},
        "seed_bundle_id": {"type": "string", "pattern": _REGISTRY_KEY_PATTERN},
        "target_content_release": {"type": "string", "pattern": _REGISTRY_KEY_PATTERN},
        "manifest_version": {"type": "string", "pattern": _SEMVER_PATTERN},
        "compiler_contract_version": {"const": COMPILER_CONTRACT_VERSION},
        "canonicalization": {"const": "RFC8785-JCS/UTF-8"},
        "hash_algorithm": {"const": "sha256"},
        "blueprints": {
            "type": "array",
            "minItems": 1,
            "items": {"$ref": "#/$defs/blueprint"},
        },
        "registry_context": {
            "type": "array",
            "uniqueItems": True,
            "items": {"$ref": "#/$defs/registry_reference"},
        },
        "registry_context_hash": {"type": "string", "pattern": _SHA256_PATTERN},
        "content_hash": {"type": "string", "pattern": _SHA256_PATTERN},
        "artifact_hash": {"type": "string", "pattern": _SHA256_PATTERN},
    },
    "$defs": {
        "blueprint": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "blueprint_key",
                "kind",
                "version",
                "parent_keys",
                "source_type",
                "tags",
                "behavior_profile_keys",
                "spawn_policy",
                "data",
            ],
            "properties": {
                "blueprint_key": {
                    "type": "string",
                    "minLength": 3,
                    "maxLength": 128,
                    "pattern": "^[a-z][a-z0-9_-]*(?:\\.[a-z][a-z0-9_-]*)+$",
                },
                "kind": {"type": "string", "minLength": 1, "maxLength": 64},
                "version": {"type": "string", "pattern": _SEMVER_PATTERN},
                "parent_keys": {
                    "type": "array",
                    "uniqueItems": True,
                    "items": {"type": "string", "minLength": 3, "maxLength": 128},
                },
                "source_type": {"enum": ["file", "db", "converter"]},
                "tags": {
                    "type": "array",
                    "uniqueItems": True,
                    "items": {"type": "string", "minLength": 1},
                },
                "behavior_profile_keys": {
                    "type": "array",
                    "uniqueItems": True,
                    "items": {"type": "string", "pattern": _REGISTRY_KEY_PATTERN},
                },
                "registry_refs": {
                    "type": "array",
                    "items": {"$ref": "#/$defs/registry_ref"},
                },
                "spawn_policy": {"type": "object"},
                "data": {"type": "object"},
            },
        },
        "registry_ref": {
            "type": "object",
            "additionalProperties": False,
            "required": ["path", "registry_kind", "registry_key"],
            "properties": {
                "path": {"type": "string", "pattern": "^/"},
                "registry_kind": {"type": "string", "minLength": 1},
                "registry_key": {"type": "string", "pattern": _REGISTRY_KEY_PATTERN},
                "registry_version": {"type": "string", "pattern": _SEMVER_PATTERN},
            },
        },
        "registry_reference": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "registry_kind",
                "registry_key",
                "registry_version",
                "definition_hash",
            ],
            "properties": {
                "registry_kind": {"type": "string", "minLength": 1},
                "registry_key": {"type": "string", "pattern": _REGISTRY_KEY_PATTERN},
                "registry_version": {"type": "string", "pattern": _SEMVER_PATTERN},
                "definition_hash": {"type": "string", "pattern": _SHA256_PATTERN},
            },
        },
    },
}


@dataclass(frozen=True, slots=True)
class SeedArtifactExpectation:
    mudlib_key: str
    seed_bundle_id: str
    target_content_release: str
    manifest_version: str


@dataclass(frozen=True, slots=True)
class LoadedSeedArtifact:
    path: Path
    artifact_hash: str
    registry_context_hash: str
    bundle: SeedBundle


@dataclass(frozen=True, slots=True)
class SeedArtifactBootstrapResult:
    artifact: LoadedSeedArtifact
    startup: ContentStartupResult


def _validation_error(message: str) -> ContentStartupError:
    return ContentStartupError(
        code=RegistryErrorsContentRelease.CONTENT_RELEASE_VALIDATION_FAILED,
        message=message,
    )


def _scope_error(message: str) -> ContentStartupError:
    return ContentStartupError(
        code=RegistryErrorsContentRelease.CONTENT_RELEASE_SCOPE_MISMATCH,
        message=message,
    )


def _read_artifact(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise _validation_error(f"seed artifact is unavailable: {path}")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise _validation_error(f"seed artifact is unreadable: {path}") from error
    if not isinstance(raw, dict):
        raise _validation_error("seed artifact root must be an object")
    try:
        Draft202012Validator.check_schema(SEED_ARTIFACT_SCHEMA)
        Draft202012Validator(SEED_ARTIFACT_SCHEMA).validate(raw)
    except (SchemaError, ValidationError) as error:
        location = "/" + "/".join(str(part) for part in error.absolute_path)
        message = f"seed artifact schema validation failed at {location}: {error.message}"
        raise _validation_error(message) from error
    return cast(dict[str, Any], raw)


def _artifact_hash(raw: Mapping[str, Any]) -> str:
    return canonical_sha256({key: value for key, value in raw.items() if key != "artifact_hash"})


def load_seed_artifact(
    path: str | Path,
    *,
    expectation: SeedArtifactExpectation,
    registry_catalog: RegistryCatalog,
) -> LoadedSeedArtifact:
    artifact_path = Path(path).resolve(strict=False)
    raw = _read_artifact(artifact_path)
    configured_identity = {
        "mudlib_key": expectation.mudlib_key,
        "seed_bundle_id": expectation.seed_bundle_id,
        "target_content_release": expectation.target_content_release,
        "manifest_version": expectation.manifest_version,
    }
    for field, expected in configured_identity.items():
        if raw[field] != expected:
            raise _scope_error(
                f"seed artifact {field} mismatch: expected {expected!r}, found {raw[field]!r}"
            )
    if raw["compiler_contract_version"] != COMPILER_CONTRACT_VERSION:
        raise _validation_error("seed artifact compiler contract is unsupported")
    if _artifact_hash(raw) != raw["artifact_hash"]:
        raise _validation_error("seed artifact hash does not match its canonical payload")

    bundle = SeedBundle.build(
        seed_bundle_id=raw["seed_bundle_id"],
        target_content_release=raw["target_content_release"],
        manifest_version=raw["manifest_version"],
        compiler_contract_version=raw["compiler_contract_version"],
        blueprints=raw["blueprints"],
    )
    if bundle.content_hash != raw["content_hash"]:
        raise _validation_error("seed artifact content hash does not match its blueprints")

    declared_context = tuple(raw["registry_context"])
    if canonical_sha256(declared_context) != raw["registry_context_hash"]:
        raise _validation_error("seed artifact Registry context hash is invalid")
    resolved_context = seed_registry_context(bundle, registry_catalog=registry_catalog)
    if declared_context != resolved_context:
        raise ContentStartupError(
            code=RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH,
            message="seed artifact Registry context differs from active definitions",
        )
    return LoadedSeedArtifact(
        path=artifact_path,
        artifact_hash=raw["artifact_hash"],
        registry_context_hash=raw["registry_context_hash"],
        bundle=bundle,
    )


def _record_startup_failure(
    *,
    instance_id: str,
    expectation: SeedArtifactExpectation,
    artifact_hash: str | None,
    error: ContentStartupError,
) -> None:
    try:
        ContentStartupFailure.objects.create(
            instance_id=instance_id,
            mudlib_key=expectation.mudlib_key,
            target_content_release=expectation.target_content_release,
            seed_bundle_id=expectation.seed_bundle_id,
            artifact_hash=artifact_hash,
            error_code=error.code,
            error_message=_SAFE_FAILURE_MESSAGES.get(error.code, "content startup failed"),
        )
    except DatabaseError:
        logger.error(
            "content startup failure audit could not be persisted",
            extra={
                "instance_id": instance_id,
                "mudlib_key": expectation.mudlib_key,
                "seed_bundle_id": expectation.seed_bundle_id,
                "error_code": error.code,
            },
        )


def bootstrap_seed_artifact(
    *,
    instance_id: str,
    expectation: SeedArtifactExpectation,
    artifact_path: str | Path,
    registry_catalog: RegistryCatalog | None = None,
) -> SeedArtifactBootstrapResult:
    catalog = registry_catalog or RegistryCatalog.empty()
    artifact: LoadedSeedArtifact | None = None
    try:
        artifact = load_seed_artifact(
            artifact_path,
            expectation=expectation,
            registry_catalog=catalog,
        )
        startup = bootstrap_seed_bundle(
            instance_id=instance_id,
            mudlib_key=expectation.mudlib_key,
            bundle=artifact.bundle,
            registry_catalog=catalog,
        )
    except ContentStartupError as error:
        _record_startup_failure(
            instance_id=instance_id,
            expectation=expectation,
            artifact_hash=artifact.artifact_hash if artifact is not None else None,
            error=error,
        )
        logger.error(
            "content seed artifact bootstrap failed",
            extra={
                "instance_id": instance_id,
                "mudlib_key": expectation.mudlib_key,
                "seed_bundle_id": expectation.seed_bundle_id,
                "error_code": error.code,
            },
        )
        raise
    except DatabaseError as error:
        startup_error = ContentStartupError(
            code=RegistryErrorsContentRelease.CONTENT_RELEASE_VALIDATION_FAILED,
            message="content bootstrap transaction failed",
        )
        _record_startup_failure(
            instance_id=instance_id,
            expectation=expectation,
            artifact_hash=artifact.artifact_hash if artifact is not None else None,
            error=startup_error,
        )
        logger.error(
            "content seed artifact bootstrap transaction failed",
            extra={
                "instance_id": instance_id,
                "mudlib_key": expectation.mudlib_key,
                "seed_bundle_id": expectation.seed_bundle_id,
                "error_code": startup_error.code,
            },
        )
        raise startup_error from error
    logger.info(
        "content seed artifact bootstrap completed",
        extra={
            "instance_id": instance_id,
            "mudlib_key": expectation.mudlib_key,
            "seed_bundle_id": artifact.bundle.seed_bundle_id,
            "artifact_hash": artifact.artifact_hash,
            "batch_id": str(startup.identity.batch_id),
            "startup_status": startup.status,
        },
    )
    return SeedArtifactBootstrapResult(artifact=artifact, startup=startup)
