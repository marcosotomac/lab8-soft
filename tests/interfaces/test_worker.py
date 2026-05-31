from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest

from rewards.domain.models import RewardAction, RewardEvent
from rewards.infrastructure.messaging.contracts import serialize_reward_action_registered
from rewards.interfaces.worker import main as worker


def test_worker_opens_resources_consumes_event_and_closes_connection(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    connection = FakeConnection()
    monkeypatch.setattr(worker, "aio_pika", FakeAioPikaModule(connection))
    monkeypatch.setattr(worker, "consume_reward_events", consume_one_message_then_return)
    monkeypatch.setattr(worker.asyncio, "Event", StoppingEvent)

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(worker.run_worker())

    assert connection.closed is True


def test_worker_reports_missing_broker_dependency(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(worker, "aio_pika", None)

    with pytest.raises(RuntimeError, match="aio-pika is required"):
        asyncio.run(worker.run_worker())


def test_worker_main_runs_async_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = []

    def run(coro):  # type: ignore[no-untyped-def]
        calls.append(coro)
        coro.close()

    monkeypatch.setattr(worker.asyncio, "run", run)

    worker.main()

    assert len(calls) == 1


def test_logging_failure_reporter_ignores_payloads() -> None:
    event = RewardEvent.from_action(_action())

    assert worker.LoggingFailureReporter().report_event_failure(
        event,
        RuntimeError("boom"),
        transient=True,
    ) is None


async def consume_one_message_then_return(connection, topology, consumer):  # type: ignore[no-untyped-def]
    _ = connection, topology
    event = RewardEvent.from_action(_action())
    result = await consumer.handle_message(FakeIncomingMessage(serialize_reward_action_registered(event)))
    assert result.decision == "ack"


def _action() -> RewardAction:
    return RewardAction.create(
        restaurant_id="rest-1",
        customer_id="cust-1",
        action_type="dinner_registered",
        occurred_at=datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC),
        amount="50.00",
        idempotency_key="idem-1",
    )


class FakeAioPikaModule:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def connect_robust(self, url: str) -> FakeConnection:
        assert url.startswith("amqp://")
        return self.connection


class FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeIncomingMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body

    async def ack(self) -> None:
        return None

    async def reject(self, *, requeue: bool) -> None:
        raise AssertionError(f"valid worker event should not be rejected: {requeue}")


class StoppingEvent:
    async def wait(self) -> None:
        raise asyncio.CancelledError
