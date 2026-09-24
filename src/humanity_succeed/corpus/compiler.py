"""Deterministic case compiler (BUILD_SPEC §5.3).

Outputs, in a NEW directory:
- ``subject_views/<episode_ref>.json``: the only model-readable tree.
- ``host/<case_id>/{world,evaluator,provenance}.json``: host-side only.
- ``train.jsonl`` / ``valid.jsonl``: approved preferred demonstrations only, one prefix row per
  target assistant turn (MLX masks only the final message; §5.3). Metadata lives in the sidecar
  ``*.rows.json`` so the JSONL stays a plain chat dataset.
- ``split_audit.json``, ``lint.json``, ``manifest.json``.

Blocking conditions return a ``blocked`` status and write nothing: strict-load/schema/semantic
errors, split lineage problems, and a preferred demonstration whose actual replay does not pass.
Rejected/counterexample trajectories never become SFT targets. No timestamps: identical input gives
byte-identical output.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .. import COMPILER_VERSION
from ..canonical import (
    StrictLoadError,
    canonical_bytes,
    load_document,
    make_new_dir,
    sha256_bytes,
    sha256_obj,
    write_new_file,
)
from ..contracts.case import CaseSource, review_status, semantic_problems, uses_local_extension
from ..contracts.schemas import implementation_case_schema, packet_schema, schema_errors
from ..corpus.lint import lint_case
from ..corpus.splits import audit_splits
from ..corpus.views import VisibleTurn, build_messages, four_views, subject_view

SFT_SPLITS = {"train": "train.jsonl", "dev": "valid.jsonl"}
TOKENIZER_IDENTITY = None  # no model selected; token/label audits are blocked, not guessed


def load_cases(path: Path) -> tuple[list[tuple[Path, CaseSource, dict[str, Any]]], list[dict]]:
    path = Path(path)
    files = sorted(
        [path] if path.is_file() else
        [p for p in path.rglob("*") if p.suffix in (".yaml", ".yml", ".json") and p.is_file()
         and "trajectories" not in p.parts]
    )
    loaded, errors = [], []
    for f in files:
        try:
            doc = load_document(f)
        except StrictLoadError as e:
            errors.append({"file": str(f), "stage": "strict_load", "error": str(e)})
            continue
        impl_errs = schema_errors(doc, implementation_case_schema())
        if impl_errs:
            errors.append({"file": str(f), "stage": "schema", "errors": impl_errs[:20]})
            continue
        try:
            case = CaseSource.model_validate(doc, strict=True)
        except Exception as e:  # noqa: BLE001 - reported, not raised
            errors.append({"file": str(f), "stage": "contract", "error": str(e)[:2000]})
            continue
        probs = semantic_problems(case)
        if probs:
            errors.append({"file": str(f), "stage": "semantic", "errors": probs})
            continue
        loaded.append((f, case, doc))
    return loaded, errors


def validate_path(path: Path) -> dict[str, Any]:
    loaded, errors = load_cases(path)
    cases = []
    for f, case, doc in loaded:
        packet_errs = schema_errors(doc, packet_schema("case.schema.json"))
        cases.append({
            "file": str(f),
            "case_id": case.case_id,
            "packet_schema": "valid" if not packet_errs else (
                "not_applicable_local_extension_b03" if uses_local_extension(case) else "invalid"
            ),
            "implementation_schema": "valid",
            "review_status": review_status(case, doc)["state"],
            "rights_status": case.provenance.rights_status,
        })
    return {"schema_id": "hs-validate-report/1",
            "status": "invalid" if errors else "valid", "cases": cases, "errors": errors}


def replay_demonstration(case: CaseSource, case_doc: dict[str, Any], demo_id: str):
    """Run a demonstration through the real engine. Returns (evaluation, visible turns)."""
    from ..evidence.store import EvidenceStore
    from ..providers.scripted import ScriptedProvider
    from ..runner.episode import run_episode
    from ..runner.scripted import evaluate_and_record, trajectory_from_demo

    traj = trajectory_from_demo(case, demo_id)
    store = EvidenceStore(Path(":memory:"), clock=lambda: "1970-01-01T00:00:00.000000Z")
    try:
        provider = ScriptedProvider(traj["raw_outputs"])
        res = run_episode(case, case_doc, provider, store, run_id="run_compile_replay")
        evaluation = evaluate_and_record(store, res.run_id, case)
        turns = _visible_turns_from_store(store, res.run_id)
    finally:
        store.close()
    return evaluation, turns


def _visible_turns_from_store(store, run_id: str) -> list[VisibleTurn]:
    """Reconstruct subject-visible turns from recorded provider inputs (not hand-invented)."""
    from ..canonical import strict_json_loads

    events = store.events(run_id)
    inputs = [e["payload"]["observation_sha256"] for e in events
              if e["event_type"] == "observation_delivered"]
    last_msgs = strict_json_loads(store.artifact(inputs[-1]))["messages"]
    raws = [e["payload"]["raw_sha256"] for e in events if e["event_type"] == "provider_response"]
    turns = []
    # messages: system, user, (assistant, tool)*; the final assistant output has no tool reply in
    # the last recorded input, so take the tool results that exist and the final raw separately.
    pairs = last_msgs[2:]
    for i in range(0, len(pairs), 2):
        turns.append(VisibleTurn(raw_output=pairs[i]["content"],
                                 tool_result=strict_json_loads(pairs[i + 1]["content"])))
    final_raw = store.artifact(raws[-1]).decode("utf-8")
    turns.append(VisibleTurn(raw_output=final_raw, tool_result={"status": "not_observed"}))
    return turns


def sft_rows(case: CaseSource, turns: list[VisibleTurn]) -> list[dict[str, Any]]:
    """One prefix example per target assistant turn; the final message is the only target."""
    view = subject_view(case)
    rows = []
    for k in range(len(turns)):
        msgs = build_messages(view, case.world.initial_tick, turns[:k])
        msgs.append({"role": "assistant", "content": turns[k].raw_output})
        rows.append({"messages": msgs})
    return rows


def compile_cases(path: Path, out_dir: Path, principles_text: str | None = None) -> dict[str, Any]:
    loaded, errors = load_cases(path)
    cases = [c for _, c, _ in loaded]
    audit = audit_splits(cases)
    lint = {c.case_id: lint_case(c, principles_text) for c in cases}
    blocked: list[dict[str, Any]] = list(errors)
    if audit["status"] != "ok":
        blocked.append({"stage": "split_audit", "problems": audit["problems"]})

    sft: dict[str, list[tuple[dict, dict]]] = {"train": [], "dev": []}
    eligibility = []
    for _, case, doc in loaded:
        rs = review_status(case, doc)
        reasons = []
        if case.split not in SFT_SPLITS:
            reasons.append(f"split {case.split} is not a training split")
        if rs["state"] != "human_reviewed_approved":
            reasons.append(f"review state {rs['state']}")
        if case.provenance.rights_status == "pending":
            reasons.append("rights pending")
        if lint[case.case_id]:
            reasons.append(f"{len(lint[case.case_id])} unreviewed lint flag(s)")
        demo_results = []
        for d in case.demonstrations:
            evaluation, turns = replay_demonstration(case, doc, d.demo_id)
            actual = evaluation["mechanical"]["verdict"]
            demo_results.append({"demo_id": d.demo_id, "training_role": d.training_role,
                                 "expected": d.expected_mechanical_outcome, "actual": actual})
            if actual != d.expected_mechanical_outcome:
                blocked.append({"stage": "demonstration_replay", "case_id": case.case_id,
                                "demo_id": d.demo_id, "expected": d.expected_mechanical_outcome,
                                "actual": actual,
                                "rule": "a trajectory's recorded expectation must match its "
                                        "actual replay; a failing trajectory is never an SFT "
                                        "target"})
                continue
            if d.training_role != "preferred" or reasons:
                continue
            for k, row in enumerate(sft_rows(case, turns)):
                sft[case.split].append((row, {
                    "case_id": case.case_id, "demo_id": d.demo_id, "target_turn": k,
                    "case_source_sha256": sha256_obj(doc),
                    "target": "final_assistant_message_only",
                }))
        eligibility.append({"case_id": case.case_id, "sft_eligible": not reasons,
                            "reasons": reasons, "demonstrations": demo_results})

    report: dict[str, Any] = {
        "schema_id": "hs-compile-report/1",
        "compiler_version": COMPILER_VERSION,
        "status": "blocked" if blocked else "compiled",
        "blocked": blocked,
        "split_audit": audit,
        "lint_flag_count": sum(len(v) for v in lint.values()),
        "training_eligibility": eligibility,
    }
    if blocked:
        return report

    out = make_new_dir(Path(out_dir))
    (out / "subject_views").mkdir()
    (out / "host").mkdir()
    outputs: dict[str, dict[str, Any]] = {}

    def emit(rel: str, body: bytes, role: str, **meta: Any) -> None:
        write_new_file(out / rel, body)
        outputs[rel] = {"sha256": sha256_bytes(body), "role": role, **meta}

    for _, case, doc in loaded:
        views = four_views(case, doc)
        src = sha256_obj(doc)
        emit(f"subject_views/{views['subject']['episode_ref']}.json",
             canonical_bytes(views["subject"]), "model_visible_subject_view",
             split=case.split, source_sha256=src)
        (out / "host" / case.case_id).mkdir()
        for name in ("world", "evaluator", "provenance"):
            emit(f"host/{case.case_id}/{name}.json", canonical_bytes(views[name]),
                 f"host_only_{name}_view", split=case.split, source_sha256=src)
    for split, fname in SFT_SPLITS.items():
        rows = sft[split]
        body = b"".join(canonical_bytes(r) + b"\n" for r, _ in rows)
        emit(fname, body, "sft_rows", split=split, rows=len(rows))
        emit(fname.replace(".jsonl", ".rows.json"), canonical_bytes([m for _, m in rows]),
             "sft_row_metadata", split=split)
    emit("split_audit.json", canonical_bytes(audit), "split_audit")
    emit("lint.json", canonical_bytes(lint), "leak_lint_flags")
    manifest = {
        "schema_id": "hs-compile-manifest/1",
        "compiler_version": COMPILER_VERSION,
        "tokenizer_identity": TOKENIZER_IDENTITY,
        "chat_template_identity": None,
        "token_audit": "blocked: no model/tokenizer selected; loss-bearing token counts unknown",
        "serialization": "hs-workroom-interface/1 messages (system, user, assistant, tool)",
        "sources": sorted(
            ({"case_id": c.case_id, "file": f.name, "sha256": sha256_obj(d), "split": c.split}
             for f, c, d in loaded), key=lambda x: x["case_id"]),
        "counts": {
            "source_cases": len(loaded),
            "source_preferred_trajectories_eligible": sum(
                1 for e in eligibility if e["sft_eligible"]
                for d in e["demonstrations"] if d["training_role"] == "preferred"),
            "compiled_rows": {s: len(v) for s, v in sft.items()},
            "loss_bearing_tokens": None,
            "optimizer_updates": None,
        },
        "outputs": outputs,
        "training_eligibility": eligibility,
    }
    write_new_file(out / "manifest.json", canonical_bytes(manifest))
    report["out_dir"] = str(out)
    report["manifest_sha256"] = sha256_obj(manifest)
    return report


def compile_many(paths: list[Path], out: Path, principles: str | None = None) -> dict[str, Any]:
    """Compile several source roots as one lineage universe (derivations may cross roots)."""
    import shutil
    import tempfile

    if len(paths) == 1:
        return compile_cases(paths[0], out, principles)
    with tempfile.TemporaryDirectory(prefix="hs-compile-") as td:
        stage = Path(td) / "sources"
        stage.mkdir()
        for i, p in enumerate(paths):
            dest = stage / f"{i:02d}"
            if Path(p).is_file():
                dest.mkdir()
                shutil.copy2(p, dest / Path(p).name)
            else:
                shutil.copytree(p, dest)
        return compile_cases(stage, out, principles)
