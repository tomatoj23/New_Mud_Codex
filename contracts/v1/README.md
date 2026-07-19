# M0 executable contracts v1

This directory is the machine-readable companion to the frozen contracts in
`docs/new_engine/11_PROTOCOL_CATALOG.md` through
`docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md`.

- `schemas/` defines accepted artifact shapes.
- `catalogs/` freezes protocol, state, error-code, and typed-registry values.
- `artifacts/` records the immutable XKX100 source and fixture identities.
- `profiles/` records approved test targets; it does not claim test execution.
- `reports/` records immutable, schema-validated evidence referenced by a profile.

The documents remain the semantic authority. `scripts/verify_m0.py` checks both
directions: machine values must appear in the owning document, and every frozen
minimum listed by the verifier must appear in the machine catalog.

Content licensing, rights evidence, and public-release legal decisions are not
represented in these engineering contracts.

To reproduce the M0 recovery evidence, provide `POSTGRES_HOST`,
`POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, and
`POSTGRES_PASSWORD` in the process environment. Put PostgreSQL client tools
on `PATH`, set `POSTGRES_BIN`, or pass `--postgres-bin`, then run:

```text
python scripts/run_recovery_drill.py --report-path contracts/v1/reports/m0-recovery-latest.json
```

The command never writes credentials into the report. A newly generated report
must be reviewed and its path, ID, metrics, and file SHA-256 updated together in
`profiles/recovery-budget.json`; until then the main contract gate fails.
