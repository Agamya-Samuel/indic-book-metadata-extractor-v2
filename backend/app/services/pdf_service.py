from pathlib import Path

import fitz


def get_page_count(pdf_path: Path) -> int:
    doc = fitz.open(str(pdf_path))
    count = doc.page_count
    doc.close()
    return count


def render_thumbnail(
    pdf_path: Path,
    page_number: int,
    output_path: Path,
    width: int = 180,
) -> None:
    doc = fitz.open(str(pdf_path))
    page = doc.load_page(page_number - 1)
    zoom = width / page.rect.width
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(output_path))
    doc.close()


def render_full_page(
    pdf_path: Path,
    page_number: int,
    output_path: Path,
    dpi: int = 300,
) -> None:
    doc = fitz.open(str(pdf_path))
    page = doc.load_page(page_number - 1)
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat, alpha=False)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(output_path))
    doc.close()
