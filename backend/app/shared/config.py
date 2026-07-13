from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment configuration. Secrets are never represented in API responses."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TSUCHIBOT_",
        extra="ignore",
        case_sensitive=False,
    )

    env: str = "development"
    log_level: str = "INFO"
    shared_password: str = "change-me"
    session_secret: str = "development-only-session-secret-change-me"
    session_secure: bool = False
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    cors_origins: str = "http://localhost:3000"
    database_url: str | None = None
    github_repository: str | None = None
    github_token: str | None = None
    github_workflow: str = "explore.yml"
    jimoty_max_pages: int = Field(default=1, ge=1, le=20)
    jimoty_request_interval_seconds: float = Field(default=1.0, ge=0.5, le=60)
    gemini_api_key: str | None = None
    gemini_product_analysis_model: str = "gemini-3.5-flash"
    gemini_timeout_seconds: float = Field(default=60, ge=1, le=180)
    mercari_evidence_days: int = Field(default=90, ge=1, le=365)
    mercari_minimum_sold_comparables: int = Field(default=3, ge=1, le=50)
    mercari_sold_result_limit: int = Field(default=50, ge=1, le=50)
    mercari_active_result_limit: int = Field(default=50, ge=1, le=50)
    browser_request_interval_seconds: float = Field(default=4, ge=2, le=60)
    browser_detail_limit_per_query: int = Field(default=10, ge=1, le=20)
    browser_navigation_timeout_seconds: float = Field(default=30, ge=5, le=120)
    model_visual_search_threshold: float = Field(default=0.7, ge=0, le=1)

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def production(self) -> bool:
        return self.env.lower() == "production"

    def validate_runtime_secrets(self) -> None:
        if not self.production:
            return
        if self.shared_password == "change-me":
            raise ValueError("TSUCHIBOT_SHARED_PASSWORD must be set in production")
        if len(self.session_secret) < 32:
            raise ValueError("TSUCHIBOT_SESSION_SECRET must be at least 32 characters")
        if not self.session_secure:
            raise ValueError("TSUCHIBOT_SESSION_SECURE must be true in production")


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    settings.validate_runtime_secrets()
    return settings
