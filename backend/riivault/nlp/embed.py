"""Text embeddings via Voyage AI (optional; powers VoC semantic dedup).

Anthropic has no embeddings API and officially recommends Voyage; the default
``voyage-3.5-lite`` outputs 1024 dimensions, matching the schema's
``feature_request.embedding VECTOR(1024)``. Mirrors the ``classify_documents``
contract: returns ``None`` when the call failed/was skipped so callers degrade
to exact-text dedup instead of marking work done.

``vector_literal`` / ``cosine_similarity`` / ``greedy_clusters`` are pure so
the dedup math is unit-testable without an API key. Vectors are bound as text
literals cast with ``::vector`` — no asyncpg codec registration needed.
"""

from __future__ import annotations

import logging

import httpx

from ..config import Settings

logger = logging.getLogger("riivault.embed")

VOYAGE_URL = "https://api.voyageai.com/v1/embeddings"
EMBED_DIM = 1024
BATCH_SIZE = 128  # well under Voyage's 1,000-texts-per-request cap


def vector_literal(vec: list[float]) -> str:
    """pgvector input literal: ``[0.1,0.2,...]`` (for ``$n::vector`` binds)."""
    return "[" + ",".join(repr(float(v)) for v in vec) + "]"


def cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def greedy_clusters(
    vectors: list[list[float]], threshold: float
) -> list[list[int]]:
    """Cluster vector indices greedily: each joins the first cluster whose
    *seed* is within ``threshold`` cosine similarity, else seeds its own.

    Seed-comparison (not centroid) keeps the result order-stable and cheap at
    ledger scale (hundreds of rows per entity/kind bucket). Returns clusters
    in first-seen order; each cluster's first index is its seed.
    """
    seeds: list[int] = []
    clusters: list[list[int]] = []
    for i, vec in enumerate(vectors):
        for c, seed_idx in enumerate(seeds):
            if cosine_similarity(vec, vectors[seed_idx]) >= threshold:
                clusters[c].append(i)
                break
        else:
            seeds.append(i)
            clusters.append([i])
    return clusters


async def embed_texts(
    texts: list[str], settings: Settings
) -> list[list[float]] | None:
    """Embed a batch of texts; ``None`` when disabled or the call failed."""
    if not settings.voc_embed_enabled or not texts:
        return None
    out: list[list[float]] = []
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            for start in range(0, len(texts), BATCH_SIZE):
                batch = texts[start : start + BATCH_SIZE]
                resp = await client.post(
                    VOYAGE_URL,
                    json={"model": settings.voyage_model, "input": batch},
                    headers={"Authorization": f"Bearer {settings.voyage_api_key}"},
                )
                resp.raise_for_status()
                data = resp.json().get("data") or []
                if len(data) != len(batch):
                    raise RuntimeError(
                        f"expected {len(batch)} embeddings, got {len(data)}"
                    )
                # API orders by input index; sort defensively anyway.
                out.extend(
                    d["embedding"]
                    for d in sorted(data, key=lambda d: d.get("index", 0))
                )
    except Exception as exc:  # noqa: BLE001 - degrade gracefully, never crash pipeline
        logger.warning("embedding failed, falling back to exact dedup: %s", exc)
        return None
    return out
