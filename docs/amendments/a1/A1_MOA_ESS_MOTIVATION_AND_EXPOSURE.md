# A1: MOA/ESS as research motivation, and the exposure record

> **What this asks.** Anthony is asked to accept a *documentation-only* statement of why the
> master-operations-agent (MOA) and experion-station-sim (ESS) results motivate this study. It is
> not a finding that training will work. The document also records, as completely as this seat can,
> what MOA/ESS material the humanity-succeed authors and reviewers have already seen. Nothing here
> makes MOA/ESS a data source, a dependency or a test set.

Written by the MacBook seat (claude-opus-5-5) on 2026-09-28. **Model called: no. MOA and ESS were
read, not modified or connected. No Stack write.**

## 1. The three projects

- **experion-station-sim (ESS)** supplies synthetic plant observations.
- **master-operations-agent (MOA)** evaluates bounded assessments of those observations.
- **humanity-succeed** investigates whether a reviewed curriculum improves evidence-responsive
  conduct beyond matched procedural practice and prompt-supplied principles.

The repositories are not connected, and this amendment does not connect them.

## 2. The motivating observation (bounded)

Successful tool use and a valid response structure do not establish a substantively supported
decision. One specified campaign shows the gap:

- **MOA's frozen v0.7 policy-only DeepSeek holdout campaign** (MOA `receipts/v0.7/README.md` at
  `68aae66`).
- **Protocol and structure succeeded:** required reads 24/24; valid advice envelopes 24/24;
  correct input guards 6/6.
- **Content did not:** useful answers 7/24. The receipt states: "The 17 withheld usable answers
  failed candidate-content validation."
- **Its controls ran and passed first:**
  - the deterministic baseline scored 24/24 useful, 6/6 guards;
  - an always-refuse control scored 0/24 useful, 6/6 guards.
- **The receipt states its own limit:** the result is "agreement with authored policy labels, not
  an independently established process-truth or safety score". It also "does not establish cloud
  superiority, model incapacity, or a measured benefit over deterministic calculation".

This is a bounded result from one specified campaign. It is not a universal diagnosis of that
model, its family, or language models in general.

A content-validation failure does not by itself identify a *conduct* problem. It may reflect:

- task comprehension;
- policy mapping;
- domain knowledge;
- output construction;
- an evaluator defect.

The experimental design has to separate those possibilities (see `A1_MEASUREMENT_AMENDMENT.md`),
not read every wrong answer as an integrity failure.

## 3. The proposed research connection

> Can a reviewed curriculum improve what a model does with available evidence (not merely its
> ability to perform the interaction protocol) beyond what the same principles in a prompt and
> matched procedural training achieve?

This does not change the study's primary comparisons. The six cells stay B0, B1, P0, P1, C0 and
C1, and the co-primary contrasts stay `H1: C0 − P0` (curriculum beyond matched procedural
practice) and `H2: C1 − B1` (curriculum beyond the same principles in the prompt). These are in
`docs/PROTOCOL.md` §3, lines 27–35. MOA's deterministic baseline is an
external reference and control in MOA's own experiments. It is not a replacement arm here, and it
does not enter this study.

## 4. The guard/abstention boundary (the source-map receipt)

MOA's `receipts/source-map-v2/README.md` (at `68aae66`) records the following run:

| Binding | Value |
|---|---|
| Provider | the deterministic baseline, **models called: 0** |
| Simulator revision | ESS `bfed001` |
| Result | 8/10 useful, 8/8 guards |
| Why | both `cooling-loss` seeds abstained with reason `quality`; TIC202 read 103.125 °C with quality `uncertain` |

- The historical 10/10 useful and 8/8 guard score stays attached to its original simulator pin,
  `3aad769`. The receipt says it "was not re-run and not edited".
- This is evidence about **source quality and system behaviour**, not about learned model conduct.
  No model chose to abstain.
- It illustrates the rule this packet adopts: a guard stopping an unsupported output is evidence
  about the guard, not evidence that a model chose responsibly.
- Neither more advisories nor more abstentions is better in itself. The question is whether the
  response is justified by the evidence, and whether useful work was completed when the evidence
  permitted it.

## 5. What MOA/ESS is and is not, for this study

**It is:** external, motivating evidence. Broad failure classes may inform *newly authored*
synthetic tasks, provided that:

- their provenance and relationship to the motivating examples is disclosed in the case
  provenance;
- the result is never described as independent of MOA/ESS.

New names, paraphrases or changed numbers do not by themselves create a new scenario root.

**It is not** a training-data source, a model-selection input, a runtime dependency, or a test set.
The following must not be imported into the curriculum or into model selection:

- MOA/ESS trajectories;
- policy mappings;
- answer keys;
- findings catalogues;
- failure transcripts;
- hidden state;
- scenario derivatives.

**A future transfer study is not authorized here.** It would ask whether an intervention developed
elsewhere transfers to industrial-style synthetic reasoning. It would not ask whether a model can
reproduce MOA's answer catalogue. It would need all of the following:

- fresh, separately governed cases;
- a frozen plan;
- matched observations across comparison arms;
- pinned simulator and evaluator versions;
- an exposure record;
- separately approved review and execution arrangements, including specialist controls-engineer
  review.

## 6. Exposure record

### 6.1 Files opened for this packet (2026-09-28, by this seat)

Read-only, at MOA `68aae66752885e98986ecdc2a78ecdc962fa5386`. Chosen to verify the two figures
in Anthony's instruction with the least exposure.

| File | sha256 | How read | What it contains |
|---|---|---|---|
| `docs/deepseek.md` | `0997f098…ff69a` | full | cloud-comparison protocol, plus v0.5/v0.6 aggregate results. Opened first; it turned out not to be the v0.7 source |
| `receipts/source-map-v2/README.md` | `264b4388…590c` | full | the source-map run summary quoted in §4 |
| `docs/holdout-evaluation-v0.7.md` | `cf8ede54…aa52` | selected lines only (grep for the campaign's counts) | protocol lines: denominators, thresholds, receipt paths |
| `receipts/v0.7/README.md` | `b5716fd2…606c1a` | full | public campaign summary quoted in §2 |
| `receipts/v0.7/holdout-aggregate.json` | `3e1f9ba5…86ba` | full (key/value walk) | public aggregate: counts and identifier totals; **by design no case IDs, labels, observations or per-case results** |

The following were **not opened**:

- MOA's private campaign outputs, drills, case lists or data files (`moa/data/…`);
- answer keys, findings catalogues, policy maps, transcripts or evaluator audits;
- the source-map `evaluation.json` rows;
- any ESS file. Only its HEAD commit, `3aad769`, was read as git metadata.

### 6.2 What reached authors and reviewers another way

- **Anthony's instruction** (2026-09-28) itself carried the aggregate v0.7 figures and the TIC202
  example to this seat. The four Sonnet drafting agents for this packet received only the parts
  relevant to their documents. The measurement drafter's brief included the general rule and the
  guard example. The two final-review agents received Anthony's full instruction text, including
  the aggregate v0.7 figures and the TIC202 example. No MOA file was given to any agent, and all
  were told not to open MOA/ESS.
- **This seat's lineage is not independent of ESS.** Earlier MacBook Claude seats architected and
  built ESS v2 and v3 (fault engine, drills, evidence-scored assessments). This seat's always-loaded
  memory carries that project history. Any ESS-derived scenario is therefore **not** unseen by the
  humanity-succeed builder.
- **MOA's own runs were operated by other seats.** The source-map run was by a MacBook grok-4.6
  seat, and the v0.7 campaign was executed by an isolated Codex agent, with disclosed author and
  reviewer exposure (MOA `receipts/v0.7/README.md`). Whether GPT-6 Astra, author of the
  humanity-succeed specification and the R1 disposition, has MOA/ESS exposure is **not recorded
  here and not verified**. It should be asked, not assumed.
- **The WP3 commissioning suite v1** (160 fixtures) was authored by Sonnet builders whose prompts
  contained no MOA/ESS material. Its scenarios are generic office-style corrections, refusals and
  formatting tasks. The auto-loaded memory index on this machine names the ESS project in one line,
  so "never mentioned in context" cannot be claimed for every agent.
- **The humanity-succeed repository** contains no MOA/ESS reference on any branch (`git grep` over
  `f65afc9` and `0d85909`, 2026-09-28).

### 6.3 Consequence

Every MOA/ESS case, result or failure class listed above is **exposed** to this project's authors.
None may later be described as an untouched external test. Abstracting a known failure class into
a new synthetic task is legitimate research design; it is not proof of independence, and its
provenance must say so.

### 6.4 Entries touched by the prior-decisions search (2026-09-28, appended)

The read-only search for Anthony's prior rulings (`PRIOR_DECISIONS.md`) surfaced Stack and helix
entries that concern MOA or ESS.

- **What the searchers took:** Anthony's governance words only (what may be used, how
  employer data is handled).
- **What they did not copy:** case content. The Sonnet searchers were told not to.
- **What the lead read in full:** Stack `32078c6d` and `0e034083` (the 2026-09-26 two-lane ruling:
  public sources, employer data, "whatever I bring to the table") via `inspect_claim`, and helix
  `#22849` (an ESS v3 seat ruling on guard outcomes) via `recall`.

Every entry below is now exposed to this project's authors:

| Entry | Domain / subject |
|---|---|
| `0ce00ce35596` | experion-station-sim,master-operations-agent,public-source-map,phase-1,phase-2-passdown,2026-09-26 |
| `0e034083409c` | anthony,ruling,two-lane-shape,gate-shape:two-lane,experion-station-sim,master-operations-agent,brought-to-the- |
| `235944fe3811` | stack claim_id=235944fe3811245e64303fde1aece604f2e96b4f244dd915bdc540baf3bc9ebb domain=experion-station-sim da |
| `32078c6dc67a` | anthony,ruling,two-lane-shape,gate-shape:two-lane,rule-6,experion-station-sim,master-operations-agent,public-s |
| `4845eef20b6c` | experion-station-sim,codex-seat,hq-verification,rescue,tmp-volatility,double-check,merged,ffde6c7 |
| `51e285798f0b` | experion-station-sim,mesh-20260827,df003bf,seat-3-3 | claim_id 51e285798f0b6a997500c8503c581fa57f9c71ba45d4ec9 |
| `5a9298f811f8` | experion-station-sim,jagan-reddy,airco-collaboration,addendum,2026-09-19 |
| `5ff597ae0209` | Stack domain=experion-station-sim,jagan-reddy,honeywell-contact,two-lane-shape,anthony-gate claim_id=5ff597ae0 |
| `61b8f693b830` | Stack domain=experion-station-sim,jagan-reddy,honeywell-contact,public-record,correction claim_id=61b8f693b830 |
| `66d1c80f159b` | experion-station-sim,master-operations-agent,phase-2,verification,2026-09-26 |
| `75eb610574d7` | templetwo-repos,experion-station-sim,made-public,pre-publication-sweep,anthony-request |
| `8753dadec411` | experion-station-sim,harbor-delta-review,airco-start-date-unreconciled,exhibit-a-framing,attribution-closed,an |
| `90550094368a` | experion-station-sim,mesh-20260827,s1-verdict,seat-3-3 | claim_id 90550094368af4de4946a66727e8e8b224a79cb26eea |
| `a1f19e364d15` | ring-2,hq-adjudication,codex-seat,witness-relay,experion-station-sim,duplicate-attribution,drain |
| `a5059eece357` | experion-station-sim,jagan-reddy,airco-collaboration,continuation,2026-09-19 |
| `baf8554637c6` | experion-station-sim | claim_id baf8554637c69e09e8237135b9ea5a0d7ce62ccc22774ee58c1056094a6a507e | 2026-08-30 |
| `c7ab01d69b24` | experion-station-sim,gate-shape:scope-broadening,rulings,2026-09-27 |
| `cbfbf3663d33` | experion-station-sim | claim_id cbfbf3663d3317b1a33c41e3e39fd040498fcea9cb89c50bb2fb4707756c8784 | 2026-08-31 |
| `d2bf3f5914ea` | Stack domain=experion-station-sim claim_id=d2bf3f5914ea9ea55c1e3bc5c4403d07052df5afc57d3900d3d39ec07d854344 (2 |
| `e7e1f2296148` | experion-station-sim,mesh-20260827,fb3123a,seat-3-3 | claim_id e7e1f2296148bc497d3c0922c8bc67c30db54232a92b06d |
| `ee2885b29061` | experion-station-sim,mesh-20260827,s2-verdict,seat-3-3 | claim_id ee2885b290618d2a47b486bba2e0398344aab7709a31 |
| `f2782a2f5af7` | experion-station-sim,phase-2,g2-stage-one,verification,2026-09-27 |
| `f9520e783a74` | stack claim_id=f9520e783a74ae62adc2cc03690a2ad13876af059383007b3f56649fe398ec72 domain=experion-station-sim da |
| `fd33e18844e2` | stack claim_id=fd33e18844e2a35adbae82c251a8cdfba35987d900ff5bc8cbc3a9cb605af780 domain=experion-station-sim da |
| `helix #22834` | t2helix domain=experion-station-sim id=22834 (2026-08-30 RULINGS — sourceBasis, default sourceBasis, and safet |
| `helix #22849` | t2helix id=22849 domain=experion-station-sim tags=mesh-20260827,v3,ruling,supersession,safety-gate date=2026-0 |
| `helix #22977` | t2helix domain=experion-station-sim id=22977 (STRIP-DEV FINDING CLOSED) |
| `helix #24103` | t2helix domain=experion-station-sim id=24103 (CROSS-LENS ON truncation work) |
| `helix #24307` | t2helix id=24307 domain=experion-station-sim tags=evidence-gate,instrument,baseline date=~2026-08-27 |
| `helix #24339` | t2helix domain=experion-station-sim id=24339 (PRE-COMMIT SEAM CATCH — evidence-gate sweep) |
| `helix #24400` | t2helix domain=experion-station-sim id=24400 (EVIDENCE-GATE PREVIEW SOUND) |
| `helix #24827` | t2helix id=24827 domain=experion-station-sim tags=v3,codex-report,gate-3,do-not-tag date=2026-08-31 |
| `helix #24918` | t2helix id=24918 domain=experion-station-sim tags=daa5025,verdict,gate-4-spec-vs-test date=~2026-08-27 |
| `helix #36698` | experion-station-sim |

## Classification

| Proposed change | Class | Why |
|---|---|---|
| Adopt §1–§5 as the study's stated motivation and boundaries (a PROTOCOL/README note) | documentation-only | no estimand, arm or endpoint changes |
| Adopt §6 as the initial exposure record, kept append-only in `docs/` | documentation-only | a record, not a mechanism |
| A provenance field for "motivated by an MOA/ESS failure class" on newly authored cases | needs implementation (small) | the case provenance has only `source_refs` today; a structured field would make disclosure checkable |
| Any use of MOA/ESS material as data, or any transfer study | separate decision from Anthony | not authorized here and not requested |
| Asking GPT-6 Astra to disclose its MOA/ESS exposure | separate decision from Anthony | Anthony directs that seat |

## Exact permission requested

"I accept A1_MOA_ESS_MOTIVATION_AND_EXPOSURE.md as documentation of the study's motivation and the
initial exposure record. This does not authorize any MOA/ESS data use, repository connection or
transfer study."
