"""Application settings loaded from environment / .env files (pydantic-settings).

Both the repo-root ``../.env`` and ``backend/.env`` are searched (in that order);
whichever exist are loaded. Real process env vars always take precedence.
"""

from __future__ import annotations

from functools import lru_cache

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
    reddit_user_agent: str = "macos:riivault:v0.1 (non-commercial research)"
    reddit_qpm: int = 90

    # --- Hacker News (no key required) ---
    hn_enabled: bool = True
    hn_rpm: int = 60
    hn_hits_per_page: int = 50
    hn_max_pages_per_term: int = 2

    # --- Collection targets (comma separated) ---
    riivault_subreddits: str = (
        "SaaS,Entrepreneur,startups,indiehackers,webdev,nocode,"
        "microsaas,SideProject,EntrepreneurRideAlong,smallbusiness"
    )

    # --- AI (optional) ---
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # --- Web (unused by backend, kept for parity/introspection) ---
    api_url: str = "http://localhost:8000"
    next_public_api_url: str = "http://localhost:8000"

    @property
    def subreddits(self) -> list[str]:
        return [s.strip() for s in self.riivault_subreddits.split(",") if s.strip()]

    @property
    def voc_enabled(self) -> bool:
        """VoC extraction runs only when an Anthropic API key is configured."""
        return bool(self.anthropic_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
