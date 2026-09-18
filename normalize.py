"""Normalization utilities shared by all matchers.

Design note: every matcher works off the SAME normalized tokens, so any
difference in matcher behaviour is due to the matching logic itself, not
inconsistent preprocessing.
"""
import re

# Honorifics / suffixes commonly seen on Indian identity & KYC documents.
# These carry no identity information and are stripped before comparison.
HONORIFICS = {
    "mr", "mrs", "ms", "miss", "dr", "prof",
    "shri", "shree", "sri", "smt", "smti",
    "kumari", "km", "jr", "sr", "late", "er",
    "bhai", "ben",  # common Gujarati name suffixes
}

# "Md" / "Mohd" are near-universal abbreviations for "Mohammed" as a name
# PREFIX in South Asian Muslim names (e.g. "Md. Rafiqul Islam"), not the
# "Doctor of Medicine" suffix -- that reading is far more common on identity
# documents in this context. Canonicalize to "mohammed" so it aligns with
# however the other document spelled it out in full; the matchers already
# know how to reconcile "mohammed"/"mohammad"/"muhammad" spelling variants.
_ABBREVIATION_MAP = {"md": "mohammed", "mohd": "mohammed"}

# S/O, D/O, W/O, C/O = son/daughter/wife/care of. Must be stripped as a whole
# pattern BEFORE generic tokenization, otherwise a bare "s" or "o" token can't
# be told apart from a genuine single-letter initial (e.g. "S. Kumar").
_RELATIONAL_PARTICLE = re.compile(r"\b[sdwc]\s*/\s*o\b", re.IGNORECASE)


def normalize_name(name: str):
    """Lowercase, strip punctuation, tokenize, drop honorifics.

    Relational particles ("S/O" etc.) are removed as an exact pattern; the
    father's/husband's name that follows them is normalized like any other
    token -- deciding whether it should count towards a match is a job for
    the matchers, not this function.
    """
    s = name.lower()
    s = _RELATIONAL_PARTICLE.sub(" ", s)
    s = re.sub(r"[^a-z\s]", " ", s)  # drop remaining punctuation & digits
    tokens = s.split()
    tokens = [_ABBREVIATION_MAP.get(t, t) for t in tokens]
    tokens = [t for t in tokens if t not in HONORIFICS]
    return tokens


def normalized_string(name: str) -> str:
    return " ".join(normalize_name(name))
