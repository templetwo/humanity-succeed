"""Packet JSON Schemas, registered locally. No schema URL is ever fetched.

``packet_schemas/`` holds byte-identical copies of the packet's ``schemas/*.schema.json``
(asserted by tests/unit/test_contracts.py). The implementation case schema is the packet case
schema plus exactly one added predicate variant (local extension B03); a test proves that is the
only difference.
"""

from __future__ import annotations

import copy
import json
from functools import cache
from importlib import resources
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

PACKET_SCHEMA_FILES = (
    "action.schema.json",
    "approval.schema.json",
    "case.schema.json",
    "event.schema.json",
    "model-manifest.schema.json",
)

PROPOSAL_EXISTS_VARIANT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "op": {"const": "proposal_exists"},
        "action_type": {
            "type": "string",
            "enum": [
                "read_resource",
                "write_resource",
                "notify",
                "request_clarification",
                "decline",
                "wait",
                "finish",
            ],
        },
        "resource_id": {"type": "string", "minLength": 1},
    },
    "required": ["op", "action_type"],
    "additionalProperties": False,
}


def packet_schema_bytes(name: str) -> bytes:
    return resources.files(__package__).joinpath("packet_schemas", name).read_bytes()


@cache
def packet_schema(name: str) -> dict[str, Any]:
    return json.loads(packet_schema_bytes(name))


@cache
def implementation_case_schema() -> dict[str, Any]:
    s = copy.deepcopy(packet_schema("case.schema.json"))
    s["$id"] = "urn:humanity-succeed:case:1.0+hs-local-b03"
    s["$defs"]["predicate"]["oneOf"].append(PROPOSAL_EXISTS_VARIANT)
    return s


def _no_remote(uri: str) -> Resource:
    raise NoSuchResource(ref=uri)


@cache
def _registry() -> Registry:
    pairs = []
    for name in PACKET_SCHEMA_FILES:
        s = packet_schema(name)
        pairs.append((s["$id"], Resource.from_contents(s)))
    return Registry(retrieve=_no_remote).with_resources(pairs)  # type: ignore[call-arg]


def validator(schema: dict[str, Any]) -> Draft202012Validator:
    return Draft202012Validator(schema, registry=_registry(), format_checker=FormatChecker())


def schema_errors(instance: Any, schema: dict[str, Any]) -> list[str]:
    errs = sorted(validator(schema).iter_errors(instance), key=lambda e: list(e.absolute_path))
    return [f"/{'/'.join(str(p) for p in e.absolute_path)}: {e.message}" for e in errs]
