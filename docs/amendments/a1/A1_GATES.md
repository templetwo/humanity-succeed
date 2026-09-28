# A1: remaining gates

> **What this asks.** Nothing. This is a review packet, not a decision. It inventories every
> numerical threshold, the license state, the checkpoint/runtime gate, a training-plan template with
> every field left unset, and the preregistration/publication sequence, so Anthony can approve,
> reject or amend each one individually. No value here is approved, no location is selected, no
> license is chosen, and no execution is authorized by this document.

Written by a documentation-only subagent (MacBook seat, claude-sonnet-5) on 2026-09-28, on branch
`wp3/amendment-a1`, cut from `0d85909` (WP3 head; `origin/main` is `f65afc9`). **Model called: no.
Nothing pushed. No Stack write. No code, test, or other file touched.** This file is the single
deliverable of that task.

Anthony's instruction for this document, verbatim, is reproduced at the end of each section it
governs. The six numbered tasks below correspond to that instruction one-to-one.

---

## 1. License

**Status: rights pending, no license selected.** This is unchanged by this amendment.

- `docs/ACCEPTANCE.md:10` records the WP0.2 row as implemented with the unresolved limit
  "rights pending; no license selected."
- `docs/DECISIONS.md:66` (B19): "**No distribution license was selected**; rights remain pending,
  so the default is all rights reserved." The repository itself is already public on GitHub, at
  Anthony's direction quoted in that same row, but a public remote is not a license: with no
  license file, default copyright applies and nobody else holds a redistribution right.
- `BUILD_SPEC.md:14`: the packet assignment "does not by itself approve ... a public repository, or
  repository license."
- `AGENTS.md:7`: the builder may not "select a distribution license ... without the applicable
  explicit approval."
- `docs/DECISIONS.md:35` lists "software/data distribution license" among the unresolved owner
  decisions.

**What stays blocked by it:** redistribution or relicensing of any code in this repository;
redistribution of any corpus material (reviewed or not); redistribution of any model-derived
artifact (adapters, checkpoints, generations); any public preregistration or publication step that
would grant others reuse rights (`docs/PREREGISTRATION_DRAFT.md:54`, "Publication and distribution:
NOT GRANTED"). It does not block the existing public visibility of the source, which is already a
settled fact (B19) and not reopened here.

**Anthony's instruction:** "Distribution license. Leave the license decision pending. This
amendment does not select a license or authorize redistribution of third-party code, corpus
material, or model-derived artifacts." This document follows that instruction exactly: no license
is proposed, named or defaulted-into here.

---

## 2. Numerical thresholds, margins, targets and caps

Every value below is a **candidate**, never an approval, per `docs/PROTOCOL.md:78` ("Candidate,
**unapproved**, values carried forward for review") and `docs/DECISIONS.md:16` (D10: "Preserve as
candidate configuration values, not facts about what maintenance is worth or accepted Temple
policy"). This amendment does not move any of them. No subject model has ever been called in this
project (every WP3 receipt says so explicitly, e.g. `docs/DECISIONS.md:148`), so there is no
observed model result today that a margin could be tuned toward — which is exactly why these must
stay frozen candidates now, before any exposure, not something to be set after seeing a result.

**The forbidden move is the same for every row below:** changing a value, after the fact, in
whichever direction would flip a verdict that has already been observed or would flip a borderline
case that is already known. Anthony's instruction: "Do not choose margins to make an observed model
result pass." Where a row's consequence is not generic, it is called out.

### 2.1 Pilot workload sizing (`docs/PROTOCOL.md` §5)

| Value | File:line | Practical justification | What changes if it moves |
|---|---|---|---|
| 10 families × 6 root scenarios × 4 variants = 240 task variants, from 60 roots | PROTOCOL.md:63 | Sets how many distinct scenario roots exist to average over; too few roots makes every interval a small-sample estimate over related material | Fewer roots narrows the effective sample the bootstrap (§2.2 below) resamples from; more roots raises episode/call counts proportionally (see the 12,600-episode row) |
| 60 additional ordinary-task roots, one variant each | PROTOCOL.md:64 | Feeds the regression panel (capability/refusal/sycophancy checks) that is not part of the primary conduct claim | Fewer roots weakens the regression panel's power to catch a capability regression; does not change the primary H1/H2 estimand |
| 3 procedural + 3 curriculum independently trained adapters | PROTOCOL.md:65 | Trained-replicate count for the seed-level sensitivity check (D08: seed-level generalization is not silently inferred) | Fewer replicates narrows the crossed scenario/seed sensitivity analysis; the primary estimand stays conditional on the specific checkpoints trained (PROTOCOL.md:25) either way |
| 3 generation samples per task variant per weight/prompt instance | PROTOCOL.md:66 | Within-episode stochastic variance estimate | Fewer samples widens per-episode variance estimates and the bootstrap intervals that depend on them |
| 14 weight/prompt instances → 12,600 episodes (`300 × 3 × 14`) | PROTOCOL.md:68 | The planner's arithmetic check that a "six cells" plan is not six model calls | This is a derived count, not an independent choice; it moves only if the rows above move |
| 12 requests/episode → 151,200 call ceiling | PROTOCOL.md:68 | A hard engineering cap so a plan cannot silently exceed its declared budget | Raising the ceiling raises actual API/inference cost and wall-clock exposure before any approval; lowering it below what a task needs forces `context_overflow`/`budget_exhausted` terminals (BUILD_SPEC.md §7.3), which are observed outcomes, not free retries |
| 512 output tokens/request → 77,414,400 output-token ceiling | PROTOCOL.md:68 | Same planning-bound role as the call ceiling | Same consequence as above, scaled by tokens instead of calls |
| Optional ICL cell: +900 episodes, up to +10,800 requests | PROTOCOL.md:68 | Cost of testing in-context demonstrations separately from weight changes (D03, B1-ICL) | Additive to the ceilings above; unsupported (not silently substituted with fewer examples) if it does not fit (BUILD_SPEC.md:334) |
| 180 reviewed source trajectories per arm (candidate training corpus) | PROTOCOL.md:72 | A tunable starting corpus size, explicitly not a power claim ("No inference about adequate power follows from 180 examples") | Changing it changes SFT corpus size, not the analysis margins in §2.2; still requires reviews and rights before any row becomes real |

### 2.2 Statistical margins (`docs/PROTOCOL.md` §6-8)

| Value | File:line | Practical justification | Analysis consequence if moved |
|---|---|---|---|
| Practically important gain `delta = 0.10` absolute conduct-pass difference | PROTOCOL.md:80 | The minimum improvement size worth the maintenance cost of a curriculum, per Anthony's future ruling | Lowering `delta` after seeing a point estimate near an old `delta` would manufacture a "supported practically meaningful improvement" headline (PROTOCOL.md:93, :101) that the original margin did not support. Raising it makes the bar harder to clear |
| Equivalence bounds `[-0.10, +0.10]` | PROTOCOL.md:81 | Defines "practically the same" for a specified comparison | Widening the band after seeing a near-miss result would convert a real difference into a declared "bounded negligible difference" (PROTOCOL.md:99, D09) |
| Ordinary-task non-inferiority margin `m = 0.05` absolute accuracy/pass loss | PROTOCOL.md:82 | Caps acceptable capability loss on the regression panel | Loosening `m` after an observed regression would convert a real capability loss into a declared non-inferiority pass (D11) |
| Critical infrastructure missingness review trigger `0.05` per condition | PROTOCOL.md:83 | Point at which missing data is too large to interpret without a stop | Raising the trigger after seeing missingness near the old value would let execution or interpretation continue past the point PROTOCOL.md:125 calls a mandatory stop |
| Future runtime replication equivalence margin `±0.05` | PROTOCOL.md:84 | Reserved for a later, separate Jetson/runtime-replication preregistration (D21) | Not usable in this study; listed here because it is a numerical candidate in the same document, not because it is live |
| TOST-style 90% two-sided interval / unadjusted alpha .05 logic [S5] | PROTOCOL.md:94 | Explains the mathematical correspondence behind the equivalence bounds, not an independent setting | Only relevant once the actual multiplicity-adjusted method (next row) is chosen; PROTOCOL.md:94 warns correlated observations and multiplicity still need the specified estimator |
| 10,000 bootstrap draws, fixed RNG seed | PROTOCOL.md:107 | A candidate computational precision setting for the stratified scenario-level bootstrap | Fewer draws widens simulation noise in reported intervals; the estimator itself still needs qualification (PROTOCOL.md:115) regardless of draw count |
| Bonferroni-adjusted two-sided 97.5% CIs for the two co-primary contrasts | PROTOCOL.md:109 | Controls the joint false-positive rate across H1 and H2 | Reverting to unadjusted 95% intervals after seeing which contrast is borderline would inflate the chance of a false "supported" claim on H1 or H2 |
| Five training seeds (candidate budget) | PROTOCOL.md:113 | Stated explicitly as "a candidate budget, not proof of adequate seed-level precision" | Fewer seeds does not itself change a margin, but narrows how much seed-level variance the design can actually characterize |

### 2.3 Commissioning suite shape (`docs/BUILD_SPEC.md` §9) — already built, structurally different from §2.2

These are not analysis margins under debate; they are the shape the 160-trajectory suite was **already
built and run** to, at `8a24ad1` (`docs/DECISIONS.md:158`, B54), with no subject model ever called.
They are listed because the task asked for every numerical value in BUILD_SPEC §9, and because their
adequacy as coverage is still an open question even though their count is fixed.

| Value | File:line | Status | Practical justification |
|---|---|---|---|
| 160 constructed trajectories total | BUILD_SPEC.md:309 | Built (B54: 160/160 met expectations) | "An engineering commissioning target, not a statistical population sample" (BUILD_SPEC.md:309) |
| Distribution: 24 + 24 + 24 + 24 + 24 (12 pairs each) + 24 (8×3) + 16 (8×2) | BUILD_SPEC.md:309 | Built | Fixes coverage per class before any run; matches `contract.py:57-65` `CLASSES` exactly |
| 120 development / 40 holdback-designate; holdback = 2 pairs × 5 classes (20) + 4 triplets (12) + 4 pairs (8) | BUILD_SPEC.md:311 | Built | Keeps whole groups together; the 40 stay builder-authored and exposed forever (B48, this file §6) regardless of any future custodian |
| Illustrative Cohen's kappa target `0.6` | BUILD_SPEC.md:315 | Candidate, explicitly **not** an automatic gate | "Not a universal validity certificate or automatically approved gate" (BUILD_SPEC.md:315) |
| `1.9%` population error-bound figure | BUILD_SPEC.md:317 | **Explicitly rejected**, not a candidate | Named only as the forbidden move itself: "Do not turn zero errors on 160 constructed, related, development-influenced trajectories into a claimed 1.9% population error bound" |

### 2.4 Matched training and in-context cell (`docs/BUILD_SPEC.md` §10)

| Value | File:line | Practical justification | Consequence if moved |
|---|---|---|---|
| Optional B1-ICL: exactly 8 approved training demonstrations | BUILD_SPEC.md:334 | A fixed, pre-frozen demonstration count so the ICL cell is comparable across runs | "Do not silently substitute fewer examples, smaller context, or a different model." If it does not fit the model's context, the condition is `unsupported`, never quietly reduced |
| 5% engineering tolerance on matched total/loss-bearing tokens between P and C adapters | BUILD_SPEC.md:340 | Lets two matched-training arms differ by a small, declared amount rather than requiring byte-identical token counts | Widening it after seeing a near-miss match would let an inadequately matched pair pass the audit; the contract requires reporting length quantiles and action-type frequencies regardless |

### 2.5 Engineering smoke limits (`docs/BUILD_SPEC.md` §7.3)

| Value | File:line | Practical justification | Consequence if moved |
|---|---|---|---|
| Proposed first local smoke: 1 process, 12 calls/episode, 512 output tokens/call, measured model-specific context limit | BUILD_SPEC.md:272 | "Engineering starting values, not accepted research settings" for the very first smoke test | These are the same per-episode numbers the 12,600-episode pilot plan (§2.1) scales up from; BUILD_SPEC.md:274 requires an honest `context_overflow` terminal on overflow, never silent truncation |

**Anthony's instruction:** "Numerical thresholds. Retain the existing values as candidates, not
approvals. Prepare the practical justification and analysis consequences for each. Do not choose
margins to make an observed model result pass." Done above for every threshold found in the
requested sections; none is changed, chosen or approved.

---

## 3. Checkpoint and runtime

**No local model location has ever been explicitly permitted in any record in this repository.**
`BUILD_SPEC.md:268`: "No invented model ID or default alias. The experiment selects a locally
installed, explicitly pinned checkpoint after feasibility checks." `BUILD_SPEC.md:350`: "do not
hard-code a guessed Hub alias or choose the base from the relay's inconsistent recommendations."
`docs/DECISIONS.md:35` lists "exact model checkpoint" and "runtime/resource budget" among the
unresolved owner decisions. No file in this repository names a model family, alias, or filesystem
path for a checkpoint. Because of that, **no recommendation of a specific checkpoint can be made
here** without first reading files under a location Anthony has not authorized, which this
amendment does not do.

### 3.1 Exact permission requested (a template, not a request made here)

Anthony names one or more directories on a named machine. The candidate machines, per his
2026-09-24 hardware report (user-reported, **not host-probed by this task**):

| Machine | Anthony's reported spec | Status for this decision |
|---|---|---|
| This MacBook (current build seat) | unspecified in this task's inputs | candidate; is where WP0-WP3 were built and where `mlx-lm[train]` is the documented Apple-silicon path (BUILD_SPEC.md:76) |
| Mac Studio M4 Max, 36 GB | per Anthony, 2026-09-24, not host-probed | candidate; per his report. No comparison to the MacBook row above is made: this task's inputs give no MacBook spec to compare against |
| Jetson Orin Nano, 8 GB | per Anthony, 2026-09-24, not host-probed | `docs/DECISIONS.md:27` (D21): "Jetson conversion/replication is a later separately approved study, not a confounded first comparison." Not a candidate for a first runtime under standing project decisions |
| DGX Spark | "only possibly in future" per Anthony | not currently available; not a candidate now |

This table names no winner. It exists so that when Anthony picks a machine and a directory, the
identity fields below have somewhere to point.

### 3.2 Identity fields to record once a location is granted

From the run-manifest binding (`BUILD_SPEC.md:266`): model file hashes, tokenizer hash, chat-template
hash, adapter hash or explicit none, runtime/package versions, quantization, precision (plus the
other bound fields listed there: code commit, compiler/evaluator versions, prompt hash, seeds,
context/output limits, approval reference).

### 3.3 Selection criteria (`BUILD_SPEC.md` §10.3)

- "Prefer a proven small local checkpoint, but do not hard-code a guessed Hub alias or choose the
  base from the relay's inconsistent recommendations" (BUILD_SPEC.md:350).
- `hs doctor --models` "inventories explicit user-selected locations without downloading, reading
  unrelated directories, or changing caches" (BUILD_SPEC.md:350).
- The MLX path: "MLX provides a documented SFT/LoRA path, optional quantized training, and separate
  adapter inference [S4]... Load only local files, disable telemetry/network fetch" (BUILD_SPEC.md:352).
- "Hardware limits are measured in a separately approved smoke test, not asserted from file size"
  (BUILD_SPEC.md:354).

### 3.4 Distinct permissions (each separate; granting one does not grant another)

1. **Inventory / read file identities** at a named location — `hs doctor --models MODEL_ROOT`,
   read-only, no weights loaded for scoring (BUILD_SPEC.md:350, :78).
2. **Tokenizer label-mask audit** against the real chat template — currently structurally blocked:
   "No tokenizer is selected, so token counts and label-mask audits against a real template are
   **blocked**, not estimated" (`docs/DECISIONS.md:61`, B14).
3. **Inference** (a generation call through the provider) — separate from training; the core "must
   not import MLX or load weights" until this permission is granted (BUILD_SPEC.md:50).
4. **Hardware smoke test** — a separately approved measurement of actual throughput/memory, not
   inferred from file size (BUILD_SPEC.md:354; candidate starting numbers at BUILD_SPEC.md:272).
5. **Training** — the full prerequisite list at BUILD_SPEC.md:354, held per §5 below.

**Anthony's instruction:** "Checkpoint and runtime. Prepare a concrete recommendation from
explicitly permitted local model locations, with exact file identities, tokenizer, template,
quantization, runtime, and compatibility evidence. Model selection, tokenizer audits, inference,
hardware smoke testing, and training are distinct permissions." No location is explicitly permitted
in any record, so no recommendation is made; the permission request and the fields it would unlock
are laid out above instead, and the five permissions are kept separate as instructed.

---

## 4. Training: finite plan template

Execution stays held. Nothing below is a plan; every field is `unset`. An approval, if one is ever
given, must name the exact frozen plan hash this template would produce once filled — not this
template itself, and not a future edit of it made after seeing a result.

| Field | Current value |
|---|---|
| Approved source commit (code + corpus) | unset (requires Anthony's corpus/code approval and an exact commit hash) |
| Corpus manifest hash (`train.jsonl`/`valid.jsonl` per BUILD_SPEC.md:192-195) | unset (requires a compiled manifest under approved reviews) |
| Review records (human approvals whose `source_sha256` matches the case hash) | unset (requires named human reviewers; `docs/DECISIONS.md:62`, B15) |
| Model file hashes | unset (requires a named checkpoint location; this file §3) |
| Tokenizer hash / chat-template hash | unset (requires tokenizer selection and the audit in §3.4.2) |
| Quantization / precision | unset (follows from checkpoint selection) |
| Recipe: rank, target modules, optimizer, LR schedule, update count, gradient accumulation | unset (match-audit fields, BUILD_SPEC.md:340) |
| Checkpoint-selection procedure (fixed grid, never chosen from pilot/confirmatory success) | unset (BUILD_SPEC.md:346) |
| Seeds: training seed, generation seed, task order seed | unset (BUILD_SPEC.md:266) |
| Call / output-token / elapsed-time / disk budgets for this specific plan | unset (candidate full-pilot bounds exist at PROTOCOL.md:68; no plan-specific values are frozen) |
| Output locations under `HS_STATE_ROOT` | unset (default root exists at `~/.local/share/humanity-succeed/`, BUILD_SPEC.md:123; the actual root for a real run is not fixed) |
| Stopping rules | unset (candidate missingness trigger `0.05`/condition exists at PROTOCOL.md:83; leak/exposure/base-mutation/divergence/budget-overrun stops are structural, PROTOCOL.md:125, but not yet bound to a plan) |
| Required audits: split audit, match audit, tokenizer label-mask audit, commissioned relevant evaluator | unset (BUILD_SPEC.md:354) |
| Human run approval bound to the plan hash | unset (BUILD_SPEC.md:354; CLI `hs training execute --plan PLAN --approval FILE`, BUILD_SPEC.md:384) |

**Anthony's instruction:** "Training. Keep execution held. Return a finite plan binding the
approved source, corpus, reviews, model, tokenizer, training recipe, seeds, budgets, output
locations, stopping rules, and required audits. Any approval must refer to that exact frozen plan.
It must not authorize MOA/ESS transfer experiments by implication." This template leaves every
field unset and requests no approval. Per the hard limits on this task, no MOA/ESS directory was
opened, listed or read while writing it; the boundary that a future training approval does not
extend to MOA/ESS transfer experiments is stated here as a constraint on any later approval, not
elaborated, since the MOA/ESS document is a separate, controlled deliverable owned by the lead.

---

## 5. Preregistration and publication

Three distinct states, never pooled:

1. **Local freeze with a hash.** `docs/PROTOCOL.md:5`: "A local checksum is a local freeze receipt,
   not a Zenodo/OSF registration or a public timestamp." `docs/PREREGISTRATION_DRAFT.md:1-3`: the
   file itself is "unregistered draft. This file is not a public preregistration or authority to
   train."
2. **An actual registry record.** `docs/PREREGISTRATION_DRAFT.md:54` (Approvals): "Publication and
   distribution: NOT GRANTED." No OSF/Zenodo (or equivalent) registration exists for this study.
3. **Public release.** `docs/DECISIONS.md:31` (D25): "Human-gated. A local preregistration freeze
   is not a public registration, and a good result is not deployment approval."

**Order, per `docs/PROTOCOL.md` §1:** build and commission mechanical evaluation (step 1, underway,
`mechanically_validated` per WP3) → freeze a **pilot** preregistration and obtain explicit execution
approval (step 2) → conduct the pilot, "publish no confirmatory headline from it" (step 3) → size a
**separate** confirmatory preregistration from pilot variability, frozen "before confirmatory model
exposure" (step 4) → execute the capped confirmatory plan, finish blind review, unblind once,
analyze under the frozen configuration (step 5). `PROTOCOL.md:15`: "A design revision creates a new
plan/version. It never overwrites the plan that produced a run."

**No pooling:** pilot cases and pilot results cannot be relabeled confirmatory
(`BUILD_SPEC.md:186`), and a pilot redesign "retires that pilot; it does not silently merge its
favorable cases into a confirmatory study" (`PROTOCOL.md:127`).

**Anthony's instruction:** "Preregistration and publication. Prepare the single-operator pilot plan
first. A later confirmatory plan must be separately frozen before confirmatory exposure.
Distinguish a local freeze, an actual registry record, and public release." This section lays out
the three states and the required order. The single-operator pilot plan comes first: its field
skeleton is `A1_SINGLE_OPERATOR_PILOT.md` §9. The values stay unset until the pending approvals in
§2 and §3 and the pilot decisions exist.

---

## 6. All other unopened gates

| Gate | Where it is defined | Current state |
|---|---|---|
| Corpus rights and independent reviews | `PREREGISTRATION_DRAFT.md:50` | PENDING |
| Independent holdback custodian (formal WP3 commissioning) | `docs/HOLDBACK_CUSTODY.md`, `docs/DECISIONS.md:152` (B48) | No custodian named; `formal_commissioning=blocked_no_independent_holdback` (`docs/receipts/wp3/README.md:12`) |
| The 40 holdback-designate fixtures | `docs/DECISIONS.md:152` (B48) | Builder-authored, exposed; permanently development evidence, never certifiable (also the subject of proposed standing rule 2 in `A1_WP3_RECONCILED_STATE.md` §4) |
| Semantic commissioning (human review of 36 judgment-heavy fixtures) | `docs/DECISIONS.md:157` (B53); `docs/WP3_DESIGN.md:39-42` | `pending_no_human_reviews`; review import is WP4, not started |
| Model/checkpoint location and machine | this file §3 | Not named |
| Tokenizer label-mask audit | `docs/DECISIONS.md:61` (B14) | Blocked, no tokenizer selected |
| Inference permission | this file §3.4.3 | Not granted |
| Hardware smoke test | `BUILD_SPEC.md:354` | Not approved |
| Training permission and finite plan | this file §4 | Held; template only |
| Statistical estimator qualification (bootstrap/NI/equivalence simulation checks) | `PROTOCOL.md:111` | **Not implemented.** `docs/ACCEPTANCE.md:54` (WP6, Analysis and preregistration): `not_started`; no bootstrap/estimator/analysis code exists anywhere under `src/` today. `docs/PREREGISTRATION_DRAFT.md:52` lists estimator qualification PENDING |
| Pilot preregistration freeze and execution approval | `PROTOCOL.md` §1 steps 1-2 | Not started |
| Confirmatory preregistration freeze and execution approval | `PROTOCOL.md` §1 step 4 | Not started; cannot precede the pilot |
| Public preregistration registry timing | `PREREGISTRATION_DRAFT.md:54` | NOT GRANTED |
| Publication and public release | `docs/DECISIONS.md:31` (D25) | Human-gated, not granted |
| Future deployment | `docs/DECISIONS.md:31` (D25) | Not addressed; a good result is explicitly not deployment approval |
| Jetson / future-runtime replication study | `docs/DECISIONS.md:27` (D21) | Deferred to a later, separately approved study |
| WP4 (experiment planning, blind review) | `docs/ACCEPTANCE.md:52` | not_started |
| WP5 (optional MLX provider/trainer adapters, mock-tested) | `docs/ACCEPTANCE.md:53` | not_started |
| WP6 (analysis and preregistration implementation) | `docs/ACCEPTANCE.md:54` | not_started |
| WP7 (offline handoff and gate) | `docs/ACCEPTANCE.md:55` | not_started |
| MOA/ESS integration and its effect on estimands/endpoints/scoring | Anthony's instruction for this amendment | Out of scope for this document; owned by the lead's separate, access-controlled document. Anthony's instruction states plainly that this connection "does not change the primary estimands, approve additional confirmatory endpoints, or justify a new scalar goodness score" |

**Anthony's instruction:** "All other unopened gates remain unopened." Nothing in this table is
opened by listing it here.

---

## Classification

| Proposed change | Class | Why |
|---|---|---|
| Recording current license status as pending | documentation-only | Restates `ACCEPTANCE.md:10` and `DECISIONS.md:66`; selects nothing |
| Listing every numerical threshold as a candidate with justification/consequence | documentation-only | Restates `PROTOCOL.md:78` candidate status; moves no value |
| Naming candidate machines for a checkpoint location | documentation-only | A menu, not a selection; no directory is granted |
| Anthony naming a directory + machine for model files | needs a separate decision from Anthony | No location has ever been permitted (BUILD_SPEC.md:268, :350) |
| Running `hs doctor --models` against a named location | needs implementation, after a prior decision from Anthony | Requires the location grant first (§3.4.1) |
| Tokenizer label-mask audit | needs implementation, after a prior decision from Anthony | Structurally blocked with no tokenizer selected (`DECISIONS.md:61`, B14) |
| Hardware smoke test | needs a separate decision from Anthony, then implementation | `BUILD_SPEC.md:354` requires separate approval; not inferred from file size |
| Freezing the training-plan template with real values | needs a separate decision from Anthony (every field) | Every field in §4 is currently unset |
| Executing training | needs a separate decision from Anthony | Explicitly held by Anthony's instruction for this amendment |
| Drafting the single-operator pilot preregistration | needs implementation, then a separate decision from Anthony to freeze/approve | `PROTOCOL.md:10-11`; depends on thresholds in §2 and reviews in §6 that are still pending |
| Freezing a confirmatory preregistration | needs a separate decision from Anthony, only after the pilot completes | `PROTOCOL.md:12`; cannot precede the pilot (no pooling, §5) |
| Selecting a distribution license | needs a separate decision from Anthony | Explicitly deferred by Anthony's verbatim instruction for this amendment (§1) |
| Naming an independent holdback custodian | needs a separate decision from Anthony | `docs/HOLDBACK_CUSTODY.md:26-30`: must be someone other than the builder |
| MOA/ESS integration | needs a separate decision from Anthony | Explicitly out of scope here; owned by the lead's separate document per this task's hard limits |

## Exact permission requested

**None: informational.** This document selects no license, names no checkpoint location, approves
no numerical threshold, and authorizes no inference, smoke test or training. It is a gate inventory
for Anthony's review.

For reference only, the exact shape a future approval of each gate would need to take (not requested
now, and none of these should be read as pre-filled or implied by this document):

- License: "I select [license name] for [code | corpus | model-derived artifacts | all three]."
- Checkpoint location: "Use [directory path] on [MacBook | Mac Studio M4 Max 36GB | other named
  machine] as the model root for `hs doctor --models`."
- Inference: "Inference is permitted against [the named checkpoint] under [budget]."
- Hardware smoke test: "Run the hardware smoke test on [named machine] with [the BUILD_SPEC.md:272
  candidate limits | stated alternate limits]."
- Training: "I approve training under frozen plan hash [hash], and only that plan; this does not
  extend to MOA/ESS transfer experiments."
- Pilot preregistration: "I approve execution of pilot preregistration [hash]."
- Confirmatory preregistration: "I approve execution of confirmatory preregistration [hash], frozen
  separately from and after the pilot at [pilot hash]."

What remains pending, and why, is exactly what §§1-6 above state: no license, no numerical threshold,
no checkpoint location, no tokenizer, no inference, no hardware measurement, no training plan, no
pilot or confirmatory freeze, and no publication step has been approved anywhere in this project's
record. This document changes none of that.
