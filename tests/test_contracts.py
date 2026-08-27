from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.verify_m0 import (
    VerificationResult,
    validate_authentication_authority,
    validate_recovery_report,
    validate_source_artifacts,
    verify_repository,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_contract_repository_is_ready() -> None:
    result = verify_repository(REPOSITORY_ROOT)

    assert result.errors == []
    assert result.blockers == []


def test_current_authentication_authority_is_consistent() -> None:
    result = VerificationResult()

    validate_authentication_authority(REPOSITORY_ROOT, result)

    assert result.errors == []


def test_issue_16_closeout_evidence_is_published() -> None:
    evidence_path = REPOSITORY_ROOT / "docs" / "new_engine" / "20_AUTH_BASELINE_EVIDENCE.md"

    assert evidence_path.is_file()

    evidence = evidence_path.read_text(encoding="utf-8")
    assert "`AUTH-005` | `implemented`" in evidence
    assert "1 skipped" in evidence
    assert "PublicV1Gate` | `blocked`" in evidence


def test_source_artifact_hash_tampering_is_rejected() -> None:
    artifact_root = REPOSITORY_ROOT / "contracts" / "v1" / "artifacts"
    names = {
        "source_snapshot.json": "artifacts/source_snapshot.json",
        "xkx100-village-alley-v1.manifest.json": (
            "artifacts/xkx100-village-alley-v1.manifest.json"
        ),
        "xkx100-skill-combat-v1.manifest.json": ("artifacts/xkx100-skill-combat-v1.manifest.json"),
        "xkx100-village-skill-combat-v1.bundle.json": (
            "artifacts/xkx100-village-skill-combat-v1.bundle.json"
        ),
    }
    instances = {
        relative: json.loads((artifact_root / filename).read_text(encoding="utf-8"))
        for filename, relative in names.items()
    }
    instances["catalogs/acceptance-states.json"] = json.loads(
        (REPOSITORY_ROOT / "contracts" / "v1" / "catalogs" / "acceptance-states.json").read_text(
            encoding="utf-8"
        )
    )
    tampered = copy.deepcopy(instances)
    tampered["artifacts/xkx100-village-alley-v1.manifest.json"]["root_files"][0]["sha256"] = (
        "0" * 64
    )
    result = VerificationResult()

    validate_source_artifacts(tampered, result)

    assert any("file hash mismatch" in error for error in result.errors)
    assert any("aggregate hash mismatch" in error for error in result.errors)


def test_recovery_report_hash_tampering_is_rejected() -> None:
    contract_root = REPOSITORY_ROOT / "contracts" / "v1"
    budget = json.loads(
        (contract_root / "profiles" / "recovery-budget.json").read_text(encoding="utf-8")
    )
    report = json.loads(
        (contract_root / "reports" / "m0-recovery-latest.json").read_text(encoding="utf-8")
    )
    budget["exercise"]["latest_report"]["artifact_sha256"] = "0" * 64
    result = VerificationResult()

    validate_recovery_report(
        REPOSITORY_ROOT,
        budget,
        {"reports/m0-recovery-latest.json": report},
        result,
    )

    assert "profiles/recovery-budget.json: recovery report hash mismatch" in result.errors
