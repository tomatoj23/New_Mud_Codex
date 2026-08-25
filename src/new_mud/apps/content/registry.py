from __future__ import annotations

import hashlib
import importlib
import inspect
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, cast

import rfc8785

from new_mud.contracts.generated import RegistryErrorsRegistry, RegistryKinds

_REGISTRY_KEY = re.compile(r"^[a-z][a-z0-9_.-]{2,63}$")
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(rfc8785.dumps(cast(Any, value))).hexdigest()


class RegistryError(ValueError):
    def __init__(self, *, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def validate_registry_identity(
    *, registry_kind: object, registry_key: object, registry_version: object
) -> None:
    """Validate a RegistryRef before attempting catalog resolution."""
    valid_kinds = {kind.value for kind in RegistryKinds}
    if not isinstance(registry_kind, str) or registry_kind not in valid_kinds:
        raise RegistryError(
            code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
            message=f"unknown registry kind: {registry_kind!r}",
        )
    if not isinstance(registry_key, str) or not _REGISTRY_KEY.fullmatch(registry_key):
        raise RegistryError(
            code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
            message=f"invalid registry key: {registry_key!r}",
        )
    if not isinstance(registry_version, str) or not _SEMVER.fullmatch(registry_version):
        raise RegistryError(
            code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
            message=f"invalid registry version: {registry_version!r}",
        )


@dataclass(frozen=True, slots=True)
class RegistryReference:
    registry_kind: str
    registry_key: str
    registry_version: str
    definition_hash: str | None = None

    @classmethod
    def from_definition(cls, definition: RegistryDefinition) -> RegistryReference:
        return cls(
            registry_kind=definition.registry_kind,
            registry_key=definition.registry_key,
            registry_version=definition.registry_version,
            definition_hash=definition.definition_hash,
        )

    def as_payload(self) -> dict[str, str]:
        if self.definition_hash is None:
            raise RegistryError(
                code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                message="registry reference is missing definition_hash",
            )
        return {
            "registry_kind": self.registry_kind,
            "registry_key": self.registry_key,
            "registry_version": self.registry_version,
            "definition_hash": self.definition_hash,
        }


@dataclass(frozen=True, slots=True)
class RegistryDefinition:
    registry_kind: str
    registry_key: str
    registry_version: str
    summary: str
    source_module: str
    declaration: Mapping[str, Any]
    tags: tuple[str, ...] = ()
    dependencies: tuple[RegistryReference, ...] = ()
    artifact_hash: str = ""
    definition_hash: str | None = None

    @classmethod
    def build(
        cls,
        *,
        registry_kind: str,
        registry_key: str,
        registry_version: str,
        summary: str,
        source_module: str,
        declaration: Mapping[str, Any],
        tags: Sequence[str] = (),
        dependencies: Sequence[RegistryReference] = (),
        artifact_hash: str = "",
        definition_hash: str | None = None,
    ) -> RegistryDefinition:
        return cls(
            registry_kind=registry_kind,
            registry_key=registry_key,
            registry_version=registry_version,
            summary=summary,
            source_module=source_module,
            declaration=dict(declaration),
            tags=tuple(tags),
            dependencies=tuple(dependencies),
            artifact_hash=artifact_hash,
            definition_hash=definition_hash,
        )

    def as_reference(self) -> RegistryReference:
        return RegistryReference.from_definition(self)

    def _hash_payload(
        self,
        dependencies: Sequence[RegistryReference],
    ) -> dict[str, object]:
        return {
            "registry_kind": self.registry_kind,
            "registry_key": self.registry_key,
            "registry_version": self.registry_version,
            "summary": self.summary,
            "source_module": self.source_module,
            "declaration": self.declaration,
            "tags": list(self.tags),
            "dependencies": [dependency.as_payload() for dependency in dependencies],
            "artifact_hash": self.artifact_hash,
        }


class RegistryCatalog:
    def __init__(
        self,
        *,
        active: Mapping[tuple[str, str], RegistryDefinition],
        compatibility: Mapping[tuple[str, str, str, str], RegistryDefinition],
    ) -> None:
        self._active = dict(active)
        self._compatibility = dict(compatibility)

    @classmethod
    def empty(cls) -> RegistryCatalog:
        return cls(active={}, compatibility={})

    @classmethod
    def from_definitions(
        cls,
        active_definitions: Sequence[RegistryDefinition],
        *,
        compatibility_definitions: Sequence[RegistryDefinition] = (),
    ) -> RegistryCatalog:
        raw_by_identity: dict[tuple[str, str, str], RegistryDefinition] = {}
        for definition in (*compatibility_definitions, *active_definitions):
            cls._validate_shape(definition)
            identity = (
                definition.registry_kind,
                definition.registry_key,
                definition.registry_version,
            )
            previous = raw_by_identity.get(identity)
            if previous is not None and previous != definition:
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_VERSION_CONTENT_MISMATCH,
                    message=(
                        f"registry definition differs for {identity[0]}/{identity[1]}@{identity[2]}"
                    ),
                )
            raw_by_identity[identity] = definition

        resolved: dict[tuple[str, str, str], RegistryDefinition] = {}

        def resolve(
            identity: tuple[str, str, str],
            visiting: tuple[tuple[str, str, str], ...],
        ) -> RegistryDefinition:
            cached = resolved.get(identity)
            if cached is not None:
                return cached
            if identity in visiting:
                cycle = " -> ".join(
                    f"{kind}/{key}@{version}" for kind, key, version in (*visiting, identity)
                )
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_REFERENCE_CYCLE,
                    message=f"registry reference cycle: {cycle}",
                )
            raw = raw_by_identity.get(identity)
            if raw is None:
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_MISSING_DEPENDENCY,
                    message=(
                        "registry definition is unavailable for "
                        f"{identity[0]}/{identity[1]}@{identity[2]}"
                    ),
                )
            exact_dependencies: list[RegistryReference] = []
            for dependency in raw.dependencies:
                target_identity = (
                    dependency.registry_kind,
                    dependency.registry_key,
                    dependency.registry_version,
                )
                target = resolve(target_identity, (*visiting, identity))
                if (
                    dependency.definition_hash is not None
                    and dependency.definition_hash != target.definition_hash
                ):
                    raise RegistryError(
                        code=RegistryErrorsRegistry.REGISTRY_VERSION_CONTENT_MISMATCH,
                        message=(
                            "registry dependency hash does not match "
                            f"{target_identity[0]}/{target_identity[1]}@{target_identity[2]}"
                        ),
                    )
                exact_dependencies.append(target.as_reference())
            definition_hash = canonical_sha256(raw._hash_payload(exact_dependencies))
            if raw.definition_hash is not None and raw.definition_hash != definition_hash:
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_VERSION_CONTENT_MISMATCH,
                    message=(
                        "registry definition hash does not match declaration for "
                        f"{identity[0]}/{identity[1]}@{identity[2]}"
                    ),
                )
            normalized = RegistryDefinition(
                registry_kind=raw.registry_kind,
                registry_key=raw.registry_key,
                registry_version=raw.registry_version,
                summary=raw.summary,
                source_module=raw.source_module,
                declaration=dict(raw.declaration),
                tags=tuple(raw.tags),
                dependencies=tuple(exact_dependencies),
                artifact_hash=raw.artifact_hash,
                definition_hash=definition_hash,
            )
            resolved[identity] = normalized
            return normalized

        for identity in raw_by_identity:
            resolve(identity, ())

        active: dict[tuple[str, str], RegistryDefinition] = {}
        for definition in active_definitions:
            active_identity = (definition.registry_kind, definition.registry_key)
            if active_identity in active:
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_DUPLICATE_KEY,
                    message=(
                        f"duplicate active registry key: {active_identity[0]}/{active_identity[1]}"
                    ),
                )
            active[active_identity] = resolved[
                (definition.registry_kind, definition.registry_key, definition.registry_version)
            ]

        compatibility = {
            (
                definition.registry_kind,
                definition.registry_key,
                definition.registry_version,
                definition.definition_hash or "",
            ): definition
            for definition in resolved.values()
        }
        return cls(active=active, compatibility=compatibility)

    @staticmethod
    def _validate_shape(definition: RegistryDefinition) -> None:
        validate_registry_identity(
            registry_kind=definition.registry_kind,
            registry_key=definition.registry_key,
            registry_version=definition.registry_version,
        )
        if (
            not isinstance(definition.summary, str)
            or not definition.summary
            or not isinstance(definition.source_module, str)
            or not definition.source_module
        ):
            raise RegistryError(
                code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                message="registry summary and source_module are required",
            )
        if not isinstance(definition.declaration, Mapping):
            raise RegistryError(
                code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                message="registry declaration must be an object",
            )
        if not all(isinstance(tag, str) and tag for tag in definition.tags):
            raise RegistryError(
                code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                message="registry tags must be non-empty strings",
            )
        for reference in definition.dependencies:
            if not isinstance(reference, RegistryReference):
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                    message="registry dependencies must be RegistryReference values",
                )
            if (
                not isinstance(reference.registry_kind, str)
                or not isinstance(reference.registry_key, str)
                or not isinstance(reference.registry_version, str)
                or not reference.registry_kind
                or not _REGISTRY_KEY.fullmatch(reference.registry_key)
                or not _SEMVER.fullmatch(reference.registry_version)
            ):
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                    message="registry dependency identity is invalid",
                )
            if reference.definition_hash is not None and not re.fullmatch(
                r"[0-9a-f]{64}", reference.definition_hash
            ):
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                    message="registry dependency definition_hash must be sha256",
                )

        required_fields: dict[str, tuple[str, ...]] = {
            "handler": (
                "callable_path",
                "input_schema",
                "result_schema_version",
                "idempotency",
            ),
            "rule": ("handler_key", "input_schema", "output_schema", "determinism"),
            "permission_policy": ("rule_keys", "combine", "default_decision"),
            "hook_set": ("hook_schema_version", "hooks"),
            "action_provider": ("source_scopes", "action_keys", "priority"),
            "render_policy": ("handler_key", "input_schema", "output_schema"),
            "blueprint_seed_provider": (
                "seed_bundle_id",
                "target_content_release",
                "content_hash",
                "loader_handler_key",
            ),
            "action": (
                "source_scopes",
                "argument_schema",
                "requires_inventory_version",
                "permission_policy_key",
                "handler_key",
                "help",
            ),
            "behavior_profile": ("entity_kinds",),
            "effect_type": (
                "payload_schema",
                "stacking_policy",
                "tick_policy",
                "persistence",
                "reference_rule_key",
                "recovery_policy",
                "handler_key_apply",
                "handler_key_expire",
            ),
            "job_type": (
                "payload_schema",
                "handler_key",
                "retry_policy",
                "overlap_policy",
                "concurrency_key_template",
                "max_runtime_s",
            ),
            "world_process_type": (
                "payload_schema",
                "handler_key",
                "singleton_scope",
                "recovery_policy",
            ),
            "startup_plan": (
                "target_kind",
                "type_key",
                "type_version",
                "payload",
                "enabled",
                "idempotency_key",
            ),
        }
        for field in required_fields.get(definition.registry_kind, ()):
            if field not in definition.declaration:
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                    message=f"{definition.registry_kind} declaration requires {field}",
                )
        if definition.registry_kind == "handler":
            callable_path = definition.declaration.get("callable_path")
            if not isinstance(callable_path, str) or not callable_path:
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_HANDLER_MISSING,
                    message="handler callable_path is required",
                )
            module_name, separator, attribute_name = callable_path.rpartition(".")
            if not separator:
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_HANDLER_MISSING,
                    message=f"handler callable path is invalid: {callable_path}",
                )
            try:
                module = importlib.import_module(module_name)
                handler = getattr(module, attribute_name)
                signature = inspect.signature(handler)
            except (ImportError, AttributeError, TypeError, ValueError) as error:
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_HANDLER_MISSING,
                    message=f"handler callable is unavailable: {callable_path}",
                ) from error
            positional = [
                parameter
                for parameter in signature.parameters.values()
                if parameter.kind
                in (
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                )
                and parameter.default is inspect.Parameter.empty
            ]
            if not callable(handler) or len(positional) != 2:
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                    message="handler callable must accept ctx and payload",
                )
            if not re.fullmatch(r"[0-9a-f]{64}", definition.artifact_hash):
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                    message="handler artifact_hash must be a required sha256",
                )
            if not isinstance(definition.declaration.get("input_schema"), Mapping):
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                    message="handler input_schema must be an object",
                )
            if definition.declaration.get("idempotency") not in {
                "idempotent",
                "requires_idempotency_key",
                "non_idempotent",
            }:
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                    message="handler idempotency is invalid",
                )
        if definition.registry_kind == "rule" and (
            not isinstance(definition.declaration.get("handler_key"), str)
            or not isinstance(definition.declaration.get("input_schema"), Mapping)
            or not isinstance(definition.declaration.get("output_schema"), Mapping)
            or definition.declaration.get("determinism") not in {"deterministic", "seeded"}
        ):
            raise RegistryError(
                code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                message="rule declaration has invalid typed fields",
            )
        if definition.registry_kind == "behavior_profile":
            entity_kinds = definition.declaration.get("entity_kinds")
            if not isinstance(entity_kinds, list) or not all(
                isinstance(kind, str) and kind for kind in entity_kinds
            ):
                raise RegistryError(
                    code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                    message="behavior_profile entity_kinds must be a string array",
                )

    @property
    def definitions(self) -> tuple[RegistryDefinition, ...]:
        return tuple(
            sorted(
                self._compatibility.values(),
                key=lambda definition: (
                    definition.registry_kind,
                    definition.registry_key,
                    definition.registry_version,
                ),
            )
        )

    def resolve_active(
        self,
        registry_kind: str,
        registry_key: str,
        registry_version: str | None = None,
    ) -> RegistryDefinition:
        definition = self._active.get((registry_kind, registry_key))
        if definition is None:
            raise RegistryError(
                code=RegistryErrorsRegistry.REGISTRY_REFERENCE_NOT_FOUND,
                message=f"active registry reference is unavailable: {registry_kind}/{registry_key}",
            )
        if registry_version is not None and definition.registry_version != registry_version:
            raise RegistryError(
                code=RegistryErrorsRegistry.REGISTRY_VERSION_CONTENT_MISMATCH,
                message=(
                    f"active registry version mismatch for {registry_kind}/{registry_key}: "
                    f"expected {registry_version}, active {definition.registry_version}"
                ),
            )
        return definition

    def resolve_exact(self, reference: RegistryReference) -> RegistryDefinition:
        if reference.definition_hash is None:
            raise RegistryError(
                code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                message="exact registry reference requires definition_hash",
            )
        validate_registry_identity(
            registry_kind=reference.registry_kind,
            registry_key=reference.registry_key,
            registry_version=reference.registry_version,
        )
        if not re.fullmatch(r"[0-9a-f]{64}", reference.definition_hash):
            raise RegistryError(
                code=RegistryErrorsRegistry.REGISTRY_SCHEMA_INVALID,
                message="exact registry reference definition_hash must be sha256",
            )
        definition = self._compatibility.get(
            (
                reference.registry_kind,
                reference.registry_key,
                reference.registry_version,
                reference.definition_hash,
            )
        )
        if definition is not None:
            return definition
        same_version = [
            candidate
            for candidate in self._compatibility.values()
            if (
                candidate.registry_kind == reference.registry_kind
                and candidate.registry_key == reference.registry_key
                and candidate.registry_version == reference.registry_version
            )
        ]
        if same_version:
            raise RegistryError(
                code=RegistryErrorsRegistry.REGISTRY_VERSION_CONTENT_MISMATCH,
                message=(
                    "registry definition hash mismatch for "
                    f"{reference.registry_kind}/{reference.registry_key}@{reference.registry_version}"
                ),
            )
        raise RegistryError(
            code=RegistryErrorsRegistry.REGISTRY_COMPAT_DEFINITION_MISSING,
            message=(
                "exact registry definition is unavailable for "
                f"{reference.registry_kind}/{reference.registry_key}@{reference.registry_version}"
            ),
        )
