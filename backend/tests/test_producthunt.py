from datetime import UTC, datetime

from riivault.collector.producthunt import _cursor_key, parse_post
from riivault.collector.reddit import author_hash

TOPIC = "developer-tools"

POST_NODE = {
    "id": "1189471",
    "name": "Launchpad",
    "tagline": "Ship your side project on Supabase in a weekend",
    "description": "Built on Supabase and Next.js with auth included.",
    "url": "https://www.producthunt.com/posts/launchpad",
    "votesCount": 42,
    "commentsCount": 7,
    "createdAt": "2026-07-09T07:01:00Z",
    "user": {"username": "maker_jane"},
}


def test_parse_post():
    ph_id, topic, ahash, name, tagline, description, url, votes, num_comments, created = (
        parse_post(POST_NODE, TOPIC)
    )
    assert ph_id == "1189471"
    assert topic == TOPIC
    assert name == "Launchpad"
    assert tagline.startswith("Ship your side project")
    assert description.startswith("Built on Supabase")
    assert url == "https://www.producthunt.com/posts/launchpad"
    assert votes == 42
    assert num_comments == 7
    assert created == datetime(2026, 7, 9, 7, 1, tzinfo=UTC)


def test_parse_post_author_is_hashed_not_plaintext():
    ahash = parse_post(POST_NODE, TOPIC)[2]
    assert ahash == author_hash("maker_jane")
    assert ahash != "maker_jane"
    assert len(ahash) == 64  # sha-256 hex digest


def test_parse_post_missing_user_yields_none():
    node = dict(POST_NODE, user=None)
    assert parse_post(node, TOPIC)[2] is None


def test_cursor_key_namespaces_by_topic():
    assert _cursor_key("saas") == "ph:posts:saas"
    assert _cursor_key("developer-tools") == "ph:posts:developer-tools"
