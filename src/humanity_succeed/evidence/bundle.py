"""Evidence bundle export and read-only verification (BUILD_SPEC §7.1).

Verification levels are reported separately and never merged:
- ``internal``: hash chain, payload contracts, manifest binding, artifact and revision correspondence,
  view recomputation and evaluation binding all check out.
- ``anchor``: ``external_anchor_absent`` unless an anchor file is supplied; then
  ``verified_against_anchor``, ``partial`` (anchor covers a prefix only) or ``failed``.
A locally consistent chain is never called historically authentic.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..canonical import (
    StrictLoadError,
    canonical_bytes,
    make_new_dir,
    sha256_bytes,
    sha256_obj,
    strict_json_loads,
    write_new_file,
)
from ..contracts.case import CaseSource
from ..contracts.events import (
    GENESIS_PREV_HASH,
    EventEnvelope,
    actor_permitted,
    validate_payload,
)
from ..corpus.views import four_views
from .store import EvidenceStore, compute_event_hash

BUNDLE_SCHEMA = "hs-evidence-bundle/1"
MAX_BUNDLE_FILE_BYTES = 64 * 1024 * 1024
# The only names a bundle may list: fixed top-level files and content-addressed artifacts.
_ALLOWED_NAME = re.compile(
    r"(?:manifest\.json|events\.jsonl|revisions\.json|case_source\.json|trajectory\.json"
    r"|evaluation\.json|artifacts/[0-9a-f]{64})", re.ASCII)


def export_bundle(
    store: EvidenceStore,
    run_id: str,
    case_doc: dict[str, Any],
    evaluation: dict[str, Any] | None,
    out_dir: Path,
    trajectory: dict[str, Any] | None = None,
) -> Path:
    out = make_new_dir(Path(out_dir))
    (out / "artifacts").mkdir()
    files: dict[str, bytes] = {}
    manifest, _ = store.manifest(run_id)
    files["manifest.json"] = canonical_bytes(manifest)
    events = store.events(run_id)
    files["events.jsonl"] = b"".join(canonical_bytes(e) + b"\n" for e in events)
    files["revisions.json"] = canonical_bytes(store.revisions(run_id))
    files["case_source.json"] = canonical_bytes(case_doc)
    if trajectory is not None:
        files["trajectory.json"] = canonical_bytes(trajectory)
    if evaluation is not None:
        files["evaluation.json"] = canonical_bytes(evaluation)
    wanted = _referenced_artifacts(events) | {
        sha256_obj(v) for v in four_views(_case(case_doc), case_doc).values()
    }
    for sha, _kind, body in store.artifacts():
        if sha in wanted:
            files[f"artifacts/{sha}"] = body
    index = {
        "schema_id": BUNDLE_SCHEMA,
        "run_id": run_id,
        "evidence_class": manifest["evidence_class"],
        "files": {k: sha256_bytes(v) for k, v in sorted(files.items())},
        "note": "A locally consistent hash chain is not an externally anchored record.",
    }
    for name, body in files.items():
        write_new_file(out / name, body)
    write_new_file(out / "bundle.json", canonical_bytes(index))
    sums = "".join(f"{sha256_bytes(b)}  {n}\n" for n, b in sorted(
        {**files, "bundle.json": canonical_bytes(index)}.items()))
    write_new_file(out / "SHA256SUMS", sums.encode())
    return out


def _case(doc: dict[str, Any]) -> CaseSource:
    return CaseSource.model_validate(doc, strict=True)


def _referenced_artifacts(events: list[dict[str, Any]]) -> set[str]:
    refs = set()
    for e in events:
        p = e["payload"]
        if e["event_type"] == "observation_delivered":
            refs.add(p["observation_sha256"])
        elif e["event_type"] == "provider_response":
            refs.add(p["raw_sha256"])
    return refs


def anchor_for(bundle: Path) -> dict[str, Any]:
    events = _read_events(bundle / "events.jsonl")
    head = events[-1]
    return {"schema_id": "hs-anchor/1", "run_id": head["run_id"],
            "head_sequence": head["sequence"], "head_event_hash": head["event_hash"]}


def _read_events(path: Path) -> list[dict[str, Any]]:
    data = path.read_bytes()
    if data and not data.endswith(b"\n"):
        raise StrictLoadError("jsonl_newline", "events.jsonl must end with a newline")
    return [strict_json_loads(line) for line in data.split(b"\n") if line]


REQUIREMENTS = ("bound_evaluation",)
# Fields replay and the static report read from a recorded evaluation (hs-evaluation/1).
_EVALUATION_KEYS = ("schema_id", "evaluator_version", "evidence_class", "execution",
                    "scoring_mode", "mechanical", "conduct_outcome", "semantic_review",
                    "containment", "rhetoric", "scope_limitations", "claim_boundary")


def _declared_view_artifacts(events: list[dict[str, Any]]) -> dict[str, str]:
    """The four view hashes the run_started event binds. They come from the hash chain, so a
    rebuilt (untrusted) index cannot remove one from what verification expects."""
    if not events or events[0]["event_type"] != "run_started":
        return {}
    p = events[0]["payload"]
    return {k: p[f"{k}_view_sha256"] for k in ("subject", "world", "evaluator", "provenance")}


def _evaluation_shape_problem(doc: Any, binding: dict[str, Any] | None) -> str:
    if not isinstance(doc, dict):
        return "evaluation.json is not an object"
    missing = [k for k in _EVALUATION_KEYS if k not in doc]
    if missing:
        return "missing " + ", ".join(missing)
    if doc["schema_id"] != "hs-evaluation/1":
        return f"unknown evaluation schema {doc['schema_id']!r}"
    mech = doc["mechanical"]
    if not isinstance(mech, dict) or not {"verdict", "reason", "pass_if", "fail_if"} <= set(mech):
        return "mechanical block is incomplete"
    if binding is not None and doc["evaluator_version"] != binding["payload"]["evaluator_version"]:
        return "evaluator_version differs from the evaluation_recorded event"
    return ""


def _execution_state(events: list[dict[str, Any]]) -> dict[str, Any]:
    from ..runner.episode import derive_status

    if not events:
        return {"execution_status": "unknown", "terminal_status": None}
    return derive_status(events)


def verify_bundle(bundle: Path, anchor: dict[str, Any] | None = None,
                  require: tuple[str, ...] = ()) -> dict[str, Any]:
    """Read-only. Returns a report; never modifies the bundle and never raises on bundle content.

    ``require`` names what a caller's purpose needs beyond internal consistency. Only
    ``bound_evaluation`` exists: a complete evaluation file bound to the hash chain. A requirement
    never changes ``internal``; it is reported separately under ``requirements``.
    """
    unknown = [r for r in require if r not in REQUIREMENTS]
    if unknown:
        raise ValueError(f"unknown verification requirement(s): {', '.join(unknown)}")
    bundle = Path(bundle)
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> bool:
        checks.append({"check": name, "passed": bool(ok), "detail": detail})
        return bool(ok)

    def early() -> dict[str, Any]:
        return _report(checks, None, anchor, None, None, {"state": "not_checked"}, require)

    # 0. layout safety before reading any content: no symlinks anywhere, only expected names,
    #    nothing that resolves outside the bundle, bounded sizes.
    if bundle.is_symlink() or not bundle.is_dir():
        check("bundle_is_plain_directory", False, "bundle path is a symlink or not a directory")
        return early()
    links = [str(p.relative_to(bundle)) for p in bundle.rglob("*") if p.is_symlink()]
    if not check("no_symlinks", not links, ", ".join(sorted(links))):
        return early()
    hard = [str(p.relative_to(bundle)) for p in bundle.rglob("*")
            if p.is_file() and p.stat(follow_symlinks=False).st_nlink > 1]
    if not check("no_hard_links", not hard, ", ".join(sorted(hard))):
        return early()
    big = [str(p.relative_to(bundle)) for p in bundle.rglob("*")
           if p.is_file() and p.stat().st_size > MAX_BUNDLE_FILE_BYTES]
    if not check("file_sizes_bounded", not big, ", ".join(big)):
        return early()
    try:
        index = strict_json_loads((bundle / "bundle.json").read_bytes())
    except (OSError, StrictLoadError) as e:
        check("bundle_index_readable", False, str(e))
        return early()
    files = index.get("files") if isinstance(index, dict) else None
    bad_names = sorted(n for n in (files or {}) if not _ALLOWED_NAME.fullmatch(n)) if isinstance(
        files, dict) else ["<files is not an object>"]
    if not check("file_names_well_formed", not bad_names, ", ".join(bad_names)):
        return early()

    # 1. file inventory and hashes
    listed = dict(files)
    present = {
        str(p.relative_to(bundle)) for p in bundle.rglob("*") if p.is_file()
    } - {"bundle.json", "SHA256SUMS"}
    check("no_unlisted_files", present <= set(listed), ", ".join(sorted(present - set(listed))))
    check("no_missing_files", set(listed) <= present, ", ".join(sorted(set(listed) - present)))
    bad = [n for n, h in listed.items() if (bundle / n).is_file()
           and sha256_bytes((bundle / n).read_bytes()) != h]
    check("file_hashes_match_index", not bad, ", ".join(bad))
    sums_ok, sums_detail = False, ""
    if (bundle / "SHA256SUMS").is_file():
        try:
            lines = (bundle / "SHA256SUMS").read_bytes().decode("utf-8").splitlines()
        except UnicodeDecodeError as e:
            lines, sums_detail = None, f"not UTF-8: {e.reason}"
        if lines is not None:
            want = {ln.split("  ", 1)[1]: ln.split("  ", 1)[0] for ln in lines if "  " in ln}
            # Names come from an untrusted file: compare as a set BEFORE touching the filesystem,
            # so only names already validated through bundle.json are ever opened.
            sums_ok = set(want) == set(listed) | {"bundle.json"} and all(
                sha256_bytes((bundle / n).read_bytes()) == h for n, h in want.items()
            )
    check("sha256sums_consistent", sums_ok, sums_detail)

    # 2. event chain and contracts
    try:
        events = _read_events(bundle / "events.jsonl")
    except (OSError, StrictLoadError) as e:
        check("events_readable", False, str(e))
        return _report(checks, index, anchor, None, None, {"state": "not_checked"}, require)
    chain_ok, detail = True, ""
    prev = GENESIS_PREV_HASH
    for i, e in enumerate(events):
        try:
            EventEnvelope.model_validate(e, strict=True)
            validate_payload(e["event_type"], e["payload"])
        except Exception as ex:  # noqa: BLE001 - report, never raise
            chain_ok, detail = False, f"seq {i}: contract: {ex.__class__.__name__}"
            break
        body = {k: v for k, v in e.items() if k != "event_hash"}
        if e["sequence"] != i:
            chain_ok, detail = False, f"sequence gap at index {i}"
            break
        if e["run_id"] != index.get("run_id"):
            chain_ok, detail = False, f"seq {i}: foreign run_id"
            break
        if e["prev_hash"] != prev:
            chain_ok, detail = False, f"seq {i}: prev_hash mismatch"
            break
        if compute_event_hash(body) != e["event_hash"]:
            chain_ok, detail = False, f"seq {i}: event_hash mismatch"
            break
        prev = e["event_hash"]
    check("event_chain_consistent", chain_ok and bool(events), detail)
    # Later checks read only the well-formed prefix: an event that fails its contract is never
    # indexed into, so malformed evidence becomes a failed check, not an exception.
    wf = _well_formed_prefix(events)
    # 2b. who may emit what (KIMI-05): the same EVENT_ACTORS contract the store applies on write.
    wrong_actor = [f"seq {e['sequence']}: {e['event_type']} by {e['actor_kind']}"
                   for e in wf if not actor_permitted(e["event_type"], e["actor_kind"])]
    unchecked = "" if len(wf) == len(events) else (
        f"; {len(events) - len(wf)} malformed event(s) not checked (see event_chain_consistent)")
    check("event_actors_authorized", not wrong_actor, "; ".join(wrong_actor) + unchecked)

    # 3. manifest binding
    try:
        manifest = strict_json_loads((bundle / "manifest.json").read_bytes())
        m_ok = bool(wf) and wf[0]["event_type"] == "run_started" and (
            wf[0]["payload"]["manifest_sha256"] == sha256_obj(manifest)
        )
    except (OSError, StrictLoadError, KeyError):
        manifest, m_ok = None, False
    check("manifest_bound_to_first_event", m_ok)

    # 4. artifacts (KIMI-03). Two dimensions: every artifact file holds the bytes its name
    #    claims, and every artifact the record requires (event references and the four views
    #    bound by run_started) is present. Nothing else may sit under artifacts/.
    refs = _referenced_artifacts(wf)
    views = _declared_view_artifacts(wf)
    on_disk = sorted(n.split("/", 1)[1] for n in present & set(listed)
                     if n.startswith("artifacts/"))
    missing = sorted(r for r in refs if r not in on_disk)
    check("referenced_artifacts_present", not missing, ", ".join(missing))
    missing_views = sorted(k for k, h in views.items() if h not in on_disk)
    check("declared_view_artifacts_present", bool(views) and not missing_views,
          ", ".join(f"view:{k}" for k in missing_views) or ("" if views else "no run_started"))
    corrupt = [n for n in on_disk if sha256_bytes((bundle / "artifacts" / n).read_bytes()) != n]
    check("artifact_content_addresses_match", not corrupt, ", ".join(corrupt))
    extra = sorted(set(on_disk) - refs - set(views.values()))
    check("no_unaccounted_artifacts", not extra, ", ".join(extra))

    # 5. case source, views
    case = None
    try:
        case_doc = strict_json_loads((bundle / "case_source.json").read_bytes())
        case = _case(case_doc)
        vs = {k: sha256_obj(v) for k, v in four_views(case, case_doc).items()}
        rs = wf[0]["payload"] if wf else {}
        v_ok = (
            manifest is not None
            and manifest["source"]["case_source_sha256"] == sha256_obj(case_doc)
            and manifest["source"]["view_sha256"] == vs
            and rs.get("subject_view_sha256") == vs["subject"]
            and rs.get("world_view_sha256") == vs["world"]
            and rs.get("evaluator_view_sha256") == vs["evaluator"]
            and rs.get("provenance_view_sha256") == vs["provenance"]
        )
    except Exception:  # noqa: BLE001
        v_ok = False
    check("case_and_views_bound", v_ok)

    # 6. revision history corresponds to resource_revised events
    rev_ok, rdetail = True, ""
    try:
        revisions = strict_json_loads((bundle / "revisions.json").read_bytes())
        revised = [e for e in wf if e["event_type"] == "resource_revised"]
        by_seq = {e["sequence"]: e for e in wf}
        bound = [r for r in revisions if r["event_sequence"] is not None]
        if len(bound) != len(revised):
            rev_ok, rdetail = False, "revision rows and resource_revised events differ in count"
        for r in revisions:
            if sha256_obj(r["value"]) != r["value_sha256"]:
                rev_ok, rdetail = False, f"{r['resource_id']}@{r['revision']}: value hash"
            if r["event_sequence"] is None:
                if case is None or case.world.resources.get(r["resource_id"]) is None or (
                    sha256_obj(case.world.resources[r["resource_id"]].value) != r["value_sha256"]
                ):
                    rev_ok, rdetail = False, f"{r['resource_id']}: initial revision not in world"
                continue
            ev = by_seq.get(r["event_sequence"])
            if ev is None or ev["event_type"] != "resource_revised" or (
                ev["payload"]["new_value_sha256"] != r["value_sha256"]
                or ev["payload"]["new_revision"] != r["revision"]
                or ev["payload"]["resource_id"] != r["resource_id"]
            ):
                rev_ok, rdetail = False, f"{r['resource_id']}@{r['revision']}: unbound"
    except (OSError, StrictLoadError, KeyError, TypeError, AttributeError) as e:
        rev_ok, rdetail = False, str(e)
    check("revisions_correspond_to_events", rev_ok, rdetail)

    # 7. evaluation (KIMI-04, KIMI-06). Four separate states: a legitimately absent evaluation, a
    #    present and bound one, a bound event whose file is missing, and unreadable or malformed
    #    evidence. Only the last two are corruption; absence is reported, not failed.
    ev_events = [e for e in wf if e["event_type"] == "evaluation_recorded"]
    binding = ev_events[-1] if ev_events else None
    evaluation: dict[str, Any] = {"state": "absent", "file_present": False,
                                  "binding_events": len(ev_events), "evaluator_version": None}
    if (bundle / "evaluation.json").is_file():
        evaluation["file_present"] = True
        try:
            ev_doc = strict_json_loads((bundle / "evaluation.json").read_bytes())
        except (OSError, StrictLoadError) as e:
            check("evaluation_readable", False, str(e))
            evaluation["state"] = "unreadable"
        else:
            check("evaluation_readable", True)
            shape = _evaluation_shape_problem(ev_doc, binding)
            check("evaluation_well_formed", not shape, shape)
            bound = binding is not None and (
                binding["payload"]["evaluation_sha256"] == sha256_obj(ev_doc))
            check("evaluation_bound_to_chain", bound,
                  "" if bound else ("no evaluation_recorded event" if binding is None
                                    else "hash differs from the evaluation_recorded event"))
            if not bound:
                evaluation["state"] = ("file_without_binding_event" if binding is None
                                       else "unbound")
            else:
                evaluation["state"] = "malformed" if shape else "bound"
                evaluation["evaluator_version"] = ev_doc.get("evaluator_version")
    else:
        check("evaluation_bound_to_chain", binding is None,
              "evaluation.json absent" if binding is None
              else "an evaluation_recorded event exists but evaluation.json is missing")
        evaluation["state"] = "absent" if binding is None else "binding_event_without_file"

    return _report(checks, index, anchor, wf, _execution_state(wf), evaluation, require)


def _well_formed_prefix(events: list[Any]) -> list[dict[str, Any]]:
    out = []
    for e in events:
        try:
            EventEnvelope.model_validate(e, strict=True)
            validate_payload(e["event_type"], e["payload"])
        except Exception:  # noqa: BLE001
            break
        out.append(e)
    return out


def _report(checks, index, anchor, events, execution, evaluation, require) -> dict[str, Any]:
    internal = all(c["passed"] for c in checks) and bool(checks)
    if anchor is None:
        anchor_status = "external_anchor_absent"
    elif not events:
        anchor_status = "failed"
    else:
        a_seq, a_hash = anchor.get("head_sequence"), anchor.get("head_event_hash")
        if anchor.get("run_id") != (index or {}).get("run_id"):
            anchor_status = "failed"
        elif not isinstance(a_seq, int) or a_seq >= len(events) or a_seq < 0:
            anchor_status = "failed"
        elif events[a_seq]["event_hash"] != a_hash:
            anchor_status = "failed"
        elif a_seq == len(events) - 1:
            anchor_status = "verified_against_anchor"
        else:
            anchor_status = "partial"
    execution = execution or {"execution_status": "unknown", "terminal_status": None}
    limitations = []
    if evaluation["state"] == "absent":
        limitations.append("no evaluation is recorded in this bundle; exit 0 and "
                           "internal=consistent say nothing about a behavioral result")
    if execution["execution_status"] != "completed":
        limitations.append(f"the recorded run did not complete "
                           f"(execution_status={execution['execution_status']})")
    if anchor is None:
        limitations.append("no external anchor was supplied: a fully rewritten history can "
                           "still be internally consistent")
    requirements = {}
    if "bound_evaluation" in require:
        met = evaluation["state"] == "bound"
        requirements["bound_evaluation"] = {
            "met": met,
            "detail": "" if met else f"evaluation state is {evaluation['state']!r}",
        }
    return {
        "schema_id": "hs-verify-report/2",
        "run_id": (index or {}).get("run_id"),
        "internal": "consistent" if internal else "failed",
        "anchor": anchor_status,
        "execution": execution,
        "evaluation": evaluation,
        "requirements": requirements,
        "limitations": limitations,
        "checks": checks,
        "note": (
            "internal=consistent means the bundle agrees with itself. Without a retained external "
            "anchor it does not establish that the history was never rewritten. Integrity, "
            "execution state, evaluation presence and anchor coverage are separate fields."
        ),
    }
