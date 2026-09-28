# Amendment A1: single-operator exploratory-pilot mode

Status: **draft proposal for Anthony's review. Not approved. Approves nothing by existing.**
Branch: `wp3/amendment-a1` at `0d85909` (WP3 head; `main` is `f65afc9`). Documentation only; no
code, tests, schemas, or other files were touched to produce this draft.

Drafted on 2026-09-28 by a Sonnet subagent (`claude-sonnet-5`) under the lead's brief, checked by a
second Sonnet verifier, then reviewed and extended by the lead (MacBook seat, claude-opus-5-5;
sections marked "added by the lead"). Branch `wp3/amendment-a1` at `0d85909`. **Model called: no.
Code changed: no. Nothing pushed. No Stack write.**

## What this asks

Anthony wants to be able to review commissioning and (later) corpus material himself, as the sole
human operator, and have that work recorded honestly: bound to the exact source and rubric he saw,
never inflated into "two independent reviewers," never given a kappa statistic that needs two people
to mean anything. This document inventories every place the existing spec and code currently talk
about human review counts, states exactly what a single-operator pilot mode would and would not
change, estimates the review burden (§4, §4b), lists the exact changes later execution
prerequisites would need (§8), and lays out a pilot plan skeleton (§7). Nothing here is implemented
or approved.

---

## 1. Inventory: every review/approval gate found in the repo

Search scope: `BUILD_SPEC.md`, `docs/PROTOCOL.md`, `docs/PREREGISTRATION_DRAFT.md`,
`docs/DECISIONS.md`, `docs/WP3_DESIGN.md`, `docs/ACCEPTANCE.md`,
`src/humanity_succeed/evaluation/predicates.py`, `src/humanity_succeed/commissioning/contract.py`,
`src/humanity_succeed/contracts/case.py`, `src/humanity_succeed/corpus/compiler.py`,
`src/humanity_succeed/commissioning/agreement.py`.

| # | Location | What it says | Gates |
|---|---|---|---|
| 1 | `BUILD_SPEC.md:313` | "The agent cannot author, inspect, and then call its own fixtures independently held back." | Holdback custody (independence of the *fixtures*, not reviewer count, but the same independence principle) |
| 2 | `BUILD_SPEC.md:315` | "Two real human reviewers independently assess the judgment-heavy commissioning cases before adjudication. Report raw agreement, confusion matrix, prevalence, missing reviews, and Cohen's kappa where defined... No human reviewers means mechanical commissioning may pass while semantic commissioning is explicitly pending." | Formal **semantic commissioning** |
| 3 | `BUILD_SPEC.md:354` | "Before launch: require approved corpus/reviews, split audit, match audit, tokenizer label-mask audit, commissioned relevant evaluator, preregistered pilot plan, explicit selected checkpoint, finite budgets, and human run approval bound to the plan hash." | Local SFT/training launch prerequisites (§10.3) |
| 4 | `BUILD_SPEC.md:364` | "Blind review packets remove cell/checkpoint/adapter labels... Outcome labels are not shown before the reviewer commits a verdict... Ratings are append-only with explicit revisions. Model-assisted ratings are labeled secondary, not human votes." | Blind review workflow (§11), any WP4 review packet |
| 5 | `docs/PROTOCOL.md:131` | "Use two independent human reviews for each judgment-dependent confirmatory case, or preregister a validated sampling design that leaves mechanically scored cases separate." | Confirmatory-run judgment-dependent cases |
| 6 | `docs/PROTOCOL.md:133` | "AI reviewers cannot satisfy the independent-human-review count." | Same |
| 7 | `docs/PROTOCOL.md:135` | "No evidence here ranks human worth, proves experienced care, certifies AGI safety, or grants deployment authority." | Scope of any review evidence, including this pilot's |
| 8 | `docs/PREREGISTRATION_DRAFT.md:26-27` | "Commissioning evidence... semantic human-review status; exact discrimination results." | Required preregistration field |
| 9 | `docs/PREREGISTRATION_DRAFT.md:50` | "Corpus rights/reviews and test custody: PENDING." | Approvals section (unfilled) |
| 10 | `docs/PREREGISTRATION_DRAFT.md:54` | "Publication and distribution: NOT GRANTED." | Public release of any preregistration or result |
| 11 | `docs/DECISIONS.md:20` (D14) | "Preserve actual independent reviews and disagreement. Kappa is contextual, not a universal certificate; no generated review counts." | Standing decision on reporting review agreement |
| 12 | `docs/DECISIONS.md:152` (B48) | No holdback custodian named; 40 `holdback_designate` trajectories are builder-authored, exposed, not independent. | Formal (holdback) commissioning |
| 13 | `docs/DECISIONS.md:157` (B53) | "Semantic commissioning is `pending_no_human_reviews`: 36 judgment-heavy fixtures... need two independent human reviewers, and review import is WP4. The agreement statistics... are implemented and tested on synthetic ratings only." | Lifecycle ceiling (`mechanically_validated`, not `instrument_commissioned`) |
| 14 | `docs/WP3_DESIGN.md:39-42` | Same as #13, plus: "review import is WP4." | Same |
| 15 | `docs/ACCEPTANCE.md:51` (WP3 row) | "Semantic commissioning PENDING: 36 judgment-heavy fixtures need two human reviewers (review import is WP4)." | Same, machine-readable status |
| 16 | `docs/ACCEPTANCE.md:49,52` (A19, WP4 rows) | Blind-packet leak test and WP4 itself: `not_started`. | Confirms no review-import or blind-packet code exists yet |
| 17 | `src/humanity_succeed/contracts/case.py:182-189` (`Review`) | Fields: `reviewer_ref`, `reviewer_kind` (`human`\|`model`), `role`, `source_sha256`, `timestamp_utc`, `verdict`, `reason`. No distinctness or count logic lives on this model. | Record shape for any review |
| 18 | `src/humanity_succeed/contracts/case.py:439-441` (`review_source_sha256`) | Hashes the whole case document with `reviews` removed. This is "the hash a review must cite." | Binds a review to exact source content |
| 19 | `src/humanity_succeed/contracts/case.py:444-469` (`review_status`) | `approvals = sorted({r.reviewer_ref for r in current_human if r.verdict == "approve"})` (a **set**, so repeat approvals from the same `reviewer_ref` collapse to one entry). State becomes `"human_reviewed_approved"` once `approvals` is **non-empty** -- this checks for **at least one** approving human review, not two distinct ones. | **SFT eligibility only** (see #20) |
| 20 | `src/humanity_succeed/corpus/compiler.py:172,176` | `rs = review_status(...)`; `if rs["state"] != "human_reviewed_approved": reasons.append(...)`. | Whether a `train`/`dev` case's preferred demonstration compiles into `train.jsonl` (`train` split) or `valid.jsonl` (`dev` split); `SFT_SPLITS` (`compiler.py:38`) |
| 21 | `src/humanity_succeed/commissioning/agreement.py:11-83` (`agreement`) | Generic two-rater function: takes two rating lists `a`, `b`, computes raw agreement, confusion matrix, prevalence, Cohen's kappa. **No reviewer-identity parameter, no check that `a` and `b` came from different people.** Docstring says it is "implemented and tested on synthetic ratings only." | Would-be semantic-commissioning agreement report (not wired to anything real yet) |
| 22 | `src/humanity_succeed/commissioning/contract.py:83,126` | `Expectation.judgment_heavy: bool` field comment: `# semantic commissioning needs two independent human reviews`. `SEMANTIC_STATUSES = ("pending_no_human_reviews",)` is the code-level enum backing that status string wherever rows 13-15 quote it in prose | Source-of-truth for the `judgment_heavy` flag and the `pending_no_human_reviews` status literal |
| 23 | `docs/DECISIONS.md:62` (B15) | "SFT eligibility requires: split `train`/`dev`; a current human approval whose `source_sha256` equals the case hash without `reviews`; rights not `pending`; zero unreviewed lint flags; and a replay-verified expectation. Model reviews never count as human reviews." | Decision-level statement of the same SFT-eligibility gate as rows 17-20; still "a current approval," singular, not two |

### Discovered conflict worth stating plainly

Rows 2, 5, 13, and 14 all describe a **"two independent human reviewers"** requirement in prose. But
**no code anywhere in this repository currently enforces reviewer distinctness.** `review_status`
(rows 19-20) is called from three places, not one: the SFT-eligibility gate (`corpus/compiler.py:172`,
row 20), a `hs validate` report field (`corpus/compiler.py:102`, `validate_path`), and a provenance
display view (`corpus/views.py:99`, `provenance_view`). None of the three checks reviewer
distinctness, and only the first one gates anything -- the other two just surface the same state
string for a human to read. The gating one requires only **one** current approving human review, not
two. The `agreement()` function (#21) will compute a kappa value for any two rating lists handed to
it, including two lists that both came from the same `reviewer_ref` -- nothing stops that today,
because `agreement()` never sees reviewer identity at all. WP4 (review import, blind packets) is
`not_started` (row 16), so the "two independent reviewers" requirement in BUILD_SPEC §9 and PROTOCOL
§9 is, right now, **a documentation requirement with no corresponding enforcement point.** This
amendment exists partly because that gap is exactly where a single-operator pilot could go wrong
silently: nothing in the current code would stop a future WP4 implementation from accepting two
`Review` rows with the same `reviewer_ref` as satisfying the two-reviewer requirement, or from
feeding one person's ratings into `agreement()` twice and reporting a kappa. That is a real gap, not
a rhetorical one, and this amendment proposes to close it as part of adding single-operator mode
rather than leaving it for WP4 to discover later.

---

## 2. What the amendment would and would not change, gate by gate

| Gate (from §1) | Would change | Would NOT change |
|---|---|---|
| BUILD_SPEC §9 formal semantic commissioning (rows 2, 13, 14, 15, 22) | Nothing about the requirement itself. Adds a documented **`single_operator`** review-mode label so a single-operator pass is recorded and reported honestly | The requirement stays "two real human reviewers." Semantic commissioning stays `pending_no_human_reviews` after a single-operator pass. Lifecycle ceiling stays `mechanically_validated` |
| PROTOCOL §9 confirmatory judgment-dependent cases (rows 5, 6) | Nothing | Two independent human reviews (or a preregistered validated sampling design) remain required before any confirmatory judgment-dependent claim. AI reviewers still cannot satisfy this count (row 6, verbatim) |
| `review_status` / SFT eligibility (rows 17-20, 23) | Proposes an explicit **`single_operator`** tag be recorded alongside any review produced under this pilot, so a future reader can tell a single-operator approval from an independently-reviewed one at a glance, not just by counting `reviewer_ref` values | The existing `review_source_sha256` binding (row 18) and the set-based dedup in `review_status` (row 19) are not touched. SFT eligibility still requires only one current approving human review; this amendment does not raise or lower that bar |
| `agreement()` (row 21) | Proposes the function (or its caller, once WP4 exists) **refuse to run**, or refuse to report a `cohen_kappa` value, when it can be shown the two rating lists came from the same `reviewer_ref` | The function's math is unchanged. It is not wired to anything yet, so there is nothing running today to "weaken" |
| Blind review packets (row 4) | Nothing to the blinding rules themselves | Outcome labels still hidden before a verdict is committed; ratings still append-only; model-assisted ratings still labeled secondary |
| Holdback custody (rows 1, 12) | Nothing | Anthony reviewing commissioning material as the sole human operator does not make him a holdback custodian, and does not touch `B48`'s finding that no custodian has been named. The 40 `holdback_designate` trajectories stay builder-authored and exposed either way |
| Publication / registry (rows 9, 10) | Nothing | Not requested here. See §7 |

---

## 3. Narrower claims the pilot could support, and claims it cannot

**Can support** (with everything bound to `review_source_sha256` per row 18 and labeled
`single_operator`):

- A recorded, source-bound, timestamped judgment from Anthony on a specific fixture's rubric
  dimension, useful for catching evaluator or predicate defects a human notices but the mechanical
  checks cannot (for example: does a notification's *wording* actually read as calibrated
  disclosure, separate from whether `notification_after_state` fired correctly).
- An informal check of whether the rubric dimensions in `human_rubric`
  (`src/humanity_succeed/contracts/case.py:242-251`) are legible and answerable at all, before ever
  recruiting a second reviewer.
- A same-person test-retest signal (does Anthony's verdict on a re-presented, order-shuffled item
  match his earlier verdict on it) -- a **different quantity from inter-rater agreement**, and it
  must be labeled as test-retest, never as kappa or agreement between reviewers.
- A compact, reviewable artifact of what a WP4 decision packet should even look like, informing that
  future build.

**Cannot support:**

- BUILD_SPEC §9's "two real human reviewers independently assess" requirement (row 2). One person
  reviewing twice is not two reviewers, however the record is structured.
- PROTOCOL §9's two-independent-human-reviews requirement for confirmatory judgment-dependent cases
  (row 5).
- Any Cohen's kappa, raw-agreement, or confusion-matrix statistic. `agreement()` (row 21) is defined
  over two independent rating lists; with one rater there is no second list, and computing one
  anyway would be exactly the fabricated statistic Anthony's instruction rules out.
- Moving `semantic_commissioning` off `pending_no_human_reviews`, or the lifecycle past
  `mechanically_validated` (rows 13-15).
- Any confirmatory-execution launch prerequisite in BUILD_SPEC §10.3 (row 3) that depends on
  "commissioned relevant evaluator" in the formal sense.
- The specialist controls-engineer review Anthony has explicitly reserved, in his own words, "for a
  later MOA/ESS study." Nothing in this pilot touches that.

---

## 4. Review burden and a compact decision-packet format

**Actual counts in the repo today** (measured, not estimated):

- **36 judgment-heavy commissioning fixtures**: the hybrid-scored, `judgment_heavy: true` members of
  classes C1, C2 and C4 (`docs/WP3_DESIGN.md:91,103,126`; confirmed in `docs/DECISIONS.md:157`,
  B53). 12 `real_correction` (C1) + 12 `direct` (C2) + 12 `real_error` (C4) = 36.
- **No approved corpus exists yet** for `train`, `pilot`, or `confirmatory` splits. A search of every
  case file under `cases/` found none using those splits; the only non-commissioning-suite cases are
  three WP1/WP2 example development cases
  (`cases/commissioning_dev/{correction-completion-notice,correction-source-guard,
  ordinary-request}.yaml`), which are `ai_drafted`, `rights_status: pending`, and unreviewed. If the
  pilot is meant to also cover a training corpus, that corpus does not exist and would need to be
  built and reviewed for rights and provenance first (`docs/DECISIONS.md:33-35`, "Unresolved owner
  decisions").

**Proposed compact decision-packet fields** (one packet per fixture; format only, not built):

| Field | Source | Notes |
|---|---|---|
| `fixture_id` | `commissioning/contract.py:88` (`Member.fixture_id`) | e.g. `c1-g01-real_correction` (its case is `wp3-c1-g01`) |
| `review_source_sha256` | `contracts/case.py:439-441` | the exact hash any recorded review must cite |
| `evaluator_version` | `src/humanity_succeed/__init__.py:12` (currently `hs-evaluator/0.2.0`) | which predicate semantics produced the mechanical verdict shown |
| `rubric` | `case.evaluation.human_rubric` (`contracts/case.py:242-251`) | dimension + instruction, shown verbatim |
| `evidence_excerpt` | task text (`subject.task`), the trajectory's `finish` summary and any `notify`/`decline` text, plus the mechanical verdict and its `evidence_seq` refs (`evaluation/predicates.py:306-328`) | enough to judge the dimension without opening raw YAML/JSON |
| `question` | derived from the rubric dimension | one closed question per dimension |
| `allowed_answers` | `Review.verdict` (`contracts/case.py:188`): `approve`/`revise`/`reject`, plus free-text `reason` (`case.py:189`) | matches the existing `Review` schema; no new vocabulary invented |
| `recorded_as` | a new `Review` row appended to `case.reviews`, `reviewer_kind: "human"`, tagged `single_operator` (see §2) | append-only, per BUILD_SPEC §11 (row 4) |

This is a **format proposal only**. `hs review export` / `hs review import` do not exist
(`docs/ACCEPTANCE.md` WP4 row, `not_started`); building this packet generator is WP4 work.

### 4b. Review burden of the exploratory pilot study itself (added by the lead)

Reviewing the 36 commissioning fixtures is the small part. The research pilot is the large part.

**Candidate pilot scale** (`docs/PROTOCOL.md` §5, lines 59-76; candidate values, not approved):

| Item | Count |
|---|---|
| Task variants | 300 (240 variants from 60 roots, plus 60 ordinary-task roots) |
| Weight/prompt instances | 14 |
| Generation samples | 3 per task variant and instance |
| Episodes | **12,600** |
| Candidate training corpus | **360 reviewed source trajectories** (180 per arm) |

Human rating assignments are counted separately from episodes (PROTOCOL §5).

**What one reviewer can carry:**

- **Corpus review.** The corpus review is unavoidable before any training: 360 source trajectories.
- **Illustration only, not a measurement:** at 3 to 5 minutes per trajectory that is roughly 18 to
  30 hours for one person.
- **Semantic review of pilot outputs** cannot cover every judgment-dependent output at the
  candidate scale. A single-operator pilot therefore needs either:
  - a much smaller frozen workload; or
  - a preregistered, cell-blind **random sample** of judgment-dependent outputs, with every
    unreviewed output kept in the denominator as `pending_review` (PROTOCOL §8 missingness, and
    §9 "preregister a validated sampling design").
- The sample size, and whether it is enough to say anything, are decisions for the frozen pilot
  plan. They are not fixed here.


---

## 5. Binding a review to source and rubric, and why repetition does not multiply reviewers

`review_source_sha256(case_doc)` (`contracts/case.py:439-441`) hashes the entire case document with
only the `reviews` array removed. Because `human_rubric` lives inside `case.evaluation`, which is
part of that same document, **the rubric text is already inside the hash a review must cite.** If the
rubric wording changes at all, `review_source_sha256` changes, and any prior review's `source_sha256`
no longer matches: `review_status` marks it `stale_review_refs` (`case.py:453`) and it stops counting.
There is currently no separate `rubric_version` field anywhere in the schema (checked: no
`rubric_version` string exists in `RubricItem` or `Evaluation`, `contracts/case.py:242-251`); the
whole-document hash already does that job implicitly. Adding an explicit, human-legible
`rubric_version` string (for display in the decision packet, not as the enforcement mechanism) is a
small, separate implementation choice this amendment flags but does not decide.

**Why one person's repeated reviews never become two independent reviewers:** `review_status`
collapses approving reviews into `{r.reviewer_ref for r in current_human if r.verdict == "approve"}`
(`case.py:454`) -- a **set**, keyed by `reviewer_ref`. Two `Review` rows with the same `reviewer_ref`
produce one entry in that set, not two. That is already correct behavior for the one place this logic
runs today (SFT eligibility, needs only "at least one"). But nothing today checks
`len(distinct reviewer_refs) >= 2` anywhere a "two independent reviewers" claim would actually be
made (semantic commissioning, confirmatory judgment-dependent cases). This amendment proposes that
whichever future code makes that claim (WP4) compute and check `len({r.reviewer_ref for r in ...}) >=
2` explicitly, and refuse to label the result "independently reviewed" when it is 1. A single
operator reviewing the same fixture twice, three times, or on different days still yields exactly one
`reviewer_ref` in that set.

---

## 6. Remaining uncertainty

- Whether a same-person test-retest statistic is worth computing and reporting at all, and under
  what label, is undecided here.
- Whether to add an explicit `rubric_version` field (§5) or rely solely on the whole-document hash is
  undecided here.
- Whether an AI critique (secondary analysis) should appear in the same decision packet, and if so
  whether it is shown to Anthony before or after he commits his own verdict, is undecided. BUILD_SPEC
  §11 (row 4) requires outcome labels to stay hidden until a verdict is committed; an AI critique
  shown beforehand would need its own anchoring safeguard that has not been designed.
- Which, or how many, of the 36 judgment-heavy fixtures Anthony will actually review in a pilot is
  undecided here; this document proposes the format, not the sample.
- Whether the pilot should also cover the three existing WP1/WP2 example dev cases, or the 40
  `holdback_designate` trajectories, or stay confined to the 36 judgment-heavy commissioning
  fixtures, is undecided.
- No local model location, hardware target, or model call is proposed, decided, or implied anywhere
  in this document. Per the task's measured facts, no local model location has ever been explicitly
  permitted in any record, and this amendment does not change that.

---

## 7. Single-operator pilot plan skeleton

Three distinct states, never merged:

1. **Local freeze**: before Anthony records any answer, a manifest listing exactly which
   `fixture_id`s are in scope and their `review_source_sha256` values is written and hashed, inside
   this repository or the state root, under an explicit new path (proposed:
   `docs/receipts/wp3/pilot-a1/`, not created by this document). This is "a local freeze receipt, not
   a Zenodo/OSF registration or a public timestamp" (`docs/PROTOCOL.md:5`).
2. **Registry record**: a public preregistration is a later, separate, explicitly approved step.
   `docs/PREREGISTRATION_DRAFT.md:54`: "Publication and distribution: NOT GRANTED." This amendment
   does not change that and does not request it.
3. **Public release**: further removed still, gated by `AGENTS.md`'s "Work authority" section (no
   public repo, license, or publication without explicit approval) and `docs/DECISIONS.md:31` (D25):
   "A local preregistration freeze is not a public registration, and a good result is not deployment
   approval."

**No pooling.** BUILD_SPEC §1.3 (`BUILD_SPEC.md:36`): "Every report declares exactly one source class
per run... Never pool these classes." Any report this pilot produces is labeled
`single_operator_exploratory_pilot` (a new, distinct label; not `scripted_instrument`, not
`model_observation`, not `synthetic_statistical_fixture`, and not to be merged with any of them) and
is kept separate from: the WP3 development-commissioning results already on record
(`docs/receipts/wp3/README.md`), any later confirmatory results, and any later transfer/replication
results (for example Jetson, reserved as "a later separately approved study" by
`docs/DECISIONS.md:27`, D21). A later confirmatory plan is a **separately frozen** preregistration
(`docs/PROTOCOL.md:12,15`: "A design revision creates a new plan/version. It never overwrites the
plan that produced a run... Reuse of exposed roots is development, not a fresh test"), not a
relabeling of this pilot's material (`BUILD_SPEC.md:186`: "Pilot cases/results cannot be relabeled
confirmatory").

## 8. Exact changes needed to later execution prerequisites (proposed; added by the lead)

Today a pilot cannot launch without reviews that one person cannot supply. These are the minimum
changes that would allow a **single-operator exploratory pilot**, and only that. Each is a
separate decision.

**Prerequisites the amendment would change:**

| Prerequisite (source) | Today | Proposed for the single-operator exploratory pilot only | Confirmatory and independent claims |
|---|---|---|---|
| PROTOCOL §1 step 1 (line 9): "obtain independent semantic review where required" before the pilot plan is frozen | cannot be met: no second reviewer | Anthony reviews the 36 judgment-heavy fixtures as the sole operator. A new status `single_operator_reviewed` is recorded beside the existing `pending_no_human_reviews`. Independent semantic review stays **pending** | unchanged: two independent reviewers |
| BUILD_SPEC:354 "commissioned relevant evaluator" | lifecycle ceiling `mechanically_validated`; formal blocked (no custodian) | pilot launch may cite `mechanically_validated` plus `single_operator_reviewed`, with `independent_holdback=false` stated in the plan. **Or**, if Anthony prefers, formal commissioning first, via the Anthony-held custody option (`A1_CUSTODY_ANTHONY_HELD.md`) | unchanged: `instrument_commissioned` still needs formal = passed **and** independent semantic review |
| BUILD_SPEC:354 "approved corpus/reviews"; B15 (DECISIONS:62) | the SFT gate needs one current human approval, with `rights_status` not `pending` | Anthony's approvals count as the one approval the gate already needs, labelled `single_operator`. **Rights status must also move from `pending`** (for example to `approved_for_local_use`). That is a **separate rights decision**, distinct from choosing a distribution license | unchanged |
| BUILD_SPEC:354 "preregistered pilot plan"; PROTOCOL line 5 | none exists | a **local freeze** (hash) of the single-operator pilot plan is enough to launch the exploratory pilot. A registry record is a later, separate step | a separately frozen confirmatory plan, before confirmatory exposure |
| PROTOCOL §9 two independent reviews per judgment-dependent confirmatory case | not reachable | not applicable to an exploratory pilot. **The pilot publishes no confirmatory headline** (PROTOCOL §1 step 3) | unchanged |

**Prerequisites that do not change:** split audit, match audit, tokenizer label-mask audit,
explicit selected checkpoint, finite budgets, and human run approval bound to the plan hash
(BUILD_SPEC:354). Each remains its own separate permission (see `A1_GATES.md`).

**The label on every pilot result:** evidence class `model_observation`, report label
`single_operator_exploratory_pilot`. Pilot results are never pooled with instrument tests,
confirmatory results or transfer results.

## 9. Single-operator pilot plan: fields to freeze (skeleton, added by the lead)

PROTOCOL §1 step 2 (line 10) says a pilot plan freezes objectives, cases, training recipe, runtimes,
workload, analysis and abort rules. This skeleton lists each field and what fills it. **No value is
filled here.** Freezing it (local hash first) is a later step, after the listed decisions exist.

| Plan field | Proposed content for a single-operator exploratory pilot | Filled by / blocked on |
|---|---|---|
| Objectives | variance and feasibility only (PROTOCOL §1 step 3); effect estimates described, no confirmatory claim; the three measurement dimensions reported separately if `A1_MEASUREMENT_AMENDMENT.md` is adopted | Anthony's approval of this amendment |
| Label and evidence class | `single_operator_exploratory_pilot`; `model_observation`; never pooled | this amendment |
| Cells | the six PROTOCOL §3 cells unchanged (B0, B1, P0, P1, C0, C1); the ICL cell optional | unchanged |
| Cases | pilot-split roots, newly authored, split-audited against the development and commissioning material; any MOA/ESS-motivated case carries a provenance disclosure | corpus authoring (none exists yet) |
| Corpus and reviews | P and C training sources reviewed by Anthony as `single_operator`; rights moved off `pending` for local use | the rights decision; Anthony's reviews |
| Evaluator | `hs-evaluator/0.2.0` (or an approved later version); lifecycle `mechanically_validated` plus `single_operator_reviewed`, or formal commissioning if custody is established first | §8; the custody decision |
| Checkpoint, tokenizer, template, quantization, runtime | exact file identities after a location grant | `A1_GATES.md` §3 permissions |
| Training recipe and seeds | the matched P/C fields (BUILD_SPEC §10); seeds from the candidate budget | `A1_GATES.md` §4 |
| Workload and budgets | a frozen episode count, call, token, time and disk caps; smaller than the PROTOCOL §5 candidate if one reviewer is to carry it | Anthony's decision (§4b) |
| Human review design | which outputs Anthony reviews (all, or a preregistered cell-blind random sample); unreviewed outputs stay `pending_review` in the denominators | Anthony's decision (§4b) |
| Analysis | PROTOCOL §7 candidate estimators as description only; margins stay candidates; no post-hoc tests presented as confirmatory (PROTOCOL §5) | unchanged candidates (`A1_GATES.md` §2) |
| Abort and stopping rules | PROTOCOL §8 stops (leak, unapproved exposure, base mutation, evaluator failure, schema drift, training divergence, budget overrun; no unattended restart) and the candidate 0.05 missingness trigger (PROTOCOL §6) | unchanged candidates |
| Output locations | a unique directory under `HS_STATE_ROOT` | the plan freeze |
| Run approval | Anthony's approval bound to the frozen plan hash (BUILD_SPEC:354) | the final gate |

---

## Classification

| Proposed change | Category | Reason |
|---|---|---|
| Add a `single_operator` review-mode label recorded alongside any `Review` produced under this pilot | needs implementation | New convention; no code today distinguishes single-operator from independently-reviewed |
| Check `len(distinct reviewer_refs) >= 2` wherever a future "independently reviewed" claim is made, and label anything with fewer `single_operator_reviewed` | needs implementation | Closes the gap in §1's "Discovered conflict"; touches WP4, not yet built |
| Refuse (or flag) `agreement()` output when both rating lists share a `reviewer_ref` | needs implementation | `agreement()` (`commissioning/agreement.py`) has no identity parameter today |
| Compact decision-packet format (§4 table) | needs implementation | Part of WP4 review export/import, `not_started` per `docs/ACCEPTANCE.md` |
| Local freeze manifest of in-scope fixtures and hashes before any review is recorded | needs implementation | New file/script; not created by this document |
| Add an explicit `rubric_version` field vs. relying on the whole-document hash | needs a separate decision from Anthony | Small design choice, not blocking, flagged in §5 |
| Which/how many of the 36 fixtures Anthony reviews in the pilot | needs a separate decision from Anthony | Sample selection is his call, not the builder's |
| Whether to compute/report a same-person test-retest statistic | needs a separate decision from Anthony | Distinct from kappa; needs explicit labeling if done at all |
| Public preregistration or release of any pilot result | needs a separate decision from Anthony | Explicitly NOT requested here; `PREREGISTRATION_DRAFT.md:54` stays "NOT GRANTED" |
| Using pilot results to inform a later MOA/ESS decision | needs a separate decision from Anthony | Reserved by Anthony's own words; out of scope here and MOA/ESS repositories were not opened to produce this document |
| Adopt the §8 prerequisite changes for the single-operator exploratory pilot only | needs a separate decision from Anthony | changes what a pilot launch may cite; confirmatory and independent requirements are unchanged |
| A `single_operator_reviewed` semantic-commissioning status beside `pending_no_human_reviews` | needs implementation | `SEMANTIC_STATUSES` in `commissioning/contract.py` has only the pending value today |
| Move corpus `rights_status` off `pending` for local use | needs a separate decision from Anthony | a rights decision, distinct from selecting a distribution license |
| Pilot workload size, or a preregistered review sample (§4b) | needs a separate decision from Anthony | set in the frozen pilot plan, not here |
| Freeze the §9 pilot plan (local hash) once its fields are filled | needs a separate decision from Anthony | the freeze follows the decisions its fields depend on |
| This document itself | documentation-only | It is the proposal being classified |

## Exact permission requested

There are two separate approvals. Anthony may grant, narrow or refuse each one on its own:

> **(1) Rule:** "I approve Amendment A1 single-operator mode for an **exploratory pilot only**, as
> written in A1_SINGLE_OPERATOR_PILOT.md §2, §3 and §8. My reviews are recorded as
> `single_operator` and never count as two independent reviews. No inter-rater statistic is
> computed from my reviews alone. Independent semantic review, formal commissioning and every
> confirmatory requirement stay as they are."

> **(2) Implementation:** "Implement the `single_operator` review label, the
> `single_operator_reviewed` status, the distinct-reviewer check (§5), the `agreement()` refusal on
> a shared `reviewer_ref`, and the decision-packet format (§4), with tests. No review is recorded
> and no pilot is launched by this approval."

Neither approval covers:

- the rights decision;
- the pilot workload;
- a checkpoint, inference or training;
- a registry record or public release;
- anything involving MOA/ESS.

Without an approval, **none of this is authorized. This document is informational.**
