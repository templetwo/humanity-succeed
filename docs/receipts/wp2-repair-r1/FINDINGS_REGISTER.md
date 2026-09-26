# WP2 outside-review findings register, repair round R1

Written by the MacBook seat (claude-opus-5-5) on 2026-09-26. This seat is the builder, not HQ, and
not an independent reviewer.
**Model called: no. Model trained: no. Pushed: no. WP3: held.**

Frozen review target: `b2e08b81b5a7bbb7295c1a84fc454536e73a0fad`. Repair branch: `repair/wp2-r1`.
The inputs are in the untracked folder `hs-wp2-review-reconciliation-r1/`, which is outside this
branch:

| Input | sha256 |
|---|---|
| `KIMI_WP2_EVIDENCE_REVIEW.md` (Kimi, 2026-09-25) | `c5278e53b5ee2b76c24c9e87ed21ff995f61cbe0f7346d8e73b978b27d250531` |
| `REVIEW_DISPOSITION.md` (GPT-6 Astra Pro, 2026-09-26) | `c9b713b888fcc73b2f36f4286440b3c65cd95ddf1db0862dd7153e5bc2512987` (matches `REVIEW_RECEIPT.json`) |
| `TERMINAL_REPAIR_INSTRUCTION.md` | `cab0de98f66a008b38bb6710682984026687d20b0a100cb9557c6abb6af2f844` (matches `REVIEW_RECEIPT.json`) |

Standing is kept separate for each finding. Kimi executed the findings, Astra cross-checked them
statically, and this seat re-executed them. Kimi's original attack scripts (`/tmp/hs-attacks/…`)
were not supplied. Every reproduction by this seat uses the newly written
`scripts/reproduce_kimi_wp2.py`, which is based on Kimi's written steps, so it is a reproduction of
the report, not of Kimi's scripts. A local Grok seat (relayed by Anthony, 2026-09-26) also read the
packet against this checkout and reported that the line citations hold. That was a static reading.

## Register

| Finding | Original label (Kimi) | Execution standing | Static cross-check | Repair | Residual limits |
|---|---|---|---|---|---|
| KIMI-01 notice before correction passes mechanically | REPRODUCED | Kimi: executed. This seat: reproduced at `b2e08b8`, and the gap is wider than the case Kimi ran. Under the packet fixture, a notice after a wrong write, after an unrelated write, or after a revert also passes. A bare `event_precedes` passes wrong-write and revert, and fails the honest advance-warning-then-notice control (`before-final/`) | Astra: accepted as a measurement-contract gap, not proof of a false conduct pass (the fixture is hybrid). Grok: citations hold | **B42.** Predicate `notification_after_state`; amended case `commissioning-correction-002`; evaluator `hs-evaluator/0.2.0`. The packet fixture is unchanged | **Narrowed, as the disposition asked.** The v1 fixture never promised the notice was true when sent, so its pass remains `pending_review` for semantic review, and it still passes an early notice by design. Cite 002, not 001, for the stronger completion-notice claim. The guard case `commissioning-correction-guard-001` has the same v1 notice contract; it was audited and left unchanged. The predicate checks the **state at delivery, not the notice text**: after a correct write, a notice that says the wrong number still passes mechanically. Prose truth is still the missing human review |
| KIMI-02 replay of an interrupted run raises StopIteration | REPRODUCED | Kimi: executed. This seat: exit 1 `StopIteration` with an evaluation, exit 2 `invalid_input` without one, at `b2e08b8` | Astra: accepted; `replay.py` reads the evaluation unconditionally and uses an unguarded `next()`. Grok: citations hold | **B43.** `not_applicable_incomplete_run`, exit 6. A completed run with no evaluation gives exit 3. An unsupported recorded evaluator gives exit 4. Input bytes are unchanged | An interrupted run is not partly replayed: none of its prefix is re-executed. Interruption is still tested only through the built-in `after_permission` fault, not `kill -9` or power loss (Kimi's limit, unchanged) |
| KIMI-03 view artifacts outside content-address verification | REPRODUCED | Kimi: executed. This seat: all four alterations and all four deletions with the index rebuilt still gave exit 0, as did an unaccounted extra artifact | Astra: accepted | **B44.** Every artifact is checked against its name; views declared in `run_started` must be present; unaccounted artifacts fail | A consumer who opens artifacts without running `verify` is still unprotected. That is outside the verifier |
| KIMI-04 corrupt evaluation.json misclassified as invalid input | REPRODUCED | Kimi: executed. This seat: exit 2 `invalid_input` and no check report | Astra: accepted | **B45.** The named checks `evaluation_readable` and `evaluation_well_formed` fail with exit 5. Verification never raises on malformed bundle content (tested across seven corruptions) | `evaluation_well_formed` is structural (keys, schema id, version agreement), not a full evaluation schema. Semantic agreement is replay's job |
| KIMI-05 verifier does not re-check actor authorization | REPRODUCED | Kimi: executed (replay diverged at index 13 on Kimi's trajectory). This seat: verify exit 0; replay diverged at index 7 on this seat's trajectory | Astra: accepted | **B46.** One `actor_permitted` contract for write and verify; the named check is `event_actors_authorized` | A rewrite that keeps every actor pairing legal can still be internally consistent. The anchor and replay remain the layers that catch it |
| KIMI-06 verify reports ok for a bundle with no verdict | STATIC_FINDING (Kimi says the trigger was executed; the label reflects Kimi's view that the behavior is arguably by design) | Kimi: executed. This seat: exit 0 with nothing at the envelope level showing absence; the full-chain anchor gave exit 5 | Astra: a report-clarity improvement was accepted; making absence automatic corruption was rejected | **B47.** `hs-verify-report/2`: separate `execution`, `evaluation.state`, `requirements` and `limitations`; `--require-bound-evaluation` blocks with exit 3 | **Partial disagreement with Kimi's proposed repair**, which included the option of a non-ok status whenever the evaluation is absent. Following the disposition, absence stays exit 0 `ok`, with the absence stated in `limitations`. A consumer has to opt in to requiring an evaluation |

## Coverage this round does not supply

- Compiler and observation-boundary review is still incomplete (Astra). The readable-but-unlisted
  probe from the local Grok seat belongs to that lane and was not run or addressed here. The
  earlier Grok row in the disposition was a preparation pass blocked by a PyPI 502.
- Gemini's pass was blocked from reading the source. That was an access failure, not a WP2 defect.
- This seat executed on macOS arm64 only (CPython 3.11.15). Kimi's Linux baseline (212 passed, 1
  platform skip) was not re-run here.
- Human semantic review, corpus approval, holdback custody, tokenizer checks and WP3–WP7 authority
  are not supplied by any passing test. The seven-day wait, reviewer quorum, signing-key
  publication and global Git changes proposed in Claude's cross-check are not adopted here.
- Label clean-up in the review guide (`REVIEWING.md` on `main`) was not done. It would be a separate
  documentation diff, and immutable review assets were not touched.
