from uuid import UUID

from sqlalchemy import func, or_, select, String, cast
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.book import Book, PUBLIC_BOOK_STATUSES
from app.models.metadata import BookMetadata
from app.models.page import Page
from app.models.user import User


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _has_metadata_condition(has_metadata: bool):
    """EXISTS clause correlating a book to its metadata row.

    Applied to both the page query and the count query so `total` matches the
    filtered result instead of the unfiltered table.
    """
    exists = select(BookMetadata.id).where(BookMetadata.book_id == Book.id)
    return exists.exists() if has_metadata else ~exists.exists()


class SearchService:
    CARD_FIELDS = [
        "author",
        "publisher",
        "publication_date",
        "genre",
        "language",
        "title",
        "subtitle",
    ]

    SEARCHABLE_JSONB_FIELDS = [
        "author",
        "publisher",
        "genre",
        "subject",
        "description_work",
        "description_edition",
        "title",
        "subtitle",
        "label",
        "translator",
        "editor",
        "place_of_publication",
    ]

    @staticmethod
    async def list_books(
        db: AsyncSession,
        language: str | None = None,
        status: str | None = None,
        page: int = 1,
        page_size: int = 20,
        owner_id: UUID | None = None,
        public_only: bool = False,
        has_metadata: bool | None = None,
    ) -> tuple[list[dict], int]:
        query = (
            select(
                Book,
                BookMetadata.fields.label("metadata_fields"),
                User.display_name.label("owner_display_name"),
                User.email.label("owner_email"),
            )
            .outerjoin(BookMetadata, BookMetadata.book_id == Book.id)
            .join(User, User.id == Book.owner_id)
        )

        count_query = select(func.count()).select_from(Book)

        if language:
            query = query.where(Book.language == language)
            count_query = count_query.where(Book.language == language)
        if status:
            query = query.where(Book.status == status)
            count_query = count_query.where(Book.status == status)
        if owner_id is not None:
            query = query.where(Book.owner_id == owner_id)
            count_query = count_query.where(Book.owner_id == owner_id)
        if public_only:
            query = query.where(Book.status.in_(PUBLIC_BOOK_STATUSES))
            count_query = count_query.where(Book.status.in_(PUBLIC_BOOK_STATUSES))
        if has_metadata is not None:
            cond = _has_metadata_condition(has_metadata)
            query = query.where(cond)
            count_query = count_query.where(cond)

        total = (await db.execute(count_query)).scalar() or 0

        query = query.order_by(Book.created_at.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(query)
        rows = result.all()

        items = []
        for book, metadata_fields, owner_display_name, owner_email in rows:
            card_metadata = {}
            if metadata_fields and isinstance(metadata_fields, dict):
                for k in SearchService.CARD_FIELDS:
                    if k in metadata_fields and metadata_fields[k] is not None:
                        card_metadata[k] = metadata_fields[k]

            items.append({
                "id": book.id,
                "title": book.title,
                "filename": book.filename,
                "language": book.language,
                "status": book.status,
                "total_pages": book.total_pages,
                "created_at": book.created_at,
                "metadata_fields": card_metadata if card_metadata else None,
                "owner_id": book.owner_id,
                "owner_display_name": owner_display_name,
                "owner_email": owner_email,
            })

        return items, total

    @staticmethod
    async def search_books(
        db: AsyncSession,
        q: str,
        language: str | None = None,
        status: str | None = None,
        genre: str | None = None,
        publisher: str | None = None,
        page: int = 1,
        page_size: int = 20,
        owner_id: UUID | None = None,
        public_only: bool = False,
        has_metadata: bool | None = None,
    ) -> tuple[list[dict], int]:
        base = (
            select(
                Book,
                BookMetadata.fields.label("metadata_fields"),
                User.display_name.label("owner_display_name"),
                User.email.label("owner_email"),
            )
            .outerjoin(BookMetadata, BookMetadata.book_id == Book.id)
            .join(User, User.id == Book.owner_id)
        )

        if language:
            base = base.where(Book.language == language)
        if status:
            base = base.where(Book.status == status)
        if owner_id is not None:
            base = base.where(Book.owner_id == owner_id)
        if public_only:
            base = base.where(Book.status.in_(PUBLIC_BOOK_STATUSES))
        if has_metadata is not None:
            base = base.where(_has_metadata_condition(has_metadata))
        if genre:
            safe_genre = _escape_like(genre)
            base = base.where(
                cast(BookMetadata.fields["genre"], String).ilike(f"%{safe_genre}%", escape="\\")
            )
        if publisher:
            safe_publisher = _escape_like(publisher)
            base = base.where(
                cast(BookMetadata.fields["publisher"], String).ilike(f"%{safe_publisher}%", escape="\\")
            )

        conditions = [
            func.similarity(cast(Book.title, String), q) > 0.1,
            func.similarity(cast(Book.filename, String), q) > 0.1,
        ]
        for field_name in SearchService.SEARCHABLE_JSONB_FIELDS:
            conditions.append(
                func.similarity(
                    cast(BookMetadata.fields[field_name], String), q
                ) > 0.1
            )

        similarity_score = func.greatest(
            func.similarity(cast(Book.title, String), q),
            func.similarity(cast(Book.filename, String), q),
            *[
                func.similarity(
                    cast(BookMetadata.fields[f], String), q
                )
                for f in SearchService.SEARCHABLE_JSONB_FIELDS
            ],
        ).label("similarity_score")

        filtered = base.where(or_(*conditions))

        count_query = select(func.count()).select_from(filtered.subquery())
        total = (await db.execute(count_query)).scalar() or 0

        ordered = filtered.order_by(similarity_score.desc())
        paginated = ordered.offset((page - 1) * page_size).limit(page_size)

        result = await db.execute(paginated)
        rows = result.all()

        items = []
        for book, metadata_fields, owner_display_name, owner_email in rows:
            card_metadata = {}
            if metadata_fields and isinstance(metadata_fields, dict):
                for k in SearchService.CARD_FIELDS:
                    if k in metadata_fields and metadata_fields[k] is not None:
                        card_metadata[k] = metadata_fields[k]

            items.append({
                "id": book.id,
                "title": book.title,
                "filename": book.filename,
                "language": book.language,
                "status": book.status,
                "total_pages": book.total_pages,
                "created_at": book.created_at,
                "metadata_fields": card_metadata if card_metadata else None,
                "owner_id": book.owner_id,
                "owner_display_name": owner_display_name,
                "owner_email": owner_email,
            })

        return items, total

    @staticmethod
    async def get_book_detail(
        db: AsyncSession,
        book_id: UUID,
    ) -> dict | None:
        from app.models.job import Job
        from app.models.llm_run import LlmRun
        from app.models.ocr_result import OcrResult

        book_result = await db.execute(select(Book).where(Book.id == book_id))
        book = book_result.scalar_one_or_none()
        if book is None:
            return None

        owner = await db.get(User, book.owner_id)

        meta_result = await db.execute(
            select(BookMetadata).where(BookMetadata.book_id == book_id)
        )
        metadata = meta_result.scalar_one_or_none()

        pages_result = await db.execute(
            select(Page)
            .where(Page.book_id == book_id)
            .order_by(Page.page_number)
        )
        pages = pages_result.scalars().all()

        page_ids = [p.id for p in pages]
        ocr_by_page = {}
        if page_ids:
            ocr_results_raw = await db.execute(
                select(OcrResult).where(OcrResult.page_id.in_(page_ids))
            )
            ocr_by_page = {r.page_id: r for r in ocr_results_raw.scalars().all()}

        page_details = []
        for p in pages:
            ocr = ocr_by_page.get(p.id)
            page_details.append({
                "id": p.id,
                "page_number": p.page_number,
                "image_url": f"/api/pages/{p.id}/image",
                "ocr_text": ocr.corrected_text if ocr and ocr.corrected_text else (ocr.raw_text if ocr else None),
                "ocr_confidence": ocr.confidence if ocr else None,
            })

        jobs_result = await db.execute(
            select(Job).where(Job.book_id == book_id).order_by(Job.created_at.desc())
        )
        jobs = jobs_result.scalars().all()

        job_ids = [j.id for j in jobs if j.id is not None]
        llm_runs = []
        if job_ids:
            runs_result = await db.execute(
                select(LlmRun)
                .where(LlmRun.job_id.in_(job_ids))
                .order_by(LlmRun.created_at.desc())
            )
            llm_runs = runs_result.scalars().all()

        return {
            "book": book,
            "owner_display_name": owner.display_name if owner else None,
            "owner_email": owner.email if owner else None,
            "metadata": metadata,
            "pages": page_details,
            "jobs": jobs,
            "llm_runs": llm_runs,
        }

    @staticmethod
    async def get_filter_options(
        db: AsyncSession,
        *,
        owner_id: UUID | None = None,
        public_only: bool = False,
    ) -> dict:
        book_filter = []
        if owner_id is not None:
            book_filter.append(Book.owner_id == owner_id)
        if public_only:
            book_filter.append(Book.status.in_(PUBLIC_BOOK_STATUSES))

        languages_query = select(Book.language).distinct()
        statuses_query = select(Book.status).distinct()
        if book_filter:
            languages_query = languages_query.where(*book_filter)
            statuses_query = statuses_query.where(*book_filter)

        languages_result = await db.execute(languages_query.order_by(Book.language))
        languages = [row[0] for row in languages_result.all()]

        statuses_result = await db.execute(statuses_query.order_by(Book.status))
        statuses = [row[0] for row in statuses_result.all()]

        genre_col = BookMetadata.fields["genre"].astext.label("genre_val")
        genres_query = (
            select(genre_col)
            .join(Book, Book.id == BookMetadata.book_id)
            .distinct()
            .where(genre_col.isnot(None))
        )
        if book_filter:
            genres_query = genres_query.where(*book_filter)
        genres_result = await db.execute(genres_query.order_by(genre_col))
        genres = [row[0] for row in genres_result.all() if row[0]]

        publisher_col = BookMetadata.fields["publisher"].astext.label("publisher_val")
        publishers_query = (
            select(publisher_col)
            .join(Book, Book.id == BookMetadata.book_id)
            .distinct()
            .where(publisher_col.isnot(None))
        )
        if book_filter:
            publishers_query = publishers_query.where(*book_filter)
        publishers_result = await db.execute(publishers_query.order_by(publisher_col))
        publishers = [row[0] for row in publishers_result.all() if row[0]]

        return {
            "languages": languages,
            "statuses": statuses,
            "genres": genres,
            "publishers": publishers,
        }

    @staticmethod
    async def count_low_confidence_fields(
        db: AsyncSession,
        book_id: UUID,
        threshold: float = 0.55,
    ) -> int:
        """Count populated metadata fields whose confidence is below the threshold.

        Used by the UI to surface a "Review needed" hint for books whose LLM
        extraction returned low-confidence answers on one or more fields.
        """
        from app.models.metadata_field_evidence import MetadataFieldEvidence

        result = await db.execute(
            select(func.count(MetadataFieldEvidence.id)).where(
                MetadataFieldEvidence.book_id == book_id,
                MetadataFieldEvidence.confidence.isnot(None),
                MetadataFieldEvidence.confidence < threshold,
                MetadataFieldEvidence.value.isnot(None),
            )
        )
        return int(result.scalar() or 0)
