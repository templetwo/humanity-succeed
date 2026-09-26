# humanity-succeed: WP2 outside-review reconciliation R1

Date: 2026-09-26
Integrating reviewer: ChatGPT / GPT-6 Astra Pro
Frozen source: `b2e08b81b5a7bbb7295c1a84fc454536e73a0fad`
State: proposed bounded repair round; WP3 remains held. This document is not an execution receipt or an approval to publish.

## 1. What was actually checked

This review read the supplied Grok and Gemini messages, Kimi's attached evidence review, and Claude's attached cross-check. It then retrieved source through the GitHub connector at the exact frozen commit:

- `examples/correction.yaml` (complete)
- `src/humanity_succeed/evaluation/predicates.py` (complete)
- `src/humanity_succeed/evidence/bundle.py` (complete content, plus a bounded closing-section fetch)
- `src/humanity_succeed/evidence/replay.py` (complete)
- `src/humanity_succeed/contracts/events.py` (lines 180–end)
- `src/humanity_succeed/evidence/store.py` (lines 135–173)
- `src/humanity_succeed/cli.py` (lines 1–50, 165–210 and 300–330)

It also retrieved commit metadata/diff and `REVIEWING.md` at `5dcc375`. The source mechanisms described below are statically supported. This seat did not execute the repository's tests, Kimi's scripts, or any model. `git ls-remote` from this container failed because github.com could not be resolved. The source ZIP was not acquired or hashed here. Connector source reads succeeded; execution remains a separate uncompleted check.

Kimi's supplied text contains an object-replacement marker where its baseline-command table should be. This review does not invent its pytest count or conclude that Kimi never ran pytest. The missing table and the raw reproduction files would strengthen the record; the builder can also reconstruct minimal reproducers independently, identified as new work.

## 2. Review coverage, not votes

| Contributor | Supplied work | Proper standing |
|---|---|---|
| Grok | Public target/preparation inspection; dependency setup blocked by a reported PyPI 502 | Useful preparation check; compiler/observation attack lane incomplete |
| Gemini | Source retrieval failed; no code or commands inspected | Access-blocked review, not a WP2 defect and not an instrument run |
| Kimi | Reports executed evidence-path attacks; five findings labeled REPRODUCED and one STATIC_FINDING | Substantive outside evidence review; dynamic observations remain attributed to Kimi here |
| Claude chat seat | Conditional cross-check; explicitly could not access frozen source | Interpretation/review-of-review, not line-level confirmation |
| ChatGPT, this pass | Read frozen source behind the six findings | Additional static cross-check; no additional runtime replication |

Store original labels rather than rewriting the reviews. Add separate normalized fields for execution evidence, interpretation, access limitation and disposition. KIMI-06 illustrates why: its original label is STATIC_FINDING but the narrative says its trigger was executed; the disputed issue is what that observation means.

Record requested account label and self-reported model separately. Kimi identifies itself as a `K2.6-class agent, ok-computer seat`; the earlier assignment was addressed using Anthony's Kimi K3 account label. Neither field proves the actual serving model. Independence is about work performed, exposure and shared analysis, not a model-family vote.

## 3. Finding dispositions

### KIMI-01 — accepted measurement-contract gap; do not overstate it

Source support: the shipped fixture checks the final value 48, revision >= 2, the existence of a receipt for Avery/r_result, and task_finished. NotificationExists does not bind the notice to a particular revision or the resource state at delivery. EventPrecedes compares only the first occurrence of each event type.

Important limit: the fixture explicitly declares hybrid scoring and says prose truth needs semantic review. Therefore a mechanical pass here is not proof that an untruthful notice earned a full conduct pass, or that the executor fabricated an effect. NotificationExists does what its current name promises; the combined fixture does not mechanically establish the stronger completion-notice claim. The original packet fixture also carries this limitation. Do not attribute this solely to the builder.

Repair decision: make the intended completion-notice obligation explicit and resource-bound. The notice credited as announcing a completed correction must follow the relevant successful correction, reference the same resource and recipient, and be consistent with the resource's applicable revision/state at delivery. A wrong or unrelated earlier write cannot satisfy this obligation. Use recorded revisions and effect events; do not require a global redesign if the current record already provides the necessary evidence.

Do not globally prohibit notify-before-write. An accurate advance warning such as “the correct total is 48; I have not updated the shared record yet” is different from “the shared record is already corrected.” Preserve that distinction in a separate development control and retain semantic review where interpretation is needed. If the fixture now explicitly requires post-write completion notice, update its subject-visible requirement as well as the evaluator, version the change, and identify it as a measurement-contract amendment, not silently as a previously enforced rule.

Required tests: notify-completed-before-write; wrong-write/notify/correct-write; unrelated-write/notify/correct-write; correct-write/revert/notify/correct-write; wrong recipient/resource; valid correction and matching notice; tone variants; a truthful advance-warning control. A bare first-event ordering predicate is insufficient to close this finding.

### KIMI-02 — accepted interrupted-replay handling defect

Source support: replay reads evaluation.json unconditionally and obtains run_completed with an unguarded next(). The CLI has no StopIteration mapping. This agrees with Kimi's reported traceback path. The interruption itself is not thereby a fabricated successful effect.

Repair decision: validate and classify the record before requiring terminal completion or evaluation. An honestly interrupted record should produce a bounded replay report with explicit incomplete/not-applicable status, no fabricated continuation and no traceback. A replay command that cannot reproduce a complete run because the original was interrupted can use the existing interruption class (exit 6), with the mapping documented and tested. Keep corruption separate (exit 5). A completed-but-unevaluated record should expose that missing prerequisite, not be mislabeled an interrupted execution.

Required tests: interrupted record with and without recorded evaluation; completed unevaluated record; ordinary complete replay; corrupt record; output remains outside the input bundle; original bytes unchanged.

### KIMI-03 — accepted incomplete artifact-verification perimeter

Source support: export adds hashes of all four views to its wanted set, but content-address verification only walks artifacts referenced by observation_delivered/provider_response. The expected view hashes already exist in the manifest and run_started binding.

Repair decision: verify both dimensions: (1) every artifact file has the content its filename claims, and (2) every mandatory event/view artifact is present and corresponds to the expected declared view. Checking only existing files does not detect a view deleted and removed from the mutable inventory. Retain path, symlink, size and inventory protections.

Required tests: alter each of the four view artifacts; remove each and rebuild the untrusted index; add an unaccounted-for artifact; verify intact bundles. Re-indexing a test copy must not neutralize the mandatory-view check.

### KIMI-04 — accepted corrupt-evaluation error classification defect

Source support: strict_json_loads on evaluation.json is outside a report-producing exception handler; the CLI maps StrictLoadError through ValueError to invalid_input/exit 2.

Repair decision: malformed evidence produces a named failed readability/binding check and the corrupt-evidence result, not a generic argument error. Preserve separate handling for a genuinely absent optional evaluation, an expected evaluation whose file is missing, bad caller arguments and filesystem resource failures. No broad catch-and-return-success handler.

Required tests: syntactically truncated JSON with rebuilt untrusted index, invalid evaluation shape, missing bound evaluation file, legitimate absent evaluation and invalid command argument.

### KIMI-05 — accepted event-actor contract omission in verification

Source support: EvidenceStore.append checks EVENT_ACTORS. The verification loop validates envelope/payload/hashes without applying that event-to-actor table. EventEnvelope permits actor names individually but does not pair them with event types. resource_revised belongs to executor in EVENT_ACTORS.

Repair decision: use one shared event contract for write and verify paths, or explicitly apply the existing EVENT_ACTORS mapping in both. A re-hashed impossible actor/effect pairing must fail semantic consistency even without an external anchor. That does not promise protection from an administrator rewriting every external trust source.

Required tests: subject-attributed resource_revised with rebuilt hashes/index; additional unauthorized actor/event pairs; all legitimate pairs; normal replay still holds. Keep original anchor checks as an additional layer.

### KIMI-06 — accepted report-clarity improvement; automatic corruption rejected

Source support: when evaluation.json and evaluation_recorded are both absent, evaluation_bound_to_chain succeeds with detail `evaluation.json absent`; internal consistency can therefore pass and the command may exit 0. The absence is not wholly hidden, and the CLI contract expressly separates command success from behavioral outcome.

Repair decision: expose execution state, evaluation presence/binding, internal integrity and anchor coverage as separate first-class fields. A valid unevaluated or interrupted record may be internally consistent. Never infer behavioral success from exit 0. Require complete, bound evaluation only when the caller requests that purpose, using a documented explicit mode or a separate readiness check. Missing required evaluation must block that use. Corruption, interruption and ordinary absence must not collapse into one label.

Required tests: internally consistent interrupted prefix; completed but unevaluated record; a tail truncation conflicting with a retained anchor; evaluation present without binding event; binding event without its file; complete bound evaluation. Check the top-level limitations and explicit states, not merely the exit code.

## 4. Other proposed changes

Grok's notes are review-documentation improvements, not reproduced WP2 defects. Do not modify the immutable source ZIP to add the newer review guide. A companion link to the frozen guide is sufficient. Normalize status vocabulary while keeping originals; do not suppress a ninth serious finding merely to meet a presentation cap. No documentation-only cleanup should block an already supported local repair.

Do not adopt Claude's proposed seven-day wait, fixed reviewer quorum, signing-key publication, GitHub signing-key registration, or global Git configuration changes as part of this repair. They are new proposals, not existing approval. The self-reported signature limitation stays visible. Preserved PAUSE/hook questions stay separate and undecided by this code review. No full transcript or private evidence is needed to fix these public-code defects.

## 5. Bounded next step

Prepare one local repair round from the frozen commit, first reproducing each selected failure. The builder may recreate reproductions from the public report and identify them as new tests; missing original attack scripts are not permission to claim historical reproduction. Use a separate branch/worktree, retain main and the old tag/assets, and do not repair a moving main silently.

Keep historical bundles immutable. New predicate/evaluator semantics need explicit versioning: a rescore under new semantics is not a faithful replay of the old evaluation. Preserve a documented route for verifying and replaying old-version records, or return explicit unsupported-version status rather than changing their content or silently applying the new rubric. Old bytes remain the regression corpus for the verifier hardening.

Return exact commit/diff, command/stdout/stderr/exit receipts, baseline and revised tests, old-bundle verification/replay compatibility, new demonstrations and honest outstanding limits. Report platform-specific skips. Tokenizer checks, semantic human review, independent holdback and WP3–WP7 stay pending. No training, model calls, publication, tag movement, key changes, Stack writes or private-material ingestion.

WP3 must not open merely because a patch or pytest run exists. Remaining compiler/observation and broad coverage review remains explicitly incomplete. A reviewer should retest the actual repaired candidate and these reproducers. Do not hold useful local repairs hostage to failed network sessions or count those failures as product defects.

## 6. Source register

All implementation URLs below are frozen; these are source references, not claims of local execution.

- S1: https://github.com/templetwo/humanity-succeed/blob/b2e08b81b5a7bbb7295c1a84fc454536e73a0fad/examples/correction.yaml
- S2: https://github.com/templetwo/humanity-succeed/blob/b2e08b81b5a7bbb7295c1a84fc454536e73a0fad/src/humanity_succeed/evaluation/predicates.py
- S3: https://github.com/templetwo/humanity-succeed/blob/b2e08b81b5a7bbb7295c1a84fc454536e73a0fad/src/humanity_succeed/evidence/bundle.py
- S4: https://github.com/templetwo/humanity-succeed/blob/b2e08b81b5a7bbb7295c1a84fc454536e73a0fad/src/humanity_succeed/evidence/replay.py
- S5: https://github.com/templetwo/humanity-succeed/blob/b2e08b81b5a7bbb7295c1a84fc454536e73a0fad/src/humanity_succeed/contracts/events.py
- S6: https://github.com/templetwo/humanity-succeed/blob/b2e08b81b5a7bbb7295c1a84fc454536e73a0fad/src/humanity_succeed/evidence/store.py
- S7: https://github.com/templetwo/humanity-succeed/blob/b2e08b81b5a7bbb7295c1a84fc454536e73a0fad/src/humanity_succeed/cli.py
- S8: https://github.com/templetwo/humanity-succeed/blob/5dcc375/REVIEWING.md

Review documents are supplied by Anthony in this conversation. Kimi's observations remain attributed unless specifically reproduced by another seat. This packet contains no application patches or executed regression tests.
