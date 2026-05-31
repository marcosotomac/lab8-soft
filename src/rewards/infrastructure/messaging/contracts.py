"""Reward event wire contracts.

The application works with domain objects. This module owns the JSON-compatible
contract used at the messaging boundary.
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from rewards.domain.models import SUPPORTED_REWARD_EVENT_SCHEMA_VERSION, RewardEvent

REWARD_ACTION_REGISTERED = "reward.action.registered"


class ContractValidationError(ValueError):
    """Raised when a reward event payload does not match the supported contract."""


def serialize_reward_action_registered(event: RewardEvent) -> bytes:
    """Serialize a reward event to the version 1 JSON message body."""

    if event.schema_version != SUPPORTED_REWARD_EVENT_SCHEMA_VERSION:
        raise ContractValidationError("unsupported reward event schema_version")
    return json.dumps(
        {
            "schema_version": event.schema_version,
            "event_id": str(event.event_id),
            "idempotency_key": event.idempotency_key,
            "restaurant_id": event.restaurant_id,
            "customer_id": event.customer_id,
            "action_type": event.action_type.value,
            "occurred_at": event.occurred_at.isoformat(),
            "amount": str(event.amount),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def deserialize_reward_action_registered(body: bytes | str) -> RewardEvent:
    """Deserialize and validate a version 1 reward event message body."""

    try:
        payload = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractValidationError("reward event body must be valid JSON") from exc

    if not isinstance(payload, dict):
        raise ContractValidationError("reward event body must be a JSON object")

    _require_fields(
        payload,
        {
            "schema_version",
            "event_id",
            "idempotency_key",
            "restaurant_id",
            "customer_id",
            "action_type",
            "occurred_at",
            "amount",
        },
    )

    try:
        occurred_at = datetime.fromisoformat(str(payload["occurred_at"]))
        return RewardEvent.create(
            schema_version=int(payload["schema_version"]),
            event_id=str(payload["event_id"]),
            idempotency_key=str(payload["idempotency_key"]),
            restaurant_id=str(payload["restaurant_id"]),
            customer_id=str(payload["customer_id"]),
            action_type=str(payload["action_type"]),
            occurred_at=occurred_at,
            amount=Decimal(str(payload["amount"])),
        )
    except (TypeError, ValueError) as exc:
        raise ContractValidationError(str(exc)) from exc


def _require_fields(payload: dict[str, Any], required_fields: set[str]) -> None:
    missing = sorted(field for field in required_fields if field not in payload)
    if missing:
        raise ContractValidationError(f"reward event missing required fields: {', '.join(missing)}")
