"""review/importer.py with packet/2 (DECISIONS B69, B70): a /2 packet imports with its /2 key, a
packet and key of different versions are a named refusal, a malformed key is a named refusal, and
nothing else about import changes (verdicts stay pass/fail in the reviewer's own words; the key's
roles, sources and expected verdicts never reach the ledger).

Synthetic /2 packets and keys from tests/review/test_status_v2.py (built through the contract
models); ratings through RatingsFile as tests/review/test_import.py builds them.
"""

from __future__ import annotations

import json

import pytest

from humanity_succeed.review.contract import (
    KEY_SCHEMA,
    KeyEntry,
    PacketKey,
    Rating,
)
from humanity_succeed.review.importer import import_ratings
from humanity_succeed.review.ledger import ledger_path, read_records

from .test_import import Env, _ratings, _write_ratings, make_env
from .test_status_v2 import ALL_ITEMS, K1, M1, T1, D, E, make_v2


def _env(tmp_path, name: str = "v2") -> Env:
    v2 = make_v2(tmp_path, name=name)
    # test_import's Env/_ratings/_write_ratings read only these fields
    return Env(v2.state_root, v2.packet_dir, v2.packet_dir / "packet.json", v2.packet_sha256,
               v2.manifest, v2.key)


def _key_file(env: Env):
    return env.state_root.joinpath("reviews", "keys", f"{env.manifest.packet_id}.json")


def _ledger_bytes(env: Env) -> bytes:
    p = ledger_path(env.state_root)
    return p.read_bytes() if p.exists() else b""


def test_a_v2_packet_imports_with_its_v2_key(tmp_path):
    env = _env(tmp_path)
    ratings = _ratings(env, [
        Rating(item_id=M1, dimension=D, verdict="pass", words="Names the corrected total."),
        Rating(item_id=K1, dimension=D, verdict="pass", words="The total is right."),
        Rating(item_id=K1, dimension=E, verdict="fail", words="It blames the other person."),
        Rating(item_id=T1, dimension=D, verdict="pass", words="True and complete."),
    ], reviewer_ref="synthetic-reviewer")
    result = import_ratings(env.export_dir, _write_ratings(env, ratings), state_root=env.state_root)
    assert result == {"status": "ok", "recorded": 4, "votes": 4, "secondary": 0, "problems": []}

    records = read_records(env.state_root, packet_id=env.manifest.packet_id)
    by_pair = {(r.item_id, r.dimension): r for r in records}
    fixture_of = {e.item_id: e.fixture_id for e in env.key.entries}
    for (item_id, _dim), r in by_pair.items():
        assert r.fixture_id == fixture_of[item_id]
        assert r.revision == 1 and r.counts_as_vote
    assert by_pair[(K1, E)].verdict == "fail"
    # the key's roles, sources and expected verdicts never reach a ledger line
    text = _ledger_bytes(env).decode()
    for token in ("measured", "decoy", "known_fail", "supplement_run", "commission_run",
                  "expected_human_verdict", "role", "honest"):
        assert token not in text, token


def test_a_second_v2_import_numbers_revisions_as_before(tmp_path):
    env = _env(tmp_path)
    for n, verdict in enumerate(("pass", "fail"), start=1):
        ratings = _ratings(env, [Rating(item_id=M1, dimension=D, verdict=verdict, words="mine")],
                           reviewer_ref="synthetic-reviewer")
        assert import_ratings(env.export_dir, _write_ratings(env, ratings, f"r{n}.json"),
                              state_root=env.state_root)["status"] == "ok"
    assert [r.revision for r in read_records(env.state_root)] == [1, 2]


def test_a_v2_packet_with_a_v1_key_is_refused_by_name(tmp_path):
    env = _env(tmp_path)
    v1_key = PacketKey(schema_id=KEY_SCHEMA, packet_id=env.manifest.packet_id,
                       packet_sha256=env.packet_sha256, order_note="x",
                       entries=[KeyEntry(item_id=i, fixture_id="fx", case="c", bundle="b")
                                for i in ALL_ITEMS])
    _key_file(env).write_bytes(json.dumps(v1_key.model_dump(mode="json")).encode())
    ratings = _ratings(env, [Rating(item_id=M1, dimension=D, verdict="pass", words="w")])
    result = import_ratings(env.export_dir, _write_ratings(env, ratings), state_root=env.state_root)
    assert result["status"] == "refused" and result["recorded"] == 0
    assert len(result["problems"]) == 1
    assert "'hs-review-key/1' does not match packet schema_id 'hs-review-packet/2'" in result["problems"][0]
    assert "mixed versions are refused" in result["problems"][0]
    assert _ledger_bytes(env) == b""


def test_a_v1_packet_with_a_v2_key_is_refused_by_name(tmp_path):
    env = make_env(tmp_path, name="v1")
    v2 = make_v2(tmp_path, name="donor")
    doc = v2.key.model_dump(mode="json")
    doc["packet_id"] = env.manifest.packet_id
    doc["packet_sha256"] = env.packet_sha256
    _key_file(env).write_bytes(json.dumps(doc).encode())
    ratings = _ratings(env, [Rating(item_id=env.manifest.items[0].item_id,
                                    dimension=env.manifest.items[0].rubric[0].dimension,
                                    verdict="pass", words="w")])
    result = import_ratings(env.export_dir, _write_ratings(env, ratings), state_root=env.state_root)
    assert result["status"] == "refused" and result["recorded"] == 0
    assert "'hs-review-key/2' does not match packet schema_id 'hs-review-packet/1'" in result["problems"][0]
    assert _ledger_bytes(env) == b""


@pytest.mark.parametrize("mutate", [
    lambda d: d.pop("export_secret"),
    lambda d: d["entries"][0].update(role="control"),
    lambda d: d["entries"][0].update(source_index=2),
    lambda d: d.update(schema_id="hs-review-key/3"),
    lambda d: d.update(entries="none"),
])
def test_a_malformed_v2_key_is_a_named_refusal_not_a_raised_error(tmp_path, mutate):
    env = _env(tmp_path)
    doc = env.key.model_dump(mode="json")
    mutate(doc)
    _key_file(env).write_bytes(json.dumps(doc).encode())
    ratings = _ratings(env, [Rating(item_id=M1, dimension=D, verdict="pass", words="w")])
    result = import_ratings(env.export_dir, _write_ratings(env, ratings), state_root=env.state_root)
    assert result["status"] == "refused"
    assert any("invalid operator key" in p for p in result["problems"]), result["problems"]
    assert _ledger_bytes(env) == b""


def test_an_invalid_v2_packet_is_refused_as_an_invalid_manifest(tmp_path):
    env = _env(tmp_path)
    doc = env.manifest.model_dump(mode="json")
    doc["created_from"] = []          # /2 requires one or two sources
    env.packet_path.write_bytes(json.dumps(doc).encode())
    ratings = _ratings(env, [Rating(item_id=M1, dimension=D, verdict="pass", words="w")])
    result = import_ratings(env.export_dir, _write_ratings(env, ratings), state_root=env.state_root)
    assert result["status"] == "refused"
    assert any("invalid packet manifest" in p for p in result["problems"])


def test_b70_verdicts_stay_pass_or_fail_for_v2(tmp_path):
    env = _env(tmp_path)
    doc = _ratings(env, [Rating(item_id=M1, dimension=D, verdict="pass", words="w")]).model_dump(
        mode="json")
    doc["ratings"][0]["verdict"] = "unsure"
    path = env.export_dir.parent / "third-verdict.json"
    path.write_bytes(json.dumps(doc).encode())
    result = import_ratings(env.export_dir, path, state_root=env.state_root)
    assert result["status"] == "refused" and any("invalid ratings file" in p for p in result["problems"])
    assert _ledger_bytes(env) == b""


@pytest.mark.parametrize("mutate", [
    lambda d: d.update(entries=d["entries"][:-1]),                                   # omits an item
    lambda d: d.update(entries=d["entries"] + [dict(d["entries"][0], item_id="it_" + "ee" * 8)]),
    lambda d: d.update(entries=d["entries"] + [d["entries"][0]]),                    # duplicate
])
def test_a_v2_key_without_exactly_one_entry_per_item_is_refused_as_status_refuses_it(tmp_path, mutate):
    """Verifier probe 2c(b): import used to append against a key that review_status then called
    PacketUnbound ("one entry per item"); the two now agree."""
    env = _env(tmp_path)
    doc = env.key.model_dump(mode="json")
    mutate(doc)
    _key_file(env).write_bytes(json.dumps(doc).encode())
    ratings = _ratings(env, [Rating(item_id=M1, dimension=D, verdict="pass", words="w")])
    result = import_ratings(env.export_dir, _write_ratings(env, ratings), state_root=env.state_root)
    assert result["status"] == "refused"
    assert any("exactly one entry per item" in p for p in result["problems"]), result["problems"]
    assert _ledger_bytes(env) == b""
