# Review packet A1: WP3 reconciliation, single-operator pilot, MOA/ESS motivation, measurement and custody

> **What this is.** This is a decision packet for Anthony, prepared 2026-09-28 on branch
> `wp3/amendment-a1`, cut from the WP3 head `0d85909`. It is local only, and documentation only.
> **Nothing in it is approved or enacted.** Each decision below is separate, bounded, and stated
> in words Anthony can approve, narrow or refuse.

Prepared by the MacBook seat (claude-opus-5-5, lead). Four documents were drafted by Sonnet
subagents, each checked by a second Sonnet verifier, then reviewed and corrected by the lead. The
MOA/ESS document, the reconciled-state document and this index were written by the lead.

**Boundaries kept while preparing it:**

- no training data added;
- no historical receipt altered;
- no model called;
- the repositories not connected, and MOA/ESS behaviour not modified;
- nothing pushed or published;
- no Stack write;
- no disk scanned for model files.

MOA was read at five files, listed in the exposure record. ESS was not read at all; only its HEAD
commit was taken from git metadata.

## Contents

| Document | What it gives Anthony |
|---|---|
| `A1_WP3_RECONCILED_STATE.md` | WP3's exact commits, how it relates to main, the receipts under review with hashes, the stale "WP3 not started" statements, and three proposed standing rules for preserving the work |
| `A1_MOA_ESS_MOTIVATION_AND_EXPOSURE.md` | The research motivation, bounded to two cited MOA receipts, the research question, what MOA/ESS may and may not be used for, and the exposure record |
| `A1_MEASUREMENT_AMENDMENT.md` | Three separately reported dimensions; an evidence-status × response matrix (supported / unsupported / contradicted / not assessable × asserted / qualified / withheld); paired controls; an always-refuse control; prospective versioning only |
| `A1_SINGLE_OPERATOR_PILOT.md` | Every two-reviewer gate in the repo, what a single-operator exploratory pilot would change and not change, the review burden, the exact prerequisite changes, and a pilot-plan skeleton |
| `A1_CUSTODY_ANTHONY_HELD.md` | Three authoring options, what an access boundary actually requires, the seal/plan/run procedure, what would establish custody versus assert it, and the implementation gaps |
| `PRIOR_DECISIONS.md` | The gate-shape law's prior-decisions line for every decision: Anthony's earlier rulings of the same shape (quoted, with pointers, re-opened), or "no prior ruling found" with the searches named |
| `A1_GATES.md` | License (pending), every numerical threshold as a candidate with its consequence, the checkpoint/runtime permission request, a training-plan template with every field unset, and preregistration states |

## Findings surfaced while preparing the packet

These are facts about the current code and records. None was acted on.

1. **Reviewer independence is prose, not code.** No code checks that two reviews come from two
   people. `agreement()` would compute a Cohen's kappa over one person's ratings entered twice.
   (Pilot §1.)
2. **The holdback run exposes the holdback.** A formal `hs commission run` writes full holdback
   bundles (task text, predicate tree, scripted actions) next to its report, and `report.html` links
   to them. "The builder sees only the report" is operator discipline today, not a tool boundary.
   (Custody §2.1.)
3. **The custody code accepts a lower bar than Anthony's.** `load_custody` grants
   `independent_holdback=true` for a free-text statement, a matching hash, and two directory checks.
   Anthony's bar also requires real access-boundary evidence. (Custody §3.)
4. **Only C3 offers an abstention channel.** Every other suite v1 class lacks `decline`. A decline
   there is a denied tool call that ends the run `not_evaluable`. So an always-refuse control needs
   new cases. (Measurement §1c, §3.)
5. **A draft error, corrected before this packet.** The first measurement draft mapped the four
   evidence labels onto the evaluator's internal branches. That conflated forbidden acts and
   incomplete runs with contradicted or unassessable claims. The lead withdrew it; the correction
   is noted in the document. (Measurement §2.)
6. **This builder seat is not independent of ESS.** Earlier MacBook Claude seats built ESS v2 and
   v3, and this seat's memory carries that history. (Exposure §6.2.)
7. **No model location has ever been permitted.** So no checkpoint can be recommended until
   Anthony names a directory on a named machine. (Gates §3.)

## Classification (consolidated)

**Documentation-only:**

- the reconciled state and its three standing rules;
- the MOA/ESS motivation and exposure record;
- restating candidate thresholds and the license status;
- the custody procedure as it exists today.

**Needs implementation**, each after its own approval:

- measurement:
  - case-level evidence-status fields;
  - response classification and the three report sections;
  - separate `guard_withheld` / `model_abstained` fields;
  - the `verdict_path` diagnostic;
  - the `supplement_a1_measurement` suite, with an abstention channel and the always-refuse control;
  - sabotage controls for the new fields;
- single-operator:
  - the `single_operator` label and `single_operator_reviewed` status;
  - the distinct-reviewer check;
  - `agreement()` refusing a shared `reviewer_ref`;
  - the decision-packet format;
  - the local pilot-scope freeze;
- custody:
  - structured access-boundary and author fields;
  - a redacted run-output mode;
- MOA/ESS: a structured provenance field for motivated cases.

**Needs a separate decision from Anthony:** everything in the next section.

## Decisions requested, in a workable order

Each decision is independent; approving one approves nothing else. **Each row's prior-decisions line
is in `PRIOR_DECISIONS.md`** (same numbering). Where a source document supplies approval wording, the
index quotes it **verbatim**. Rows marked *(index wording)* have no quote in their source document.

**Status after Anthony's rulings of 2026-09-28** (`PRIOR_DECISIONS.md`, last section):

- **Ruled.** #3's exposure part (the house exposure ledger, `8ac7c661`; this seat's nine events
  are filed) and the Astra question (`149f1cfa`).
- **Conformed and awaiting a yes or no.** #4, #6, #7 and #8, reworded to carry over the principles
  of rulings `c96025ad`, `a764ada2` and `06d942da`, as Anthony directed.
- **Restate existing law.** #1 and the prospective-only part of #5.
- **Clear precedents in other rooms.** #2, #9, #10 and #11.

| # | Decision | Exact words to approve | Source |
|---|---|---|---|
| 1 | Accept the reconciled WP3 state and its standing rules | *(index wording)* "I accept A1_WP3_RECONCILED_STATE.md and its three standing rules as a DECISIONS entry." | Reconciled §4 |
| 2 | Merge `wp3/commissioning` into main | *(index wording)* "Merge wp3/commissioning at 0d85909 into main." Separate from #1 | Reconciled §1 |
| 3 | Accept the MOA/ESS motivation (exposure is **ruled**: the Stack ledger) | "I accept A1_MOA_ESS_MOTIVATION_AND_EXPOSURE.md as documentation of the study's motivation, with exposure recorded on the Stack exposure-ledger. This does not authorize any MOA/ESS data use, repository connection or transfer study." | Exposure, end |
| 4 | The grid as the reviewer's checklist, plus the evidence-status and guard/abstention fields (**conformed** to `c96025ad`) | "Adopt the evidence-status × response grid as the reviewer's checklist under §7 of `A1_MEASUREMENT_AMENDMENT.md` (conformed to ruling c96025ad), and the case evidence-status fields and separate guard/abstention report fields of §2 for a new evaluator version; implement and test them without rescoring suite v1." | Measurement §7, end |
| 5 | Cut the new evaluator version | "Cut `hs-evaluator/0.3.0` per §5, applied prospectively only; all existing bundles continue to replay under their recorded evaluator version." | Measurement, end |
| 6 | Build the measurement supplement (**conformed** to `a764ada2`; figures set from his stance) | "Build `supplement_a1_measurement` per §3 and §8 (conformed to ruling a764ada2): 12 groups, 60 trajectories (48 assert/withhold plus 12 qualified), at most 12 judgment-heavy, grown only by a new freeze, as its own generator/suite/plan/report, never merged into `cases/commissioning_suite_v1/`." | Measurement §8, end |
| 7 | Single-reviewer rule for an exploratory pilot (**conformed** to `06d942da`) | "I approve Amendment A1 single-reviewer mode for an **exploratory pilot only**, as written in A1_SINGLE_OPERATOR_PILOT.md §2, §3 and §8 as conformed by §10 (ruling 06d942da). My reviews are recorded in my own words with the case hash, labelled `single-reviewer`, and never count as two independent reviews. No inter-rater statistic is computed from my reviews alone. Independent semantic review, formal commissioning and every confirmatory requirement stay as they are." | Pilot §10, end |
| 8 | Implement the single-reviewer safeguards | "Implement the `single-reviewer` label (§10), a `single_reviewer_reviewed` semantic-commissioning status beside `pending_no_human_reviews`, verdict records in my own words bound to the case hash, the distinct-reviewer check (§5), the `agreement()` refusal on a shared `reviewer_ref`, and the decision-packet format (§4), with tests. No review is recorded and no pilot is launched by this approval." | Pilot, end |
| 9 | Corpus rights for local use (not a distribution license) | *(index wording)* "Corpus material may be marked approved_for_local_use; no distribution license is selected." | Pilot §8 |
| 10 | Custody: authoring option, access-boundary type, run-output exposure boundary | Anthony's choice of option A, B or C, the boundary type, and what the builder may see (four questions at the end of the custody document; house precedent: the 2026-08-06 canary draw) | Custody, end |
| 11 | Name a model directory and machine | "Use [directory path] on [MacBook \| Mac Studio M4 Max 36GB \| other named machine] as the model root for `hs doctor --models`." `hs doctor --models` itself is not implemented yet (WP5), so this grants the location only. Tokenizer audit, inference, smoke test and training stay separate | Gates §3.4 |

**Still pending and not requested in this packet:**

- the distribution license;
- numerical margins;
- tokenizer audit, inference, hardware smoke test and training;
- the pilot workload and review sample;
- any registry record or public release;
- any MOA/ESS transfer study;
- independent semantic validation;
- specialist controls-engineer review;
- **a send-record audit of what the house relayed to Astra** (Stack and Slack). Under ruling
  `149f1cfa`, Astra is treated as exposed to MOA/ESS until that audit shows otherwise;
- **whether `hs commission run` should file its own `exposure-ledger` entry** in formal mode
  (`docs/HOLDBACK_CUSTODY.md`);
- **how to separate the causes of a wrong or unsupported answer** (comprehension, policy mapping,
  domain knowledge, output construction, evaluator defect). This is an undecided design question.
  It needs a subject model to be meaningful and is distinct from the grid (Measurement §4). Only the
  evaluator-defect part has a working tool today: the sabotage controls.

## Stopping point

The packet stops here. Nothing further happens on this branch until Anthony decides.
