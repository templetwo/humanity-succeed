"""Inter-rater agreement statistics for semantic commissioning (docs/WP3_DESIGN.md).

Semantic commissioning itself stays ``pending_no_human_reviews`` (no human reviewers exist yet);
these statistics are implemented and tested on synthetic ratings only. Two raters, each rating the
same ordered list of items with a label from a closed vocabulary or ``None`` for "not yet reviewed".
"""

from __future__ import annotations

from ..review.identity import same_reviewer


def agreement(a: list[str | None], b: list[str | None], labels: list[str]) -> dict:
    """Raw agreement, confusion matrix, pooled prevalence and Cohen's kappa for two raters.

    ``a`` and ``b`` must be the same length (one rating per item, ``None`` for a missing review).
    Every non-``None`` rating must be one of ``labels``, or this raises ``ValueError``.

    ``missing`` counts items (not proportions): ``a``/``b`` count how many items that rater left
    unrated, ``either`` counts items missing from at least one rater (so it is not simply the sum).

    ``prevalence`` pools both raters' ratings over the paired (both-rated) items: for each label,
    the proportion of the ``2 * n_paired`` individual ratings -- rater a's and rater b's together --
    that used it.

    ``cohen_kappa`` uses each rater's own marginal distribution over the paired items (the standard
    definition), which is a different quantity from the pooled ``prevalence`` above. It is ``None``
    (with a reason) when there are no paired items, or when the expected chance agreement is 1 (no
    variability for kappa to explain against).
    """
    if len(a) != len(b):
        raise ValueError(f"a and b must have equal length: {len(a)} != {len(b)}")
    label_set = set(labels)
    for name, ratings in (("a", a), ("b", b)):
        for v in ratings:
            if v is not None and v not in label_set:
                raise ValueError(f"rating {v!r} in {name} is not one of labels {labels!r}")

    n_items = len(a)
    missing_a = sum(1 for x in a if x is None)
    missing_b = sum(1 for x in b if x is None)
    missing_either = sum(1 for x, y in zip(a, b, strict=True) if x is None or y is None)
    paired = [(x, y) for x, y in zip(a, b, strict=True) if x is not None and y is not None]
    n_paired = len(paired)

    confusion_matrix = {la: {lb: 0 for lb in labels} for la in labels}
    for x, y in paired:
        confusion_matrix[x][y] += 1

    raw_agreement = (sum(1 for x, y in paired if x == y) / n_paired) if n_paired else None

    if n_paired:
        pooled = {lbl: 0 for lbl in labels}
        for x, y in paired:
            pooled[x] += 1
            pooled[y] += 1
        prevalence = {lbl: pooled[lbl] / (2 * n_paired) for lbl in labels}
    else:
        prevalence = {lbl: None for lbl in labels}

    cohen_kappa: float | None = None
    kappa_undefined_reason: str | None = None
    if n_paired == 0:
        kappa_undefined_reason = "no paired ratings (n_paired == 0)"
    else:
        row_marginal = {lbl: sum(confusion_matrix[lbl].values()) / n_paired for lbl in labels}
        col_marginal = {
            lbl: sum(confusion_matrix[la][lbl] for la in labels) / n_paired for lbl in labels
        }
        expected_agreement = sum(row_marginal[lbl] * col_marginal[lbl] for lbl in labels)
        if expected_agreement == 1:
            kappa_undefined_reason = "expected chance agreement is 1 (no variability to explain)"
        else:
            cohen_kappa = (raw_agreement - expected_agreement) / (1 - expected_agreement)

    return {
        "n_items": n_items,
        "n_paired": n_paired,
        "missing": {"a": missing_a, "b": missing_b, "either": missing_either},
        "raw_agreement": raw_agreement,
        "confusion_matrix": confusion_matrix,
        "prevalence": prevalence,
        "cohen_kappa": cohen_kappa,
        "kappa_undefined_reason": kappa_undefined_reason,
    }


def agreement_between_reviewers(
    ref_a: str,
    ratings_a: list[str | None],
    ref_b: str,
    ratings_b: list[str | None],
    labels: list[str],
) -> dict:
    """``agreement()`` bound to reviewer identity (DECISIONS B60/B61, ruling 06d942da).

    Refuses to compute a statistic when there is no second, distinct human reviewer: an empty
    ``reviewer_ref`` is refused outright, ``ref_a == ref_b`` is refused because one person rating
    the same items twice is a revision, never a second reviewer (B61), and two references that are
    the same reviewer once case, whitespace and Unicode form are normalised
    (``review/identity.py``) are refused for the same reason. The math itself is unchanged: on
    success this returns exactly ``agreement(ratings_a, ratings_b, labels)`` with a
    ``"reviewers": [ref_a, ref_b]`` key added.
    """
    if not ref_a or not ref_b:
        raise ValueError(
            "agreement_between_reviewers requires a non-empty reviewer_ref for both reviewers"
        )
    if ref_a == ref_b:
        raise ValueError(
            f"agreement_between_reviewers refuses equal reviewer_ref {ref_a!r}: one reviewer "
            "rating the same items twice is a revision, not a second independent reviewer (B61)"
        )
    if same_reviewer(ref_a, ref_b):
        raise ValueError(
            f"agreement_between_reviewers refuses reviewer_ref {ref_a!r} and {ref_b!r}: they name "
            "the same reviewer once case, whitespace and Unicode form are normalised; one reviewer "
            "is never two (B61)"
        )
    result = agreement(ratings_a, ratings_b, labels)
    return {**result, "reviewers": [ref_a, ref_b]}


__all__ = ["agreement", "agreement_between_reviewers"]
