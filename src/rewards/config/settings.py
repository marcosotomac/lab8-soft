"""Environment-only runtime settings.

Defaults intentionally point to local, non-secret resources so unit tests can load settings without
requiring credentials or external services.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from os import environ


@dataclass(frozen=True, slots=True)
class Settings:
    app_env: str
    database_url: str
    reward_event_publisher: str
    rabbitmq_url: str
    rabbitmq_exchange: str
    rabbitmq_reward_queue: str
    reward_rate: Decimal


def load_settings() -> Settings:
    app_env = environ.get("APP_ENV", "test")
    return Settings(
        app_env=app_env,
        database_url=environ.get("DATABASE_URL", "sqlite+pysqlite:///:memory:"),
        reward_event_publisher=environ.get(
            "REWARD_EVENT_PUBLISHER",
            "rabbitmq" if app_env.lower() in {"prod", "production"} else "memory",
        ),
        rabbitmq_url=environ.get("RABBITMQ_URL", "amqp://localhost/"),
        rabbitmq_exchange=environ.get("RABBITMQ_EXCHANGE", "rewards.events"),
        rabbitmq_reward_queue=environ.get("RABBITMQ_REWARD_QUEUE", "rewards.processing"),
        reward_rate=_decimal_env("REWARD_RATE", "0.10"),
    )


def _decimal_env(name: str, default: str) -> Decimal:
    raw_value = environ.get(name, default)
    try:
        value = Decimal(raw_value)
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a decimal value") from exc
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return value
