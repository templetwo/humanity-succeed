# Reviewing a blind packet: what the tools do and do not do

For the human reviewer of a packet made by `hs review export` or `hs review export-controls`
(DECISIONS B60, B61, B67, B68, B69, B71). This page
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

- `reviewer_ref`: your stable identity reference, typed the same way every time, in plain ASCII
  letters, digits, space, `-`, `_` or `.` (for example `anthony-vasquez-sr`). Two references are
  the same reviewer when they agree once case, spacing and punctuation are ignored, so `Anthony`,
  `anthony.` and `anthony vasquez` are all refused once `anthony-vasquez` is recorded; one person
  is never counted as two (B61). A reference is also one kind of reviewer: a reference first
  imported as `model` cannot later be imported as `human`. Choose it once. A name in another script
  belongs in `words`, not here.
- `reviewer_kind`: `human`. A model's ratings may be imported with `model`; they are recorded as
  secondary and never count as votes.
- `rated_at_utc`: a UTC instant written as `2026-10-07T14:03:00Z` (optionally with fractional
  seconds). Offsets, bare dates and times without a zone are refused.
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
Status refuses a `packet.json` that is not byte-for-byte the one the operator key was written for,
and reports its `packet_sha256`, coverage per item, the distinct human reviewers, any colliding or
unusable reviewer references, and an agreement statistic only when two distinct humans cover the
same items. When two humans overlap on only some items, the status stays `single_reviewer_*` with
the `single-reviewer` label and the agreement block covers the shared items alone; it is not an
independent-review result.

## What your review changes, and what it does not

- `hs review status` moves from `pending_no_human_reviews` to `single_reviewer_partial` or
  `single_reviewer_reviewed`, labelled `single-reviewer`, until a second distinct human covers every
  item; then to `split_unadjudicated` while any disagreement is unsettled, and to
  `independently_reviewed` only when none is. No agreement statistic is computed from one reviewer.
- The commission run's `report.json` and `report.html` are not changed; suite v1 is never rescored
  (B55). The lifecycle stays `mechanically_validated`.
- No case file gains a review entry. Your verdicts live in the ledger under the state root, bound
  to the packet hash and each item's source hash.
- A packet is a one-time export. A re-export of the same run is a different packet with different
  item ids, and ratings for one cannot be imported against the other. Keep the directory you were
  given until your ratings are imported.

## Packets with control items (`hs review export-controls`, DECISIONS B68, B69)

A packet made by `hs review export-controls` looks the same as one made by `hs review export`:
the same three files, the same template, the same rules above. Two things differ.

- **Some items are controls.** Some are items the evaluator did not pass; some are items a careful
  reader should fail, built on purpose. Nothing in the packet says which, or how many. Judge every
  item on its rubric line alone. The operator key, under the state root, carries each item's role;
  do not ask for it, and do not open `cases/supplement_a1_semantic_controls_v1/` in the repository,
  before you commit your verdicts. Both would tell you the answers.
- **Status says more, later.** After a human has rated every item, `hs review status` reports the
  control hit-rate for that reviewer as counts (wrong-on-purpose items failed out of their total;
  honest controls passed out of theirs), the bucket counts, and an agreement statistic with and
  without controls when two humans overlap. Nothing about controls is reported before full
  coverage, so a partial import cannot read the answers back. Verdicts revised after that point
  are revisions of your own, and the report counts them as made after the disclosure.

The honest verdict for each control was written down before the supplement was ever run
(`cases/supplement_a1_semantic_controls_v1/SUPPLEMENT.json`), as suite v1's mechanical
expectations were. The 36 items of the earlier packet are not changed by any of this; a packet with
controls is a new export with new item ids.

## When two reviewers disagree (`hs review adjudicate`, DECISIONS B71)

When two distinct humans cover every item and their latest verdicts differ on some item and rubric
line, status reads `split_unadjudicated` with the `single-reviewer` label, not
`independently_reviewed`. The named adjudicator, Anthony, settles each one:

```sh
uv run hs review adjudicate --packet PACKET_DIR --item ITEM_ID --dimension DIMENSION \
    --adjudicator anthony-vasquez-sr --decision pass|fail --words "your reasons" \
    --at 2026-10-08T01:02:03Z --state-root STATE_ROOT
```

An adjudication is its own append-only record. It never rewrites a reviewer's verdict and is not a
third rating. It is refused when the reviewers agree (nothing to settle), when fewer than two humans
have rated the item, when the words are blank, or when the adjudicator reference collides with a
recorded reviewer's without being identical. The adjudicator may also be one of the two reviewers
for the pilot; status says so when that is the case. If either reviewer revises after an
adjudication, or a third human rates the item, the adjudication is stale and the split is open
again until it is settled anew. Status lists every adjudication and whether it is stale.

See `docs/audits/2026-10-07_human_side_audit_a1_review.md` for what the earlier packet can and
cannot establish, and `docs/A1_SEMANTIC_CONTROLS.md` for why controls exist and what they do not do.
