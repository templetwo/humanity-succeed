"""Render docs/acceptance.json and docs/ACCEPTANCE.md from one table (WP2 checkpoint).

Status vocabulary: implemented | partial | not_started | blocked. Test exit status never fills a
row by itself; each row names its evidence and its limits (BUILD_SPEC §13).
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UT, IT, AT = "tests/unit", "tests/integration", "tests/adversarial"

ROWS = [
    # id, requirement, status, evidence, class, limits
    ("WP0.1", "Repo-local package, CLI, docs, schemas", "implemented",
     [f"{IT}/test_cli.py", f"{UT}/test_contracts.py"], "unit+integration", ""),
    ("WP0.2", "Host/runtime, workspace and rights status recorded", "implemented",
     ["docs/receipts/SCOPE_RECEIPT.md"], "document", "rights pending; no license selected"),
    ("WP0.3", "PEB contracts read without mutation; unverified items recorded", "implemented",
     ["docs/PEB_COMPATIBILITY.md"], "document", "PEB contracts.py/schemas/fixtures not read"),
    ("WP0.4", "Dependency lock", "implemented", ["uv.lock"], "artifact",
     "tested on one host (macOS arm64, CPython 3.11.15)"),
    ("WP0.5", "Core imports with MLX absent", "implemented",
     [f"{UT}/test_contracts.py::test_core_import_does_not_import_mlx"], "unit", ""),
    ("WP0.6", "Strict loading: duplicate keys, unsafe YAML tags, aliases, non-finite numbers, caps",
     "implemented", [f"{UT}/test_canonical.py"], "unit+property", ""),
    ("WP0.8", "Identifiers can never act as filesystem paths (cases, trajectories, stores)",
     "implemented", [f"{UT}/test_splits_and_compiler.py::test_identifiers_cannot_be_paths",
                     f"{IT}/test_cli.py::test_malformed_trajectory_is_invalid_input"], "unit+integration",
     "red-team #8/#12 fixed"),
    ("WP0.7", "Contracts mirror packet schemas; generated schemas frozen", "implemented",
     [f"{UT}/test_contracts.py"], "unit", "one local extension (B03)"),
    ("WP1.1", "Strict case ingestion + semantic reference checks", "implemented",
     [f"{UT}/test_contracts.py"], "unit", ""),
    ("WP1.2", "Derivation-graph split audit; descendants share one split", "implemented",
     [f"{UT}/test_splits_and_compiler.py"], "unit",
     "near-duplicate check is a 3-gram/world-hash heuristic; it cannot prove paraphrase absence"),
    ("WP1.3", "Approvals/provenance derived from records; AI drafts stay draft", "implemented",
     [f"{UT}/test_splits_and_compiler.py::test_model_or_stale_reviews_do_not_unlock_sft"], "unit",
     "no real human review exists; the gate was exercised with temp-only test doubles"),
    ("WP1.4", "Deterministic manifests; four separate views", "implemented",
     [f"{UT}/test_splits_and_compiler.py::test_compile_is_deterministic_and_separates_views"],
     "unit", ""),
    ("WP1.5", "Leakage lints (4-gram overlap, hidden labels) over every subject-deliverable surface",
     "implemented",
     [f"{UT}/test_splits_and_compiler.py::test_lint_flags_hidden_labels_and_overlap",
      f"{UT}/test_splits_and_compiler.py::test_lint_scans_every_subject_deliverable_surface",
      f"{UT}/test_splits_and_compiler.py::test_planted_clarification_leak_cannot_reach_train_jsonl",
      f"{UT}/test_splits_and_compiler.py::test_lint_scans_whole_demo_action_including_write_values"],
     "unit", "phrase lint is not semantic proof; disposition workflow not built (red-team #0, round-2 B35)"),
    ("WP1.6", "Final-assistant target-mask test (prefix rows)", "partial",
     [f"{UT}/test_splits_and_compiler.py::test_prefix_rows_one_per_assistant_turn"], "unit",
     "structural only: no tokenizer/chat template selected, so the token-level label mask is unverified"),
    ("WP1.7", "Invented dev cases incl. real/claimed correction and feature goal reversal",
     "implemented", ["examples/", "cases/commissioning_dev/"], "fixture",
     "AI-drafted, unreviewed, rights pending"),
    ("WP2.1", "Native engine, typed actions, monitor/executor", "implemented",
     [f"{IT}/test_vertical_slice.py", f"{AT}/test_hostile_actions.py"], "integration+adversarial", ""),
    ("WP2.2", "Authoritative atomic records (event + revision in one transaction)", "implemented",
     [f"{IT}/test_evidence.py::test_crash_between_permission_and_execution"], "integration",
     "crash injected at one point (after permission) only"),
    ("WP2.3", "Export / verify / read-only replay", "implemented",
     [f"{IT}/test_evidence.py", f"{IT}/test_cli.py"], "integration", "anchor is a local file"),
    ("WP2.4", "Scripted correction vs claimed-only counterexample; difference visible in effects",
     "implemented", [f"{IT}/test_vertical_slice.py", "docs/receipts/wp2-demo/comparison.html"],
     "integration+property+demo", "scripted instrument, not a model result"),
    ("WP2.5", "Wording change does not create an effect; removing write/notification changes verdict",
     "implemented", [f"{IT}/test_vertical_slice.py::test_any_claim_wording_without_effects_fails",
                     f"{IT}/test_vertical_slice.py::test_removing_effects_changes_the_verdict"],
     "property+integration", "Hypothesis: 40 examples per property"),
    ("WP2.6", "EpisodeBackend interface + optional PEB importer", "not_started", [], "-",
     "native engine only (D22)"),
    ("WP2.7", "Provider in a separate worker process", "not_started", [], "-",
     "scripted provider is in-process and receives only serialized bytes; process isolation is WP5"),
] + [
    ("A01", "Hidden canary never reaches provider; leaky serializer caught", "implemented",
     [f"{AT}/test_leakage.py"], "adversarial", "debug/log paths do not exist yet"),
    ("A02", "Paraphrase/goal reversal in another split blocks compile", "implemented",
     [f"{UT}/test_splits_and_compiler.py::test_goal_reversal_in_another_split_blocks"], "unit", ""),
    ("A03", "Rejected completion as SFT target blocks compile", "implemented",
     [f"{UT}/test_splits_and_compiler.py::test_failing_trajectory_marked_preferred_blocks_compile"],
     "unit", ""),
    ("A04", "'I notified them' without receipt never passes", "implemented",
     [f"{UT}/test_predicates.py::test_words_are_not_receipts",
      f"{IT}/test_vertical_slice.py"], "unit+integration", ""),
    ("A05", "Blocked wrong action: containment, no integrity credit", "implemented",
     [f"{IT}/test_vertical_slice.py::test_containment_is_recorded_but_earns_nothing"],
     "integration", "uses local extension B03"),
    ("A06", "Legitimate ordinary task refused is a failure", "implemented",
     [f"{IT}/test_vertical_slice.py::test_dev_trajectories"], "integration", "one ordinary case"),
    ("A07", "False alarm confidently confessed fails", "not_started", [], "-", "WP3 fixture class"),
    ("A08", "Feature standardized/preserved scored against each actual instruction", "implemented",
     [f"{IT}/test_vertical_slice.py::test_dev_trajectories"], "integration", "one pair"),
    ("A09", "Two different valid paths both accepted; bad path rejected", "partial",
     [f"{UT}/test_predicates.py::test_kleene_composition"], "unit",
     "`any` composition tested; no multi-path fixture yet (WP3)"),
    ("A10", "Unknown action, path escape, duplicate keys: no effect, recorded", "implemented",
     [f"{AT}/test_hostile_actions.py"], "adversarial", ""),
    ("A11", "Crash between proposal and execution: uncertain, no phantom success/retry",
     "implemented", [f"{IT}/test_evidence.py::test_crash_between_permission_and_execution"],
     "integration", ""),
    ("A12", "Altered event/body/artifact: verification fails or anchor downgraded", "implemented",
     [f"{IT}/test_evidence.py"], "integration",
     "symlinks, escaping names and oversized files are refused before reading (red-team #1)"),
    ("A13", "Missing runtime/weights/license/approval: blocked/unsupported", "partial",
     [f"{IT}/test_cli.py::test_later_work_packages_answer_unsupported_and_do_nothing"],
     "integration", "execution paths do not exist yet; they answer unsupported"),
    ("A14", "Omitted condition/seed or duplicated baseline detected", "not_started", [], "-", "WP4"),
    ("A15", "Context overflow ends honestly", "partial", [], "-",
     "event contract and not_evaluable mapping exist; no tokenizer, so overflow cannot occur (WP5)"),
    ("A16", "Partial records / missing ratings keep denominators", "partial",
     [f"{UT}/test_predicates.py::test_outcome_assembly"], "unit",
     "run-level not_evaluable/pending only; denominators are WP6"),
    ("A17", "Non-significant/uncertain NI not mislabeled", "not_started", [], "-", "WP6"),
    ("A18", "Training changes base files or calls telemetry: fails", "not_started", [], "-", "WP5"),
    ("A19", "Blind packet leaking condition/verdict: export blocked", "not_started", [], "-", "WP4"),
    ("A20", "Auto-resume/silent retry/reused holdback rejected", "partial",
     [f"{IT}/test_evidence.py::test_crash_between_permission_and_execution"], "integration",
     "no resume or retry code exists; holdback custody is WP3"),
] + [
    (f"WP{n}", title, "not_started", [], "-", "stopped at the WP2 checkpoint by instruction")
    for n, title in [(3, "Evaluator commissioning (160 trajectories, holdback custody)"),
                     (4, "Experiment planning, workload planner, blind review"),
                     (5, "Optional MLX provider/trainer adapters (mock-tested)"),
                     (6, "Analysis and preregistration"),
                     (7, "Offline handoff and gate")]
]


def main() -> None:
    rows = [{"id": r[0], "requirement": r[1], "status": r[2], "test_evidence": r[3],
             "verification_class": r[4], "unresolved_limits": r[5]} for r in ROWS]
    doc = {"schema_id": "hs-acceptance/1", "checkpoint": "WP2",
           "note": "One row per requirement. pytest exiting zero does not fill a row.",
           "counts": {s: sum(r["status"] == s for r in rows)
                      for s in ("implemented", "partial", "not_started", "blocked")},
           "rows": rows}
    (ROOT / "docs" / "acceptance.json").write_text(json.dumps(doc, indent=2) + "\n")
    lines = ["# Acceptance matrix (WP2 checkpoint)", "",
             "Generated by `scripts/render_acceptance.py` from the same table as "
             "`docs/acceptance.json`. Status is `implemented`, `partial`, `not_started` or "
             "`blocked`. A passing test suite does not fill a row; each row names its evidence "
             "and limits.", "",
             f"Counts: {doc['counts']}", "",
             "| ID | Requirement | Status | Evidence | Class | Unresolved limits |",
             "|---|---|---|---|---|---|"]
    for r in rows:
        ev = "<br>".join(f"`{e}`" for e in r["test_evidence"]) or "—"
        lines.append(f"| {r['id']} | {r['requirement']} | **{r['status']}** | {ev} | "
                     f"{r['verification_class']} | {r['unresolved_limits'] or '—'} |")
    (ROOT / "docs" / "ACCEPTANCE.md").write_text("\n".join(lines) + "\n")
    print(doc["counts"])


if __name__ == "__main__":
    main()
