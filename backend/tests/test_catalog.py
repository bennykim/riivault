"""Catalog validation tests + a regression net over the real entities.yaml."""

import pytest

from riivault.catalog import DEFAULT_CATALOG_PATH, entry_row, load_catalog

VALID = """
entities:
  - type: product
    name: Supabase
    aliases: [Supabase]
    tracked: true
    context: r/webdev
    repo: supabase/supabase
    npm: "@supabase/supabase-js"
    pypi: supabase
    se_tag: supabase
  - type: topic
    name: AI wrapper
"""


def test_load_catalog_valid():
    entries = load_catalog(VALID)
    assert len(entries) == 2
    assert entries[0]["name"] == "Supabase"


def test_entry_row_full_mapping():
    entries = load_catalog(VALID)
    etype, name, aliases, metadata = entry_row(entries[0])
    assert (etype, name, aliases) == ("product", "Supabase", ["Supabase"])
    assert metadata == {
        "tracked": True,
        "context": "r/webdev",
        "repo": "supabase/supabase",
        "npm": "@supabase/supabase-js",
        "pypi": "supabase",
        "se_tag": "supabase",
    }


def test_entry_row_defaults():
    _, name, aliases, metadata = entry_row(load_catalog(VALID)[1])
    assert (name, aliases) == ("AI wrapper", [])
    # tracked always present (false by default); unset mappings omitted.
    assert metadata == {"tracked": False}


@pytest.mark.parametrize(
    "text",
    [
        "entities: []",                                          # empty list
        "entities:\n  - type: gadget\n    name: X",              # bad type
        "entities:\n  - type: product\n    name: ''",            # blank name
        "entities:\n  - type: product\n    name: A\n  - type: product\n    name: A",  # dup
        "entities:\n  - type: product\n    name: A\n    aliases: [3]",     # bad alias
        "entities:\n  - type: product\n    name: A\n    tracked: 'yes'",   # bad tracked
        "entities:\n  - type: product\n    name: A\n    repo: 3",          # bad mapping
    ],
)
def test_load_catalog_rejects(text):
    with pytest.raises(ValueError):
        load_catalog(text)


def test_shipped_catalog_is_valid():
    """The real entities.yaml must always parse — CI syncs it unattended."""
    entries = load_catalog(DEFAULT_CATALOG_PATH.read_text(encoding="utf-8"))
    assert len(entries) >= 7
    for entry in entries:
        _, _, _, metadata = entry_row(entry)
        repo = metadata.get("repo")
        if repo is not None:
            owner, _, name = repo.partition("/")
            assert owner and name, f"repo must be owner/name: {repo!r}"
