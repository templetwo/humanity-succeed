# PEB compatibility (WP0)

Recorded 2026-09-24 by the MacBook seat (claude-opus-5-5). The inspection was read-only. Only
what is listed under "What was read" was examined. PEB's application and tests were not run,
nothing was pulled or checked out, no file was modified, and no code was copied.

## Candidate checkout

| Item | Established value | How |
|---|---|---|
| Path | `~/Desktop/project-epistemic-bound` (Anthony named this as a candidate; no wider disk search) | `ls` |
| Git top level | same path | `git rev-parse --show-toplevel` |
| Branch / HEAD | `main` at `885de3dcb7964d1931c1e4fa5f3298b55470d41d` (2026-09-13 16:41:21 -0400, "Merge trace readability follow-up with measured self-review") | `git rev-parse HEAD`, `git log -3` |
| Working tree | clean (0 entries in `git status --porcelain`) | `git status` |
| Remote | `origin https://github.com/templetwo/project-epistemic-bound.git` | `git remote -v` |
| Python | `requires-python = ">=3.12"` (this repo targets 3.11) | `pyproject.toml` |
| Runtime deps | pydantic, fastapi, uvicorn, httpx, textual | `pyproject.toml` |
| **Software license** | **None found.** No LICENSE/COPYING/NOTICE file is tracked, and `pyproject.toml`/`README.md` declare none. `docs/PREDICATE_LICENSES.md` is about evaluator "predicate licenses" (claim scoping), not software rights. | `git ls-files`, `grep -i license` |

**Consequence:** no permission to copy PEB code has been established, and none was copied. Any
future reuse needs Anthony's explicit rights decision for PEB first.

## What was read

- `pyproject.toml`
- `docs/INTERFACES.md`: header, §4 tool catalog, §5 subject decision, §6 core records,
  §7 protocols, §8 canonicalization, §9 event chain, §10 error codes
- `docs/SCENARIO_FAMILIES.md`: first 25 lines
- `docs/PREDICATE_LICENSES.md`: first 30 lines
- the first ~900 bytes of one recorded `events.jsonl` under `docs/evidence/deepseek-01/`
- the list of tracked files (`git ls-files`)

## Interface comparison (from the files read)

| Concern | PEB (frozen S1 contract, per its INTERFACES.md) | humanity-succeed v0.1 (packet) | Compatible? |
|---|---|---|---|
| Subject output | Discriminated on `kind`: `action` / `decline` / `escalate` / `finish`, each with `statement`; `action` carries `{tool, arguments, claimed_grant_id?}` plus an optional `PreActionDeclaration` | One object `{"action": {"type": ...}, "message"?}` over a seven-action union | **No.** The shapes and semantics differ (grants, escalation, pre-action declarations) |
| Tool catalog | `workspace.list/read`, `report.write`, `fixture.repair`, `checks.run`, `handoff.write`, `commitment.propose`, `export.send` | `read_resource`, `write_resource`, `notify`, `request_clarification`, `decline`, `wait`, `finish` | **No.** Different closed sets |
| Record separation | `ActionProposal`, `GateDecision`, `EffectReceipt` and `StoredEvent` are separate records; `ReferenceMonitor.authorize` / `SyntheticExecutor.execute` protocols | `action_proposed`, `permission_decided`, `action_executed` + effect events, separate SQLite rows | **Same principle, different contracts** |
| Event hashing | `digest(domain, obj)` = SHA-256(`domain ‖ 0x00 ‖ canonical_json`); genesis `prev_hash` is `null`; fields include `event_id`, `ts`, `actor` | SHA-256(canonical envelope without `event_hash`); genesis `prev_hash` is 64 zeros; packet event schema fields | **No.** Hashes are not interchangeable |
| Verification levels | `chain_consistent; external_anchor_absent` / `verified_against_anchor` / `partial` / `failed` | `internal: consistent/failed` plus `anchor: external_anchor_absent / verified_against_anchor / partial / failed` | **Conceptually aligned.** Implemented independently here |
| Scenario families | Six development families (conceal-error, fictional-authority, claimed-harmlessness, evaluation-pressure, authorized-useful-work, correction-handoff) with four frame wrappers | Ten families F01–F10 of this project's own (PROTOCOL §4) | **Not the same families**; none is imported or assumed |

## Disposition

- **Native synthetic engine is the default** (DECISIONS D22). It does not depend on PEB.
- **The `EpisodeBackend` interface and PEB export importer are not implemented at WP2.** If one
  is built later, it must be read-only, map PEB's recorded bundles through an explicit adapter,
  and answer `unsupported` for anything it cannot map. It must never invent PEB APIs or family
  names.
- **Unverified:** PEB's current `contracts.py`, its 22 published schemas, its fixture contents,
  and whether its bundles could be imported losslessly. None of these were read.
- No change to PEB is required or requested.
