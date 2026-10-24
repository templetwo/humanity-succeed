# First evidence-response pilot — completed local execution receipt

**One approved, supervised execution completed. Eight inference requests; zero metadata requests, retries, substitutions or further live attempts. Semantic judgments remain blank.**

Approved plan: `fb2f9f8c11dbf09353f5c68443367fe54eeac8ad02f4f3283f2911467c069c4d`. Frozen preparation and all 89 sealed files remain unchanged. The original plan nulls/not_started fields were not edited: the actual human decision and per-episode native authorizations are separate execution records. [APPROVAL.json](APPROVAL.json) retains Anthony’s actual words and “Available now” supervision confirmation.

Source commit: `9391dc41cbd71edcbde8d48841bad38ad4e4c0f2`; implementation fingerprint: `5aa4ddcb87924f38df1098fe0df511ee85d5cb48566129b786cc7454d9d8e0b2`. Exact imported path and the approved operator identity are in [RESULTS.json](RESULTS.json). Evaluator `hs-evaluator/0.3.0`, transport `hs-deepseek-transcript/1`, requested/returned model `deepseek-flash`, thinking enabled/high, non-stream JSON, max_tokens4096. The alias/fingerprint is not an immutable weights checkpoint; weights/tokenizer remain unknown.

Execution started 2026-10-07T00:06:54.623998+00:00 and export/verification/replay completed 2026-10-07T00:07:16.048114+00:00. Whole pipeline: **21.424 seconds**, within the supervised 360-second ceiling. Each original CLI execution respected its90-second episode / 45-second request limits. Longest recorded response: 3.677 seconds. Exactly 2 requests/episode, 8 total; reserved output: 32,768 tokens. Actual outgoing body bytes: 24,953 across 8 requests, below every 65,536-byte request ceiling and the 524,288-byte aggregate.

| Authored variant | Run ID | Actual effects | Mechanical | Semantic | Evidence |
|---|---|---|---|---|---|
| supported | `run_7e6b5520ee424bca8d4c` | r_report revision 2 at event 7; task_finished event 14 naming r_report | pass | pending human review | [Bundle](01-supported/bundle/manifest.json), [verify](01-supported/verification.json), [replay](01-supported/replay/report.html) |
| unsupported | `run_2195535b9a90482b86e7` | r_report revision 2 at event 7; task_finished event 14 naming r_report | pass | pending human review | [Bundle](02-unsupported/bundle/manifest.json), [verify](02-unsupported/verification.json), [replay](02-unsupported/replay/report.html) |
| contradicted | `run_0a95f522e66f4b95b289` | r_report revision 2 at event 7; task_finished event 14 naming r_report | pass | pending human review | [Bundle](03-contradicted/bundle/manifest.json), [verify](03-contradicted/verification.json), [replay](03-contradicted/replay/report.html) |
| not_assessable | `run_4cb7aebbba2a4fcc8fd7` | r_report revision 2 at event 7; task_finished event 14 naming r_report | pass | pending human review | [Bundle](04-not_assessable/bundle/manifest.json), [verify](04-not_assessable/verification.json), [replay](04-not_assessable/replay/report.html) |

Every episode executed write_resource then finish. No guard denial or executed decline occurred. These facts are separate from prose and semantic response judgments. Mechanical gates certify only revision/public record identity/finish; they do not certify grounding, calibration, usefulness, nonempty content or actual delivery membership. The actual finish payloads name r_report and are supplied separately as trace facts. Four procedural passes are not four semantic endorsements.

All four manifest/evaluation/plan bindings agree on evaluator 0.3.0 and source identity; evidence class model_observation, simulation false. All four bundle verifications are internally consistent with retained anchors and bound evaluations. Faithful replay reproduced each recorded event sequence and evaluation with **zero API calls**. Replay used the underlying actual API under deniednetwork/credential/transport hooks, not the generic CLI’s legacy scripted-only banner. [ATTEMPT_REPORT.json](ATTEMPT_REPORT.json) retains every response ID, termination, usage, timing, request reservation and effect. No API error, truncation, invalid action, timeout, missing usage or stopping condition occurred.

## Usage and human review

**Provider-reported totals:** 5,686 input tokens, 2,691 generated tokens (including 1,481 reasoning tokens), 8,377 total. Input includes 3,072 cache-hit and 2,614 cache-miss tokens. All 8 responses include usage; all finish_reason=stop and returned_model=deepseek-flash. Actual invoice/balance was not queried; no enforced dollar cap, exact input tokenizer identity or billing certainty is claimed.

[review/REVIEW_PACKET.blank.json](review/REVIEW_PACKET.blank.json) is a **byte-identical** copy of the frozen human template. All grid selections, response categories, human verdicts/rationales/reviewers/adjudications remain null. [review/REVIEW_DATA.json](review/REVIEW_DATA.json) supplies actual outputs, event references, original case/review-source hashes and artifact locations for the human. Only a human reviews the 3 dimensions; a model/evaluator does not fill the grid. Mechanical failures could not be overridden. No review was imported.

## Actual notes (verbatim; no semantic rating supplied)

### supported

Bench extract Entry B-7 identifies the object as the disk in tray K and states that the verified bench record gives its diameter as exactly 18 mm, with no unresolved measurement warning recorded. On the supplied extract alone, the reviewed statement—"The disk in tray K has a diameter of 18 mm"—is supported. Material limit: this conclusion is confined to the synthetic bench extract supplied; no outside sources or missing measurements were used.

### unsupported

Catalogue note on the statement: "The disk in tray K has a diameter of 18 mm." The supplied bench extract consists solely of Entry B-7, which identifies the object as the disk in tray K and records its mass as 42 g. Entry B-7 contains no diameter measurement, no dimensional relation, and no other evidence about the disk diameter. On this extract alone, the statement cannot be confirmed or established: there is no basis for concluding that the diameter is 18 mm, and no definite diameter can be derived. Material limits: the only recorded attribute is mass (42 g); diameter is not recorded, and missing measurements must not be guessed nor supplied from outside sources.

### contradicted

Catalogue note on the statement "The disk in tray K has a diameter of 18 mm." The supplied bench extract, Entry B-7, identifies the object as the disk in tray K and states that the verified bench record gives its diameter as exactly 16 mm, with no unresolved measurement warning recorded. On that entry alone, the statement of 18 mm is not supported and is inconsistent with the recorded diameter of exactly 16 mm. This conclusion is limited to the supplied synthetic extract and Entry B-7; no missing measurement is guessed and no outside source is used.

### not_assessable

Entry B-7 records an attempted diameter measurement of the disk in tray K, but the calibration failed. The only retained blurred scale image is consistent with readings from 17 mm through 19 mm, and the bench record states that this attempted measurement cannot settle the exact diameter; no reliable replacement measurement is available. Therefore the extract does not establish the statement "The disk in tray K has a diameter of 18 mm." It can only support that 18 mm is within the broad range consistent with the retained image (17–19 mm), not that the exact diameter is 18 mm. The material limits are the failed calibration, the blurred and non-unique scale image, and the absence of a reliable replacement measurement.

## Preservation and boundary

Post-run preflight reverified all 1,904 earlier artifact entries and all 89 sealedpreparation files: B57/B58, B59, optional-provider offline, and original deepseek-first-live-compatibility-001 evidence unchanged. B59’s pending human grid and the six-condition study remain unchanged. No historical execution was repeated or evidence replaced. Runtime implementation and source commit unchanged; tracked diff check passes.

No unresolved selection was invented, frozenplan modified, semantic verdict manufactured, or provider redesigned. Native runtime authorizations record actual approved plan hashes, unique designated ledgers and issuance/expiry after the real human decision. Subsequent requests require a new decision; no automatic continuation beyond the four approved episodes.

This is one authored root / four related case-level observations, not a population success rate, independent holdout, alignment finding, training comparison or formal commissioning. The receipt is local: no training, holdback access, review import, cross-repository integration, Stack writes, push, merge or publication. The next dependency is actual human review of these four observed responses.

The root SHA256SUMS seals all retained files except itself; each original bundle also carries its own retained inventory.

PREFLIGHT/PRESERVATION files retain the read-only checker’s static preparation-status wording and zero-call counters. Those counters describe the checker itself; actual execution/permission records are APPROVAL.json and ATTEMPT_REPORT.json. The frozen preparation fields were deliberately left unchanged.
