from pathlib import Path
import uuid as _uuid

from app.core.config import settings


def _validate_book_id(book_id: str) -> str:
    try:
        _uuid.UUID(book_id)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"Invalid book_id: {book_id}") from exc
    return book_id


def _base() -> Path:
    return Path(settings.storage_path).resolve()


def uploads_dir(book_id: str) -> Path:
    book_id = _validate_book_id(book_id)
    p = _base() / "uploads" / book_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def thumbnails_dir(book_id: str) -> Path:
    book_id = _validate_book_id(book_id)
    p = _base() / "thumbnails" / book_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def pages_dir(book_id: str) -> Path:
    book_id = _validate_book_id(book_id)
    p = _base() / "pages" / book_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def original_pdf_path(book_id: str) -> Path:
    return uploads_dir(book_id) / "original.pdf"


def thumbnail_path(book_id: str, page_number: int) -> Path:
    return thumbnails_dir(book_id) / f"p{page_number:04d}.jpg"


def full_page_path(book_id: str, page_number: int) -> Path:
    return pages_dir(book_id) / f"p{page_number:04d}.png"


def processed_dir(book_id: str) -> Path:
    book_id = _validate_book_id(book_id)
    p = _base() / "processed" / book_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def processed_image_path(book_id: str, page_number: int) -> Path:
    return processed_dir(book_id) / f"p{page_number:04d}_processed.png"


def relative(path: Path) -> str:
    base = _base()
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(base))
    except ValueError:
        raise ValueError(
            f"Path {path} escapes storage root — refusing to process"
        ) from None
