"""Static hosted evidence checks. This module never imports or invokes a network client."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from ..canonical import sha256_obj, strict_json_loads
from .contracts import HostedIdentity, RequestRecord, ResponseRecord
from .transport import decode, encode, unpack


def validate_hosted_bundle(bundle: Path, manifest: dict, events: list[dict]) -> str:
    try:
        identity = HostedIdentity.model_validate(manifest["provider"]["hosted"], strict=True)
        plan = identity.plan
        classification = "scripted_instrument" if plan.simulation else "model_observation"
        if (
            manifest["evidence_class"] != classification
            or events[0]["payload"]["evidence_class"] != classification
            or manifest["versions"]["evaluator"] != plan.evaluator
            or manifest["source"]["case_source_sha256"] != plan.case_sha256
            or manifest["source"]["view_sha256"]["subject"] != plan.subject_sha256
            or manifest["provider"]["kind"] != "deepseek"
            or manifest["limits"]
            != {"max_provider_calls": plan.limits.requests, "max_output_bytes": plan.limits.action_bytes}
        ):
            return "manifest/plan/classification mismatch"
        artifacts = bundle / "artifacts"
        requests: dict[int, RequestRecord] = {}
        for event in events:
            p = event["payload"]
            if event["event_type"] == "provider_requested":
                record = RequestRecord.model_validate(p["hosted"], strict=True)
                if (
                    record.attempt != len(requests) + 1
                    or record.attempt > plan.limits.requests
                    or p["call_index"] in requests
                    or record.canonical_input_sha256 != p["input_sha256"]
                    or record.authorization_sha256 != identity.authorization_sha256
                    or record.reserved_output_tokens != plan.settings.max_tokens
                ):
                    return "request authorization/accounting mismatch"
                observation = (artifacts / p["input_sha256"]).read_bytes()
                outgoing = (artifacts / record.request_sha256).read_bytes()
                if (
                    decode(outgoing) != observation
                    or encode(observation, plan.model, plan.settings) != outgoing
                    or len(outgoing) > plan.limits.request_bytes
                ):
                    return "request encoding mismatch"
                requests[p["call_index"]] = record
            if event["event_type"] == "provider_response":
                if p["call_index"] not in requests:
                    return "response without request"
                response_record = ResponseRecord.model_validate(p["hosted"], strict=True)
                data = (artifacts / response_record.response_sha256).read_bytes()
                raw = (artifacts / p["raw_sha256"]).read_bytes().decode()
                content, metadata = unpack(
                    data, response_record.elapsed_ms, plan.allowed_returned_models, plan.limits.action_bytes
                )
                if (
                    metadata != response_record.model_dump(mode="json")
                    or content != raw
                    or len(data) > plan.limits.response_bytes
                ):
                    return "response binding mismatch"
            if event["event_type"] == "provider_error" and "hosted" not in p:
                return "hosted error metadata absent"
        # Manifest code records the resolved execution source, rather than a bare provider label.
        if manifest["code"]["commit"] != plan.source_commit:
            return "source commit differs from plan"
        case_doc = strict_json_loads((bundle / "case_source.json").read_bytes())
        if sha256_obj(case_doc) != plan.case_sha256:
            return "case hash mismatch"
        return ""
    except (KeyError, ValueError, TypeError, OSError, ValidationError, IndexError):
        return "invalid hosted evidence"
