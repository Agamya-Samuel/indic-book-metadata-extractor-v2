"""Admin endpoints for publishing reviewed metadata to Wikibase."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_audit_context, require_admin
from app.core.config import settings
from app.core.database import get_db
from app.models.book import Book, BookStatus
from app.models.user import User
from app.schemas.export import PublishRequest
from app.services import audit_service, wikibase_publish
from app.services.audit_service import AuditAction, AuditContext

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(require_admin)])


def _credentials_configured() -> bool:
    return bool(settings.wikibase_bot_username and settings.wikibase_bot_password)


@router.post("/publish")
async def publish_to_wikibase(
    body: PublishRequest,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
    ctx: AuditContext = Depends(get_audit_context),
) -> dict:
    """Create or update one Wikibase item per selected book.

    Books that already have ``wikibase_item_id`` are updated in place; entity
    values (author, publisher, ...) are matched by label and created once as
    stubs when missing.
    """
    if not body.dry_run and not _credentials_configured():
        raise HTTPException(
            status_code=400,
            detail="WIKIBASE_BOT_USERNAME and WIKIBASE_BOT_PASSWORD must be configured",
        )

    statement = select(Book).options(selectinload(Book.metadata_record))
    if body.book_ids:
        statement = statement.where(Book.id.in_(set(body.book_ids)))
    elif not body.dry_run:
        # Without an explicit selection, only publish books whose review is
        # complete. A dry run may preview any book.
        statement = statement.where(Book.status == BookStatus.COMPLETE)
    if body.language:
        statement = statement.where(Book.language == body.language)

    books = list((await db.execute(statement)).scalars().all())
    if body.book_ids:
        found = {book.id for book in books}
        missing = [str(b) for b in body.book_ids if b not in found]
        if missing:
            raise HTTPException(status_code=404, detail=f"Books not found: {', '.join(missing)}")

    mapping = wikibase_publish.mapping()
    client = wikibase_publish.build_client()
    reports: list[dict] = []
    try:
        if not body.dry_run:
            await client.login()

        for book in books:
            fields = (book.metadata_record.fields if book.metadata_record else None) or {}
            report = await wikibase_publish.publish_book(client, book, fields, mapping, dry_run=body.dry_run)
            if report.item_id and not body.dry_run:
                book.wikibase_item_id = report.item_id
            reports.append(
                {
                    "book_id": str(book.id),
                    "title": book.title,
                    "language": book.language,
                    "item_id": report.item_id,
                    "created": report.created,
                    "warnings": report.warnings,
                }
            )
            logger.info(
                "publish book=%s item=%s created=%s warnings=%d",
                book.id,
                report.item_id,
                report.created,
                len(report.warnings),
            )

        if not body.dry_run:
            await db.commit()
    finally:
        await client.aclose()

    published = len([r for r in reports if r["item_id"]])
    await audit_service.record_isolated(
        db,
        action=AuditAction.EXPORT_WIKIBASE,
        ctx=ctx,
        description=f"Wikibase publish ({'dry run' if body.dry_run else 'live'}) for {len(reports)} book(s)",
        resource_type="wikibase",
        details={
            "dry_run": body.dry_run,
            "book_count": len(reports),
            "published": published,
            "book_ids": [r["book_id"] for r in reports],
            "language": body.language,
        },
    )
    return {
        "dry_run": body.dry_run,
        "published": published,
        "reports": reports,
    }
