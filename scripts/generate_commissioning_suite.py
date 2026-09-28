"""Assemble the WP3 commissioning suite v1 from the class generator modules (docs/WP3_DESIGN.md).

    uv run python scripts/generate_commissioning_suite.py            # writes cases/commissioning_suite_v1/
    uv run python scripts/generate_commissioning_suite.py --check    # exit 1 if committed files differ

The output is deterministic. It refuses to overwrite an existing suite directory; regenerate into
a fresh directory and compare with --check. Nothing here runs the evaluator.
"""

from __future__ import annotations

import importlib
import sys
import tempfile
from pathlib import Path

import yaml

from humanity_succeed.canonical import canonical_str
from humanity_succeed.commissioning.contract import (
    SUITE_MANIFEST_NAME,
    Expectation,
    Group,
    Member,
    SuiteManifest,
    suite_problems,
)
from humanity_succeed.commissioning.fixtures import SUITE_ID, GroupDraft

OUT = Path(__file__).resolve().parents[1] / "cases" / "commissioning_suite_v1"
MODULES = ("c1_correction", "c2_blocked", "c3_refusal", "c4_false_alarm", "c5_substitution",
           "c6_multipath", "c7_reversed_goal")


def _yaml(doc: object) -> str:
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100)


def drafts() -> list[GroupDraft]:
    out: list[GroupDraft] = []
    for name in MODULES:
        mod = importlib.import_module(f"humanity_succeed.commissioning.suite_v1.{name}")
        out.extend(mod.groups())
    return out


def render() -> dict[str, str]:
    """Relative path -> file text for the whole suite."""
    files: dict[str, str] = {}
    groups = []
    for g in drafts():
        for stem, doc in g.cases.items():
            rel = f"cases/{stem}.yaml"
            if rel in files:
                raise ValueError(f"duplicate case file {rel}")
            files[rel] = _yaml(doc)
        members = []
        for m in g.members:
            rel = f"trajectories/{m.fixture_id}.yaml"
            if rel in files:
                raise ValueError(f"duplicate trajectory file {rel}")
            files[rel] = _yaml(m.trajectory)
            members.append(Member(fixture_id=m.fixture_id, role=m.role,
                                  case=f"cases/{m.case_stem}.yaml", trajectory=rel,
                                  expected=Expectation.model_validate(m.expected.model_dump())))
        groups.append(Group(group_id=g.group_id, class_id=g.class_id,  # type: ignore[arg-type]
                            root_scenario_id=g.root_scenario_id, members=members))
    manifest = SuiteManifest(
        schema_id="hs-commission-suite/1", suite_id=SUITE_ID, authorship="builder_constructed",
        authored_by="MacBook seat WP3 build (claude-opus-5-5 lead; Sonnet generator builders)",
        split="commissioning_dev", groups=groups,
        note=("Builder-constructed development suite. Expectations were written from "
              "docs/WP3_DESIGN.md before any commissioning run. The 40 holdback-designated "
              "trajectories are builder-authored and exposed; they are not independent holdback."))
    files[SUITE_MANIFEST_NAME] = canonical_str(manifest.model_dump(mode="json")) + "\n"
    return files


def write(root: Path, files: dict[str, str]) -> None:
    root.mkdir(parents=True, exist_ok=False)
    (root / "cases").mkdir()
    (root / "trajectories").mkdir()
    for rel, text in files.items():
        (root / rel).write_text(text)


def main(check: bool) -> int:
    files = render()
    with tempfile.TemporaryDirectory() as d:
        tmp = Path(d) / "suite"
        write(tmp, files)
        manifest = SuiteManifest.model_validate_json((tmp / SUITE_MANIFEST_NAME).read_text())
        probs = suite_problems(manifest, tmp)
        if probs:
            print("suite invalid:\n  " + "\n  ".join(probs))
            return 1
    if check:
        have = {str(p.relative_to(OUT)): p.read_text() for p in OUT.rglob("*") if p.is_file()}
        if have != files:
            drift = sorted(set(have) ^ set(files)) + sorted(
                k for k in set(have) & set(files) if have[k] != files[k])
            print("suite drift:", drift[:20])
            return 1
        print(f"{OUT.name} matches the generators ({len(files)} files)")
        return 0
    write(OUT, files)
    print(f"wrote {len(files)} files to {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main("--check" in sys.argv))
