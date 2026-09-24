"""Canonical JSON, hashing, and strict document loading.

Canonical form (BUILD_SPEC §7.1): UTF-8, sorted object keys, compact separators, no NaN or
Infinity, no trailing newline inside hashed bytes. JSONL exports append exactly one "\\n" per line;
that newline is not part of any hashed record.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import yaml

MAX_DOCUMENT_BYTES = 1_000_000
MAX_DEPTH = 64
MAX_STRING_CHARS = 100_000
MAX_CONTAINER_ITEMS = 10_000


class StrictLoadError(ValueError):
    """A document violated a strict-loading rule. The message names the rule."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"{code}: {message}")
        self.code = code


def canonical_bytes(obj: Any) -> bytes:
    _check_finite(obj)
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
    ).encode("utf-8")


def canonical_str(obj: Any) -> str:
    return canonical_bytes(obj).decode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_obj(obj: Any) -> str:
    return sha256_bytes(canonical_bytes(obj))


def json_equal(a: Any, b: Any) -> bool:
    """Exact JSON equality. Unlike Python ``==``, ``True`` is not ``1`` and ``1`` is not ``1.0``."""
    return _typed(a) == _typed(b)


def _typed(v: Any) -> Any:
    if isinstance(v, bool) or v is None:
        return ("lit", v)
    if isinstance(v, int):
        return ("int", v)
    if isinstance(v, float):
        return ("float", v)
    if isinstance(v, str):
        return ("str", v)
    if isinstance(v, list):
        return ("list", tuple(_typed(x) for x in v))
    if isinstance(v, dict):
        return ("dict", tuple(sorted((k, _typed(x)) for k, x in v.items())))
    raise TypeError(f"not a JSON value: {type(v).__name__}")


def _check_finite(obj: Any, depth: int = 0) -> None:
    if depth > MAX_DEPTH:
        raise StrictLoadError("depth_exceeded", f"nesting deeper than {MAX_DEPTH}")
    if isinstance(obj, float) and not math.isfinite(obj):
        raise StrictLoadError("nonfinite_number", "NaN/Infinity are not JSON")
    if isinstance(obj, dict):
        if len(obj) > MAX_CONTAINER_ITEMS:
            raise StrictLoadError("too_many_items", "object too large")
        for k, v in obj.items():
            if not isinstance(k, str):
                raise StrictLoadError("non_string_key", f"object key {k!r} is not a string")
            _check_finite(v, depth + 1)
    elif isinstance(obj, list):
        if len(obj) > MAX_CONTAINER_ITEMS:
            raise StrictLoadError("too_many_items", "array too large")
        for v in obj:
            _check_finite(v, depth + 1)
    elif isinstance(obj, str) and len(obj) > MAX_STRING_CHARS:
        raise StrictLoadError("string_too_long", f"string longer than {MAX_STRING_CHARS}")


def _no_dup_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in pairs:
        if k in out:
            raise StrictLoadError("duplicate_key", f"duplicate JSON key {k!r}")
        out[k] = v
    return out


def _reject_constant(name: str) -> Any:
    raise StrictLoadError("nonfinite_number", f"{name} is not JSON")


def strict_json_loads(text: str | bytes) -> Any:
    """Parse exactly one JSON document. Rejects duplicate keys, NaN/Infinity, and oversize input."""
    if isinstance(text, bytes):
        if len(text) > MAX_DOCUMENT_BYTES:
            raise StrictLoadError("document_too_large", f"over {MAX_DOCUMENT_BYTES} bytes")
        try:
            text = text.decode("utf-8")
        except UnicodeDecodeError as e:
            raise StrictLoadError("invalid_utf8", str(e)) from e
    if len(text.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise StrictLoadError("document_too_large", f"over {MAX_DOCUMENT_BYTES} bytes")
    try:
        obj = json.loads(
            text, object_pairs_hook=_no_dup_pairs, parse_constant=_reject_constant
        )
    except StrictLoadError:
        raise
    except (json.JSONDecodeError, RecursionError) as e:
        raise StrictLoadError("invalid_json", str(e)) from e
    _check_finite(obj)
    return obj


class _StrictYamlLoader(yaml.SafeLoader):
    """SafeLoader (no arbitrary tags) that also rejects duplicate mapping keys and aliases."""

    def compose_node(self, parent, index):  # type: ignore[override]
        if self.check_event(yaml.AliasEvent):
            raise StrictLoadError("yaml_alias", "YAML anchors/aliases are not accepted")
        return super().compose_node(parent, index)


def _construct_mapping(loader: _StrictYamlLoader, node: yaml.MappingNode, deep: bool = False):
    loader.flatten_mapping(node)
    out: dict[Any, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise StrictLoadError("non_string_key", f"YAML key {key!r} is not a string")
        if key in out:
            raise StrictLoadError("duplicate_key", f"duplicate YAML key {key!r}")
        out[key] = loader.construct_object(value_node, deep=deep)
    return out


_StrictYamlLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping
)
# Timestamps and other implicit non-JSON types are refused: keep YAML to the JSON data model.
_StrictYamlLoader.add_constructor(
    "tag:yaml.org,2002:timestamp", lambda loader, node: loader.construct_scalar(node),  # type: ignore[arg-type]
)


def strict_yaml_loads(text: str | bytes) -> Any:
    if isinstance(text, bytes):
        if len(text) > MAX_DOCUMENT_BYTES:
            raise StrictLoadError("document_too_large", f"over {MAX_DOCUMENT_BYTES} bytes")
        text = text.decode("utf-8")
    if len(text.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        raise StrictLoadError("document_too_large", f"over {MAX_DOCUMENT_BYTES} bytes")
    loader = _StrictYamlLoader(text)
    try:
        docs = []
        while loader.check_data():
            docs.append(loader.get_data())
    except StrictLoadError:
        raise
    except yaml.YAMLError as e:
        raise StrictLoadError("invalid_yaml", str(e)) from e
    finally:
        loader.dispose()
    if len(docs) != 1:
        raise StrictLoadError("document_count", f"expected exactly one YAML document, got {len(docs)}")
    _check_finite(docs[0])
    return docs[0]


def load_document(path: Path) -> Any:
    data = path.read_bytes()
    if path.suffix in (".yaml", ".yml"):
        return strict_yaml_loads(data)
    if path.suffix == ".json":
        return strict_json_loads(data)
    raise StrictLoadError("unsupported_extension", f"{path.name}: expected .yaml, .yml or .json")


def write_new_file(path: Path, data: bytes) -> None:
    """Create a file; refuse to overwrite (every mutating command creates a new object)."""
    with open(path, "xb") as f:
        f.write(data)


def make_new_dir(path: Path) -> Path:
    """Create a new, empty output directory; refuse an existing path."""
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing path: {path}")
    path.mkdir(parents=True)
    return path
