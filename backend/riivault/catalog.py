"""Entity catalog sync: ``entities.yaml`` -> ``entity`` table (idempotent).

The YAML file is the single source of truth for what riivault tracks; the
collect workflow runs ``riivault sync-entities`` before every pass so editing
the file and pushing is the whole onboarding flow. The sync only upserts —
entities missing from the file are left untouched (non-destructive), so a
botched edit cannot drop accumulated time-series.

``load_catalog`` / ``entry_row`` are pure so validation is unit-testable
without a database or filesystem.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

from .config import Settings, get_settings
from .db import pool_context

logger = logging.getLogger("riivault.catalog")

# Mirrors the schema comment on entity.type.
ALLOWED_TYPES = {"product", "ticker", "brand", "topic", "subreddit", "keyword"}
# Flat YAML keys that land in entity.metadata (tracked defaults to false).
METADATA_KEYS = ("tracked", "context", "repo", "npm", "pypi", "se_tag")

DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[1] / "entities.yaml"


def load_catalog(text: str) -> list[dict[str, Any]]:
    """Parse + validate the YAML catalog; raises ValueError on any bad entry.

    Failing loudly (rather than skipping bad entries) is deliberate: the sync
    runs unattended in CI, and a silently dropped entity would just look like
    a mysteriously flat time-series later.
    """
    data = yaml.safe_load(text) or {}
    entries = data.get("entities")
    if not isinstance(entries, list) or not entries:
        raise ValueError("entities.yaml must contain a non-empty 'entities' list")

    seen: set[tuple[str, str]] = set()
    validated: list[dict[str, Any]] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"entities[{i}] must be a mapping")
        etype = entry.get("type")
        name = entry.get("name")
        if etype not in ALLOWED_TYPES:
            raise ValueError(f"entities[{i}] ({name!r}): invalid type {etype!r}")
        if not isinstance(name, str) or not name.strip():
            raise ValueError(f"entities[{i}]: 'name' is required")
        key = (etype, name.strip())
        if key in seen:
            raise ValueError(f"entities[{i}]: duplicate ({etype}, {name})")
        seen.add(key)

        aliases = entry.get("aliases") or []
        if not isinstance(aliases, list) or not all(
            isinstance(a, str) and a.strip() for a in aliases
        ):
            raise ValueError(f"entities[{i}] ({name}): aliases must be non-empty strings")
        if not isinstance(entry.get("tracked", False), bool):
            raise ValueError(f"entities[{i}] ({name}): tracked must be a boolean")
        for field in ("context", "repo", "npm", "pypi", "se_tag"):
            value = entry.get(field)
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise ValueError(f"entities[{i}] ({name}): {field} must be a string")
        validated.append(entry)
    return validated


def entry_row(entry: dict[str, Any]) -> tuple[str, str, list[str], dict[str, Any]]:
    """Map a validated entry to an ``entity`` upsert row (pure).

    Returns ``(type, canonical_name, aliases, metadata)``; metadata carries the
    flat YAML keys, omitting unset ones (``tracked`` is always present).
    """
    metadata: dict[str, Any] = {"tracked": bool(entry.get("tracked", False))}
    for field in METADATA_KEYS[1:]:
        value = entry.get(field)
        if value is not None:
            metadata[field] = value.strip()
    return (
        entry["type"],
        entry["name"].strip(),
        [a.strip() for a in entry.get("aliases") or []],
        metadata,
    )


async def sync_entities(
    settings: Settings | None = None, path: Path | None = None
) -> dict:
    settings = settings or get_settings()
    path = path or DEFAULT_CATALOG_PATH
    entries = load_catalog(path.read_text(encoding="utf-8"))
    rows = [entry_row(e) for e in entries]

    async with pool_context(settings) as pool:
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                INSERT INTO entity (type, canonical_name, aliases, metadata)
                VALUES ($1, $2, $3, $4)
                ON CONFLICT (type, canonical_name) DO UPDATE
                    SET aliases = EXCLUDED.aliases, metadata = EXCLUDED.metadata
                """,
                rows,
            )
            total = await conn.fetchval("SELECT count(*) FROM entity")

    summary = {"synced": len(rows), "entities_total": int(total)}
    logger.info("sync_entities complete: %s", summary)
    return summary
