"""Algorithm 1: exact match after normalization -- the baseline."""
from algorithms.base import BaseMatcher, MatchResult
from normalize import normalize_name


class ExactNormalizedMatcher(BaseMatcher):
    """Baseline: normalize, drop honorifics, sort tokens, require exact equality.

    Handles: honorifics/suffixes, case/punctuation noise, given<->surname reordering.
    Misses: initials, spelling/transliteration variants, typos, missing middle names.
    Chosen as the baseline because it is what a naive "just clean up the string"
    implementation looks like, with no fuzzy logic at all -- it's the floor every
    other approach should beat.
    """

    name = "exact_normalized"

    def match(self, name_a, name_b):
        ta = sorted(normalize_name(name_a))
        tb = sorted(normalize_name(name_b))
        is_match = bool(ta) and ta == tb
        return MatchResult(is_match, 1.0 if is_match else 0.0, f"{ta} vs {tb}")
