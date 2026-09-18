"""
Run with:  pytest -q          (from the repo root)
or:        python -m pytest -q tests/test_matchers.py -v

Unit tests pin down specific expected behaviours (including known weaknesses,
e.g. phonetic matcher failing on bare initials -- that's asserted on purpose,
not a bug). The integration test runs the full labeled dataset through
main_pipeline.run_full_evaluation and asserts the hybrid matcher clears a
minimum bar, so a regression in any algorithms/*.py file or normalize.py
fails CI, not just a human eyeballing a printout.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from algorithms.exact_match import ExactNormalizedMatcher
from algorithms.fuzzy_match import TokenFuzzyMatcher
from algorithms.phonetic_match import PhoneticMatcher
from algorithms.hybrid_match import HybridRuleMatcher
from main_pipeline import run_full_evaluation, threshold_sweep


# ---------------------------------------------------------------------------
# ExactNormalizedMatcher
# ---------------------------------------------------------------------------

def test_exact_matches_identical_after_normalization():
    m = ExactNormalizedMatcher()
    assert m.match("Suresh Kumar", "suresh   kumar").is_match
    assert m.match("Shri Ramesh Kumar", "Ramesh Kumar").is_match  # honorific stripped
    assert m.match("Sharma Rakesh", "Rakesh Sharma").is_match  # order-independent


def test_exact_rejects_initials():
    m = ExactNormalizedMatcher()
    assert not m.match("S. Kumar", "Suresh Kumar").is_match  # known limitation


def test_exact_rejects_different_people():
    m = ExactNormalizedMatcher()
    assert not m.match("Rajesh Kumar", "Ramesh Kumar").is_match


# ---------------------------------------------------------------------------
# TokenFuzzyMatcher
# ---------------------------------------------------------------------------

def test_fuzzy_handles_typos():
    m = TokenFuzzyMatcher()
    assert m.match("Sushma Reddy", "Sushama Reddy").is_match


def test_fuzzy_struggles_with_bare_initials():
    m = TokenFuzzyMatcher()
    # documented weakness: too little character overlap to clear the threshold
    assert not m.match("S. Kumar", "Suresh Kumar").is_match


# ---------------------------------------------------------------------------
# PhoneticMatcher
# ---------------------------------------------------------------------------

def test_phonetic_handles_transliteration():
    m = PhoneticMatcher()
    assert m.match("Mohammed Farooq", "Muhammad Farooq").is_match
    assert m.match("Sunita Kumari", "Suneeta Kumari").is_match


def test_phonetic_known_weakness_lakshmi_laxmi():
    m = PhoneticMatcher()
    # documented limitation: NYSIIS codes "Lakshmi" and "Laxmi" differently
    # (LACSN vs LAXN) -- see NOTES.md "proudest edge case". 3 of 14 TRANSLIT
    # pairs in the dataset fail this way; token_fuzzy and hybrid_rule both
    # catch this one via edit-distance instead.
    result = m.match("Lakshmi Devi", "Laxmi Devi")
    assert not result.is_match


def test_phonetic_fails_on_bare_initials():
    m = PhoneticMatcher()
    # a single letter has no usable phonetic code -- documented weakness
    assert not m.match("S. Kumar", "Suresh Kumar").is_match


# ---------------------------------------------------------------------------
# HybridRuleMatcher
# ---------------------------------------------------------------------------

def test_hybrid_handles_initials():
    m = HybridRuleMatcher()
    assert m.match("S. Kumar", "Suresh Kumar").is_match


def test_hybrid_handles_transliteration():
    m = HybridRuleMatcher()
    assert m.match("Mohammed Farooq", "Muhammad Farooq").is_match


def test_hybrid_handles_md_abbreviation():
    m = HybridRuleMatcher()
    # "Md"/"Mohd" is a name-prefix abbreviation for "Mohammed" on South Asian
    # Muslim ID documents, not a "Doctor of Medicine" suffix -- canonicalized
    # in normalize.py, so every matcher benefits from this, not just hybrid.
    assert m.match("Md. Rafiqul Islam", "Mohammed Rafiqul Islam").is_match
    assert ExactNormalizedMatcher().match("Md. Rafiqul Islam", "Mohammed Rafiqul Islam").is_match


def test_hybrid_handles_reordering_and_honorifics():
    m = HybridRuleMatcher()
    assert m.match("Shri Ramesh Kumar", "Kumar Ramesh").is_match


def test_hybrid_rejects_siblings_sharing_surname():
    m = HybridRuleMatcher()
    assert not m.match("Vikram Malhotra", "Vikas Malhotra").is_match


def test_hybrid_rejects_common_surname_different_given_name():
    m = HybridRuleMatcher()
    assert not m.match("Suman Sharma", "Seema Sharma").is_match


def test_hybrid_known_weakness_rajesh_ramesh():
    m = HybridRuleMatcher()
    # documented limitation: rapidfuzz.ratio("rajesh","ramesh") = 83, clearing
    # the >=80 typo-tolerance rule, so this common-surname negative pair is
    # incorrectly accepted. This is the single COMMON_SURNAME false accept
    # in the full dataset -- see NOTES.md "if I had another day".
    result = m.match("Rajesh Kumar", "Ramesh Kumar")
    assert result.is_match  # documents the known false accept, not desired behaviour


def test_hybrid_handles_dropped_middle_name():
    m = HybridRuleMatcher()
    # Fixed via the whole-string fallback: token counts differ (3 vs 2), so
    # the despaced whole-string ratio (0.80) is used instead of the raw
    # token-alignment score (0.67), which correctly clears the threshold.
    # One residual case is NOT fixed by this -- see
    # test_hybrid_residual_weakness_large_dropped_token below.
    result = m.match("Anil Kumar Sharma", "Anil Sharma")
    assert result.is_match


def test_hybrid_residual_weakness_large_dropped_token():
    m = HybridRuleMatcher()
    # documented residual limitation (see NOTES.md): when the dropped token
    # is large relative to the whole name, even the whole-string fallback
    # ratio stays below threshold. 1 of 14 MIDDLE-category pairs still fails
    # this way.
    result = m.match("Geeta D/O Mohan Kumari", "Geeta Kumari")
    assert not result.is_match


def test_hybrid_handles_segmentation_mismatch():
    m = HybridRuleMatcher()
    # user-contributed real example: same compound name, split into a
    # different number of words across documents
    assert m.match("Seethamahalakshmi", "Seeta maha laxmi").is_match
    assert m.match("Srinuvasarao", "Srinuvas Rao").is_match


def test_hybrid_handles_truncated_name():
    m = HybridRuleMatcher()
    # Aadhaar-style field truncation, cut off mid-word
    assert m.match("Seethamahalakshmi Devi", "SEETHAMAHALAKSHM").is_match


def test_hybrid_does_not_accept_over_truncated_name():
    m = HybridRuleMatcher()
    # too little signal left to trust -- correctly stays a non-match
    assert not m.match("Suresh Kumar", "SURES").is_match


def test_hybrid_still_rejects_hard_negatives_after_fallback_added():
    m = HybridRuleMatcher()
    # regression guard: the whole-string fallback must not have reopened
    # any of the hard-negative categories it wasn't meant to touch
    assert not m.match("Rohan S/O Manoj Sharma", "Rohit S/O Manoj Sharma").is_match
    assert not m.match("Suman Sharma", "Seema Sharma").is_match


# ---------------------------------------------------------------------------
# Full-dataset integration test
# ---------------------------------------------------------------------------

def test_full_dataset_hybrid_clears_minimum_bar():
    all_metrics, rows, _, _ = run_full_evaluation(verbose=False)
    assert len(rows) >= 100, "dataset must have 100+ labeled pairs per the brief"
    hybrid = all_metrics["hybrid_rule"]
    assert hybrid["accuracy"] >= 0.80
    assert hybrid["false_accept_rate"] <= 0.20, "false accepts are the costly error in KYC"


def test_threshold_sweep_runs_without_error():
    threshold_sweep(verbose=False)
    assert os.path.exists(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results", "threshold_sweep.csv")
    )
