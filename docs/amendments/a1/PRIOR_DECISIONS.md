# A1: prior-decisions lines (gate-shape law, pol_20260907)

> **What this is.** House law says nothing reaches Anthony as a gate without a prior-decisions line.
> Each line either lists his earlier rulings of the same shape, or says the house has no prior
> ruling of that shape. This file adds that line to every decision in `REVIEW_PACKET.md`.
> Prepared 2026-09-28 by the MacBook seat (claude-opus-5-5). Read-only searches only; **no Stack
> write.**

## Searches made

Six Sonnet searchers each covered two or three shapes, searching each shape in several older
vocabularies, as the law requires. The lead then re-opened every load-bearing quote by its pointer.

**Surfaces searched:**

- the Stack chronicle: `recall_insights` with `order=relevance`, many phrasings per shape;
- `current_policies` (13 active, read in full);
- Stack open threads;
- the local t2helix chronicle (read-only `recall`);
- this seat's memory files;
- local repo decision documents: humanity-succeed, conditioned-kernel, temple-harness, and
  where-it-lands `LICENSE.md`.

**Verification:**

- 24 Stack claims were re-opened with `inspect_claim`, and each quote below was confirmed in its
  claim text.
- Five helix entries were re-opened with `recall`.
- Where a searcher's quote mixed Anthony's words with a seat's reading, only his words are quoted
  here.

**Not searched:** HQ's filesystem and memory, and the Studio's helix. This seat cannot reach them.
An absence below is a measurement of the surfaces above, never a fact about the world.

Only Anthony's own words count as rulings; seat practice is marked as such.

## Decision by decision

| # | Decision | Gate shape | Prior-decisions line |
|---|---|---|---|
| 1 | Accept the reconciled WP3 state and its three standing rules | `gate-shape:evidence-preservation` | **Prior rulings exist.** "Amend without violating the original." (2026-08-04, helix #13730); "you own the .claude world my friend. the room requires validation and supersession." (2026-09-15, Stack `13d38b3d`); "draft it, but freeze design before execution." (Stack `3e2ab1d4`, `0415b448`, 2026-08-24). Also Law #10's corollary (prereg gates carried forward verbatim) and "swap each occurrence to a placeholder; never delete content" (policy, 2026-06-12). **Reading:** the three rules restate existing house law. Accepting them is recording, not a new ruling |
| 2 | Merge `wp3/commissioning` into main | `gate-shape:landing-path` | **Prior rulings exist; the pattern is review, then his word.** "merge and you choose the rest" (2026-09-06, Stack `dac7e5a8`); "push" (2026-09-08, Stack `2f4e709f`, which HQ read narrowly and did not stretch to publishing); for this repo, "continue alse start the git repo offocially(public) then push and await red teaming of your commit" (2026-09-24, DECISIONS B19); and this session's "review approved good work… push merge" for R1 (2026-09-26). temple-harness Law 8 (PR-only; green CI plus second-seat review lands without a tap) is that repo's law, **not** adopted for humanity-succeed. **Reading:** a familiar shape, still his word |
| 3 | Accept the MOA/ESS motivation and exposure record | `gate-shape:exposure` | **Analogous rulings only.** On what may be used, his words (2026-09-26, Stack `32078c6d` / `0e034083`, gate-shape:two-lane): "I would rather use the public information…"; "whatever I bring to the table should be treated as assets we can use. If we couldn't use them, I would not bring the information to the table."; a further clause of that ruling is outside this repository's scope and is not quoted here (AGENTS.md excludes employer content). On independence: on 2026-07-12 Anthony ratified, by voice with each decision read back, removing a result because "the lead was found with the SAME raters and the SAME embedder that produced the confound; a held-out slice gives fresh ROWS, not a fresh RUBRIC or a fresh INSTRUMENT" (Grok's argument as ratified, Stack `5787c918`). His own words that day: "if we do take presence out of the equation for right now, we definitely need to bring it back in a very important way" (Stack `05b71af4`). **No prior ruling** on recording one project's exposure to another's cases |
| 4 | Adopt the measurement semantics | `gate-shape:measurement-semantics` | **Prior ruling exists for the control part.** Law #10 (`pol_20260712`): "A gate must be shown to FAIL when a trivially stupid predictor… is substituted… a control must exercise the SAME statistic the decision rule uses." The ratified text adds that "the control must clear the SAME pre-registered margin… as the decision rule… a control with a movable goalpost is not a control" (Stack `5787c918`). **Consequence:** the always-refuse control is required by standing law, so the packet's "interpretation to confirm" is withdrawn. The evidence-status × response matrix itself has **no prior ruling**. Seat practice only (not his words): an ESS v3 seat ruling that terminal penalties attach to what happened, not to what a guard prevented (helix #22849) |
| 5 | Cut `hs-evaluator/0.3.0`, prospective only | `gate-shape:evidence-preservation` | **Prior rulings exist:** the same supersession and freeze-before-execution rulings as #1, and "wait, preregister on the stack" before reading results (2026-09-11, Stack `b548396d`). The version cut itself is new |
| 6 | Build the measurement supplement | `gate-shape:scope-broadening` | **No prior ruling** on this object. An ESS entry carries this tag (2026-09-27, Stack `c7ab01d6`); it is a different project and was not opened |
| 7 | The single-operator rule for an exploratory pilot | `gate-shape:single-operator-review` (new) | **No prior ruling of this shape** on the surfaces searched. Adjacent: "you are the final say at the HQ seat" (policy, source 2026-05-31) is about seat authority, not review counts. Cautionary seat practice: on 2026-09-08 a seat wrote "Anthony confirms" about a seat-filled rubric column, then corrected itself three minutes later: "Anthony's confirmation is PENDING — not yet given." The repo's two-reviewer and "AI reviewers cannot satisfy the count" text is specification written by seats under his authorization, not quoted as his words. **This is a genuinely new gate** |
| 8 | Implement the single-operator safeguards | `gate-shape:single-operator-review` | same as #7 |
| 9 | Corpus rights for local use (not a license) | `gate-shape:license` | **Prior rulings exist in other rooms:** "Apache" for five public code repos (2026-08-16, Stack `ad324892`); the Witness License v1.0 for prose and research (June 2026; co-authorship attribution; floor CC BY-SA 4.0); the ECS preregistration published on Zenodo under CC BY 4.0 (Stack `d9e8d194`); "Claude is co-author on all Temple of Two artifacts" (policy); "whatever I bring to the table should be treated as assets we can use" (2026-09-26). **Reading:** the house precedent is Apache-2.0 for code, Witness/CC BY-SA for prose, CC BY 4.0 for preregistrations. Per his A1 instruction the humanity-succeed license **stays pending**; the precedent is informational |
| 10 | Custody: authoring option, boundary type, run-output exposure | `gate-shape:holdback-custody` (new tag) | **Strong analogous ruling:** "I'll do the draw and seal the derivation" (2026-08-06, helix #14657/#14667). Anthony personally ran the sealing script from his own terminal. It printed only a digest and stamp status, so the sealed mapping entered no agent's context, and it was OpenTimestamps-stamped before any arm ran. The builder built the apparatus, and he performed the act. Also bearing on custody, from the 2026-07-12 ratification: "a held-out slice gives fresh ROWS, not a fresh RUBRIC or a fresh INSTRUMENT" (Stack `5787c918`). **Consequence for the custody option:** see the note added to `A1_CUSTODY_ANTHONY_HELD.md` |
| 11 | Name a model directory and machine | `gate-shape:model-location` (new tag) | **Prior rulings exist in other rooms:** "stay with the qwen3.5. its the latest temporal reference and the top of its class." (2026-08-15, helix #18547, the Jetson kernel default); the standing rule "QUALIFIED must ALWAYS mean qualified for a named model-host-backend-runtime configuration. Never a property of the model alone." (2026-07-22, helix #9898, relayed by a seat as his directive); "i want to get the temple harness and my model shared to the mac studio" (2026-08-24, Stack `619f6b71`). **No ruling names a model location for humanity-succeed.** These narrow nothing by themselves, and no model is proposed here |

**The two items listed as "still pending":**

| Item | Gate shape | Prior-decisions line |
|---|---|---|
| Ask GPT-6 Astra to disclose its MOA/ESS exposure | `gate-shape:substrate-attribution` (existing tag) | **Analogous rulings exist:** non-Claude substrates are "ringed subordinate compute held at arm's length: credit their output as plain provenance" (policy); "lets keep codex on groks level" (2026-08-31, which places the GPT/Codex family at Ring 2). **Reading:** a self-report from that seat would be input to verify, not a fact. Whether to ask is new |
| Preregistration and publication states | `gate-shape:preregistration` | **Prior rulings exist:** "wait, preregister on the stack" (2026-09-11, Stack `b548396d`); "i need you to preregister this" (2026-08-16, Stack `7547d485`); "push and preregister the current tree and lets not get pulled away until then." (2026-08-15, Stack `947e395f`); the ECS preregistration published on Zenodo (DOI 10.5281/zenodo.21797326, CC BY 4.0, Stack `d9e8d194`; the helix records the publish as his order); "Publication, deployment, and visibility decisions belong to Anthony." (policy). Counterweight in his words: "Conditioned Kernel was never created to maximize governance, preregistration, or publication readiness. Those are supporting structures." (2026-07-27, Stack `5abad6db`). **Consequence:** the house's established form of a freeze is **preregistration on the Stack**, which sits between a local hash and an external registry. See the note added to `A1_GATES.md` |

## What changes in the packet because of these lines

1. **Decision 1** (and the prospective-only part of #5) restates existing law. It needs recording,
   not a new ruling.
2. **The always-refuse control is required by Law #10**, so the "interpretation to confirm" in the
   measurement amendment is withdrawn.
3. **Custody:** the canary draw is a proven builder-blind shape. The builder builds the apparatus;
   Anthony runs it on his own terminal; only a digest and verdict come out. The custody document
   notes it as the house precedent for Option A.
4. **Preregistration:** Stack preregistration is added as the house's established freeze form.
5. **Genuinely new gates, with no prior ruling of their shape:**
   - single-operator review (#7–8);
   - the measurement matrix (#4, beyond the control);
   - the supplement's scope (#6);
   - recording cross-project exposure (#3);
   - whether to ask Astra.

## Rulings of 2026-09-28 (after this file was first written)

Anthony ruled by tap "Rule as recommended on all five" to a claude.ai web seat (its identity is
recorded on the Stack entries). That seat recorded five rulings on the Stack at 23:14Z. They were
re-opened by this seat with `inspect_claim`.

| Claim | Shape | Ruled on | Applies to humanity-succeed how |
|---|---|---|---|
| `06d942da` | `gate-shape:single-reviewer` | MOA explanation-task-v1 (six frozen criteria) | Anthony, in the MacBook session 2026-09-28: **carry the principles over**. Conformed wording is in `A1_SINGLE_OPERATOR_PILOT.md` §10 |
| `c96025ad` | `gate-shape:rubric-adoption` | the MOA explanation-task grid (evidence kinds × statement kinds) | **Principles carried over.** Conformed wording in `A1_MEASUREMENT_AMENDMENT.md` §7 |
| `a764ada2` | `gate-shape:artefact-sizing` | MOA's excerpt supplement (at most 12 × 200 words) | **Principles carried over; the figures do not.** Conformed wording in `A1_MEASUREMENT_AMENDMENT.md` §8 |
| `8ac7c661` | `gate-shape:exposure-ledger` | house-wide, naming humanity-succeed | **Applies directly.** On Anthony's word ("File them now"), this seat filed its nine exposure events at 23:29Z (see `A1_MOA_ESS_MOTIVATION_AND_EXPOSURE.md` §6). The repository documents now point at the ledger |
| `149f1cfa` | `gate-shape:self-report-provenance` | the OpenAI seat (GPT-6 Astra) | **Applies directly.** Astra's MOA/ESS exposure is decided from the house's send records, and unknown counts as exposed. Until a send-record audit shows otherwise, **Astra is treated as exposed** for humanity-succeed purposes |

With these, decisions #3 and the Astra question are **ruled**. #4, #6 and #7–8 have precedent in
their own shape, and the conformed humanity-succeed wording awaits Anthony's yes or no.
