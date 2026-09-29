"""Blind review: the shared contract (BUILD_SPEC §11, §12; DECISIONS B60, B61; A1 Pilot §10).

Written by the lead before fan-out. Builders must NOT edit this file; report defects instead.

What it serves now: Anthony's single-reviewer semantic review of the judgment-heavy commissioning
fixtures (the 36 hybrid-pass fixtures of suite v1). The rules it encodes are rulings, not options:

- Verdicts are the reviewer's OWN WORDS bound to the case hash he reviewed (ruling 06d942da, B60).
  No code path writes a human rating. A rating file is supplied by the operator; a seat-written
  "Anthony confirms" is not a review.
- Only ``reviewer_kind == "human"`` ratings are votes. Model ratings may be imported, labelled
  secondary, and are never counted (PROTOCOL §9: AI reviewers cannot satisfy the human count).
- Repeated ratings by one ``reviewer_ref`` are revisions, never extra reviewers (B61). Independence
  needs at least two DISTINCT human ``reviewer_ref`` values.
- No agreement statistic is computed from one reviewer (ruling 06d942da; D14).
- Packets are blind (BUILD_SPEC §11; A19): no fixture/case/group/class ids, roles, expectations,
  evaluator verdicts, predicates or condition-specific file names reach the reviewer. The
  item-to-fixture key is operator-only and lives under the state root, not in the packet.
- Ratings are append-only with explicit revisions.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

PACKET_SCHEMA = "hs-review-packet/1"
KEY_SCHEMA = "hs-review-key/1"
RATINGS_SCHEMA = "hs-review-ratings/1"
RECORD_SCHEMA = "hs-review-record/1"
STATUS_SCHEMA = "hs-review-status/1"

PACKET_FILE = "packet.json"            # in the export directory (reviewer-facing)
PACKET_HTML = "index.html"             # in the export directory (reviewer-facing, static, offline)
RATINGS_TEMPLATE = "ratings-template.json"  # in the export directory, blanks for the reviewer
KEY_DIR = ("reviews", "keys")          # state_root/reviews/keys/<packet_id>.json (operator-only)
LEDGER_PATH = ("reviews", "ledger.jsonl")   # state_root/reviews/ledger.jsonl (append-only)

REVIEW_MODE_SINGLE = "single-reviewer"      # the label every report built on one reviewer carries
VERDICTS = ("pass", "fail")

# Semantic-commissioning statuses a review status report may use (also appended to
# commissioning.contract.SEMANTIC_STATUSES). Nothing else is allowed.
STATUS_PENDING = "pending_no_human_reviews"
STATUS_PARTIAL = "single_reviewer_partial"          # some, not all, items have a human verdict
STATUS_SINGLE = "single_reviewer_reviewed"          # every item has >= 1 human verdict, < 2 distinct
STATUS_INDEPENDENT = "independently_reviewed"       # every item has >= 2 distinct human reviewers
REVIEW_STATUSES = (STATUS_PENDING, STATUS_PARTIAL, STATUS_SINGLE, STATUS_INDEPENDENT)

ItemId = Annotated[str, Field(pattern=r"^it_[0-9a-f]{16}$")]
PacketId = Annotated[str, Field(pattern=r"^pk_[0-9a-f]{16}$")]
Sha256 = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
NonEmpty = Annotated[str, Field(min_length=1)]


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class RubricLine(_Strict):
    dimension: NonEmpty
    instruction: NonEmpty


class VisibleStep(_Strict):
    """One turn of the actual recorded sequence, as the reviewer sees it: what the subject proposed
    and what the environment did. Taken from the verified bundle's events, never from a trajectory
    file and never from the evaluation."""

    turn: Annotated[int, Field(ge=0)]
    proposed: dict          # the action object exactly as recorded (action_proposed.payload.action)
    message: str | None     # the subject's free-text message, if any
    outcome: NonEmpty       # plain description: "allowed: resource revised to …", "denied", …


class PacketItem(_Strict):
    item_id: ItemId
    task: NonEmpty                      # the subject-visible task text
    visible_resources: dict             # initial values of the subject-visible resources
    steps: list[VisibleStep]
    rubric: Annotated[list[RubricLine], Field(min_length=1)]
    question: NonEmpty
    allowed_verdicts: list[Literal["pass", "fail"]]
    source_sha256: Sha256               # contracts.case.review_source_sha256 of the case reviewed
                                        # (the rubric is inside that hash)


class PacketManifest(_Strict):
    schema_id: Literal["hs-review-packet/1"]
    packet_id: PacketId
    mode: Literal["single-reviewer"]
    created_from: dict                  # {"run_report_sha256", "plan_sha256"} of the source run
    instructions: NonEmpty
    items: Annotated[list[PacketItem], Field(min_length=1)]
    claim_boundary: NonEmpty


class KeyEntry(_Strict):
    item_id: ItemId
    fixture_id: NonEmpty
    case: NonEmpty                      # suite-relative case path
    bundle: NonEmpty                    # run-relative bundle path


class PacketKey(_Strict):
    """Operator-only. Never written into the export directory."""

    schema_id: Literal["hs-review-key/1"]
    packet_id: PacketId
    packet_sha256: Sha256               # sha256 of the exported packet.json bytes
    order_note: NonEmpty                # how the item order was derived
    entries: list[KeyEntry]


class Rating(_Strict):
    item_id: ItemId
    dimension: NonEmpty
    verdict: Literal["pass", "fail"]
    words: Annotated[str, Field(min_length=1)]   # the reviewer's own words; blank is refused


class RatingsFile(_Strict):
    """Filled in by the reviewer, supplied by the operator to `hs review import`."""

    schema_id: Literal["hs-review-ratings/1"]
    packet_id: PacketId
    packet_sha256: Sha256
    reviewer_ref: NonEmpty              # a stable identity reference, e.g. "anthony-vasquez-sr"
    reviewer_kind: Literal["human", "model"]
    rated_at_utc: NonEmpty
    ratings: Annotated[list[Rating], Field(min_length=1)]


class ReviewRecord(_Strict):
    """One line of the append-only ledger (state_root/reviews/ledger.jsonl)."""

    schema_id: Literal["hs-review-record/1"]
    packet_id: PacketId
    item_id: ItemId
    fixture_id: NonEmpty                # resolved from the operator key at import
    source_sha256: Sha256
    dimension: NonEmpty
    verdict: Literal["pass", "fail"]
    words: NonEmpty
    reviewer_ref: NonEmpty
    reviewer_kind: Literal["human", "model"]
    counts_as_vote: bool                # True only for reviewer_kind == "human"
    revision: Annotated[int, Field(ge=1)]   # 1 for the first record of (reviewer, item, dimension)
    rated_at_utc: NonEmpty
    ratings_file_sha256: Sha256


# ---------------------------------------------------------------- function signatures (builders)
#
# review/export.py     export_packet(run_dir: Path, out: Path, *, state_root: Path,
#                                    repo_root: Path) -> dict
#     Reads report.json in a commission run directory, verifies every judgment-heavy fixture's
#     bundle (evidence.bundle.verify_bundle must be "consistent" or export refuses), builds one
#     PacketItem per judgment-heavy fixture, orders items deterministically by sha256 of
#     (packet_id, item_id), writes PACKET_FILE, PACKET_HTML and RATINGS_TEMPLATE into a NEW `out`
#     directory and the PacketKey under state_root/KEY_DIR. Runs leak_check first and refuses on
#     any hit. Returns {"status": "ok"|"blocked_leak"|"blocked_input", "packet_id", "items",
#     "problems", "paths"}.
# review/leak.py       forbidden_tokens(report: dict, suite_manifest: SuiteManifest) -> set[str]
#                      leak_check(text: str, forbidden: set[str]) -> list[str]
# review/importer.py   import_ratings(packet_path: Path, ratings_path: Path, *,
#                                     state_root: Path) -> dict
#     Validates RatingsFile strictly against the packet (packet_sha256 matches the manifest bytes;
#     every item_id and dimension exists; verdict allowed; words non-blank after strip), resolves
#     fixture ids via the operator key, appends ReviewRecord lines (never rewrites), numbers
#     revisions. Returns {"status": "ok"|"refused", "recorded", "votes", "secondary", "problems"}.
# review/ledger.py     ledger_path(state_root) -> Path; read_records(state_root, packet_id=None)
#                      -> list[ReviewRecord]; append_records(state_root, records) -> None
# review/status.py     review_status(packet_path: Path, *, state_root: Path) -> dict
#     Per item: distinct human reviewer_refs (latest revision per reviewer counts), verdicts.
#     Overall status from REVIEW_STATUSES; label REVIEW_MODE_SINGLE whenever fewer than two
#     distinct human reviewers exist; agreement computed ONLY through
#     commissioning.agreement.agreement_between_reviewers and ONLY when two distinct humans rated
#     the same items; otherwise {"agreement": null, "reason": ...}.
# commissioning/agreement.py  agreement_between_reviewers(ref_a, ratings_a, ref_b, ratings_b,
#                              labels) -> dict  — raises ValueError when ref_a == ref_b.
