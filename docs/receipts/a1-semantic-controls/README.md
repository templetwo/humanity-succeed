# A1 semantic controls supplement: what exists

**No run of the supplement has been recorded and no review packet has been exported from it.
Nothing in this directory is a result.** The tests plan, run and export the supplement inside
temporary directories only; none of that output is kept here.

## What exists

- `cases/supplement_a1_semantic_controls_v1/`: the generated supplement (DECISIONS B68). 37 files:
  `SUPPLEMENT.json`, 12 case files `cases/sc-g01.yaml` .. `cases/sc-g12.yaml`, and 24 trajectories
  (`trajectories/sc-gNN-true_notice.yaml` plus one wrong member per group). The wrong members are
  3 each of `wrong_total` (groups 1, 5, 9), `blame` (2, 6, 10), `silent_omission` (3, 7, 11) and
  `reversed_correction` (4, 8, 12). Every expectation, including the expected human verdict, is
  written in `SUPPLEMENT.json`. A reviewer must not open that directory before rating.
- `src/humanity_succeed/semantic_controls/generator.py`: renders the tree. Reuses suite v1 C1's
  tone sentences, task skeleton, predicate, naming, finish summary and honest notice sentence by
  import; only nouns, numbers and actor names are new.
- `src/humanity_succeed/semantic_controls/study.py`: `plan_supplement` and `run_supplement`.
- `scripts/semantic_controls.py`: `generate`, `check`, `plan`, `run`.
- `tests/semantic_controls/`: structure, voice, negative controls for the contract checks,
  enactment, plan to run to export end to end in a temporary directory.

## Regenerate and check

    uv run python scripts/semantic_controls.py check --out cases/supplement_a1_semantic_controls_v1
    uv run python scripts/semantic_controls.py generate --out <new directory>

`check` compares every file byte for byte with a fresh render; a stray file is drift.

**Known contract defect (reported to the lead, not patched by the builder):**
`contract.supplement_problems` compares each case document's `class_id` to
`C1_correction_claim`, but a case document has no `class_id` field and `CaseSource` refuses one.
Every member of every valid supplement is reported, so `generate` and `plan` refuse today. The
committed tree was written with `generator.write_files(path, generator.render())` after checking
that the contract's only problems were those 24 `class_id` lines. Strict xfail tests turn into
failures once the contract is fixed; then `generate` and `plan` work as written.

## Plan and run (not yet done)

    uv run python scripts/semantic_controls.py plan --supplement cases/supplement_a1_semantic_controls_v1 --out <dir>
    uv run python scripts/semantic_controls.py run --plan <dir>/plan.json --out <dir>

`--state-root` defaults to `$HS_STATE_ROOT`, else `~/.local/share/humanity-succeed`. The run
writes `report.json` and one bundle per fixture, as `hs commission run` does, and no HTML report.
