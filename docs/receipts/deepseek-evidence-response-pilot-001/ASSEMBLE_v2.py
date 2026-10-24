"""New local freeze after a preparation-tool lint correction; original freeze stays intact."""

from datetime import UTC, datetime
from pathlib import Path

import PREFLIGHT_v2

from humanity_succeed.canonical import canonical_bytes, load_document, sha256_bytes, sha256_obj
from humanity_succeed.contracts.case import review_source_sha256
from humanity_succeed.corpus.views import four_views
from humanity_succeed.hosted.contracts import HostedPlan
from humanity_succeed.hosted.provider import make_plan
from humanity_succeed.runner.scripted import load_case

PACKET = Path(__file__).resolve().parent


def write_new(name, document):
    path = PACKET / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(canonical_bytes(document))


def main():
    PREFLIGHT_v2.deny_external_access()
    previous = load_document(PACKET / "FREEZE.json")
    PREFLIGHT_v2.verify_members(PACKET, previous)
    revision = load_document(PACKET / "REVISION.json")
    assert revision["previous_freeze_sha256"] == sha256_obj(previous)
    old_plan = load_document(PACKET / "PILOT_PLAN.json")
    assert revision["previous_plan_sha256"] == sha256_obj(old_plan)
    # Root references are corrected by the case author, not by the spec author.
    # Task/evidence/criteria/outcomes are unchanged; original v1 members remain intact.
    review = load_document(PACKET / "REVIEW_PACKET.blank.json")
    episodes = []
    for index, old in enumerate(old_plan["episodes"]):
        status = old["evidence_status"]
        case_path = f"cases_v2/{status}.json"
        case, doc = load_case(PACKET / case_path)
        old_case, old_doc = load_case(PACKET / old["case"])
        compare = dict(old_doc)
        compare["derivation_ids"] = []
        assert doc == compare
        assert case.subject == old_case.subject and case.evaluation == old_case.evaluation
        hosted = HostedPlan.model_validate(load_document(PACKET / old["hosted_plan"]), strict=True)
        new = make_plan(
            case,
            doc,
            model=hosted.model,
            allowed=hosted.allowed_returned_models,
            simulation=False,
            settings=hosted.settings,
            limits=hosted.limits,
        )
        new_path = f"plans_v2/{status}.json"
        write_new(new_path, new.model_dump(mode="json"))
        row = dict(old)
        row.update(
            case=case_path,
            derivation_ids=[],
            case_sha256=sha256_obj(doc),
            review_source_sha256=review_source_sha256(doc),
            hosted_plan=new_path,
            hosted_plan_sha256=sha256_obj(new.model_dump(mode="json")),
        )
        # Observation and outgoing request bytes are unchanged; explicitly retain new copies.
        for key in ("observation", "request"):
            new_name = old[key].replace("outbound/", "outbound_v2/")
            write_new(new_name, load_document(PACKET / old[key]))
            assert (PACKET / new_name).read_bytes() == (PACKET / old[key]).read_bytes()
            row[key] = new_name
        for view, value in four_views(case, doc).items():
            write_new(f"views_v2/{status}/{view}.json", value)
        episodes.append(row)
        entry = review["episodes"][index]
        entry.update(
            case=case_path, case_sha256=sha256_obj(doc), review_source_sha256=review_source_sha256(doc)
        )
        entry["authored_expectations_ref"] = entry["authored_expectations_ref"].replace("cases/", "cases_v2/")
    write_new("REVIEW_PACKET.blank.v2.json", review)
    added = [
        "FREEZE.json",
        "PILOT_PLAN.json",
        "REVISION.json",
        "ASSEMBLE_v2.py",
        "PREFLIGHT_v2.py",
        "test_preparation_v2.py",
        "REVIEW_PACKET.blank.v2.json",
    ]
    for directory in ("cases_v2", "plans_v2", "outbound_v2", "views_v2"):
        added.extend(
            str(path.relative_to(PACKET)) for path in (PACKET / directory).rglob("*") if path.is_file()
        )
    frozen = dict(previous)
    frozen.update(
        version=2,
        frozen_at_utc=datetime.now(UTC).isoformat(),
        previous_freeze_sha256=sha256_obj(previous),
        revision_ref="REVISION.json",
        episodes=episodes,
        review_template_sha256=sha256_obj(review),
        criteria_and_acceptable_outcomes="cases_v2/AUTHOR_NOTES.json; pre-subject-call authored contract",
    )
    frozen["files_sha256"] = {
        **previous["files_sha256"],
        **{name: sha256_bytes((PACKET / name).read_bytes()) for name in added},
    }
    write_new("FREEZE.v2.json", frozen)
    plan = dict(old_plan)
    plan.update(
        version=2,
        freeze_sha256=sha256_obj(frozen),
        previous_plan_sha256=sha256_obj(old_plan),
        revision_ref="REVISION.json",
        preflight="PREFLIGHT_v2.py",
        episodes=episodes,
    )
    plan["outbound"] = {**old_plan["outbound"], "initial_request_files": [row["request"] for row in episodes]}
    write_new("PILOT_PLAN.v2.json", plan)
    print(
        {
            "plan_sha256": sha256_obj(plan),
            "freeze_sha256": sha256_obj(frozen),
            "case_ancestry_metadata_corrected": True,
            "task_evidence_criteria_outcomes_changed": False,
            "model_calls": 0,
        }
    )


if __name__ == "__main__":
    main()
