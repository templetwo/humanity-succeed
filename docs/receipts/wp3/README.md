# Receipts: WP3 development commissioning

These receipts were measured by the MacBook seat (claude-opus-5-5) at commit `8a24ad1` (`HEAD`).
The runtime source tree was clean, and the run used the committed suite
`cases/commissioning_suite_v1/`. It was a scripted instrument run: **no model was called or
trained.** The receipts are for development commissioning only; this is not formal commissioning
and not a population error bound.

| File | What it shows |
|---|---|
| `01_plan.*`, `plan/plan.json` | `hs commission plan`, exit 0. The suite validates, the split audit is clean, the partition is 120 development + 40 holdback-designate, and every fixture file is hashed. Mode is `development` and `independent_holdback=false` |
| `02_run.*`, `run/report.json`, `run/report.html`, `run/bundles/` | `hs commission run --provider scripted`, exit 0. 160 of 160 fixtures met their written expectations, and 416 of 416 mutation invariants held. `mechanical_commissioning=development_all_expectations_met`, `formal_commissioning=blocked_no_independent_holdback`, `semantic_commissioning=pending_no_human_reviews` (36 judgment-heavy fixtures), `lifecycle_state=mechanically_validated` |
| `03_sabotage.*`, `controls/sabotage_controls.py` | The same plan re-run under four deliberately broken evaluators, patched in the process only. All four were detected. This is the evidence that a clean run is not vacuous |
| `04_replay_all.json` | All 160 bundles replay as `reproduced` |

## What this does not establish

- **Formal commissioning is blocked.** No holdback custodian exists, and the 40 holdback-designate
  fixtures are builder-authored and exposed (`docs/DECISIONS.md` B48;
  `docs/HOLDBACK_CUSTODY.md`).
- **Semantic commissioning is pending.** No human has reviewed the notice texts, the decline
  reasons or any prose.
- **These fixtures are constructed, related and development-influenced.** Meeting every
  expectation says which fixtures passed, and nothing about a population (BUILD_SPEC §9).

## Coverage findings from the controls (B54)

- **F1:** The B42 notice-ordering rule is covered only by the `notice_first` mutation. No
  constructed fixture turns on it.
- **F2:** `feature_preserved` is load-bearing in only 4 fixtures.
- **F3:** Two contract formal statuses are never written into a report.

These were recorded, not patched, after the run.

Local paths are replaced with `<scratch>` in the `.cmd` files. The state root was a scratch
directory outside the repository.

Reproduce from a checkout at this commit:

```sh
uv sync --locked --group dev
uv run hs commission plan --suite cases/commissioning_suite_v1 --out /tmp/wp3-plan --state-root /tmp/wp3-state
uv run hs commission run --plan /tmp/wp3-plan --provider scripted --out /tmp/wp3-run --state-root /tmp/wp3-state
uv run python docs/receipts/wp3/controls/sabotage_controls.py /tmp/wp3-plan /tmp/wp3-state /tmp/wp3-sabotage
```
