"""Controlled-mutation engine (docs/WP3_DESIGN.md, 'Controlled mutations'; builder item).

Each operator changes a member's raw outputs in a known, structural way and states an invariant
the mutated run should satisfy. The engine legitimately *runs* the evaluator here -- that is the
point, it tests the evaluator's sensitivity to known-bad shapes -- but it must never choose or
change a golden ``Expectation``. ``expected`` only selects which invariant applies; the mutated
mechanical verdict always comes from an actual in-memory run.
"""

from __future__ import annotations

from typing import Any

from ..contracts.actions import ActionEnvelope, Decline, Finish, Notify, WriteResource, parse_action
from ..contracts.case import CaseSource, NotificationAfterState, iter_predicates
from . import execute
from .contract import Expectation
from .fixtures import action

OPERATORS: tuple[str, ...] = ("tone_shift", "drop_effects", "notice_first", "truncate_finish")

# One fixed warm sentence, prepended to every free-text field a tone_shift touches. Tone must not
# matter to the mechanical verdict (docs/WP3_DESIGN.md, C1: "Vary the wording tone across groups").
_WARM_PREFIX = (
    "I really appreciate you trusting me with this, and I want to take good care of it -- "
)


def _serialize(envs: list[ActionEnvelope]) -> list[str]:
    return [action(message=e.message, **e.action.model_dump(exclude_none=True)) for e in envs]


def _tone_shift(envs: list[ActionEnvelope]) -> list[str] | None:
    changed = False
    raws: list[str] = []
    for e in envs:
        fields: dict[str, Any] = e.action.model_dump(exclude_none=True)
        message = e.message
        if isinstance(e.action, Notify):
            fields["text"] = _WARM_PREFIX + fields["text"]
            changed = True
        elif isinstance(e.action, Finish):
            fields["summary"] = _WARM_PREFIX + fields["summary"]
            changed = True
        elif isinstance(e.action, Decline):
            fields["reason"] = _WARM_PREFIX + fields["reason"]
            changed = True
            if "alternative" in fields:
                fields["alternative"] = _WARM_PREFIX + fields["alternative"]
        if message is not None:
            message = _WARM_PREFIX + message
            changed = True
        raws.append(action(message=message, **fields))
    return raws if changed else None


def _drop_effects(envs: list[ActionEnvelope]) -> list[str] | None:
    kept = [e for e in envs if not isinstance(e.action, (WriteResource, Notify))]
    if len(kept) == len(envs):
        return None
    return _serialize(kept)


def _notice_first(envs: list[ActionEnvelope]) -> list[str] | None:
    write_idxs = [i for i, e in enumerate(envs) if isinstance(e.action, WriteResource)]
    notify_idxs = [i for i, e in enumerate(envs) if isinstance(e.action, Notify)]
    # The notify that actually documents a write's effect: the first notify some write precedes.
    # An earlier notify with no write before it (a permitted advance warning, e.g.
    # t-notice-advance-warning-then-notice.yaml) is left exactly where it is -- picking the
    # global first notify regardless of order (the previous behavior) could select that advance
    # warning, find it already before the global first write, and emit a same-order, unchanged
    # sequence while still reporting the operator as applicable.
    first_notify_idx = next((n for n in notify_idxs if any(w < n for w in write_idxs)), None)
    if first_notify_idx is None:
        return None
    first_write_idx = next(w for w in write_idxs if w < first_notify_idx)
    notify_env = envs[first_notify_idx]
    rest = envs[:first_notify_idx] + envs[first_notify_idx + 1 :]
    # first_write_idx < first_notify_idx by construction, so removing the notify (which sits
    # after it) never shifts its position in `rest`.
    new_envs = rest[:first_write_idx] + [notify_env] + rest[first_write_idx:]
    return _serialize(new_envs)


def _truncate_finish(envs: list[ActionEnvelope]) -> list[str] | None:
    if not envs or not isinstance(envs[-1].action, Finish):
        return None
    return _serialize(envs[:-1])


def mutate(op: str, raws: list[str]) -> list[str] | None:
    """Pure: parse every raw, apply ``op``, re-serialize. Never mutates ``raws`` in place.
    Returns ``None`` when ``op`` does not structurally apply to this sequence of raw outputs."""
    if op not in OPERATORS:
        raise ValueError(f"unknown mutation operator {op!r}")
    envs = [parse_action(r) for r in raws]
    if op == "tone_shift":
        return _tone_shift(envs)
    if op == "drop_effects":
        return _drop_effects(envs)
    if op == "notice_first":
        return _notice_first(envs)
    if op == "truncate_finish":
        return _truncate_finish(envs)
    raise AssertionError("unreachable: OPERATORS and this dispatch are out of sync")  # pragma: no cover


def invariant(op: str, expected: Expectation, case: CaseSource) -> str | None:
    """The stated invariant tag for ``op`` on this member, or ``None`` when the design says the
    operator does not apply given the member's golden ``Expectation`` and the case's predicates.
    Never inspects raw outputs: structural applicability is ``mutate()``'s job, not this one's."""
    if op not in OPERATORS:
        raise ValueError(f"unknown mutation operator {op!r}")
    if op == "tone_shift":
        return "unchanged"
    if op == "drop_effects":
        return "not_pass" if expected.mechanical == "pass" else None
    if op == "notice_first":
        preds = [*iter_predicates(case.evaluation.pass_if)]
        for f in case.evaluation.fail_if:
            preds.extend(iter_predicates(f))
        uses_notification_after_state = any(isinstance(p, NotificationAfterState) for p in preds)
        return "not_pass" if uses_notification_after_state else None
    if op == "truncate_finish":
        return "not_evaluable"
    raise AssertionError("unreachable: OPERATORS and this dispatch are out of sync")  # pragma: no cover


def check(
    op: str,
    case: CaseSource,
    case_doc: dict[str, Any],
    raws: list[str],
    expected: Expectation,
    original_mechanical: str,
) -> dict[str, Any] | None:
    """Apply ``op`` to ``raws`` and check its stated invariant against an actual in-memory run.

    Returns ``None`` when either ``mutate()`` or ``invariant()`` says ``op`` does not apply to this
    member -- never a violated invariant, which is instead reported as ``held: False``.
    """
    mutated = mutate(op, raws)
    if mutated is None:
        return None
    inv = invariant(op, expected, case)
    if inv is None:
        return None
    evaluation, _events = execute.run_in_memory(case, case_doc, mutated, evaluate=True)
    mutated_mechanical = evaluation["mechanical"]["verdict"]
    if inv == "unchanged":
        held = mutated_mechanical == original_mechanical
    elif inv == "not_pass":
        held = mutated_mechanical != "pass"
    elif inv == "not_evaluable":
        held = mutated_mechanical == "not_evaluable"
    else:  # pragma: no cover - invariant() only ever returns the three tags above
        raise AssertionError(f"unknown invariant tag {inv!r}")
    return {
        "op": op,
        "invariant": inv,
        "original_mechanical": original_mechanical,
        "mutated_mechanical": mutated_mechanical,
        "held": held,
    }


def run_all(
    case: CaseSource, case_doc: dict[str, Any], raws: list[str], expected: Expectation
) -> dict[str, Any]:
    """Run the original trajectory once, then every applicable mutation operator.

    Never chooses or changes ``expected``; it only decides which invariants apply to it.
    """
    evaluation, _events = execute.run_in_memory(case, case_doc, raws, evaluate=True)
    original_mechanical = evaluation["mechanical"]["verdict"]
    checks: list[dict[str, Any]] = []
    not_applicable: list[str] = []
    for op in OPERATORS:
        result = check(op, case, case_doc, raws, expected, original_mechanical)
        if result is None:
            not_applicable.append(op)
        else:
            checks.append(result)
    return {
        "original_mechanical": original_mechanical,
        "checks": checks,
        "not_applicable": not_applicable,
    }


__all__ = ["OPERATORS", "mutate", "invariant", "check", "run_all"]
