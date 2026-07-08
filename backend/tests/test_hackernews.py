from datetime import UTC, datetime

from riivault.collector.hackernews import _cursor_key, parse_hit
from riivault.collector.reddit import author_hash

STORY_HIT = {
    "objectID": "12345",
    "title": "Show HN: I built a Cursor competitor",
    "story_text": "It uses AI to edit your code inline.",
    "url": "https://example.com/launch",
    "author": "alice",
    "points": 42,
    "num_comments": 7,
    "created_at_i": 1700000000,
}

COMMENT_HIT = {
    "objectID": "999",
    "title": None,
    "story_title": "Ask HN: best editor?",
    "comment_text": "I switched to Notion last week and never looked back.",
    "author": "bob",
    "points": None,
    "created_at_i": 1699999999,
}


def test_parse_hit_story():
    hn_id, kind, ahash, title, body, url, points, num_comments, created = parse_hit(
        STORY_HIT, "story"
    )
    assert hn_id == "12345"
    assert kind == "story"
    assert title  # non-empty
    assert body  # story_text
    assert url == "https://example.com/launch"
    assert points == 42
    assert num_comments == 7
    assert isinstance(created, datetime)
    assert created == datetime.fromtimestamp(1700000000, tz=UTC)


def test_parse_hit_comment_has_no_title_and_uses_comment_text():
    hn_id, kind, ahash, title, body, url, points, num_comments, created = parse_hit(
        COMMENT_HIT, "comment"
    )
    assert kind == "comment"
    assert title is None
    assert body == "I switched to Notion last week and never looked back."
    assert points is None
    assert created == datetime.fromtimestamp(1699999999, tz=UTC)


def test_parse_hit_author_is_hashed_not_plaintext():
    ahash = parse_hit(STORY_HIT, "story")[2]
    assert ahash == author_hash("alice")
    assert ahash != "alice"
    assert len(ahash) == 64  # sha-256 hex digest


def test_parse_hit_missing_author_yields_none():
    hit = {"objectID": "1", "comment_text": "no author here", "created_at_i": 1700000000}
    assert parse_hit(hit, "comment")[2] is None


def test_cursor_key_namespaces_by_kind_and_term():
    assert _cursor_key("story", "Cursor AI") == "hn:story:Cursor AI"
    assert _cursor_key("comment", "Notion") == "hn:comment:Notion"
