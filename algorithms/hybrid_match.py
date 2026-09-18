"""Algorithm 4: domain-tuned hybrid ensemble -- the recommended matcher."""
import jellyfish
from rapidfuzz import fuzz

from algorithms.base import BaseMatcher, MatchResult
from normalize import normalize_name


class HybridRuleMatcher(BaseMatcher):
    """Domain-tuned ensemble, built specifically for KYC name-pair noise.

    Aligns tokens between the two names (order-independent, one-to-one) using
    the best of four token-pair rules, then scores the alignment as a whole:

      - exact token match                          -> 1.00
      - one token is a single initial that matches
        the other token's first letter             -> 0.90  (S. -> Suresh)
      - same NYSIIS phonetic code                   -> 0.85  (Mohammed/Mohammad)
      - rapidfuzz ratio >= 80                        -> ratio/100  (typos)
      - otherwise                                    -> 0.00

    Overall score = sum(best pair scores, greedy 1-to-1 assignment) / max(len_a, len_b).

    The denominator is the key design choice: a genuinely mismatched token (a
    different given name behind a shared surname, e.g. siblings) scores 0 and
    pulls the average down, which is what lets this approach reject hard
    negatives that pure token-overlap methods (fuzzy, phonetic) wave through.

    Whole-string fallback (only when token counts differ): if the two names
    split into a different number of tokens -- one document writes a
    compound name as one fused word, another splits it into two or three
    ("Seethamahalakshmi" vs "Seeta Maha Laxmi"), or a field got truncated
    ("...DEVI" cut off mid-word) -- token-by-token alignment breaks down
    regardless of how good the per-token rule is. In that specific situation
    only, this also checks the two names concatenated with spaces removed,
    compared as one string via rapidfuzz.ratio, and takes whichever score is
    higher. This is gated strictly on "token counts differ" because that
    condition holds for 0 of the non-match pairs in the evaluation dataset,
    but for every segmentation/truncation case -- i.e. it's a signal that's
    only trustworthy in the specific situation it's meant for.

    Known residual weaknesses (see NOTES.md for full detail and rejected
    fixes): the fuzzy-ratio rule can't distinguish a typo of the same name
    from a different name one edit away (e.g. "Rajesh"/"Ramesh" wrongly
    accepted); and the whole-string fallback doesn't fire when truncation
    happens mid-token rather than dropping a whole word (token counts stay
    equal).
    """

    name = "hybrid_rule"

    def __init__(self, threshold: float = 0.75):
        self.threshold = threshold

    @staticmethod
    def _pair_score(a: str, b: str) -> float:
        if a == b:
            return 1.0
        if len(a) == 1 or len(b) == 1:
            short, long_ = (a, b) if len(a) == 1 else (b, a)
            if long_.startswith(short):
                return 0.90
        if len(a) > 1 and len(b) > 1 and jellyfish.nysiis(a) == jellyfish.nysiis(b):
            return 0.85
        ratio = fuzz.ratio(a, b)
        if ratio >= 80:
            return ratio / 100.0
        return 0.0

    def match(self, name_a, name_b):
        ta = normalize_name(name_a)
        tb = normalize_name(name_b)
        if not ta or not tb:
            return MatchResult(False, 0.0, "empty")

        remaining_b = list(tb)
        pair_scores = []
        for a in ta:
            best_score, best_idx = 0.0, -1
            for i, b in enumerate(remaining_b):
                s = self._pair_score(a, b)
                if s > best_score:
                    best_score, best_idx = s, i
            pair_scores.append(best_score)
            if best_idx >= 0:
                remaining_b.pop(best_idx)

        denom = max(len(ta), len(tb))
        overall = sum(pair_scores) / denom if denom else 0.0
        detail = f"pairs={[round(s, 2) for s in pair_scores]} denom={denom}"

        if len(ta) != len(tb):
            concat_ratio = fuzz.ratio("".join(ta), "".join(tb)) / 100.0
            if concat_ratio > overall:
                overall = concat_ratio
                detail += f" | whole_string_ratio={concat_ratio:.2f} (token counts differ, used as fallback)"

        return MatchResult(overall >= self.threshold, overall, detail)
