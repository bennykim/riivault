from riivault.entities import EntityMatcher


def make_matcher() -> EntityMatcher:
    return EntityMatcher(
        [
            (1, ["Cursor", "Cursor AI", "cursor.sh"]),
            (2, ["Notion AI", "Notion"]),
            (3, ["Go"]),
            (4, ["asp.net"]),
        ]
    )


def test_alias_and_case_insensitive():
    m = make_matcher()
    assert m.match("I switched to cursor ai yesterday") == {1}
    assert m.match("NOTION is great") == {2}
    assert m.match("multi-word Notion AI alias") == {2}


def test_word_boundary_no_partial_match():
    m = make_matcher()
    assert 3 not in m.match("I use Google every day")  # 'Go' not inside 'Google'
    assert m.match("I write Go daily") == {3}


def test_special_chars_are_escaped():
    m = make_matcher()
    assert m.match("aspXnet is not a match") == set()  # '.' is literal
    assert m.match("built with asp.net here") == {4}
    assert m.match("visit cursor.sh now") == {1}


def test_multiple_entities_and_empty_inputs():
    m = make_matcher()
    assert m.match("Notion AI vs Cursor showdown") == {1, 2}
    assert m.match("") == set()
    assert m.match(None) == set()


def test_len_reports_pattern_count():
    assert len(make_matcher()) == 4
