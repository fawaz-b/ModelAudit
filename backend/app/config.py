"""Application configuration and environment settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration loaded from environment variables."""

    app_name: str = "ModelAudit API"
    app_version: str = "0.1.0"
    environment: str = "development"
    max_upload_size_mb: int = 15
    max_pdf_pages: int = 40

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
