from app.core.config import Settings


def test_settings_load_default_local_values():
    settings = Settings()

    assert settings.app_name == "FinBrief"
    assert settings.app_version == "0.1.0"
    assert settings.app_env == "local"
    assert settings.api_v1_prefix == "/api/v1"
    assert settings.enable_mock_data is True
    assert settings.delivery_dry_run is True


def test_settings_support_environment_overrides(monkeypatch):
    monkeypatch.setenv("APP_NAME", "FinBrief Test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ENABLE_MOCK_DATA", "false")

    settings = Settings()

    assert settings.app_name == "FinBrief Test"
    assert settings.app_env == "test"
    assert settings.enable_mock_data is False


def test_settings_reject_api_prefix_without_leading_slash():
    try:
        Settings(api_v1_prefix="api/v1")
    except ValueError as exc:
        assert "api_v1_prefix" in str(exc)
    else:
        raise AssertionError("Settings must reject an API prefix without a leading slash")


def test_public_settings_exclude_secret_values():
    settings = Settings(discord_webhook_url="https://example.invalid/secret-token")

    public_data = settings.public_dict()

    assert "secret-token" not in str(public_data)
    assert "discord_webhook_url" not in public_data
