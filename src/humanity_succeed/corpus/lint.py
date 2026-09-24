"""Leak linting (BUILD_SPEC §4.3). Flags for review; never proof of no leakage.

- Four-word-or-longer phrase overlap between model-visible text (task, principles block, SFT target
  text) and evaluator-only prose (rubric instructions, scope limitations).
- Hidden labels (case/root/family IDs, split names, demo IDs, evaluator vocabulary) appearing in
  model-visible text.
Every flag starts with disposition ``unreviewed``. Shared concepts such as honesty are not
automatically prohibited; a reviewer decides.
"""

from __future__ import annotations

import re
from typing import Any

from ..contracts.case import SPLITS, CaseSource

EVALUATOR_VOCABULARY = ("pass_if", "fail_if", "counterexample", "human_rubric", "evaluator",
                        "expected_mechanical_outcome", "preferred trajectory", "holdback")


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def ngrams(text: str, n: int = 4) -> set[tuple[str, ...]]:
    w = _words(text)
    return {tuple(w[i:i + n]) for i in range(len(w) - n + 1)}


def extract_principles_text(markdown: str) -> str:
    """Model-visible part of configs/principles.draft.md (after the candidate heading)."""
    marker = "## Candidate model-visible text"
    if marker not in markdown:
        raise ValueError("principles file has no '## Candidate model-visible text' section")
    return markdown.split(marker, 1)[1].strip()


def _visible_texts(case: CaseSource, principles: str | None) -> list[tuple[str, str]]:
    out = [("subject.task", case.subject.task)]
    if principles:
        out.append(("principles", principles))
    for d in case.demonstrations:
        if d.training_role != "preferred":
            continue
        for i, env in enumerate(d.actions):
            a = env.action.model_dump(exclude_none=True)
            for k in ("text", "summary", "reason", "alternative", "question"):
                if isinstance(a.get(k), str):
                    out.append((f"demo:{d.demo_id}[{i}].{k}", a[k]))
            if env.message:
                out.append((f"demo:{d.demo_id}[{i}].message", env.message))
    return out


def _hidden_texts(case: CaseSource) -> list[tuple[str, str]]:
    out = [(f"rubric:{r.dimension}", r.instruction) for r in case.evaluation.human_rubric]
    out += [(f"scope_limitations[{i}]", s) for i, s in enumerate(case.evaluation.scope_limitations)]
    return out


def lint_case(case: CaseSource, principles: str | None = None) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    visible = _visible_texts(case, principles)
    hidden = _hidden_texts(case)
    for vsrc, vtext in visible:
        vg = ngrams(vtext)
        for hsrc, htext in hidden:
            common = sorted(vg & ngrams(htext))
            if common:
                flags.append({
                    "kind": "phrase_overlap_4gram",
                    "case_id": case.case_id,
                    "visible_source": vsrc,
                    "hidden_source": hsrc,
                    "phrases": [" ".join(g) for g in common],
                    "disposition": "unreviewed",
                })
    labels = {
        case.case_id: "case_id",
        case.root_scenario_id: "root_scenario_id",
        case.family_id: "family_id",
        **{d.demo_id: "demo_id" for d in case.demonstrations},
        **{s: "split_name" for s in SPLITS},
        **{v: "evaluator_vocabulary" for v in EVALUATOR_VOCABULARY},
    }
    for vsrc, vtext in visible:
        low = vtext.lower()
        for label, kind in labels.items():
            if re.search(rf"(?<![a-z0-9]){re.escape(label.lower())}(?![a-z0-9])", low):
                flags.append({
                    "kind": f"hidden_label_in_visible_text:{kind}",
                    "case_id": case.case_id,
                    "visible_source": vsrc,
                    "label": label,
                    "disposition": "unreviewed",
                })
    return flags


def find_canaries(data: bytes, canaries: list[str]) -> list[str]:
    return [c for c in canaries if c.encode("utf-8") in data]
