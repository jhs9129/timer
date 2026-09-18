from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    database_url: str = "postgresql+asyncpg://village:village@localhost:5432/village"
    cors_origins: list[str] = ["http://localhost:5173"]
    db_connect_timeout_seconds: float = 3.0
    frontend_url: str = "http://localhost:5173"

    # auth
    session_secret: str = "dev-secret-change-me"
    cookie_name: str = "mlv_session"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_max_age_seconds: int = 60 * 60 * 24 * 30
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/auth/google/callback"
    dev_login_enabled: bool = True  # honored only when app_env == "development"

    # focus sessions
    heartbeat_interval_seconds: int = 30
    heartbeat_timeout_seconds: int = 90
    day_boundary_hour: int = 4
    abandon_grace_seconds: int = 30 * 60
    default_timezone: str = "Asia/Seoul"

    # internal cron
    cron_secret: str = "dev-cron-secret"
    dispatch_batch_size: int = 200

    # notifications (leave keys empty in development: senders then log instead of sending)
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@example.com"
    resend_api_key: str = ""
    email_from: str = "My Little Village <noreply@example.com>"
    retro_pending_delay_seconds: int = 30 * 60
    notification_max_attempts: int = 5
    reminder_window_minutes: int = 10
    weekly_summary_weekday: int = 0  # Monday
    weekly_summary_hour: int = 8

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()
