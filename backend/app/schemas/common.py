"""Shared response envelopes."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    """A single page of a collection.

    The four metadata fields mirror every list endpoint in the API so the
    client only has to understand one pagination shape.
    """

    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(
        cls,
        items: list,
        total: int,
        page: int,
        page_size: int,
        **extra,
    ) -> "Page":
        from app.services.pagination import page_count

        return cls(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=page_count(total, page_size),
            **extra,
        )
