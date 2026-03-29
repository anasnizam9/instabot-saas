import pytest

from app.core.config import Settings
from app.core.runtime_checks import validate_runtime_settings


def test_runtime_checks_skip_for_non_production():
    settings = Settings(app_env="development")

    validate_runtime_settings(settings)


def test_runtime_checks_fail_on_default_production_values():
    settings = Settings(app_env="production")

    with pytest.raises(RuntimeError):
        validate_runtime_settings(settings)


def test_runtime_checks_pass_for_valid_production_values():
    settings = Settings(
        app_env="production",
        secret_key="strong-secret-key-123",
        encryption_key="12345678901234567890123456789012",
        auto_create_tables=False,
        instagram_webhook_verify_token="verify-token",
    )

    validate_runtime_settings(settings)
