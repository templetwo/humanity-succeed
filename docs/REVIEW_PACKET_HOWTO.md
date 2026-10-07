# Reviewing a blind packet: what the tools do and do not do

For the human reviewer of a packet made by `hs review export` (DECISIONS B60, B61, B67). This page
describes the mechanics as the code behaves at this checkpoint. It does not tell you how to judge.

## What you receive

A directory with three files and nothing else:

- `index.html`: every item, offline, no scripts. Each item shows the task the subject saw, the
  resources it could see, the recorded sequence (what it proposed, what it said, what happened),
  the rubric line or lines, and the item id and source hash.
- `packet.json`: the same content as data.
- `ratings-template.json`: one blank row per item per rubric line.

The key that maps items back to fixtures stays with the operator under the state root. Do not ask
for it before you commit your verdicts.

## Filling the template

- `reviewer_ref`: your stable identity reference, typed the same way every time. Case, spacing and
  Unicode variants of a recorded reference are refused on import, so one person is never counted
  as two (B61). Choose it once.
- `reviewer_kind`: `human`. A model's ratings may be imported with `model`; they are recorded as
  secondary and never count as votes.
- `rated_at_utc`: an ISO 8601 timestamp, for example `2026-10-07T14:03:00Z`.
- Each row: `verdict` is `pass` or `fail`; `words` is your reason in your own words. A blank in
  either refuses the whole file; nothing is defaulted on your behalf.

**Partial progress.** The import is all or nothing per file. To hand in part of a packet, delete
the rows you have not rated and import the rest; status then reads `single_reviewer_partial`.
Import the remaining rows later under the same `reviewer_ref`. Rating a row again later is recorded
as a revision of your own verdict, never as a second reviewer.

**A fixture you think is defective.** There is no separate channel yet. Say so in `words` for that
row; the ledger keeps every word you write, and the operator can resolve the item to its fixture
with the key.

## What the operator runs

```sh
uv run hs review import --packet PACKET_DIR --ratings YOUR_FILE.json --state-root STATE_ROOT
uv run hs review status --packet PACKET_DIR --state-root STATE_ROOT
```

Import validates everything first and appends to an append-only ledger only if everything holds.
Status reports coverage per item, the distinct human reviewers, any colliding reviewer references,
and an agreement statistic only when two distinct humans cover the same items.

## What your review changes, and what it does not

- `hs review status` moves from `pending_no_human_reviews` to `single_reviewer_partial` or
  `single_reviewer_reviewed`, labelled `single-reviewer`, until a second distinct human covers every
  item. No agreement statistic is computed from one reviewer.
- The commission run's `report.json` and `report.html` are not changed; suite v1 is never rescored
  (B55). The lifecycle stays `mechanically_validated`.
- No case file gains a review entry. Your verdicts live in the ledger under the state root, bound
  to the packet hash and each item's source hash.
- A packet is a one-time export. A re-export of the same run is a different packet with different
  item ids, and ratings for one cannot be imported against the other. Keep the directory you were
  given until your ratings are imported.

See `docs/audits/2026-10-07_human_side_audit_a1_review.md` for what the current packet can and
cannot establish.
