# Semantic-controls supplement v1: plan frozen, not run

`plan.json` was written by `hs controls plan --supplement cases/supplement_a1_semantic_controls_v1
--out docs/receipts/a1-semantic-controls/freeze-v1` on 2026-10-08 (UTC) from the MacBook seat, at the
commit that carries it. It binds the 37 files of the supplement by sha256, the 24 fixtures with their
mechanical AND human expectations, and the evaluator (`hs-evaluator/0.2.0`), engine, compiler and
package versions. The same command produced the same `plan_sha256` twice on different state roots,
so the plan is deterministic.

**No run has been made against this plan and no packet with controls has been exported.** Anthony
sees the supplement before anything runs (`docs/audits/2026-10-08_five_questions_plain_words.md`:
"shows you before anything runs"). The run, when he says so:

    uv run hs controls run --plan docs/receipts/a1-semantic-controls/freeze-v1/plan.json --out <dir>

refuses if any bound file has changed since this freeze, or if the evaluator or engine version differs.
