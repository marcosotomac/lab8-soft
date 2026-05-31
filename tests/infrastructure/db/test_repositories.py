from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.exc import IntegrityError

from rewards.application.ports import TransientApplicationError
from rewards.application.use_cases import ProcessRewardEvent, RegisterRewardAction
from rewards.domain.models import DuplicateOutcome, Reward, RewardAction, RewardEvent
from rewards.domain.reward_rules import RewardCalculator
from rewards.infrastructure.db.models import Base
from rewards.infrastructure.db.repositories import (
    SQLAlchemyRewardActionRepository,
    SQLAlchemyRewardRepository,
    SQLAlchemyTransaction,
    _sqlite_safe_datetime,
    create_session_factory,
    create_sqlite_compatible_engine,
    session_scope,
)


def test_action_repository_persists_and_loads_reward_action() -> None:
    session_factory = _session_factory()

    with session_factory() as session:
        repository = SQLAlchemyRewardActionRepository(session)
        repository.save(_action())
        session.commit()

    with session_factory() as session:
        loaded = SQLAlchemyRewardActionRepository(session).get_by_idempotency_key("idem-1")

    assert loaded == _action()


def test_action_repository_supports_duplicate_safe_registration() -> None:
    session_factory = _session_factory()
    publisher = RecordingPublisher()

    with session_factory() as session:
        use_case = RegisterRewardAction(
            actions=SQLAlchemyRewardActionRepository(session),
            publisher=publisher,
        )
        first = use_case.execute(_action())
        duplicate = use_case.execute(_action(amount="99.99"))
        session.commit()

    assert first.outcome == DuplicateOutcome.CREATED
    assert duplicate.outcome == DuplicateOutcome.DUPLICATE
    assert duplicate.action.amount == Decimal("50.00")
    assert len(publisher.events) == 1


def test_reward_repository_persists_and_loads_reward() -> None:
    session_factory = _session_factory()
    reward = _reward()

    with session_factory() as session:
        repository = SQLAlchemyRewardRepository(session)
        repository.save(reward)
        session.commit()

    with session_factory() as session:
        loaded = SQLAlchemyRewardRepository(session).get_by_idempotency_key("idem-1")

    assert loaded == reward


def test_reward_repository_supports_duplicate_safe_processing() -> None:
    session_factory = _session_factory()
    event = RewardEvent.from_action(_action(), event_id=UUID(int=1))

    with session_factory() as session:
        use_case = ProcessRewardEvent(
            rewards=SQLAlchemyRewardRepository(session),
            calculator=RewardCalculator(Decimal("0.10")),
            failure_reporter=RecordingFailureReporter(),
        )
        first = use_case.execute(event)
        duplicate = use_case.execute(event)
        session.commit()

    assert first.outcome == DuplicateOutcome.CREATED
    assert first.reward.amount == Decimal("5.00")
    assert duplicate.outcome == DuplicateOutcome.DUPLICATE
    assert duplicate.reward == first.reward


def test_file_sqlite_engine_path_uses_default_pool() -> None:
    engine = create_sqlite_compatible_engine("sqlite+pysqlite:///:memory:?cache=shared")

    assert engine.url.drivername == "sqlite+pysqlite"


def test_transaction_exit_without_enter_is_noop() -> None:
    with _session_factory()() as session:
        assert SQLAlchemyTransaction(session).__exit__(None, None, None) is None


def test_session_scope_closes_session() -> None:
    session = ClosingRecorderSession()


    with session_scope(lambda: session) as active:
        assert active is session

    assert session.closed is True


def test_action_repository_wraps_integrity_errors() -> None:
    repository = SQLAlchemyRewardActionRepository(FailingFlushSession())

    with pytest.raises(TransientApplicationError, match="reward action persistence failed"):
        repository.save(_action())


def test_reward_repository_wraps_integrity_errors() -> None:
    repository = SQLAlchemyRewardRepository(FailingFlushSession())

    with pytest.raises(TransientApplicationError, match="reward persistence failed"):
        repository.save(_reward())


def test_sqlite_safe_datetime_preserves_aware_values() -> None:
    value = datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC)

    assert _sqlite_safe_datetime(value) is value


def _session_factory():
    engine = create_sqlite_compatible_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    return create_session_factory(engine)


def _action(*, amount: str = "50.00") -> RewardAction:
    return RewardAction.create(
        restaurant_id="rest-1",
        customer_id="cust-1",
        action_type="dinner_registered",
        occurred_at=datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC),
        amount=amount,
        idempotency_key="idem-1",
    )


def _reward() -> Reward:
    event = RewardEvent.from_action(_action(), event_id=UUID(int=1))
    return Reward.from_event(event, amount=Decimal("5.00"))


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[RewardEvent] = []

    def publish_reward_action_registered(self, event: RewardEvent) -> None:
        self.events.append(event)


class RecordingFailureReporter:
    def report_event_failure(self, event: RewardEvent, error: BaseException, *, transient: bool) -> None:
        raise AssertionError("no failures expected")


class ClosingRecorderSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FailingFlushSession:
    def add(self, record: object) -> None:
        _ = record

    def flush(self) -> None:
        raise IntegrityError("statement", "params", Exception("duplicate"))
