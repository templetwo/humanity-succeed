"""Stage 0 freeze (semantic-controls build): packet/1 reviewer-facing text and render are pinned.

If this test goes red, packet/1 changed. That is a decision (B69 says the existing packet is not
altered), not a regression to paper over: re-capture only with a DECISIONS row that says so.
Vacuity control: the baseline is compared field by field, and a perturbed manifest must differ.
"""

from __future__ import annotations

import json
from pathlib import Path

from humanity_succeed.canonical import canonical_bytes, sha256_bytes

from .capture_review_v1_text import SCHEMA_ID, measure, synthetic_manifest

BASELINE = Path(__file__).with_name("review_v1_text.json")


def test_packet_v1_text_and_render_are_frozen() -> None:
    baseline = json.loads(BASELINE.read_text())
    assert baseline["schema_id"] == SCHEMA_ID
    now = measure()
    assert now == baseline, {k: (baseline.get(k), now.get(k)) for k in now if now[k] != baseline.get(k)}


def test_freeze_notices_a_changed_packet() -> None:
    """Positive control: the digest moves when the reviewer-facing text moves."""
    baseline = json.loads(BASELINE.read_text())
    m = synthetic_manifest()
    perturbed = m.model_copy(update={"instructions": m.instructions + " (changed)"})
    digest = sha256_bytes(canonical_bytes(perturbed.model_dump(mode="json")))
    assert digest != baseline["synthetic_packet_sha256"]
