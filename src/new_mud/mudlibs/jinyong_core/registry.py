from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from new_mud.apps.content.registry import (
    RegistryCatalog,
    RegistryDefinition,
    RegistryReference,
)


def room_behavior_handler(context: object, payload: dict[str, Any]) -> dict[str, Any]:
    """Return the no-op structured result used by the initial room profile."""
    del context, payload
    return {
        "status": "ok",
        "events": [],
        "audit_entries": [],
        "state_patches": [],
    }


def _module_artifact_hash() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def build_registry_catalog() -> RegistryCatalog:
    handler = RegistryDefinition.build(
        registry_kind="handler",
        registry_key="handler.room.default",
        registry_version="1.0.0",
        summary="Default room behavior handler",
        source_module=__name__,
        declaration={
            "callable_path": f"{__name__}.room_behavior_handler",
            "input_schema": {"type": "object"},
            "result_schema_version": "1.0.0",
            "idempotency": "idempotent",
        },
        artifact_hash=_module_artifact_hash(),
    )
    profile = RegistryDefinition.build(
        registry_kind="behavior_profile",
        registry_key="profile.room.default",
        registry_version="1.0.0",
        summary="Default static room behavior profile",
        source_module=__name__,
        declaration={
            "entity_kinds": ["room"],
            "state_schema": {"type": "object"},
        },
        dependencies=(RegistryReference.from_definition(handler),),
    )
    return RegistryCatalog.from_definitions((handler, profile))
