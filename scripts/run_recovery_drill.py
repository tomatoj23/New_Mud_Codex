from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tempfile
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import psycopg
from psycopg import sql

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_PATH = REPOSITORY_ROOT / "contracts" / "v1" / "reports" / "m0-recovery-latest.json"
REQUIRED_SCOPES = (
    "accounts",
    "characters",
    "world_topology",
    "content_batches",
    "audit_chain",
)
DATABASE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]{0,62}$")
VERSION_RE = re.compile(r"\b(\d+)(?:\.(\d+))?(?:\.(\d+))?\b")


class DrillError(RuntimeError):
    pass


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    database: str
    user: str
    password: str
    connect_timeout: int

    @classmethod
    def from_environment(cls) -> DatabaseConfig:
        password = os.getenv("POSTGRES_PASSWORD")
        if password is None:
            raise DrillError("POSTGRES_PASSWORD must be supplied in the process environment")
        database = os.getenv("POSTGRES_DB", "new_mud")
        user = os.getenv("POSTGRES_USER", "new_mud")
        for label, value in (("POSTGRES_DB", database), ("POSTGRES_USER", user)):
            if not DATABASE_NAME_RE.fullmatch(value):
                raise DrillError(f"{label} is not a valid PostgreSQL identifier")
        return cls(
            host=os.getenv("POSTGRES_HOST", "127.0.0.1"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
            database=database,
            user=user,
            password=password,
            connect_timeout=int(os.getenv("POSTGRES_CONNECT_TIMEOUT", "5")),
        )

    def connection_kwargs(self, database: str) -> dict[str, Any]:
        return {
            "host": self.host,
            "port": self.port,
            "dbname": database,
            "user": self.user,
            "password": self.password,
            "connect_timeout": self.connect_timeout,
            "application_name": "new-mud-recovery-drill",
        }

    def tool_environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment["PGPASSWORD"] = self.password
        environment["PGCONNECT_TIMEOUT"] = str(self.connect_timeout)
        return environment


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso_timestamp(value: datetime) -> str:
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return sha256_bytes(payload)


def resolve_tool(name: str, postgres_bin: Path | None) -> Path:
    executable_name = f"{name}.exe" if os.name == "nt" else name
    if postgres_bin is not None:
        candidate = postgres_bin / executable_name
        if candidate.is_file():
            return candidate
        raise DrillError(f"PostgreSQL tool not found: {candidate}")
    discovered = shutil.which(name)
    if discovered is None:
        raise DrillError(f"{name} is not on PATH; pass --postgres-bin or set POSTGRES_BIN")
    return Path(discovered)


def run_tool(
    executable: Path,
    arguments: Sequence[str],
    *,
    environment: dict[str, str],
    timeout_seconds: int = 300,
) -> str:
    command = [str(executable), *arguments]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()
        raise DrillError(
            f"{executable.name} failed with exit code {completed.returncode}: {detail}"
        )
    return completed.stdout.strip()


def tool_version(executable: Path, environment: dict[str, str]) -> str:
    return run_tool(executable, ["--version"], environment=environment, timeout_seconds=30)


def version_major(value: str) -> int:
    match = VERSION_RE.search(value)
    if match is None:
        raise DrillError(f"cannot parse PostgreSQL version from {value!r}")
    return int(match.group(1))


def database_arguments(config: DatabaseConfig, database: str) -> list[str]:
    return [
        "--host",
        config.host,
        "--port",
        str(config.port),
        "--username",
        config.user,
        "--dbname",
        database,
    ]


def normalize_schema_text(value: str) -> bytes:
    normalized: list[str] = []
    for line in value.splitlines():
        if line.startswith(("\\restrict ", "\\unrestrict ")):
            continue
        normalized.append(line.rstrip())
    return ("\n".join(normalized).rstrip() + "\n").encode("utf-8")


def normalize_schema_dump(path: Path) -> bytes:
    return normalize_schema_text(path.read_text(encoding="utf-8"))


def fetch_scalar(cursor: psycopg.Cursor[Any]) -> Any:
    row = cursor.fetchone()
    if row is None:
        raise DrillError("PostgreSQL scalar query returned no row")
    return row[0]


def collect_database_data(
    connection: psycopg.Connection[Any],
) -> tuple[str, dict[str, int], str]:
    server_version = str(fetch_scalar(connection.execute("SHOW server_version")))
    table_rows = connection.execute(
        """
        SELECT schemaname, tablename
        FROM pg_catalog.pg_tables
        WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
        ORDER BY schemaname, tablename
        """
    ).fetchall()
    table_counts: dict[str, int] = {}
    for schema_name, table_name in table_rows:
        statement = sql.SQL("SELECT count(*) FROM {}.{}").format(
            sql.Identifier(str(schema_name)),
            sql.Identifier(str(table_name)),
        )
        count = int(fetch_scalar(connection.execute(statement)))
        table_counts[f"{schema_name}.{table_name}"] = count

    migration_history: list[list[str]] = []
    if "public.django_migrations" in table_counts:
        rows = connection.execute(
            """
            SELECT app, name, applied
            FROM public.django_migrations
            ORDER BY app, name, applied
            """
        ).fetchall()
        migration_history = [
            [str(app), str(name), applied.isoformat()] for app, name, applied in rows
        ]
    return server_version, table_counts, canonical_sha256(migration_history)


def extract_schema(
    pg_restore: Path,
    archive_path: Path,
    output_path: Path,
    environment: dict[str, str],
) -> str:
    run_tool(
        pg_restore,
        [
            "--schema-only",
            "--no-owner",
            "--no-privileges",
            "--file",
            str(output_path),
            str(archive_path),
        ],
        environment=environment,
    )
    return sha256_bytes(normalize_schema_dump(output_path))


def dump_schema_archive(
    pg_dump: Path,
    config: DatabaseConfig,
    database: str,
    archive_path: Path,
    environment: dict[str, str],
) -> None:
    run_tool(
        pg_dump,
        [
            *database_arguments(config, database),
            "--format=custom",
            "--schema-only",
            "--no-owner",
            "--no-privileges",
            "--file",
            str(archive_path),
        ],
        environment=environment,
    )


def scope_results(table_counts: dict[str, int]) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for scope in REQUIRED_SCOPES:
        if scope == "content_batches":
            count = table_counts.get("public.content_contentreleasebatch")
            if count is not None and count > 0:
                results.append(
                    {
                        "scope": scope,
                        "status": "verified",
                        "basis": (
                            f"{count} persisted content release batch rows matched after restore."
                        ),
                    }
                )
            else:
                results.append(
                    {
                        "scope": scope,
                        "status": "not_implemented",
                        "basis": (
                            "The table contract exists but no release batch row is present; "
                            "release-data recovery is not yet exercised."
                        ),
                    }
                )
            continue
        results.append(
            {
                "scope": scope,
                "status": "not_implemented",
                "basis": f"The {scope} persistence slice is not implemented in M0.",
            }
        )
    return results


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    path.write_text(payload, encoding="utf-8", newline="\n")


def run_drill(args: argparse.Namespace) -> dict[str, Any]:
    config = DatabaseConfig.from_environment()
    postgres_bin_value = args.postgres_bin or os.getenv("POSTGRES_BIN")
    postgres_bin = Path(postgres_bin_value).resolve() if postgres_bin_value else None
    tools = {
        name: resolve_tool(name, postgres_bin)
        for name in ("createdb", "dropdb", "pg_dump", "pg_restore")
    }
    environment = config.tool_environment()
    versions = {
        "pg_dump": tool_version(tools["pg_dump"], environment),
        "pg_restore": tool_version(tools["pg_restore"], environment),
    }

    started_at = utc_now()
    restore_database = (
        f"new_mud_recovery_{started_at.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
    )
    created_at: datetime | None = None
    dropped_at: datetime | None = None
    recovery_started_at: datetime | None = None
    validation_completed_at: datetime | None = None
    report: dict[str, Any] | None = None

    with tempfile.TemporaryDirectory(prefix="new-mud-recovery-") as temporary:
        temporary_root = Path(temporary)
        backup_path = temporary_root / "source.dump"
        source_schema_path = temporary_root / "source-schema.sql"
        restored_schema_archive = temporary_root / "restored-schema.dump"
        restored_schema_path = temporary_root / "restored-schema.sql"
        try:
            with (
                psycopg.connect(**config.connection_kwargs(config.database)) as source_connection,
                source_connection.transaction(),
            ):
                source_connection.execute(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"
                )
                snapshot_id = str(
                    fetch_scalar(source_connection.execute("SELECT pg_export_snapshot()"))
                )
                snapshot_exported_at = utc_now()
                source_server, source_counts, source_migrations = collect_database_data(
                    source_connection
                )
                run_tool(
                    tools["pg_dump"],
                    [
                        *database_arguments(config, config.database),
                        "--format=custom",
                        "--no-owner",
                        "--no-privileges",
                        "--snapshot",
                        snapshot_id,
                        "--file",
                        str(backup_path),
                    ],
                    environment=environment,
                )
            backup_completed_at = utc_now()
            source_schema_hash = extract_schema(
                tools["pg_restore"],
                backup_path,
                source_schema_path,
                environment,
            )
            backup_hash = sha256_bytes(backup_path.read_bytes())
            backup_size = backup_path.stat().st_size

            recovery_started_at = utc_now()
            run_tool(
                tools["createdb"],
                [
                    "--host",
                    config.host,
                    "--port",
                    str(config.port),
                    "--username",
                    config.user,
                    "--maintenance-db",
                    "postgres",
                    "--template",
                    "template0",
                    "--encoding",
                    "UTF8",
                    restore_database,
                ],
                environment=environment,
            )
            created_at = utc_now()
            run_tool(
                tools["pg_restore"],
                [
                    *database_arguments(config, restore_database),
                    "--exit-on-error",
                    "--no-owner",
                    "--no-privileges",
                    str(backup_path),
                ],
                environment=environment,
            )
            with psycopg.connect(
                **config.connection_kwargs(restore_database)
            ) as restored_connection:
                restored_server, restored_counts, restored_migrations = collect_database_data(
                    restored_connection
                )
            dump_schema_archive(
                tools["pg_dump"],
                config,
                restore_database,
                restored_schema_archive,
                environment,
            )
            restored_schema_hash = extract_schema(
                tools["pg_restore"],
                restored_schema_archive,
                restored_schema_path,
                environment,
            )
            validation_completed_at = utc_now()

            schema_match = source_schema_hash == restored_schema_hash
            migrations_match = source_migrations == restored_migrations
            counts_match = source_counts == restored_counts
            measured_rpo = (recovery_started_at - snapshot_exported_at).total_seconds() / 60
            measured_rto = (validation_completed_at - recovery_started_at).total_seconds() / 60
            within_budget = measured_rpo <= args.rpo_minutes and measured_rto <= args.rto_minutes
            tool_major_match = (
                version_major(source_server)
                == version_major(versions["pg_dump"])
                == version_major(versions["pg_restore"])
            )
            passed = all(
                (schema_match, migrations_match, counts_match, within_budget, tool_major_match)
            )

            source_database = {
                "database_name": config.database,
                "server_version": source_server,
                "schema_sha256": source_schema_hash,
                "migration_history_sha256": source_migrations,
                "table_counts": source_counts,
            }
            restored_database = {
                "database_name": restore_database,
                "server_version": restored_server,
                "schema_sha256": restored_schema_hash,
                "migration_history_sha256": restored_migrations,
                "table_counts": restored_counts,
            }
            report = {
                "contract_version": "1",
                "artifact_type": "recovery_report",
                "report_id": f"m0-recovery-{started_at.strftime('%Y%m%d-%H%M%S')}z",
                "report_version": 1,
                "requirement_ids": ["MILESTONE-001", "NFR-002"],
                "source_documents": [
                    "docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md",
                    "requirements_v6.md",
                ],
                "historical_source_documents": ["requirements_v5.md"],
                "evidence_level": "m0_infrastructure",
                "release_gate_eligible": False,
                "backup": {
                    "format": "postgresql_custom",
                    "sha256": backup_hash,
                    "size_bytes": backup_size,
                    "snapshot_exported_at": iso_timestamp(snapshot_exported_at),
                    "completed_at": iso_timestamp(backup_completed_at),
                    "stored_in_repository": False,
                    "retained_after_drill": False,
                },
                "databases": {
                    "source": source_database,
                    "restored": restored_database,
                },
                "metrics": {
                    "rpo_definition": "recovery_start_minus_exported_snapshot",
                    "rto_definition": "recovery_start_to_validation_complete",
                    "measured_rpo_minutes": round(measured_rpo, 6),
                    "measured_rto_minutes": round(measured_rto, 6),
                    "rpo_minutes_max": args.rpo_minutes,
                    "rto_minutes_max": args.rto_minutes,
                    "within_budget": within_budget,
                },
                "validation": {
                    "schema_sha256_match": schema_match,
                    "migration_history_match": migrations_match,
                    "table_counts_match": counts_match,
                    "tool_major_match": tool_major_match,
                    "required_scopes": scope_results(source_counts),
                },
                "passed": passed,
            }
        finally:
            if created_at is not None:
                run_tool(
                    tools["dropdb"],
                    [
                        "--host",
                        config.host,
                        "--port",
                        str(config.port),
                        "--username",
                        config.user,
                        "--maintenance-db",
                        "postgres",
                        "--if-exists",
                        "--force",
                        restore_database,
                    ],
                    environment=environment,
                )
                dropped_at = utc_now()

        if report is None or recovery_started_at is None or validation_completed_at is None:
            raise DrillError("recovery drill did not produce a report")
        if created_at is None or dropped_at is None:
            raise DrillError("isolated recovery database cleanup was not verified")
        report["execution"] = {
            "started_at": iso_timestamp(started_at),
            "runner": args.runner,
            "runner_platform": f"{platform.system()} {platform.release()}",
            "isolated_database": {
                "database_name": restore_database,
                "created_at": iso_timestamp(created_at),
                "dropped_at": iso_timestamp(dropped_at),
                "deleted": True,
            },
            "tool_versions": {
                "server": report["databases"]["source"]["server_version"],
                **versions,
            },
        }
    report["execution"]["completed_at"] = iso_timestamp(utc_now())
    write_report(args.report_path, report)
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an isolated PostgreSQL dump/restore drill and emit M0 evidence."
    )
    parser.add_argument(
        "--postgres-bin",
        type=Path,
        help="directory containing PostgreSQL client tools; defaults to POSTGRES_BIN or PATH",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=DEFAULT_REPORT_PATH,
        help="JSON report output path",
    )
    parser.add_argument("--runner", default="project-owner-controlled-environment")
    parser.add_argument("--rpo-minutes", type=int, default=15)
    parser.add_argument("--rto-minutes", type=int, default=60)
    args = parser.parse_args()
    if not 1 <= args.rpo_minutes <= 15:
        parser.error("--rpo-minutes must be between 1 and 15")
    if not 1 <= args.rto_minutes <= 60:
        parser.error("--rto-minutes must be between 1 and 60")
    return args


def main() -> int:
    try:
        report = run_drill(parse_args())
    except (DrillError, OSError, psycopg.Error, subprocess.SubprocessError) as error:
        print(f"RECOVERY DRILL FAILED: {error}")
        return 1
    metrics = report["metrics"]
    print(
        "RECOVERY DRILL PASSED"
        if report["passed"]
        else "RECOVERY DRILL COMPLETED WITH FAILED CHECKS"
    )
    print(f"report_id={report['report_id']}")
    print(f"measured_rpo_minutes={metrics['measured_rpo_minutes']}")
    print(f"measured_rto_minutes={metrics['measured_rto_minutes']}")
    print("release_gate_eligible=false")
    return 0 if report["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
