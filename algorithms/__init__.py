"""Exposes every implemented matching algorithm through one function."""
from algorithms.exact_match import ExactNormalizedMatcher
from algorithms.fuzzy_match import TokenFuzzyMatcher
from algorithms.phonetic_match import PhoneticMatcher
from algorithms.hybrid_match import HybridRuleMatcher


def get_all_matchers():
    """Fresh matcher instances (avoids any shared mutable state across runs)."""
    return [
        ExactNormalizedMatcher(),
        TokenFuzzyMatcher(),
        PhoneticMatcher(),
        HybridRuleMatcher(),
    ]
