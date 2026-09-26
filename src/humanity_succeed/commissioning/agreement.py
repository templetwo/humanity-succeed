"""Inter-rater agreement statistics for semantic commissioning (docs/WP3_DESIGN.md).

Semantic commissioning itself stays ``pending_no_human_reviews`` (no human reviewers exist yet);
these statistics are implemented and tested on synthetic ratings only. Two raters, each rating the
same ordered list of items with a label from a closed vocabulary or ``None`` for "not yet reviewed".
"""

from __future__ import annotations


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


__all__ = ["agreement"]
