from pydantic_settings import BaseSettings

# Production extraction model. Thinking models must use Ollama's native
# /api/chat (the OpenAI-compatible /v1 path drops think:false).
DEFAULT_LLM_MODEL = "gemma4:e4b"


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
    # Force extraction through Ollama's native /api/chat for non-thinking
    # models too. Thinking models (gemma4) always use it regardless of this
    # flag, because the /v1 path drops `think:false` and they return empty
    # content there. Off by default so phi4-mini keeps the /v1 path.
    llm_native_endpoint: bool = False

    # Storage
    storage_path: str = "/app/storage"

    # Upload limits
    max_upload_size_mb: int = 200
    # A running job older than this is treated as lost (no worker will finish it).
    stale_job_minutes: int = 90
    stale_job_reaper_enabled: bool = True

    # Authentication
    jwt_secret_key: str = "dev-insecure-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    email_verification_expire_hours: int = 24
    password_reset_expire_minutes: int = 60
    password_min_length: int = 10
    cookie_secure: bool = False
    cookie_domain: str = ""
    frontend_url: str = "http://localhost:3000"

    # Registration moderation. When True, new signups start `pending` and need
    # admin approval; when False, signups are auto-approved (open registration).
    registration_requires_approval: bool = True

    # Email delivery (SMTP)
    smtp_enabled: bool = False
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""
    smtp_starttls: bool = True
    smtp_use_tls: bool = False
    smtp_timeout: int = 15

    # OCR
    tesseract_cmd: str = "tesseract"
    tesseract_oem: int = 1
    tesseract_tessdata_dir: str = ""
    ocr_batch_size: int = 10
    ocr_thread_workers: int = 4
    ocr_render_dpi: int = 300

    # OCR preprocessing (Tier 1)
    # Sauvola binarization + denoise can erode the shiro-rekha in Devanagari,
    # so both are off by default; enable per page via preprocessing_config.
    ocr_binarization: str = "sauvola"  # sauvola / otsu / adaptive / none
    ocr_denoise_strength: int = 7
    ocr_upscale_dpi: int = 300

    # OCR models (Tier 2 + Tier 3)
    # Custom Tesseract models go in TESSERACT_TESSDATA_DIR (a full tessdata
    # directory including every language the configured OCR path loads).
    # Telugu line OCR engine. "tesseract" (default) keeps today's behaviour;
    # "line_model" selects harsha-desaraju/telugu-ocr-model (measured Telugu
    # CER 0.16 vs Tesseract 0.40). Hindi and English always use Tesseract.
    # The line model needs torch/transformers plus vendored weights — never
    # downloaded at runtime — and falls back to Tesseract per page on error.
    ocr_tel_engine: str = "tesseract"
    ocr_line_model_name: str = "harsha-desaraju/telugu-ocr-model"
    ocr_line_model_decode: str = "ctc"
    # The line model emits no word confidences. Store a conservative value so
    # the review UI warns instead of showing a false green.
    ocr_line_model_confidence: float = 50.0

    # OCR dictionaries (Tier 4)
    ocr_use_dictionary: str = ""  # comma-separated language codes, e.g. "hin,tel"

    # Page-level script routing. When the Telugu line model returns a
    # Latin-dominated page (front matter / cover), re-run it through Tesseract
    # and keep the better-coverage result. Pure Telugu pages are untouched.
    ocr_script_routing: bool = True

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
    # surfaces a "Review needed" hint in the UI. Set below the LLM baseline
    # (0.6) so only genuinely low-confidence fields surface the badge.
    low_confidence_threshold: float = 0.55

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
