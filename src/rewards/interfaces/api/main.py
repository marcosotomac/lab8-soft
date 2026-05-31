"""FastAPI application for reward action registration."""

from __future__ import annotations

import asyncio
from datetime import datetime
from decimal import Decimal
from typing import Protocol

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from rewards.application.use_cases import RegisterRewardAction
from rewards.config.settings import Settings, load_settings
from rewards.domain.models import ActionType, DuplicateOutcome, RewardAction, RewardEvent
from rewards.infrastructure.db.repositories import (
    SessionFactory,
    SQLAlchemyRewardActionRepository,
    create_session_factory,
    create_sqlite_compatible_engine,
    create_tables,
)
from rewards.infrastructure.messaging import rabbitmq
from rewards.infrastructure.messaging.rabbitmq import RabbitMQRewardEventPublisher, RabbitMQTopology


class RewardEventPublisher(Protocol):
    def publish_reward_action_registered(self, event: RewardEvent) -> None: ...


class RabbitMQAPIEventPublisher:
    """Synchronous API publisher that owns short-lived RabbitMQ resources per request."""

    def __init__(self, settings: Settings, topology: RabbitMQTopology) -> None:
        self._settings = settings
        self._topology = topology

    def publish_reward_action_registered(self, event: RewardEvent) -> None:
        asyncio.run(self._publish_once(event))

    async def _publish_once(self, event: RewardEvent) -> None:
        broker = rabbitmq.aio_pika  # type: ignore[attr-defined]
        if broker is None:
            raise RuntimeError("aio-pika is required for live RabbitMQ operations")
        connection = await broker.connect_robust(self._settings.rabbitmq_url)
        try:
            channel = await connection.channel()
            await rabbitmq.declare_reward_topology(channel, self._topology)
            publisher = RabbitMQRewardEventPublisher(channel, self._topology)
            await publisher.publish_reward_action_registered_async(event)
        finally:
            await connection.close()


class RewardActionRequest(BaseModel):
    restaurant_id: str = Field(min_length=1)
    customer_id: str = Field(min_length=1)
    action_type: ActionType
    occurred_at: datetime
    amount: Decimal = Field(gt=0)
    idempotency_key: str = Field(min_length=1)

    @field_validator("occurred_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("occurred_at must include timezone information")
        return value


class RewardActionResponse(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    status: DuplicateOutcome
    restaurant_id: str
    customer_id: str
    action_type: ActionType
    idempotency_key: str
    event_id: str | None = None


class InMemoryRewardEventPublisher:
    def __init__(self) -> None:
        self.events: list[RewardEvent] = []

    def publish_reward_action_registered(self, event: RewardEvent) -> None:
        self.events.append(event)


def create_app(
    *,
    session_factory: SessionFactory | None = None,
    publisher: RewardEventPublisher | None = None,
) -> FastAPI:
    settings = load_settings()
    if session_factory is None:
        engine = create_sqlite_compatible_engine(settings.database_url)
        create_tables(engine)
        session_factory = create_session_factory(engine)
    runtime_publisher = publisher or create_reward_event_publisher(settings)

    app = FastAPI(title="Restaurant Rewards API")
    app.state.publisher = runtime_publisher

    @app.post(
        "/reward-actions",
        status_code=status.HTTP_202_ACCEPTED,
    )
    def register_reward_action(request: RewardActionRequest) -> RewardActionResponse:
        try:
            action = RewardAction.create(**request.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc

        with session_factory() as session:
            repository = SQLAlchemyRewardActionRepository(session)
            use_case = RegisterRewardAction(actions=repository, publisher=runtime_publisher)
            result = use_case.execute(action)
            session.commit()

        return RewardActionResponse(
            status=result.outcome,
            restaurant_id=result.action.restaurant_id,
            customer_id=result.action.customer_id,
            action_type=result.action.action_type,
            idempotency_key=result.action.idempotency_key,
            event_id=str(result.event.event_id) if result.event else None,
        )

    return app


def create_reward_event_publisher(settings: Settings) -> RewardEventPublisher:
    publisher_kind = settings.reward_event_publisher.lower()
    if publisher_kind == "memory":
        return InMemoryRewardEventPublisher()
    if publisher_kind == "rabbitmq":
        return _create_rabbitmq_publisher(settings)
    raise ValueError("REWARD_EVENT_PUBLISHER must be 'memory' or 'rabbitmq'")


def _create_rabbitmq_publisher(settings: Settings) -> RabbitMQAPIEventPublisher:
    if rabbitmq.aio_pika is None:  # type: ignore[attr-defined]
        raise RuntimeError("aio-pika is required for live RabbitMQ operations")
    topology = RabbitMQTopology(settings.rabbitmq_exchange, settings.rabbitmq_reward_queue)
    return RabbitMQAPIEventPublisher(settings, topology)
