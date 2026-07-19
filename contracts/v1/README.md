# M0 executable contracts v1

This directory is the machine-readable companion to the frozen contracts in
`docs/new_engine/11_PROTOCOL_CATALOG.md` through
`docs/new_engine/16_OPERATIONS_TESTING_CONTRACT.md`.

- `schemas/` defines accepted artifact shapes.
- `catalogs/` freezes protocol, state, error-code, and typed-registry values.
- `artifacts/` records the immutable XKX100 source and fixture identities.
- `profiles/` records approved test targets; it does not claim test execution.

The documents remain the semantic authority. `scripts/verify_m0.py` checks both
directions: machine values must appear in the owning document, and every frozen
minimum listed by the verifier must appear in the machine catalog.

Content licensing, rights evidence, and public-release legal decisions are not
represented in these engineering contracts.
