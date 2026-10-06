"""Host authorization and evidence hooks around a separate, bounded provider worker."""

from __future__ import annotations

import re
import stat
import time
from pathlib import Path
from typing import Any

from ..canonical import canonical_bytes, sha256_bytes, sha256_obj
from ..runner.episode import code_identity
from .contracts import Authorization, HostedIdentity, HostedPlan
from .transport import FakeReply, HostedFailure, _contains_secret, dispatch, encode, unpack


def implementation_identity() -> dict[str, str]:
    root = Path(__file__).resolve().parents[3]
    paths = [*root.glob("src/**/*.py"), root / "pyproject.toml", root / "uv.lock"]
    digest = sha256_obj({str(p.relative_to(root)): sha256_bytes(p.read_bytes()) for p in sorted(paths)})
    return {
        "source_commit": code_identity()["commit"],
        "implementation_sha256": digest,
        "imported_path": str(root / "src/humanity_succeed"),
    }


def read_credential(path: Path) -> str:
    # Explicit selection only; literal one-line file, never sourced, expanded or discovered.
    try:
        if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise ValueError
        with path.open("rb") as stream:
            data = stream.read(65537)
        if len(data) > 65536:
            raise ValueError
        match = re.fullmatch(rb"DEEPSEEK_API_KEY=([A-Za-z0-9_-]{8,256})\r?\n?", data)
        if match is None:
            raise ValueError
        return match[1].decode("ascii")
    except Exception:
        raise HostedFailure("credential_file_invalid") from None


def make_plan(
    case, case_doc: dict[str, Any], *, model: str, allowed: list[str], simulation: bool, **options
) -> HostedPlan:
    from ..corpus.views import subject_view

    return HostedPlan.model_validate(
        {
            "schema_id": "hs-hosted-plan/1",
            **implementation_identity(),
            "simulation": simulation,
            "case_sha256": sha256_obj(case_doc),
            "subject_sha256": sha256_obj(subject_view(case).model_dump(mode="json")),
            "evaluator": "hs-evaluator/0.3.0",
            "model": model,
            "allowed_returned_models": allowed,
            **options,
        },
        strict=True,
    )


class DeepSeekProvider:
    kind = "deepseek"

    def __init__(
        self,
        plan: HostedPlan,
        authorization: Authorization,
        *,
        cloud_enabled: bool,
        credential_file: Path,
        ledger: Path,
        fake_replies: list[FakeReply] | None = None,
    ):
        if not cloud_enabled:
            raise HostedFailure("cloud_disabled")
        self.plan = plan
        self.authorization = authorization
        self.hosted = HostedIdentity(
            schema_id="hs-hosted-provider/1",
            plan=plan,
            plan_sha256=sha256_obj(plan.model_dump(mode="json")),
            authorization=authorization,
            authorization_sha256=sha256_obj(authorization.model_dump(mode="json")),
        ).model_dump(mode="json")
        self.check_authorization()
        if authorization.ledger_root != str(ledger.resolve()):
            raise HostedFailure("authorization_ledger_mismatch")
        if plan.simulation != (fake_replies is not None):
            raise HostedFailure("transport_class_mismatch")
        self._secret = read_credential(credential_file)
        self._fakes = fake_replies
        self.attempts = 0
        self._start = time.monotonic()
        self._ledger = ledger / (authorization.authorization_id + ".jsonl")
        self.request_record: dict[str, Any] | None = None
        self.response_record: dict[str, Any] | None = None
        self.request_body = b""
        self.response_body = b""
        self._claimed = False
        self._prepared = False

    def check_authorization(self):
        now = int(time.time())
        a = self.authorization
        if (
            sha256_obj(self.plan.model_dump(mode="json")) != self.hosted["plan_sha256"]
            or sha256_obj(a.model_dump(mode="json")) != self.hosted["authorization_sha256"]
        ):
            raise HostedFailure("authorization_changed")
        if not a.issued_at <= now < a.expires_at:
            raise HostedFailure("authorization_expired_or_future")
        if a.plan_sha256 != sha256_obj(self.plan.model_dump(mode="json")):
            raise HostedFailure("authorization_mismatch")
        identity = implementation_identity()
        if any(getattr(self.plan, k) != v for k, v in identity.items()):
            raise HostedFailure("implementation_changed")

    def validate_case(self, case_doc: dict[str, Any], subject: dict[str, Any], evaluator: str):
        self.check_authorization()
        if (
            sha256_obj(case_doc) != self.plan.case_sha256
            or sha256_obj(subject) != self.plan.subject_sha256
            or evaluator != self.plan.evaluator
        ):
            raise HostedFailure("case_or_evaluator_mismatch")
        if _contains_secret(case_doc, self._secret):
            raise HostedFailure("credential_in_source")
        if _contains_secret(self.hosted, self._secret):
            raise HostedFailure("credential_in_configuration")
        if self._claimed:
            raise HostedFailure("authorization_already_claimed")
        if not self._claimed:
            self._ledger.parent.mkdir(parents=True, exist_ok=True)
            try:
                with self._ledger.open("xb") as stream:
                    stream.write(
                        canonical_bytes(
                            {"authorization_sha256": self.hosted["authorization_sha256"], "claimed": True}
                        )
                        + b"\n"
                    )
            except FileExistsError:
                raise HostedFailure("authorization_already_claimed") from None
            self._claimed = True

    def prepare(self, observation: bytes):
        self.check_authorization()
        self._prepared = False
        if self.attempts >= self.plan.limits.requests:
            raise HostedFailure("request_budget_exhausted")
        if time.monotonic() - self._start >= self.plan.limits.episode_seconds:
            raise HostedFailure("episode_budget_exhausted")
        body = encode(observation, self.plan.model, self.plan.settings)
        from ..canonical import strict_json_loads

        if _contains_secret(strict_json_loads(body), self._secret):
            raise HostedFailure("credential_in_observation")
        if len(body) > self.plan.limits.request_bytes:
            raise HostedFailure("request_size_limit")
        self.request_body = body
        self.request_record = {
            "schema_id": "hs-hosted-request/1",
            "encoding": self.plan.encoding,
            "request_sha256": sha256_bytes(body),
            "canonical_input_sha256": sha256_bytes(observation),
            "authorization_sha256": self.hosted["authorization_sha256"],
            "attempt": self.attempts + 1,
            "reserved_output_tokens": self.plan.settings.max_tokens,
        }
        self._prepared = True

    def generate(self, observation: bytes) -> str:
        if not self._claimed or not self._prepared:
            raise HostedFailure("request_not_prepared")
        self.check_authorization()  # Authorization can expire between preparation and dispatch.
        if (
            self.request_record is None
            or sha256_bytes(observation) != self.request_record["canonical_input_sha256"]
        ):
            raise HostedFailure("observation_changed")
        remaining = self.plan.limits.episode_seconds - (time.monotonic() - self._start)
        if remaining <= 0:
            raise HostedFailure("episode_budget_exhausted")
        # Durable reservation BEFORE dispatch; crashes/timeouts do not replenish this allowance.
        with self._ledger.open("ab") as stream:
            stream.write(canonical_bytes(self.request_record) + b"\n")
            stream.flush()
            import os

            os.fsync(stream.fileno())
        self._prepared = False
        fake = None
        if self._fakes is not None:
            if self.attempts >= len(self._fakes):
                raise HostedFailure("fake_transport_exhausted")
            fake = self._fakes[self.attempts]
        self.attempts += 1
        data, elapsed = dispatch(
            self.request_body,
            self._secret,
            min(self.plan.limits.request_seconds, remaining),
            self.plan.limits.response_bytes,
            fake,
        )
        raw, metadata = unpack(
            data, elapsed, self.plan.allowed_returned_models, self.plan.limits.action_bytes
        )
        self.response_body, self.response_record = data, metadata
        return raw


class RecordedProvider:
    """Offline replay adapter: recorded metadata is evidence, not a newly measured request."""

    kind = "deepseek"

    def __init__(self, manifest, events, artifacts: Path):
        self.hosted = manifest["provider"]["hosted"]
        self.events = [e for e in events if e["event_type"] in ("provider_response", "provider_error")]
        self.requests = [e for e in events if e["event_type"] == "provider_requested"]
        self.artifacts = artifacts
        self.index = 0
        self.request_record = None
        self.response_record = None

    def validate_case(self, case_doc, subject, evaluator):
        p = self.hosted["plan"]
        if sha256_obj(case_doc) != p["case_sha256"] or sha256_obj(subject) != p["subject_sha256"]:
            raise HostedFailure("replay_case_mismatch")

    def prepare(self, observation):
        event = self.events[self.index]
        request = next((e for e in self.requests if e["payload"]["call_index"] == self.index), None)
        if request is None:
            raise HostedFailure(event["payload"]["code"])
        self.request_record = request["payload"]["hosted"]
        if sha256_bytes(observation) != self.request_record["canonical_input_sha256"]:
            raise HostedFailure("replay_observation_changed")
        self.request_body = (self.artifacts / self.request_record["request_sha256"]).read_bytes()

    def generate(self, observation):
        event = self.events[self.index]
        self.index += 1
        if event["event_type"] == "provider_error":
            p = event["payload"]
            failure = HostedFailure(p["code"])
            failure.record = p["hosted"]
            raise failure
        self.response_record = event["payload"]["hosted"]
        self.response_body = (self.artifacts / self.response_record["response_sha256"]).read_bytes()
        return (self.artifacts / event["payload"]["raw_sha256"]).read_bytes().decode()
