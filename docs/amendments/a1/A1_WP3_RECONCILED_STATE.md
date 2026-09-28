# A1: reconciled WP3 state

> **What this asks.** Nothing new. It records exactly what WP3 is, how it relates to accepted main,
> and which receipts are under review, so that no one rebuilds completed work from a stale note.
> It also proposes three standing rules for preserving that work (a documentation-only DECISIONS
> row). Review and merge remain separate decisions for Anthony.

Written by the MacBook seat (claude-opus-5-5) on 2026-09-28 on branch `wp3/amendment-a1`. **Model
called: no. Nothing pushed. No Stack write.**

## 1. Where WP3 actually is

| Item | Value |
|---|---|
| WP3 branch | `origin/wp3/commissioning` = `0d85909d3e1d4a8ca5f3797c42243da3a59f62e0` (2026-09-26), pushed, **not merged** |
| Accepted main | `origin/main` = `f65afc90cf212eb082b102eb7a639fd52652af4f` |
| Common base | `8dbda7a` (the R1 merge Anthony approved) |
| On WP3 only | `cc4cb6b` stage 0 freeze → `4641f6e` stage 1 contract → `c1a2e9f` stage 2 generators/partition/custody/mutations + suite v1 → `8a24ad1` stage 3 plan/run/CLI + custody kit → `0d85909` stage 4 run, controls, docs |
| On main only | `f65afc9` adds the four R1 review-input files (`hs-wp2-review-reconciliation-r1/`). Documentation only; no conflict with WP3 |
| This packet | branch `wp3/amendment-a1`, cut from `0d85909`; documentation only; committed locally on this branch, not pushed |

## 2. The receipts under review

The measurement ran at `8a24ad1` (`docs/receipts/wp3/HEAD`) with a clean runtime tree. It was
re-verified in a clean clone at `0d85909` (591 tests passed).

| Receipt | sha256 | What it shows |
|---|---|---|
| `docs/receipts/wp3/plan/plan.json` | `819c1c2a…9ab2b` | suite valid; split audit clean; 120 development + 40 holdback-designate; development mode; `independent_holdback=false` |
| `docs/receipts/wp3/run/report.json` | `3d3f5510…0fe78` | 160/160 written expectations met; 416/416 mutation invariants held; `formal_commissioning=blocked_no_independent_holdback`; `semantic_commissioning=pending_no_human_reviews` (36 judgment-heavy fixtures); `lifecycle_state=mechanically_validated` |
| `docs/receipts/wp3/03_sabotage.stdout` | `1f3b0ce9…67543` | 4 of 4 deliberately broken evaluators detected |
| `docs/receipts/wp3/04_replay_all.json` | `519a59fa…683a5` | 160/160 bundles replay as reproduced |
| `cases/commissioning_suite_v1/SUITE.json` | `20933f34…ff12f` | the suite manifest the plan hashed |
| `docs/WP3_DESIGN.md` | `d0d6c06f…c033db` | the class contracts the expectations were written from |

What these do **not** establish: formal commissioning (no custodian), semantic commissioning (no
human review), or any population error rate. See `docs/receipts/wp3/README.md` and DECISIONS
B48–B54.

## 3. Stale statements to read correctly, not act on

These say WP3 has not started. They were true when written, and some are still true *on main*,
because WP3 is not merged. None is a reason to rebuild WP3.

| Where | Statement | Status |
|---|---|---|
| `main:docs/HANDOFF.md:38` | "WP3 stays held until Anthony decides." | superseded: Anthony opened WP3 on 2026-09-26 |
| `main:docs/HANDOFF.md:156-165` | WP2-checkpoint "smallest next action" asking whether WP3 may begin | superseded by the same decision |
| `main:README.md:28` | "WP3–WP7 not started" | accurate for main until a WP3 merge; the WP3 branch README says otherwise |
| Stack handoff `20260926T060305` (thread humanity-succeed) | "WP3 STAYS HELD" | superseded by the same seat's handoff `20260926T075007` |

If WP3 is merged, main's README and HANDOFF become current through that merge. No separate edit
is proposed here.

## 4. Proposed standing rules (documentation-only DECISIONS row)

1. **The existing work is preserved as recorded.**
   - Suite v1, its plan and report, the sabotage controls, the findings F1–F3 and the historical
     reports are not regenerated, extended or rescored.
   - A later evaluator or rubric version replays these records faithfully under
     `hs-evaluator/0.2.0` (B43 pattern). It does not re-grade them.
2. **The 40 holdback-designate fixtures are development evidence permanently.**
   - They were authored and inspected by the builder.
   - Moving them to another directory, re-labelling their split, sealing them, or later appointing
     a custodian does not make them fresh holdback (B48; BUILD_SPEC §9).
3. **New coverage arrives only as a new, explicitly versioned suite or supplement** (for example
   `commissioning_suite_v2` or `supplement_a1_measurement`).
   - It has its own plan, run and receipts.
   - No new receipt is presented as covering suite v1, and the v1 receipt is never presented as
     covering additions.
   - This covers findings F1/F2 and any measurement-amendment controls.

## Classification

| Proposed change | Class | Why |
|---|---|---|
| Record this reconciled state | documentation-only | a statement of fact with receipts |
| DECISIONS row stating rules 1–3 | documentation-only | restates B43/B48/B54 as standing rules |
| Merge WP3 into main | separate decision from Anthony | review and merge are separate decisions |

## Exact permission requested

None for this document. The merge of `wp3/commissioning` is a separate decision; this packet does
not request it.
