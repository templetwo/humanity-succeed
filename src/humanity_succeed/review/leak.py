"""Leak scanning for blind review packet exports (BUILD_SPEC §11, §13 A19; DECISIONS B60/B61).

Two functions: the forbidden-token set a review export must contain zero occurrences of, and the
substring scan that checks serialized packet text against that set -- the same substring-match
precedent as ``corpus.lint.find_canaries``. Neither function proves the absence of a leak; both are
flags for the operator, same as the corpus lint's own stated limit.

Gap flagged to the lead: ``forbidden_tokens``'s signature in review/contract.py names a
``suite_manifest: SuiteManifest`` parameter, but ``export_packet(run_dir, out, *, state_root,
repo_root)`` has no path back to a real one. ``report.json`` stores only ``plan_sha256`` (a hash of
the plan document, not a path), and the plan that names the suite
(``docs/receipts/wp3/plan/plan.json``) is a sibling of ``run_dir`` chosen independently by the CLI
invocation (``docs/receipts/wp3/01_plan.cmd``, ``02_run.cmd``) -- nothing in ``run_dir`` points back
to it. Hardcoding a suite-root convention (e.g. ``cases/commissioning_suite_v1``) would only be
right for this one committed receipt, and a silently empty forbidden set would make "zero leak
hits" pass for the wrong reason. Rather than either, ``suite_manifest`` here is optional (``None``
when unreachable, as ``export_packet`` calls it today) and ``case_ids`` is an explicit keyword the
caller fills from each opened bundle's own ``case_source.json`` -- exactly "case ids (from the
bundles' case_source case_id)" as specified; ``report.json``'s own ``fixtures`` rows already carry
complete fixture/class/group ids, so nothing about those three is guessed. When a real
``SuiteManifest`` does become reachable, pass it: its groups' fixture/group/class ids are folded in
too, as a defense-in-depth cross-check against the values ``report.json`` already carries directly.

A second, narrower deviation, measured rather than assumed (see ``tests/review/test_export.py``):
a few of the vocabulary words below collide with ordinary, legitimate packet content once treated
as a bare substring. ``"expected"`` is a prefix of ``expected_revision``, a real field on every
visible ``write_resource`` proposal (BUILD_SPEC's own action contract); forbidding bare
``expected`` would flag every fixture that ever writes a resource. The predicate connectives
``all``/``any``/``not`` are also ordinary English words that appear in ordinary task prose.
``pending_review`` is a CSS class name inside ``evidence.replay._CSS`` itself (styling for that
report's own conduct-outcome spans, which ``review/html.py`` never emits but still inlines
verbatim per the fan-out brief) -- measured directly: exporting the real committed run with
``pending_review`` forbidden bare blocks on that stylesheet text alone, with nothing reviewer-facing
involved at all. All four are forbidden here in their JSON-key/value quoted form (``"expected"``,
``"not"``, ``"pending_review"``, ...) instead of bare: a literal leak of a report field or a
serialized predicate tree is always JSON-quoted (``"op":"not"``, ``"expected":{...}``), so the
quoted form still catches it, without flagging content that merely happens to contain the same
letters (or, for ``pending_review``, the same CSS selector this module was told to reuse).
"""

from __future__ import annotations

import typing
from collections.abc import Iterable
from typing import Any

from ..commissioning.contract import SuiteManifest
from ..contracts.case import Predicate

# Report/evaluator field names that must never reach a blind packet (BUILD_SPEC §11; A19).
_EVALUATOR_FIELD_NAMES = (
    "judgment_heavy",
    "expected",
    "conduct_outcome",
    "mechanical",
    "pass_if",
    "fail_if",
    "pending_review",
    "holdback_designate",
)
# Bare substrings that collide with legitimate visible content (see module docstring). Forbidden
# only in their quoted JSON-key/value form, never bare.
_QUOTE_ONLY = frozenset({"expected", "all", "any", "not", "pending_review"})


def _predicate_op_names() -> frozenset[str]:
    """Every discriminator value of ``contracts.case.Predicate``, read from the union itself so
    this can never silently drift from the actual predicate registry as it grows."""
    union = typing.get_args(Predicate)[0]
    names: set[str] = set()
    for cls in typing.get_args(union):
        field = cls.model_fields["op"]
        names.update(typing.get_args(field.annotation))
    return frozenset(names)


def forbidden_tokens(
    report: dict[str, Any],
    suite_manifest: SuiteManifest | None = None,
    *,
    case_ids: Iterable[str] = (),
) -> set[str]:
    """The token set a blind review export must contain zero occurrences of.

    Always includes every fixture/class/group id in ``report["fixtures"]`` (present for every row
    regardless of ``suite_manifest``), every id in ``case_ids`` (the caller's own opened-bundle
    ``case_source.json`` ``case_id`` values), the evaluator/report vocabulary words, and every
    registered predicate op name. See the module docstring for why ``suite_manifest`` is optional
    and why a few of the vocabulary words are represented in quoted form.
    """
    ids: set[str] = set()
    for row in report.get("fixtures") or []:
        for key in ("fixture_id", "class_id", "group_id"):
            value = row.get(key)
            if value:
                ids.add(str(value))
    ids.update(str(c) for c in case_ids if c)
    if suite_manifest is not None:
        for group in suite_manifest.groups:
            ids.add(group.group_id)
            ids.add(group.class_id)
            for member in group.members:
                ids.add(member.fixture_id)

    vocab = set(_EVALUATOR_FIELD_NAMES) | _predicate_op_names()
    bare = {v for v in vocab if v not in _QUOTE_ONLY}
    quoted = {f'"{v}"' for v in vocab if v in _QUOTE_ONLY}
    return ids | bare | quoted


def leak_check(text: str, forbidden: set[str]) -> list[str]:
    """Sorted substring hits of ``forbidden`` in ``text`` (corpus.lint.find_canaries' precedent
    applied to a str instead of bytes). Never proof of no leakage."""
    return sorted(token for token in forbidden if token in text)


__all__ = ["forbidden_tokens", "leak_check"]
