"""Newsletter subscription."""

from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, EmailStr

from ..deps import get_pool

router = APIRouter()


class SubscribeIn(BaseModel):
    email: EmailStr


@router.post("/subscribe", status_code=201)
async def subscribe(
    body: SubscribeIn,
    response: Response,
    pool: asyncpg.Pool = Depends(get_pool),
):
    async with pool.acquire() as conn:
        status = await conn.execute(
            """
            INSERT INTO newsletter_subscriber (email) VALUES ($1)
            ON CONFLICT (email) DO NOTHING
            """,
            str(body.email),
        )
    # asyncpg returns 'INSERT 0 1' on insert, 'INSERT 0 0' when the row existed.
    if status.split()[-1] == "1":
        return {"ok": True}
    response.status_code = 200
    return {"ok": True, "already": True}
