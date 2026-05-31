from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID

import pytest

from rewards.domain.models import RewardAction, RewardEvent
from rewards.infrastructure.messaging.contracts import (
    ContractValidationError,
    deserialize_reward_action_registered,
    serialize_reward_action_registered,
)


def test_reward_action_registered_contract_round_trips_valid_event() -> None:
    event = RewardEvent.from_action(_action(), event_id=UUID(int=1))

    body = serialize_reward_action_registered(event)
    restored = deserialize_reward_action_registered(body)

    assert restored == event


@pytest.mark.parametrize(
    "body",
    [
        b"not-json",
        b"[]",
        b'{"schema_version":2}',
        b'{"schema_version":1,"event_id":"bad"}',
    ],
)
def test_reward_action_registered_contract_rejects_invalid_payloads(body: bytes) -> None:
    with pytest.raises(ContractValidationError):
        deserialize_reward_action_registered(body)


def test_contract_rejects_serializing_unsupported_schema_version() -> None:
    event = RewardEvent.from_action(_action(), event_id=UUID(int=1))

    with pytest.raises(ContractValidationError, match="schema_version"):
        serialize_reward_action_registered(replace(event, schema_version=2))


def test_contract_wraps_domain_validation_errors() -> None:
    body = (
        b'{"schema_version":1,"event_id":"00000000-0000-0000-0000-000000000001",'
        b'"idempotency_key":"idem-1","restaurant_id":"rest-1","customer_id":"cust-1",'
        b'"action_type":"dinner_registered","occurred_at":"2026-05-30T12:00:00",'
        b'"amount":"10.00"}'
    )

    with pytest.raises(ContractValidationError, match="timezone"):
        deserialize_reward_action_registered(body)


def _action() -> RewardAction:
    return RewardAction.create(
        restaurant_id="rest-1",
        customer_id="cust-1",
        action_type="dinner_registered",
        occurred_at=datetime(2026, 5, 30, 12, 0, 0, tzinfo=UTC),
        amount="50.00",
        idempotency_key="idem-1",
    )
