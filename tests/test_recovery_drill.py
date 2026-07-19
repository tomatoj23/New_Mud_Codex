from __future__ import annotations

from scripts.run_recovery_drill import normalize_schema_text, scope_results


def test_schema_hash_input_ignores_pg_dump_restriction_tokens() -> None:
    first = "\\restrict first-token\nCREATE TABLE example (id integer);\n\\unrestrict first-token\n"
    second = (
        "\\restrict second-token\nCREATE TABLE example (id integer);\n\\unrestrict second-token\n"
    )

    assert normalize_schema_text(first) == normalize_schema_text(second)


def test_empty_content_batch_table_is_not_release_recovery_evidence() -> None:
    empty_results = {
        result["scope"]: result
        for result in scope_results({"public.content_contentreleasebatch": 0})
    }
    populated_results = {
        result["scope"]: result
        for result in scope_results({"public.content_contentreleasebatch": 2})
    }

    assert empty_results["content_batches"]["status"] == "not_implemented"
    assert populated_results["content_batches"]["status"] == "verified"
