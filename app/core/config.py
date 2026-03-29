from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "InstaBot SaaS API"
    app_env: str = "development"
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 30
    algorithm: str = "HS256"
    database_url: str = "sqlite+aiosqlite:///./instabot.db"
    auto_create_tables: bool = False

    # Instagram/Meta OAuth
    instagram_app_id: str = ""
    instagram_app_secret: str = ""
    instagram_redirect_uri: str = (
        "http://127.0.0.1:8000/api/v1/instagram/oauth/callback"
    )
    instagram_api_version: str = "v23.0"
    instagram_webhook_verify_token: str = "instabot-webhook-verify-token"

    # Token encryption
    encryption_key: str = "change-me-to-32-char-key-min"  # min 32 chars for Fernet

    # Phase 3 scheduler/publisher
    scheduler_enabled: bool = True
    scheduler_interval_seconds: int = 30
    scheduler_batch_size: int = 20
    scheduler_automation_interval_seconds: int = 300
    scheduler_stuck_check_interval_seconds: int = 120
    scheduler_cleanup_interval_hours: int = 24
    publisher_max_attempts: int = 3
    publisher_retry_base_delay_seconds: int = 60
    publisher_retry_jitter_ratio: float = 0.15
    publisher_stuck_timeout_minutes: int = 15
    webhook_max_age_seconds: int = 600
    webhook_event_retention_days: int = 14

    # Phase 5 observability/runtime defaults
    log_level: str = "INFO"
    request_id_header: str = "X-Request-ID"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False
    )


settings = Settings()
