"""Algorithm 2: Levenshtein-style fuzzy matcher (rapidfuzz token_sort_ratio)."""
from rapidfuzz import fuzz

from algorithms.base import BaseMatcher, MatchResult
from normalize import normalized_string


class TokenFuzzyMatcher(BaseMatcher):
    """Levenshtein-style fuzzy matcher (rapidfuzz token_sort_ratio).

    Handles: everything the baseline handles, plus typos and minor spelling drift.
    Misses: single-letter initials (too little character overlap to score high),
    and phonetic-only transliteration variants whose edit distance is large
    relative to name length.
    Chosen as the standard "off-the-shelf fuzzy matching" approach most teams
    reach for first -- useful to show what it does and doesn't buy you over the
    baseline.
    """

    name = "token_fuzzy"

    def __init__(self, threshold: float = 82.0):
        self.threshold = threshold

    def match(self, name_a, name_b):
        a = normalized_string(name_a)
        b = normalized_string(name_b)
        if not a or not b:
            return MatchResult(False, 0.0, "empty")
        score = fuzz.token_sort_ratio(a, b)
        return MatchResult(score >= self.threshold, score / 100.0, f"token_sort_ratio={score:.1f}")
