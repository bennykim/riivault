"""Entity resolution: match canonical names + aliases in free text.

Matching is case-insensitive with word boundaries; every term is regex-escaped
so alias metacharacters (``.``, ``+``, ``/`` …) are treated literally.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

import asyncpg


class EntityMatcher:
    """Compiled matcher mapping text -> the set of entity ids it mentions."""

    def __init__(self, entities: Iterable[tuple[int, Iterable[str]]]):
        self._patterns: list[tuple[int, re.Pattern[str]]] = []
        for entity_id, terms in entities:
            escaped = sorted(
                {re.escape(t.strip()) for t in terms if t and t.strip()},
                key=len,
                reverse=True,
            )
            if not escaped:
                continue
            # (?<!\w) / (?!\w) act as word boundaries that also behave well for
            # multi-word aliases and terms with trailing punctuation.
            pattern = re.compile(
                r"(?<!\w)(?:" + "|".join(escaped) + r")(?!\w)",
                re.IGNORECASE,
            )
            self._patterns.append((entity_id, pattern))

    def match(self, text: str | None) -> set[int]:
        if not text:
            return set()
        return {eid for eid, pattern in self._patterns if pattern.search(text)}

    def __len__(self) -> int:
        return len(self._patterns)


async def load_matcher(conn: asyncpg.Connection) -> EntityMatcher:
    """Build a matcher from the ``entity`` table."""
    rows = await conn.fetch("SELECT entity_id, canonical_name, aliases FROM entity")
    entities = [
        (row["entity_id"], [row["canonical_name"], *(row["aliases"] or [])])
        for row in rows
    ]
    return EntityMatcher(entities)
