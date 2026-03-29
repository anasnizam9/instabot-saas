from app.core.config import Settings


DEFAULT_SECRET_KEY = "change-me"
DEFAULT_ENCRYPTION_KEY = "change-me-to-32-char-key-min"


def validate_runtime_settings(settings: Settings) -> None:
    """Fail fast for unsafe production configuration."""
    if settings.app_env.lower() != "production":
        return

    errors: list[str] = []

    if settings.secret_key == DEFAULT_SECRET_KEY:
        errors.append("SECRET_KEY must be changed in production")

    if settings.encryption_key == DEFAULT_ENCRYPTION_KEY:
        errors.append("ENCRYPTION_KEY must be changed in production")

    if len(settings.encryption_key) < 32:
        errors.append("ENCRYPTION_KEY must be at least 32 characters")

    if settings.auto_create_tables:
        errors.append("AUTO_CREATE_TABLES must be false in production")

    if not settings.instagram_webhook_verify_token:
        errors.append("INSTAGRAM_WEBHOOK_VERIFY_TOKEN is required in production")

    if errors:
        raise RuntimeError("Invalid production settings: " + "; ".join(errors))
