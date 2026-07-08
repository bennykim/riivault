"""Shared FastAPI dependencies."""

from __future__ import annotations

import asyncpg
from fastapi import Request


async def get_pool(request: Request) -> asyncpg.Pool:
    return request.app.state.pool
