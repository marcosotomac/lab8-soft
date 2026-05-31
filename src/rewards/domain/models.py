"""Reward domain models with validation-friendly constructors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from uuid import UUID, uuid4

SUPPORTED_REWARD_EVENT_SCHEMA_VERSION = 1


class ActionType(StrEnum):
    DINNER_REGISTERED = "dinner_registered"
    PURCHASE_COMPLETED = "purchase_completed"


class DuplicateOutcome(StrEnum):
    CREATED = "created"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class RewardAction:
    restaurant_id: str
    customer_id: str
    action_type: ActionType
    occurred_at: datetime
    amount: Decimal
    idempotency_key: str

    @classmethod
    def create(
        cls,
        *,
        restaurant_id: str,
        customer_id: str,
        action_type: str | ActionType,
        occurred_at: datetime,
        amount: Decimal | str | int | float,
        idempotency_key: str,
    ) -> RewardAction:
        normalized_amount = parse_money(amount)
        if normalized_amount <= 0:
            raise ValueError("amount must be greater than zero")
        return cls(
            restaurant_id=non_empty(restaurant_id, "restaurant_id"),
            customer_id=non_empty(customer_id, "customer_id"),
            action_type=ActionType(action_type),
            occurred_at=aware_datetime(occurred_at, "occurred_at"),
            amount=normalized_amount,
            idempotency_key=non_empty(idempotency_key, "idempotency_key"),
        )


@dataclass(frozen=True, slots=True)
class RewardEvent:
    event_id: UUID
    idempotency_key: str
    restaurant_id: str
    customer_id: str
    action_type: ActionType
    occurred_at: datetime
    amount: Decimal
    schema_version: int = SUPPORTED_REWARD_EVENT_SCHEMA_VERSION

    @classmethod
    def from_action(cls, action: RewardAction, *, event_id: UUID | None = None) -> RewardEvent:
        return cls(
            event_id=event_id or uuid4(),
            idempotency_key=action.idempotency_key,
            restaurant_id=action.restaurant_id,
            customer_id=action.customer_id,
            action_type=action.action_type,
            occurred_at=action.occurred_at,
            amount=action.amount,
        )

    @classmethod
    def create(
        cls,
        *,
        event_id: UUID | str,
        idempotency_key: str,
        restaurant_id: str,
        customer_id: str,
        action_type: str | ActionType,
        occurred_at: datetime,
        amount: Decimal | str | int | float,
        schema_version: int,
    ) -> RewardEvent:
        if schema_version != SUPPORTED_REWARD_EVENT_SCHEMA_VERSION:
            raise ValueError("unsupported reward event schema_version")
        normalized_amount = parse_money(amount)
        if normalized_amount <= 0:
            raise ValueError("amount must be greater than zero")
        return cls(
            event_id=event_id if isinstance(event_id, UUID) else UUID(non_empty(event_id, "event_id")),
            idempotency_key=non_empty(idempotency_key, "idempotency_key"),
            restaurant_id=non_empty(restaurant_id, "restaurant_id"),
            customer_id=non_empty(customer_id, "customer_id"),
            action_type=ActionType(action_type),
            occurred_at=aware_datetime(occurred_at, "occurred_at"),
            amount=normalized_amount,
            schema_version=schema_version,
        )


@dataclass(frozen=True, slots=True)
class Reward:
    idempotency_key: str
    restaurant_id: str
    customer_id: str
    action_type: ActionType
    occurred_at: datetime
    source_event_id: UUID
    amount: Decimal

    @classmethod
    def from_event(cls, event: RewardEvent, *, amount: Decimal) -> Reward:
        if amount < 0:
            raise ValueError("reward amount must not be negative")
        return cls(
            idempotency_key=event.idempotency_key,
            restaurant_id=event.restaurant_id,
            customer_id=event.customer_id,
            action_type=event.action_type,
            occurred_at=event.occurred_at,
            source_event_id=event.event_id,
            amount=amount,
        )


@dataclass(frozen=True, slots=True)
class RegisterRewardActionResult:
    outcome: DuplicateOutcome
    action: RewardAction
    event: RewardEvent | None = None


@dataclass(frozen=True, slots=True)
class ProcessRewardEventResult:
    outcome: DuplicateOutcome
    reward: Reward


def non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    return value.strip()


def aware_datetime(value: datetime, field_name: str) -> datetime:
    if not isinstance(value, datetime):
        raise ValueError(f"{field_name} must be a datetime")
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")
    return value.astimezone(UTC)


def parse_money(value: Decimal | str | int | float) -> Decimal:
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("amount must be a decimal-compatible value") from exc
    return decimal_value.quantize(Decimal("0.01"))
