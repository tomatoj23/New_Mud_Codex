from new_mud.apps.content.registry import RegistryCatalog, RegistryDefinition

from .registry import build_registry_catalog


def build_character_registry_catalog() -> RegistryCatalog:
    base_catalog = build_registry_catalog()
    character_creation_profile = RegistryDefinition.build(
        registry_kind="character_creation_profile",
        registry_key="default-v1",
        registry_version="1.0.0",
        summary="Public V1 deterministic Character creation profile",
        source_module=__name__,
        declaration={
            "display_name": "江湖新秀",
            "gender_options": ["unspecified", "female", "male", "nonbinary"],
            "pronoun_options": ["unspecified", "she", "he", "they"],
            "initial_state_schema_version": "character-initial-state/1",
            "initial_state": {
                "stats": {},
                "resources": {},
                "skill_grants": [],
                "item_grants": [],
            },
            "start_room_ref": {
                "blueprint_key": "room.xiangyang.east_gate",
                "expected_kind": "room",
            },
            "source_ref": {
                "source_snapshot": "xkx100-public-v1",
                "source_path": "room/xiangyang/east_gate",
            },
        },
        tags=("public_v1",),
    )
    return RegistryCatalog.from_definitions((*base_catalog.definitions, character_creation_profile))
