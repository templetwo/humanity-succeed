import copy
import subprocess
import sys

import pytest
from pydantic import ValidationError

from humanity_succeed.canonical import load_document
from humanity_succeed.contracts.actions import ParseFailure, parse_action
from humanity_succeed.contracts.case import CaseSource, semantic_problems
from humanity_succeed.contracts.schemas import (
    NOTIFICATION_AFTER_STATE_VARIANT,
    PACKET_SCHEMA_FILES,
    PROPOSAL_EXISTS_VARIANT,
    implementation_case_schema,
    packet_schema,
    packet_schema_bytes,
    schema_errors,
)

from ..conftest import DEV_CASES, EXAMPLES, REPO


def test_embedded_packet_schemas_are_byte_identical_to_packet():
    for name in PACKET_SCHEMA_FILES:
        assert packet_schema_bytes(name) == (REPO / "schemas" / name).read_bytes(), name


def test_implementation_schema_only_adds_the_two_local_extensions():
    packet = copy.deepcopy(packet_schema("case.schema.json"))
    impl = copy.deepcopy(implementation_case_schema())
    assert impl["$defs"]["predicate"]["oneOf"].pop() == NOTIFICATION_AFTER_STATE_VARIANT  # B42
    assert impl["$defs"]["predicate"]["oneOf"].pop() == PROPOSAL_EXISTS_VARIANT  # B03
    impl["$id"] = packet["$id"]
    assert impl == packet


def test_generated_schemas_are_frozen():
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "export_schemas.py"), "--check"],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.yaml")) + sorted(DEV_CASES.glob("*.yaml")))
def test_fixtures_validate(path):
    doc = load_document(path)
    assert schema_errors(doc, implementation_case_schema()) == []
    case = CaseSource.model_validate(doc, strict=True)
    assert semantic_problems(case) == []
    assert case.reviews == []  # no fabricated reviews anywhere in the repo fixtures
    assert case.provenance.rights_status == "pending"
    assert case.split == "commissioning_dev"


@pytest.mark.parametrize("path", sorted(EXAMPLES.glob("*.yaml")))
def test_packet_examples_validate_against_unmodified_packet_schema(path):
    assert schema_errors(load_document(path), packet_schema("case.schema.json")) == []


def test_extension_case_is_honestly_invalid_against_packet_schema():
    doc = load_document(DEV_CASES / "correction-source-guard.yaml")
    assert schema_errors(doc, packet_schema("case.schema.json"))


def test_reject_unknown_subject_field(correction_doc):
    correction_doc["subject"]["preferred_answer"] = "write 48"
    assert schema_errors(correction_doc, implementation_case_schema())
    with pytest.raises(ValidationError):
        CaseSource.model_validate(correction_doc, strict=True)


def test_reject_private_material(correction_doc):
    correction_doc["provenance"]["private_material"] = True
    assert schema_errors(correction_doc, implementation_case_schema())
    with pytest.raises(ValidationError):
        CaseSource.model_validate(correction_doc, strict=True)


def test_goal_completed_is_unsupported_not_guessed(correction_doc):
    correction_doc["evaluation"]["pass_if"] = {"op": "goal_completed", "goal_id": "g1"}
    case = CaseSource.model_validate(correction_doc, strict=True)
    assert any("goal_completed" in p for p in semantic_problems(case))


def test_fabricated_event_name_rejected(correction_doc):
    correction_doc["evaluation"]["pass_if"] = {"op": "event_exists", "event_type": "correction_made"}
    case = CaseSource.model_validate(correction_doc, strict=True)
    assert any("unregistered event type" in p for p in semantic_problems(case))


def test_unknown_resource_reference_rejected(correction_doc):
    correction_doc["evaluation"]["pass_if"]["args"][0]["resource_id"] = "r_missing"
    case = CaseSource.model_validate(correction_doc, strict=True)
    assert any("unknown resource" in p for p in semantic_problems(case))


def test_claimed_human_review_without_record_rejected(correction_doc):
    correction_doc["provenance"]["kind"] = "ai_drafted_human_reviewed"
    case = CaseSource.model_validate(correction_doc, strict=True)
    assert any("claims human review" in p for p in semantic_problems(case))


def test_preferred_demo_must_expect_pass(correction_doc):
    correction_doc["demonstrations"][1]["training_role"] = "preferred"
    case = CaseSource.model_validate(correction_doc, strict=True)
    assert any("preferred trajectory must expect" in p for p in semantic_problems(case))


GOOD = '{"action":{"type":"read_resource","resource_id":"r_source"}}'


@pytest.mark.parametrize("raw,code", [
    ("", "empty_response"),
    ("```json\n" + GOOD + "\n```", "not_a_json_object"),
    ("Sure! " + GOOD, "not_a_json_object"),
    (GOOD + GOOD, "invalid_json"),
    ('{"action":{"type":"read_resource","resource_id":"a","resource_id":"b"}}', "duplicate_key"),
    ('{"action":{"type":"shell","cmd":"ls"}}', "schema_violation"),
    ('{"action":{"type":"read_resource","resource_id":"r","path":"/etc"}}', "schema_violation"),
    ('{"action":{"type":"write_resource","resource_id":"r","expected_revision":true,"value":1}}',
     "schema_violation"),
    ('{"action":{"type":"write_resource","resource_id":"r","expected_revision":1,"value":NaN}}',
     "nonfinite_number"),
    ('{"action":{"type":"decline","reason":"x","alternative":null}}', "schema_violation"),
    ('{"action":{"type":"wait","ticks":101}}', "schema_violation"),
    ('{"action":{"type":"finish","summary":"x","delivered_resource_ids":[]},"extra":1}',
     "schema_violation"),
    ("[1]", "not_a_json_object"),
])
def test_action_parser_fails_closed(raw, code):
    with pytest.raises(ParseFailure) as e:
        parse_action(raw)
    assert e.value.code == code


def test_action_parser_accepts_whitespace_only_tolerance():
    env = parse_action("\n  " + GOOD + "  \n")
    assert env.action.type == "read_resource"


def test_core_import_does_not_import_mlx():
    code = (
        "import importlib, sys\n"
        "class Block:\n"
        "    def find_spec(self, name, path=None, target=None):\n"
        "        if name == 'mlx' or name.startswith('mlx.') or name.startswith('mlx_lm'):\n"
        "            raise ImportError('mlx blocked for test')\n"
        "sys.meta_path.insert(0, Block())\n"
        "import humanity_succeed, humanity_succeed.cli\n"
        "for m in ['canonical','contracts.case','contracts.actions','contracts.events',"
        "'corpus.compiler','corpus.views','environment.engine','evidence.store','evidence.bundle',"
        "'evidence.replay','evaluation.predicates','runner.episode','runner.scripted','demo']:\n"
        "    importlib.import_module('humanity_succeed.' + m)\n"
        "assert not any(k == 'mlx' or k.startswith('mlx') for k in sys.modules)\n"
        "print('ok')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stderr
