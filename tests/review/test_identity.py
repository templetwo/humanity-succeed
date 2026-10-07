"""review/identity.py: the comparison form of ``reviewer_ref`` behind the B61 distinct-reviewer check."""

from __future__ import annotations

import pytest

from humanity_succeed.review.identity import (
    canonical_reviewer_ref,
    is_tidy_reviewer_ref,
    same_reviewer,
)


@pytest.mark.parametrize("variant", ["anthony", "Anthony", "ANTHONY", "anthony ", " anthony", "\tanthony\n"])
def test_case_and_whitespace_variants_of_one_name_are_one_reviewer(variant):
    assert canonical_reviewer_ref(variant) == "anthony"
    assert same_reviewer(variant, "anthony")


def test_repeated_internal_whitespace_collapses():
    assert canonical_reviewer_ref("anthony   vasquez") == "anthony vasquez"
    assert same_reviewer("Anthony  Vasquez", "anthony vasquez")


def test_nfkc_folds_compatibility_characters():
    # a fullwidth Latin capital A is the same reviewer as the ASCII form after NFKC + casefold
    assert same_reviewer("Ａnthony", "anthony")


def test_genuinely_distinct_references_stay_distinct():
    assert not same_reviewer("anthony", "maria")
    assert not same_reviewer("anthony-vasquez-sr", "anthony-vasquez-jr")
    assert not same_reviewer("anthony vasquez", "anthonyvasquez")


@pytest.mark.parametrize("ref", ["anthony", "anthony-vasquez-sr", "A. Vasquez"])
def test_tidy_references_are_accepted(ref):
    assert is_tidy_reviewer_ref(ref)


@pytest.mark.parametrize("ref", ["", " anthony", "anthony ", "an  thony", "\tanthony", "anthony\n"])
def test_untidy_references_are_refused(ref):
    assert not is_tidy_reviewer_ref(ref)
