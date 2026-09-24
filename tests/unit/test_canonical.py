import math

import pytest
from hypothesis import given
from hypothesis import strategies as st

from humanity_succeed.canonical import (
    MAX_DOCUMENT_BYTES,
    StrictLoadError,
    canonical_bytes,
    json_equal,
    make_new_dir,
    sha256_obj,
    strict_json_loads,
    strict_yaml_loads,
    write_new_file,
)

json_values = st.recursive(
    st.none() | st.booleans() | st.integers() | st.text()
    | st.floats(allow_nan=False, allow_infinity=False),
    lambda kids: st.lists(kids, max_size=4) | st.dictionaries(st.text(max_size=8), kids, max_size=4),
    max_leaves=20,
)


@pytest.mark.parametrize("text,code", [
    ('{"a":1,"a":2}', "duplicate_key"),
    ("NaN", "nonfinite_number"),
    ('{"a":Infinity}', "nonfinite_number"),
    ('{"a":-Infinity}', "nonfinite_number"),
    ("{", "invalid_json"),
])
def test_strict_json_rejects(text, code):
    with pytest.raises(StrictLoadError) as e:
        strict_json_loads(text)
    assert e.value.code == code


@pytest.mark.parametrize("text,code", [
    ("a: 1\na: 2\n", "duplicate_key"),
    ("a: &x 1\nb: *x\n", "yaml_alias"),
    ("a: !!python/object/apply:os.system ['true']\n", "invalid_yaml"),
    ("a: !!float .nan\n", "non_json_scalar"),
    ("a: !!bool no\n", "non_json_scalar"),
    ("a: !!bool yes\n", "non_json_scalar"),
    ("a: !!int 010\n", "non_json_scalar"),
    ("a: !!int 1:30\n", "non_json_scalar"),
    ("a: !!int 1_000\n", "non_json_scalar"),
    ("a: !!int 0x1F\n", "non_json_scalar"),
    ("a: !!float 1:30\n", "non_json_scalar"),
    ("a: !!null x\n", "non_json_scalar"),
    ("a: !!timestamp 2026-09-24\n", "non_json_type"),
    ("a: !!binary aGk=\n", "non_json_type"),
    ("a: !!set {x}\n", "non_json_type"),
    (b"a: \xff\n", "invalid_utf8"),
    ("a: 1\n---\nb: 2\n", "document_count"),
    ("1: x\n", "non_string_key"),
])
def test_strict_yaml_rejects(text, code):
    with pytest.raises(StrictLoadError) as e:
        strict_yaml_loads(text)
    assert e.value.code == code


def test_yaml_dates_stay_strings():
    assert strict_yaml_loads("d: 2026-09-24\n") == {"d": "2026-09-24"}


def test_yaml_uses_json_model_implicit_typing():
    """Red-team #11: YAML 1.1 implicit typing silently changed types."""
    doc = strict_yaml_loads(
        "a: no\nb: yes\nc: on\nd: off\ne: 017\nf: 0o17\ng: 1_000\nh: 12:30\ni: .nan\n"
        "t: true\nn: null\nz: ~\nk: 48\nm: -3\nx: 1.5\ny: 1e5\n")
    assert doc == {"a": "no", "b": "yes", "c": "on", "d": "off", "e": "017", "f": "0o17",
                   "g": "1_000", "h": "12:30", "i": ".nan", "t": True, "n": None, "z": None,
                   "k": 48, "m": -3, "x": 1.5, "y": 100000.0}


@pytest.mark.parametrize("text", ['{"a":"\\ud800"}', '{"\\udc00":1}', '"\ud800"'])
def test_lone_surrogates_rejected(text):
    """Red-team #9: a lone surrogate crashed canonical hashing downstream."""
    with pytest.raises(StrictLoadError) as e:
        strict_json_loads(text)
    assert e.value.code == "invalid_unicode"


def test_oversize_rejected():
    with pytest.raises(StrictLoadError) as e:
        strict_json_loads(b" " * (MAX_DOCUMENT_BYTES + 1))
    assert e.value.code == "document_too_large"


def test_canonical_form_is_sorted_compact_utf8():
    assert canonical_bytes({"b": 1, "a": "é"}) == '{"a":"é","b":1}'.encode()
    with pytest.raises(StrictLoadError):
        canonical_bytes({"x": math.nan})


@given(json_values)
def test_canonical_roundtrip_hash_stable(v):
    assert sha256_obj(strict_json_loads(canonical_bytes(v))) == sha256_obj(v)


def test_json_equal_is_type_exact():
    assert not json_equal(True, 1)
    assert not json_equal(1, 1.0)
    assert not json_equal(0, False)
    assert json_equal({"a": [1, "x"]}, {"a": [1, "x"]})


def test_refuse_overwrite(tmp_path):
    f = tmp_path / "f"
    write_new_file(f, b"1")
    with pytest.raises(FileExistsError):
        write_new_file(f, b"2")
    with pytest.raises(FileExistsError):
        make_new_dir(tmp_path)


def test_explicit_json_tags_still_allowed():
    """Red-team round 2 (#11): explicit tags are held to the JSON grammar, not banned."""
    assert strict_yaml_loads("a: !!int 12\nb: !!bool true\nc: !!float 1.5\nd: !!null ~\n"
                             "e: !!str no\nf: !!float 3\n") == {
        "a": 12, "b": True, "c": 1.5, "d": None, "e": "no", "f": 3.0}


def test_unreadable_path_is_a_strict_load_error(tmp_path):
    """Red-team round 2 (#13): a directory passed as a document raised a raw OSError."""
    from humanity_succeed.canonical import load_document

    d = tmp_path / "x.yaml"
    d.mkdir()
    with pytest.raises(StrictLoadError) as e:
        load_document(d)
    assert e.value.code == "unreadable_path"
