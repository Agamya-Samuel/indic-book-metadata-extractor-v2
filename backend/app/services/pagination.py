"""Shared pagination helpers."""

from __future__ import annotations

import math

from sqlalchemy.ext.asyncio import AsyncSession


def page_count(total: int, page_size: int) -> int:
    """Total number of pages for a result set."""
    return math.ceil(total / page_size) if total > 0 else 0


async def paginate(
    db: AsyncSession,
    query,
    count_query,
    *,
    page: int,
    page_size: int,
):
    """Return ``(rows, total)`` for one page of ``query``."""
    total = int(await db.scalar(count_query) or 0)
    rows = (await db.execute(query.offset((page - 1) * page_size).limit(page_size))).all()
    return rows, total
