from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from rewards.application.ports import TransientApplicationError
from rewards.application.use_cases import ProcessRewardEvent
from rewards.domain.models import DuplicateOutcome, Reward, RewardAction, RewardEvent
from rewards.domain.reward_rules import RewardCalculator


def test_process_reward_event_returns_duplicate_without_resaving() -> None:
    event = RewardEvent.from_action(_action())
    existing = Reward.from_event(event, amount=Decimal("5.00"))
    rewards = InMemoryRewardRepository(existing=existing)
    use_case = ProcessRewardEvent(
        rewards=rewards,
        calculator=RewardCalculator(Decimal("0.10")),
        failure_reporter=RecordingFailureReporter(),
    )

    result = use_case.execute(event)

    assert result.outcome == DuplicateOutcome.DUPLICATE
    assert result.reward == existing
    assert rewards.save_calls == 0


def test_process_reward_event_reports_persistence_unavailable_as_transient() -> None:
    event = RewardEvent.from_action(_action())
    reporter = RecordingFailureReporter()
    use_case = ProcessRewardEvent(
        rewards=InMemoryRewardRepository(fail_on_save=True),
        calculator=RewardCalculator(Decimal("0.10")),
        failure_reporter=reporter,
    )

    with pytest.raises(TransientApplicationError):
        use_case.execute(event)

    assert reporter.failures == [(event, True)]


def _action() -> RewardAction:
    return RewardAction.create(
        restaurant_id="rest-1",
        customer_id="cust-1",
        action_type="dinner_registered",
        occurred_at=datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC),
        amount="50.00",
        idempotency_key="idem-1",
    )


class InMemoryRewardRepository:
    def __init__(self, *, existing: Reward | None = None, fail_on_save: bool = False) -> None:
        self.records: dict[str, Reward] = {}
        if existing is not None:
            self.records[existing.idempotency_key] = existing
        self.fail_on_save = fail_on_save
        self.save_calls = 0

    def get_by_idempotency_key(self, idempotency_key: str) -> Reward | None:
        return self.records.get(idempotency_key)

    def save(self, reward: Reward) -> Reward:
        self.save_calls += 1
        if self.fail_on_save:
            raise TransientApplicationError("persistence unavailable")
        self.records[reward.idempotency_key] = reward
        return reward


class RecordingFailureReporter:
    def __init__(self) -> None:
        self.failures: list[tuple[RewardEvent, bool]] = []

    def report_event_failure(self, event: RewardEvent, error: BaseException, *, transient: bool) -> None:
        self.failures.append((event, transient))
