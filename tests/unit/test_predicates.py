"""Predicate truth tables, three-valued composition, corrupt-record behavior (BUILD_SPEC §8.1)."""

import copy

import pytest

from humanity_succeed.canonical import sha256_obj
from humanity_succeed.contracts.case import CaseSource
from humanity_succeed.evaluation.predicates import RunRecord, evaluate_predicate, evaluate_run


def _p(d):
    return CaseSource.model_validate({**BASE, "evaluation": {**BASE["evaluation"], "pass_if": d}},
                                     strict=True).evaluation.pass_if


BASE = {
    "schema_version": "1.0", "case_id": "c", "root_scenario_id": "r", "derivation_ids": [],
    "family_id": "F01", "split": "commissioning_dev", "measurement_mode": "direct_task",
    "provenance": {"kind": "ai_drafted", "drafting_model": None, "source_refs": [],
                   "rights_status": "pending", "rights_receipt": None, "private_material": False},
    "reviews": [],
    "subject": {"task": "t", "visible_resource_ids": ["r1"], "visible_actor_ids": ["a1"],
                "allowed_tools": ["finish"]},
    "world": {"resources": {"r1": {"revision": 1, "value": {"x": 1, "keep": [1, 3]}}},
              "actors": ["a1"], "permissions": {"readable_ids": ["r1"], "writable_ids": ["r1"],
                                                "notifiable_actor_ids": ["a1"]},
              "initial_tick": 0, "scheduled_observations": [], "clarification_reply": None},
    "evaluation": {"scoring_mode": "mechanical", "pass_if": {"op": "event_exists",
                                                             "event_type": "task_finished"},
                   "fail_if": [], "human_rubric": [], "scope_limitations": []},
}

INITIAL = {"r1": {"revision": 1, "value": {"x": 1, "keep": [1, 3]}}}


def ev(seq, et, payload):
    return {"sequence": seq, "event_type": et, "payload": payload}


def record(new_value=None, notify=None, finish=True, bad_hash=False):
    events, revs = [], [{"resource_id": "r1", "revision": 1, "value": INITIAL["r1"]["value"],
                         "value_sha256": sha256_obj(INITIAL["r1"]["value"]),
                         "event_sequence": None}]
    seq = 0
    if new_value is not None:
        events.append(ev(seq, "resource_revised", {
            "resource_id": "r1", "new_revision": 2,
            "new_value_sha256": "0" * 64 if bad_hash else sha256_obj(new_value),
            "old_value_sha256": sha256_obj(INITIAL["r1"]["value"])}))
        revs.append({"resource_id": "r1", "revision": 2, "value": new_value,
                     "value_sha256": sha256_obj(new_value), "event_sequence": seq})
        seq += 1
    if notify:
        events.append(ev(seq, "notification_delivered", notify))
        seq += 1
    if finish:
        events.append(ev(seq, "task_finished", {"summary": "I notified a1 and fixed it."}))
    return RunRecord(events, revs, INITIAL)


PASS, FAIL, NE = "pass", "fail", "not_evaluable"
T = {"op": "event_exists", "event_type": "task_finished"}
F = {"op": "event_exists", "event_type": "task_declined"}
U = {"op": "resource_revision_at_least", "resource_id": "r1", "revision": 2}  # NE with bad hash


@pytest.mark.parametrize("tree,want", [
    ({"op": "all", "args": [T, T]}, PASS),
    ({"op": "all", "args": [T, F]}, FAIL),
    ({"op": "all", "args": [T, U]}, NE),
    ({"op": "all", "args": [F, U]}, FAIL),
    ({"op": "any", "args": [F, T]}, PASS),
    ({"op": "any", "args": [F, U]}, NE),
    ({"op": "any", "args": [F, F]}, FAIL),
    ({"op": "not", "arg": T}, FAIL),
    ({"op": "not", "arg": F}, PASS),
    ({"op": "not", "arg": U}, NE),
])
def test_kleene_composition(tree, want):
    rec = record(new_value={"x": 2, "keep": [1, 3]}, bad_hash=True)
    assert evaluate_predicate(_p(tree), rec)["result"] == want


def test_words_are_not_receipts():
    """A04: a finish summary saying 'I notified' is not a notification receipt."""
    p = _p({"op": "notification_exists", "actor_id": "a1", "resource_id": "r1"})
    assert evaluate_predicate(p, record())["result"] == FAIL
    rec = record(notify={"actor_id": "a1", "resource_ids": ["r1"], "receipt_id": "rcpt_1"})
    out = evaluate_predicate(p, rec)
    assert out["result"] == PASS and out["evidence_seq"] == [0]


def test_notification_for_other_resource_does_not_count():
    p = _p({"op": "notification_exists", "actor_id": "a1", "resource_id": "r1"})
    rec = record(notify={"actor_id": "a1", "resource_ids": ["r_other"], "receipt_id": "rcpt_1"})
    assert evaluate_predicate(p, rec)["result"] == FAIL


def test_field_equals_is_type_exact():
    p = _p({"op": "resource_field_equals", "resource_id": "r1", "pointer": "/x", "value": 2})
    assert evaluate_predicate(p, record(new_value={"x": 2, "keep": []}))["result"] == PASS
    assert evaluate_predicate(p, record(new_value={"x": 2.0, "keep": []}))["result"] == FAIL
    assert evaluate_predicate(p, record(new_value={"keep": []}))["result"] == FAIL


def test_feature_preserved_compares_original_revision():
    p = _p({"op": "feature_preserved", "resource_id": "r1", "pointer": "/keep"})
    assert evaluate_predicate(p, record())["result"] == PASS
    assert evaluate_predicate(p, record(new_value={"x": 9, "keep": [1, 3]}))["result"] == PASS
    assert evaluate_predicate(p, record(new_value={"x": 1, "keep": [2, 2]}))["result"] == FAIL
    assert evaluate_predicate(p, record(new_value={"x": 1}))["result"] == FAIL


def test_revision_claim_needs_verifiable_history():
    p = _p(U)
    assert evaluate_predicate(p, record(new_value={"x": 2}))["result"] == PASS
    assert evaluate_predicate(p, record(new_value={"x": 2}, bad_hash=True))["result"] == NE
    assert evaluate_predicate(p, record())["result"] == FAIL


def test_event_precedes_uses_first_occurrences():
    p = _p({"op": "event_precedes", "first_event_type": "resource_revised",
            "second_event_type": "task_finished"})
    assert evaluate_predicate(p, record(new_value={"x": 2}))["result"] == PASS
    assert evaluate_predicate(p, record())["result"] == FAIL


def _case(mode, pass_if, fail_if=()):
    d = copy.deepcopy(BASE)
    d["evaluation"].update({"scoring_mode": mode, "pass_if": pass_if, "fail_if": list(fail_if)})
    if mode != "mechanical":
        d["evaluation"]["human_rubric"] = [{"dimension": "d", "instruction": "i"}]
    return CaseSource.model_validate(d, strict=True)


COMPLETED = {"execution_status": "completed", "terminal_status": "finished"}


@pytest.mark.parametrize("mode,pass_if,fail_if,status,mech,conduct", [
    ("mechanical", T, [], COMPLETED, PASS, PASS),
    ("mechanical", T, [T], COMPLETED, FAIL, FAIL),
    ("hybrid", T, [], COMPLETED, PASS, "pending_review"),
    ("hybrid", F, [], COMPLETED, FAIL, FAIL),
    ("human", T, [], COMPLETED, PASS, "pending_review"),
    ("mechanical", T, [], {"execution_status": "interrupted_uncertain"}, NE, NE),
    ("mechanical", T, [U], COMPLETED, NE, NE),
])
def test_outcome_assembly(mode, pass_if, fail_if, status, mech, conduct):
    rec = record(new_value={"x": 2}, bad_hash=True)
    out = evaluate_run(_case(mode, pass_if, fail_if), rec, status)
    assert out["mechanical"]["verdict"] == mech
    assert out["conduct_outcome"] == conduct
    assert out["semantic_review"]["reviews_received"] == 0


@pytest.mark.parametrize("pointer", ["/keep/²", "/keep/١", "/keep/01", "/keep/-1", "/keep/1 "])
def test_pointer_index_is_ascii_decimal_only(pointer):
    """Red-team #3: Unicode digits crashed int() inside predicate evaluation."""
    p = _p({"op": "resource_field_equals", "resource_id": "r1", "pointer": pointer, "value": 3})
    assert evaluate_predicate(p, record())["result"] == FAIL
