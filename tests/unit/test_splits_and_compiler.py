"""WP1: split isolation (A02), compiler determinism, SFT gates (A03), prefix rows, review gates."""

import copy
import hashlib
from pathlib import Path

import pytest
import yaml

from humanity_succeed.canonical import load_document, strict_json_loads
from humanity_succeed.contracts.case import CaseSource, review_source_sha256, review_status
from humanity_succeed.corpus.compiler import compile_cases, compile_many
from humanity_succeed.corpus.lint import extract_principles_text, lint_case
from humanity_succeed.corpus.splits import audit_splits

from ..conftest import DEV_CASES, EXAMPLES, REPO


def _write(dirpath: Path, name: str, doc: dict) -> Path:
    dirpath.mkdir(parents=True, exist_ok=True)
    p = dirpath / name
    p.write_text(yaml.safe_dump(doc, sort_keys=False))
    return p


def _cases(*paths):
    return [CaseSource.model_validate(load_document(p), strict=True) for p in paths]


def test_packet_goal_twins_share_one_split():
    rep = audit_splits(_cases(EXAMPLES / "feature-preserve.yaml",
                              EXAMPLES / "feature-standardize.yaml"))
    assert rep["status"] == "ok"
    assert len(rep["groups"]) == 1


def test_goal_reversal_in_another_split_blocks(tmp_path):
    """A02."""
    pres = load_document(EXAMPLES / "feature-preserve.yaml")
    std = load_document(EXAMPLES / "feature-standardize.yaml")
    std["split"] = "train"
    _write(tmp_path / "src", "p.yaml", pres)
    _write(tmp_path / "src", "s.yaml", std)
    rep = compile_cases(tmp_path / "src", tmp_path / "out")
    assert rep["status"] == "blocked"
    assert any(p["kind"] == "lineage_spans_splits" for p in rep["split_audit"]["problems"])
    assert not (tmp_path / "out").exists()


def test_shared_root_without_derivation_edge_still_one_lineage():
    a = CaseSource.model_validate(load_document(EXAMPLES / "feature-preserve.yaml"), strict=True)
    d = load_document(EXAMPLES / "feature-standardize.yaml")
    d["derivation_ids"] = []
    d["split"] = "pilot"
    rep = audit_splits([a, CaseSource.model_validate(d, strict=True)])
    assert rep["status"] == "blocked"


def test_unresolved_and_cross_root_derivations_block():
    d = load_document(EXAMPLES / "feature-standardize.yaml")
    rep = audit_splits(_cases_from([d]))
    assert any(p["kind"] == "unresolved_derivation" for p in rep["problems"])
    pres = load_document(EXAMPLES / "feature-preserve.yaml")
    d2 = copy.deepcopy(d)
    d2["root_scenario_id"] = "root-other"
    rep = audit_splits(_cases_from([pres, d2]))
    assert any(p["kind"] == "derivation_crosses_roots" for p in rep["problems"])


def test_near_duplicate_across_lineages_flagged():
    a = load_document(EXAMPLES / "correction.yaml")
    b = copy.deepcopy(a)
    b.update(case_id="x-2", root_scenario_id="root-x-2")
    b["subject"]["task"] = a["subject"]["task"].upper()
    rep = audit_splits(_cases_from([a, b]))
    assert any(p["kind"] == "near_duplicate_across_lineages" for p in rep["problems"])


def _cases_from(docs):
    return [CaseSource.model_validate(d, strict=True) for d in docs]


def _tree_digest(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


def test_compile_is_deterministic_and_separates_views(tmp_path):
    srcs = [EXAMPLES, DEV_CASES]
    r1 = compile_many(srcs, tmp_path / "a")
    r2 = compile_many(srcs, tmp_path / "b")
    assert r1["status"] == r2["status"] == "compiled"
    assert _tree_digest(tmp_path / "a") == _tree_digest(tmp_path / "b")
    subj = list((tmp_path / "a" / "subject_views").iterdir())
    assert len(subj) == 5
    for f in subj:
        v = strict_json_loads(f.read_bytes())
        assert set(v) == {"schema_id", "episode_ref", "task", "visible_resource_ids",
                          "visible_actor_ids", "allowed_tools"}
        assert "commissioning" not in f.name and "F0" not in f.read_text()
    man = strict_json_loads((tmp_path / "a" / "manifest.json").read_bytes())
    assert man["counts"]["compiled_rows"] == {"train": 0, "dev": 0}
    assert man["tokenizer_identity"] is None
    assert all(not e["sft_eligible"] for e in man["training_eligibility"])
    assert (tmp_path / "a" / "train.jsonl").read_bytes() == b""


def test_compile_refuses_existing_output(tmp_path):
    (tmp_path / "out").mkdir()
    with pytest.raises(FileExistsError):
        compile_cases(EXAMPLES, tmp_path / "out")


def _approved_train_case(tmp_path: Path, doc: dict, reviewer_kind="human", tamper=False) -> Path:
    """Test double only: a synthetic review record created inside a temporary directory to exercise
    the compiler gate. It is never written to the repository and is not a human review."""
    doc = copy.deepcopy(doc)
    doc["split"] = "train"
    doc["provenance"]["rights_status"] = "approved_for_local_use"
    doc["provenance"]["rights_receipt"] = "synthetic-test-fixture"
    doc["evaluation"]["human_rubric"] = []
    doc["evaluation"]["scope_limitations"] = []
    doc["evaluation"]["scoring_mode"] = "mechanical"
    src = review_source_sha256(doc)
    doc["reviews"] = [{
        "reviewer_ref": "synthetic-test-fixture-not-a-person", "reviewer_kind": reviewer_kind,
        "role": "reviewer", "source_sha256": "0" * 64 if tamper else src,
        "timestamp_utc": "2026-09-24T00:00:00Z", "verdict": "approve", "reason": "test double"}]
    return _write(tmp_path / "src", "c.yaml", doc)


def test_prefix_rows_one_per_assistant_turn(tmp_path, correction_doc):
    """Golden two-or-more-action correction: n actions -> n rows; only the final message is the
    target; rows are prefix-consistent; tool observations come from the real engine."""
    _approved_train_case(tmp_path, correction_doc)
    rep = compile_cases(tmp_path / "src", tmp_path / "out")
    assert rep["status"] == "compiled", rep["blocked"]
    rows = [strict_json_loads(x) for x in (tmp_path / "out" / "train.jsonl").read_bytes()
            .splitlines()]
    meta = strict_json_loads((tmp_path / "out" / "train.rows.json").read_bytes())
    assert len(rows) == 3 == len(meta)  # write, notify, finish of the preferred demo only
    assert all(m["demo_id"] == "correction_effect" for m in meta)
    for k, row in enumerate(rows):
        msgs = row["messages"]
        assert msgs[-1]["role"] == "assistant"
        assert sum(m["role"] == "assistant" for m in msgs) == k + 1
        assert meta[k]["target"] == "final_assistant_message_only"
        if k:
            assert msgs[:len(rows[k - 1]["messages"])] == rows[k - 1]["messages"]
    tool = strict_json_loads(rows[1]["messages"][-2]["content"])
    assert tool == {"status": "ok", "resource_id": "r_result", "revision": 2}
    body = (tmp_path / "out" / "train.jsonl").read_text()
    assert "I corrected the total and notified Avery." not in body  # counterexample excluded


def test_failing_trajectory_marked_preferred_blocks_compile(tmp_path, correction_doc):
    """A03: a rejected completion cannot become an SFT target."""
    bad = correction_doc["demonstrations"][1]
    bad["training_role"] = "preferred"
    bad["expected_mechanical_outcome"] = "pass"
    _approved_train_case(tmp_path, correction_doc)
    rep = compile_cases(tmp_path / "src", tmp_path / "out")
    assert rep["status"] == "blocked"
    assert any(b.get("stage") == "demonstration_replay" and b["actual"] == "fail"
               for b in rep["blocked"])
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("kind,tamper,reason", [
    ("model", False, "review state draft"),
    ("human", True, "review state draft"),
])
def test_model_or_stale_reviews_do_not_unlock_sft(tmp_path, correction_doc, kind, tamper, reason):
    _approved_train_case(tmp_path, correction_doc, reviewer_kind=kind, tamper=tamper)
    rep = compile_cases(tmp_path / "src", tmp_path / "out")
    [elig] = rep["training_eligibility"]
    assert not elig["sft_eligible"] and reason in elig["reasons"]
    assert (tmp_path / "out" / "train.jsonl").read_bytes() == b""


def test_review_status_is_derived_not_declared(correction_doc):
    case = CaseSource.model_validate(correction_doc, strict=True)
    st = review_status(case, correction_doc)
    assert st["state"] == "draft" and st["model_reviews_counted_as_human"] == 0


def test_lint_flags_hidden_labels_and_overlap(correction_doc):
    correction_doc["subject"]["task"] += " (case commissioning-correction-001, split pilot)"
    correction_doc["subject"]["task"] += " must accurately describe the corrected total"
    flags = lint_case(CaseSource.model_validate(correction_doc, strict=True))
    kinds = {f["kind"] for f in flags}
    assert "hidden_label_in_visible_text:case_id" in kinds
    assert "hidden_label_in_visible_text:split_name" in kinds
    assert "phrase_overlap_4gram" in kinds
    assert all(f["disposition"] == "unreviewed" for f in flags)


def test_principles_draft_extracts_only_model_visible_text():
    text = extract_principles_text((REPO / "configs" / "principles.draft.md").read_text())
    assert "Status:" not in text and text.startswith("Help people")
