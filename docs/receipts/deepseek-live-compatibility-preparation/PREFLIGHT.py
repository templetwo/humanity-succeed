"""Read-only checkpoint checks. Never construct a provider or read a credential."""

import argparse
import socket
import time
from pathlib import Path

from humanity_succeed.canonical import canonical_bytes, load_document, sha256_bytes, sha256_obj
from humanity_succeed.corpus.views import build_provider_input, subject_view
from humanity_succeed.evaluation.predicates import require_compatible
from humanity_succeed.hosted.contracts import Authorization, HostedPlan
from humanity_succeed.hosted.provider import implementation_identity, make_plan
from humanity_succeed.hosted.transport import decode, encode
from humanity_succeed.runner.episode import code_identity
from humanity_succeed.runner.scripted import load_case


def forbidden(*args, **kwargs):
    raise RuntimeError("Preparation cannot read credentials or contact a provider")


def main():
    socket.socket.connect = forbidden
    socket.create_connection = forbidden
    import humanity_succeed.hosted.provider as provider_module

    provider_module.read_credential = forbidden
    provider_module.dispatch = forbidden
    parser = argparse.ArgumentParser()
    parser.add_argument("--decision-sha256", required=True)
    parser.add_argument("--authorization", type=Path)
    args = parser.parse_args()
    packet = Path(__file__).resolve().parent
    root = packet.parents[2]
    decision = load_document(packet / "LIVE_PROPOSAL.v2.json")
    assert sha256_obj(decision) == args.decision_sha256, "decision plan changed"
    for name, digest in decision["preparation_files_sha256"].items():
        assert sha256_bytes((packet / name).read_bytes()) == digest, "preparation artifact changed"
    plan = HostedPlan.model_validate(load_document(packet / "HOSTED_PLAN.json"), strict=True)
    assert sha256_obj(plan.model_dump(mode="json")) == decision["hosted_plan_sha256"]
    assert plan.model_dump(mode="json") == decision["hosted_plan"]
    assert implementation_identity() == decision["source"], "source/import identity changed"
    assert code_identity()["dirty"] is False, "tracked implementation changed"
    case, doc = load_case(root / decision["case"])
    assert sha256_obj(doc) == plan.case_sha256, "task changed"
    assert sha256_obj(subject_view(case).model_dump(mode="json")) == plan.subject_sha256
    require_compatible(case, plan.evaluator)
    rebuilt = make_plan(
        case, doc, model=plan.model, allowed=plan.allowed_returned_models, simulation=False,
        settings=plan.settings, limits=plan.limits,
    )
    assert rebuilt == plan, "configuration changed"
    observation = build_provider_input(subject_view(case), case.world.initial_tick, [])
    body = encode(observation, plan.model, plan.settings)
    assert decode(body) == observation
    assert sha256_bytes(observation) == decision["canonical_initial_observation_sha256"]
    assert sha256_bytes(body) == decision["initial_outgoing_request_sha256"]
    assert len(body) <= plan.limits.request_bytes
    assert decision["authenticated_metadata_requests"] == 0
    assert decision["credential"]["path_confirmed_by_anthony"] is True
    # Do not stat, open, or otherwise inspect the designated credential path.
    for name in ("output_root", "ledger_root"):
        assert not Path(decision["locations"][name]).exists(), "single-use location already exists"
    authorization_checked = False
    if args.authorization is not None:
        authorization = Authorization.model_validate(load_document(args.authorization), strict=True)
        assert authorization.plan_sha256 == decision["hosted_plan_sha256"]
        assert authorization.ledger_root == decision["locations"]["ledger_root"]
        assert authorization.simulation is False
        assert authorization.issued_at <= int(time.time()) < authorization.expires_at
        assert authorization.expires_at - authorization.issued_at <= 300
        authorization_checked = True
    print(canonical_bytes({
        "status": "identities_match_authorization_still_requires_explicit_human_decision",
        "decision_plan_sha256": args.decision_sha256,
        "hosted_plan_sha256": decision["hosted_plan_sha256"],
        "source": implementation_identity(),
        "task_identity_checked_before_any_credential_access": True,
        "authorization_contract_checked": authorization_checked,
        "credential_accesses": 0, "authenticated_requests": 0, "inference_requests": 0,
        "whole_run_deadline_automatically_enforced": False,
        "dollar_spending_limit_enforced": False,
    }).decode())


if __name__ == "__main__":
    main()
