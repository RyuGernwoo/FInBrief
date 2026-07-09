"""Runtime configuration for the FinBrief API."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "FinBrief"
    app_version: str = "0.1.0"
    app_env: Literal["local", "test", "dev", "prod"] = "local"
    api_v1_prefix: str = "/api/v1"
    log_level: str = "INFO"
    default_timezone: str = "Asia/Seoul"
    enable_mock_data: bool = True

    supabase_url: str | None = None
    supabase_anon_key: SecretStr | None = None
    supabase_service_role_key: SecretStr | None = None
    supabase_db_schema: str = "public"

    litellm_model: str = "upstage/solar-pro"
    litellm_fallback_model: str | None = None
    upstage_api_key: SecretStr | None = None

    langfuse_enabled: bool = False
    langfuse_public_key: str | None = None
    langfuse_secret_key: SecretStr | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    fred_api_key: SecretStr | None = None
    ecos_api_key: SecretStr | None = None
    news_rss_urls: list[str] = Field(default_factory=list)

    discord_webhook_url: SecretStr | None = None
    slack_webhook_url: SecretStr | None = None
    delivery_dry_run: bool = True

    @field_validator("api_v1_prefix")
    @classmethod
    def validate_api_prefix(cls, value: str) -> str:
        if not value.startswith("/"):
            raise ValueError("api_v1_prefix must start with '/'")
        return value.rstrip("/") or "/"

    @field_validator("news_rss_urls", mode="before")
    @classmethod
    def split_news_rss_urls(cls, value: object) -> object:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    def public_dict(self) -> dict[str, object]:
        """Return non-secret settings that are safe to expose in API responses."""

        return {
            "app_name": self.app_name,
            "app_version": self.app_version,
            "app_env": self.app_env,
            "api_v1_prefix": self.api_v1_prefix,
            "log_level": self.log_level,
            "default_timezone": self.default_timezone,
            "enable_mock_data": self.enable_mock_data,
            "langfuse_enabled": self.langfuse_enabled,
            "delivery_dry_run": self.delivery_dry_run,
        }


@lru_cache
def get_settings() -> Settings:
    """Return cached runtime settings."""

    return Settings()
