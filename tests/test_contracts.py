from __future__ import annotations

import copy
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from scripts.verify_m0 import (
    VerificationResult,
    validate_authentication_authority,
    validate_documents,
    validate_recovery_report,
    validate_source_artifacts,
    verify_repository,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_contract_repository_is_ready() -> None:
    result = verify_repository(REPOSITORY_ROOT)

    assert result.errors == []
    assert result.blockers == []


def test_document_links_pass_from_tracked_files_only(tmp_path: Path) -> None:
    tracked_paths = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=REPOSITORY_ROOT,
    ).split(b"\0")
    for raw_path in tracked_paths:
        if not raw_path:
            continue
        relative = Path(raw_path.decode("utf-8"))
        source = REPOSITORY_ROOT / relative
        destination = tmp_path / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)

    result = VerificationResult()

    validate_documents(tmp_path, result)

    assert result.errors == []


def test_test_settings_honor_explicit_postgres_database() -> None:
    environment = {**os.environ, "POSTGRES_DB": "ci_service_database"}

    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            ("from new_mud.settings import test; print(test.DATABASES['default']['NAME'])"),
        ],
        cwd=REPOSITORY_ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )

    assert completed.stdout.strip() == "ci_service_database"


def test_current_authentication_authority_is_consistent() -> None:
    result = VerificationResult()

    validate_authentication_authority(REPOSITORY_ROOT, result)

    assert result.errors == []


def test_issue_16_closeout_evidence_is_published() -> None:
    evidence_path = REPOSITORY_ROOT / "docs" / "new_engine" / "20_AUTH_BASELINE_EVIDENCE.md"

    assert evidence_path.is_file()

    evidence = evidence_path.read_text(encoding="utf-8")
    assert "`AUTH-005` | `verified`" in evidence
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
