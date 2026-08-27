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
    "reports/m0-recovery-latest.json",
}

SCHEMA_BY_ARTIFACT_TYPE = {
    "acceptance_bundle": "acceptance-bundle.schema.json",
    "browser_matrix": "browser-matrix.schema.json",
    "capacity_profile": "capacity-profile.schema.json",
    "error_code_catalog": "machine-catalog.schema.json",
    "fixture_manifest": "fixture-manifest.schema.json",
    "protocol_catalog": "machine-catalog.schema.json",
    "recovery_budget": "recovery-budget.schema.json",
    "recovery_report": "recovery-report.schema.json",
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
    "protocol-errors.json": {
        "action_domain",
        "authentication_presence",
        "protocol",
    },
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
    "character_creation_profile",
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

REQUIRED_RECOVERY_SCOPES = {
    "accounts",
    "characters",
    "world_topology",
    "content_batches",
    "audit_chain",
}

FROZEN_PROTOCOL_REQUEST_MINIMUM = {"presence.recover"}
REST_ONLY_AUTHENTICATION_ERRORS = {
    "ACCOUNT_ALREADY_RETIRED",
    "ACCOUNT_NOT_REOPENABLE",
    "ACCOUNT_RECOVERY_UNAVAILABLE",
    "ACCOUNT_REOPEN_WINDOW_EXPIRED",
    "RECOVERY_CODE_INVALID",
    "RECOVERY_CODE_RETIRED",
    "RECOVERY_RATE_LIMITED",
}
FROZEN_PROTOCOL_ERROR_MINIMUM = {
    "PRESENCE_RECOVERY_UNAVAILABLE",
    "CHARACTER_PROFILE_INVALID",
    "MODERATION_REPORT_INVALID",
}

AUTHENTICATION_ADR_FILES = {
    "docs/adr/0005-verified-contact-methods-replace-recovery-code.md",
    "docs/adr/0006-encrypted-verified-contact-storage.md",
    "docs/adr/0007-durable-verification-delivery-outbox.md",
    "docs/adr/0008-access-tokens-require-active-auth-session.md",
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

AUTHENTICATION_AUTHORITY_MARKERS = {
    "requirements_v6.md": {
        "`AUTH-005`",
        "`VerifiedContactMethod`",
        "`VerificationChallenge`",
        "RecoveryCode 已退役",
        "Character Slice 2",
    },
    "CONTEXT.md": {
        "**VerifiedContactMethod**",
        "**VerificationChallenge**",
        "A retired player-held proof",
    },
    "UBIQUITOUS_LANGUAGE.md": {
        "**RecoveryCode**（已退役历史术语）",
        "**VerifiedContactMethod**",
        "**VerificationChallenge**",
    },
    "docs/03_account_system.md": {
        "`VerifiedContactMethod`",
        "不是登录身份",
    },
    "docs/19_documentation_governance.md": {
        "ADR-0004 已由 ADR-0005",
        "ADR-0008",
        "VerifiedContactMethod",
        "VerificationChallenge",
    },
    "docs/adr/0004-recovery-code-and-presence-recovery-boundaries.md": {
        "Status: superseded by ADR-0005",
    },
    "docs/adr/0005-verified-contact-methods-replace-recovery-code.md": {
        "`VerifiedContactMethod`",
        "`VerificationChallenge`",
        "Character、Presence、PresenceRecovery 和 takeover",
    },
    "docs/adr/0006-encrypted-verified-contact-storage.md": {"keyed lookup digest"},
    "docs/adr/0007-durable-verification-delivery-outbox.md": {
        "PostgreSQL 持久 outbox",
    },
    "docs/adr/0008-access-tokens-require-active-auth-session.md": {
        "`active` 的 AuthSession",
    },
    "docs/new_engine/00_README.md": {
        "已验证邮箱注册",
        "普通账号名/密码登录",
    },
    "docs/new_engine/03_RUNTIME_SESSIONS.md": {
        "REST 已验证邮箱注册",
        "VerifiedContactMethod",
        "VerificationChallenge",
    },
    "docs/new_engine/08_PERMISSIONS_ADMIN_API.md": {
        "/api/v1/auth/registration-verification/request",
        "/api/v1/auth/password-reset/request",
        "`RECOVERY_CODE_RETIRED`",
        "`VerifiedContactMethod`",
    },
    "docs/new_engine/10_ROADMAP.md": {
        "Auth Baseline Amendment",
        "Character Slice 2",
        "Issue #10",
    },
    "docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md": {
        "`VerificationChallenge`",
        "`VerifiedContactMethod`",
        "`RECOVERY_CODE_RETIRED`",
        "`active` AuthSession",
    },
    "docs/new_engine/15_FRONTEND_H5_CONTRACT.md": {
        "/api/v1/auth/registration-verification/request",
        "/api/v1/auth/password-reset/request",
        "邮箱验证码",
    },
    "docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md": {
        "`VerificationDeliveryOutbox`",
        "`Idempotency-Key`",
        "`RECOVERY_CODE_RETIRED`",
    },
    "docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md": {
        "| `AUTH-005` | `implemented` |",
        "Issue #10",
        "Issue #16",
        "20_AUTH_BASELINE_EVIDENCE.md",
    },
    "docs/new_engine/18_IMPLEMENTATION_STATUS.md": {
        "Auth Baseline Amendment",
        "| `AUTH-005` | `implemented` |",
        "Issue #10",
        "Issue #16",
        "20_AUTH_BASELINE_EVIDENCE.md",
    },
    "docs/new_engine/19_V6_CONTRACT_DIFFERENCES.md": {
        "`VerifiedContactMethod`",
        "`VerificationChallenge`",
        "ADR-0005",
        "20_AUTH_BASELINE_EVIDENCE.md",
    },
    "docs/new_engine/20_AUTH_BASELINE_EVIDENCE.md": {
        "`AUTH-005` | `implemented`",
        "`PublicV1Gate` | `blocked`",
        "1 skipped",
        "Character Slice 2",
    },
    "docs/new_engine/NEXT_SESSION_HANDOFF.md": {
        "Auth Baseline Amendment 的 Issue #16 正在复审收口",
        "Character Slice 2",
        "Issue #16",
        "20_AUTH_BASELINE_EVIDENCE.md",
    },
    "plans/m0-e1-tracer-bullets.md": {
        "**Status**: `in_progress`",
        "Auth Baseline Amendment",
        "Character Slice 2",
        "Issue #10",
        "#16 正式复审",
    },
    "plans/email-verification-and-account-recovery.md": {
        "**Status**: `in_progress`",
        "Issue #16",
        "20_AUTH_BASELINE_EVIDENCE.md",
    },
}

OBSOLETE_AUTHENTICATION_AUTHORITY_MARKERS = {
    "requirements_v6.md": {"- 用户名密码注册"},
    "docs/03_account_system.md": {"`AuthIdentity`：手机号、微信等外部身份"},
    "docs/19_documentation_governance.md": {"；RecoveryCode 与 CharacterCreationProfile；"},
    "docs/new_engine/00_README.md": {"首发认证固定为用户名密码注册与独立登录"},
    "docs/new_engine/03_RUNTIME_SESSIONS.md": {"REST 用户名密码注册（首次使用）"},
    "docs/new_engine/08_PERMISSIONS_ADMIN_API.md": {
        "- 用户名密码注册",
        "一次性明文 RecoveryCode",
        "### 4.4 RecoveryCode 与账号生命周期",
    },
    "docs/new_engine/13_SESSION_AUTH_STATE_MACHINE.md": {
        "REST register 只原子创建 User、GameAccount 与 RecoveryCode 哈希",
        "### 10.1 RecoveryCode 与 GameAccount 生命周期",
    },
    "docs/new_engine/15_FRONTEND_H5_CONTRACT.md": {
        "4.2 的四个开户/认证端点",
        "只在该响应一次展示 RecoveryCode",
    },
    "docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md": {
        "M1 后台 RecoveryCode 流程覆盖",
        "register/login/refresh/logout 四个端点都拒绝未允许 Origin",
    },
    "docs/new_engine/17_REQUIREMENTS_TRACEABILITY.md": {"分层总证据仍待 #16"},
    "docs/new_engine/18_IMPLEMENTATION_STATUS.md": {
        "分层总证据仍待 #16",
        "下一实现入口是 Auth Baseline Amendment 的 Issue #16",
    },
    "docs/new_engine/NEXT_SESSION_HANDOFF.md": {
        "下一步 Issue #16",
        "Issue #16 的唯一合法启动顺序",
    },
    "plans/m0-e1-tracer-bullets.md": {"当前唯一未认领 frontier 是 #16"},
    "plans/email-verification-and-account-recovery.md": {
        "运行实现尚未开始",
    },
}


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
        repository_root / "requirements_v6.md",
        repository_root / "CONTEXT.md",
        repository_root / "UBIQUITOUS_LANGUAGE.md",
        repository_root / "contracts" / "v1" / "README.md",
    ]
    documents.extend(sorted((repository_root / "docs").rglob("*.md")))
    documents.extend(sorted((repository_root / "plans").rglob("*.md")))
    return sorted(set(documents))


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
        heading_levels: list[int] = []
        fence_marker: str | None = None
        for line in text.splitlines():
            fence = re.match(r"^\s*(`{3,}|~{3,})", line)
            if fence:
                marker = fence.group(1)
                if fence_marker is None:
                    fence_marker = marker
                elif marker[0] == fence_marker[0] and len(marker) >= len(fence_marker):
                    fence_marker = None
                continue
            if fence_marker is not None:
                continue
            heading = re.match(r"^(#{1,6})\s+", line)
            if heading:
                heading_levels.append(len(heading.group(1)))

        h1_count = heading_levels.count(1)
        result.check(h1_count == 1, f"{relative}: expected exactly one H1, found {h1_count}")
        heading_jumps = [
            (previous, current)
            for previous, current in zip(heading_levels, heading_levels[1:], strict=False)
            if current > previous + 1
        ]
        result.check(
            not heading_jumps,
            f"{relative}: heading level jumps found: {heading_jumps}",
        )
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


def validate_authority_markers(
    repository_root: Path,
    result: VerificationResult,
    marker_groups: dict[str, set[str]],
    *,
    must_be_present: bool,
) -> None:
    for relative, markers in marker_groups.items():
        path = repository_root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as error:
            if must_be_present:
                result.error(f"{relative}: cannot validate authentication authority: {error}")
            continue
        for marker in sorted(markers):
            qualifier = (
                "authentication authority"
                if must_be_present
                else "obsolete authentication authority"
            )
            result.check(
                (marker in text) is must_be_present,
                f"{relative}: {qualifier} marker {marker!r} "
                f"{'is missing' if must_be_present else 'remains'}",
            )


def validate_authentication_authority(repository_root: Path, result: VerificationResult) -> None:
    validate_authority_markers(
        repository_root,
        result,
        AUTHENTICATION_AUTHORITY_MARKERS,
        must_be_present=True,
    )
    validate_authority_markers(
        repository_root,
        result,
        OBSOLETE_AUTHENTICATION_AUTHORITY_MARKERS,
        must_be_present=False,
    )
    for relative in sorted(AUTHENTICATION_ADR_FILES):
        text = (repository_root / relative).read_text(encoding="utf-8")
        decision_text = "\n".join(
            line for line in text.splitlines() if line and not line.startswith(("#", "Status:"))
        )
        sentence_count = len(re.findall(r"[。！？](?=\s|$)", decision_text))
        result.check(
            1 <= sentence_count <= 3,
            f"{relative}: authentication ADR must contain 1-3 decision sentences, "
            f"found {sentence_count}",
        )
    plan_path = repository_root / "plans" / "email-verification-and-account-recovery.md"
    plan_text = plan_path.read_text(encoding="utf-8")
    password_reset_section = plan_text.split("### D.", 1)[-1].split("### E.", 1)[0]
    blocker = re.search(r"^\*\*阻塞\*\*：([^。\n]+)。$", password_reset_section, re.MULTILINE)
    result.check(
        blocker is not None and blocker.group(1) == "C",
        "plans/email-verification-and-account-recovery.md: Issue #14 must be blocked only by C",
    )
    result.check(
        "并行" not in password_reset_section,
        "plans/email-verification-and-account-recovery.md: "
        "Issue #14 must not claim parallel delivery",
    )


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
        for directory in ("artifacts", "catalogs", "profiles", "reports")
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
        if filename == "protocol.json":
            request_section = source_text.split("## 5. 请求目录", 1)[-1].split("## 6.", 1)[0]
            frozen_requests = {
                match.group(1)
                for line in request_section.splitlines()
                if (match := re.match(r"^\|\s*`([^`]+)`\s*\|", line))
            }
            for value in frozen_requests:
                result.check(
                    value in catalog["values"]["request_types"],
                    f"{relative}: frozen request {value!r} is missing from machine catalog",
                )
            for value in FROZEN_PROTOCOL_REQUEST_MINIMUM:
                result.check(
                    value in frozen_requests,
                    f"{relative}: verifier minimum {value!r} is absent from source document",
                )
        if filename == "protocol-errors.json":
            protocol_errors = set(catalog_values(catalog))
            result.check(
                protocol_errors.isdisjoint(REST_ONLY_AUTHENTICATION_ERRORS),
                f"{relative}: REST-only authentication errors leaked into WebSocket catalog",
            )
            source_errors = {
                error for error in REST_ONLY_AUTHENTICATION_ERRORS if error in source_text
            }
            result.check(
                not source_errors,
                f"{relative}: REST-only authentication errors remain in WebSocket source: "
                f"{sorted(source_errors)}",
            )
            for value in FROZEN_PROTOCOL_ERROR_MINIMUM:
                result.check(
                    value in catalog_values(catalog),
                    f"{relative}: frozen error {value!r} is missing from machine catalog",
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


def validate_recovery_report(
    repository_root: Path,
    recovery_budget: dict[str, Any],
    instances: dict[str, Any],
    result: VerificationResult,
) -> None:
    report_reference = recovery_budget["exercise"]["latest_report"]
    if report_reference is None:
        result.block("profiles/recovery-budget.json: isolated recovery report is missing")
        return

    relative = report_reference["artifact_path"]
    report = instances.get(relative)
    if report is None:
        result.error(f"profiles/recovery-budget.json: report artifact is missing: {relative}")
        return
    report_path = repository_root / "contracts" / "v1" / relative
    try:
        report_hash = hashlib.sha256(report_path.read_bytes()).hexdigest()
    except OSError as error:
        result.error(f"{relative}: cannot hash recovery report: {error}")
        return

    result.check(
        report_reference["artifact_sha256"] == report_hash,
        "profiles/recovery-budget.json: recovery report hash mismatch",
    )
    result.check(
        report_reference["report_id"] == report["report_id"],
        "profiles/recovery-budget.json: recovery report id mismatch",
    )
    result.check(
        report_reference["evidence_level"] == report["evidence_level"],
        "profiles/recovery-budget.json: recovery evidence level mismatch",
    )
    result.check(
        report_reference["release_gate_eligible"] == report["release_gate_eligible"],
        "profiles/recovery-budget.json: recovery release eligibility mismatch",
    )
    metrics = report["metrics"]
    for key in ("measured_rpo_minutes", "measured_rto_minutes"):
        result.check(
            report_reference[key] == metrics[key],
            f"profiles/recovery-budget.json: recovery report {key} mismatch",
        )
    result.check(
        metrics["rpo_minutes_max"] == recovery_budget["rpo_minutes_max"],
        "recovery report: RPO budget mismatch",
    )
    result.check(
        metrics["rto_minutes_max"] == recovery_budget["rto_minutes_max"],
        "recovery report: RTO budget mismatch",
    )
    calculated_within_budget = (
        metrics["measured_rpo_minutes"] <= metrics["rpo_minutes_max"]
        and metrics["measured_rto_minutes"] <= metrics["rto_minutes_max"]
    )
    result.check(
        metrics["within_budget"] == calculated_within_budget,
        "recovery report: budget result is inconsistent",
    )
    validation = report["validation"]
    scope_names = [entry["scope"] for entry in validation["required_scopes"]]
    result.check(
        len(scope_names) == len(set(scope_names)),
        "recovery report: duplicate required scope results",
    )
    result.check(
        set(scope_names) == REQUIRED_RECOVERY_SCOPES,
        "recovery report: required scope set mismatch",
    )
    if report["release_gate_eligible"]:
        result.check(
            report["evidence_level"] == "release_candidate",
            "recovery report: release eligibility requires release-candidate evidence",
        )
        result.check(
            all(entry["status"] == "verified" for entry in validation["required_scopes"]),
            "recovery report: release eligibility requires every scope to be verified",
        )
    if report["evidence_level"] == "m0_infrastructure":
        result.check(
            not report["release_gate_eligible"],
            "recovery report: M0 infrastructure evidence cannot pass the release gate",
        )
    source = report["databases"]["source"]
    restored = report["databases"]["restored"]
    result.check(
        validation["schema_sha256_match"] == (source["schema_sha256"] == restored["schema_sha256"]),
        "recovery report: schema match result is inconsistent",
    )
    result.check(
        validation["migration_history_match"]
        == (source["migration_history_sha256"] == restored["migration_history_sha256"]),
        "recovery report: migration match result is inconsistent",
    )
    result.check(
        validation["table_counts_match"] == (source["table_counts"] == restored["table_counts"]),
        "recovery report: table count match result is inconsistent",
    )
    tool_versions = report["execution"]["tool_versions"]
    version_matches = [
        re.search(r"\b(\d+)(?:\.\d+)", tool_versions[key])
        for key in ("server", "pg_dump", "pg_restore")
    ]
    result.check(
        all(match is not None for match in version_matches),
        "recovery report: cannot parse PostgreSQL tool versions",
    )
    if all(match is not None for match in version_matches):
        tool_major_match = len({match.group(1) for match in version_matches if match}) == 1
        result.check(
            validation["tool_major_match"] == tool_major_match,
            "recovery report: tool major match result is inconsistent",
        )
    expected_pass = all(
        (
            validation["schema_sha256_match"],
            validation["migration_history_match"],
            validation["table_counts_match"],
            validation["tool_major_match"],
            metrics["within_budget"],
        )
    )
    result.check(report["passed"] == expected_pass, "recovery report: pass result is inconsistent")
    result.check(
        report_reference["passed"] == report["passed"],
        "profiles/recovery-budget.json: recovery pass result mismatch",
    )
    if not report["passed"]:
        result.block("profiles/recovery-budget.json: latest recovery exercise did not pass")


def validate_profiles(
    repository_root: Path,
    instances: dict[str, Any],
    result: VerificationResult,
) -> None:
    profile_paths = sorted(path for path in instances if path.startswith("profiles/"))
    for relative in profile_paths:
        profile = instances[relative]
        approval = profile["approval"]
        if approval["status"] != "approved":
            result.block(f"{relative}: approval is {approval['status']}")
    browser = instances.get("profiles/browser-matrix.json")
    if browser is not None:
        targets = [*browser["desktop_targets"], *browser["mobile_targets"]]
        if any(not target["target_versions"] for target in targets):
            result.block("profiles/browser-matrix.json: exact target browser versions are missing")
        for target in targets:
            target_versions = target["target_versions"]
            tested_versions = target["tested_versions"]
            result.check(
                all(version in target_versions for version in tested_versions),
                "profiles/browser-matrix.json: tested version is not an approved target",
            )
            if target["version_policy"] == "latest_two_stable_major":
                target_majors = {
                    version["browser_version"].split(".", maxsplit=1)[0]
                    for version in target_versions
                }
                result.check(
                    len(target_majors) >= 2,
                    "profiles/browser-matrix.json: latest-two policy lacks two browser majors",
                )
    recovery = instances.get("profiles/recovery-budget.json")
    if recovery is not None:
        validate_recovery_report(repository_root, recovery, instances, result)


def verify_repository(
    repository_root: Path = REPOSITORY_ROOT,
    *,
    write_generated: bool = False,
) -> VerificationResult:
    result = VerificationResult()
    contract_root = repository_root / "contracts" / "v1"
    validate_documents(repository_root, result)
    validate_authentication_authority(repository_root, result)
    schemas = load_schemas(contract_root, result)
    instances = validate_instances(contract_root, schemas, result)
    requirements = parse_traceability(repository_root, result)
    validate_requirement_ids(instances, requirements, result)
    validate_dependency_lock(repository_root, result)
    validate_catalogs(repository_root, instances, result)
    validate_source_artifacts(instances, result)
    generated_path = repository_root / GENERATED_CATALOGS.relative_to(REPOSITORY_ROOT)
    validate_generated_catalogs(instances, generated_path, write_generated, result)
    validate_profiles(repository_root, instances, result)
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
    print("M0 CONTRACT BASELINE: READY")
    print("MILESTONE-001 status remains governed by docs/new_engine/18_IMPLEMENTATION_STATUS.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
