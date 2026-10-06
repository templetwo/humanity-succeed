"""B57/B58 evaluator-only declarations and factual trace references, not human judgments."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Finding(_Strict):
    finding_id: Annotated[str, Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")]
    finding: Annotated[str, Field(min_length=1)]
    evidence_status: Literal["supported", "unsupported", "contradicted", "not_assessable"]


class A1Evidence(_Strict):
    schema_id: Literal["hs-a1-evidence/1"]
    findings: Annotated[list[Finding], Field(min_length=1)]

    @field_validator("findings")
    @classmethod
    def unique_identifiers(cls, findings: list[Finding]) -> list[Finding]:
        ids = [f.finding_id for f in findings]
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate finding_id")
        return findings


Seq = Annotated[int, Field(ge=1)]


class GuardWithheld(_Strict):
    proposal_seq: Seq
    permission_seq: Seq
    denial_seq: Seq
    action_type: Literal[
        "read_resource", "write_resource", "notify", "request_clarification", "decline", "wait", "finish"
    ]
    reason_code: Annotated[str, Field(min_length=1)]


class ModelAbstained(_Strict):
    proposal_seq: Seq
    execution_seq: Seq
    decline_seq: Seq


class A1Facts(_Strict):
    guard_withheld: list[GuardWithheld]
    model_abstained: list[ModelAbstained]
