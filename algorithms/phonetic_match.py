"""Algorithm 3: token-level phonetic matcher using NYSIIS codes (jellyfish)."""
import jellyfish

from algorithms.base import BaseMatcher, MatchResult
from normalize import normalize_name


class PhoneticMatcher(BaseMatcher):
    """Token-level phonetic matcher using NYSIIS codes (jellyfish).

    Handles: transliteration/spelling variants (Mohammed/Mohammad/Muhammad,
    Lakshmi/Laxmi), given<->surname reordering (compared as a set of codes).
    Misses: initials (a single letter has no meaningful phonetic code), and
    risks false positives on genuinely different names that sound alike.

    Tested against several alternatives (Soundex, Metaphone, DoubleMetaphone,
    MRA, Caverphone, BeiderMorse) -- all share the same structural blind spot:
    they are consonant-centric and largely vowel-blind, so names that differ
    only in a vowel (e.g. "Karan"/"Kiran", "Sana"/"Saina") collapse to the
    same code even when a human clearly hears the difference. See NOTES.md.
    """

    name = "phonetic"

    def __init__(self, overlap_threshold: float = 0.8):
        self.overlap_threshold = overlap_threshold

    def _codes(self, name):
        tokens = normalize_name(name)
        return {jellyfish.nysiis(t) for t in tokens if len(t) > 1}

    def match(self, name_a, name_b):
        ca = self._codes(name_a)
        cb = self._codes(name_b)
        if not ca or not cb:
            return MatchResult(False, 0.0, "empty token set (all-initials or blank name)")
        overlap = len(ca & cb) / max(len(ca), len(cb))
        return MatchResult(overlap >= self.overlap_threshold, overlap, f"{ca} vs {cb}")
