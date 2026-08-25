from __future__ import annotations

import copy
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from django.db import transaction

from new_mud.contracts.generated import (
    RegistryErrorsBlueprint,
    RegistryErrorsContentRelease,
)

from .models import (
    BlueprintHead,
    BlueprintRevision,
    ContentReleaseBatch,
    ContentReleaseHead,
    ContentReleaseItem,
    ResolvedBlueprintDependency,
    ResolvedRegistryDependency,
)
from .registry import (
    RegistryCatalog,
    RegistryError,
    RegistryReference,
    canonical_sha256,
    validate_registry_identity,
)

COMPILER_CONTRACT_VERSION = "blueprint-compiler/1"


class ContentStartupStatus(StrEnum):
    BOOTSTRAPPED = "bootstrapped"
    VERIFIED = "verified"


class ContentStartupError(RuntimeError):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class SeedBundle:
    seed_bundle_id: str
    target_content_release: str
    manifest_version: str
    compiler_contract_version: str
    blueprints: tuple[dict[str, Any], ...]
    content_hash: str

    def calculated_content_hash(self) -> str:
        return canonical_sha256(
            {
                "seed_bundle_id": self.seed_bundle_id,
                "target_content_release": self.target_content_release,
                "manifest_version": self.manifest_version,
                "compiler_contract_version": self.compiler_contract_version,
                "blueprints": self.blueprints,
            }
        )

    @classmethod
    def build(
        cls,
        *,
        seed_bundle_id: str,
        target_content_release: str,
        manifest_version: str,
        compiler_contract_version: str,
        blueprints: Sequence[Mapping[str, Any]],
    ) -> SeedBundle:
        normalized = tuple(
            sorted(
                (copy.deepcopy(dict(blueprint)) for blueprint in blueprints),
                key=lambda blueprint: str(blueprint.get("blueprint_key", "")),
            )
        )
        bundle = cls(
            seed_bundle_id=seed_bundle_id,
            target_content_release=target_content_release,
            manifest_version=manifest_version,
            compiler_contract_version=compiler_contract_version,
            blueprints=normalized,
            content_hash="",
        )
        return cls(**{**bundle.__dict__, "content_hash": bundle.calculated_content_hash()})


@dataclass(frozen=True)
class ContentReleaseIdentity:
    release_head_id: uuid.UUID
    batch_id: uuid.UUID
    release_version: int
    seed_bundle_id: str
    release_hash: str
    blueprint_count: int


@dataclass(frozen=True)
class ContentStartupResult:
    status: ContentStartupStatus
    identity: ContentReleaseIdentity


@dataclass(frozen=True)
class _PreparedBlueprintDependency:
    dependency_path: str
    dependency_kind: str
    ordinal: int
    target_head_id: uuid.UUID
    target_revision_id: uuid.UUID
    target_blueprint_key: str
    expected_kind: str

    def as_compiled_payload(self, *, source_revision_id: uuid.UUID) -> dict[str, object]:
        return {
            "source_revision_id": str(source_revision_id),
            "dependency_path": self.dependency_path,
            "dependency_kind": self.dependency_kind,
            "ordinal": self.ordinal,
            "target_head_id": str(self.target_head_id),
            "target_revision_id": str(self.target_revision_id),
            "target_blueprint_key": self.target_blueprint_key,
            "expected_kind": self.expected_kind,
        }

    def as_hash_payload(self) -> dict[str, object]:
        payload = self.as_compiled_payload(source_revision_id=uuid.UUID(int=0))
        payload.pop("source_revision_id")
        return payload


@dataclass(frozen=True)
class _PreparedRegistryDependency:
    dependency_path: str
    ordinal: int
    reference: RegistryReference

    def as_compiled_payload(self, *, source_revision_id: uuid.UUID) -> dict[str, object]:
        return {
            "source_revision_id": str(source_revision_id),
            "dependency_path": self.dependency_path,
            "ordinal": self.ordinal,
            **self.reference.as_payload(),
        }

    def as_hash_payload(self) -> dict[str, object]:
        payload = self.as_compiled_payload(source_revision_id=uuid.UUID(int=0))
        payload.pop("source_revision_id")
        return payload


@dataclass(frozen=True)
class _PreparedBlueprint:
    head_id: uuid.UUID
    revision_id: uuid.UUID
    raw_payload: dict[str, Any]
    compiled_payload: dict[str, Any]
    content_hash: str
    compiled_hash: str
    resolved_dependency_hash: str
    blueprint_dependencies: tuple[_PreparedBlueprintDependency, ...]
    registry_dependencies: tuple[_PreparedRegistryDependency, ...]

    @property
    def blueprint_key(self) -> str:
        return str(self.raw_payload["blueprint_key"])


def _deep_merge(base: object, override: object) -> object:
    if isinstance(base, dict) and isinstance(override, dict):
        merged = copy.deepcopy(base)
        for key, value in override.items():
            merged[key] = _deep_merge(merged[key], value) if key in merged else copy.deepcopy(value)
        return merged
    return copy.deepcopy(override)


def _prepare_registry_dependencies(
    raw_payload: Mapping[str, Any],
    *,
    inherited: Sequence[_PreparedRegistryDependency],
    registry_catalog: RegistryCatalog,
) -> tuple[_PreparedRegistryDependency, ...]:
    references: list[tuple[str, int, str, str, str | None]] = [
        (
            dependency.dependency_path,
            dependency.ordinal,
            dependency.reference.registry_kind,
            dependency.reference.registry_key,
            dependency.reference.registry_version,
        )
        for dependency in inherited
    ]
    if "behavior_profile_keys" in raw_payload:
        behavior_profile_keys = raw_payload.get("behavior_profile_keys")
        if not isinstance(behavior_profile_keys, list):
            raise ContentStartupError(
                code=RegistryErrorsBlueprint.BLUEPRINT_SCHEMA_INVALID,
                message="behavior_profile_keys must be an array",
            )
        references = [
            reference
            for reference in references
            if not reference[0].startswith("/behavior_profile_keys/")
        ]
        for ordinal, registry_key in enumerate(behavior_profile_keys):
            if not isinstance(registry_key, str) or not registry_key:
                raise ContentStartupError(
                    code=RegistryErrorsBlueprint.BLUEPRINT_SCHEMA_INVALID,
                    message="behavior_profile_keys entries must be non-empty strings",
                )
            references.append(
                (
                    f"/behavior_profile_keys/{ordinal}",
                    ordinal,
                    "behavior_profile",
                    registry_key,
                    None,
                )
            )
    explicit_references = raw_payload.get("registry_refs", [])
    if not isinstance(explicit_references, list):
        raise ContentStartupError(
            code=RegistryErrorsBlueprint.BLUEPRINT_SCHEMA_INVALID,
            message="registry_refs must be an array",
        )
    for ordinal, raw_reference in enumerate(explicit_references):
        if not isinstance(raw_reference, Mapping):
            raise ContentStartupError(
                code=RegistryErrorsBlueprint.BLUEPRINT_SCHEMA_INVALID,
                message="registry_refs entries must be objects",
            )
        path = raw_reference.get("path")
        registry_kind = raw_reference.get("registry_kind")
        registry_key = raw_reference.get("registry_key")
        if not all(
            isinstance(value, str) and value for value in (path, registry_kind, registry_key)
        ):
            raise ContentStartupError(
                code=RegistryErrorsBlueprint.BLUEPRINT_SCHEMA_INVALID,
                message="registry_refs require path, registry_kind and registry_key",
            )
        registry_version = raw_reference.get("registry_version")
        if registry_version is not None and not isinstance(registry_version, str):
            raise ContentStartupError(
                code=RegistryErrorsBlueprint.BLUEPRINT_SCHEMA_INVALID,
                message="registry_refs registry_version must be a string",
            )
        if registry_version is not None:
            try:
                validate_registry_identity(
                    registry_kind=registry_kind,
                    registry_key=registry_key,
                    registry_version=registry_version,
                )
            except RegistryError as error:
                raise ContentStartupError(code=error.code, message=str(error)) from error
        references.append(
            (
                str(path),
                ordinal,
                str(registry_kind),
                str(registry_key),
                registry_version if isinstance(registry_version, str) else None,
            )
        )

    references_by_path = {
        (path, ordinal): (path, ordinal, registry_kind, registry_key, registry_version)
        for path, ordinal, registry_kind, registry_key, registry_version in references
    }
    prepared: list[_PreparedRegistryDependency] = []
    for path, ordinal, registry_kind, registry_key, registry_version in references_by_path.values():
        try:
            validate_registry_identity(
                registry_kind=registry_kind,
                registry_key=registry_key,
                registry_version=registry_version or "0.0.0",
            )
        except RegistryError as error:
            raise ContentStartupError(code=error.code, message=str(error)) from error
        try:
            definition = registry_catalog.resolve_active(
                registry_kind,
                registry_key,
                registry_version,
            )
        except RegistryError as error:
            code = (
                RegistryErrorsBlueprint.BLUEPRINT_PROFILE_NOT_FOUND
                if (
                    registry_kind == "behavior_profile"
                    and error.code == "REGISTRY_REFERENCE_NOT_FOUND"
                )
                else (
                    RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_VERSION_UNAVAILABLE
                    if error.code == "REGISTRY_VERSION_CONTENT_MISMATCH"
                    else RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_REFERENCE_NOT_FOUND
                )
            )
            raise ContentStartupError(code=code, message=str(error)) from error
        prepared.append(
            _PreparedRegistryDependency(
                dependency_path=path,
                ordinal=ordinal,
                reference=definition.as_reference(),
            )
        )
    return tuple(
        sorted(
            prepared,
            key=lambda dependency: (
                dependency.reference.registry_kind,
                dependency.reference.registry_key,
                dependency.reference.registry_version,
                dependency.dependency_path,
                dependency.ordinal,
            ),
        )
    )


def _prepare_blueprints(
    bundle: SeedBundle,
    *,
    registry_catalog: RegistryCatalog,
) -> tuple[_PreparedBlueprint, ...]:
    identities: dict[str, tuple[dict[str, Any], uuid.UUID, uuid.UUID]] = {}
    for raw_payload in bundle.blueprints:
        blueprint_key = str(raw_payload.get("blueprint_key", ""))
        if not blueprint_key or blueprint_key in identities:
            raise ContentStartupError(
                code=RegistryErrorsBlueprint.BLUEPRINT_DUPLICATE_KEY,
                message="seed bundle blueprint keys must be non-empty and unique",
            )
        identities[blueprint_key] = (copy.deepcopy(raw_payload), uuid.uuid4(), uuid.uuid4())

    prepared_by_key: dict[str, _PreparedBlueprint] = {}

    def prepare(blueprint_key: str, visiting: tuple[str, ...]) -> _PreparedBlueprint:
        if blueprint_key in prepared_by_key:
            return prepared_by_key[blueprint_key]
        if blueprint_key in visiting:
            cycle = " -> ".join((*visiting, blueprint_key))
            raise ContentStartupError(
                code=RegistryErrorsBlueprint.BLUEPRINT_INHERITANCE_CYCLE,
                message=f"blueprint inheritance cycle: {cycle}",
            )

        raw_payload, head_id, revision_id = identities[blueprint_key]
        kind = str(raw_payload.get("kind", ""))
        resolved_data: object = {}
        source_lineage: list[dict[str, str]] = []
        dependencies: list[_PreparedBlueprintDependency] = []
        inherited_registry_dependencies: dict[
            tuple[str, int], _PreparedRegistryDependency
        ] = {}
        for ordinal, parent_key_value in enumerate(raw_payload.get("parent_keys", [])):
            parent_key = str(parent_key_value)
            parent_identity = identities.get(parent_key)
            if parent_identity is None:
                raise ContentStartupError(
                    code=RegistryErrorsBlueprint.BLUEPRINT_PARENT_NOT_FOUND,
                    message=f"blueprint parent {parent_key!r} is unavailable",
                )
            parent = prepare(parent_key, (*visiting, blueprint_key))
            parent_kind = str(parent.raw_payload.get("kind", ""))
            if parent_kind != kind:
                raise ContentStartupError(
                    code=RegistryErrorsBlueprint.BLUEPRINT_KIND_MISMATCH,
                    message=f"blueprint parent {parent_key!r} has kind {parent_kind!r}",
                )
            resolved_data = _deep_merge(
                resolved_data,
                parent.compiled_payload["resolved_data"],
            )
            source_lineage.extend(copy.deepcopy(parent.compiled_payload["source_lineage"]))
            inherited_registry_dependencies.update(
                {
                    (dependency.dependency_path, dependency.ordinal): dependency
                    for dependency in parent.registry_dependencies
                }
            )
            dependencies.append(
                _PreparedBlueprintDependency(
                    dependency_path=f"/parent_keys/{ordinal}",
                    dependency_kind=ResolvedBlueprintDependency.DependencyKind.PARENT,
                    ordinal=ordinal,
                    target_head_id=parent.head_id,
                    target_revision_id=parent.revision_id,
                    target_blueprint_key=parent.blueprint_key,
                    expected_kind=kind,
                )
            )
        resolved_data = _deep_merge(resolved_data, raw_payload.get("data", {}))
        registry_dependencies = _prepare_registry_dependencies(
            raw_payload,
            inherited=tuple(inherited_registry_dependencies.values()),
            registry_catalog=registry_catalog,
        )
        source_lineage.append(
            {
                "blueprint_key": blueprint_key,
                "head_id": str(head_id),
                "revision_id": str(revision_id),
            }
        )
        compiled_dependencies = [
            dependency.as_compiled_payload(source_revision_id=revision_id)
            for dependency in dependencies
        ]
        dependency_payload = {
            "blueprint_dependencies": [dependency.as_hash_payload() for dependency in dependencies],
            "registry_dependencies": [
                dependency.as_hash_payload() for dependency in registry_dependencies
            ],
        }
        resolved_dependency_hash = canonical_sha256(dependency_payload)
        compiled_payload = {
            "blueprint_key": blueprint_key,
            "kind": kind,
            "version": raw_payload.get("version"),
            "compiler_contract_version": bundle.compiler_contract_version,
            "resolved_data": resolved_data,
            "tags": copy.deepcopy(raw_payload.get("tags", [])),
            "resolved_behavior_profiles": [
                dependency.reference.as_payload()
                for dependency in registry_dependencies
                if dependency.reference.registry_kind == "behavior_profile"
            ],
            "spawn_policy": copy.deepcopy(raw_payload.get("spawn_policy", {})),
            "source_lineage": source_lineage,
            "resolved_dependencies": compiled_dependencies,
            "resolved_registry_dependencies": [
                dependency.as_compiled_payload(source_revision_id=revision_id)
                for dependency in registry_dependencies
            ],
            "resolved_dependency_hash": resolved_dependency_hash,
        }
        compiled_hash = canonical_sha256(
            {
                "compiled_payload": compiled_payload,
                **dependency_payload,
            }
        )
        prepared = _PreparedBlueprint(
            head_id=head_id,
            revision_id=revision_id,
            raw_payload=copy.deepcopy(raw_payload),
            compiled_payload=compiled_payload,
            content_hash=canonical_sha256(raw_payload),
            compiled_hash=compiled_hash,
            resolved_dependency_hash=resolved_dependency_hash,
            blueprint_dependencies=tuple(dependencies),
            registry_dependencies=registry_dependencies,
        )
        prepared_by_key[blueprint_key] = prepared
        return prepared

    for blueprint_key in identities:
        prepare(blueprint_key, ())
    return tuple(prepared_by_key[key] for key in sorted(prepared_by_key))


def seed_registry_context(
    bundle: SeedBundle,
    *,
    registry_catalog: RegistryCatalog,
) -> tuple[dict[str, str], ...]:
    """Return the exact active Registry context selected by a seed bundle."""
    exact_references = {
        (
            dependency.reference.registry_kind,
            dependency.reference.registry_key,
            dependency.reference.registry_version,
            dependency.reference.definition_hash or "",
        )
        for blueprint in _prepare_blueprints(bundle, registry_catalog=registry_catalog)
        for dependency in blueprint.registry_dependencies
    }
    return tuple(
        {
            "registry_kind": registry_kind,
            "registry_key": registry_key,
            "registry_version": registry_version,
            "definition_hash": definition_hash,
        }
        for registry_kind, registry_key, registry_version, definition_hash in sorted(
            exact_references
        )
    )


def _release_hash(prepared: Sequence[_PreparedBlueprint]) -> str:
    items = [
        {
            "blueprint_head_id": str(item.head_id),
            "blueprint_key": item.blueprint_key,
            "published_revision_id": str(item.revision_id),
            "content_hash": item.content_hash,
            "compiled_hash": item.compiled_hash,
        }
        for item in sorted(prepared, key=lambda value: value.blueprint_key.encode("utf-8"))
    ]
    return canonical_sha256(items)


def _stored_release_hash(items: Sequence[ContentReleaseItem]) -> str:
    hash_items = [
        {
            "blueprint_head_id": str(item.blueprint_head_id),
            "blueprint_key": item.blueprint_key,
            "published_revision_id": str(item.published_revision_id),
            "content_hash": item.published_revision.content_hash,
            "compiled_hash": item.published_revision.compiled_hash,
        }
        for item in sorted(items, key=lambda value: value.blueprint_key.encode("utf-8"))
    ]
    return canonical_sha256(hash_items)


def _verify_published_revision(
    revision: BlueprintRevision,
    *,
    registry_catalog: RegistryCatalog,
    active_registry: bool,
) -> None:
    """Recompute immutable revision material before exposing it at startup."""
    if not isinstance(revision.raw_payload, Mapping) or not isinstance(
        revision.compiled_payload, Mapping
    ):
        raise ContentStartupError(
            code=RegistryErrorsBlueprint.BLUEPRINT_SCHEMA_INVALID,
            message=f"published revision {revision.revision_id} has invalid payload",
        )
    blueprint_dependencies = sorted(
        revision.blueprint_dependencies.all(),
        key=lambda dependency: (
            dependency.dependency_kind,
            dependency.dependency_path,
            dependency.ordinal,
        ),
    )
    registry_dependencies = sorted(
        revision.registry_dependencies.all(),
        key=lambda dependency: (
            dependency.registry_kind,
            dependency.registry_key,
            dependency.registry_version,
            dependency.dependency_path,
            dependency.ordinal,
        ),
    )
    dependency_payload = {
        "blueprint_dependencies": [
            {
                "dependency_path": dependency.dependency_path,
                "dependency_kind": dependency.dependency_kind,
                "ordinal": dependency.ordinal,
                "target_head_id": str(dependency.target_head_id),
                "target_revision_id": str(dependency.target_revision_id),
                "target_blueprint_key": dependency.target_blueprint_key,
                "expected_kind": dependency.expected_kind,
            }
            for dependency in blueprint_dependencies
        ],
        "registry_dependencies": [
            {
                "dependency_path": dependency.dependency_path,
                "ordinal": dependency.ordinal,
                "registry_kind": dependency.registry_kind,
                "registry_key": dependency.registry_key,
                "registry_version": dependency.registry_version,
                "definition_hash": dependency.definition_hash,
            }
            for dependency in registry_dependencies
        ],
    }
    compiled_registry_payload = revision.compiled_payload.get(
        "resolved_registry_dependencies"
    )
    expected_registry_payload = [
        {
            "source_revision_id": str(revision.revision_id),
            **dependency,
        }
        for dependency in dependency_payload["registry_dependencies"]
    ]
    expected_blueprint_payload = [
        {
            "source_revision_id": str(revision.revision_id),
            **dependency,
        }
        for dependency in dependency_payload["blueprint_dependencies"]
    ]
    def registry_sort_key(value: object) -> tuple[str, int]:
        if not isinstance(value, Mapping) or not isinstance(
            value.get("dependency_path"), str
        ):
            raise ContentStartupError(
                code=RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH,
                message=f"compiled registry dependencies are malformed for {revision.revision_id}",
            )
        ordinal_value = value.get("ordinal")
        try:
            ordinal = int(ordinal_value) if ordinal_value is not None else -1
        except (TypeError, ValueError) as error:
            raise ContentStartupError(
                code=RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH,
                message=f"compiled registry dependencies are malformed for {revision.revision_id}",
            ) from error
        return str(value["dependency_path"]), ordinal

    if not isinstance(compiled_registry_payload, list) or sorted(
        compiled_registry_payload, key=registry_sort_key
    ) != sorted(expected_registry_payload, key=registry_sort_key):
        raise ContentStartupError(
            code=RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH,
            message=f"compiled registry dependencies mismatch revision {revision.revision_id}",
        )
    compiled_blueprint_payload = revision.compiled_payload.get("resolved_dependencies")
    if (
        not isinstance(compiled_blueprint_payload, list)
        or compiled_blueprint_payload != expected_blueprint_payload
    ):
        raise ContentStartupError(
            code=RegistryErrorsBlueprint.BLUEPRINT_REFERENCE_NOT_FOUND,
            message=f"compiled blueprint dependencies mismatch revision {revision.revision_id}",
        )
    if canonical_sha256(revision.raw_payload) != revision.content_hash:
        raise ContentStartupError(
            code=RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH,
            message=f"content hash mismatch for revision {revision.revision_id}",
        )
    if canonical_sha256(dependency_payload) != revision.resolved_dependency_hash:
        raise ContentStartupError(
            code=RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH,
            message=f"dependency hash mismatch for revision {revision.revision_id}",
        )
    if (
        revision.compiled_payload.get("resolved_dependency_hash")
        != revision.resolved_dependency_hash
    ):
        raise ContentStartupError(
            code=RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH,
            message=f"compiled dependency hash mismatch for revision {revision.revision_id}",
        )
    expected_compiled_hash = canonical_sha256(
        {"compiled_payload": revision.compiled_payload, **dependency_payload}
    )
    if expected_compiled_hash != revision.compiled_hash:
        raise ContentStartupError(
            code=RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH,
            message=f"compiled hash mismatch for revision {revision.revision_id}",
        )
    for dependency in registry_dependencies:
        reference = RegistryReference(
            registry_kind=dependency.registry_kind,
            registry_key=dependency.registry_key,
            registry_version=dependency.registry_version,
            definition_hash=dependency.definition_hash,
        )
        try:
            if active_registry:
                active_definition = registry_catalog.resolve_active(
                    dependency.registry_kind,
                    dependency.registry_key,
                )
                if (
                    active_definition.registry_version != dependency.registry_version
                    or active_definition.definition_hash != dependency.definition_hash
                ):
                    raise RegistryError(
                        code=RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_VERSION_UNAVAILABLE,
                        message="active registry definition differs from revision dependency",
                    )
            else:
                registry_catalog.resolve_exact(reference)
        except RegistryError as error:
            raise ContentStartupError(code=error.code, message=str(error)) from error


def _verify_existing_release(
    *,
    instance_id: str,
    mudlib_key: str,
    bundle: SeedBundle,
    registry_catalog: RegistryCatalog,
) -> ContentStartupResult | None:
    release_head = (
        ContentReleaseHead.objects.select_related("active_batch")
        .filter(
            instance_id=instance_id,
            mudlib_key=mudlib_key,
            target_content_release=bundle.target_content_release,
        )
        .first()
    )
    namespace_has_heads = BlueprintHead.objects.filter(
        instance_id=instance_id,
        mudlib_key=mudlib_key,
    ).exists()
    if release_head is None:
        if namespace_has_heads:
            raise ContentStartupError(
                code=RegistryErrorsContentRelease.CONTENT_RELEASE_SCOPE_MISMATCH,
                message="content namespace is partially initialized",
            )
        return None
    if release_head.active_batch is None:
        raise ContentStartupError(
            code=RegistryErrorsContentRelease.CONTENT_RELEASE_VALIDATION_FAILED,
            message="content release has no active batch",
        )

    seed_batch = (
        ContentReleaseBatch.objects.filter(
            release_head=release_head,
            source_seed_bundle_id=bundle.seed_bundle_id,
        )
        .order_by("release_version")
        .first()
    )
    if seed_batch is None:
        raise ContentStartupError(
            code=RegistryErrorsContentRelease.CONTENT_RELEASE_SCOPE_MISMATCH,
            message="configured seed bundle does not match initialized content",
        )
    seed_items = list(
        ContentReleaseItem.objects.filter(batch=seed_batch)
        .select_related("published_revision")
        .prefetch_related("published_revision__blueprint_dependencies")
        .prefetch_related("published_revision__registry_dependencies")
        .order_by("blueprint_key")
    )
    seed_hash_input = {
        "seed_bundle_id": bundle.seed_bundle_id,
        "target_content_release": bundle.target_content_release,
        "manifest_version": seed_batch.manifest_version,
        "compiler_contract_version": bundle.compiler_contract_version,
        "blueprints": tuple(item.published_revision.raw_payload for item in seed_items),
    }
    stored_seed_hash = canonical_sha256(seed_hash_input)
    if stored_seed_hash != bundle.content_hash:
        raise ContentStartupError(
            code=RegistryErrorsContentRelease.CONTENT_RELEASE_VALIDATION_FAILED,
            message="seed bundle id is bound to different content",
        )

    for item in seed_items:
        _verify_published_revision(
            item.published_revision,
            registry_catalog=registry_catalog,
            active_registry=False,
        )

    historical_revisions = BlueprintRevision.objects.filter(
        head__instance_id=instance_id,
        head__mudlib_key=mudlib_key,
        revision_kind=BlueprintRevision.RevisionKind.PUBLISHED,
    ).prefetch_related("blueprint_dependencies", "registry_dependencies")
    for revision in historical_revisions:
        _verify_published_revision(
            revision,
            registry_catalog=registry_catalog,
            active_registry=False,
        )

    active_batch = release_head.active_batch
    active_items = list(
        ContentReleaseItem.objects.filter(batch=active_batch)
        .select_related("published_revision")
        .prefetch_related("published_revision__blueprint_dependencies")
        .prefetch_related("published_revision__registry_dependencies")
        .order_by("blueprint_key")
    )
    for item in active_items:
        _verify_published_revision(
            item.published_revision,
            registry_catalog=registry_catalog,
            active_registry=True,
        )
    stored_release_hash = _stored_release_hash(active_items)
    if stored_release_hash != active_batch.release_hash:
        raise ContentStartupError(
            code=RegistryErrorsContentRelease.CONTENT_RELEASE_VALIDATION_FAILED,
            message="active content release hash does not match its items",
        )
    return ContentStartupResult(
        status=ContentStartupStatus.VERIFIED,
        identity=ContentReleaseIdentity(
            release_head_id=release_head.release_head_id,
            batch_id=active_batch.batch_id,
            release_version=active_batch.release_version,
            seed_bundle_id=bundle.seed_bundle_id,
            release_hash=active_batch.release_hash,
            blueprint_count=len(active_items),
        ),
    )


def bootstrap_seed_bundle(
    *,
    instance_id: str,
    mudlib_key: str,
    bundle: SeedBundle,
    registry_catalog: RegistryCatalog | None = None,
) -> ContentStartupResult:
    catalog = registry_catalog or RegistryCatalog.empty()
    if bundle.compiler_contract_version != COMPILER_CONTRACT_VERSION:
        raise ContentStartupError(
            code=RegistryErrorsContentRelease.CONTENT_RELEASE_VALIDATION_FAILED,
            message=(f"seed bundle compiler contract does not match {COMPILER_CONTRACT_VERSION}"),
        )
    if bundle.calculated_content_hash() != bundle.content_hash:
        raise ContentStartupError(
            code=RegistryErrorsContentRelease.CONTENT_RELEASE_VALIDATION_FAILED,
            message="seed bundle content hash does not match its normalized payload",
        )
    with transaction.atomic():
        existing = _verify_existing_release(
            instance_id=instance_id,
            mudlib_key=mudlib_key,
            bundle=bundle,
            registry_catalog=catalog,
        )
        if existing is not None:
            return existing

        prepared = _prepare_blueprints(bundle, registry_catalog=catalog)
        release_head_id = uuid.uuid4()
        batch_id = uuid.uuid4()
        release_hash = _release_hash(prepared)
        release_head = ContentReleaseHead.objects.create(
            release_head_id=release_head_id,
            instance_id=instance_id,
            mudlib_key=mudlib_key,
            target_content_release=bundle.target_content_release,
        )
        heads: dict[uuid.UUID, BlueprintHead] = {}
        for item in prepared:
            heads[item.head_id] = BlueprintHead.objects.create(
                head_id=item.head_id,
                instance_id=instance_id,
                mudlib_key=mudlib_key,
                blueprint_key=item.blueprint_key,
            )
        batch = ContentReleaseBatch.objects.create(
            batch_id=batch_id,
            release_head=release_head,
            release_version=1,
            manifest_version=bundle.manifest_version,
            source_seed_bundle_id=bundle.seed_bundle_id,
            release_hash=release_hash,
            created_by="system:seed-bootstrap",
        )
        for item in prepared:
            head = heads[item.head_id]
            revision = BlueprintRevision.objects.create(
                revision_id=item.revision_id,
                head=head,
                blueprint_key=item.blueprint_key,
                revision_kind=BlueprintRevision.RevisionKind.PUBLISHED,
                source_seed_bundle_id=bundle.seed_bundle_id,
                raw_payload=item.raw_payload,
                compiled_payload=item.compiled_payload,
                content_hash=item.content_hash,
                compiled_hash=item.compiled_hash,
                resolved_dependency_hash=item.resolved_dependency_hash,
                compiler_contract_version=bundle.compiler_contract_version,
                publication_reason=BlueprintRevision.PublicationReason.SEED_BOOTSTRAP,
                created_in_batch=batch,
                created_by="system:seed-bootstrap",
            )
            ResolvedBlueprintDependency.objects.bulk_create(
                [
                    ResolvedBlueprintDependency(
                        source_revision=revision,
                        dependency_path=dependency.dependency_path,
                        dependency_kind=dependency.dependency_kind,
                        ordinal=dependency.ordinal,
                        target_head=heads[dependency.target_head_id],
                        target_revision_id=dependency.target_revision_id,
                        target_blueprint_key=dependency.target_blueprint_key,
                        expected_kind=dependency.expected_kind,
                    )
                    for dependency in item.blueprint_dependencies
                ]
            )
            ResolvedRegistryDependency.objects.bulk_create(
                [
                    ResolvedRegistryDependency(
                        source_revision=revision,
                        dependency_path=dependency.dependency_path,
                        ordinal=dependency.ordinal,
                        registry_kind=dependency.reference.registry_kind,
                        registry_key=dependency.reference.registry_key,
                        registry_version=dependency.reference.registry_version,
                        definition_hash=dependency.reference.definition_hash or "",
                    )
                    for dependency in item.registry_dependencies
                ]
            )
            ContentReleaseItem.objects.create(
                batch=batch,
                release_head=release_head,
                blueprint_head=head,
                blueprint_key=item.blueprint_key,
                published_revision=revision,
            )
            BlueprintHead.objects.filter(pk=head.pk).update(published_revision=revision)
        ContentReleaseHead.objects.filter(pk=release_head.pk).update(
            active_batch=batch,
            release_version=1,
        )

    return ContentStartupResult(
        status=ContentStartupStatus.BOOTSTRAPPED,
        identity=ContentReleaseIdentity(
            release_head_id=release_head_id,
            batch_id=batch_id,
            release_version=1,
            seed_bundle_id=bundle.seed_bundle_id,
            release_hash=release_hash,
            blueprint_count=len(prepared),
        ),
    )
