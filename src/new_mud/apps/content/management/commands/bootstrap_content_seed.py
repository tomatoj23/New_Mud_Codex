from __future__ import annotations

import json
from importlib import resources
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from new_mud.apps.content.seed_artifact import (
    SeedArtifactExpectation,
    bootstrap_seed_artifact,
)
from new_mud.apps.content.startup import ContentStartupError
from new_mud.mudlibs.jinyong_core.manifest import (
    MANIFEST_VERSION,
    MUDLIB_KEY,
    SEED_BUNDLE_ID,
    TARGET_CONTENT_RELEASE,
)
from new_mud.mudlibs.jinyong_core.registry import build_registry_catalog


class Command(BaseCommand):
    help = "Validate and atomically bootstrap the frozen jinyong.core seed artifact."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--instance-id", required=True)
        parser.add_argument(
            "--artifact",
            type=Path,
            help="Optional explicit artifact path; defaults to the packaged frozen seed.",
        )

    def handle(self, *args: Any, **options: Any) -> str | None:
        explicit_artifact = options.get("artifact")
        packaged_artifact = resources.files("new_mud.mudlibs.jinyong_core").joinpath(
            "seed/content-seed-v1.json"
        )
        expectation = SeedArtifactExpectation(
            mudlib_key=MUDLIB_KEY,
            seed_bundle_id=SEED_BUNDLE_ID,
            target_content_release=TARGET_CONTENT_RELEASE,
            manifest_version=MANIFEST_VERSION,
        )
        try:
            if isinstance(explicit_artifact, Path):
                result = bootstrap_seed_artifact(
                    instance_id=options["instance_id"],
                    expectation=expectation,
                    artifact_path=explicit_artifact,
                    registry_catalog=build_registry_catalog(),
                )
            else:
                with resources.as_file(packaged_artifact) as artifact_path:
                    result = bootstrap_seed_artifact(
                        instance_id=options["instance_id"],
                        expectation=expectation,
                        artifact_path=artifact_path,
                        registry_catalog=build_registry_catalog(),
                    )
        except ContentStartupError as error:
            raise CommandError(f"{error.code}: {error}") from error
        output = json.dumps(
            {
                "status": result.startup.status,
                "instance_id": options["instance_id"],
                "mudlib_key": MUDLIB_KEY,
                "seed_bundle_id": SEED_BUNDLE_ID,
                "artifact_hash": result.artifact.artifact_hash,
                "batch_id": str(result.startup.identity.batch_id),
                "release_version": result.startup.identity.release_version,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return output
