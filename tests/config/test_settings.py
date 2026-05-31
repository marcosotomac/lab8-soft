from decimal import Decimal

import pytest

from rewards.config.settings import load_settings


def test_settings_use_safe_non_secret_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in [
        "APP_ENV",
        "DATABASE_URL",
        "RABBITMQ_URL",
        "RABBITMQ_EXCHANGE",
        "RABBITMQ_REWARD_QUEUE",
        "REWARD_EVENT_PUBLISHER",
        "REWARD_RATE",
    ]:
        monkeypatch.delenv(name, raising=False)

    settings = load_settings()

    assert settings.app_env == "test"
    assert settings.database_url == "sqlite+pysqlite:///:memory:"
    assert settings.reward_event_publisher == "memory"
    assert settings.rabbitmq_exchange == "rewards.events"
    assert settings.rabbitmq_reward_queue == "rewards.processing"
    assert settings.reward_rate == Decimal("0.10")


def test_settings_read_environment_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///local.db")
    monkeypatch.setenv("RABBITMQ_URL", "amqp://localhost/")
    monkeypatch.setenv("RABBITMQ_EXCHANGE", "custom.exchange")
    monkeypatch.setenv("RABBITMQ_REWARD_QUEUE", "custom.queue")
    monkeypatch.setenv("REWARD_EVENT_PUBLISHER", "rabbitmq")
    monkeypatch.setenv("REWARD_RATE", "0.25")

    settings = load_settings()

    assert settings.app_env == "local"
    assert settings.database_url == "sqlite:///local.db"
    assert settings.rabbitmq_url == "amqp://localhost/"
    assert settings.reward_event_publisher == "rabbitmq"
    assert settings.rabbitmq_exchange == "custom.exchange"
    assert settings.rabbitmq_reward_queue == "custom.queue"
    assert settings.reward_rate == Decimal("0.25")


def test_settings_reject_invalid_reward_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REWARD_RATE", "bad-rate")

    with pytest.raises(ValueError, match="REWARD_RATE"):
        load_settings()


def test_settings_reject_negative_reward_rate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REWARD_RATE", "-0.01")

    with pytest.raises(ValueError, match="REWARD_RATE"):
        load_settings()


def test_settings_default_to_rabbitmq_publisher_in_production(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("REWARD_EVENT_PUBLISHER", raising=False)

    settings = load_settings()

    assert settings.reward_event_publisher == "rabbitmq"
