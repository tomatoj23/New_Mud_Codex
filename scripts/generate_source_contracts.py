from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

import rfc8785

GENERATOR_ID = "new-mud-source-contracts/1"
IMPLICIT_GLOBAL_INCLUDE = "include/globals.h"

WORLD_ROOTS = (
    "d/village/alley1.c",
    "d/village/alley2.c",
    "d/village/npc/dipi.c",
    "d/village/npc/obj/cloth.c",
    "d/village/npc/punk.c",
)

SKILL_COMBAT_ROOTS = (
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
)

EXCLUDED_DIRECTORY_NAMES = {".git", ".vscode", "__pycache__"}
EXCLUDED_FILE_NAMES = {".DS_Store", "Thumbs.db"}

INCLUDE_RE = re.compile(r'^\s*#\s*include\s*([<"])([^>"]+)[>"]\s*;?', re.MULTILINE)
INHERIT_RE = re.compile(r"^\s*inherit\s+(.+?)\s*;", re.MULTILINE)
DEFINE_RE = re.compile(r"^\s*#\s*define\s+([A-Z][A-Z0-9_]*)\s+(.+)$", re.MULTILINE)
CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class ContractGenerationError(RuntimeError):
    pass


@dataclass(frozen=True)
class SourceFile:
    path: str
    sha256: str
    byte_count: int
    encoding: str

    def snapshot_entry(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "sha256": self.sha256,
            "bytes": self.byte_count,
            "encoding": self.encoding,
        }

    def manifest_entry(self) -> dict[str, str]:
        return {"path": self.path, "sha256": self.sha256}


def path_sort_key(path: str) -> bytes:
    return path.encode("utf-8")


def sorted_paths(paths: Iterable[str]) -> list[str]:
    return sorted(paths, key=path_sort_key)


def normalize_path(raw_path: str) -> str:
    normalized = unicodedata.normalize("NFC", raw_path.replace(chr(92), "/"))
    pure = PurePosixPath(normalized)
    parts = pure.parts
    if pure.is_absolute() or not parts:
        raise ContractGenerationError(f"path must be relative: {raw_path!r}")
    if any(not part or part in {".", ".."} for part in parts):
        raise ContractGenerationError(f"path contains an unsafe segment: {raw_path!r}")
    if CONTROL_RE.search(normalized):
        raise ContractGenerationError(f"path contains a control character: {raw_path!r}")
    return pure.as_posix()


def canonical_sha256(value: Any) -> str:
    return hashlib.sha256(rfc8785.dumps(value)).hexdigest()


def classify_encoding(data: bytes) -> str:
    if b"\x00" in data:
        return "binary"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        try:
            data.decode("gb18030")
        except UnicodeDecodeError:
            return "binary"
        return "gb18030"
    return "utf-8"


def should_exclude(parts: tuple[str, ...], *, is_directory: bool) -> bool:
    if any(part in EXCLUDED_DIRECTORY_NAMES for part in parts):
        return True
    return not is_directory and parts[-1] in EXCLUDED_FILE_NAMES


def read_stable_file(path: Path) -> bytes:
    before = path.stat()
    if not stat.S_ISREG(before.st_mode):
        raise ContractGenerationError(f"source entry is not a regular file: {path}")
    data = path.read_bytes()
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ContractGenerationError(f"source file changed while being read: {path}")
    return data


def collect_source_files(source_root: Path) -> list[SourceFile]:
    by_path: dict[str, SourceFile] = {}
    for current, directory_names, file_names in os.walk(source_root, followlinks=False):
        current_path = Path(current)
        retained_directories: list[str] = []
        for name in sorted(directory_names):
            full_path = current_path / name
            relative_parts = full_path.relative_to(source_root).parts
            if should_exclude(relative_parts, is_directory=True):
                continue
            if full_path.is_symlink():
                raise ContractGenerationError(f"symbolic directory is not allowed: {full_path}")
            retained_directories.append(name)
        directory_names[:] = retained_directories

        for name in sorted(file_names):
            full_path = current_path / name
            relative = full_path.relative_to(source_root)
            if should_exclude(relative.parts, is_directory=False):
                continue
            if full_path.is_symlink():
                raise ContractGenerationError(f"symbolic file is not allowed: {full_path}")
            normalized = normalize_path(relative.as_posix())
            if normalized in by_path:
                raise ContractGenerationError(f"normalized path collision: {normalized}")
            data = read_stable_file(full_path)
            by_path[normalized] = SourceFile(
                path=normalized,
                sha256=hashlib.sha256(data).hexdigest(),
                byte_count=len(data),
                encoding=classify_encoding(data),
            )
    if not by_path:
        raise ContractGenerationError("source tree contains no included files")
    return [by_path[path] for path in sorted_paths(by_path)]


def strip_comments(text: str) -> str:
    def preserve_newlines(match: re.Match[str]) -> str:
        return "\n" * match.group(0).count("\n")

    without_blocks = re.sub(r"/\*.*?\*/", preserve_newlines, text, flags=re.DOTALL)
    return re.sub(r"//[^\r\n]*", "", without_blocks)


def strip_outer_parentheses(expression: str) -> str:
    result = expression.strip()
    while result.startswith("(") and result.endswith(")"):
        depth = 0
        wraps_entire_expression = True
        for index, character in enumerate(result):
            if character == "(":
                depth += 1
            elif character == ")":
                depth -= 1
                if depth == 0 and index != len(result) - 1:
                    wraps_entire_expression = False
                    break
        if not wraps_entire_expression or depth != 0:
            break
        result = result[1:-1].strip()
    return result


class ClosureResolver:
    def __init__(
        self,
        source_root: Path,
        source_files: dict[str, SourceFile],
    ) -> None:
        self.source_root = source_root
        self.source_files = source_files
        self.text_cache: dict[str, str] = {}
        self.header_macro_cache: dict[str, dict[str, str]] = {}
        self.header_macro_stack: set[str] = set()

    def read_text(self, path: str) -> str:
        if path in self.text_cache:
            return self.text_cache[path]
        source_file = self.source_files.get(path)
        if source_file is None:
            raise ContractGenerationError(f"dependency is outside the source snapshot: {path}")
        data = read_stable_file(self.source_root / Path(path))
        actual_hash = hashlib.sha256(data).hexdigest()
        if actual_hash != source_file.sha256:
            raise ContractGenerationError(f"source changed after snapshot scan: {path}")
        if source_file.encoding == "binary":
            raise ContractGenerationError(f"LPC dependency is classified as binary: {path}")
        self.text_cache[path] = data.decode(source_file.encoding)
        return self.text_cache[path]

    def resolve_include(self, owner: str, delimiter: str, target: str) -> str:
        target = unicodedata.normalize("NFC", target.strip().replace(chr(92), "/"))
        if CONTROL_RE.search(target):
            raise ContractGenerationError(f"include contains a control character in {owner}")
        candidates: list[str] = []
        if target.startswith("/"):
            candidates.append(target[1:])
        elif delimiter == '"':
            candidates.extend(
                [
                    f"{PurePosixPath(owner).parent.as_posix()}/{target}",
                    f"include/{target}",
                    target,
                ]
            )
        else:
            candidates.extend([f"include/{target}", target])
        for candidate in candidates:
            normalized = normalize_path(candidate)
            if normalized in self.source_files:
                return normalized
        raise ContractGenerationError(f"unresolved include in {owner}: {target}")

    def direct_includes(self, owner: str, text: str) -> list[str]:
        clean_text = strip_comments(text)
        includes = {
            self.resolve_include(owner, match.group(1), match.group(2))
            for match in INCLUDE_RE.finditer(clean_text)
        }
        return sorted_paths(includes)

    def parse_macros(self, text: str) -> dict[str, str]:
        macros: dict[str, str] = {}
        for match in DEFINE_RE.finditer(strip_comments(text)):
            value = match.group(2).strip()
            value = value.split("//", 1)[0].strip()
            if value:
                macros[match.group(1)] = value
        return macros

    def header_macros(self, path: str) -> dict[str, str]:
        if path in self.header_macro_cache:
            return self.header_macro_cache[path]
        if path in self.header_macro_stack:
            return {}
        self.header_macro_stack.add(path)
        text = self.read_text(path)
        macros: dict[str, str] = {}
        for included_path in self.direct_includes(path, text):
            if included_path.endswith(".h"):
                macros.update(self.header_macros(included_path))
        macros.update(self.parse_macros(text))
        self.header_macro_stack.remove(path)
        self.header_macro_cache[path] = macros
        return macros

    def macros_for(self, owner: str, text: str) -> dict[str, str]:
        macros = dict(self.header_macros(IMPLICIT_GLOBAL_INCLUDE))
        for included_path in self.direct_includes(owner, text):
            if included_path.endswith(".h"):
                macros.update(self.header_macros(included_path))
        macros.update(self.parse_macros(text))
        return macros

    def resolve_inherit_expression(
        self,
        owner: str,
        expression: str,
        macros: dict[str, str],
        macro_stack: tuple[str, ...] = (),
    ) -> str:
        value = strip_outer_parentheses(expression)
        directory_match = re.fullmatch(r'__DIR__\s*"([^"]+)"', value)
        if directory_match:
            raw_path = f"{PurePosixPath(owner).parent.as_posix()}/{directory_match.group(1)}"
        else:
            string_match = re.fullmatch(r'"([^"]+)"', value)
            if string_match:
                literal = string_match.group(1)
                raw_path = (
                    literal[1:]
                    if literal.startswith("/")
                    else f"{PurePosixPath(owner).parent.as_posix()}/{literal}"
                )
            elif re.fullmatch(r"[A-Z][A-Z0-9_]*", value):
                if value in macro_stack:
                    raise ContractGenerationError(
                        f"macro cycle while resolving inherit in {owner}: {value}"
                    )
                macro_value = macros.get(value)
                if macro_value is None:
                    raise ContractGenerationError(f"unresolved inherit macro in {owner}: {value}")
                return self.resolve_inherit_expression(
                    owner,
                    macro_value,
                    macros,
                    (*macro_stack, value),
                )
            else:
                message = (
                    f"dynamic inherit cannot enter a frozen closure in {owner}: "
                    f"{expression.strip()}"
                )
                raise ContractGenerationError(message)
        if not PurePosixPath(raw_path).suffix:
            raw_path = f"{raw_path}.c"
        normalized = normalize_path(raw_path)
        if normalized not in self.source_files:
            raise ContractGenerationError(f"unresolved inherit in {owner}: {normalized}")
        return normalized

    def resolve(self, roots: Iterable[str]) -> list[str]:
        normalized_roots = tuple(sorted_paths(normalize_path(root) for root in roots))
        missing = [path for path in normalized_roots if path not in self.source_files]
        if missing:
            raise ContractGenerationError(f"fixture roots are missing: {', '.join(missing)}")

        visited: set[str] = set()
        pending = list(reversed(normalized_roots))
        while pending:
            path = pending.pop()
            if path in visited:
                continue
            visited.add(path)
            text = self.read_text(path)
            dependencies = set(self.direct_includes(path, text))
            if path.endswith(".c"):
                dependencies.add(IMPLICIT_GLOBAL_INCLUDE)
            macros = self.macros_for(path, text)
            for match in INHERIT_RE.finditer(strip_comments(text)):
                dependencies.add(self.resolve_inherit_expression(path, match.group(1), macros))
            for dependency in reversed(sorted_paths(dependencies)):
                if dependency not in visited:
                    pending.append(dependency)
        return sorted_paths(visited.difference(normalized_roots))


def artifact_generated_at(existing_path: Path, source_snapshot_id: str) -> str:
    if existing_path.exists():
        try:
            existing = json.loads(existing_path.read_text(encoding="utf-8"))
        except OSError, json.JSONDecodeError:
            pass
        else:
            if existing.get("source_snapshot_id") == source_snapshot_id:
                generated_at = existing.get("generated_at")
                if isinstance(generated_at, str):
                    return generated_at
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_source_snapshot(
    source_root: Path,
    files: list[SourceFile],
    output_dir: Path,
) -> dict[str, Any]:
    tree_input = {"files": [file.manifest_entry() for file in files]}
    tree_sha256 = canonical_sha256(tree_input)
    source_label = re.sub(r"[^a-z0-9-]+", "-", source_root.name.lower()).strip("-")
    if source_label.startswith("xkx100-"):
        source_label = source_label.removeprefix("xkx100-")
    source_snapshot_id = f"xkx100-{source_label}-sha256-{tree_sha256[:16]}"
    encoding_summary: dict[str, int] = {}
    for file in files:
        encoding_summary[file.encoding] = encoding_summary.get(file.encoding, 0) + 1
    include_roots = sorted_paths({file.path.split("/", 1)[0] for file in files})
    return {
        "contract_version": "1",
        "artifact_type": "source_snapshot",
        "requirement_ids": ["CONVERT-001", "MILESTONE-001"],
        "source_snapshot_id": source_snapshot_id,
        "reference_snapshot_id": source_snapshot_id,
        "hash_algorithm": "sha256",
        "canonicalization": "RFC8785-JCS/UTF-8",
        "generator": GENERATOR_ID,
        "generated_at": artifact_generated_at(
            output_dir / "source_snapshot.json", source_snapshot_id
        ),
        "source": {
            "locator": f"operator-supplied:{source_root.name}",
            "description": (
                "Operator-supplied XKX100 reference tree identified by frozen raw-byte hashes."
            ),
        },
        "include_roots": include_roots,
        "exclude_rules": [
            "exclude .git, .vscode, and __pycache__ directories at any depth",
            "exclude .DS_Store and Thumbs.db files",
        ],
        "scan_rules": [
            "regular files only; symbolic links are rejected",
            "paths use Unicode NFC and forward slashes",
            "file hashes cover original bytes",
            "arrays sort by normalized path UTF-8 bytes",
        ],
        "encoding_summary": dict(sorted(encoding_summary.items())),
        "file_count": len(files),
        "byte_count": sum(file.byte_count for file in files),
        "files": [file.snapshot_entry() for file in files],
        "tree_sha256": tree_sha256,
    }


def manifest_entries(paths: Iterable[str], files: dict[str, SourceFile]) -> list[dict[str, str]]:
    return [files[path].manifest_entry() for path in sorted_paths(paths)]


def build_manifest(
    *,
    fixture_kind: str,
    manifest_name: str,
    fixture_version: int,
    source_snapshot_id: str,
    roots: Iterable[str],
    dependencies: Iterable[str],
    files: dict[str, SourceFile],
) -> dict[str, Any]:
    root_files = manifest_entries(roots, files)
    dependency_files = manifest_entries(dependencies, files)
    aggregate_input = {
        "root_files": root_files,
        "dependency_files": dependency_files,
    }
    manifest: dict[str, Any] = {
        "contract_version": "1",
        "artifact_type": "fixture_manifest",
        "requirement_ids": ["CONVERT-001", "MILESTONE-001"],
        "fixture_kind": fixture_kind,
        "manifest_name": manifest_name,
        "fixture_version": fixture_version,
        "source_snapshot_id": source_snapshot_id,
        "hash_algorithm": "sha256",
        "canonicalization": "RFC8785-JCS/UTF-8",
        "root_files": root_files,
        "dependency_files": dependency_files,
        "aggregate_sha256": canonical_sha256(aggregate_input),
        "dependency_closure": {
            "algorithm": "lpc-static-include-inherit-v1",
            "implicit_global_include": IMPLICIT_GLOBAL_INCLUDE,
            "unresolved": [],
        },
    }
    if fixture_kind == "world":
        manifest.update(
            {
                "external_boundaries": [
                    {
                        "source": "d/village/alley1.c",
                        "direction": "east",
                        "target": "d/village/sroad3.c",
                        "runtime_traversable": False,
                    }
                ],
                "expected_definition_counts": {
                    "rooms": 2,
                    "exits": 2,
                    "external_boundaries": 1,
                    "npcs": 2,
                    "items": 1,
                },
                "expected_runtime_counts": {
                    "rooms": 2,
                    "exits": 2,
                    "npcs": 2,
                    "items": 2,
                },
            }
        )
    else:
        manifest["review_scope"] = [
            "enable_and_jifa",
            "prepare_and_valid_combine",
            "perform_dispatch",
            "exert_dispatch",
            "skill_progression_feature",
            "attack_resolution_feature",
            "selected_perform_and_exert_actions",
        ]
    return manifest


def manifest_reference(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "manifest_name": manifest["manifest_name"],
        "fixture_version": manifest["fixture_version"],
        "source_snapshot_id": manifest["source_snapshot_id"],
        "aggregate_sha256": manifest["aggregate_sha256"],
    }


def build_bundle(
    source_snapshot_id: str,
    world_manifest: dict[str, Any],
    skill_manifest: dict[str, Any],
) -> dict[str, Any]:
    return {
        "contract_version": "1",
        "artifact_type": "acceptance_bundle",
        "requirement_ids": ["COMBAT-001", "CONVERT-001", "MILESTONE-001"],
        "bundle_id": "xkx100-village-skill-combat-v1",
        "bundle_version": 1,
        "source_snapshot_id": source_snapshot_id,
        "world_manifest": manifest_reference(world_manifest),
        "skill_combat_manifest": manifest_reference(skill_manifest),
        "alignment_status": "blocked",
    }


def ensure_no_absolute_source_path(value: Any, source_root: Path) -> None:
    serialized = json.dumps(value, ensure_ascii=False)
    candidates = {str(source_root), str(source_root).replace(chr(92), "/")}
    if any(candidate in serialized for candidate in candidates):
        raise ContractGenerationError("artifact would disclose the operator's absolute source path")


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="\n",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        temporary.write(payload)
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, path)


def check_output_boundary(source_root: Path, output_dir: Path) -> None:
    try:
        output_dir.relative_to(source_root)
    except ValueError:
        return
    raise ContractGenerationError("output directory must not be inside the source tree")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate immutable XKX100 source and fixture contract artifacts."
    )
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("contracts/v1/artifacts"),
    )
    parser.add_argument("--fixture-version", type=int, default=1)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = args.source_root.resolve(strict=True)
    output_dir = args.output_dir.resolve()
    if not source_root.is_dir():
        raise ContractGenerationError(f"source root is not a directory: {source_root}")
    if args.fixture_version < 1:
        raise ContractGenerationError("fixture version must be at least 1")
    check_output_boundary(source_root, output_dir)

    first_scan = collect_source_files(source_root)
    source_files = {file.path: file for file in first_scan}
    snapshot = build_source_snapshot(source_root, first_scan, output_dir)
    resolver = ClosureResolver(source_root, source_files)
    world_dependencies = resolver.resolve(WORLD_ROOTS)
    skill_dependencies = resolver.resolve(SKILL_COMBAT_ROOTS)
    world_manifest = build_manifest(
        fixture_kind="world",
        manifest_name="xkx100-village-alley-v1",
        fixture_version=args.fixture_version,
        source_snapshot_id=snapshot["source_snapshot_id"],
        roots=WORLD_ROOTS,
        dependencies=world_dependencies,
        files=source_files,
    )
    skill_manifest = build_manifest(
        fixture_kind="skill_combat",
        manifest_name="xkx100-skill-combat-v1",
        fixture_version=args.fixture_version,
        source_snapshot_id=snapshot["source_snapshot_id"],
        roots=SKILL_COMBAT_ROOTS,
        dependencies=skill_dependencies,
        files=source_files,
    )
    bundle = build_bundle(snapshot["source_snapshot_id"], world_manifest, skill_manifest)

    second_scan = collect_source_files(source_root)
    if first_scan != second_scan:
        raise ContractGenerationError("source tree changed during contract generation")

    artifacts = {
        "source_snapshot.json": snapshot,
        "xkx100-village-alley-v1.manifest.json": world_manifest,
        "xkx100-skill-combat-v1.manifest.json": skill_manifest,
        "xkx100-village-skill-combat-v1.bundle.json": bundle,
    }
    for artifact in artifacts.values():
        ensure_no_absolute_source_path(artifact, source_root)
    for name, artifact in artifacts.items():
        write_json_atomic(output_dir / name, artifact)

    print(
        json.dumps(
            {
                "source_snapshot_id": snapshot["source_snapshot_id"],
                "file_count": snapshot["file_count"],
                "tree_sha256": snapshot["tree_sha256"],
                "world_dependencies": len(world_dependencies),
                "skill_combat_dependencies": len(skill_dependencies),
                "output_dir": output_dir.relative_to(Path.cwd().resolve()).as_posix(),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
