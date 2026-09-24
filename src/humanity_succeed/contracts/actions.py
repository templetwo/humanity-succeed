"""Subject action contract: exactly one strict JSON object per model turn (BUILD_SPEC §6.2).

The parser never repairs markdown, never extracts commands from prose, and never accepts more
than one object. A failed parse is an observed behavior (``invalid_action``), not a retry trigger.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, ValidationError, field_validator

from ..canonical import StrictLoadError, _check_finite, strict_json_loads

TOOL_NAMES = (
    "read_resource",
    "write_resource",
    "notify",
    "request_clarification",
    "decline",
    "wait",
    "finish",
)

MAX_RAW_RESPONSE_BYTES = 64_000
MAX_MESSAGE_CHARS = 4000


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class ReadResource(_Strict):
    type: Literal["read_resource"]
    resource_id: Annotated[str, Field(min_length=1)]


class WriteResource(_Strict):
    type: Literal["write_resource"]
    resource_id: Annotated[str, Field(min_length=1)]
    expected_revision: Annotated[int, Field(ge=0)]
    value: Any

    @field_validator("value")
    @classmethod
    def _json_value(cls, v: Any) -> Any:
        _check_json_value(v)
        return v


class Notify(_Strict):
    type: Literal["notify"]
    actor_ids: Annotated[list[Annotated[str, Field(min_length=1)]], Field(min_length=1)]
    resource_ids: Annotated[list[Annotated[str, Field(min_length=1)]], Field(min_length=1)]
    text: Annotated[str, Field(min_length=1)]


class RequestClarification(_Strict):
    type: Literal["request_clarification"]
    question: Annotated[str, Field(min_length=1)]


class Decline(_Strict):
    type: Literal["decline"]
    reason: Annotated[str, Field(min_length=1)]
    alternative: str | None = None

    @field_validator("alternative")
    @classmethod
    def _no_explicit_null(cls, v: str | None) -> str:
        # The packet schema allows the key to be absent, not null.
        if v is None:
            raise ValueError("alternative may be omitted but not null")
        return v


class Wait(_Strict):
    type: Literal["wait"]
    ticks: Annotated[int, Field(ge=1, le=100)]


class Finish(_Strict):
    type: Literal["finish"]
    summary: str
    delivered_resource_ids: list[Annotated[str, Field(min_length=1)]]


Action = Annotated[
    ReadResource | WriteResource | Notify | RequestClarification | Decline | Wait | Finish,
    Field(discriminator="type"),
]


class ActionEnvelope(_Strict):
    action: Action
    message: Annotated[str, Field(max_length=MAX_MESSAGE_CHARS)] | None = None

    @field_validator("message")
    @classmethod
    def _no_explicit_null(cls, v: str | None) -> str:
        if v is None:
            raise ValueError("message may be omitted but not null")
        return v


_ENVELOPE = TypeAdapter(ActionEnvelope)


def _check_json_value(v: Any) -> None:
    if isinstance(v, (bool, int, float, str)) or v is None:
        _check_finite(v)
        return
    if isinstance(v, list):
        for x in v:
            _check_json_value(x)
        return
    if isinstance(v, dict):
        for k, x in v.items():
            if not isinstance(k, str):
                raise ValueError("object keys must be strings")
            _check_json_value(x)
        return
    raise ValueError(f"not a JSON value: {type(v).__name__}")


class ParseFailure(Exception):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def parse_action(raw: str) -> ActionEnvelope:
    """Parse one raw model response into an ActionEnvelope, or raise ParseFailure.

    Leading/trailing whitespace is the only tolerance. Code fences, prose, multiple objects,
    duplicate keys, unknown fields, unknown action types, bool-for-int and non-finite numbers
    all fail closed.
    """
    if len(raw.encode("utf-8")) > MAX_RAW_RESPONSE_BYTES:
        raise ParseFailure("response_too_large", f"over {MAX_RAW_RESPONSE_BYTES} bytes")
    text = raw.strip()
    if not text:
        raise ParseFailure("empty_response", "no content")
    if not text.startswith("{"):
        raise ParseFailure("not_a_json_object", "response must be exactly one JSON object")
    try:
        obj = strict_json_loads(text)
    except StrictLoadError as e:
        raise ParseFailure(e.code, str(e)) from e
    if not isinstance(obj, dict):
        raise ParseFailure("not_a_json_object", "response must be exactly one JSON object")
    try:
        return _ENVELOPE.validate_python(obj, strict=True)
    except ValidationError as e:
        first = e.errors()[0]
        loc = ".".join(str(p) for p in first.get("loc", ()))
        raise ParseFailure("schema_violation", f"{loc}: {first.get('type')}") from e


def action_to_dict(env: ActionEnvelope) -> dict[str, Any]:
    d: dict[str, Any] = {"action": env.action.model_dump(exclude_none=True)}
    if env.message is not None:
        d["message"] = env.message
    return d
