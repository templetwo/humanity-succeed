# Red-team: reviewer identity after the B61 fix (2026-10-07)

Target: the distinct-reviewer check closed by draft PR #1 at `17860e0` on branch
`audit/a1-human-side-2026-10-07` (`review/identity.py`, `review/importer.py`, `review/status.py`,
`commissioning/agreement.py`; audit `docs/audits/2026-10-07_human_side_audit_a1_review.md` §3
F03/F04). Goal: make one person count as two reviewers, make a single-reviewer result look
independently reviewed, or make `hs review status` say something the ledger does not support.

Everything below was measured with `uv run hs review export|import|status` and direct Python
against the modules, on fresh exports of `docs/receipts/wp3/run` into a scratch directory with a
scratch state root. Reproducer scripts sit beside this file; `transcripts/before/` holds their
output at `17860e0`, `transcripts/after-patch/` their output with `proposed-fixes.patch` applied
in a throwaway worktree. No model was called. Nothing under `src/`, `tests/`, `cases/`,
`docs/receipts/` or `docs/DECISIONS.md` was changed; the patch is a proposal, not applied.

**Result: 6 defeats (2 high, 3 medium, 1 low), 5 held-by-procedure-only, the rest held.** The most
important: a trailing dot, hyphen or underscore is still a second reviewer (D1).

## 1. Defeats, ranked

| # | Attack | Severity | Fix in `proposed-fixes.patch` | Inside B61's approved wording? |
|---|---|---|---|---|
| D1 | `anthony` + `anthony.` (or `-`, `_`, ` 2`, `..`) reach `independently_reviewed`; `.` and `..` are two reviewers | high | canonical form keeps letters and digits only; a ref with neither is refused | yes: it is the distinct-reviewer check and the `agreement()` refusal |
| D2 | `hs review status` is not bound to the operator key: a trimmed `packet.json` (same `packet_id`, 2 of 36 items) reports `independently_reviewed`; the output has no `packet_sha256` | high | status loads the key under the state root, refuses on hash mismatch, reports `packet_sha256`; CLI exit 2 | no: status integrity under B60's "bound to the exact case hash"; a B61 follow-through row, not the check itself |
| D3 | legacy ledger holding a look-alike ref (Cyrillic `аnthony`) counts it as a human; ASCII `anthony` then imports as a second one | medium (legacy ledgers only) | status applies `reviewer_ref_problem` to ledger refs: excluded from votes, reported under `reviewer_ref_problems` | yes |
| D4 | two ledger lines with the same `(item, dimension, reviewer_ref, revision)` and contradicting verdicts: status silently reports the first, nothing is flagged | medium (hand-edited or doubled ledger) | `read_records` raises `LedgerCorrupt` on a duplicated revision; importer and status both refuse | adjacent: "never silent" ledger integrity, not the reviewer check |
| D5 | a `reviewer_ref` imported as `model` is later imported as `human` under the same ref and counted as votes | medium | importer refuses a ref already recorded under a different `reviewer_kind` | yes, with PROTOCOL §9 |
| D6 | `rated_at_utc` accepts `+05:30`, `2026-10-07`, naive, `2026-W41-3`, 9-digit fractions, year 9999, stores them unnormalised in a field named `utc` | low (status never reads it) | strict `YYYY-MM-DDTHH:MM:SS[.ffffff]Z` | no: F09, and an existing test deliberately accepts the offset form |

### D1. Punctuation is still a second reviewer

`a1_ref_variants.py`, `a9_direct_python.py`.

```
$ hs review import --packet P --ratings r1.json --state-root S     # reviewer_ref "anthony"
  exit 0  recorded 36  votes 36
$ hs review import --packet P --ratings r2.json --state-root S     # reviewer_ref "anthony."
  exit 0  recorded 36  votes 36
$ hs review status --packet P --state-root S
  status independently_reviewed   label null
  distinct_human_reviewers ["anthony", "anthony."]   reviewer_ref_collisions []
  agreement[truthful_notification] reviewers ['anthony','anthony.'] n_paired 36 raw 1.0
```

After nineteen admitted spellings of one name (`anthony-`, `anthony_`, `anthony 2`,
`anthony.vasquez`, `anthony-vasquez`, `anthony_vasquez`, `anthony vasquez`, `anthonyvasquez`,
`a.vasquez`, `.`, `..`, `-`, `_`, `0`, `anthony2`, `anthony..`, `anthony-.-`) status lists 19
distinct human reviewers and the agreement pair is `['-', '.']`. Direct Python:
`agreement_between_reviewers("anthony", ..., "anthony.", ...)` returns raw_agreement 1.0, as does
`(".", "..")` and `("a.vasquez", "a-vasquez")`.

This is F03 again one character over: the canonical form collapses whitespace and case but keeps
the three separator characters the charset rule admits. Verdict: **defeated**.

Fix (patch, `review/identity.py`): `canonical_reviewer_ref` = NFKC, casefold, then only
`str.isalnum()` characters; `reviewer_ref_problem` refuses a reference whose canonical form is
empty. After the patch every variant above except `anthony 2`/`anthony2`, `a.vasquez`, `0` and
`anthony.vasquez` is refused at import as a collision, and `agreement_between_reviewers` refuses
`anthony` vs `anthony.`. What remains distinct (`anthony` vs `anthony2`, `anthony` vs `a.vasquez`)
cannot be decided by normalisation; that is the reviewer-registry decision in F04.

Test impact: `tests/review/test_identity.py::test_repeated_internal_whitespace_collapses` expects
`"anthony vasquez"` (now `"anthonyvasquez"`), and
`test_genuinely_distinct_references_stay_distinct` asserts `"anthony vasquez"` and
`"anthonyvasquez"` are distinct. That second assertion is a choice PR #1 made on purpose; this
patch reverses it, and the parent session should decide which way it goes. Treating them as one
reviewer is the strict direction (a label can only be too strict, never inflated), and
`anthony-vasquez-sr` vs `anthony-vasquez-jr` stays distinct either way.

### D2. Status is not bound to the packet it is handed

`a22_status_unbound.py`, `a9_direct_python.py` (A9d).

`review_status` reads whatever `packet.json` it is given, filters the ledger by the manifest's
`packet_id`, and never checks the manifest bytes against the operator key or the records'
`source_sha256`. So:

```
$ hs review import ... reviewer_ref "anthony"  (36 of 36)      exit 0
$ hs review import ... reviewer_ref "bob"      (2 of 36)       exit 0
$ hs review status --packet REAL  --state-root S
  status single_reviewer_reviewed  label single-reviewer   (1 of 36 items independent)
$ hs review status --packet TRIMMED --state-root S          # same packet_id, only bob's 2 items
  status independently_reviewed  label null
  distinct_human_reviewers ["anthony","bob"]  agreement n_paired 2 raw 1.0
  output keys: no packet_sha256
```

A manifest copy with one item's `source_sha256` altered (the rubric "edited" after rating) is
likewise reported in full against records bound to the original hash. The status output carries
`packet_id` only, so a consumer cannot tell which manifest produced it. Verdict: **defeated**
(the report says something the ledger does not support).

Fix (patch, `review/status.py`, `cli.py`): compute the packet hash from the raw bytes, load
`state_root/reviews/keys/<packet_id>.json`, raise `PacketUnbound` when the key is missing or its
`packet_sha256` differs, add `packet_sha256` to the output; the CLI maps `PacketUnbound` to
`invalid` / exit 2. After the patch both the trimmed and the altered manifest are refused with the
two hashes named. Because the key binding is the same one the importer enforces, a record for an
item outside the manifest or with a different `source_sha256` can no longer reach status.

Test impact: eleven tests in `tests/review/test_status.py` build a packet with no key under the
state root; the `_write_packet` helper there needs to also write a `PacketKey` (one helper change).

### D3. A legacy look-alike reference still counts

`a2_legacy_collisions.py` (A2g). A ledger written between `d7cf683` and `17860e0`, or by hand,
can hold a reference the charset rule would now refuse. Status applies no charset check:

```
ledger: 36 records, reviewer_ref "аnthony" (Cyrillic a), human, covering every item
$ hs review import ... reviewer_ref "anthony"   exit 0  recorded 36
$ hs review status
  status independently_reviewed  distinct_human_reviewers ["anthony", "аnthony"]
  reviewer_ref_collisions []
```

Verdict: **defeated** for legacy ledgers; the importer alone cannot reach this state after
`17860e0`. Fix (patch, `review/status.py`): records whose `reviewer_ref` fails
`reviewer_ref_problem` are excluded from votes and listed under a new `reviewer_ref_problems`
key. Strict direction: a legitimate legacy reviewer loses coverage until re-imported under an
admissible reference, and the report says why.

### D4. A duplicated revision is resolved silently

`a2_legacy_collisions.py` (A2e). Two lines `bob` revision 1 `pass` then `bob` revision 1 `fail`
(same literal, same revision): status reports `bob: pass` with no collision, no problem, no
refusal. `status.py`'s tie-break only fires when the literals differ, and `read_records` does not
check revision uniqueness. The importer never writes this, but the ledger is a plain file. Verdict:
**defeated** (silent resolution of an ambiguous ledger). Fix (patch, `review/ledger.py`):
`read_records` raises `LedgerCorrupt` naming both lines; importer and status refuse the ledger
until the operator resolves it.

### D5. A model's reference becomes a human's

`a3_a4_a5_cross_packet_relabel_key.py` (A4a). `claude-seat` imported with `reviewer_kind: model`
(36 secondary, never votes), then the same file with `reviewer_kind: human`: accepted, 36 votes,
`independently_reviewed`. The collision check compares references, not kinds, and an exact literal
match is allowed. Verdict: **defeated** in the narrow sense that the ledger now says one reference
is both a model and a human. Fix (patch, `review/importer.py`): refuse a ratings file whose
`reviewer_ref` is already recorded under another `reviewer_kind`. This does not close F04: a seat
that picks a fresh reference and writes `human` is still indistinguishable in code (H3 below).

### D6. `rated_at_utc` is any parseable instant

`a8_rated_at.py`. Accepted at `17860e0`: `+05:30`, `-12:00`, `+23:59`, `2026-10-07` (date only),
naive `2026-10-07T14:03:00`, basic `20261007T140300`, `2026-W41-3`, `2026-10-07 14:03:00Z`,
`2026-10-07T14:03:00.123456789Z`, year 9999 and year 1. Refused: `+24:00`, Feb 30, `24:00:00`,
`now`, an epoch integer. The record stores the text as typed, so a field named `_utc` holds
`+05:30`. Status never reads the field (ordering is by `revision`), so nothing downstream moves.
Verdict: **defeated** only as a contract on the field's name; low. Fix (patch): a strict
`YYYY-MM-DDTHH:MM:SS[.ffffff]Z` pattern before `fromisoformat`. Note that
`tests/review/test_import.py::test_rated_at_utc_must_be_an_iso_8601_timestamp` deliberately
accepts `-04:00` ("the record keeps what was typed"); the parent session should decide whether
F09 meant "a timestamp" or "a UTC timestamp".

## 2. Held by procedure only

These are not closed by code and the proposed patch does not close them. Each is a custody or
identity assumption the record already makes; listed so the claim boundary stays honest.

| # | Attack | What happened | What would close it |
|---|---|---|---|
| H1 | hand-edit `ledger.jsonl`: flip `gpt-x`'s 36 lines from `model`/`false` to `human`/`true` | `read_records` reads 72 records cleanly; status `independently_reviewed`, `secondary_ratings 0` | a hash chain over ledger lines or retained ratings files under the state root; outside B61's wording |
| H2 | swap two `fixture_id`s in the operator key, reverse entry order, import | import ok; the ledger records the swapped `fixture_id`; status unchanged (it never reads fixture ids); `source_sha256` is still correct | `KeyEntry` carrying `source_sha256` and the importer cross-checking it against the manifest item; `review/contract.py` is lead-owned, so a proposal to the lead |
| H3 | a ratings file with `reviewer_kind: human` under a fresh reference, written by anyone | counted; F04 as recorded | the reviewer registry under BUILD_SPEC §4; Anthony's decision |
| H4 | two references, byte-identical ratings (same verdicts, words, timestamp on all 36) | `independently_reviewed`, no signal | an advisory `identical_rating_sets` count in status; a heuristic, not a check, so not proposed here |
| H5 | join each item's `source_sha256` to the committed run bundles | 36 of 36 items resolve to a committed case id (`wp3-c1-g09`, ...), so the class is legible to anyone holding the repository; both fixtures of a case share the hash, so the condition is not | by design (B60 binds verdicts to that hash); the reviewer is bound by procedure, and F05 already records that the task wording gives the class away |

## 3. Held

- **Case and whitespace variants** (the PR #1 fix as advertised): `Anthony`, `anthony `, `AnThOnY`
  refused at import against a recorded `anthony`; `agreement_between_reviewers` refuses them;
  colliding literals already in a ledger count once and are listed under `reviewer_ref_collisions`.
- **Cross-packet identity** (`a3_...py`): two exports of one run have disjoint item ids and
  different packet ids (same `source_sha256` set); ratings for packet A are refused against packet
  B on both `packet_id` and `packet_sha256`; `Tony` on packet A is refused because `tony` exists on
  packet B (the collision check is ledger-wide). Each packet stays `single_reviewer_reviewed`.
- **Key and packet tampering** (`a3_...py` A5b, A5c): a key with an entry removed names the
  missing item; a zeroed key hash is refused; a one-character edit to `packet.json` is refused on
  the ratings file's hash.
- **Partial coverage** (`a6_coverage_games.py`): a second human covering 1 of 36 items leaves
  status `single_reviewer_reviewed`, label `single-reviewer`, 1 item independent. On a synthetic
  two-dimension item, a reviewer who rated one dimension never covers. A hand-edited `model` record
  with `counts_as_vote: true` and a `human` record with `counts_as_vote: false` are both excluded.
  Legacy `B` on d1 and `b` on d2 merge into one covering reviewer, which is correct: one person did
  rate both dimensions.
- **Three partial humans** (A6b: anthony 36, bob 1-18, carol 19-36) reach `independently_reviewed`.
  That matches the contract's definition (every item has two distinct covering humans). Observation,
  not a defeat: the agreement block shows only the best pair over its 18 common items; `n_items`
  says 18 but nothing says "of 36" at packet level.
- **Legacy tie-break** (A2a-d) behaves as the `status.py` docstring says: equal revisions go to the
  later line, a higher revision wins even when a colliding literal's lower revision is
  chronologically newer (A2d). Observation: once a ledger holds `anthony`/`Anthony`/`ANTHONY`,
  importing the exact literal `anthony` is refused too (A2f), while the message says "reuse the
  recorded reference exactly". Strict direction; the message is wrong for that case.
- **Leakage** (`a7_leakage.py`): token hits in `packet.json` and `index.html` are CSS `class`
  attributes, `expected_revision` inside recorded action objects, a hex `c2`, and the packet's own
  instruction and claim-boundary sentences. No script, comment or link in the HTML; two `meta`
  tags (charset, viewport). Every item has a unique resource-id pair, so there is no grouping
  fingerprint beyond the task wording F05 already records. The step shape (a `read_resource`
  before the write, or not) is the sequence the reviewer is asked to judge, not a leak.
- **`agreement_between_reviewers`** cannot be made to raise from inside `review_status`: the pair
  it is handed are display names keyed by canonical form, so they are never canonically equal.

## 4. The patch

`proposed-fixes.patch` (5 files, +86/-14) applies cleanly to `17860e0`. Replayed in a worktree:
D1, D2, D3, D4, D5 and D6 each refuse as described above (`transcripts/after-patch/`). The full
suite there (`pytest -x`): 488 passed, 2 skipped before the first expected failure; the review
subset (`tests/review`, `tests/integration/test_cli_review.py`, `tests/commissioning`): 355 passed,
14 failed, every failure in a test that encodes the behaviour D1, D2 or D6 changes, none elsewhere. Those tests need the one-line
adjustments described; no fixture, receipt or decision file is touched.

Suggested order for the parent session: D1 and D5 (inside B61's wording, no decision needed
beyond the `anthony vasquez` question), then D2 (one status-test helper change, a new output key),
then D3 and D4 (strict-direction legacy handling), then D6 if F09 is read as "UTC".

## 5. Boundaries kept

No model called. No Stack or external write. Every state root and packet export under the session
scratch directory; the default `HS_STATE_ROOT` never used (`_lib.py` strips it from the
environment). `src/`, `tests/`, `cases/`, `docs/receipts/`, `docs/DECISIONS.md` unchanged on this
branch; the patch was applied only in a throwaway worktree that is removed. Scratch paths in the
transcripts are replaced by `SCRATCH`. The relay author of this report is a contributor, not a
reviewer, and nothing here is a human rating.

## 6. Reproducing

```sh
uv sync
cd docs/audits/cloud/redteam-identity
export HS_RT_SCRATCH=$(mktemp -d)           # every state root and export lands here
uv run python a1_ref_variants.py            # D1
uv run python a22_status_unbound.py         # D2
uv run python a2_legacy_collisions.py       # D3 (A2g), D4 (A2e), tie-break
uv run python a3_a4_a5_cross_packet_relabel_key.py   # cross-packet, D5, H1, H2
uv run python a6_coverage_games.py          # coverage games
uv run python a7_leakage.py                 # leak scan, H5
uv run python a8_rated_at.py                # D6
uv run python a9_direct_python.py           # direct module calls, H4
# with the patch: git worktree add WT HEAD && git -C WT apply proposed-fixes.patch
# HS_RT_REPO=WT uv run --project WT python a1_ref_variants.py   (and so on)
```
