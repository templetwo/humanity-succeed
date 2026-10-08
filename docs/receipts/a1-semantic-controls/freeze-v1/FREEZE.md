# Semantic-controls supplement v1: plan frozen, not run

`plan.json` was written by `hs controls plan --supplement cases/supplement_a1_semantic_controls_v1
--out docs/receipts/a1-semantic-controls/freeze-v1` on 2026-10-08 (UTC) from the MacBook seat, at the
commit that carries it. It binds the 37 files of the supplement by sha256, the 24 fixtures with their
mechanical AND human expectations, and the evaluator (`hs-evaluator/0.2.0`), engine, compiler and
package versions. The same command produced the same `plan_sha256` twice on different state roots,
so the plan is deterministic.

**Run on 2026-10-08 (UTC) at Anthony's word** ("add a briefing for me while blind with a link to where i can
find the final reviewable doc"): `run-v1/` beside this folder, 24 of 24 expectations met, lifecycle
`mechanically_validated`; packet `pk_bbdaab359ec8a4b9` exported (`../export.json`). The command was:

    uv run hs controls run --plan docs/receipts/a1-semantic-controls/freeze-v1/plan.json --out <dir>

refuses if any bound file has changed since this freeze, or if the evaluator or engine version differs.
