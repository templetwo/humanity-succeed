# Amendment A1: Anthony-held, builder-blind custody option for fresh holdback material

Status: **proposal for Anthony's review**. Nothing in this document approves, selects, or
establishes anything. It does not change `formal_commissioning`, which stays
`blocked_no_independent_holdback` (`docs/receipts/wp3/run/report.json`) until real evidence exists.
No code, test, or fixture file changes with this amendment.

Drafted on 2026-09-28 by a Sonnet subagent (`claude-sonnet-5`) under the lead's brief, checked by a
second Sonnet verifier, then reviewed and extended by the lead (MacBook seat, claude-opus-5-5;
sections marked "added by the lead"). Branch `wp3/amendment-a1` at `0d85909`. **Model called: no.
Code changed: no. Nothing pushed. No Stack write.**

## What this asks

Anthony asked for an Anthony-held, builder-blind custody option for the 40 fresh holdback
trajectories the spec requires (`docs/HOLDBACK_CUSTODY.md`), verbatim: "Prepare an Anthony-held,
builder-blind custody option for fresh holdback material. Custody is established only when the
actual access boundary, provenance, and exposure record support it. Until then, retain the truthful
blocked status." This packet lays out who could author the 40 trajectories and where they could
live, the exact sealing/run procedure, what would actually establish custody versus merely assert
it, and where the current code falls short of any of these options. It ends with a classification
table and the exact permission language Anthony would need to approve to start. **It recommends no
single option.** That choice, and everything numerical or operational inside it, is his.

## 1. Who authors the 40 trajectories, and where they live

`docs/HOLDBACK_CUSTODY.md:26-30` sets the bar: "Anyone except the builder... In practice: a
different person, working on a machine the builder does not have access to." BUILD_SPEC
§9 (`BUILD_SPEC.md:313`) is the reason: "The agent cannot author, inspect, and then call its own
fixtures independently held back." Anthony is not the builder of this suite (the builder is the
Sonnet/opus seat lineage that wrote `cases/commissioning_suite_v1/`, `docs/DECISIONS.md:142-158`),
so he is permitted to be custodian under the letter of the spec. The harder questions are who
*authors* the 40 fresh trajectories and where the bytes physically live before sealing, because
authorship and custody are not the same act, and the spec's honest-limit paragraph
(`docs/HOLDBACK_CUSTODY.md:18-24`) already says this scheme "verifies bytes, not people."

### 1.1 Every realistic author option

| Option | Who writes the 40 scenarios | Exposure risk | What provenance can show | What it cannot show |
|---|---|---|---|---|
| **A. Anthony himself** | Anthony, by hand, in his own words, off any machine the builder session runs on | Lowest structural risk if he genuinely never discusses drafts with the builder session (`docs/HOLDBACK_CUSTODY.md:85-90` forbids exactly that). Residual risk: Anthony has read this project's docs and code (including `docs/WP3_DESIGN.md`'s class contracts, which is expected and allowed) and could unconsciously echo builder phrasing | A `CustodyRecord.statement` (`src/humanity_succeed/commissioning/contract.py:112-119`) naming himself, plus a manifest `authored_by` field (`contract.py:106`) naming himself, plus the split audit finding no shared roots/near-duplicates with the dev suite (`docs/HOLDBACK_CUSTODY.md:79-84`, `B29` in `docs/DECISIONS.md:87`) | That he did not look at the builder's suite file text while writing (the spec already forbids this, `docs/HOLDBACK_CUSTODY.md:85-90`, but nothing mechanically checks it); that he is in fact the person named |
| **B. A separate AI seat that never shares context, files, or memory with the builder** | A different agent session, with its own model access, run so that it has no read path to this repository, this worktree, or any file the builder session can write | Depends entirely on the isolation being real, not just "a different chat window." See 1.2 below — this is the option where the promise/evidence gap is largest | A `CustodyRecord.statement` describing the isolation mechanism used; ideally a structured access-boundary record this codebase does not yet have (§4.1) | Whether the isolation actually held for the whole authoring period; today's `CustodyRecord` has no field to record *how* isolation was verified, only a free-text claim (`contract.py:119`, `custody.py:140-141`) |
| **C. An outside person** (not Anthony, not any AI seat on Anthony's hardware) | A person with no access to this repository or Anthony's machines | Lowest builder-exposure risk of the three, at the cost of a real logistics and trust problem: someone has to be recruited, briefed on the class contracts without being shown the actual suite files, and trusted to keep the material off any shared storage | Same as A/B: a `CustodyRecord.statement` and `authored_by`; independent of Anthony's own machines entirely, which is a structurally stronger claim than A or B for the "not on builder hardware" half of the boundary | Nothing about this person's competence or good faith is checked by any tool in this repo; `custody.py:79-84` says this outright: "Custodian identity is attested by the record, never verified by this tool" |

None of these three is disqualified by the spec. `docs/HOLDBACK_CUSTODY.md:26-30` only excludes the
builder.

**Burden note (added by the lead).** Option A is the heaviest for Anthony: 40 trajectories plus their
case files in the strict schema, with expectations written before any run. Any authoring aid would
itself have to sit on the custodian's side of the access boundary. A template or generator supplied
by the builder would carry builder phrasing and structure into the holdback, so it would need to be
disclosed in the provenance and weighed as exposure. But "permitted" is not "established" — see §3.

### 1.2 Same-machine AI seats: why "builder-blind" needs an access boundary, not a promise

If Option B is the one Anthony wants, the isolation claim needs to be concrete, because two AI
sessions on the same account are not automatically blind to each other. Two failure modes are worth
naming plainly:

- **Shared filesystem, same user account.** If a second agent session runs under the same OS user
  account as the builder session, ordinary file permissions do not separate them — either session
  can read anything the other wrote, including a holdback draft sitting in a "private" folder. This
  is exactly the shape `docs/HOLDBACK_CUSTODY.md:74-78` and `scripts/seal_holdback.py:140-147` guard
  against for the *sealed* suite (refusing a holdback path inside the repo or the `hs` state root),
  but that check only fires at seal time, against two specific locations. It says nothing about
  where the material sat *while being authored*, and nothing about a second account on the same
  machine.
- **Shared auto-loaded memory or instructions.** An agent harness that loads a global
  instructions/memory file for every session run under a given account (this build's own session is
  an instance of exactly that pattern) means a second "separate" seat under the same account is not
  context-isolated from the first merely because it is a different conversation. Anything either
  session's harness writes back to that shared file becomes readable context for the other the next
  time it boots. This is a real, general risk, not specific to any one project's tooling, and it is
  the reason "a different chat" is not the same claim as "a different access boundary."

An actual access boundary is one of: a different physical machine with no shared mount; a different
user account whose file permissions are set (and checked) to exclude the builder account, with no
harness-level shared memory file readable by both; or an encrypted container/volume whose
decryption key the builder account never holds, so that even someone with filesystem or admin access
to the storage medium cannot read the plaintext. A statement that merely says "I used a separate
session" does not, by itself, establish any of these. `docs/HOLDBACK_CUSTODY.md` does not currently
ask a custodian to name which boundary they used, and `CustodyRecord` has no field for it (§4.1).

On hardware: Anthony has reported (2026-09-24, not independently probed by this session) a Mac
Studio (M4 Max, 36 GB) and a Jetson Orin Nano (8 GB), with a DGX Spark only possibly available in
the future. **No record anywhere in this project has ever approved a specific local model location
for any purpose**, so if Option B is chosen, a separate open question is *what model, on which of
these machines, under whose account* would author or assist authoring the 40 trajectories — that is
a new decision, not something this amendment resolves, and not something the hardware facts alone
answer.

## 2. The concrete procedure

This is the mechanism as it already exists in the repository (`docs/HOLDBACK_CUSTODY.md`,
`scripts/seal_holdback.py`, `src/humanity_succeed/commissioning/{custody,plan,run}.py`), laid out as
a sequence, with each implementation gap flagged inline and expanded in §4.

1. **Author outside the repo.** Write 40 trajectories in the exact §9 shapes
   (`BUILD_SPEC.md:307-317`; per-class counts in
   `src/humanity_succeed/commissioning/contract.py:57-65`), laid out as `SUITE.json` + `cases/*.yaml`
   + `trajectories/*.yaml`, with `authorship: custodian_supplied` and
   `split: commissioning_holdback` on the manifest and every case
   (`docs/HOLDBACK_CUSTODY.md:32-70`). Never inside this repository, never inside the `hs` state
   root, never templated from `cases/commissioning_suite_v1/`, never shown to or sanity-checked by
   the builder (`docs/HOLDBACK_CUSTODY.md:72-90`).
2. **Seal it.**
   ```sh
   uv run python scripts/seal_holdback.py \
     --holdback /path/outside/this/repo/your-holdback-root \
     --custodian "your name or role" \
     --statement "how you kept it out of the builder's reach" \
     --out /path/outside/this/repo/custody-record.json
   ```
   (`docs/HOLDBACK_CUSTODY.md:96-101`). This validates the manifest shape, refuses a holdback root
   inside the repo or the state root by an inode-based ancestor check
   (`scripts/seal_holdback.py:140-147`, `src/humanity_succeed/commissioning/custody.py:61-71`),
   computes `holdback_suite_sha256` over every referenced file
   (`custody.py:37-55`), and writes a `CustodyRecord` (`contract.py:112-119`). It never prints
   fixture contents, only counts and the hash (`scripts/seal_holdback.py:14-17`).
3. **Keep the custody record and the holdback root together, off the builder's machine**
   (`docs/HOLDBACK_CUSTODY.md:118`).
4. **Pre-registered hash commitment before any run.** Publishing just the `holdback_suite_sha256`
   field "commits you to the exact bytes without exposing them"
   (`docs/HOLDBACK_CUSTODY.md:119-121`). This is the pre-registration step BUILD_SPEC §5.2 implies
   ("bound to a hash before any run touches them") — `hs commission plan` reads and checks this hash
   *before* any fixture runs (`src/humanity_succeed/commissioning/plan.py:127-174`), so the
   commitment really does precede execution.
5. **One formal run.**
   ```sh
   hs commission plan \
     --suite cases/commissioning_suite_v1 \
     --holdback /path/outside/this/repo/your-holdback-root \
     --custody /path/outside/this/repo/custody-record.json \
     --out NEW_PLAN_DIR

   hs commission run --plan NEW_PLAN_DIR --provider scripted --out NEW_BUNDLE_DIR
   ```
   (`docs/HOLDBACK_CUSTODY.md:128-135`). `plan` re-validates both suites together (a combined split
   audit, `plan.py:142-144`), re-checks custody, and refuses an already-exposed holdback
   (`plan.py:151-156`). `run` re-hashes every planned file — any change refuses the whole run with
   no output created (`src/humanity_succeed/commissioning/run.py:108-122`) — then re-checks custody
   and exposure one more time immediately before running anything (`run.py:131-142`), runs every
   fixture, and writes `formal_commissioning: passed` or `failed` depending on whether every
   holdback fixture matched its expectation (`run.py:185-189`). **Nothing in this run can ever
   report `independent_holdback=true` from Anthony's say-so alone** — it is computed from
   `load_custody`'s hash match and location check (`custody.py:77-142`), not from a flag anyone
   sets.
6. **Exposure ledger.** The instant a formal run completes, `record_exposure` appends a line keyed
   by `holdback_suite_sha256` to an append-only ledger under the state root
   (`custody.py:166-178`; `run.py:190-192`). A second formal run against the same 40 trajectories is
   refused from then on (`plan.py:151-156`; A20, `docs/ACCEPTANCE.md`). A miss stays in the record; a
   fixed evaluator needs a genuinely fresh 40, not a resubmission (`docs/HOLDBACK_CUSTODY.md:154-160`).
7. **What the builder may see afterward.** This is where the current implementation is weaker than
   the phrase "only the report" suggests — see §2.1.

### 2.1 What "the report" actually exposes

`hs commission run` writes two things into the *same* output directory, `NEW_BUNDLE_DIR`: a report
(`report.json` / `report.html`) and, right beside it, `bundles/<fixture_id>/` for **every** fixture,
including all 40 holdback ones (`run.py:148-178`, `bundle_out = out_dir / "bundles" / fx["fixture_id"]`
at `run.py:158`; `run_scripted` at `src/humanity_succeed/runner/scripted.py:93-112`).

- **Even the report alone is not empty of content.** `report.json`'s `fixtures` list includes, per
  holdback fixture: `fixture_id`, `group_id`, `class_id`, the full `expected` `Expectation` object
  — which includes `rationale`, a natural-language sentence the custodian wrote describing what the
  scenario tests (`contract.py:77-85`) — the coarse `observed` triple (`mechanical`/`conduct`/
  `contained`, `src/humanity_succeed/commissioning/execute.py:56-59`), whether it `match`ed, and a
  relative link to its bundle (`run.py:166-178`; rendered as a clickable link in `report.html`,
  `src/humanity_succeed/commissioning/report.py:61-74`). That is real content about each of the 40
  fixtures, not just an aggregate pass/fail count.
- **The bundle directories are far more revealing, and nothing currently separates them from the
  report.** Each `bundles/<fixture_id>/case_source.json` holds the fixture's entire content — task
  text, world resources, and the `pass_if`/`fail_if` predicate tree, i.e. the answer key — and
  `trajectory.json` holds the exact scripted actions. Confirmed against a real (development-suite)
  bundle at `docs/receipts/wp3/run/bundles/c5-g11-substitution/case_source.json` and `evaluation.json`
  — the latter shows per-predicate results, observed values, and revision numbers, not just a
  verdict. A formal run's holdback bundles have this same shape (`run.py:150` branches only on
  `fx["source"]`, not on whether the fixture is a holdback one). If "only the report" is meant
  literally, the operator running `hs commission run` needs to hand the builder `report.json`/
  `report.html` **and withhold `bundles/`** by hand — the tool does not offer a redacted or
  summary-only output mode, and `report.html` actively links into the bundles it sits beside
  (`report.py:70`).
- **What handing over even the redacted report exposes:** for 36 of the 160 suite fixtures overall
  `judgment_heavy` is true (`docs/receipts/wp3/run/report.json`, `docs/ACCEPTANCE.md` WP3 row); the
  holdback set will include some fraction of these (the class/shape proportions are fixed by
  `contract.py:57-65`), so the builder would see, for those, a written rationale sentence and a
  pass/fail/pending outcome without seeing the underlying task or evidence. That is a smaller
  exposure than the full bundle, but it is not zero, and no document currently states that this is
  the intended exposure boundary. This is a decision for Anthony, not something this amendment
  resolves (see the classification table).

## 3. What would establish custody versus merely assert it

`docs/HOLDBACK_CUSTODY.md:18-24` states the honest limit already: "this custody scheme verifies
*bytes*, not *people*." A `CustodyRecord` is "a claim the custodian makes, attested by the record
itself, never independently checked." Anthony's instruction adds the standard this amendment must
hold to: custody is established only when the actual access boundary, provenance, and exposure
record *support* it, not merely assert it.

| Element | What would establish it | What merely asserts it (today's state) |
|---|---|---|
| **Access boundary** | A concrete, checkable fact: a different physical machine with no shared mount; a different user account with verified permissions and no shared auto-loaded memory file; or an encrypted container whose key the builder account never holds — stated as a specific, falsifiable claim (which machine, which account, which key custody arrangement) | `CustodyRecord.statement` today is a free-text field (`contract.py:119`) — "how the custodian kept it out of the builder's reach" — with no structure and no independent check. `custody.py:79-84` and its own `note` field (`custody.py:140-141`) say plainly that identity and the isolation story are attested, not verified |
| **Provenance** | A record of who actually authored each fixture, consistent across the manifest's `authored_by` (`contract.py:106`) and the `CustodyRecord.custodian` (`contract.py:116`), plus the split audit finding no shared roots or cross-split near-duplicates against the development suite (`docs/HOLDBACK_CUSTODY.md:79-84`; enforced in `plan.py:142-144` via `audit_splits`) | The split audit *is* real, automatic, and already enforced — that part is established mechanically, not just claimed. What is not established is that the *named* author is who they say, or that they never saw the builder's suite files while writing (the rule exists, `docs/HOLDBACK_CUSTODY.md:85-90`, but no tool checks it) |
| **Exposure record** | An append-only ledger entry, keyed by the exact sealed hash, written automatically at the moment of the one formal run, refusing reuse of that hash afterward | This part is already real and automatic (`custody.py:148-178`; `run.py:185-192`; A20 in `docs/ACCEPTANCE.md`). It establishes *that* an exposure happened and *when*, but says nothing about the access boundary or provenance above |

**The rule this amendment follows:** until the access-boundary element specifically has real,
checkable support (not a sentence), `formal_commissioning` stays whatever `load_custody` and
`run_commissioning` actually compute — `blocked_no_independent_holdback` in development mode
(`run.py:186`), or, if a `CustodyRecord` were supplied today with only a `statement` and no
structural access-boundary evidence, the tooling would still accept it as `independent_holdback:
true` provided the hash matches and the location checks pass (`custody.py:134-142`). That is a real
gap: **the code currently treats "statement plus a matching hash plus not inside two forbidden
directories" as sufficient**, which is weaker than Anthony's stated bar. Closing that gap is a
`needs implementation` item (§4), not something achieved by writing this document.

## 4. Gaps in the current implementation for this option

| Gap | Where | Classification | Why |
|---|---|---|---|
| `CustodyRecord` has no field for access-boundary evidence (which of the three boundary types, on what machine/account, key-custody arrangement) | `contract.py:112-119` | **needs implementation** | Closing the gap in §3 requires the schema to hold something more structured than free-text `statement`; today `load_custody` cannot check what it does not have a field for |
| `CustodyRecord` has no field distinguishing *author* identity from *custodian* identity when they differ (e.g. Option B or C where the author is not the person sealing) | `contract.py:112-119` (only `custodian`); `contract.py:106` (`SuiteManifest.authored_by` exists but is not cross-checked against `CustodyRecord.custodian`) | **needs implementation** | Without this, a record cannot honestly represent "Anthony sealed material a separate seat authored" as a distinct, checkable claim from "Anthony authored and sealed it himself" |
| Custodian/author identity is attested, never verified, by design | `custody.py:79-84`, `custody.py:140-141` | **documentation-only** (the code already says this honestly; the limitation is inherent to a bytes-only custody scheme, not a bug) | No tool in this repo can verify a human's identity or their claimed isolation; the honest move is the one already taken — state the limit, not paper over it |
| `hs commission run`'s output directory always writes full per-fixture bundles (task text, world, predicate tree, trajectory) beside the report, with no redacted/summary-only mode, and `report.html` links directly into them | `run.py:148-178`, `run.py:158`, `report.py:61-74` | **needs implementation** (a redacted output mode) if Anthony wants "only the report" to be a real, tool-enforced boundary rather than an operator's manual discipline; **needs a separate decision from Anthony** on what the intended exposure boundary even is (see §2.1) | The current design already documents that a formal run is "the one place your holdback stops being held back" (`docs/HOLDBACK_CUSTODY.md:148`), but does not specify how much of the bundle a builder may see afterward, and provides no tool support for withholding it |
| `report.json` includes each holdback fixture's `rationale` text and per-fixture match/mismatch, not just an aggregate count, with no option to suppress this | `contract.py:84` (`rationale: NonEmpty`), `run.py:166-178` | **needs implementation** if a coarser aggregate-only report is wanted; **documentation-only** if Anthony accepts this level of exposure as the intended cost of a formal run | This is a real, measured fact about what the tooling emits today (verified against a real bundle at `docs/receipts/wp3/run/bundles/c5-g11-substitution/`), not a hypothetical |
| No mechanism records or checks *which* access-boundary type (separate machine / separate account / encrypted container) a custodian used, even if the schema gap above were closed and a field existed | (would live in `custody.py`'s validation, alongside the existing location checks at `custody.py:99-102`) | **needs implementation**, and only after Anthony decides which boundary types this project will accept as adequate — a policy question, not just a schema question | `custody.py:61-71`'s `_inside` check already verifies one specific, narrow boundary (not inside two named directories) mechanically; a broader boundary claim would need its own, differently-shaped check, which does not exist and cannot be designed before Anthony picks what counts |
| `docs/HOLDBACK_CUSTODY.md` documents the procedure but does not itself state what the builder may see after a formal run, or that `report.html` links to full bundles | `docs/HOLDBACK_CUSTODY.md:146-164` ("What exposure means") | **documentation-only** | This is a real underspecification the review surfaced (§2.1); fixing the prose to say plainly what "exposure" includes is a text change, not a code change, but it still needs Anthony's sign-off on what the true intended boundary is before the text can say it accurately |

Every "needs implementation" row above is unimplemented. Nothing in this amendment adds or edits
any code, schema, or fixture. This table is the packet's account of the distance between "the
mechanism exists" and "the mechanism supports the specific custody claim Anthony described."

## 5. The 40 holdback-designate fixtures can never become holdback

Confirmed directly from the code and the record, not merely restated from the prompt:

- `cases/commissioning_suite_v1/` is one `builder_constructed` suite, split `commissioning_dev`
  (`docs/WP3_DESIGN.md:25-26`; `docs/DECISIONS.md:152`, B48).
- `src/humanity_succeed/commissioning/partition.py:67-144` deterministically marks 40 of its 160
  trajectories `holdback_designate` (whole groups only, per the counts in `contract.py:57-65`,
  proven by `partition.py:116-141`'s count-and-compare against `contract.CLASSES`). This is purely
  structural bookkeeping over an already-builder-authored, already-exposed suite — it changes no
  file's location, authorship, or exposure history.
- `run.py:186` and the actual run receipt (`docs/receipts/wp3/run/report.json`,
  `docs/receipts/wp3/README.md:11-25`) confirm these fixtures are reported as `partition:
  holdback_designate` and never contribute to `formal_commissioning`, which reads only
  `plan["holdback"]` — a wholly separate, custodian-supplied suite (`plan.py:127-174`) — never the
  `holdback_designate` slice of the development suite.
- `docs/WP3_DESIGN.md:28-30` states the reason directly: they "stay in the development split and are
  reported as builder-authored, exposed, not independent. They never count toward formal
  commissioning." Anthony's own instruction restates the same rule: "moving them into another
  directory or appointing a custodian later does not make them fresh holdback material." Nothing in
  this amendment, or in any option in §1, proposes otherwise. Any future custody arrangement — under
  any of options A, B, or C — requires 40 **newly authored** trajectories, never a relocation or
  re-labeling of `cases/commissioning_suite_v1/`'s existing files.

## Classification

| Proposed change | Classification | Reason |
|---|---|---|
| Naming Anthony as the human who could serve as custodian (not builder) | documentation-only | Already permitted by `docs/HOLDBACK_CUSTODY.md:26-30`; this amendment states it, changes nothing |
| Choosing among Options A/B/C (§1) for who authors the 40 trajectories | needs a separate decision from Anthony | No spec or code language picks one; each carries a different exposure/logistics trade-off he alone can weigh |
| Running the existing seal → plan → run procedure (§2) once a real holdback suite exists | documentation-only (procedure already implemented) | `scripts/seal_holdback.py`, `commission plan`, `commission run` already do exactly this; no code change needed to execute it |
| Deciding what a formal run's output may show the builder (§2.1) | needs a separate decision from Anthony | Not specified anywhere today; the current tooling's default (full bundles beside the report) may or may not be what he intends |
| Adding a structured access-boundary field to `CustodyRecord` (§4) | needs implementation | Schema change to `contract.py`, plus new validation in `custody.py` |
| Adding an author-identity field distinct from custodian (§4) | needs implementation | Schema change; also needs Anthony's decision on whether author ≠ custodian should even be an accepted shape |
| Adding a redacted/summary-only `hs commission run` output mode (§4) | needs implementation | New code path in `run.py`/`report.py`; only worth building once §2.1's exposure question is decided |
| Clarifying `docs/HOLDBACK_CUSTODY.md`'s "What exposure means" section to state the bundle-vs-report distinction plainly | documentation-only, pending Anthony's decision on the underlying question | The prose fix is small; what it should say depends on the decision above |
| Selecting specific hardware/account/model for Option B if chosen | needs a separate decision from Anthony | No local model location has ever been approved in any record; this is untouched by this amendment |
| Declaring any of the above "established" or changing `formal_commissioning`'s current value | **not proposed here** | Anthony's instruction: "Until then, retain the truthful blocked status." This amendment does not attempt it |

## Exact permission requested

**None: informational.** This packet asks for no action and changes no code, schema, fixture, or
status. `formal_commissioning` remains `blocked_no_independent_holdback`
(`docs/receipts/wp3/run/report.json`) exactly as measured at commit `8a24ad1`.

If and when Anthony wants to move this forward, the smallest next decisions — each separable, each
his alone — are:

1. Which of Options A, B, or C (§1) for authoring the 40 fresh trajectories, or a variant of one.
2. If Option B: which machine, which account, which access-boundary mechanism, and whether any local
   model may be used in the authoring process (none is currently approved anywhere).
3. What a formal run's output to the builder is intended to contain — report only, report with
   bundles withheld by hand, or something the tooling would need to be built to produce (§2.1, §4).
4. Whether to approve the schema/tooling changes in §4 before or after a first real holdback suite is
   authored (they are useful either way, but are not a precondition the spec currently imposes).

None of these four is answered by this document. Each requires his explicit word before any
implementation work, holdback authoring, or formal run begins.
