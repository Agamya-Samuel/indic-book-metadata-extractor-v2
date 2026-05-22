from pathlib import Path

import cv2
import numpy as np

DEFAULT_PREPROCESSING_CONFIG = {
    "grayscale": True,
    "brightness": 0,
    "contrast": 0,
    "binarization": None,
    "adaptive_block_size": 11,
    "adaptive_c": 2,
    "deskew": True,
    "denoise": False,
    "denoise_strength": 10,
}


def to_grayscale(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 2:
        return image
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)


def adjust_brightness_contrast(
    image: np.ndarray, brightness: int = 0, contrast: int = 0
) -> np.ndarray:
    if brightness == 0 and contrast == 0:
        return image
    alpha = 1.0 + contrast / 100.0
    beta = float(brightness)
    return cv2.convertScaleAbs(image, alpha=alpha, beta=beta)


def binarize_otsu(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 3:
        image = to_grayscale(image)
    _, result = cv2.threshold(image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return result


def binarize_adaptive(
    image: np.ndarray, block_size: int = 11, c: int = 2
) -> np.ndarray:
    if len(image.shape) == 3:
        image = to_grayscale(image)
    block_size = block_size if block_size % 2 == 1 else block_size + 1
    block_size = max(3, block_size)
    return cv2.adaptiveThreshold(
        image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, block_size, c
    )


def deskew(image: np.ndarray) -> np.ndarray:
    if len(image.shape) == 3:
        gray = to_grayscale(image)
    else:
        gray = image

    thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]

    coords = np.column_stack(np.where(thresh > 0))
    if len(coords) < 10:
        return image

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)
    else:
        angle = -angle

    if abs(angle) < 0.5:
        return image

    h, w = image.shape[:2]
    center = (w // 2, h // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        image,
        matrix,
        (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated


def denoise(image: np.ndarray, strength: int = 10) -> np.ndarray:
    if len(image.shape) == 3:
        return cv2.fastNlMeansDenoisingColored(image, None, strength, strength, 7, 21)
    return cv2.fastNlMeansDenoising(image, None, strength, 7, 21)


def run_pipeline(image_path: Path, config: dict, output_path: Path) -> Path:
    merged = {**DEFAULT_PREPROCESSING_CONFIG, **(config or {})}

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Cannot read image: {image_path}")

    if merged.get("grayscale"):
        image = to_grayscale(image)

    brightness = merged.get("brightness", 0)
    contrast = merged.get("contrast", 0)
    if brightness != 0 or contrast != 0:
        image = adjust_brightness_contrast(image, brightness, contrast)

    if merged.get("denoise"):
        image = denoise(image, merged.get("denoise_strength", 10))

    binarization = merged.get("binarization")
    if binarization == "otsu":
        image = binarize_otsu(image)
    elif binarization == "adaptive":
        image = binarize_adaptive(
            image,
            merged.get("adaptive_block_size", 11),
            merged.get("adaptive_c", 2),
        )

    if merged.get("deskew"):
        image = deskew(image)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image)
    return output_path
