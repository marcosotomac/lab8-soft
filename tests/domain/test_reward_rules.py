from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

import pytest

from rewards.domain.models import Reward, RewardAction, RewardEvent, aware_datetime
from rewards.domain.reward_rules import RewardCalculator


def test_calculates_rewards_using_configurable_rate() -> None:
    event = RewardEvent.from_action(_action(amount="120.50"), event_id=UUID(int=1))

    reward_amount = RewardCalculator(Decimal("0.10")).calculate(event)

    assert reward_amount == Decimal("12.05")


def test_zero_rate_is_allowed_for_no_reward_promotions() -> None:
    event = RewardEvent.from_action(_action(amount="99.99"))

    assert RewardCalculator(Decimal("0.00")).calculate(event) == Decimal("0.00")


def test_negative_rate_is_rejected() -> None:
    with pytest.raises(ValueError, match="reward_rate"):
        RewardCalculator(Decimal("-0.01"))


def test_reward_action_requires_timezone_aware_occurrence_time() -> None:
    with pytest.raises(ValueError, match="timezone"):
        _action(occurred_at=datetime(2026, 5, 30, 12, 0, 0))


def test_reward_event_rejects_unsupported_schema_version() -> None:
    with pytest.raises(ValueError, match="schema_version"):
        RewardEvent.create(
            event_id=UUID(int=1),
            idempotency_key="idem-1",
            restaurant_id="rest-1",
            customer_id="cust-1",
            action_type="dinner_registered",
            occurred_at=datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC),
            amount="10.00",
            schema_version=999,
        )


def test_reward_event_rejects_invalid_amount() -> None:
    with pytest.raises(ValueError, match="amount"):
        RewardEvent.create(
            event_id=UUID(int=1),
            idempotency_key="idem-1",
            restaurant_id="rest-1",
            customer_id="cust-1",
            action_type="dinner_registered",
            occurred_at=datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC),
            amount="not-money",
            schema_version=1,
        )


def test_reward_event_rejects_non_positive_amount() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        RewardEvent.create(
            event_id=UUID(int=1),
            idempotency_key="idem-1",
            restaurant_id="rest-1",
            customer_id="cust-1",
            action_type="dinner_registered",
            occurred_at=datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC),
            amount="0.00",
            schema_version=1,
        )


def test_reward_rejects_negative_amount() -> None:
    event = RewardEvent.from_action(_action(), event_id=UUID(int=1))

    with pytest.raises(ValueError, match="reward amount"):
        Reward.from_event(event, amount=Decimal("-0.01"))


def test_aware_datetime_rejects_non_datetime_value() -> None:
    with pytest.raises(ValueError, match="must be a datetime"):
        aware_datetime("2026-05-30", "occurred_at")  # type: ignore[arg-type]


def test_reward_event_accepts_string_uuid_and_normalizes_datetime() -> None:
    event = RewardEvent.create(
        event_id="00000000-0000-0000-0000-000000000001",
        idempotency_key=" idem-1 ",
        restaurant_id=" rest-1 ",
        customer_id=" cust-1 ",
        action_type="dinner_registered",
        occurred_at=datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC),
        amount=10,
        schema_version=1,
    )

    assert event.event_id == UUID(int=1)
    assert event.idempotency_key == "idem-1"
    assert event.amount == Decimal("10.00")


def test_reward_action_rejects_blank_values() -> None:
    with pytest.raises(ValueError, match="restaurant_id"):
        _action_with(restaurant_id=" ")


def test_reward_action_rejects_non_positive_amount() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        _action_with(amount="0.00")


def _action(
    *,
    amount: str = "25.00",
    occurred_at: datetime | None = None,
) -> RewardAction:
    return RewardAction.create(
        restaurant_id="rest-1",
        customer_id="cust-1",
        action_type="dinner_registered",
        occurred_at=occurred_at or datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC),
        amount=amount,
        idempotency_key="idem-1",
    )


def _action_with(
    *,
    restaurant_id: str = "rest-1",
    amount: str = "25.00",
) -> RewardAction:
    return RewardAction.create(
        restaurant_id=restaurant_id,
        customer_id="cust-1",
        action_type="dinner_registered",
        occurred_at=datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC),
        amount=amount,
        idempotency_key="idem-1",
    )
