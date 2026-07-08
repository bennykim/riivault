"""FastAPI application. Serves derived/aggregate data only (never raw_*)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..config import get_settings
from ..db import create_pool
from .routes import entities, issue, painpoints, signals, subscribe

logger = logging.getLogger("riivault.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.pool = await create_pool(settings)
    logger.info("riivault API pool ready")
    try:
        yield
    finally:
        await app.state.pool.close()


app = FastAPI(title="riivault API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/healthz")
async def healthz():
    db_ok = False
    pool = getattr(app.state, "pool", None)
    if pool is not None:
        try:
            async with pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
            db_ok = True
        except Exception:  # noqa: BLE001
            db_ok = False
    return {"status": "ok", "db": db_ok}


app.include_router(issue.router, prefix="/api/v1")
app.include_router(entities.router, prefix="/api/v1")
app.include_router(painpoints.router, prefix="/api/v1")
app.include_router(signals.router, prefix="/api/v1")
app.include_router(subscribe.router, prefix="/api/v1")
