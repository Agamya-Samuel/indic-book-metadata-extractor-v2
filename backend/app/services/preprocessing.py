from pathlib import Path

import cv2
import numpy as np

DEFAULT_PREPROCESSING_CONFIG = {
    "grayscale": True,
    "brightness": 0,
    "contrast": 0,
    "binarization": None,
    "binarization_method": "sauvola",
    "sauvola_window": 25,
    "sauvola_k": 0.2,
    "adaptive_block_size": 11,
    "adaptive_c": 2,
    "deskew": True,
    "denoise": False,
    "denoise_strength": 7,
    "upscale_to_300dpi": True,
    "remove_borders": True,
    "border_content_ratio": 0.85,
    "auto_preprocess": True,
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


def binarize_sauvola(image: np.ndarray, window_size: int = 25, k: float = 0.2, r: float = 128.0) -> np.ndarray:
    """Sauvola binarization — handles uneven paper backgrounds better than Otsu.

    The classic Sauvola formula computes a per-pixel threshold of:
        T(x,y) = m(x,y) * (1 + k * ((s(x,y) / r) - 1))
    where m and s are the local mean and stddev over a ``window_size`` neighborhood.
    For Indic book scans with stained or shadowed paper this preserves text in
    regions where Otsu would clip it to background.
    """
    if len(image.shape) == 3:
        image = to_grayscale(image)
    if image.dtype != np.uint8:
        image = image.astype(np.uint8)

    window = window_size if window_size % 2 == 1 else window_size + 1
    window = max(3, window)

    mean = cv2.boxFilter(image, cv2.CV_32F, (window, window), borderType=cv2.BORDER_REFLECT)
    sqmean = cv2.boxFilter(image.astype(np.float32) ** 2, cv2.CV_32F, (window, window), borderType=cv2.BORDER_REFLECT)
    variance = np.maximum(sqmean - mean * mean, 0.0)
    stddev = np.sqrt(variance)

    threshold = mean * (1.0 + k * ((stddev / r) - 1.0))
    binary = (image.astype(np.float32) > threshold).astype(np.uint8) * 255
    return binary


def upscale_to_dpi(image: np.ndarray, current_dpi: int = 200, target_dpi: int = 300) -> np.ndarray:
    """Upscale an image to the target DPI using cubic interpolation.

    Tesseract's LSTM is tuned around 300 DPI; pages below that lose accuracy on
    small conjuncts and matras. We default ``current_dpi`` to 200 because that is
    what most consumer scanners emit when no DPI metadata is present in the PDF.
    """
    if current_dpi >= target_dpi:
        return image
    scale = target_dpi / float(current_dpi)
    if scale <= 1.0:
        return image
    new_w = int(round(image.shape[1] * scale))
    new_h = int(round(image.shape[0] * scale))
    return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)


def remove_borders(image: np.ndarray, min_content_ratio: float = 0.85) -> np.ndarray:
    """Strip uniform-color margins (page numbers, marginalia, scanner borders).

    Walks inward from each edge; if a strip of pixels is more than ``min_content_ratio``
    uniform (white in a light-mode page, black in dark mode), it's cropped away.
    Designed for a few-pixel-to-few-cm margins, not for full-page blank borders.
    """
    if image is None or image.size == 0:
        return image

    if len(image.shape) == 3:
        gray = to_grayscale(image)
    else:
        gray = image

    h, w = gray.shape[:2]
    if h < 20 or w < 20:
        return image

    median = float(np.median(gray))
    is_dark_mode = median < 128.0

    strip_h = max(8, h // 40)
    strip_w = max(8, w // 40)

    def _is_uniform(strip: np.ndarray) -> bool:
        if strip.size == 0:
            return True
        if is_dark_mode:
            return float(np.mean(strip)) < 32.0
        return float(np.mean(strip)) > 223.0

    top, bottom = 0, h
    while top < bottom - 4 and _is_uniform(gray[top:top + strip_h, :]):
        top += strip_h
    while bottom > top + 4 and _is_uniform(gray[bottom - strip_h:bottom, :]):
        bottom -= strip_h

    left, right = 0, w
    while left < right - 4 and _is_uniform(gray[:, left:left + strip_w]):
        left += strip_w
    while right > left + 4 and _is_uniform(gray[:, right - strip_w:right]):
        right -= strip_w

    if top == 0 and bottom == h and left == 0 and right == w:
        return image

    content_h = bottom - top
    content_w = right - left
    if content_h < h * 0.3 or content_w < w * 0.3:
        return image

    return image[top:bottom, left:right]


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


def denoise(image: np.ndarray, strength: int = 7) -> np.ndarray:
    """Non-local means denoising.

    Strength kept low (default 7, max ~10) to avoid eroding the shiro-rekha line
    that joins Devanagari/Telugu letters into syllables — a known Tesseract failure
    mode on Indic scripts after heavy denoise.
    """
    if len(image.shape) == 3:
        return cv2.fastNlMeansDenoisingColored(image, None, strength, strength, 7, 21)
    return cv2.fastNlMeansDenoising(image, None, strength, 7, 21)


def run_pipeline(image_path: Path, config: dict, output_path: Path) -> Path:
    merged = {**DEFAULT_PREPROCESSING_CONFIG, **(config or {})}

    image = cv2.imread(str(image_path))
    if image is None:
        raise ValueError(f"Cannot read image: {image_path}")

    if merged.get("upscale_to_300dpi"):
        image = upscale_to_dpi(image, current_dpi=200, target_dpi=300)

    if merged.get("grayscale"):
        image = to_grayscale(image)

    brightness = merged.get("brightness", 0)
    contrast = merged.get("contrast", 0)
    if brightness != 0 or contrast != 0:
        image = adjust_brightness_contrast(image, brightness, contrast)

    if merged.get("denoise"):
        image = denoise(image, merged.get("denoise_strength", 7))

    binarization = merged.get("binarization")
    if binarization == "otsu":
        image = binarize_otsu(image)
    elif binarization == "adaptive":
        image = binarize_adaptive(
            image,
            merged.get("adaptive_block_size", 11),
            merged.get("adaptive_c", 2),
        )
    elif binarization == "sauvola":
        image = binarize_sauvola(
            image,
            merged.get("sauvola_window", 25),
            merged.get("sauvola_k", 0.2),
        )

    if merged.get("deskew"):
        image = deskew(image)

    if merged.get("remove_borders"):
        image = remove_borders(image, merged.get("border_content_ratio", 0.85))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), image)
    return output_path