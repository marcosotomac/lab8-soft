"""RabbitMQ adapter for reward event publication and consumption."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

try:
    import aio_pika
except ModuleNotFoundError:  # pragma: no cover - exercised only when optional broker deps are absent.
    aio_pika = None  # type: ignore[assignment]

from rewards.application.ports import TransientApplicationError
from rewards.application.use_cases import ProcessRewardEvent
from rewards.domain.models import DuplicateOutcome, RewardEvent
from rewards.infrastructure.messaging.contracts import (
    REWARD_ACTION_REGISTERED,
    ContractValidationError,
    deserialize_reward_action_registered,
    serialize_reward_action_registered,
)


@dataclass(frozen=True, slots=True)
class RabbitMQTopology:
    exchange_name: str
    reward_queue_name: str
    routing_key: str = REWARD_ACTION_REGISTERED


@dataclass(frozen=True, slots=True)
class MessageHandlingResult:
    decision: str
    outcome: DuplicateOutcome | None = None
    error: str | None = None


async def declare_reward_topology(channel: aio_pika.abc.AbstractChannel, topology: RabbitMQTopology) -> None:
    broker = _require_aio_pika()
    exchange = await channel.declare_exchange(
        topology.exchange_name,
        broker.ExchangeType.TOPIC,
        durable=True,
    )
    queue = await channel.declare_queue(topology.reward_queue_name, durable=True)
    await queue.bind(exchange, routing_key=topology.routing_key)


class RabbitMQRewardEventPublisher:
    def __init__(self, channel: aio_pika.abc.AbstractChannel, topology: RabbitMQTopology) -> None:
        self._channel = channel
        self._topology = topology

    def publish_reward_action_registered(self, event: RewardEvent) -> None:
        """Publish from the synchronous application port."""

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.publish_reward_action_registered_async(event))
            return
        raise RuntimeError("use publish_reward_action_registered_async inside an active event loop")

    async def publish_reward_action_registered_async(self, event: RewardEvent) -> None:
        broker = _require_aio_pika()
        exchange = await self._channel.get_exchange(self._topology.exchange_name)
        await exchange.publish(
            broker.Message(
                serialize_reward_action_registered(event),
                content_type="application/json",
                delivery_mode=broker.DeliveryMode.PERSISTENT,
                type=REWARD_ACTION_REGISTERED,
            ),
            routing_key=self._topology.routing_key,
        )


class RewardEventConsumer:
    def __init__(self, use_case_factory: Callable[[], ProcessRewardEvent]) -> None:
        self._use_case_factory = use_case_factory

    async def handle_message(self, message: aio_pika.abc.AbstractIncomingMessage) -> MessageHandlingResult:
        try:
            event = deserialize_reward_action_registered(message.body)
        except ContractValidationError as exc:
            await message.reject(requeue=False)
            return MessageHandlingResult(decision="reject", error=str(exc))

        try:
            result = self._use_case_factory().execute(event)
        except TransientApplicationError as exc:
            await message.reject(requeue=True)
            return MessageHandlingResult(decision="retry", error=str(exc))

        await message.ack()
        return MessageHandlingResult(decision="ack", outcome=result.outcome)


async def consume_reward_events(
    connection: aio_pika.abc.AbstractRobustConnection,
    topology: RabbitMQTopology,
    consumer: RewardEventConsumer,
) -> object:
    channel = await connection.channel()
    await channel.set_qos(prefetch_count=10)
    await declare_reward_topology(channel, topology)
    queue = await channel.get_queue(topology.reward_queue_name)
    return await queue.consume(consumer.handle_message)


def _require_aio_pika() -> Any:
    if aio_pika is None:
        raise RuntimeError("aio-pika is required for live RabbitMQ operations")
    return aio_pika
