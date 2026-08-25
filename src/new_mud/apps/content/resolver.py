from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ObjectDoesNotExist

from new_mud.contracts.generated import RegistryErrorsBlueprint

from .models import BlueprintRevision, ContentReleaseItem
from .registry import RegistryCatalog, RegistryError, RegistryReference


class ContentResolutionError(LookupError):
    def __init__(
        self,
        message: str,
        *,
        code: str = RegistryErrorsBlueprint.BLUEPRINT_SCHEMA_INVALID,
    ) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ResolvedBlueprintDependencyView:
    path: str
    kind: str
    ordinal: int
    target_revision_id: uuid.UUID
    target_blueprint_key: str
    expected_kind: str


@dataclass(frozen=True)
class ResolvedRegistryDependencyView:
    path: str
    ordinal: int
    registry_kind: str
    registry_key: str
    registry_version: str
    definition_hash: str


@dataclass(frozen=True)
class ResolvedBlueprint:
    blueprint_key: str
    revision_id: uuid.UUID
    batch_id: uuid.UUID | None
    compiled_payload: dict[str, Any]
    blueprint_dependencies: tuple[ResolvedBlueprintDependencyView, ...]
    registry_dependencies: tuple[ResolvedRegistryDependencyView, ...]


def _resolved_blueprint(
    revision: BlueprintRevision,
    *,
    batch_id: uuid.UUID | None,
    registry_catalog: RegistryCatalog,
    active_registry: bool = False,
) -> ResolvedBlueprint:
    if revision.compiled_payload is None:
        raise ContentResolutionError(
            f"published blueprint {revision.blueprint_key!r} has no compiled payload"
        )
    dependencies = tuple(
        ResolvedBlueprintDependencyView(
            path=dependency.dependency_path,
            kind=dependency.dependency_kind,
            ordinal=dependency.ordinal,
            target_revision_id=dependency.target_revision_id,
            target_blueprint_key=dependency.target_blueprint_key,
            expected_kind=dependency.expected_kind,
        )
        for dependency in revision.blueprint_dependencies.order_by(
            "dependency_kind",
            "dependency_path",
            "ordinal",
        )
    )
    registry_dependencies = tuple(
        ResolvedRegistryDependencyView(
            path=dependency.dependency_path,
            ordinal=dependency.ordinal,
            registry_kind=dependency.registry_kind,
            registry_key=dependency.registry_key,
            registry_version=dependency.registry_version,
            definition_hash=dependency.definition_hash,
        )
        for dependency in revision.registry_dependencies.order_by(
            "registry_kind",
            "registry_key",
            "registry_version",
            "dependency_path",
            "ordinal",
        )
    )
    persisted_registry_payload = [
        {
            "source_revision_id": str(revision.revision_id),
            "dependency_path": dependency.path,
            "ordinal": dependency.ordinal,
            "registry_kind": dependency.registry_kind,
            "registry_key": dependency.registry_key,
            "registry_version": dependency.registry_version,
            "definition_hash": dependency.definition_hash,
        }
        for dependency in registry_dependencies
    ]
    compiled_registry_payload = revision.compiled_payload.get("resolved_registry_dependencies")
    if not isinstance(compiled_registry_payload, list):
        raise ContentResolutionError(
            f"published blueprint {revision.blueprint_key!r} has invalid registry dependencies",
            code=RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH,
        )

    def sort_key(dependency: object) -> tuple[str, int]:
        if not isinstance(dependency, dict):
            raise ContentResolutionError(
                f"published blueprint {revision.blueprint_key!r} has invalid registry dependencies",
                code=RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH,
            )
        try:
            ordinal = int(dependency.get("ordinal", 0))
        except (TypeError, ValueError) as error:
            raise ContentResolutionError(
                f"published blueprint {revision.blueprint_key!r} has invalid registry dependencies",
                code=RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH,
            ) from error
        return str(dependency.get("dependency_path", "")), ordinal

    if sorted(compiled_registry_payload, key=sort_key) != sorted(
        persisted_registry_payload,
        key=sort_key,
    ):
        raise ContentResolutionError(
            f"published blueprint {revision.blueprint_key!r} has mismatched registry dependencies",
            code=RegistryErrorsBlueprint.BLUEPRINT_REGISTRY_DEFINITION_HASH_MISMATCH,
        )
    for dependency in registry_dependencies:
        try:
            reference = RegistryReference(
                registry_kind=dependency.registry_kind,
                registry_key=dependency.registry_key,
                registry_version=dependency.registry_version,
                definition_hash=dependency.definition_hash,
            )
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
                        message=(
                            "active registry definition differs from the published "
                            f"dependency {dependency.registry_kind}/{dependency.registry_key}"
                        ),
                    )
            else:
                registry_catalog.resolve_exact(reference)
        except RegistryError as error:
            raise ContentResolutionError(str(error), code=error.code) from error
    return ResolvedBlueprint(
        blueprint_key=revision.blueprint_key,
        revision_id=revision.revision_id,
        batch_id=batch_id,
        compiled_payload=revision.compiled_payload,
        blueprint_dependencies=dependencies,
        registry_dependencies=registry_dependencies,
    )


class ContentResolver:
    @staticmethod
    def resolve_active(
        *,
        instance_id: str,
        mudlib_key: str,
        target_content_release: str,
        blueprint_key: str,
        registry_catalog: RegistryCatalog | None = None,
    ) -> ResolvedBlueprint:
        catalog = registry_catalog or RegistryCatalog.empty()
        try:
            item = (
                ContentReleaseItem.objects.select_related(
                    "batch",
                    "published_revision",
                )
                .prefetch_related(
                    "published_revision__blueprint_dependencies",
                    "published_revision__registry_dependencies",
                )
                .get(
                    batch__active_for_release_heads__instance_id=instance_id,
                    batch__active_for_release_heads__mudlib_key=mudlib_key,
                    batch__active_for_release_heads__target_content_release=target_content_release,
                    batch__active_for_release_heads__active_batch_id__isnull=False,
                    blueprint_key=blueprint_key,
                )
            )
        except ObjectDoesNotExist as error:
            raise ContentResolutionError(
                f"active blueprint {blueprint_key!r} is unavailable"
            ) from error
        return _resolved_blueprint(
            item.published_revision,
            batch_id=item.batch_id,
            registry_catalog=catalog,
            active_registry=True,
        )

    @staticmethod
    def resolve_pinned(
        *,
        revision_id: uuid.UUID,
        registry_catalog: RegistryCatalog | None = None,
    ) -> ResolvedBlueprint:
        catalog = registry_catalog or RegistryCatalog.empty()
        try:
            revision = BlueprintRevision.objects.prefetch_related(
                "blueprint_dependencies",
                "registry_dependencies",
            ).get(
                revision_id=revision_id,
                revision_kind=BlueprintRevision.RevisionKind.PUBLISHED,
                compiled_payload__isnull=False,
            )
        except ObjectDoesNotExist as error:
            raise ContentResolutionError(
                f"pinned blueprint revision {revision_id} is unavailable"
            ) from error
        return _resolved_blueprint(
            revision,
            batch_id=revision.created_in_batch_id,
            registry_catalog=catalog,
        )
