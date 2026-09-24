# Reviewing humanity-succeed (WP2 checkpoint)

Outside review is welcome. This page describes what to review, how to reproduce it, and how to
report what you find.

**Instrument under construction. No behavioral result about any model is established by this
repository.** Every run recorded here is a `scripted_instrument` run: no model was downloaded,
called or trained.

## The frozen review target

Review this exact commit, not `main`. `main` may later carry review-process documents only; code
changes happen after review, through the owner's repair process.

| Item | Value |
|---|---|
| Tag | `wp2-review-b2e08b8` |
| Commit | `b2e08b81b5a7bbb7295c1a84fc454536e73a0fad` |
| Tree | `d1d798e081bb383619896dd6f4c608c323c64179` |
| Source ZIP | `humanity-succeed-b2e08b8.zip` (attached to the `wp2-review-b2e08b8` pre-release) |
| ZIP SHA-256 | `f412ce20c63da0e3a8c6cf56cb2e9f8fd243c3117b0df35a0da7608b4206ebd8` |

Regenerate the ZIP yourself. The same bytes were produced with git 2.50.1; other git versions may
differ, in which case compare file contents against the tree instead:

```sh
git archive --format=zip --prefix=humanity-succeed-b2e08b8/ \
  b2e08b81b5a7bbb7295c1a84fc454536e73a0fad | shasum -a 256
```

The commit carries an SSH signature that is **not verified**: GitHub reports `unknown_key`, and
no allowed-signers file is published. Treat authorship as stated in the commit trailers, not as
cryptographically established.

## Read first

`AGENTS.md`, `BUILD_SPEC.md` (§4–§8, §12–§14), `docs/PROTOCOL.md` §8, `docs/DECISIONS.md`,
`docs/ACCEPTANCE.md` and `docs/HANDOFF.md`. WP3–WP7 are **not started**. A missing later-package
feature is not a WP2 defect unless the docs claim it is done.

## Reproduce (offline after dependency install)

Use a fresh clone or the extracted ZIP, and temporary state roots. No test needs a model, a GPU,
network access (beyond installing dependencies) or any secret.

```sh
uv sync --locked --group dev
uv run pytest                                          # committed receipt: 213 passed at c14445b
uv run ruff check src tests scripts
uv run python scripts/export_schemas.py --check
uv run hs demo --out "$(mktemp -d)/demo" --state-root "$(mktemp -d)"
uv run hs evidence verify docs/receipts/wp2r1/demo/bundles/t-correction-claim-warm \
  --anchor docs/receipts/wp2r1/anchors/t-correction-claim-warm.anchor.json
uv run hs evidence replay docs/receipts/wp2r1/demo/bundles/t-correction-claim-warm \
  --out "$(mktemp -d)/replay"
```

**Commit relationship.** `b2e08b8` differs from `c14445b` (the commit the latest test receipt was
made at) only in five documentation and receipt files. Check it yourself with
`git diff --stat c14445b b2e08b8`.

**Test-suite caveat.** `tests/` contains red-team material: symlink, hard-link, oversized-file and
path-escape cases. They build their inputs in pytest temporary directories. Read a test before
running it anywhere unusual.

## What to attack

Attack the contracts, not just the earlier fixes:

- **Observation boundary.** Everything that can reach a subject or an SFT target: task text,
  nested resource values, clarification replies, scheduled observations, tool/error text,
  identifiers and filenames, and evaluator-only content.
- **Loaders.** Duplicate keys, unusual Unicode, YAML tags and coercion, and path-like IDs.
- **Engine.** Stale revisions, wrong-recipient notifications, permitted-but-unexecuted actions,
  and crashes between transaction stages.
- **Evidence.** Event, manifest, artifact and anchor corruption or substitution; replay
  assumptions; the difference between internal consistency and verification against an anchor.
- **Scoring.** False mechanical passes; containment versus integrity; refusal of ordinary work;
  the feature-preservation goal in both directions. Warmer or colder wording must never create a
  missing write or receipt.

## Prior exposure

Two internal red-team rounds (Claude Sonnet agents directed by the building seat) are already
recorded: `docs/DECISIONS.md` rows B23–B41, and the regression tests whose docstrings begin
"Red-team". They are prior exposure, not independent review. Their raw scratch material is kept
privately by the owner and is not in this repository.

## How to report

Open an issue with the **Review finding** template, one finding per issue, or send a report to
the owner. Please:

- **Report at most eight substantive findings,** ranked by concrete impact. Report nothing where
  nothing is established.
- **For each finding give:** the commit, file and lines, the violated contract, severity,
  mechanism, a minimal reproducer, expected and observed behavior, execution status, an evidence
  pointer or hash, and the smallest repair.
- **Execution status must be one of:** `static_candidate`, `reproduced_in_review`,
  `not_reproduced` or `blocked_by_environment`. A reviewer without execution tools reports
  `static_only` findings. Being unable to run a test is neither a pass nor a defect.
- **Mark new adversarial fixtures as development-only material.** They can never become holdback
  cases.

Please file findings as issues rather than pull requests. The owner plans to repair accepted
findings in a separate round that starts from the reviewed commit.

## Rights

No license has been selected. The repository is public for review; that does not grant a license
to reuse the code or fixtures.
