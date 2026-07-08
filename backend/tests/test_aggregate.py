from datetime import date

import pytest

from riivault.collector.aggregate import aggregate_mentions, aggregate_sentiments

D = date(2026, 7, 1)


def test_aggregate_mentions_groups_and_overall_row():
    events = [
        {"day": D, "entity_id": 1, "subreddit": "SaaS", "author_hash": "a",
         "score": 10, "upvote_ratio": 0.9, "num_comments": 3},
        {"day": D, "entity_id": 1, "subreddit": "SaaS", "author_hash": "a",
         "score": 5, "upvote_ratio": 0.7, "num_comments": 1},
        {"day": D, "entity_id": 1, "subreddit": "webdev", "author_hash": "b",
         "score": 2, "upvote_ratio": None, "num_comments": 0},
    ]
    by_key = {
        (r["day"], r["entity_id"], r["subreddit"]): r
        for r in aggregate_mentions(events)
    }

    saas = by_key[(D, 1, "SaaS")]
    assert saas["mention_count"] == 2
    assert saas["unique_authors"] == 1  # same author twice
    assert saas["score_sum"] == 15
    assert saas["comment_sum"] == 4
    assert saas["upvote_ratio_avg"] == pytest.approx(0.8)

    overall = by_key[(D, 1, "")]
    assert overall["mention_count"] == 3
    assert overall["unique_authors"] == 2
    assert overall["score_sum"] == 17
    assert overall["comment_sum"] == 4
    assert overall["upvote_ratio_avg"] == pytest.approx(0.8)  # None ignored


def test_aggregate_mentions_no_overall_dupe_when_only_blank_subreddit():
    events = [
        {"day": D, "entity_id": 9, "subreddit": "", "author_hash": "z",
         "score": 1, "upvote_ratio": None, "num_comments": 0},
    ]
    rows = aggregate_mentions(events)
    assert len(rows) == 1
    assert rows[0]["subreddit"] == ""
    assert rows[0]["mention_count"] == 1


def test_aggregate_sentiments_stats_and_ratios():
    events = [
        {"day": D, "entity_id": 1, "compound": 0.5},
        {"day": D, "entity_id": 1, "compound": -0.5},
        {"day": D, "entity_id": 1, "compound": 0.0},
    ]
    r = aggregate_sentiments(events)[0]
    assert r["sample_size"] == 3
    assert r["sentiment_mean"] == pytest.approx(0.0)
    assert r["pos_ratio"] == pytest.approx(1 / 3)
    assert r["neg_ratio"] == pytest.approx(1 / 3)
    assert r["neu_ratio"] == pytest.approx(1 / 3)
    assert r["sentiment_std"] == pytest.approx(((0.25 + 0.25 + 0.0) / 3) ** 0.5)


def test_aggregate_sentiments_threshold_bands():
    events = [
        {"day": D, "entity_id": 2, "compound": 0.05},   # pos
        {"day": D, "entity_id": 2, "compound": -0.05},  # neg
        {"day": D, "entity_id": 2, "compound": 0.04},   # neu
        {"day": D, "entity_id": 2, "compound": -0.04},  # neu
    ]
    r = aggregate_sentiments(events)[0]
    assert r["pos_ratio"] == pytest.approx(0.25)
    assert r["neg_ratio"] == pytest.approx(0.25)
    assert r["neu_ratio"] == pytest.approx(0.5)
