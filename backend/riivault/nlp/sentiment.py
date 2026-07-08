"""Sentiment scoring via VADER. ``compound`` is already normalized to [-1, +1]."""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def _analyzer():
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    return SentimentIntensityAnalyzer()


def sentiment_compound(text: str | None) -> float:
    """Return VADER compound polarity in [-1.0, +1.0]. Empty text -> 0.0."""
    if not text or not text.strip():
        return 0.0
    return float(_analyzer().polarity_scores(text)["compound"])
