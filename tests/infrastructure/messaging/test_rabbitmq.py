from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal

from rewards.application.ports import TransientApplicationError
from rewards.application.use_cases import ProcessRewardEvent
from rewards.domain.models import DuplicateOutcome, Reward, RewardAction, RewardEvent
from rewards.domain.reward_rules import RewardCalculator
from rewards.infrastructure.messaging import rabbitmq
from rewards.infrastructure.messaging.contracts import serialize_reward_action_registered
from rewards.infrastructure.messaging.rabbitmq import (
    RabbitMQRewardEventPublisher,
    RabbitMQTopology,
    RewardEventConsumer,
    consume_reward_events,
    declare_reward_topology,
)


def test_declare_reward_topology_declares_and_binds_queue(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(rabbitmq, "aio_pika", FakeAioPikaModule())
    channel = FakeChannel()
    topology = RabbitMQTopology("rewards.events", "rewards.processing")

    asyncio.run(declare_reward_topology(channel, topology))

    assert channel.declared_exchange == ("rewards.events", "topic", True)
    assert channel.declared_queue == ("rewards.processing", True)
    assert channel.queue.bindings == [(channel.exchange, "reward.action.registered")]


def test_publisher_serializes_event_as_persistent_json(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(rabbitmq, "aio_pika", FakeAioPikaModule())
    channel = FakeChannel()
    topology = RabbitMQTopology("rewards.events", "rewards.processing")
    event = RewardEvent.from_action(_action())

    RabbitMQRewardEventPublisher(channel, topology).publish_reward_action_registered(event)

    published = channel.exchange.published[0]
    restored = rabbitmq.deserialize_reward_action_registered(published[0].body)
    assert restored == event
    assert published[1] == "reward.action.registered"


def test_publisher_rejects_sync_publish_inside_running_loop(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(rabbitmq, "aio_pika", FakeAioPikaModule())
    publisher = RabbitMQRewardEventPublisher(FakeChannel(), RabbitMQTopology("rewards.events", "rewards.processing"))

    async def publish_inside_loop() -> None:
        publisher.publish_reward_action_registered(RewardEvent.from_action(_action()))

    try:
        asyncio.run(publish_inside_loop())
    except RuntimeError as exc:
        assert "publish_reward_action_registered_async" in str(exc)
    else:  # pragma: no cover - defensive assertion path.
        raise AssertionError("sync publish must fail inside a running event loop")


def test_consumer_acks_contract_valid_event() -> None:
    event = RewardEvent.from_action(_action())
    message = FakeIncomingMessage(serialize_reward_action_registered(event))
    consumer = RewardEventConsumer(
        lambda: ProcessRewardEvent(
            rewards=InMemoryRewardRepository(),
            calculator=RewardCalculator(Decimal("0.10")),
            failure_reporter=RecordingFailureReporter(),
        )
    )

    result = asyncio.run(consumer.handle_message(message))

    assert result.decision == "ack"
    assert result.outcome == DuplicateOutcome.CREATED
    assert message.acked is True
    assert message.rejections == []


def test_consumer_rejects_contract_invalid_event_without_requeue() -> None:
    message = FakeIncomingMessage(b'{"schema_version": 2}')
    consumer = RewardEventConsumer(lambda: NotCalledProcessRewardEvent())

    result = asyncio.run(consumer.handle_message(message))

    assert result.decision == "reject"
    assert message.acked is False
    assert message.rejections == [False]


def test_consumer_acks_duplicate_event_without_creating_new_reward() -> None:
    event = RewardEvent.from_action(_action())
    existing = Reward.from_event(event, amount=Decimal("5.00"))
    rewards = InMemoryRewardRepository(existing=existing)
    message = FakeIncomingMessage(serialize_reward_action_registered(event))
    consumer = RewardEventConsumer(
        lambda: ProcessRewardEvent(
            rewards=rewards,
            calculator=RewardCalculator(Decimal("0.10")),
            failure_reporter=RecordingFailureReporter(),
        )
    )

    result = asyncio.run(consumer.handle_message(message))

    assert result.decision == "ack"
    assert result.outcome == DuplicateOutcome.DUPLICATE
    assert len(rewards.records) == 1
    assert message.acked is True


def test_consumer_retries_when_persistence_is_unavailable() -> None:
    event = RewardEvent.from_action(_action())
    reporter = RecordingFailureReporter()
    message = FakeIncomingMessage(serialize_reward_action_registered(event))
    consumer = RewardEventConsumer(
        lambda: ProcessRewardEvent(
            rewards=InMemoryRewardRepository(fail_on_save=True),
            calculator=RewardCalculator(Decimal("0.10")),
            failure_reporter=reporter,
        )
    )

    result = asyncio.run(consumer.handle_message(message))

    assert result.decision == "retry"
    assert message.acked is False
    assert message.rejections == [True]
    assert reporter.failures == [(event, True)]


def test_consume_reward_events_declares_topology_and_starts_consumer(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(rabbitmq, "aio_pika", FakeAioPikaModule())
    connection = FakeConnection()
    topology = RabbitMQTopology("rewards.events", "rewards.processing")
    consumer = RewardEventConsumer(lambda: NotCalledProcessRewardEvent())

    result = asyncio.run(consume_reward_events(connection, topology, consumer))

    assert result == "consumer-tag"
    assert connection.channel_instance.qos == 10
    assert connection.channel_instance.queue.consumer.__self__ is consumer


def test_live_rabbitmq_operations_require_aio_pika(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(rabbitmq, "aio_pika", None)

    try:
        asyncio.run(declare_reward_topology(FakeChannel(), RabbitMQTopology("rewards.events", "rewards.processing")))
    except RuntimeError as exc:
        assert "aio-pika is required" in str(exc)
    else:  # pragma: no cover - defensive assertion path.
        raise AssertionError("live RabbitMQ operations must require aio-pika")


def _action() -> RewardAction:
    return RewardAction.create(
        restaurant_id="rest-1",
        customer_id="cust-1",
        action_type="dinner_registered",
        occurred_at=datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC),
        amount="50.00",
        idempotency_key="idem-1",
    )


class FakeIncomingMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.acked = False
        self.rejections: list[bool] = []

    async def ack(self) -> None:
        self.acked = True

    async def reject(self, *, requeue: bool) -> None:
        self.rejections.append(requeue)


class InMemoryRewardRepository:
    def __init__(self, *, existing: Reward | None = None, fail_on_save: bool = False) -> None:
        self.records: dict[str, Reward] = {}
        if existing is not None:
            self.records[existing.idempotency_key] = existing
        self.fail_on_save = fail_on_save

    def get_by_idempotency_key(self, idempotency_key: str) -> Reward | None:
        return self.records.get(idempotency_key)

    def save(self, reward: Reward) -> Reward:
        if self.fail_on_save:
            raise TransientApplicationError("persistence unavailable")
        self.records[reward.idempotency_key] = reward
        return reward


class RecordingFailureReporter:
    def __init__(self) -> None:
        self.failures: list[tuple[RewardEvent, bool]] = []

    def report_event_failure(self, event: RewardEvent, error: BaseException, *, transient: bool) -> None:
        self.failures.append((event, transient))


class NotCalledProcessRewardEvent:
    def execute(self, event: RewardEvent) -> None:
        raise AssertionError("invalid contracts must not reach the use case")


class FakeAioPikaModule:
    ExchangeType = type("ExchangeType", (), {"TOPIC": "topic"})
    DeliveryMode = type("DeliveryMode", (), {"PERSISTENT": "persistent"})

    class Message:
        def __init__(self, body: bytes, **kwargs: object) -> None:
            self.body = body
            self.kwargs = kwargs


class FakeExchange:
    def __init__(self) -> None:
        self.published: list[tuple[object, str]] = []

    async def publish(self, message: object, *, routing_key: str) -> None:
        self.published.append((message, routing_key))


class FakeQueue:
    def __init__(self) -> None:
        self.bindings: list[tuple[FakeExchange, str]] = []
        self.consumer = None

    async def bind(self, exchange: FakeExchange, *, routing_key: str) -> None:
        self.bindings.append((exchange, routing_key))

    async def consume(self, callback: object) -> str:
        self.consumer = callback
        return "consumer-tag"


class FakeChannel:
    def __init__(self) -> None:
        self.exchange = FakeExchange()
        self.queue = FakeQueue()
        self.declared_exchange: tuple[str, str, bool] | None = None
        self.declared_queue: tuple[str, bool] | None = None
        self.qos: int | None = None

    async def set_qos(self, *, prefetch_count: int) -> None:
        self.qos = prefetch_count

    async def declare_exchange(self, name: str, exchange_type: str, *, durable: bool) -> FakeExchange:
        self.declared_exchange = (name, exchange_type, durable)
        return self.exchange

    async def declare_queue(self, name: str, *, durable: bool) -> FakeQueue:
        self.declared_queue = (name, durable)
        return self.queue

    async def get_exchange(self, name: str) -> FakeExchange:
        assert name == "rewards.events"
        return self.exchange

    async def get_queue(self, name: str) -> FakeQueue:
        assert name == "rewards.processing"
        return self.queue


class FakeConnection:
    def __init__(self) -> None:
        self.channel_instance = FakeChannel()

    async def channel(self) -> FakeChannel:
        return self.channel_instance
