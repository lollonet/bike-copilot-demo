from __future__ import annotations

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="APP_",
        extra="ignore",
    )

    db_url: str = Field(
        default="sqlite:///./app.db",
        description="SQLAlchemy database URL",
    )
    out_dir: str = Field(
        default="out",
        description="Directory for generated artefacts (HTML/PDF quotes)",
    )
    prefer_in_stock: bool = Field(
        default=True,
        description="Prefer in-stock offers by default in search",
    )
    synonyms_path: str = Field(
        default="app/synonyms.yaml",
        description="Path to product attribute synonyms YAML",
        # env_prefix="APP_" → resolves APP_SYNONYMS / APP_SYNONYMS_PATH
        validation_alias=AliasChoices("SYNONYMS", "SYNONYMS_PATH"),
    )
    category_synonyms_path: str = Field(
        default="app/category_synonyms.yaml",
        description="Path to category synonyms YAML",
        validation_alias=AliasChoices("CATEGORY_SYNONYMS", "CATEGORY_SYNONYMS_PATH"),
    )
    basic_user: str = Field(default="", description="HTTP basic auth username")
    basic_pass: str = Field(default="", description="HTTP basic auth password")


settings = Settings()
