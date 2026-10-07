# Review-slice test coverage extension (cloud seat, 2026-10-07)

Spawned by the parent audit session for Anthony, on top of
`docs/audits/2026-10-07_human_side_audit_a1_review.md` at `17860e0` (branch
`audit/a1-human-side-2026-10-07`). This extends that audit; it does not repeat it.

**Model called: no. Stack read or write: no. Human rating written: no. `src/` edited: no. Existing
test edited: no. `cases/`, `docs/receipts/`, `docs/DECISIONS.md` edited: no.** Every state root in
the new tests is under `tmp_path`. All ratings are synthetic under obviously fake references.

## What was added

| File | Tests | Purpose |
|---|---|---|
| `tests/review/test_coverage_cloud.py` | 48 | module-level gaps in export, leak, html, importer, status, ledger, contract, agreement |
| `tests/integration/test_cli_review_cloud.py` | 12 | `hs review` paths with no end-to-end test |
| `tests/golden/test_freeze_scope_cloud.py` | 6 | what the stage-0 freeze pins and does not; the review-source freeze |
| `tests/golden/capture_suite_v1_review_source.py` | – | measures the new baseline (same style as `capture_suite_v1_observed.py`) |
| `tests/golden/suite_v1_review_source.json` | – | the measured baseline, 36 fixtures, two hashes each |

66 tests. Full suite before: 677 passed, 2 skipped (239 s). After: see the final message of the
session and the PR; `uv run ruff check src tests scripts` clean. No test was marked `xfail` or
`skip`; `docs/audits/cloud/review-tests/failing/` was not created because no test failed for a
code reason (see "Defects" below).

## 1. Gaps found and which test closes each

### Tests that passed for the wrong reason, or would have

| # | Gap | Closed by |
|---|---|---|
| G1 | `test_real_run_export_has_zero_leak_hits_and_is_static` recomputes the forbidden set in the test and asserts zero hits. It passes unchanged if `forbidden_tokens` returns an empty set, and it never checks the set `export_packet` itself scans with. | `test_real_export_scans_with_a_forbidden_set_that_names_every_id_and_vocabulary_category`: spies on `leak.leak_check` during a real export, asserts the captured set holds every fixture/class/group id in `report.json`, all 36 bundle `case_id`s, the bare vocabulary, the quoted-only vocabulary (and that the bare forms are absent), every registered predicate op; then plants one token per category into the real packet text and watches the scan fire. |
| G2 | A new leaking field whose text is free prose (no id, no field name) is not caught by the token scan. This run's `expected.rationale` strings all happen to contain `pass_if`, so a test on them would pass by luck. | `test_free_prose_from_report_json_is_outside_the_token_scan_so_the_packet_is_checked_by_field` measures the limit (an injected prose sentence exports `ok`). `test_every_packet_field_is_traceable_to_its_verified_bundle_and_no_report_prose_is_present` is the actual guard: every item field is recomputed from `case_source.json` and `events.jsonl` and compared; every `expected.rationale` sentence and every report-row JSON label is asserted absent from both `packet.json` and `index.html`. |
| G3 | The existing A19 negative control injects a fixture id, which the id set catches; nothing tested that the packet content is a function of the bundles alone. | same as G2 (field-level parity). |
| G4 | The HTML was only checked for the absence of `http`/`<script` and the presence of one notice text. Nothing checked that every manifest string is on the page, or that the page carries nothing the manifest does not. | `test_real_export_html_shows_everything_in_packet_json_and_nothing_more` parses `index.html`, strips `<style>`, and requires the multiset of non-static text runs to equal exactly the runs derived from the manifest, in order, plus the `h2` ids. `test_the_parity_checker_itself_notices_a_dropped_or_added_item` is the positive control on the checker. `test_hostile_strings_render_escaped_and_round_trip_exactly` covers escaping (`<script>`, `&`, quotes, non-ASCII, `&middot;`, `</pre>`) and the omitted resources card; `test_a_step_without_a_message_renders_the_none_marker_not_an_empty_cell` covers the `none` marker. |

### Export behaviours with no test

| # | Behaviour | Closed by |
|---|---|---|
| G5 | Item order (`sha256_obj([packet_id, item_id])`) and key-entry order; `order_note` text | `test_items_and_key_entries_are_ordered_by_sha256_of_packet_id_and_item_id` (also asserts the hash order differs from lexicographic order for the packet it made, so the sort is observable) |
| G6 | `created_from.run_report_sha256` = sha256 of `report.json`; `plan_sha256` copied; key and template `packet_sha256` = sha256 of `packet.json` bytes; export dir holds exactly three files | `test_created_from_key_and_template_hashes_bind_the_packet_to_its_run_and_bytes` |
| G7 | `visible_resources` are initial values even when the subject revised the resource | `test_visible_resources_are_initial_values_even_when_the_subject_revised_them` |
| G8 | `task_finished` outcome text (present in all 36 bundles, never asserted) | `test_task_finished_outcome_carries_the_subject_summary` |
| G9 | `_outcome` branches `allowed but not applied: <result>`, `clock advanced ... nothing new was observed`, `awaiting input` | `test_revision_conflict_empty_wait_and_awaiting_input_outcomes_are_named` (bundle built through the real engine) |
| G10 | A bundle directory named in `report.json` that does not exist | `test_missing_bundle_directory_is_blocked_input_naming_the_fixture_and_writes_nothing` |
| G11 | A run with no judgment-heavy fixture | `test_run_with_no_judgment_heavy_fixture_writes_nothing` (pins current behaviour; see D1) |
| G12 | A rubric edit in a bundle copy | `test_a_copy_of_the_run_with_one_rubric_word_changed_is_refused_at_export` |
| G13 | Audit F10 (a re-export is a different packet) was stated, never tested | `test_ratings_bound_to_one_export_cannot_be_imported_against_a_re_export` |

### Importer refusals with no test

| # | Behaviour | Closed by |
|---|---|---|
| G14 | unreadable packet path; packet bytes that are not a manifest | `test_unreadable_or_invalid_packet_is_refused_not_raised` |
| G15 | verdict `PASS`/`True`, `reviewer_kind` `bot`, an extra field, empty `ratings`, `packet_id` mismatch | `test_malformed_ratings_documents_are_refused_with_nothing_recorded` (parametrised) |
| G16 | missing ratings path; unparseable YAML | `test_unreadable_and_unparseable_ratings_files_are_refused` |
| G17 | key `packet_id` mismatch; corrupt key bytes; key missing an item's entry | `test_operator_key_with_wrong_packet_id_corrupt_bytes_or_a_missing_item_is_refused` |
| G18 | several problems in one file are all named, count exact | `test_every_problem_in_a_file_is_named_together_and_nothing_is_recorded` |
| G19 | identity collision check is ledger-wide across `reviewer_kind` | `test_reviewer_identity_is_ledger_wide_across_reviewer_kinds` |
| G20 | the HOWTO's partial-progress procedure (audit F06) at the CLI | `test_partial_template_round_trip_as_the_howto_describes_it` |
| G21 | model ratings through the CLI (audit §4 measured it by hand) | `test_model_ratings_through_the_cli_are_secondary_and_leave_status_pending` |

### Status paths with no test

| # | Behaviour | Closed by |
|---|---|---|
| G22 | another packet's records never count | `test_records_of_another_packet_never_count_for_this_one` |
| G23 | two humans with disjoint coverage: single-reviewer, reason named | `test_two_humans_who_never_overlap_are_not_independent_review` |
| G24 | two humans with partial overlap: status single, label kept, agreement over the shared items only | `test_partial_overlap_keeps_the_single_reviewer_label_and_scores_only_the_shared_items` |
| G25 | three reviewers: the pair with the largest overlap is scored | `test_three_reviewers_the_pair_with_the_largest_overlap_is_scored` |
| G26 | two rubric dimensions scored separately | `test_two_rubric_dimensions_are_scored_separately` |
| G27 | a human record with `counts_as_vote: false` is not coverage | `test_a_human_record_marked_not_a_vote_is_excluded_from_coverage` |
| G28 | packet path as file vs directory | `test_status_accepts_the_packet_json_file_as_well_as_its_directory` |
| G29 | partial import on the real packet counts only rated items | `test_status_of_a_real_export_with_a_partial_import_counts_only_the_rated_items` |

### Ledger, contract, agreement, CLI

| # | Behaviour | Closed by |
|---|---|---|
| G30 | missing ledger reads `[]`; appending nothing creates nothing; blank lines skipped; packet filter; canonical round trip | `test_ledger_reads_nothing_from_a_missing_file_and_appending_nothing_creates_nothing`, `test_ledger_round_trips_canonically_skips_blank_lines_and_filters_by_packet` |
| G31 | a well-formed JSON line that is not a record is corruption naming its line, filter or not | `test_a_well_formed_json_line_that_is_not_a_record_is_corruption_naming_its_line` |
| G32 | `Rating`, `ReviewRecord`, `RatingsFile` strictness (patterns, literals, coerced types, extra fields, schema id, min one rating) | `test_rating_rows_are_validated_strictly`, `test_review_record_refuses_coerced_types_and_an_unknown_kind`, `test_ratings_file_schema_pins_its_schema_id_and_requires_a_rating` |
| G33 | `agreement_between_reviewers` is exactly `agreement()` plus the pair (dict equality, with `None` ratings) | `test_agreement_between_reviewers_is_exactly_agreement_plus_the_reviewer_pair` |
| G34 | audit §2's arithmetic (all-pass packet: kappa undefined; one disagreement: 0.0) | `test_an_all_pass_packet_has_undefined_kappa_by_construction` |
| G35 | CLI: export envelope (artifacts, limitations, key path outside the packet); default state root from `HS_STATE_ROOT`; `blocked_leak` exit 3 with nothing written; missing ratings file; corrupt ledger exit 2 `invalid_input`; missing packet; required arguments | the remaining tests in `tests/integration/test_cli_review_cloud.py` |

## 2. Defects and observations

No test written here failed because the code is wrong. Three observations, none a correctness
defect in the slice the reviewer uses:

**D1 (low). A run with no judgment-heavy fixture raises instead of returning `blocked_input`.**
`PacketManifest.items` has `min_length=1`, so `export_packet` raises pydantic's `ValidationError`
before the leak check; the CLI maps it (a `ValueError`) to `invalid_input`, exit 2, with nothing
written. Nothing is simulated and nothing is written, so this is a rough edge, not a safeguard
failure. Proposed minimal fix in `review/export.py`, after `rows = _judgment_heavy_rows(report)`:
`if not rows: return {"status": "blocked_input", "packet_id": None, "items": 0, "problems":
["report.json names no judgment-heavy fixture; nothing to review"], "paths": {}}`.
`test_run_with_no_judgment_heavy_fixture_writes_nothing` pins today's behaviour (raises, writes
nothing) and will need its `pytest.raises` replaced by a status assertion if D1 is taken.

**D2 (low, not pinned). `rated_at_utc` accepts a date without a time.** `datetime.fromisoformat`
accepts `2026-10-07`, so the importer's ISO 8601 check (audit F09) admits a bare date. Harmless for
the record (the string is stored as typed) and not pinned here so the check can be tightened
without touching a test. If tightened: require `T` and a zone designator, or `datetime` with
`tzinfo` not `None`.

**D3 (documentation). Partial overlap emits an agreement block under the single-reviewer label.**
When two distinct humans both cover some items but not all, `review_status` reports
`single_reviewer_reviewed`, keeps the `single-reviewer` label, and still emits `agreement` over the
shared items (G24 pins it). This is consistent with `review/contract.py` ("ONLY when two distinct
humans rated the same items") and with "no agreement statistic is computed from one reviewer", but
a reader of the status JSON could take the block for an independent-review result.
`docs/REVIEW_PACKET_HOWTO.md` could say so in one sentence. Not changed here (docs were out of
scope for this seat).

Also measured and recorded, not a defect: a group id is a prefix of its fixture ids
(`c1-g01` of `c1-g01-real_correction`), so a planted fixture id produces two hits; the leak scan
is a substring scan and says so.

## 3. The stage-0 golden freeze: what it pins and what it does not

`tests/golden/test_suite_v1_observed_freeze.py` re-executes all 160 suite v1 trajectories and
compares, per fixture, exactly four values: `mechanical`, `conduct`, `contained`,
`evaluator_version`. Measured here (`test_observed_freeze_scope_is_the_four_verdict_fields_only`).

Not caught by it:

- **Rubric text, task text, world values, predicates, scope limitations.** None of these change a
  verdict when edited consistently. `test_a_rubric_edit_is_invisible_to_the_observed_freeze_and_visible_here`
  shows one rubric word changed yields the same four values.
- **Event payload changes.** The freeze keeps only the verdict derived from the events; a change to
  what a step records (a notice text, a revision number, a summary) with the same verdict passes.
- **Bundle bytes and hashes.** The committed bundles under `docs/receipts/wp3/run` are
  self-verified by `verify_bundle` wherever they are opened (the export tests open the 36
  judgment-heavy ones), but no golden test pins their digests, and the 124 other bundles are not
  opened by any test.
- **Which fixtures are judgment-heavy.** The set comes from `SUITE.json`/`report.json`
  `expected.judgment_heavy`, which the observed freeze does not read.

Other golden coverage of suite v1: none for event streams or case hashes.
`test_wp3_stage0_freeze.py` pins stable event streams and evaluation digests for the 24 dev
trajectories and the compiled tree of `examples` + `commissioning_dev`, not suite v1.
`tests/commissioning/test_suite_v1.py::test_committed_suite_matches_its_generators` pins the suite
YAML to the generator code, so an edit in `cases/` alone is caught, but an edit made in
`suite_v1/*.py` and regenerated is not, by any test, until now.

### The freeze added here

`tests/golden/suite_v1_review_source.json` (schema `hs-suite-v1-review-source/1`), measured by
`capture_suite_v1_review_source.py` from the committed run's bundle copies of the 36 judgment-heavy
cases, pins per fixture:

- `review_source_sha256`: the hash every review record cites (case document minus `reviews`:
  task, world, evaluation with rubric and predicates, provenance, limitations). All 36 are distinct.
- `stable_events_sha256`: the stable event stream the fixture's suite trajectory re-executes to,
  with `evidence.replay._stable` applied (same construction as the WP3 stage-0 freeze). This is
  what the packet's recorded sequence is built from.

Tests: the measurement matches the baseline; the live suite YAML hashes to the same 36
review-source values (so bundle copies and suite source agree, measured: 36 of 36); the 36 are
exactly the observed freeze's `pending_review` + `pass` fixtures (audit F02 as arithmetic); a
rubric edit moves the review-source hash while the observed freeze stays blind; a forged baseline
is noticed. Cost: 36 in-memory runs, about one second.

Not added, proposed: a digest freeze of the 160 committed bundles' `bundle.json` recorded hashes
(cheap, reads only) if the custody of `docs/receipts/wp3/run` is ever to be asserted by a test
rather than by `SHA256SUMS` alone; and widening `stable_events_sha256` to all 160 fixtures (about
four seconds) if the dev-only WP3 freeze is felt to leave the 124 mechanical fixtures' event streams
unpinned. Either needs the parent's word on scope; neither changes behaviour.

## 4. HTML/JSON parity and the template round trip

Parity holds on the real export: every text run on `index.html` outside the fixed labels is a
string the manifest carries, in manifest order, and every manifest-derived string appears; item ids
are the `h2` anchors in order; no script, no URL. The page's fixed chrome is the title, the banner
sentence, the card labels and column headers, and the `none` marker. The only content the page
carries that `packet.json` does not is that chrome and the inlined replay stylesheet.

Template round trip at the CLI, 36 rows: half filled is refused whole with nothing recorded; the
same 18 rows alone record 18 votes and read `single_reviewer_partial` with 18 covered items; the
other 18 later under the same reference complete the review, 36 ledger lines all revision 1,
18 `pass` and 18 `fail` where typed.

## 5. Boundaries kept

Read-only against `src/` and existing tests; new files only. No Stack heartbeat was made: the
spawn instruction forbids Stack writes and the user preference marks grounding as optional, so no
external call was made at all. No model was called. Nothing under `cases/`, `docs/receipts/`,
`docs/DECISIONS.md` or any frozen artifact was touched. State roots only under `tmp_path`.
