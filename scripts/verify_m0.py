from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as metadata
import json
import re
import sys
import tomllib
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import IntEnum, StrEnum
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote

import rfc8785
from jsonschema import FormatChecker
from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.utils import canonicalize_name

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ROOT = REPOSITORY_ROOT / "contracts" / "v1"
GENERATED_CATALOGS = REPOSITORY_ROOT / "src" / "new_mud" / "contracts" / "generated.py"
TRACEABILITY_DOCUMENT = REPOSITORY_ROOT / "docs" / "new_engine" / "17_REQUIREMENTS_TRACEABILITY.md"

EXPECTED_INSTANCE_FILES = {
    "artifacts/source_snapshot.json",
    "artifacts/xkx100-skill-combat-v1.manifest.json",
    "artifacts/xkx100-village-alley-v1.manifest.json",
    "artifacts/xkx100-village-skill-combat-v1.bundle.json",
    "catalogs/acceptance-states.json",
    "catalogs/content-states.json",
    "catalogs/protocol-errors.json",
    "catalogs/protocol-states.json",
    "catalogs/protocol.json",
    "catalogs/refresh-errors.json",
    "catalogs/registry-errors.json",
    "catalogs/registry.json",
    "catalogs/session-states.json",
    "profiles/browser-matrix.json",
    "profiles/capacity-profile.json",
    "profiles/recovery-budget.json",
}

SCHEMA_BY_ARTIFACT_TYPE = {
    "acceptance_bundle": "acceptance-bundle.schema.json",
    "browser_matrix": "browser-matrix.schema.json",
    "capacity_profile": "capacity-profile.schema.json",
    "error_code_catalog": "machine-catalog.schema.json",
    "fixture_manifest": "fixture-manifest.schema.json",
    "protocol_catalog": "machine-catalog.schema.json",
    "recovery_budget": "recovery-budget.schema.json",
    "registry_catalog": "registry-catalog.schema.json",
    "source_snapshot": "source-snapshot.schema.json",
    "state_catalog": "machine-catalog.schema.json",
}

EXPECTED_CATALOG_KEYS = {
    "acceptance-states.json": {"alignment_statuses", "non_passing_review_statuses"},
    "content-states.json": {
        "blueprint_dependency_kinds",
        "blueprint_revision_kinds",
        "publication_reasons",
    },
    "protocol-errors.json": {"action_domain", "authentication_presence", "protocol"},
    "protocol-states.json": {"activation_states", "delivery_statuses"},
    "protocol.json": {
        "action_sources",
        "application_close_codes",
        "client_envelope_fields",
        "event_types",
        "protocol_versions",
        "request_types",
        "server_envelope_fields",
        "terminal_types",
    },
    "refresh-errors.json": {"refresh"},
    "registry-errors.json": {
        "blueprint",
        "condition_effect",
        "content_release",
        "registry",
    },
    "session-states.json": {
        "auth_session_states",
        "connection_session_states",
        "credential_states",
        "delivery_classes",
        "outbox_states",
        "presence_runtime_states",
        "presence_snapshot_states",
        "refresh_family_states",
        "terminal_kinds",
    },
}

EXPECTED_REGISTRY_KINDS = {
    "action",
    "action_provider",
    "behavior_profile",
    "blueprint_seed_provider",
    "effect_type",
    "handler",
    "hook_set",
    "job_type",
    "permission_policy",
    "render_policy",
    "rule",
    "startup_plan",
    "world_process_type",
}

WORLD_ROOTS = {
    "d/village/alley1.c",
    "d/village/alley2.c",
    "d/village/npc/dipi.c",
    "d/village/npc/obj/cloth.c",
    "d/village/npc/punk.c",
}

SKILL_COMBAT_ROOTS = {
    "cmds/skill/enable.c",
    "cmds/skill/exert.c",
    "cmds/skill/perform.c",
    "cmds/skill/prepare.c",
    "feature/attack.c",
    "feature/skill.c",
    "kungfu/skill/bahuang-gong.c",
    "kungfu/skill/bahuang-gong/heal.c",
    "kungfu/skill/bahuang-gong/powerup.c",
    "kungfu/skill/bahuang-gong/qudu.c",
    "kungfu/skill/baihua-cuoquan.c",
    "kungfu/skill/baihua-cuoquan/cuo.c",
    "kungfu/skill/benlei-shou.c",
    "kungfu/skill/benlei-shou/yunkai.c",
}

REQUIREMENT_STATUSES = {"blocked", "implemented", "retired", "specified", "verified"}
MARKDOWN_LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
TRACEABILITY_ROW_RE = re.compile(r"^\|\s*`([A-Z]+-[0-9]{3})`\s*\|\s*`([a-z_]+)`\s*\|")
LOCK_ENTRY_RE = re.compile(r"^([A-Za-z0-9_.-]+)==([A-Za-z0-9][A-Za-z0-9_.+!-]*)$")


@dataclass
class VerificationResult:
    checks: int = 0
    errors: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)

    def check(self, condition: bool, message: str) -> None:
        self.checks += 1
        if not condition:
            self.errors.append(message)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def block(self, message: str) -> None:
        if message not in self.blockers:
            self.blockers.append(message)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot load JSON {path}: {error}") from error


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def utf8_sorted(values: Iterable[str]) -> list[str]:
    return sorted(values, key=lambda value: value.encode("utf-8"))


def active_documents(repository_root: Path) -> list[Path]:
    documents = [
        repository_root / "README.md",
        repository_root / "requirements_v5.md",
        repository_root / "UBIQUITOUS_LANGUAGE.md",
    ]
    documents.extend(sorted((repository_root / "docs").rglob("*.md")))
    return documents


def validate_documents(repository_root: Path, result: VerificationResult) -> None:
    for path in active_documents(repository_root):
        relative = path.relative_to(repository_root).as_posix()
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8")
        except (OSError, UnicodeDecodeError) as error:
            result.error(f"{relative}: not readable UTF-8: {error}")
            continue
        text = text.removeprefix("\ufeff")
        h1_count = sum(line.startswith("# ") for line in text.splitlines())
        result.check(h1_count == 1, f"{relative}: expected exactly one H1, found {h1_count}")
        for target in MARKDOWN_LINK_RE.findall(text):
            target = target.strip().split(maxsplit=1)[0].strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            local_part = unquote(target.split("#", 1)[0])
            resolved = (path.parent / local_part).resolve()
            try:
                resolved.relative_to(repository_root.resolve())
            except ValueError:
                result.error(f"{relative}: link escapes repository: {target}")
                continue
            result.check(resolved.exists(), f"{relative}: broken local link: {target}")


def load_schemas(contract_root: Path, result: VerificationResult) -> dict[str, Any]:
    schemas: dict[str, Any] = {}
    schema_ids: set[str] = set()
    for path in sorted((contract_root / "schemas").glob("*.json")):
        try:
            schema = load_json(path)
            validator_for(schema).check_schema(schema)
        except (SchemaError, ValueError) as error:
            result.error(f"schemas/{path.name}: invalid schema: {error}")
            continue
        schema_id = schema.get("$id")
        result.check(isinstance(schema_id, str), f"schemas/{path.name}: missing $id")
        if isinstance(schema_id, str):
            result.check(
                schema_id not in schema_ids, f"schemas/{path.name}: duplicate $id {schema_id}"
            )
            schema_ids.add(schema_id)
        schemas[path.name] = schema
    result.check(
        set(SCHEMA_BY_ARTIFACT_TYPE.values()).issubset(schemas),
        "schema directory does not cover every executable artifact type",
    )
    return schemas


def validate_instances(
    contract_root: Path,
    schemas: dict[str, Any],
    result: VerificationResult,
) -> dict[str, Any]:
    instances: dict[str, Any] = {}
    actual_files = {
        path.relative_to(contract_root).as_posix()
        for directory in ("artifacts", "catalogs", "profiles")
        for path in (contract_root / directory).glob("*.json")
    }
    result.check(actual_files == EXPECTED_INSTANCE_FILES, "contract instance file set has drifted")
    for relative in sorted(actual_files):
        path = contract_root / relative
        try:
            instance = load_json(path)
        except ValueError as error:
            result.error(str(error))
            continue
        artifact_type = instance.get("artifact_type")
        schema_name = SCHEMA_BY_ARTIFACT_TYPE.get(artifact_type)
        if schema_name is None:
            result.error(f"{relative}: unknown artifact_type {artifact_type!r}")
            continue
        schema = schemas.get(schema_name)
        if schema is None:
            result.error(f"{relative}: missing schema {schema_name}")
            continue
        validator_class = validator_for(schema)
        validator = validator_class(schema, format_checker=FormatChecker())
        for validation_error in sorted(
            validator.iter_errors(instance), key=lambda item: list(item.path)
        ):
            location = "/".join(str(part) for part in validation_error.absolute_path) or "<root>"
            result.error(f"{relative}:{location}: {validation_error.message}")
        instances[relative] = instance
    return instances


def parse_traceability(repository_root: Path, result: VerificationResult) -> dict[str, str]:
    path = repository_root / "docs" / "new_engine" / "17_REQUIREMENTS_TRACEABILITY.md"
    text = path.read_text(encoding="utf-8")
    requirements: dict[str, str] = {}
    for line in text.splitlines():
        match = TRACEABILITY_ROW_RE.match(line)
        if not match:
            continue
        requirement_id, status = match.groups()
        result.check(status in REQUIREMENT_STATUSES, f"traceability: invalid status {status}")
        result.check(
            requirement_id not in requirements, f"traceability: duplicate {requirement_id}"
        )
        requirements[requirement_id] = status
    result.check(bool(requirements), "traceability: no requirement rows found")
    return requirements


def validate_requirement_ids(
    instances: dict[str, Any],
    requirements: dict[str, str],
    result: VerificationResult,
) -> None:
    for relative, instance in instances.items():
        for requirement_id in instance.get("requirement_ids", []):
            result.check(
                requirement_id in requirements,
                f"{relative}: unknown requirement id {requirement_id}",
            )


def validate_dependency_lock(repository_root: Path, result: VerificationResult) -> None:
    pyproject = tomllib.loads((repository_root / "pyproject.toml").read_text(encoding="utf-8"))
    lock_path = repository_root / "requirements.lock"
    locked_versions: dict[str, str] = {}
    for line_number, raw_line in enumerate(
        lock_path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = LOCK_ENTRY_RE.fullmatch(line)
        if match is None:
            result.error(f"requirements.lock:{line_number}: expected name==version")
            continue
        raw_name, version = match.groups()
        name = canonicalize_name(raw_name)
        result.check(name not in locked_versions, f"requirements.lock: duplicate package {name}")
        locked_versions[name] = version

    python_version = ".".join(str(part) for part in sys.version_info[:3])
    python_requirement = SpecifierSet(pyproject["project"]["requires-python"])
    result.check(
        python_requirement.contains(python_version),
        f"Python {python_version} does not satisfy project requires-python",
    )

    declared = [
        *pyproject["build-system"]["requires"],
        *pyproject["project"]["dependencies"],
        *pyproject["project"]["optional-dependencies"]["dev"],
    ]
    for declaration in declared:
        requirement = Requirement(declaration)
        declared_name = canonicalize_name(requirement.name)
        locked_version = locked_versions.get(declared_name)
        result.check(
            locked_version is not None,
            f"requirements.lock: missing direct dependency {declared_name}",
        )
        if locked_version is not None:
            result.check(
                requirement.specifier.contains(locked_version),
                f"requirements.lock: {declared_name}=={locked_version} "
                f"violates {requirement.specifier}",
            )

    for locked_name, locked_version in locked_versions.items():
        try:
            installed_version = metadata.version(locked_name)
        except metadata.PackageNotFoundError:
            result.error(f"environment: locked package {locked_name} is not installed")
            continue
        result.check(
            installed_version == locked_version,
            f"environment: {locked_name}=={installed_version}, lock requires {locked_version}",
        )


def catalog_values(instance: dict[str, Any]) -> list[str | int]:
    return [value for values in instance["values"].values() for value in values]


def validate_catalogs(
    repository_root: Path,
    instances: dict[str, Any],
    result: VerificationResult,
) -> None:
    for filename, expected_keys in EXPECTED_CATALOG_KEYS.items():
        relative = f"catalogs/{filename}"
        catalog = instances.get(relative)
        if catalog is None:
            continue
        result.check(
            set(catalog["values"]) == expected_keys, f"{relative}: catalog groups have drifted"
        )
        source_path = repository_root / catalog["source_document"]
        result.check(source_path.is_file(), f"{relative}: source document does not exist")
        if not source_path.is_file():
            continue
        source_text = source_path.read_text(encoding="utf-8")
        for value in catalog_values(catalog):
            result.check(
                str(value) in source_text, f"{relative}: {value!r} absent from source document"
            )

    registry = instances.get("catalogs/registry.json")
    if registry is None:
        return
    actual_kinds = {entry["registry_kind"] for entry in registry["entries"]}
    result.check(
        actual_kinds == EXPECTED_REGISTRY_KINDS, "catalogs/registry.json: kinds have drifted"
    )
    source_path = repository_root / registry["source_document"]
    source_text = source_path.read_text(encoding="utf-8")
    for entry in registry["entries"]:
        for value in (entry["registry_kind"], entry["definition_type"], *entry["required_fields"]):
            result.check(
                str(value) in source_text,
                f"catalogs/registry.json: {value!r} absent from source document",
            )


def validate_snapshot(snapshot: dict[str, Any], result: VerificationResult) -> dict[str, str]:
    files = snapshot["files"]
    paths = [entry["path"] for entry in files]
    result.check(paths == utf8_sorted(paths), "source snapshot: files are not UTF-8-byte sorted")
    result.check(len(paths) == len(set(paths)), "source snapshot: duplicate paths")
    for path in paths:
        pure = PurePosixPath(path)
        result.check(
            path == unicodedata.normalize("NFC", path), f"source snapshot: non-NFC path {path}"
        )
        result.check("\\" not in path, f"source snapshot: backslash path {path}")
        result.check(not pure.is_absolute(), f"source snapshot: absolute path {path}")
        result.check(not ({".", ".."} & set(pure.parts)), f"source snapshot: unsafe path {path}")
    result.check(snapshot["file_count"] == len(files), "source snapshot: file_count mismatch")
    result.check(
        snapshot["byte_count"] == sum(entry["bytes"] for entry in files),
        "source snapshot: byte_count mismatch",
    )
    encoding_summary: dict[str, int] = {}
    for entry in files:
        encoding = entry["encoding"]
        encoding_summary[encoding] = encoding_summary.get(encoding, 0) + 1
    result.check(
        snapshot["encoding_summary"] == encoding_summary,
        "source snapshot: encoding summary mismatch",
    )
    tree_input = {"files": [{"path": entry["path"], "sha256": entry["sha256"]} for entry in files]}
    expected_tree_hash = canonical_sha256(tree_input)
    result.check(
        snapshot["tree_sha256"] == expected_tree_hash, "source snapshot: tree hash mismatch"
    )
    result.check(
        snapshot["source_snapshot_id"].endswith(expected_tree_hash[:16]),
        "source snapshot: id does not bind tree hash",
    )
    result.check(
        snapshot["reference_snapshot_id"] == snapshot["source_snapshot_id"],
        "source snapshot: reference id mismatch",
    )
    expected_roots = utf8_sorted({path.split("/", 1)[0] for path in paths})
    result.check(
        snapshot["include_roots"] == expected_roots, "source snapshot: include roots mismatch"
    )
    return {entry["path"]: entry["sha256"] for entry in files}


def validate_manifest(
    manifest: dict[str, Any],
    snapshot_id: str,
    snapshot_files: dict[str, str],
    expected_roots: set[str],
    result: VerificationResult,
) -> None:
    result.check(
        manifest["source_snapshot_id"] == snapshot_id, "fixture manifest: snapshot id mismatch"
    )
    root_files = manifest["root_files"]
    dependency_files = manifest["dependency_files"]
    root_paths = [entry["path"] for entry in root_files]
    dependency_paths = [entry["path"] for entry in dependency_files]
    result.check(
        root_paths == utf8_sorted(root_paths), f"{manifest['manifest_name']}: roots not sorted"
    )
    result.check(
        dependency_paths == utf8_sorted(dependency_paths),
        f"{manifest['manifest_name']}: dependencies not sorted",
    )
    result.check(
        set(root_paths) == expected_roots, f"{manifest['manifest_name']}: root whitelist mismatch"
    )
    result.check(
        not set(root_paths).intersection(dependency_paths),
        f"{manifest['manifest_name']}: root/dependency overlap",
    )
    for entry in [*root_files, *dependency_files]:
        result.check(
            entry["path"] in snapshot_files,
            f"{manifest['manifest_name']}: path absent from snapshot",
        )
        result.check(
            snapshot_files.get(entry["path"]) == entry["sha256"],
            f"{manifest['manifest_name']}: file hash mismatch for {entry['path']}",
        )
    expected_hash = canonical_sha256(
        {"root_files": root_files, "dependency_files": dependency_files}
    )
    result.check(
        manifest["aggregate_sha256"] == expected_hash,
        f"{manifest['manifest_name']}: aggregate hash mismatch",
    )
    result.check(
        manifest["dependency_closure"]["unresolved"] == [],
        f"{manifest['manifest_name']}: unresolved dependency closure",
    )


def manifest_reference(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "manifest_name": manifest["manifest_name"],
        "fixture_version": manifest["fixture_version"],
        "source_snapshot_id": manifest["source_snapshot_id"],
        "aggregate_sha256": manifest["aggregate_sha256"],
    }


def validate_source_artifacts(instances: dict[str, Any], result: VerificationResult) -> None:
    required = {
        "snapshot": "artifacts/source_snapshot.json",
        "world": "artifacts/xkx100-village-alley-v1.manifest.json",
        "skill": "artifacts/xkx100-skill-combat-v1.manifest.json",
        "bundle": "artifacts/xkx100-village-skill-combat-v1.bundle.json",
    }
    if any(path not in instances for path in required.values()):
        return
    snapshot = instances[required["snapshot"]]
    world = instances[required["world"]]
    skill = instances[required["skill"]]
    bundle = instances[required["bundle"]]
    snapshot_files = validate_snapshot(snapshot, result)
    snapshot_id = snapshot["source_snapshot_id"]
    validate_manifest(world, snapshot_id, snapshot_files, WORLD_ROOTS, result)
    validate_manifest(skill, snapshot_id, snapshot_files, SKILL_COMBAT_ROOTS, result)
    result.check(
        bundle["source_snapshot_id"] == snapshot_id, "acceptance bundle: snapshot id mismatch"
    )
    result.check(
        bundle["world_manifest"] == manifest_reference(world),
        "acceptance bundle: world reference mismatch",
    )
    result.check(
        bundle["skill_combat_manifest"] == manifest_reference(skill),
        "acceptance bundle: skill/combat reference mismatch",
    )
    acceptance_states = instances.get("catalogs/acceptance-states.json", {}).get("values", {})
    result.check(
        bundle["alignment_status"] in acceptance_states.get("alignment_statuses", []),
        "acceptance bundle: unknown alignment status",
    )


def identifier(value: str) -> str:
    candidate = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").upper()
    if not candidate:
        candidate = "EMPTY"
    if candidate[0].isdigit():
        candidate = f"VALUE_{candidate}"
    return candidate


def class_name(*parts: str) -> str:
    return "".join(
        part.capitalize() for value in parts for part in re.split(r"[^A-Za-z0-9]+", value) if part
    )


def render_generated_catalogs(instances: dict[str, Any]) -> str:
    groups: list[tuple[str, list[str | int]]] = []
    for relative in sorted(path for path in instances if path.startswith("catalogs/")):
        catalog = instances[relative]
        stem = Path(relative).stem
        if "values" in catalog:
            for group_name, values in sorted(catalog["values"].items()):
                groups.append((class_name(stem, group_name), values))
        if catalog.get("artifact_type") == "registry_catalog":
            groups.append(
                ("RegistryKinds", [entry["registry_kind"] for entry in catalog["entries"]])
            )
    lines = [
        '"""Generated from contracts/v1/catalogs; do not edit by hand."""',
        "",
        "from enum import IntEnum, StrEnum",
        "",
        "",
    ]
    for index, (name, values) in enumerate(groups):
        enum_type = IntEnum if all(isinstance(value, int) for value in values) else StrEnum
        lines.append(f"class {name}({enum_type.__name__}):")
        used_members: set[str] = set()
        for value in values:
            member = identifier(str(value))
            suffix = 2
            original = member
            while member in used_members:
                member = f"{original}_{suffix}"
                suffix += 1
            used_members.add(member)
            literal = json.dumps(value, ensure_ascii=True)
            lines.append(f"    {member} = {literal}")
        if not values:
            lines.append("    pass")
        if index != len(groups) - 1:
            lines.extend(["", ""])
    return "\n".join(lines) + "\n"


def validate_generated_catalogs(
    instances: dict[str, Any],
    generated_path: Path,
    write_generated: bool,
    result: VerificationResult,
) -> None:
    expected = render_generated_catalogs(instances)
    if write_generated:
        generated_path.parent.mkdir(parents=True, exist_ok=True)
        init_path = generated_path.parent / "__init__.py"
        if not init_path.exists():
            init_path.write_text("", encoding="utf-8")
        generated_path.write_text(expected, encoding="utf-8", newline="\n")
    try:
        actual = generated_path.read_text(encoding="utf-8")
    except OSError:
        actual = ""
    result.check(actual == expected, "generated catalog enums are missing or stale")


def validate_profiles(instances: dict[str, Any], result: VerificationResult) -> None:
    profile_paths = sorted(path for path in instances if path.startswith("profiles/"))
    for relative in profile_paths:
        profile = instances[relative]
        approval = profile["approval"]
        if approval["status"] != "approved":
            result.block(f"{relative}: approval is {approval['status']}")
    browser = instances.get("profiles/browser-matrix.json")
    if browser is not None:
        targets = [*browser["desktop_targets"], *browser["mobile_targets"]]
        if any(not target["tested_versions"] for target in targets):
            result.block("profiles/browser-matrix.json: exact tested browser versions are missing")
    recovery = instances.get("profiles/recovery-budget.json")
    if recovery is not None:
        report = recovery["exercise"]["latest_report"]
        if report is None:
            result.block("profiles/recovery-budget.json: isolated recovery report is missing")
        elif not report["passed"]:
            result.block("profiles/recovery-budget.json: latest recovery exercise did not pass")


def verify_repository(
    repository_root: Path = REPOSITORY_ROOT,
    *,
    write_generated: bool = False,
) -> VerificationResult:
    result = VerificationResult()
    contract_root = repository_root / "contracts" / "v1"
    validate_documents(repository_root, result)
    schemas = load_schemas(contract_root, result)
    instances = validate_instances(contract_root, schemas, result)
    requirements = parse_traceability(repository_root, result)
    validate_requirement_ids(instances, requirements, result)
    validate_dependency_lock(repository_root, result)
    validate_catalogs(repository_root, instances, result)
    validate_source_artifacts(instances, result)
    generated_path = repository_root / GENERATED_CATALOGS.relative_to(REPOSITORY_ROOT)
    validate_generated_catalogs(instances, generated_path, write_generated, result)
    validate_profiles(instances, result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify the executable M0 contract baseline.")
    parser.add_argument(
        "--structural-only",
        action="store_true",
        help="return success for valid contracts even when approvals keep M0 blocked",
    )
    parser.add_argument(
        "--write-generated",
        action="store_true",
        help="refresh deterministic Python enums before checking drift",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = verify_repository(write_generated=args.write_generated)
    if result.errors:
        print(f"M0 CONTRACTS FAILED ({len(result.errors)} errors, {result.checks} checks)")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 1
    print(f"M0 CONTRACT STRUCTURE PASSED ({result.checks} checks)")
    if result.blockers:
        print("M0 STATUS: BLOCKED")
        for blocker in result.blockers:
            print(f"BLOCKED: {blocker}")
        return 0 if args.structural_only else 2
    print("M0 STATUS: READY")
    return 0


if __name__ == "__main__":
    sys.exit(main())
