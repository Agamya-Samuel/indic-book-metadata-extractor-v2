from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "Indic Book Metadata Extractor"
    debug: bool = False

    # CORS (comma-separated origins)
    cors_origins: str = "http://localhost:3000"

    # Database
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
    default_ocr_language: str = "tel"

    # New Relic
    new_relic_license_key: str = ""
    new_relic_app_name: str = "Indic Book Metadata Extractor"
    new_relic_enabled: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
