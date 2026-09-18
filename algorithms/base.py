"""Shared base class + result type used by every matcher in algorithms/."""
from dataclasses import dataclass


@dataclass
class MatchResult:
    is_match: bool
    score: float
    detail: str = ""


class BaseMatcher:
    name = "base"

    def match(self, name_a: str, name_b: str) -> MatchResult:
        raise NotImplementedError
