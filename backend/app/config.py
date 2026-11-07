"""Application configuration and environment settings."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    app_name: str = "ModelAudit API"
    app_version: str = "0.1.0"
    environment: str = "development"

    max_upload_size_mb: int = 15
    max_pdf_pages: int = 40

    # LLM provider configuration
    llm_provider: str = "gemini"
    llm_model: str = "gemini-3.8-flash"
    llm_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"
    llm_api_key: str = ""

    llm_timeout_seconds: int = 90
    llm_max_retries: int = 3

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
