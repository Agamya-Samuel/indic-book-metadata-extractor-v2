from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.models.ocr_result import OcrResult
from app.models.page import Page
from app.schemas.page import (
    OcrCorrectionRequest,
    OcrResultResponse,
    PreprocessingConfig,
    PreprocessingResponse,
)
from app.services import storage
from app.services import preprocessing as prep_svc

router = APIRouter()


async def _get_page(page_id: UUID, db: AsyncSession) -> Page:
    result = await db.execute(select(Page).where(Page.id == page_id))
    page = result.scalar_one_or_none()
    if page is None:
        raise HTTPException(status_code=404, detail="Page not found")
    return page


@router.put("/{page_id}/preprocessing", response_model=PreprocessingResponse)
async def update_preprocessing(
    page_id: UUID,
    config: PreprocessingConfig,
    db: AsyncSession = Depends(get_db),
) -> PreprocessingResponse:
    page = await _get_page(page_id, db)

    if not page.image_path:
        raise HTTPException(status_code=400, detail="Page has no source image")

    source_image = Path(settings.storage_path) / page.image_path
    if not source_image.exists():
        raise HTTPException(status_code=404, detail="Source image file not found")

    output_path = storage.processed_image_path(str(page.book_id), page.page_number)
    try:
        prep_svc.run_pipeline(source_image, config.model_dump(), output_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Preprocessing failed: {e}")

    page.preprocessing_config = config.model_dump()
    page.processed_image_path = storage.relative(output_path)
    await db.commit()
    await db.refresh(page)

    image_url = f"/api/pages/{page_id}/image"

    return PreprocessingResponse(
        page_id=page.id,
        processed_image_url=image_url,
        config_applied=config,
    )


@router.get("/{page_id}/image")
async def get_page_image(
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    page = await _get_page(page_id, db)

    if page.processed_image_path:
        processed = Path(settings.storage_path) / page.processed_image_path
        if processed.exists():
            return FileResponse(processed, media_type="image/png")

    if page.image_path:
        original = Path(settings.storage_path) / page.image_path
        if original.exists():
            return FileResponse(original, media_type="image/png")

    raise HTTPException(status_code=404, detail="Page image not found")


@router.get("/{page_id}/ocr", response_model=OcrResultResponse)
async def get_ocr_result(
    page_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> OcrResultResponse:
    page = await _get_page(page_id, db)

    result = await db.execute(select(OcrResult).where(OcrResult.page_id == page_id))
    ocr = result.scalar_one_or_none()
    if ocr is None:
        raise HTTPException(status_code=404, detail="OCR result not found")

    words = None
    if ocr.bounding_boxes and "words" in ocr.bounding_boxes:
        words = ocr.bounding_boxes["words"]

    return OcrResultResponse(
        page_id=page.id,
        raw_text=ocr.raw_text,
        bounding_boxes=words,
        confidence=ocr.confidence,
        language_detected=ocr.language_detected,
        corrected_text=ocr.corrected_text,
    )


@router.put("/{page_id}/ocr", response_model=OcrResultResponse)
async def update_ocr_correction(
    page_id: UUID,
    body: OcrCorrectionRequest,
    db: AsyncSession = Depends(get_db),
) -> OcrResultResponse:
    page = await _get_page(page_id, db)

    result = await db.execute(select(OcrResult).where(OcrResult.page_id == page_id))
    ocr = result.scalar_one_or_none()
    if ocr is None:
        raise HTTPException(status_code=404, detail="OCR result not found")

    ocr.corrected_text = body.corrected_text
    await db.commit()
    await db.refresh(ocr)

    words = None
    if ocr.bounding_boxes and "words" in ocr.bounding_boxes:
        words = ocr.bounding_boxes["words"]

    return OcrResultResponse(
        page_id=page.id,
        raw_text=ocr.raw_text,
        bounding_boxes=words,
        confidence=ocr.confidence,
        language_detected=ocr.language_detected,
        corrected_text=ocr.corrected_text,
    )
