from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Application
    app_name: str = "Indic Book Metadata Extractor"
    debug: bool = True

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/indic_books"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Ollama
    ollama_url: str = "http://localhost:11434"

    # Storage
    storage_path: str = "/app/storage"

    # Upload limits
    max_upload_size_mb: int = 200

    # OCR
    tesseract_cmd: str = "tesseract"
    default_ocr_language: str = "tel"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
