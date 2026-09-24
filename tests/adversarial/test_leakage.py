"""A01 and §4.3: evaluator-only, host-only and future content never reaches the provider."""

import copy
import uuid

import pytest
import yaml

from humanity_succeed.canonical import canonical_bytes, canonical_str
from humanity_succeed.corpus import views
from humanity_succeed.corpus.lint import find_canaries
from humanity_succeed.evidence.store import EvidenceStore
from humanity_succeed.providers.scripted import ScriptedProvider
from humanity_succeed.runner.episode import run_episode
from humanity_succeed.runner.scripted import load_case


def act(**a):
    return canonical_str({"action": a})


def canary(tag):
    return f"CANARY-{tag}-{uuid.uuid4().hex[:10]}"


@pytest.fixture
def canaried(tmp_path, correction_doc):
    d = copy.deepcopy(correction_doc)
    c = {k: canary(k) for k in ("case_id", "root", "family", "rubric", "scope", "expected",
                                "source_ref", "drafter", "demo_text", "hidden_res", "future",
                                "clar", "demo_id")}
    d["case_id"] = c["case_id"]
    d["root_scenario_id"] = c["root"]
    d["family_id"] = c["family"]
    d["provenance"]["source_refs"] = [c["source_ref"]]
    d["provenance"]["drafting_model"] = c["drafter"]
    d["evaluation"]["human_rubric"][0]["instruction"] = c["rubric"]
    d["evaluation"]["scope_limitations"] = [c["scope"]]
    d["evaluation"]["pass_if"]["args"].append(
        {"op": "any", "args": [{"op": "resource_field_equals", "resource_id": "r_result",
                                "pointer": "/note", "value": c["expected"]},
                               {"op": "event_exists", "event_type": "task_finished"}]})
    d["demonstrations"][0]["demo_id"] = c["demo_id"]
    d["demonstrations"][0]["actions"][1]["action"]["text"] = c["demo_text"]
    # a resource that exists in the world but is not readable by the subject
    d["world"]["resources"]["r_hidden"] = {"revision": 1, "value": {"secret": c["hidden_res"]}}
    # a future event the episode never reaches, and a clarification never requested
    d["world"]["scheduled_observations"] = [{"at_tick": 50, "observation": c["future"]}]
    d["world"]["clarification_reply"] = c["clar"]
    p = tmp_path / "canaried.yaml"
    p.write_text(yaml.safe_dump(d, sort_keys=False))
    return p, c


HOSTILE_SCRIPT = [
    "not json at all",                                                   # parse-error path
    '{"action":{"type":"read_resource","resource_id":"r_x","resource_id":"r_y"}}',
    act(type="read_resource", resource_id="r_hidden"),                   # unreadable
    act(type="read_resource", resource_id="../../evaluator.json"),       # path escape
    act(type="write_resource", resource_id="r_hidden", expected_revision=1, value={}),
    act(type="write_resource", resource_id="r_result", expected_revision=7,
        value={"total": 48}),                                            # revision conflict
    act(type="read_resource", resource_id="r_source"),
    act(type="write_resource", resource_id="r_result", expected_revision=1,
        value={"total": 48}),
    act(type="notify", actor_ids=["actor_avery"], resource_ids=["r_result"], text="corrected"),
    act(type="wait", ticks=3),                                           # future stays hidden
    act(type="finish", summary="done", delivered_resource_ids=["r_result"]),
]


def test_no_hidden_byte_reaches_the_provider(tmp_path, canaried):
    path, c = canaried
    case, doc = load_case(path)
    store = EvidenceStore(tmp_path / "s.sqlite")
    prov = ScriptedProvider(HOSTILE_SCRIPT)
    run_episode(case, doc, prov, store, run_id="run_leak")
    seen = b"".join(prov.received_inputs)
    assert len(prov.received_inputs) == len(HOSTILE_SCRIPT)
    assert find_canaries(seen, list(c.values())) == []
    # host-side views, by contrast, do carry them (the canaries are real)
    host = canonical_bytes(views.four_views(case, doc))
    assert set(find_canaries(host, list(c.values()))) == set(c.values())
    store.close()


def test_unknown_and_unreadable_are_indistinguishable(tmp_path, canaried):
    path, _ = canaried
    case, doc = load_case(path)
    store = EvidenceStore(tmp_path / "s.sqlite")
    prov = ScriptedProvider([act(type="read_resource", resource_id="r_hidden"),
                             act(type="read_resource", resource_id="r_nope"),
                             act(type="finish", summary="x", delivered_resource_ids=[])])
    run_episode(case, doc, prov, store, run_id="run_x")
    import json
    last = json.loads(prov.received_inputs[-1])["messages"]
    tool_msgs = [m["content"] for m in last if m["role"] == "tool"]
    assert tool_msgs[0] == tool_msgs[1] == '{"reason":"not_permitted","status":"denied"}'
    store.close()


def test_deliberately_leaky_serializer_is_caught(tmp_path, canaried, monkeypatch):
    """The detector is not vacuous: a serializer that leaks the evaluator view is caught."""
    path, c = canaried
    case, doc = load_case(path)
    leaky_payload = canonical_bytes(views.evaluator_view(case))
    real = views.build_provider_input

    def leaky(view, tick0, turns):
        return real(view, tick0, turns) + leaky_payload

    import humanity_succeed.runner.episode as ep
    monkeypatch.setattr(ep, "build_provider_input", leaky)
    store = EvidenceStore(tmp_path / "s.sqlite")
    prov = ScriptedProvider([act(type="finish", summary="x", delivered_resource_ids=[])])
    run_episode(case, doc, prov, store, run_id="run_leaky")
    assert find_canaries(b"".join(prov.received_inputs), [c["rubric"], c["scope"]])
    store.close()


def test_observation_builder_rejects_non_subject_input(correction_doc):
    from humanity_succeed.contracts.case import CaseSource
    case = CaseSource.model_validate(correction_doc, strict=True)
    with pytest.raises(TypeError):
        views.build_provider_input(case, 0, [])  # type: ignore[arg-type]


def test_released_scheduled_observation_is_visible_only_after_wait(tmp_path, correction_doc):
    d = copy.deepcopy(correction_doc)
    d["subject"]["allowed_tools"].append("wait")
    mark = canary("sched")
    d["world"]["scheduled_observations"] = [{"at_tick": 2, "observation": mark}]
    p = tmp_path / "s.yaml"
    p.write_text(yaml.safe_dump(d, sort_keys=False))
    case, doc = load_case(p)
    store = EvidenceStore(tmp_path / "s.sqlite")
    prov = ScriptedProvider([act(type="wait", ticks=1), act(type="wait", ticks=1),
                             act(type="finish", summary="x", delivered_resource_ids=[])])
    run_episode(case, doc, prov, store, run_id="run_sched")
    assert not find_canaries(prov.received_inputs[1], [mark])  # after tick 1: still hidden
    assert find_canaries(prov.received_inputs[2], [mark])      # after tick 2: released
    store.close()
