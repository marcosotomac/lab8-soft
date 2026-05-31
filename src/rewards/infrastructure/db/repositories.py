"""SQLAlchemy repository adapters for reward application ports."""

from __future__ import annotations

from collections.abc import Callable, Generator
from contextlib import AbstractContextManager, contextmanager
from datetime import UTC, datetime
from types import TracebackType
from uuid import UUID

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from rewards.application.ports import TransientApplicationError
from rewards.domain.models import ActionType, Reward, RewardAction
from rewards.infrastructure.db.models import Base, RewardActionRecord, RewardRecord

SessionFactory = Callable[[], Session]


def create_sqlite_compatible_engine(database_url: str) -> Engine:
    if database_url == "sqlite+pysqlite:///:memory:":
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    return create_engine(database_url)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def create_tables(engine: Engine) -> None:
    Base.metadata.create_all(engine)


class SQLAlchemyTransaction(AbstractContextManager["SQLAlchemyTransaction"]):
    def __init__(self, session: Session) -> None:
        self._session = session
        self._transaction: AbstractContextManager[object] | None = None

    def __enter__(self) -> SQLAlchemyTransaction:
        self._transaction = self._session.begin()
        self._transaction.__enter__()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        if self._transaction is None:
            return None
        return self._transaction.__exit__(exc_type, exc, traceback)


@contextmanager
def session_scope(session_factory: SessionFactory) -> Generator[Session]:
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


class SQLAlchemyRewardActionRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_idempotency_key(self, idempotency_key: str) -> RewardAction | None:
        record = self._session.scalar(
            select(RewardActionRecord).where(RewardActionRecord.idempotency_key == idempotency_key)
        )
        if record is None:
            return None
        return _action_from_record(record)

    def save(self, action: RewardAction) -> RewardAction:
        record = RewardActionRecord(
            restaurant_id=action.restaurant_id,
            customer_id=action.customer_id,
            action_type=action.action_type.value,
            occurred_at=action.occurred_at,
            amount=action.amount,
            idempotency_key=action.idempotency_key,
        )
        self._session.add(record)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise TransientApplicationError("reward action persistence failed") from exc
        return action


class SQLAlchemyRewardRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_idempotency_key(self, idempotency_key: str) -> Reward | None:
        record = self._session.scalar(
            select(RewardRecord).where(RewardRecord.idempotency_key == idempotency_key)
        )
        if record is None:
            return None
        return _reward_from_record(record)

    def save(self, reward: Reward) -> Reward:
        record = RewardRecord(
            idempotency_key=reward.idempotency_key,
            restaurant_id=reward.restaurant_id,
            customer_id=reward.customer_id,
            action_type=reward.action_type.value,
            occurred_at=reward.occurred_at,
            source_event_id=str(reward.source_event_id),
            amount=reward.amount,
        )
        self._session.add(record)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise TransientApplicationError("reward persistence failed") from exc
        return reward


def _action_from_record(record: RewardActionRecord) -> RewardAction:
    return RewardAction.create(
        restaurant_id=record.restaurant_id,
        customer_id=record.customer_id,
        action_type=record.action_type,
        occurred_at=_sqlite_safe_datetime(record.occurred_at),
        amount=record.amount,
        idempotency_key=record.idempotency_key,
    )


def _reward_from_record(record: RewardRecord) -> Reward:
    return Reward(
        idempotency_key=record.idempotency_key,
        restaurant_id=record.restaurant_id,
        customer_id=record.customer_id,
        action_type=ActionType(record.action_type),
        occurred_at=_sqlite_safe_datetime(record.occurred_at),
        source_event_id=UUID(record.source_event_id),
        amount=record.amount,
    )


def _sqlite_safe_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=UTC)
    return value
