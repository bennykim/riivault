"""Application settings loaded from environment / .env files (pydantic-settings).

Both the repo-root ``../.env`` and ``backend/.env`` are searched (in that order);
whichever exist are loaded. Real process env vars always take precedence.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- DB ---
    database_url: str = "postgresql://riivault:riivault@localhost:5433/riivault"

    # --- Reddit API ---
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    # Must satisfy collector.reddit.USER_AGENT_RE — the client refuses to build
    # otherwise. The placeholder username is deliberately invalid-looking so an
    # unconfigured deployment fails loudly instead of calling Reddit as someone else.
    reddit_user_agent: str = "web:riivault:v0.2 (by /u/SET_REDDIT_USER_AGENT)"
    reddit_qpm: int = 90

    # --- Hacker News (no key required) ---
    hn_enabled: bool = True
    hn_rpm: int = 60
    hn_hits_per_page: int = 50
    hn_max_pages_per_term: int = 2

    # --- GitHub (token optional: 60 req/hr without, 5000 req/hr with) ---
    # GitHub Actions forbids secrets starting with GITHUB_, so the canonical
    # env var is GH_API_TOKEN; GITHUB_TOKEN is accepted for local .env parity.
    gh_api_token: str = Field(
        "", validation_alias=AliasChoices("GH_API_TOKEN", "GITHUB_TOKEN")
    )
    gh_enabled: bool = True
    gh_rpm: int = 30
    gh_per_page: int = 100
    gh_max_pages_per_repo: int = 3

    # --- Product Hunt (developer token; GraphQL v2) ---
    producthunt_token: str = ""
    ph_enabled: bool = True
    ph_rpm: int = 10
    ph_first: int = 20
    ph_max_pages_per_topic: int = 2
    ph_topics: str = "artificial-intelligence,saas,developer-tools,productivity,no-code"

    # --- Collection targets (comma separated) ---
    # Deliberately small: the five communities closest to the tracked niche.
    # Steady-state cost is one listing request per subreddit per run (~60/day),
    # far below the free-tier allowance — see docs/reddit-api-access-brief.html.
    riivault_subreddits: str = (
        "SaaS,indiehackers,microsaas,startups,Entrepreneur"
    )

    # --- AI (optional) ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # --- Embeddings (optional; VoC semantic dedup) ---
    # voyage-3.5-lite outputs 1024 dims, matching feature_request.embedding
    # VECTOR(1024). Without a key the dedup degrades to exact text match.
    voyage_api_key: str = ""
    voyage_model: str = "voyage-3.5-lite"
    voc_dedup_threshold: float = 0.85  # cosine similarity to merge VoC entries

    # --- Web (unused by backend, kept for parity/introspection) ---
    api_url: str = "http://localhost:8000"
    next_public_api_url: str = "http://localhost:8000"

    @property
    def subreddits(self) -> list[str]:
        return [s.strip() for s in self.riivault_subreddits.split(",") if s.strip()]

    @property
    def ph_topic_list(self) -> list[str]:
        return [t.strip() for t in self.ph_topics.split(",") if t.strip()]

    @property
    def voc_enabled(self) -> bool:
        """VoC extraction runs only when an Anthropic API key is configured."""
        return bool(self.anthropic_api_key.strip())

    @property
    def voc_embed_enabled(self) -> bool:
        """Semantic VoC dedup runs only when a Voyage API key is configured."""
        return bool(self.voyage_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
