from pathlib import Path

from app.core.config import settings


def _base() -> Path:
    return Path(settings.storage_path)


def uploads_dir(book_id: str) -> Path:
    p = _base() / "uploads" / book_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def thumbnails_dir(book_id: str) -> Path:
    p = _base() / "thumbnails" / book_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def pages_dir(book_id: str) -> Path:
    p = _base() / "pages" / book_id
    p.mkdir(parents=True, exist_ok=True)
    return p


def original_pdf_path(book_id: str) -> Path:
    return uploads_dir(book_id) / "original.pdf"


def thumbnail_path(book_id: str, page_number: int) -> Path:
    return thumbnails_dir(book_id) / f"p{page_number:04d}.jpg"


def full_page_path(book_id: str, page_number: int) -> Path:
    return pages_dir(book_id) / f"p{page_number:04d}.png"


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(_base()))
    except ValueError:
        return str(path)
