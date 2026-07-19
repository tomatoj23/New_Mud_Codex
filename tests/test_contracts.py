from __future__ import annotations

import copy
import json
from pathlib import Path

from scripts.verify_m0 import VerificationResult, validate_source_artifacts, verify_repository

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_contract_repository_is_structurally_valid() -> None:
    result = verify_repository(REPOSITORY_ROOT)

    assert result.errors == []
    assert result.blockers


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
