"""One-time VoC ledger re-cluster: merge semantically duplicate entries.

Before semantic dedup shipped, the exact-text merge almost never fired (the
LLM rewords each run), leaving the ledger as N near-duplicate rows with
``occurrences = 1``. This job embeds every ``feature_request`` row, greedily
clusters within each (entity_id, kind) bucket, and merges each cluster into
its earliest row (occurrences summed, first_seen/last_seen widened,
``topic_daily`` volume series remapped onto the canonical fr_id).

Safety: **dry-run by default** (prints the merge plan only). ``--apply``
snapshots ``feature_request`` / ``topic_daily`` into ``*_backup_YYYYMMDD``
tables before writing, and runs the whole merge in one transaction.

``plan_merges`` is pure so the clustering/merge math is unit-testable.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import UTC, datetime
from typing import Any

from ..config import Settings, get_settings
from ..db import pool_context
from ..nlp.embed import embed_texts, greedy_clusters, vector_literal
from .aggregate import _recompute_fr_momentum

logger = logging.getLogger("riivault.recluster")


def plan_merges(
    rows: list[dict[str, Any]],
    vectors: list[list[float]],
    threshold: float,
) -> list[dict[str, Any]]:
    """Compute the merge plan (pure).

    ``rows`` and ``vectors`` are index-aligned; rows must be ordered by
    (first_seen, fr_id) so each cluster's seed is its earliest entry, which
    becomes the canonical row (its wording is the ledger identity).
    Returns one dict per multi-row cluster:
    ``{canonical, duplicates, occurrences, first_seen, last_seen, example_ref}``.
    """
    buckets: dict[tuple, list[int]] = defaultdict(list)
    for i, row in enumerate(rows):
        buckets[(row["entity_id"], row["kind"])].append(i)

    merges: list[dict[str, Any]] = []
    for indices in buckets.values():
        clusters = greedy_clusters([vectors[i] for i in indices], threshold)
        for cluster in clusters:
            if len(cluster) < 2:
                continue
            members = [rows[indices[c]] for c in cluster]
            canonical = members[0]
            merges.append(
                {
                    "canonical": canonical["fr_id"],
                    "duplicates": [m["fr_id"] for m in members[1:]],
                    "occurrences": sum(m["occurrences"] for m in members),
                    "first_seen": min(m["first_seen"] for m in members),
                    "last_seen": max(m["last_seen"] for m in members),
                    "example_ref": next(
                        (m["example_ref"] for m in members if m["example_ref"]), None
                    ),
                }
            )
    return merges


async def recluster_voc(
    settings: Settings | None = None,
    apply: bool = False,
    threshold: float | None = None,
) -> dict:
    settings = settings or get_settings()
    threshold = threshold if threshold is not None else settings.voc_dedup_threshold
    if not settings.voc_embed_enabled:
        logger.warning("recluster skipped: VOYAGE_API_KEY is not set")
        return {"merged": 0, "skipped": "no_voyage_key"}

    async with pool_context(settings) as pool:
        async with pool.acquire() as conn:
            rows = [
                dict(r)
                for r in await conn.fetch(
                    """
                    SELECT fr_id, entity_id, kind, normalized_text,
                           first_seen, last_seen, occurrences, example_ref
                      FROM feature_request
                     ORDER BY first_seen, fr_id
                    """
                )
            ]
            if not rows:
                return {"merged": 0, "rows": 0}

            vectors = await embed_texts([r["normalized_text"] for r in rows], settings)
            if vectors is None:
                return {"merged": 0, "skipped": "embedding_failed"}

            merges = plan_merges(rows, vectors, threshold)
            dup_count = sum(len(m["duplicates"]) for m in merges)
            logger.info(
                "recluster plan: %s rows -> %s clusters to merge (%s duplicates, "
                "threshold %.2f)%s",
                len(rows), len(merges), dup_count, threshold,
                "" if apply else " [dry-run: pass --apply to execute]",
            )
            by_id = {r["fr_id"]: r for r in rows}
            for m in merges[:20]:
                logger.info(
                    "  keep fr_id=%s %r  <- merges %s",
                    m["canonical"],
                    by_id[m["canonical"]]["normalized_text"][:70],
                    m["duplicates"],
                )
            if len(merges) > 20:
                logger.info("  ... and %s more clusters", len(merges) - 20)

            if not apply:
                return {"rows": len(rows), "clusters": len(merges),
                        "duplicates": dup_count, "applied": False}

            suffix = datetime.now(UTC).strftime("%Y%m%d")
            vec_by_id = {r["fr_id"]: vectors[i] for i, r in enumerate(rows)}
            async with conn.transaction():
                # Snapshot both tables before any destructive write.
                await conn.execute(
                    f"CREATE TABLE IF NOT EXISTS feature_request_backup_{suffix}"
                    " AS TABLE feature_request"
                )
                await conn.execute(
                    f"CREATE TABLE IF NOT EXISTS topic_daily_backup_{suffix}"
                    " AS TABLE topic_daily"
                )

                for m in merges:
                    dupes = m["duplicates"]
                    # Fold the duplicates' per-day volume series into the
                    # canonical topic_id, then drop the duplicate series/rows.
                    # Pre-aggregate by day: two duplicates sharing a day would
                    # otherwise produce two (day, canonical) rows in one INSERT,
                    # and ON CONFLICT cannot touch the same key twice.
                    await conn.execute(
                        """
                        INSERT INTO topic_daily
                            (day, topic_id, entity_id, label, volume, momentum)
                        SELECT day, $1,
                               (array_agg(entity_id ORDER BY day))[1],
                               (array_agg(label ORDER BY day))[1],
                               SUM(volume),
                               (array_agg(momentum ORDER BY day))[1]
                          FROM topic_daily WHERE topic_id = ANY($2::bigint[])
                         GROUP BY day
                        ON CONFLICT (day, topic_id) DO UPDATE
                            SET volume = topic_daily.volume + EXCLUDED.volume
                        """,
                        m["canonical"], dupes,
                    )
                    await conn.execute(
                        "DELETE FROM topic_daily WHERE topic_id = ANY($1::bigint[])",
                        dupes,
                    )
                    await conn.execute(
                        "DELETE FROM feature_request WHERE fr_id = ANY($1::bigint[])",
                        dupes,
                    )
                    await conn.execute(
                        """
                        UPDATE feature_request
                           SET occurrences = $2, first_seen = $3, last_seen = $4,
                               example_ref = COALESCE(example_ref, $5)
                         WHERE fr_id = $1
                        """,
                        m["canonical"], m["occurrences"],
                        m["first_seen"], m["last_seen"], m["example_ref"],
                    )

                # Store embeddings on every surviving row so incremental
                # semantic dedup has a full ledger to match against.
                surviving = await conn.fetch(
                    "SELECT fr_id FROM feature_request WHERE embedding IS NULL"
                )
                stored = 0
                for r in surviving:
                    vec = vec_by_id.get(r["fr_id"])
                    if vec is None:
                        continue
                    await conn.execute(
                        "UPDATE feature_request SET embedding = $2::vector WHERE fr_id = $1",
                        r["fr_id"], vector_literal(vec),
                    )
                    stored += 1

                await _recompute_fr_momentum(conn)

    summary = {
        "rows": len(rows), "clusters": len(merges), "duplicates_removed": dup_count,
        "embeddings_stored": stored, "backup_suffix": suffix, "applied": True,
    }
    logger.info("recluster complete: %s", summary)
    return summary
