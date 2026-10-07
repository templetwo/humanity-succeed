"""review/identity.py: the comparison form of ``reviewer_ref`` behind the B61 distinct-reviewer check."""

from __future__ import annotations

import pytest

from humanity_succeed.review.identity import (
    canonical_reviewer_ref,
    is_tidy_reviewer_ref,
    reviewer_ref_problem,
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


@pytest.mark.parametrize("ref", ["anthony", "anthony-vasquez-sr", "A. Vasquez", "reviewer_2"])
def test_plain_ascii_references_have_no_problem(ref):
    assert reviewer_ref_problem(ref) is None


@pytest.mark.parametrize("ref", ["\u0430nthony", "anth\u200dony", "\uff21nthony", "ant\u00f3n"])
def test_lookalike_and_non_ascii_references_are_named_as_problems(ref):
    problem = reviewer_ref_problem(ref)
    assert problem is not None and "outside ASCII" in problem and "U+" in problem


def test_non_breaking_space_is_refused_as_whitespace():
    # str.split treats U+00A0 as whitespace, so the tidy rule catches it first; refused either way
    problem = reviewer_ref_problem("anthony\u00a0vasquez")
    assert problem is not None and "whitespace" in problem


def test_untidy_reference_problem_is_the_whitespace_message():
    assert "whitespace" in reviewer_ref_problem("anthony ")
