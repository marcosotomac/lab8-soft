"""Reward event worker entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import suppress

try:
    import aio_pika
except ModuleNotFoundError:  # pragma: no cover - startup dependency guard.
    aio_pika = None  # type: ignore[assignment]

from rewards.application.use_cases import ProcessRewardEvent
from rewards.config.settings import load_settings
from rewards.domain.models import RewardEvent
from rewards.domain.reward_rules import RewardCalculator
from rewards.infrastructure.db.repositories import (
    SQLAlchemyRewardRepository,
    SQLAlchemyTransaction,
    create_session_factory,
    create_sqlite_compatible_engine,
    create_tables,
)
from rewards.infrastructure.messaging.rabbitmq import (
    RabbitMQTopology,
    RewardEventConsumer,
    consume_reward_events,
)


class LoggingFailureReporter:
    """Minimal failure reporter that avoids printing payloads or credentials."""

    def report_event_failure(self, event: RewardEvent, error: BaseException, *, transient: bool) -> None:
        _ = event, error, transient


async def run_worker() -> None:
    if aio_pika is None:
        raise RuntimeError("aio-pika is required to run the RabbitMQ worker")

    settings = load_settings()
    engine = create_sqlite_compatible_engine(settings.database_url)
    create_tables(engine)
    session_factory = create_session_factory(engine)
    topology = RabbitMQTopology(settings.rabbitmq_exchange, settings.rabbitmq_reward_queue)

    def use_case_factory() -> ProcessRewardEvent:
        session = session_factory()
        return ProcessRewardEvent(
            rewards=SQLAlchemyRewardRepository(session),
            calculator=RewardCalculator(settings.reward_rate),
            failure_reporter=LoggingFailureReporter(),
            transaction=ClosingSQLAlchemyTransaction(session),
        )

    connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    try:
        await consume_reward_events(connection, topology, RewardEventConsumer(use_case_factory))
        await asyncio.Event().wait()
    finally:
        with suppress(Exception):
            await connection.close()


def main() -> None:
    asyncio.run(run_worker())


class ClosingSQLAlchemyTransaction(SQLAlchemyTransaction):
    def __exit__(self, exc_type, exc, traceback):  # type: ignore[no-untyped-def]
        try:
            return super().__exit__(exc_type, exc, traceback)
        finally:
            self._session.close()


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint delegates to tested main().
    main()
