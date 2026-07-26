from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    app_name: str = "SafeOps AI API"
    app_version: str = "0.1.0"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    llm_model: str = "gpt-5-mini"
    llm_api_key: SecretStr | None = None
    llm_base_url: str | None = None
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2

    prometheus_base_url: str = "http://127.0.0.1:9090"
    jaeger_base_url: str = "http://127.0.0.1:16686"
    observability_timeout_seconds: float = 10.0

    prometheus_base_url: str = "http://127.0.0.1:9090"
    jaeger_base_url: str = "http://127.0.0.1:16686"
    observability_timeout_seconds: float = 10.0

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached application settings instance."""

    return Settings()