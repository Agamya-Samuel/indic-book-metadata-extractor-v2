from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class PreprocessingConfig(BaseModel):
    grayscale: bool = True
    brightness: int = Field(default=0, ge=-100, le=100)
    contrast: int = Field(default=0, ge=-100, le=100)
    binarization: Literal["otsu", "adaptive"] | None = None
    adaptive_block_size: int = Field(default=11, ge=3)
    adaptive_c: int = Field(default=2)
    deskew: bool = True
    denoise: bool = False
    denoise_strength: int = Field(default=10, ge=1, le=50)


class PreprocessingResponse(BaseModel):
    page_id: uuid.UUID
    processed_image_url: str
    config_applied: PreprocessingConfig


class BoundingBox(BaseModel):
    x: int
    y: int
    w: int
    h: int


class OcrWord(BaseModel):
    text: str
    confidence: int
    bbox: BoundingBox
    block_num: int
    line_num: int
    word_num: int


class OcrResultResponse(BaseModel):
    page_id: uuid.UUID
    raw_text: str | None
    bounding_boxes: list[OcrWord] | None
    confidence: float | None
    language_detected: str | None
    corrected_text: str | None


class OcrCorrectionRequest(BaseModel):
    corrected_text: str
