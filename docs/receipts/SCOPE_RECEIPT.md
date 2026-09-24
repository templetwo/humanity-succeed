# Scope receipt: WP0–WP2 local build

Written by the MacBook seat (claude-opus-5-5), 2026-09-24. This seat is not the HQ seat.

## Authorization actually given (Anthony, in this session, quoted)

1. Build scope (pasted instruction, excerpts):
   - "Go. Proceed with WP0–WP2 in: ~/Desktop/🔬 Active_Research/humanity-succeed"
   - "This authorizes the local implementation and scripted tests described below. It does not
     approve a research study, model execution, or training."
   - "Initialize Git in this exact project directory … Local commits are authorized. No remote
     creation, push, public license selection, destructive cleanup, or modification of global
     Git settings."
   - "Ordinary build/test dependencies may be installed into a project-local virtual environment."
   - "Keep the first slice single-agent. No subagent fan-out, Stack writes, private-record
     ingestion, or changes to another repository."
   - "Stop at this checkpoint before WP3–WP7."
2. A later direction that **widens** item 1 for the remote only, verbatim:
   "continue alse start the git repo offocially(public) then push and await red teaming of your
   commit". Separately: "ultracode engaged" and then "use ultracode when helpfull".
   - This authorizes creating a public GitHub repository and pushing to it.
   - It does **not** authorize selecting a license. No license was selected.
   - It does not authorize model execution, training, a study, publication of a preregistration,
     or Stack writes. None of those happened.

## What this seat did not do

- It downloaded no model, called no model, and trained no weights.
- It did not modify, pull, check out or execute anything in PEB or any other repository.
- It made no Stack writes. It also sent no chronicle entry, handoff, or policy change.
- It changed no global git settings. The commit identity is the existing configured one.
- It fabricated no human review and no approval receipt.

## Governance checks performed (read-only)

| Check | Result |
|---|---|
| Stack heartbeat | `ok`, version 1.21.0, 52 tools |
| Arrival | the Stack's lightweight read-only arrival |
| Standing policies (read-only) | 13 active. Applied here: subagents one tier below the spawning seat, the children's-names exclusion, protected personal records stay out, non-Claude systems credited as provenance only, the owner decides publication, and nuisance-baseline controls (relevant from WP3) |
| Pre-action compass check (live schema; `action` is required) | **PROCEED**, no risk signals, for: local build, git init plus local commits, project-local venv, read-only PEB inspection; no push/remote/model/training/Stack writes. Suggested verifications: check the git diff; verify the target branch |
| Compass check for the public push | Run separately, immediately before the push. See `docs/receipts/PUSH_RECEIPT.md` |

The packet's recorded compass failure ("'action' is a required property") was a schema
mismatch, not clearance. This session used the live schema and received an actual verdict.

## Host and runtime (measured)

- macOS 27.0 (26A428), arm64
- uv 0.9.18; CPython 3.11.15 (uv-managed), project-local `.venv`
- Locked packages: see `uv.lock` (31 packages)
- Workspace: `~/Desktop/🔬 Active_Research/humanity-succeed`. Nothing enclosed it in another
  git repository (`git rev-parse` failed in the directory and in its parent before `git init`)

## Rights status

- Repository software and documentation: **no license selected.** Pending Anthony.
- Fixtures: `rights_status: pending` in every case file.
- PEB: no license found, and nothing copied (`docs/PEB_COMPATIBILITY.md`).
