# B57/B58 offline local acceptance

**B57/B58 implemented and mechanically verified for the recorded development scope.**
This is scripted instrument development. No human review is recorded; the instrument is not
labelled formally commissioned. No subject model was selected, loaded, called, or trained.

## Identity and representation

- Starting main and available remote head: `3f304a14da78ef29165254a574d2f015aecd7d20`.
- Original checkout was clean on main. Its four existing additional worktrees were preserved.
- Isolated branch: `a1/measurement-v030`.
- Tested code commit: `fede45e3a9a749318e9415c1f071c3d996c22882`.
- Final receipt commit is separate and contains only this packet and the appended implementation
  facts in DECISIONS. Resolve its exact identity with
  `git log -1 --format=%H -- docs/receipts/a1-measurement-v030`; it is also in the builder return.
  A commit cannot embed its own final hash. The tested source remains identical to the code commit.
- Tested runtime: CPython 3.11.15, Pydantic 2.13.5, macOS arm64, dependencies from unchanged `uv.lock`.

`code-files-changed.txt` lists the 24 code/documentation/test/schema files in the implementation
commit. `acceptance.json` supplies the machine-readable command results and requirement mapping.
The receipt adds logs, JUnit summaries, the example, preservation results and an inventory of hashes.

The representation is the optional `evaluation.a1_evidence` object with explicit
`schema_id: hs-a1-evidence/1`, nonempty findings, stable unique `finding_id`, finding text, and one
of the four authored statuses. Strict Pydantic ingestion checks ID uniqueness; implementation JSON
Schema validates shape. The packet schemas and their packaged copies remain unchanged. Absence
stays absent in legacy case dumps, evaluator views and old evaluations.

0.3.0 requires `guard_withheld` and `model_abstained` lists with exact event references. The lists
are nonexclusive and contain facts only. The declarations are evaluator-only and never inferred.
Mechanical/conduct logic, execution/missingness semantics, and pending human review remain separate.
The global default stays 0.2.0; new scripted runs and compiler replay can explicitly select 0.3.0.
See [the contract](../../A1_MEASUREMENT_V030.md) for field meanings and compatibility details.

## Requirement-to-test mapping

All named tests below are in `tests/integration/test_a1_measurement.py` unless another file is given.
Fixtures are clearly invented engineering development material, outside the frozen suite.

| Requirement | Evidence |
|---|---|
| Four strict authored statuses; malformed declarations, duplicate finding IDs and unknown fields rejected | `test_declared_statuses_strictly_accepted`, `test_malformed_declarations_refused`; packet identity and generated schema tests in `tests/unit/test_contracts.py` |
| Older evaluator versions explicitly refuse A1 metadata | `test_older_versions_refuse_metadata_before_execution_or_compilation`; CLI default refusal test |
| Declarations isolated from subject/provider/training messages | `test_declarations_do_not_change_observations_or_conduct_or_judgments`, `test_canaries_and_positive_leak_controls_in_provider_and_training`; direct SFT-prefix rows are nonempty; actual compile remains unreviewed and supplies no eligible training rows |
| Guard-only, executed-decline-only, both, neither with trace refs | `test_separate_facts_with_exact_references` |
| Denied decline and prose-only decline are not executed abstention | `test_denied_decline_is_only_guard_withholding`; prose-only finish in the guard/neither cases |
| Silence, script exhaustion, permitted-unexecuted interruption do not imply abstention | `test_silence_exhaustion_and_interruption_are_not_abstention` |
| Authored evidence status does not change conduct or create grid/human judgment | `test_declarations_do_not_change_observations_or_conduct_or_judgments` |
| Selected version binds manifest, evaluation event, exported bundle, verification and faithful replay | `test_manifest_evaluation_binding_export_and_replay_agree`, `test_inconsistent_evaluation_version_refused`, CLI selection test; `example/` |
| Required new fields, malformed fields, changed declarations, references and version mismatches fail validation | `test_rehashed_invalid_v030_evidence_fails_validation` (11 mutations) |
| Rehashed, well-shaped conduct forgery detected by anchor and replay | `test_retained_anchor_and_replay_detect_rehashed_semantic_tampering` |
| No invented declaration on a legacy case, even with explicit 0.3.0 | `test_absence_stays_absent_in_legacy_serialization`, `test_explicit_v030_on_legacy_case_adds_facts_not_inferred_declarations` |
| Missing evaluation remains missing; unsupported evaluator remains explicit | `test_complete_v030_run_without_evaluation_replays_events_only`; existing B43 unsupported-version and incomplete-run tests in `tests/integration/test_wp2_repair_r1.py` |
| Historical verdict/evaluation/event/compiler digests unchanged | `tests/golden/test_wp3_stage0_freeze.py`, `tests/golden/test_suite_v1_observed_freeze.py`; `legacy.json` checks frozen paths against the starting commit |
| All old committed bundles verify/replay under their recorded version | `legacy.json`: 30 WP2 (0.1.0) and 160 WP3 (0.2.0), each file set unchanged; WP2 retained anchors verified |

## Exact commands and results

Commands ran from the isolated worktree except the reference-main mypy comparison. All core
checks ran offline without a model or network dependency. `.venv` was created by `uv sync --locked`
(exit 0, 26 packages installed). Full commands, exit codes, test totals, elapsed times and SHA-256
values are in `acceptance.json`; raw logs and JUnit are in `checks/`.

```sh
.venv/bin/python -m pytest -q tests/integration/test_a1_measurement.py --junitxml=docs/receipts/a1-measurement-v030/checks/a1.xml
.venv/bin/python -m pytest -q --junitxml=docs/receipts/a1-measurement-v030/checks/offline.xml
.venv/bin/python scripts/export_schemas.py --check
.venv/bin/ruff check src tests scripts
git diff --check
.venv/bin/python scripts/build_a1_measurement_example.py --out docs/receipts/a1-measurement-v030/example --state-root /private/tmp/hs-a1-example-state-fede45e
.venv/bin/python scripts/check_a1_legacy.py --out /private/tmp/hs-a1-legacy-fede45e
.venv/bin/mypy --no-incremental src
```

The A1 targeted suite passes 45 tests. The final full offline regression passes **684 tests**, with
zero failures, errors or skips (198.31 seconds). The results are recorded in `checks/offline.log`,
`checks/offline.xml` and `acceptance.json`.
Generated-schema comparison, Ruff and diff checks pass. The example verifies against its local
retained anchor and faithfully replays. All 190 historical bundles verify/replay without mutation.

**Additional type-check failure, retained:** mypy exits 1 with 40 errors in both the implementation
and reference main. Using the same installed mypy against untouched main reproduces exactly the
same errors after removing line-number shifts, with zero new errors (`checks/mypy-comparison.json`).
The two raw logs are retained. Those pre-existing type/stub issues were not broadened into this bound.

Development failures were resolved before the tested commit: the first schema export used the
wrong location for the packet's inline evaluation schema; test collection caught an invalid HTML
f-string and a misnamed test helper import; the historical evaluator-version assertion assumed
newest supported = default (118 passes/1 failure). The updated assertion visibly preserves the
historical 0.2.0 default and permits explicit 0.3.0. No golden was regenerated. A sandboxed uv run
exited 101 in macOS system-configuration access; the escalated rerun reached test collection,
and final verification used the locked environment's `.venv/bin/python` directly. The pre-final
full regression run passed 683 tests; the final commit adds one additional A1 optional-extension test.

## Example and historical preservation

The example is a read, forbidden write (guard denied), then executed decline. Both factual lists
are present. The conduct outcome is **fail**, because the authored forbidden-write criterion
still holds. Semantic review has zero received reviews and remains pending. This is neither a
claim that the decline was justified nor a human-reviewed judgment.

`example/bundle/manifest.json` identifies the clean tested code commit and 0.3.0.
`example/bundle/evaluation.json` is bound by the final `evaluation_recorded` event.
`example/verification.json` and `example/replay/replay.json` report consistent, locally anchored,
faithfully reproduced evidence. `example/example.json` lists the artifact hashes; `SHA256SUMS`
covers this acceptance packet. The retained anchor is local, not independent custody or publication.

`legacy.json` records each historical bundle's recorded version, verification, anchor status,
faithful replay details, evaluation/events digests and before/after file equality. Its frozen-path
diff against `3f304a1` is empty. Both frozen golden hashes are retained there. No original WP2/WP3
bundle, report, plan, receipt, frozen suite case or expectation was modified.

## Remaining limits and next dependency

These checks establish instrument behavior only for the constructed development scope. Declared
evidence status is case-authored, not independently certified. Leakage lint is a mechanical check,
not semantic proof. No reviewer grid, qualification assessment or reviewer verdict was produced.
The existing 40 mypy errors remain. Formal commissioning and semantic review are not established.

B59's approved, separately frozen **12-group / 60-trajectory** supplement remains the next bounded
build. This packet does not construct it or rescind its approval. Private review import, operator
keys, protected Chronicle, holdbacks/custody, model work, integration, Stack writes, push, merge,
publication and release are outside this return. Study conditions, contrasts and thresholds are unchanged.
