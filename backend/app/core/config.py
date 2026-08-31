from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "Indic Book Metadata Extractor"
    debug: bool = False

    # CORS (comma-separated origins)
    cors_origins: str = "http://localhost:3000"

    # Database — set via DATABASE_URL env var in production
    # Local dev default only.
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/indic_books"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    # Ollama
    ollama_url: str = "http://localhost:11434"

    # Storage
    storage_path: str = "/app/storage"

    # Upload limits
    max_upload_size_mb: int = 200

    # OCR
    tesseract_cmd: str = "tesseract"
    tesseract_oem: int = 1
    tesseract_tessdata_dir: str = ""
    default_ocr_language: str = "tel"
    ocr_batch_size: int = 10
    ocr_thread_workers: int = 4
    ocr_render_dpi: int = 300

    # OCR preprocessing (Tier 1)
    # Disabled by default — Sauvola binarization + denoise can erode shiro-rekha
    # in Devanagari, causing conjunct misrecognition. Enable per-book via
    # preprocessing_config or set OCR_AUTO_PREPROCESS=true to apply globally.
    ocr_auto_preprocess: bool = False
    ocr_binarization: str = "sauvola"  # sauvola / otsu / adaptive / none
    ocr_denoise_strength: int = 7
    ocr_upscale_dpi: int = 300

    # OCR models (Tier 2 + Tier 3)
    ocr_custom_model_dir: str = ""

    # OCR dictionaries (Tier 4)
    ocr_use_dictionary: str = ""  # comma-separated language codes, e.g. "hin,tel"

    # OCR post-processing (Tier 5)
    ocr_postprocess: bool = True
    ocr_low_conf_retry: bool = True
    ocr_low_conf_threshold: int = 40

    # New Relic
    new_relic_enabled: bool = False
    new_relic_license_key: str = ""
    new_relic_app_name: str = "Indic Book Metadata Extractor"
    new_relic_environment: str = "production"
    new_relic_distributed_tracing_enabled: bool = True
    new_relic_log: str = "error"
    new_relic_config_file: str = "newrelic.ini"
    new_relic_monitor_mode: bool = True
    new_relic_developer_mode: bool = False

    # Wikibase property mapping (JSON file mapping Wikidata P-IDs to local P-IDs)
    property_mapping_path: str = "/app/storage/property-mapping.json"

    # Threshold below which a metadata field is considered "low confidence" and
    # surfaces a "Review needed" hint in the UI.
    low_confidence_threshold: float = 0.70

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()