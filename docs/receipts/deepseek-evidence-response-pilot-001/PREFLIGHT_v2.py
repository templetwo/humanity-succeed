"""Read-only frozen-pilot checks. No provider construction, credential access or network."""

import argparse
import socket
from pathlib import Path

from humanity_succeed.canonical import load_document, sha256_bytes, sha256_obj
from humanity_succeed.contracts.case import review_source_sha256
from humanity_succeed.corpus.views import build_provider_input, subject_view
from humanity_succeed.evaluation.predicates import require_compatible
from humanity_succeed.hosted.contracts import HostedPlan
from humanity_succeed.hosted.provider import implementation_identity, make_plan
from humanity_succeed.hosted.transport import decode, encode
from humanity_succeed.runner.episode import code_identity
from humanity_succeed.runner.scripted import load_case

PACKET = Path(__file__).resolve().parent
ROOT = PACKET.parents[2]
ORDER = ["supported", "unsupported", "contradicted", "not_assessable"]


def denied(*args, **kwargs):
    raise RuntimeError("Preparation prohibits credential access and subject/network calls")


def deny_external_access():
    socket.socket.connect = denied
    socket.create_connection = denied
    import humanity_succeed.hosted.provider as provider

    provider.read_credential = denied
    provider.dispatch = denied


def verify_members(packet, freeze):
    for name, digest in freeze["files_sha256"].items():
        path = packet / name
        assert path.resolve().is_relative_to(packet.resolve()), "frozen path escape"
        assert not path.is_symlink(), "symlink in frozen packet"
        assert sha256_bytes(path.read_bytes()) == digest, f"freeze drift: {name}"


def verify_preservation(dependency):
    count = 0
    for item in dependency["preserved"]:
        directory = Path(item["root"])
        assert sha256_bytes((directory / "SHA256SUMS").read_bytes()) == item["inventory_sha256"]
        for name, digest in item["files"].items():
            assert sha256_bytes((directory / name).read_bytes()) == digest, "old evidence changed"
            count += 1
    return count


def check(expected_plan_sha256, *, packet=PACKET, fresh_locations=True):
    plan = load_document(packet / "PILOT_PLAN.v2.json")
    assert sha256_obj(plan) == expected_plan_sha256, "decision plan changed"
    assert plan["authorization"] is None and plan["human_approval"] is None
    assert plan["status"] == "frozen_preparation_pending_new_human_decision"
    freeze = load_document(packet / "FREEZE.v2.json")
    assert sha256_obj(freeze) == plan["freeze_sha256"], "freeze changed"
    verify_members(packet, freeze)
    dependency = load_document(packet / "DEPENDENCY.json")
    assert implementation_identity() == dependency["source"] == plan["source"]
    assert code_identity()["dirty"] is False, "implementation dirty"
    assert [row["evidence_status"] for row in plan["episodes"]] == ORDER
    assert len(plan["episodes"]) == 4
    assert plan["workload"]["logical_roots"] == 1
    assert plan["workload"]["inference_requests_ceiling"] == 8
    assert plan["workload"]["authenticated_metadata_requests"] == 0
    assert plan["workload"]["reserved_output_tokens_total"] == 32768
    assert plan["credential"]["read_during_preparation"] is False
    roots = set()
    for row in plan["episodes"]:
        case, doc = load_case(packet / row["case"])
        roots.add(case.root_scenario_id)
        assert case.split == "pilot" and case.measurement_mode == "after_supplied_evidence"
        assert case.reviews == [] and case.demonstrations == []
        assert case.evaluation.scoring_mode == "hybrid"
        assert case.evaluation.a1_evidence.findings[0].evidence_status == row["evidence_status"]
        assert sha256_obj(doc) == row["case_sha256"]
        assert review_source_sha256(doc) == row["review_source_sha256"]
        require_compatible(case, "hs-evaluator/0.3.0")
        hosted = HostedPlan.model_validate(load_document(packet / row["hosted_plan"]), strict=True)
        assert sha256_obj(hosted.model_dump(mode="json")) == row["hosted_plan_sha256"]
        assert hosted.limits.requests == 2 and hosted.settings.max_tokens == 4096
        assert hosted.limits.episode_seconds == 90 and hosted.limits.request_seconds == 45
        assert hosted.simulation is False and hosted.model == "deepseek-flash"
        rebuilt = make_plan(
            case,
            doc,
            model=hosted.model,
            allowed=hosted.allowed_returned_models,
            simulation=False,
            settings=hosted.settings,
            limits=hosted.limits,
        )
        assert rebuilt == hosted
        observation = build_provider_input(subject_view(case), case.world.initial_tick, [])
        body = encode(observation, hosted.model, hosted.settings)
        assert decode(body) == observation
        assert sha256_bytes(observation) == row["initial_observation_sha256"]
        assert sha256_bytes(body) == row["initial_request_sha256"]
        assert len(body) == row["initial_request_bytes"] <= hosted.limits.request_bytes
        assert (packet / row["observation"]).read_bytes() == observation
        assert (packet / row["request"]).read_bytes() == body
        if fresh_locations:
            for name in ("output_root", "ledger_root", "authorization_file"):
                assert not Path(row["locations"][name]).exists(), "single-use path already exists"
    assert len(roots) == 1
    review = load_document(packet / "REVIEW_PACKET.blank.v2.json")
    assert len(review["episodes"]) == 4
    for episode in review["episodes"]:
        case, doc = load_case(packet / episode["case"])
        assert episode["review_source_sha256"] == review_source_sha256(doc)
        for field in ("verdict", "rationale", "reviewer", "adjudication", "response_category"):
            assert episode[field] is None
        for cell in episode["grid_cells"]:
            assert cell["judgment"] is None and cell["selected"] is None
            assert cell["criterion_ref"] == "/evaluation/human_rubric/1"
            assert cell["criterion_sha256"] == sha256_obj(doc["evaluation"]["human_rubric"][1])
        for dimension in episode["dimensions"]:
            assert dimension["judgment"] is None
    return {
        "status": "prepared_not_authorized_not_executed",
        "plan_sha256": expected_plan_sha256,
        "freeze_sha256": plan["freeze_sha256"],
        "episodes": 4,
        "shared_roots": 1,
        "preserved_entries": verify_preservation(dependency),
        "source": implementation_identity(),
        "credential_accesses": 0,
        "authenticated_requests": 0,
        "inference_requests": 0,
        "human_reviews_recorded": 0,
    }


def main():
    from humanity_succeed.canonical import canonical_bytes

    parser = argparse.ArgumentParser()
    parser.add_argument("--plan-sha256", required=True)
    args = parser.parse_args()
    deny_external_access()
    print(canonical_bytes(check(args.plan_sha256)).decode())


if __name__ == "__main__":
    main()
