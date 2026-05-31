from datetime import UTC, datetime
from decimal import Decimal

import pytest

from rewards.application.ports import TransientApplicationError
from rewards.application.use_cases import ProcessRewardEvent, RegisterRewardAction
from rewards.domain.models import DuplicateOutcome, Reward, RewardAction, RewardEvent
from rewards.domain.reward_rules import RewardCalculator


def test_register_reward_action_publishes_only_first_action_for_idempotency_key() -> None:
    actions = InMemoryActionRepository()
    publisher = RecordingPublisher()
    use_case = RegisterRewardAction(actions=actions, publisher=publisher)
    action = _action()

    first = use_case.execute(action)
    duplicate = use_case.execute(action)

    assert first.outcome == DuplicateOutcome.CREATED
    assert first.event is not None
    assert duplicate.outcome == DuplicateOutcome.DUPLICATE
    assert duplicate.event is None
    assert len(publisher.events) == 1
    assert len(actions.records) == 1


def test_process_reward_event_persists_only_first_reward_for_idempotency_key() -> None:
    rewards = InMemoryRewardRepository()
    reporter = RecordingFailureReporter()
    event = RewardEvent.from_action(_action())
    use_case = ProcessRewardEvent(
        rewards=rewards,
        calculator=RewardCalculator(Decimal("0.20")),
        failure_reporter=reporter,
    )

    first = use_case.execute(event)
    duplicate = use_case.execute(event)

    assert first.outcome == DuplicateOutcome.CREATED
    assert first.reward.amount == Decimal("10.00")
    assert duplicate.outcome == DuplicateOutcome.DUPLICATE
    assert duplicate.reward == first.reward
    assert len(rewards.records) == 1
    assert reporter.failures == []


def test_process_reward_event_reports_and_reraises_transient_failures() -> None:
    rewards = InMemoryRewardRepository(fail_on_save=True)
    reporter = RecordingFailureReporter()
    event = RewardEvent.from_action(_action())
    use_case = ProcessRewardEvent(
        rewards=rewards,
        calculator=RewardCalculator(Decimal("0.10")),
        failure_reporter=reporter,
    )

    with pytest.raises(TransientApplicationError):
        use_case.execute(event)

    assert len(rewards.records) == 0
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


class InMemoryActionRepository:
    def __init__(self) -> None:
        self.records: dict[str, RewardAction] = {}

    def get_by_idempotency_key(self, idempotency_key: str) -> RewardAction | None:
        return self.records.get(idempotency_key)

    def save(self, action: RewardAction) -> RewardAction:
        self.records[action.idempotency_key] = action
        return action


class InMemoryRewardRepository:
    def __init__(self, *, fail_on_save: bool = False) -> None:
        self.records: dict[str, Reward] = {}
        self.fail_on_save = fail_on_save

    def get_by_idempotency_key(self, idempotency_key: str) -> Reward | None:
        return self.records.get(idempotency_key)

    def save(self, reward: Reward) -> Reward:
        if self.fail_on_save:
            raise TransientApplicationError("persistence unavailable")
        self.records[reward.idempotency_key] = reward
        return reward


class RecordingPublisher:
    def __init__(self) -> None:
        self.events: list[RewardEvent] = []

    def publish_reward_action_registered(self, event: RewardEvent) -> None:
        self.events.append(event)


class RecordingFailureReporter:
    def __init__(self) -> None:
        self.failures: list[tuple[RewardEvent, bool]] = []

    def report_event_failure(self, event: RewardEvent, error: BaseException, *, transient: bool) -> None:
        self.failures.append((event, transient))
