"""Pure dedup math: vector literals, cosine similarity, greedy clustering,
the recluster merge plan, and the embed 429-retry loop."""

from datetime import date

import httpx

from riivault.collector.recluster import plan_merges
from riivault.config import Settings
from riivault.nlp.embed import (
    BASE_BACKOFF,
    cosine_similarity,
    embed_texts,
    greedy_clusters,
    vector_literal,
)


def test_vector_literal_format():
    assert vector_literal([0.5, -1.0, 2.0]) == "[0.5,-1.0,2.0]"


def test_cosine_similarity_basics():
    assert cosine_similarity([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == -1.0
    assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0  # zero vector guard


def test_greedy_clusters_groups_near_duplicates():
    vectors = [
        [1.0, 0.0],    # seed A
        [0.99, 0.05],  # ~A
        [0.0, 1.0],    # seed B
        [0.05, 0.99],  # ~B
        [-1.0, 0.0],   # its own cluster
    ]
    assert greedy_clusters(vectors, threshold=0.9) == [[0, 1], [2, 3], [4]]


def test_greedy_clusters_low_threshold_merges_all():
    vectors = [[1.0, 0.0], [0.9, 0.1], [0.8, 0.2]]
    assert greedy_clusters(vectors, threshold=0.5) == [[0, 1, 2]]


def _row(fr_id, entity_id, kind, occ, first, last, ref=None):
    return {
        "fr_id": fr_id, "entity_id": entity_id, "kind": kind,
        "normalized_text": f"text-{fr_id}", "occurrences": occ,
        "first_seen": first, "last_seen": last, "example_ref": ref,
    }


def test_plan_merges_within_entity_kind_only():
    rows = [
        _row(1, 10, "pain_point", 1, date(2026, 7, 9), date(2026, 7, 9)),
        _row(2, 10, "pain_point", 1, date(2026, 7, 10), date(2026, 7, 12), "http://x"),
        _row(3, 10, "praise", 1, date(2026, 7, 10), date(2026, 7, 10)),  # other kind
        _row(4, 20, "pain_point", 1, date(2026, 7, 11), date(2026, 7, 11)),  # other entity
    ]
    same = [1.0, 0.0]
    vectors = [same, same, same, same]  # identical vectors everywhere

    merges = plan_merges(rows, vectors, threshold=0.9)
    # Only rows 1+2 share (entity, kind); kind/entity boundaries are respected.
    assert len(merges) == 1
    m = merges[0]
    assert m["canonical"] == 1 and m["duplicates"] == [2]
    assert m["occurrences"] == 2
    assert m["first_seen"] == date(2026, 7, 9)
    assert m["last_seen"] == date(2026, 7, 12)
    assert m["example_ref"] == "http://x"  # first non-null wins


def test_plan_merges_no_merges_below_threshold():
    rows = [
        _row(1, 10, "bug", 1, date(2026, 7, 9), date(2026, 7, 9)),
        _row(2, 10, "bug", 1, date(2026, 7, 10), date(2026, 7, 10)),
    ]
    vectors = [[1.0, 0.0], [0.0, 1.0]]  # orthogonal
    assert plan_merges(rows, vectors, threshold=0.85) == []


# --- embed_texts 429 retry loop (no real network / no real sleep) ----------

def _settings(**overrides) -> Settings:
    # _env_file=None so a real ../.env VOYAGE_API_KEY can't leak into tests.
    return Settings(
        _env_file=None, database_url="postgresql://x/y", **overrides
    )


async def test_embed_retries_on_429_then_succeeds():
    calls = {"n": 0}
    slept: list[float] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:  # first attempt rate-limited
            return httpx.Response(429, headers={"Retry-After": "2"})
        return httpx.Response(200, json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]})

    transport = httpx.MockTransport(handler)

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    # Patch the client the module builds so the mock transport is used.
    import riivault.nlp.embed as embed_mod

    orig = embed_mod.httpx.AsyncClient
    embed_mod.httpx.AsyncClient = lambda **kw: orig(transport=transport, **kw)
    try:
        out = await embed_texts(
            ["a complaint"], _settings(voyage_api_key="test-key"), sleep=fake_sleep
        )
    finally:
        embed_mod.httpx.AsyncClient = orig

    assert out == [[0.1, 0.2]]
    assert calls["n"] == 2
    assert slept == [2.0]  # Retry-After honored, not the backoff default


async def test_embed_gives_up_after_max_retries():
    slept: list[float] = []
    transport = httpx.MockTransport(lambda req: httpx.Response(429))

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    import riivault.nlp.embed as embed_mod

    orig = embed_mod.httpx.AsyncClient
    embed_mod.httpx.AsyncClient = lambda **kw: orig(transport=transport, **kw)
    try:
        out = await embed_texts(
            ["x"], _settings(voyage_api_key="test-key"), sleep=fake_sleep
        )
    finally:
        embed_mod.httpx.AsyncClient = orig

    assert out is None  # graceful degrade to exact-match dedup
    assert slept and slept[0] == BASE_BACKOFF  # backoff used when no Retry-After


async def test_embed_disabled_without_key():
    assert await embed_texts(["x"], _settings()) is None
