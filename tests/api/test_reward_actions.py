from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from rewards.config.settings import Settings
from rewards.domain.models import RewardAction, RewardEvent
from rewards.infrastructure.db.repositories import (
    create_session_factory,
    create_sqlite_compatible_engine,
    create_tables,
)
from rewards.infrastructure.messaging import rabbitmq
from rewards.interfaces.api.main import (
    InMemoryRewardEventPublisher,
    create_app,
    create_reward_event_publisher,
)


def test_post_reward_action_accepts_valid_payload_and_publishes_event() -> None:
    client, publisher = _client()

    response = client.post("/reward-actions", json=_payload())

    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "created"
    assert body["restaurant_id"] == "rest-1"
    assert body["customer_id"] == "cust-1"
    assert body["action_type"] == "dinner_registered"
    assert body["idempotency_key"] == "idem-1"
    assert body["event_id"] is not None
    assert len(publisher.events) == 1
    assert publisher.events[0].idempotency_key == "idem-1"


def test_post_reward_action_rejects_invalid_payload() -> None:
    client, publisher = _client()
    payload = _payload(amount="0.00")

    response = client.post("/reward-actions", json=payload)

    assert response.status_code == 422
    assert publisher.events == []


def test_post_reward_action_rejects_timezone_naive_payload() -> None:
    client, publisher = _client()
    payload = _payload()
    payload["occurred_at"] = "2026-05-30T12:00:00"

    response = client.post("/reward-actions", json=payload)

    assert response.status_code == 422
    assert publisher.events == []


def test_post_reward_action_maps_domain_validation_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    client, publisher = _client()

    def reject_action(cls: type[RewardAction], **kwargs: object) -> None:
        _ = cls, kwargs
        raise ValueError("domain rejected action")

    monkeypatch.setattr(RewardAction, "create", classmethod(reject_action))

    response = client.post("/reward-actions", json=_payload())

    assert response.status_code == 422
    assert response.json()["detail"] == "domain rejected action"
    assert publisher.events == []


def test_post_reward_action_returns_duplicate_safe_response() -> None:
    client, publisher = _client()

    first = client.post("/reward-actions", json=_payload())
    duplicate = client.post("/reward-actions", json=_payload(amount="99.99"))

    assert first.status_code == 202
    assert duplicate.status_code == 202
    assert duplicate.json()["status"] == "duplicate"
    assert duplicate.json()["event_id"] is None
    assert len(publisher.events) == 1


def test_create_publisher_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="REWARD_EVENT_PUBLISHER"):
        create_reward_event_publisher(_settings(reward_event_publisher="unknown"))


def test_create_publisher_returns_memory_publisher() -> None:
    publisher = create_reward_event_publisher(_settings(reward_event_publisher="memory"))

    assert isinstance(publisher, InMemoryRewardEventPublisher)


def test_create_app_builds_default_sqlite_resources(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("REWARD_EVENT_PUBLISHER", "memory")
    app = create_app()

    with TestClient(app) as client:
        response = client.post("/reward-actions", json=_payload(idempotency_key="default-db"))

    assert response.status_code == 202
    assert response.json()["status"] == "created"


def test_create_publisher_requires_aio_pika_for_rabbitmq(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rabbitmq, "aio_pika", None)

    with pytest.raises(RuntimeError, match="aio-pika is required"):
        create_reward_event_publisher(_settings(reward_event_publisher="rabbitmq"))


def test_create_publisher_configures_rabbitmq_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_broker = FakeAioPikaModule()
    monkeypatch.setattr(rabbitmq, "aio_pika", fake_broker)

    publisher = create_reward_event_publisher(_settings(reward_event_publisher="rabbitmq"))
    publisher.publish_reward_action_registered(RewardEvent.from_action(_action()))

    assert fake_broker.connection.channel_instance.exchange.published
    assert fake_broker.connection.channel_instance.declared_exchange == ("rewards.events", "topic", True)
    assert fake_broker.connection.channel_instance.declared_queue == ("rewards.processing", True)
    assert fake_broker.connection.closed is True


def test_create_rabbitmq_publisher_fails_clearly_when_dependency_missing_on_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_broker = FakeAioPikaModule()
    monkeypatch.setattr(rabbitmq, "aio_pika", fake_broker)
    publisher = create_reward_event_publisher(_settings(reward_event_publisher="rabbitmq"))
    monkeypatch.setattr(rabbitmq, "aio_pika", None)

    with pytest.raises(RuntimeError, match="aio-pika is required"):
        publisher.publish_reward_action_registered(RewardEvent.from_action(_action()))


def _client() -> tuple[TestClient, InMemoryRewardEventPublisher]:
    engine = create_sqlite_compatible_engine("sqlite+pysqlite:///:memory:")
    create_tables(engine)
    publisher = InMemoryRewardEventPublisher()
    app = create_app(session_factory=create_session_factory(engine), publisher=publisher)
    return TestClient(app), publisher


def _session_factory():
    engine = create_sqlite_compatible_engine("sqlite+pysqlite:///:memory:")
    create_tables(engine)
    return create_session_factory(engine)


def _payload(*, amount: str = "120.50", idempotency_key: str = "idem-1") -> dict[str, str]:
    return {
        "restaurant_id": "rest-1",
        "customer_id": "cust-1",
        "action_type": "dinner_registered",
        "occurred_at": "2026-05-30T12:00:00+00:00",
        "amount": amount,
        "idempotency_key": idempotency_key,
    }


def _action() -> RewardAction:
    return RewardAction.create(
        restaurant_id="rest-1",
        customer_id="cust-1",
        action_type="dinner_registered",
        occurred_at=datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC),
        amount="120.50",
        idempotency_key="idem-1",
    )


def _settings(*, reward_event_publisher: str) -> Settings:
    return Settings(
        app_env="test",
        database_url="sqlite+pysqlite:///:memory:",
        reward_event_publisher=reward_event_publisher,
        rabbitmq_url="amqp://localhost/",
        rabbitmq_exchange="rewards.events",
        rabbitmq_reward_queue="rewards.processing",
        reward_rate=Decimal("0.10"),
    )


class FakeAioPikaModule:
    ExchangeType = type("ExchangeType", (), {"TOPIC": "topic"})
    DeliveryMode = type("DeliveryMode", (), {"PERSISTENT": "persistent"})

    def __init__(self) -> None:
        self.connection = FakeConnection()

    async def connect_robust(self, url: str) -> FakeConnection:
        assert url == "amqp://localhost/"
        return self.connection

    class Message:
        def __init__(self, body: bytes, **kwargs: object) -> None:
            self.body = body
            self.kwargs = kwargs


class FakeConnection:
    def __init__(self) -> None:
        self.channel_instance = FakeChannel()
        self.closed = False

    async def channel(self) -> FakeChannel:
        return self.channel_instance

    async def close(self) -> None:
        self.closed = True


class FakeExchange:
    def __init__(self) -> None:
        self.published: list[tuple[object, str]] = []

    async def publish(self, message: object, *, routing_key: str) -> None:
        self.published.append((message, routing_key))


class FakeQueue:
    async def bind(self, exchange: FakeExchange, *, routing_key: str) -> None:
        _ = exchange, routing_key


class FakeChannel:
    def __init__(self) -> None:
        self.exchange = FakeExchange()
        self.queue = FakeQueue()
        self.declared_exchange: tuple[str, str, bool] | None = None
        self.declared_queue: tuple[str, bool] | None = None

    async def declare_exchange(self, name: str, exchange_type: str, *, durable: bool) -> FakeExchange:
        self.declared_exchange = (name, exchange_type, durable)
        return self.exchange

    async def declare_queue(self, name: str, *, durable: bool) -> FakeQueue:
        self.declared_queue = (name, durable)
        return self.queue

    async def get_exchange(self, name: str) -> FakeExchange:
        assert name == "rewards.events"
        return self.exchange
