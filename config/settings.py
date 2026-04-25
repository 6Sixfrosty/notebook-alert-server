from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    app_env: str = Field(default="development", validation_alias="APP_ENV")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
    )
    app_name: str = Field(default="Alerta dos Notebooks", validation_alias="APP_NAME")
    app_version: str = Field(default="1.0.0", validation_alias="APP_VERSION")
    api_token: str = Field(validation_alias="API_TOKEN", repr=False)
    database_url: str = Field(validation_alias="DATABASE_URL", repr=False)
    database_name: str = Field(
        default="alerta_dos_notebooks",
        validation_alias="DATABASE_NAME",
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    @field_validator(
        "app_env",
        "app_name",
        "app_version",
        "api_token",
        "database_url",
        "database_name",
        mode="before",
    )
    @classmethod
    def required_string_must_not_be_blank(cls, value: object, info):
        if not isinstance(value, str) or not value.strip():
            field_name = str(info.field_name or "").upper()
            raise ValueError(f"{field_name} is required and cannot be empty.")
        return value.strip()

    @field_validator("log_level", mode="before")
    @classmethod
    def normalize_log_level(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("LOG_LEVEL is required and cannot be empty.")
        return value.strip().upper()


@lru_cache
def get_settings() -> Settings:
    return Settings()
