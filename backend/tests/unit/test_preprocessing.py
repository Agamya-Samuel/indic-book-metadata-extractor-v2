from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from app.services.preprocessing import (
    adjust_brightness_contrast,
    binarize_adaptive,
    binarize_otsu,
    binarize_sauvola,
    denoise,
    deskew,
    remove_borders,
    run_pipeline,
    to_grayscale,
    upscale_to_dpi,
)


def _white_image(h: int = 200, w: int = 300) -> np.ndarray:
    return np.ones((h, w, 3), dtype=np.uint8) * 255


def _white_gray(h: int = 200, w: int = 300) -> np.ndarray:
    return np.ones((h, w), dtype=np.uint8) * 255


def _dark_image(h: int = 200, w: int = 300) -> np.ndarray:
    return np.zeros((h, w, 3), dtype=np.uint8)


class TestToGrayscale:
    def test_rgb_image(self):
        img = _white_image()
        result = to_grayscale(img)
        assert result.ndim == 2
        assert result.shape == (200, 300)

    def test_already_grayscale(self):
        img = _white_gray()
        result = to_grayscale(img)
        assert result is img


class TestAdjustBrightnessContrast:
    def test_positive_brightness(self):
        img = _white_gray()
        result = adjust_brightness_contrast(img, brightness=50)
        assert result.mean() >= img.mean()

    def test_positive_contrast(self):
        img = np.full((100, 100), 128, dtype=np.uint8)
        result = adjust_brightness_contrast(img, contrast=50)
        assert result.mean() != 128 or contrast == 0

    def test_noop(self):
        img = _white_gray()
        result = adjust_brightness_contrast(img, brightness=0, contrast=0)
        assert np.array_equal(result, img)


class TestBinarizeOtsu:
    def test_returns_binary(self):
        img = _white_gray()
        result = binarize_otsu(img)
        unique = set(np.unique(result))
        assert unique.issubset({0, 255})

    def test_rgb_input_converts(self):
        img = _white_image()
        result = binarize_otsu(img)
        assert result.ndim == 2


class TestBinarizeAdaptive:
    def test_returns_binary(self):
        img = _white_gray()
        result = binarize_adaptive(img, block_size=11, c=2)
        unique = set(np.unique(result))
        assert unique.issubset({0, 255})

    def test_even_blocksize_corrected(self):
        img = _white_gray()
        result = binarize_adaptive(img, block_size=10, c=2)
        assert result.ndim == 2

    def test_small_blocksize_clamped(self):
        img = _white_gray()
        result = binarize_adaptive(img, block_size=1, c=2)
        assert result.ndim == 2

    def test_rgb_input_converts(self):
        img = _white_image()
        result = binarize_adaptive(img)
        assert result.ndim == 2


class TestDeskew:
    def test_no_rotation(self):
        img = _white_gray()
        result = deskew(img)
        assert result.shape == img.shape

    def test_few_pixels(self):
        img = _white_gray()
        img[0, 0] = 0
        result = deskew(img)
        assert np.array_equal(result, img)

    def test_rgb_input(self):
        img = _white_image()
        result = deskew(img)
        assert result.shape[:2] == (200, 300)

    def test_with_rotation(self):
        img = _white_gray()
        center = (150, 100)
        matrix = cv2.getRotationMatrix2D(center, 3.0, 1.0)
        rotated = cv2.warpAffine(img, matrix, (300, 200), borderValue=255)
        black_rect = np.zeros((40, 100), dtype=np.uint8)
        rotated[80:120, 100:200] = black_rect
        result = deskew(rotated)
        assert result.shape == rotated.shape


class TestDenoise:
    def test_color_image(self):
        img = _white_image()
        result = denoise(img, strength=10)
        assert result.shape == img.shape
        assert result.dtype == np.uint8

    def test_gray_image(self):
        img = _white_gray()
        result = denoise(img, strength=10)
        assert result.shape == img.shape
        assert result.dtype == np.uint8


class TestRunPipeline:
    def test_full_pipeline(self, tmp_path):
        img = _white_gray()
        img[50:150, 50:250] = 0
        input_path = tmp_path / "input.png"
        output_path = tmp_path / "output.png"
        cv2.imwrite(str(input_path), img)

        config = {
            "grayscale": True,
            "brightness": 10,
            "contrast": 10,
            "binarization": "otsu",
            "deskew": True,
            "denoise": False,
        }
        result = run_pipeline(input_path, config, output_path)
        assert result.exists()
        loaded = cv2.imread(str(result), cv2.IMREAD_UNCHANGED)
        assert loaded is not None

    def test_default_config(self, tmp_path):
        img = _white_image()
        input_path = tmp_path / "input.png"
        output_path = tmp_path / "output.png"
        cv2.imwrite(str(input_path), img)

        result = run_pipeline(input_path, {}, output_path)
        assert result.exists()

    def test_invalid_path(self, tmp_path):
        input_path = tmp_path / "nonexistent.png"
        output_path = tmp_path / "output.png"
        with pytest.raises(ValueError, match="Cannot read image"):
            run_pipeline(input_path, {}, output_path)

    def test_creates_parent_dirs(self, tmp_path):
        img = _white_image()
        input_path = tmp_path / "input.png"
        output_path = tmp_path / "nested" / "dir" / "output.png"
        cv2.imwrite(str(input_path), img)

        run_pipeline(input_path, {}, output_path)
        assert output_path.exists()


class TestBinarizeSauvola:
    def test_returns_binary(self):
        img = _white_gray()
        img[80:120, 80:220] = 0
        result = binarize_sauvola(img)
        unique = set(np.unique(result))
        assert unique.issubset({0, 255})

    def test_rgb_input(self):
        img = _white_image()
        result = binarize_sauvola(img)
        assert result.ndim == 2

    def test_handles_uneven_background(self):
        # Gradient background (simulated stained paper)
        h, w = 100, 200
        gradient = np.tile(np.linspace(80, 180, w, dtype=np.uint8), (h, 1))
        result = binarize_sauvola(gradient)
        assert set(np.unique(result)).issubset({0, 255})

    def test_even_window_corrected(self):
        img = _white_gray()
        result = binarize_sauvola(img, window_size=20)
        assert result.ndim == 2


class TestUpscaleToDpi:
    def test_upscale_below_target(self):
        img = _white_gray(200, 300)
        result = upscale_to_dpi(img, current_dpi=200, target_dpi=300)
        assert result.shape == (300, 450)

    def test_no_change_at_or_above_target(self):
        img = _white_gray(200, 300)
        result = upscale_to_dpi(img, current_dpi=300, target_dpi=300)
        assert result.shape == img.shape
        result = upscale_to_dpi(img, current_dpi=600, target_dpi=300)
        assert result.shape == img.shape


class TestRemoveBorders:
    def test_no_borders_no_change(self):
        img = _white_gray()
        img[20:180, 20:280] = 0
        result = remove_borders(img)
        assert result.shape == img.shape

    def test_strips_uniform_margin(self):
        img = np.ones((400, 600), dtype=np.uint8) * 255
        img[80:320, 100:500] = 0
        result = remove_borders(img)
        assert result.shape[0] < img.shape[0] or result.shape[1] < img.shape[1]

    def test_tiny_image_unchanged(self):
        img = _white_gray(10, 10)
        result = remove_borders(img)
        assert result.shape == img.shape

    def test_handles_rgb(self):
        img = _white_image()
        img[40:160, 40:260] = 0
        result = remove_borders(img)
        assert result.ndim in (2, 3)
