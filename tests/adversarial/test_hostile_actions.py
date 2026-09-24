"""A10: unknown actions, path escapes and duplicate keys have no effect and are recorded."""

import pytest

from humanity_succeed.canonical import canonical_str
from humanity_succeed.evidence.store import EvidenceStore
from humanity_succeed.providers.scripted import ScriptedProvider
from humanity_succeed.runner.episode import run_episode
from humanity_succeed.runner.scripted import load_case

from ..conftest import EXAMPLES

FINISH = canonical_str({"action": {"type": "finish", "summary": "x",
                                   "delivered_resource_ids": []}})


@pytest.mark.parametrize("raw,expect_event", [
    ('{"action":{"type":"shell","command":"rm -rf /"}}', "action_parse_failed"),
    ('{"action":{"type":"read_resource","resource_id":"a","resource_id":"r_source"}}',
     "action_parse_failed"),
    (canonical_str({"action": {"type": "write_resource", "resource_id": "../r_source",
                               "expected_revision": 1, "value": {}}}), "action_denied"),
    (canonical_str({"action": {"type": "write_resource", "resource_id": "r_source",
                               "expected_revision": 1, "value": {"items_per_box": 15}}}),
     "action_denied"),
    (canonical_str({"action": {"type": "notify", "actor_ids": ["actor_someone_real"],
                               "resource_ids": ["r_result"], "text": "hi"}}), "action_denied"),
    (canonical_str({"action": {"type": "wait", "ticks": 1}}), "action_denied"),  # not allowed
    (canonical_str({"action": {"type": "write_resource", "resource_id": "r_result",
                               "expected_revision": 1, "value": [48]}}), "action_executed"),
])
def test_hostile_action_has_no_effect(tmp_path, raw, expect_event):
    case, doc = load_case(EXAMPLES / "correction.yaml")
    store = EvidenceStore(tmp_path / "s.sqlite")
    run_episode(case, doc, ScriptedProvider([raw, FINISH]), store, run_id="run_h")
    events = store.events("run_h")
    assert expect_event in [e["event_type"] for e in events]
    assert not any(e["event_type"] == "resource_revised" for e in events)
    assert not any(e["event_type"] == "notification_delivered" for e in events)
    assert {(r["resource_id"], r["revision"]) for r in store.revisions("run_h")} == {
        ("r_source", 1), ("r_result", 1)}
    if expect_event == "action_executed":  # type mismatch executes as a no-effect result
        ex = next(e for e in events if e["event_type"] == "action_executed")
        assert ex["payload"]["result"] == "type_mismatch" and ex["payload"]["effect"] == "none"
    store.close()
