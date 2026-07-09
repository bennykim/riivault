from datetime import UTC, datetime

from riivault.collector.github import _cursor_key, _issue_number_from_url, parse_issue
from riivault.collector.reddit import author_hash

REPO = "supabase/supabase"

ISSUE_ITEM = {
    "id": 111,
    "number": 123,
    "title": "Realtime drops connection after idle",
    "body": "Steps to reproduce: leave a channel idle for 10 minutes.",
    "state": "open",
    "comments": 5,
    "html_url": "https://github.com/supabase/supabase/issues/123",
    "created_at": "2026-07-08T10:00:00Z",
    "user": {"login": "alice"},
}

COMMENT_ITEM = {
    "id": 999,
    "body": "Same here — happens on the free tier too.",
    "issue_url": "https://api.github.com/repos/supabase/supabase/issues/42",
    "html_url": "https://github.com/supabase/supabase/issues/42#issuecomment-999",
    "created_at": "2026-07-08T11:30:00Z",
    "user": {"login": "bob"},
}


def test_parse_issue():
    gh_id, repo, kind, number, ahash, title, body, state, num_comments, url, created = (
        parse_issue(ISSUE_ITEM, REPO, "issue")
    )
    assert gh_id == "supabase/supabase#123"
    assert repo == REPO
    assert kind == "issue"
    assert number == 123
    assert title  # non-empty
    assert body  # non-empty
    assert state == "open"
    assert num_comments == 5
    assert url == "https://github.com/supabase/supabase/issues/123"
    assert created == datetime(2026, 7, 8, 10, 0, tzinfo=UTC)


def test_parse_comment_has_no_title_and_number_from_issue_url():
    gh_id, repo, kind, number, ahash, title, body, state, num_comments, url, created = (
        parse_issue(COMMENT_ITEM, REPO, "comment")
    )
    assert gh_id == "supabase/supabase#c999"
    assert kind == "comment"
    assert number == 42
    assert title is None
    assert state is None
    assert num_comments == 0
    assert body == "Same here — happens on the free tier too."


def test_parse_issue_author_is_hashed_not_plaintext():
    ahash = parse_issue(ISSUE_ITEM, REPO, "issue")[4]
    assert ahash == author_hash("alice")
    assert ahash != "alice"
    assert len(ahash) == 64  # sha-256 hex digest


def test_parse_issue_missing_user_yields_none():
    item = dict(ISSUE_ITEM, user=None)
    assert parse_issue(item, REPO, "issue")[4] is None


def test_issue_number_from_url_edge_cases():
    assert _issue_number_from_url("https://api.github.com/repos/o/r/issues/7") == 7
    assert _issue_number_from_url("https://api.github.com/repos/o/r/issues/7/") == 7
    assert _issue_number_from_url(None) is None
    assert _issue_number_from_url("https://api.github.com/repos/o/r") is None


def test_cursor_key_namespaces_by_kind_and_repo():
    assert _cursor_key("issue", REPO) == "gh:issue:supabase/supabase"
    assert _cursor_key("comment", REPO) == "gh:comment:supabase/supabase"
