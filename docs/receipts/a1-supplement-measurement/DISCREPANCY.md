# Retained first-run discrepancy and report-only correction

First-run evidence commit: `f98ee823083e4f57e7080d21b304340c11c2d03a`.
Execution source freeze: `2da21832f8584bacb0443a40832fb1ce05e2d499`.
Original source/generator: `60d226f8ff50135d332c000b094cba149b49326a`.
Original plan SHA-256: `68aaae8f3e12103cc66e5868453315c0c181bb094266751b8e2a6c06ff2c38d3`.

The first run returned command exit 1 and reported 48/60 expectation matches,
with the 12 qualified IDs in its discrepancies list. Inspection shows all 60
bound mechanical and conduct evaluations actually match the frozen expectations.
All bundles verify against their anchors and all 60 faithful replays reproduce.

The 12 errors occur after execution, evaluation, export, verification and replay:
`StrictLoadError: non_json_type: tuple is not a JSON value`. The reviewer material
attempted canonical serialization of `subject_view(case).model_dump()`; Python
mode retains tuple-valued handles/tools. The wrapper then overwrote completed
execution status with failed/incomplete and set expectation_match false. This is
a supplement presentation defect, not a fixture, authored expectation, execution,
or B57/B58 evaluator defect. Original raw records correctly report completed runs.

The correction serializes the view with `mode="json"` and prevents a subsequent
presentation failure from replacing execution facts. A separately versioned
`hs-a1-supplement-report/2` is exported under a committed report-only freeze.
It rechecks the retained anchors and reads the bound evaluations/visible traces;
it invokes no evaluator, execution or replay. No case, declaration, predicate,
grid criterion, expected outcome, evaluator implementation or version changes.
The original report, progress rows, plan, bundles and replay reports remain intact.

The repaired source must fail original plan preflight as post-freeze drift.
The new report freeze binds the repair source, original plan, complete first-run
inventory, unchanged corpus and blank grid. This preserves exactly 60 planned
and completed study executions rather than creating a second study sample to
repair presentation. The 12 human verdicts remain blank in both versions.
