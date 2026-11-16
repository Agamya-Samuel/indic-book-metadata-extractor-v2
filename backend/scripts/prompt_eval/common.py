"""Shared paths, book discovery and the fixed run configuration.

Everything in this package is driven by ``plans/018-prompt-optimization.md``.
The run configuration is a module constant rather than a flag on purpose:
prompt comparisons are only meaningful when the model and every generation
parameter are held constant.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

GT_ROOT = REPO_ROOT / "datasets" / "ground-truth"
EVAL_ROOT = REPO_ROOT / "datasets" / "evaluation"
CORPUS_ROOT = EVAL_ROOT / "corpus"
BUNDLE_ROOT = EVAL_ROOT / "bundles"
MASK_ROOT = EVAL_ROOT / "masks"
STRESS_ROOT = EVAL_ROOT / "stress"
FEWSHOT_ROOT = EVAL_ROOT / "fewshot"
MANIFEST_PATH = EVAL_ROOT / "manifest.json"
REPORT_ROOT = REPO_ROOT / "benchmarks" / "prompt-eval"

MAX_OCR_CHARS = 2500
# Wide OCR window: metadata can sit past page 12 (measured), so scan further and
# filter afterwards. FRONT_KEEP/TAIL_KEEP bound what the corpus stores so each
# batch's per-page character budget stays usable.
FRONT_PAGES = 24
TAIL_PAGES = 4
# 16 front pages covers a scan whose real front matter starts at page 10 and runs
# into a table of contents at 17-24; capping at 8 measurably dropped
# human-confirmed fields.
FRONT_KEEP = 16
TAIL_KEEP = 4

TRACKS = ("ocr", "clean")

# Fixed for every variant. Changing any of these mid-study invalidates the
# comparison (and evicts Ollama's prompt-prefix cache, per learnings/018).
RUN_CONFIG: dict = {
    "model": "gemma4:e4b",
    "num_ctx": 4096,
    "num_predict": 512,
    "temperature": 0.0,
    "seed": 42,
    "repeat_penalty": 1.0,
    "think": False,
    "fmt": "schema",
    "keep_alive": "30m",
    "num_thread": 3,
}


@dataclass(frozen=True)
class Book:
    language: str
    slug: str
    directory: Path

    @property
    def sample_id(self) -> str:
        return f"{self.language}/{self.slug}"


def now_iso() -> str:
    # timezone.utc (not datetime.UTC) so the harness also runs on the Ubuntu
    # 22.04 benchmark nodes, which ship Python 3.10.
    return datetime.now(timezone.utc).isoformat()


def git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=BACKEND_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        ).stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001 - metadata only
        return "unknown"


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def discover_books(
    languages: list[str] | None = None,
    slugs: list[str] | None = None,
) -> list[Book]:
    """Every ground-truth book that has an ``expected_metadata.json``."""
    books: list[Book] = []
    if not GT_ROOT.exists():
        return books
    wanted_slugs = set(slugs or ())
    for lang_dir in sorted(GT_ROOT.iterdir()):
        if not lang_dir.is_dir():
            continue
        if languages and lang_dir.name not in languages:
            continue
        for book_dir in sorted(lang_dir.iterdir()):
            if not book_dir.is_dir():
                continue
            if not (book_dir / "expected_metadata.json").is_file():
                continue
            if wanted_slugs and book_dir.name not in wanted_slugs:
                continue
            books.append(Book(language=lang_dir.name, slug=book_dir.name, directory=book_dir))
    return books


def load_envelope(book: Book) -> dict:
    return json.loads((book.directory / "expected_metadata.json").read_text(encoding="utf-8"))


def load_expected(book: Book) -> dict:
    envelope = load_envelope(book)
    return envelope.get("expected_metadata", envelope)


def ignored_fields(envelope: dict) -> set[str]:
    """GT fields whose value came from model prefill, not a source.

    Mirrors ``scripts/evaluate_extraction.ignored_fields``: scoring those would
    reward the model for reproducing its own earlier output.
    """
    src = envelope.get("field_source") if isinstance(envelope, dict) else None
    if not isinstance(src, dict):
        return set()
    return {name for name, origin in src.items() if origin == "node_llm_extraction"}


def corpus_path(track: str, book: Book) -> Path:
    return CORPUS_ROOT / track / book.language / f"{book.slug}.json"


def load_corpus(track: str, book: Book) -> dict | None:
    path = corpus_path(track, book)
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest() -> dict:
    if MANIFEST_PATH.is_file():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"generated_at": None, "books": {}, "tracks": list(TRACKS), "holdout": []}


def save_manifest(manifest: dict) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    manifest["generated_at"] = now_iso()
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


def mask_path(track: str) -> Path:
    return MASK_ROOT / f"{track}.json"


def load_mask(track: str) -> dict[str, dict[str, str]]:
    path = mask_path(track)
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8")).get("fields", {})


def page_records(payload: dict) -> list:
    from app.services.batch_routing import PageText

    return [PageText(page_number=int(p["n"]), text=p.get("text") or "") for p in payload.get("pages", [])]


def routed_text(pages: list, batch_name: str) -> str:
    """The exact text production would give this batch for these pages."""
    from app.services.batch_routing import assemble_ocr_text, select_pages_for_batch

    return assemble_ocr_text(select_pages_for_batch(pages, batch_name), MAX_OCR_CHARS)


def batch_field_names(batch_name: str) -> list[str]:
    from app.schemas.metadata import METADATA_BATCHES

    return [f for f in METADATA_BATCHES[batch_name].model_fields if f != "custom_fields"]
