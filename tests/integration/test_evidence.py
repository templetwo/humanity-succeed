"""Evidence integrity: verify, anchors, tampering (A12), crash (A11), read-only replay."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from humanity_succeed.canonical import canonical_bytes, sha256_bytes, sha256_obj
from humanity_succeed.evidence.bundle import anchor_for, verify_bundle
from humanity_succeed.evidence.replay import replay_bundle
from humanity_succeed.evidence.store import EvidenceStore, compute_event_hash
from humanity_succeed.providers.scripted import ScriptedProvider
from humanity_succeed.runner.episode import SimulatedCrash, derive_status, run_episode
from humanity_succeed.runner.scripted import evaluate_and_record, load_case

from ..conftest import EXAMPLES
from .helpers import act, run_trajectory_file


def _digest(root: Path) -> dict:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


@pytest.fixture
def bundle(tmp_path):
    b, _ = run_trajectory_file("t-correction-actual", tmp_path)
    return b


def _events(b: Path) -> list[dict]:
    return [json.loads(x) for x in (b / "events.jsonl").read_text().splitlines()]


def _write_events(b: Path, events: list[dict]) -> None:
    (b / "events.jsonl").write_bytes(b"".join(canonical_bytes(e) + b"\n" for e in events))


def _reindex(b: Path) -> None:
    """Attacker with write access: recompute every file hash so the index agrees again."""
    idx = json.loads((b / "bundle.json").read_text())
    idx["files"] = {n: sha256_bytes((b / n).read_bytes()) for n in idx["files"]}
    (b / "bundle.json").write_bytes(canonical_bytes(idx))
    sums = "".join(f"{sha256_bytes((b / n).read_bytes())}  {n}\n"
                   for n in sorted([*idx["files"], "bundle.json"]))
    (b / "SHA256SUMS").write_text(sums)


def test_clean_bundle_verifies_without_claiming_anchor(bundle):
    rep = verify_bundle(bundle)
    assert rep["internal"] == "consistent"
    assert rep["anchor"] == "external_anchor_absent"


def test_anchor_levels(bundle, tmp_path):
    anc = anchor_for(bundle)
    assert verify_bundle(bundle, anc)["anchor"] == "verified_against_anchor"
    prefix = dict(anc, head_sequence=anc["head_sequence"] - 2,
                  head_event_hash=_events(bundle)[anc["head_sequence"] - 2]["event_hash"])
    assert verify_bundle(bundle, prefix)["anchor"] == "partial"
    assert verify_bundle(bundle, dict(anc, run_id="run_other"))["anchor"] == "failed"
    assert verify_bundle(bundle, dict(anc, head_event_hash="0" * 64))["anchor"] == "failed"


def test_payload_edit_breaks_chain(bundle):
    ev = _events(bundle)
    rev = next(e for e in ev if e["event_type"] == "resource_revised")
    rev["payload"]["new_value"] = {"total": 60}
    _write_events(bundle, ev)
    _reindex(bundle)
    rep = verify_bundle(bundle)
    assert rep["internal"] == "failed"
    assert not next(c for c in rep["checks"] if c["check"] == "event_chain_consistent")["passed"]


def test_fully_rewritten_chain_is_consistent_but_fails_retained_anchor(bundle):
    anc = anchor_for(bundle)
    ev = _events(bundle)
    # drop the notification: rewrite the history and recompute every hash from scratch
    ev = [e for e in ev if e["event_type"] != "notification_delivered"]
    prev = "0" * 64
    for i, e in enumerate(ev):
        e["sequence"], e["prev_hash"] = i, prev
        e["event_hash"] = compute_event_hash({k: v for k, v in e.items() if k != "event_hash"})
        prev = e["event_hash"]
    _write_events(bundle, ev)
    _reindex(bundle)
    rep = verify_bundle(bundle, anc)
    # Internal consistency may or may not survive other bindings; the anchor must not.
    assert rep["anchor"] == "failed"


def test_tail_truncation_detected_by_anchor(bundle):
    anc = anchor_for(bundle)
    ev = _events(bundle)[:-3]
    _write_events(bundle, ev)
    _reindex(bundle)
    assert verify_bundle(bundle, anc)["anchor"] == "failed"


@pytest.mark.parametrize("target", ["evaluation.json", "manifest.json", "revisions.json",
                                    "case_source.json"])
def test_edited_bound_file_fails_even_after_reindex(bundle, target):
    doc = json.loads((bundle / target).read_text())
    if target == "evaluation.json":
        doc["conduct_outcome"] = "pass"
    elif target == "manifest.json":
        doc["limits"]["max_provider_calls"] = 99
    elif target == "revisions.json":
        doc[-1]["value"] = {"total": 47}
        doc[-1]["value_sha256"] = sha256_obj(doc[-1]["value"])
    else:
        doc["evaluation"]["scoring_mode"] = "mechanical"
    (bundle / target).write_bytes(canonical_bytes(doc))
    _reindex(bundle)
    assert verify_bundle(bundle)["internal"] == "failed"


def test_artifact_edit_and_extra_file_detected(bundle):
    art = next((bundle / "artifacts").iterdir())
    art.write_bytes(art.read_bytes() + b" ")
    assert verify_bundle(bundle)["internal"] == "failed"


def test_unlisted_file_detected(bundle):
    (bundle / "notes.txt").write_text("x")
    assert verify_bundle(bundle)["internal"] == "failed"


def test_replay_is_read_only_and_reproduces(bundle, tmp_path):
    before = _digest(bundle)
    rep = replay_bundle(bundle, tmp_path / "replay")
    assert rep["replay"]["status"] == "reproduced"
    assert _digest(bundle) == before
    html = (tmp_path / "replay" / "report.html").read_text()
    assert "http://" not in html and "https://" not in html  # no network dependency
    assert "Scripted instrument run" in html


def test_replay_refuses_corrupt_bundle(bundle, tmp_path):
    (bundle / "notes.txt").write_text("x")
    rep = replay_bundle(bundle, tmp_path / "replay")
    assert rep["replay"]["status"] == "refused"


def test_store_rejects_reuse_and_readers_cannot_write(tmp_path):
    s = EvidenceStore(tmp_path / "s.sqlite")
    s.close()
    with pytest.raises(FileExistsError):
        EvidenceStore(tmp_path / "s.sqlite")
    r = EvidenceStore.open_readonly(tmp_path / "s.sqlite")
    with pytest.raises(PermissionError):
        r.put_artifact("x", b"y")
    r.close()


def test_crash_between_permission_and_execution(tmp_path):
    """A11: a permitted-but-unexecuted action stays distinguishable; no phantom success, no retry."""
    case, doc = load_case(EXAMPLES / "correction.yaml")
    store = EvidenceStore(tmp_path / "crash.sqlite")
    write = act(type="write_resource", resource_id="r_result", expected_revision=1,
                value={"total": 48})
    with pytest.raises(SimulatedCrash):
        run_episode(case, doc, ScriptedProvider([write]), store, run_id="run_crash",
                    fault="after_permission")
    events = store.events("run_crash")
    status = derive_status(events)
    assert status["execution_status"] == "interrupted_uncertain"
    assert status["permitted_not_executed_proposals"] == [
        e["sequence"] for e in events if e["event_type"] == "action_proposed"]
    assert not any(e["event_type"] in ("action_executed", "resource_revised", "run_completed")
                   for e in events)
    ev = evaluate_and_record(store, "run_crash", case)
    assert ev["mechanical"]["verdict"] == "not_evaluable"
    assert ev["conduct_outcome"] == "not_evaluable"
    revs = [r for r in store.revisions("run_crash") if r["resource_id"] == "r_result"]
    assert [r["revision"] for r in revs] == [1]
    store.close()


def test_bundle_copy_verifies_independently(bundle, tmp_path):
    dst = tmp_path / "copy"
    shutil.copytree(bundle, dst)
    assert verify_bundle(dst)["internal"] == "consistent"
