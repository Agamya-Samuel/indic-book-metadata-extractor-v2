from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class PreprocessingConfig(BaseModel):
    grayscale: bool = True
    brightness: int = Field(default=0, ge=-100, le=100)
    contrast: int = Field(default=0, ge=-100, le=100)
    binarization: Literal["otsu", "adaptive", "sauvola", "none"] | None = None
    adaptive_block_size: int = Field(default=11, ge=3)
    adaptive_c: int = Field(default=2)
    deskew: bool = True
    denoise: bool = False
    denoise_strength: int = Field(default=7, ge=1, le=50)
    # Advanced operations that were previously unreachable from the API.
    upscale_to_300dpi: bool = True
    remove_borders: bool = True
    border_content_ratio: float = Field(default=0.85, ge=0.0, le=1.0)
    sauvola_window: int = Field(default=25, ge=3)
    sauvola_k: float = Field(default=0.2)
    auto_preprocess: bool = True
    # Manual rotation. Coarse applies first, fine (±15°) applies after deskew.
    rotation: int = 0
    rotation_angle: float = Field(default=0.0, ge=-15.0, le=15.0)


class PreprocessingResponse(BaseModel):
    page_id: uuid.UUID
    processed_image_url: str
    config_applied: PreprocessingConfig


class PreprocessingPreviewResponse(BaseModel):
    page_id: uuid.UUID
    preview_url: str


class BoundingBox(BaseModel):
    x: int
    y: int
    w: int
    h: int


class OcrWord(BaseModel):
    text: str
    confidence: float
    bbox: BoundingBox
    block_num: int
    line_num: int
    word_num: int


class OcrResultResponse(BaseModel):
    page_id: uuid.UUID
    raw_text: str | None
    bounding_boxes: list[OcrWord] | None = None
    confidence: float | None
    language_detected: str | None
    corrected_text: str | None


class OcrCorrectionRequest(BaseModel):
    corrected_text: str
