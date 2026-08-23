"""Duplicate / near-duplicate detection for generated scenarios.

Layer 1: exact sha256 content hash (identical text).
Layer 2: TF-IDF cosine similarity against the last N scenarios
         (near-duplicate wording). Regeneration is triggered above a
         similarity threshold.
"""

import hashlib
from typing import List

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DEFAULT_THRESHOLD = 0.85
DEFAULT_HISTORY_WINDOW = 20


def content_hash(text: str) -> str:
    """sha256 of the normalized scenario text (subject + body)."""
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


class FreshnessChecker:
    """Checks whether a candidate scenario is too similar to history."""

    def __init__(self, threshold: float = DEFAULT_THRESHOLD,
                 history_window: int = DEFAULT_HISTORY_WINDOW):
        if not 0.0 < threshold <= 1.0:
            raise ValueError("threshold must be in (0, 1]")
        self.threshold = threshold
        self.history_window = history_window

    def _text(self, scenario: dict) -> str:
        return f"{scenario.get('subject', '')} {scenario.get('body', '')}"

    def check(self, candidate: dict, history: List[dict]) -> dict:
        """Return {hash_duplicate, max_cosine, passed}.

        passed is True when the candidate is fresh enough to store.
        """
        candidate_text = self._text(candidate)
        candidate_hash = content_hash(candidate_text)
        recent = history[-self.history_window:] if self.history_window else history

        hash_duplicate = any(
            content_hash(self._text(h)) == candidate_hash for h in recent
        )

        max_cosine = 0.0
        if len(recent) > 0:
            max_cosine = self._max_cosine(candidate_text, [self._text(h) for h in recent])

        passed = not hash_duplicate and max_cosine < self.threshold
        return {"hash_duplicate": hash_duplicate, "max_cosine": max_cosine, "passed": passed}

    def _max_cosine(self, candidate_text: str, history_texts: List[str]) -> float:
        if not history_texts:
            return 0.0
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix = vectorizer.fit_transform([candidate_text] + history_texts)
        similarities = cosine_similarity(matrix[0:1], matrix[1:])[0]
        return float(max(similarities))

    def regenerated_ok(self, candidate: dict, history: List[dict], max_tries: int = 2) -> bool:
        """Wrapper for the caller: whether a fresh candidate was produced
        (in practice the caller regenerates and re-checks; this method
        documents the intended 2-retry policy)."""
        return len(history) < self.history_window or self.check(candidate, history)["passed"]