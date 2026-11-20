import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.media_tokens import (
    issue_media_token,
    page_image_url,
    page_preview_url,
    thumbnail_scope,
)
from app.models.base import uuid
from app.models.book import Book, BookStatus
from app.models.job import Job, JobType, JobStatus
from app.models.ocr_result import OcrResult
from app.models.page import Page
from app.schemas.book import (
    BookDetail,
    BookDetailResponse,
    BookLanguageResponse,
    BookLanguageUpdate,
    BookUploadResponse,
    OcrStatusResponse,
    OcrPageStatus,
    PageResponse,
    PageSelectionRequest,
    PageSelectionResponse,
)
from app.schemas.common import Page as PageEnvelope
from app.schemas.job import JobResponse
from app.schemas.page import PreprocessingConfig
from app.services import pdf_service, storage
from app.services.ocr_service import LANGUAGE_MAP
from app.services.search_service import SearchService
from app.services.stage_manager import StageManager
from app.api.deps import (
    PaginationParams,
    get_audit_context,
    get_current_user,
    get_owned_book_or_404,
    get_pagination,
)
from app.models.user import User
from app.services import admin_service, audit_service
from app.services.audit_service import AuditAction, AuditContext

VALID_LANGUAGES = frozenset(LANGUAGE_MAP.keys())
logger = logging.getLogger(__name__)


def _pre_render_thumbnails(book_id: str, pdf_path: Path, total_pages: int) -> None:
    """Background task: render all thumbnails so the page selector loads instantly."""
    try:
        thumb_dir = storage.thumbnails_dir(book_id)
        pdf_service.render_all_thumbnails(pdf_path, thumb_dir, total_pages)
        logger.info("Pre-rendered %d thumbnails for book %s", total_pages, book_id)
    except Exception:
        logger.exception("Failed to pre-render thumbnails for book %s", book_id)


router = APIRouter()


def _duplicate_job_conflict(job: Job) -> HTTPException:
    """409 for a repeated submission; the id lets the UI resume polling it."""
    return HTTPException(
        status_code=409,
        detail="An identical job is already queued or running for this book",
        headers={"X-Existing-Job-Id": str(job.id)},
    )


@router.post("/upload", response_model=BookUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_book(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    title: str | None = Form(None),
    language: str = Form(""),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    ctx: AuditContext = Depends(get_audit_context),
) -> BookUploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds {settings.max_upload_size_mb} MB limit",
        )

    if not language:
        raise HTTPException(
            status_code=422,
            detail=f"Language is required. Valid options: {sorted(VALID_LANGUAGES)}",
        )

    if language not in VALID_LANGUAGES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported language '{language}'. Valid options: {sorted(VALID_LANGUAGES)}",
        )

    book_id = uuid.uuid4()
    pdf_path = storage.original_pdf_path(str(book_id))
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    try:
        with open(pdf_path, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {settings.max_upload_size_mb} MB limit",
                    )
                f.write(chunk)
    except HTTPException:
        pdf_path.unlink(missing_ok=True)
        raise
    except OSError:
        pdf_path.unlink(missing_ok=True)
        logger.exception("Could not store upload for book %s", book_id)
        raise HTTPException(status_code=500, detail="Could not store the uploaded file")

    try:
        page_count = pdf_service.get_page_count(pdf_path)
    except Exception:
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Invalid or corrupted PDF")

    book = Book(
        id=book_id,
        title=title,
        filename=file.filename,
        language=language,
        total_pages=page_count,
        status=BookStatus.UPLOADED,
        owner_id=user.id,
    )
    db.add(book)
    await db.commit()
    await db.refresh(book)

    await StageManager.initiate_stage(db, book.id, "upload")
    await StageManager.start_stage(db, book.id, "upload")
    await StageManager.complete_stage(db, book.id, "upload")
    await db.commit()

    background_tasks.add_task(_pre_render_thumbnails, str(book_id), pdf_path, page_count)

    await audit_service.record_isolated(
        db,
        action=AuditAction.BOOK_UPLOADED,
        ctx=ctx,
        description=f"Uploaded book {book.title or book.filename}",
        resource_type="book",
        resource_id=book.id,
        resource_label=book.title or book.filename,
        subject_user_id=user.id,
        details={
            "filename": book.filename,
            "language": book.language,
            "total_pages": book.total_pages,
        },
    )

    return BookUploadResponse.model_validate(book)


@router.patch("/{book_id}/language", response_model=BookLanguageResponse)
async def update_book_language(
    body: BookLanguageUpdate,
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    ctx: AuditContext = Depends(get_audit_context),
) -> BookLanguageResponse:
    """Correct a book's language and re-run OCR when pages already exist.

    Language is a page-routing input, not just metadata: a Hindi book stored as
    Telugu is sent to the Telugu model and produces Latin/Telugu rubble
    (learnings/029). Changing it clears OCR derived from the old language and
    keeps the original PDF, page images, and reviewed metadata.
    """
    if body.language not in VALID_LANGUAGES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported language '{body.language}'. Valid options: {sorted(VALID_LANGUAGES)}",
        )

    previous_language = book.language
    updated, job = await admin_service.change_language(
        db,
        book.id,
        body.language,
        requested_by_id=user.id,
    )
    if updated.language != previous_language:
        await audit_service.record_isolated(
            db,
            action=AuditAction.BOOK_LANGUAGE_CHANGED,
            ctx=ctx,
            description=f"Changed the language of book {updated.title or updated.filename} to {updated.language}",
            resource_type="book",
            resource_id=updated.id,
            resource_label=updated.title or updated.filename,
            subject_user_id=updated.owner_id,
            before={"language": previous_language},
            after={"language": updated.language},
            details={"job_id": str(job.id) if job is not None else None},
        )
    return BookLanguageResponse(
        id=updated.id,
        language=updated.language,
        job_id=job.id if job is not None else None,
    )


async def _build_book_detail(
    db: AsyncSession,
    book: Book,
    *,
    owner_display_name: str | None = None,
    owner_email: str | None = None,
) -> BookDetail:
    """Build the shared BookDetail payload (review flags + optional owner fields)."""
    low_conf_count = await SearchService.count_low_confidence_fields(db, book.id, settings.low_confidence_threshold)
    data = {
        **BookDetail.model_validate(book).model_dump(),
        "needs_review": book.status == BookStatus.AWAITING_REVIEW and low_conf_count > 0,
        "low_confidence_count": low_conf_count,
        "thumbnail_token": issue_media_token(*thumbnail_scope(book.id)),
    }
    if owner_display_name is not None:
        data["owner_display_name"] = owner_display_name
    if owner_email is not None:
        data["owner_email"] = owner_email
    return BookDetail.model_validate(data)


@router.get("/{book_id}", response_model=BookDetail)
async def get_book(
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> BookDetail:
    return await _build_book_detail(db, book)


@router.get("/{book_id}/detail", response_model=BookDetailResponse)
async def get_book_detail(
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> BookDetailResponse:
    detail = await SearchService.get_book_detail(db, book.id, book=book)
    if detail is None:
        raise HTTPException(status_code=404, detail="Book not found")

    metadata = detail["metadata"]

    book_detail = await _build_book_detail(
        db,
        book,
        owner_display_name=detail.get("owner_display_name"),
        owner_email=detail.get("owner_email"),
    )

    return BookDetailResponse(
        book=book_detail,
        metadata=metadata.fields if metadata else None,
        metadata_updated_at=metadata.updated_at if metadata else None,
        owner_display_name=detail.get("owner_display_name"),
    )


@router.post("/{book_id}/pages", response_model=PageSelectionResponse)
async def select_pages(
    body: PageSelectionRequest,
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    ctx: AuditContext = Depends(get_audit_context),
) -> PageSelectionResponse:
    """Select pages and enqueue a PAGE_EXTRACTION job to render them.

    Rendering used to block this request. It now runs in the worker with
    per-page progress and cancellation; the response carries the job id.
    """
    book_id = book.id
    if not book.total_pages:
        raise HTTPException(status_code=400, detail="Book has no pages")

    unique_pages = sorted(set(body.selected_pages))
    for pn in unique_pages:
        if pn < 1 or pn > book.total_pages:
            raise HTTPException(
                status_code=422,
                detail=f"Page {pn} out of range (1-{book.total_pages})",
            )

    pdf_path = storage.original_pdf_path(str(book_id))
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail="Original PDF not found")

    duplicate = await admin_service.find_active_job(db, book_id, JobType.PAGE_EXTRACTION)
    if duplicate is not None:
        raise _duplicate_job_conflict(duplicate)

    # Supersede any in-flight job for this book before mutating its pages.
    active_jobs = await db.execute(
        select(Job).where(
            Job.book_id == book_id,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
    )
    revoked: list[tuple[str | None, bool]] = []
    for job in active_jobs.scalars().all():
        revoked.append((job.celery_task_id, job.status == JobStatus.RUNNING))
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.now(timezone.utc)
        job.error_log = "Superseded by a new page selection"
    await db.flush()

    results = await db.execute(select(Page).where(Page.book_id == book_id))
    existing = results.scalars().all()
    for p in existing:
        if p.image_path:
            fp = Path(settings.storage_path) / p.image_path
            fp.unlink(missing_ok=True)
        await db.delete(p)
    await db.flush()

    # Invalidate any downstream stage state from the previous page selection.
    await StageManager.reset_from_stage(db, book_id, "page_selection", "Superseded by a new page selection")

    job = Job(
        book_id=book_id,
        requested_by_id=user.id,
        job_type=JobType.PAGE_EXTRACTION,
        status=JobStatus.QUEUED,
        progress=0.0,
    )
    db.add(job)
    await db.flush()
    book.status = BookStatus.PAGES_SELECTED
    await audit_service.record(
        db,
        action=AuditAction.PAGES_SELECTED,
        ctx=ctx,
        description=f"Selected {len(unique_pages)} pages for book {book.title or book.filename}",
        resource_type="book",
        resource_id=book_id,
        resource_label=book.title or book.filename,
        subject_user_id=book.owner_id,
        details={
            "selected_count": len(unique_pages),
            "page_numbers": unique_pages,
            "superseded_job_count": len(revoked),
            "job_id": str(job.id),
        },
    )
    await db.commit()
    admin_service._revoke_task_ids(revoked)
    await db.refresh(job)

    await StageManager.initiate_stage(db, book_id, "page_selection")
    await StageManager.start_stage(db, book_id, "page_selection")
    await db.commit()

    from app.tasks.page_tasks import render_pages_for_book

    render_pages_for_book.delay(str(job.id), str(book_id), unique_pages)

    return PageSelectionResponse(
        book_id=book_id,
        selected_count=len(unique_pages),
        status=book.status,
        job_id=job.id,
    )


@router.post(
    "/{book_id}/preprocessing",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def apply_preprocessing_all(
    book_id: UUID,
    config: PreprocessingConfig,
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    ctx: AuditContext = Depends(get_audit_context),
) -> JobResponse:
    """Apply one preprocessing config to every page as a background job.

    Replaces the old UI loop that fired one blocking CPU request per page;
    that saturated the API and gave no aggregate progress.
    """
    has_page = (await db.execute(select(Page.id).where(Page.book_id == book.id).limit(1))).scalar_one_or_none()
    if has_page is None:
        raise HTTPException(status_code=400, detail="No pages selected for this book")

    duplicate = await admin_service.find_active_job(db, book.id, JobType.PREPROCESSING)
    if duplicate is not None:
        raise _duplicate_job_conflict(duplicate)

    job = Job(
        book_id=book.id,
        requested_by_id=user.id,
        job_type=JobType.PREPROCESSING,
        status=JobStatus.QUEUED,
        progress=0.0,
    )
    db.add(job)
    await db.flush()
    await audit_service.record(
        db,
        action=AuditAction.PREPROCESSING_APPLIED,
        ctx=ctx,
        description=f"Applied preprocessing to every page of book {book.title or book.filename}",
        resource_type="book",
        resource_id=book.id,
        resource_label=book.title or book.filename,
        subject_user_id=book.owner_id,
        details={"job_id": str(job.id), "config": config.model_dump()},
    )
    await db.commit()
    await db.refresh(job)

    from app.tasks.page_tasks import apply_preprocessing_bulk

    apply_preprocessing_bulk.delay(str(job.id), str(book.id), config.model_dump())

    return JobResponse.model_validate(job)


@router.get("/{book_id}/pages", response_model=PageEnvelope[PageResponse])
async def list_pages(
    include_ocr: bool = Query(default=False),
    pagination: PaginationParams = Depends(get_pagination),
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> PageEnvelope[PageResponse]:
    total = int(await db.scalar(select(func.count(Page.id)).where(Page.book_id == book.id)) or 0)
    result = await db.execute(
        select(Page)
        .where(Page.book_id == book.id)
        .order_by(Page.page_number)
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    pages = result.scalars().all()

    ocr_by_page: dict = {}
    if include_ocr and pages:
        ocr_rows = await db.execute(select(OcrResult).where(OcrResult.page_id.in_([p.id for p in pages])))
        ocr_by_page = {row.page_id: row for row in ocr_rows.scalars().all()}

    items: list[PageResponse] = []
    for page in pages:
        item = PageResponse.model_validate(page)
        item.image_url = page_image_url(page.id)
        item.preview_url = page_preview_url(page.id)
        if include_ocr:
            ocr = ocr_by_page.get(page.id)
            item.ocr_text = ocr.corrected_text if ocr and ocr.corrected_text else (ocr.raw_text if ocr else None)
            item.ocr_confidence = ocr.confidence if ocr else None
        items.append(item)

    return PageEnvelope[PageResponse].create(
        items=items,
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


@router.post("/{book_id}/run-ocr", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def run_ocr(
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    ctx: AuditContext = Depends(get_audit_context),
) -> JobResponse:
    book_id = book.id

    duplicate = await admin_service.find_active_job(db, book_id, JobType.OCR)
    if duplicate is not None:
        raise _duplicate_job_conflict(duplicate)

    if book.status not in (BookStatus.PAGES_SELECTED,):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot run OCR from status '{book.status}'. Re-select pages first.",
        )

    active_jobs = await db.execute(
        select(Job).where(
            Job.book_id == book_id,
            Job.job_type == JobType.OCR,
            Job.status.in_([JobStatus.QUEUED, JobStatus.RUNNING]),
        )
    )
    revoked: list[tuple[str | None, bool]] = []
    for j in active_jobs.scalars().all():
        revoked.append((j.celery_task_id, j.status == JobStatus.RUNNING))
        j.status = JobStatus.CANCELLED
        j.completed_at = datetime.now(timezone.utc)
        j.error_log = "Cancelled: new OCR job submitted"
    await db.flush()

    pages_result = await db.execute(select(Page).where(Page.book_id == book_id))
    pages = pages_result.scalars().all()
    if not pages:
        raise HTTPException(status_code=400, detail="No pages selected for this book")

    job = Job(
        book_id=book_id,
        requested_by_id=user.id,
        job_type=JobType.OCR,
        status=JobStatus.QUEUED,
        progress=0.0,
    )
    db.add(job)
    await db.flush()

    book.status = BookStatus.OCR_RUNNING
    await audit_service.record(
        db,
        action=AuditAction.OCR_REQUESTED,
        ctx=ctx,
        description=f"Started OCR for book {book.title or book.filename}",
        resource_type="book",
        resource_id=book_id,
        resource_label=book.title or book.filename,
        subject_user_id=book.owner_id,
        details={"job_id": str(job.id), "page_count": len(pages)},
    )
    await db.commit()
    admin_service._revoke_task_ids(revoked)
    await db.refresh(job)

    await StageManager.initiate_stage(db, book_id, "ocr")
    await StageManager.start_stage(db, book_id, "ocr")
    await db.commit()

    from app.tasks.ocr_tasks import preprocess_pages_for_book

    preprocess_pages_for_book.delay(str(job.id), str(book_id), book.language)

    return JobResponse.model_validate(job)


@router.get("/{book_id}/ocr-status", response_model=OcrStatusResponse)
async def get_ocr_status(
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> OcrStatusResponse:
    book_id = book.id

    pages_result = await db.execute(select(Page).where(Page.book_id == book_id).order_by(Page.page_number))
    pages = pages_result.scalars().all()

    page_statuses: list[OcrPageStatus] = []
    confidences: list[float] = []

    page_ids = [p.id for p in pages]
    ocr_results_raw = await db.execute(select(OcrResult).where(OcrResult.page_id.in_(page_ids)))
    ocr_by_page = {r.page_id: r for r in ocr_results_raw.scalars().all()}

    for page in pages:
        ocr = ocr_by_page.get(page.id)
        has_ocr = ocr is not None and ocr.raw_text is not None
        conf = ocr.confidence if ocr else None
        if conf is not None:
            confidences.append(conf)
        page_statuses.append(
            OcrPageStatus(
                page_number=page.page_number,
                page_id=page.id,
                has_ocr=has_ocr,
                confidence=conf,
                ocr_error=page.ocr_error,
            )
        )

    ocr_complete = sum(1 for ps in page_statuses if ps.has_ocr)
    avg_conf = sum(confidences) / len(confidences) if confidences else None

    return OcrStatusResponse(
        total_pages=len(pages),
        ocr_complete_count=ocr_complete,
        ocr_pending_count=len(pages) - ocr_complete,
        avg_confidence=avg_conf,
        pages=page_statuses,
    )


@router.get("/{book_id}/jobs", response_model=PageEnvelope[JobResponse])
async def list_jobs(
    pagination: PaginationParams = Depends(get_pagination),
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> PageEnvelope[JobResponse]:
    total = int(await db.scalar(select(func.count(Job.id)).where(Job.book_id == book.id)) or 0)
    result = await db.execute(
        select(Job)
        .where(Job.book_id == book.id)
        .order_by(Job.created_at.desc())
        .offset(pagination.offset)
        .limit(pagination.page_size)
    )
    jobs = result.scalars().all()
    return PageEnvelope[JobResponse].create(
        items=[JobResponse.model_validate(j) for j in jobs],
        total=total,
        page=pagination.page,
        page_size=pagination.page_size,
    )


# ---------------------------------------------------------------------------
# Owner-scoped book management
# ---------------------------------------------------------------------------


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_own_book(
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await admin_service.delete_book(db, book.id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Book not found")


@router.post("/{book_id}/reset")
async def reset_own_book(
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
) -> dict:
    try:
        updated = await admin_service.reset_book(db, book.id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"id": str(updated.id), "status": updated.status}


@router.post("/{book_id}/rerun-ocr", status_code=status.HTTP_201_CREATED)
async def rerun_own_ocr(
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        job = await admin_service.rerun_ocr(db, book.id, requested_by_id=user.id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Book not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "job_id": str(job.id),
        "book_id": str(book.id),
        "status": job.status,
    }


@router.post("/{book_id}/rerun-extraction", status_code=status.HTTP_201_CREATED)
async def rerun_own_extraction(
    book: Book = Depends(get_owned_book_or_404),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> dict:
    try:
        job = await admin_service.rerun_extraction(db, book.id, requested_by_id=user.id)
    except LookupError:
        raise HTTPException(status_code=404, detail="Book not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "job_id": str(job.id),
        "book_id": str(book.id),
        "status": job.status,
    }
