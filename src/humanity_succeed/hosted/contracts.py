"""Prospective hosted contracts; original offline approval contracts remain unchanged."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Hash = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
ENCODING: Literal["hs-deepseek-transcript/1"] = "hs-deepseek-transcript/1"
DESTINATION: Literal["https://api.deepseek.com/chat/completions"] = (
    "https://api.deepseek.com/chat/completions"
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Settings(Strict):
    stream: Literal[False] = False
    response_format: Literal["json_object"] = "json_object"
    thinking: Literal["enabled"] = "enabled"
    reasoning_effort: Literal["high"] = "high"
    max_tokens: Annotated[int, Field(ge=1, le=4096)] = 4096


class Limits(Strict):
    requests: Annotated[int, Field(ge=1, le=4)] = 4
    request_bytes: Annotated[int, Field(ge=1, le=65536)] = 65536
    response_bytes: Annotated[int, Field(ge=1, le=1000000)] = 1000000
    action_bytes: Annotated[int, Field(ge=1, le=64000)] = 64000
    request_seconds: Annotated[int, Field(ge=1, le=45)] = 45
    episode_seconds: Annotated[int, Field(ge=1, le=180)] = 180


class HostedPlan(Strict):
    schema_id: Literal["hs-hosted-plan/1"]
    simulation: bool
    source_commit: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")]
    implementation_sha256: Hash
    imported_path: str
    case_sha256: Hash
    subject_sha256: Hash
    evaluator: Literal["hs-evaluator/0.3.0"]
    model: Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9._-]+$")]
    allowed_returned_models: Annotated[list[str], Field(min_length=1)]
    destination: Literal["https://api.deepseek.com/chat/completions"] = DESTINATION
    encoding: Literal["hs-deepseek-transcript/1"] = ENCODING
    settings: Settings = Settings()
    limits: Limits = Limits()

    @model_validator(mode="after")
    def models(self):
        if len(set(self.allowed_returned_models)) != len(self.allowed_returned_models):
            raise ValueError("duplicate returned model")
        return self


class Authorization(Strict):
    schema_id: Literal["hs-hosted-authorization/1"]
    authorization_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")]
    plan_sha256: Hash
    ledger_root: Annotated[str, Field(min_length=1)]
    issued_at: int
    expires_at: int
    allow_cloud: Literal[True]
    simulation: bool
    approver: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def interval(self):
        if self.expires_at <= self.issued_at:
            raise ValueError("invalid authorization interval")
        return self


class HostedIdentity(Strict):
    schema_id: Literal["hs-hosted-provider/1"]
    plan: HostedPlan
    plan_sha256: Hash
    authorization: Authorization
    authorization_sha256: Hash
    weights_sha256: None = None
    tokenizer_identity: None = None

    @model_validator(mode="after")
    def bindings(self):
        from ..canonical import sha256_obj

        if self.plan_sha256 != sha256_obj(self.plan.model_dump(mode="json")):
            raise ValueError("plan hash mismatch")
        if self.authorization_sha256 != sha256_obj(self.authorization.model_dump(mode="json")):
            raise ValueError("authorization hash mismatch")
        if self.authorization.plan_sha256 != self.plan_sha256:
            raise ValueError("authorization does not bind plan")
        if self.authorization.simulation != self.plan.simulation:
            raise ValueError("simulation authorization mismatch")
        return self


class RequestRecord(Strict):
    schema_id: Literal["hs-hosted-request/1"]
    encoding: Literal["hs-deepseek-transcript/1"] = ENCODING
    request_sha256: Hash
    canonical_input_sha256: Hash
    authorization_sha256: Hash
    attempt: Annotated[int, Field(ge=1, le=4)]
    reserved_output_tokens: Annotated[int, Field(ge=1, le=4096)]


class ResponseRecord(Strict):
    schema_id: Literal["hs-hosted-response/1"]
    response_sha256: Hash
    returned_model: str
    response_id: str | None
    system_fingerprint: str | None
    usage: dict[str, Any] | None
    finish_reason: str
    elapsed_ms: Annotated[int, Field(ge=0)]
    execute_content: bool


class FailureRecord(Strict):
    schema_id: Literal["hs-hosted-failure/1"]
    attempted: bool
    elapsed_ms: Annotated[int, Field(ge=0)]
    completion_unknown: bool
    billing_unknown: bool
