"""Application ports for clean architecture boundaries."""

from __future__ import annotations

from types import TracebackType
from typing import Protocol

from rewards.domain.models import Reward, RewardAction, RewardEvent


class TransientApplicationError(RuntimeError):
    """Raised when processing should be retried rather than acknowledged as complete."""


class RewardActionRepository(Protocol):
    def get_by_idempotency_key(self, idempotency_key: str) -> RewardAction | None: ...

    def save(self, action: RewardAction) -> RewardAction: ...


class RewardRepository(Protocol):
    def get_by_idempotency_key(self, idempotency_key: str) -> Reward | None: ...

    def save(self, reward: Reward) -> Reward: ...


class RewardEventPublisher(Protocol):
    def publish_reward_action_registered(self, event: RewardEvent) -> None: ...


class TransactionBoundary(Protocol):
    def __enter__(self) -> TransactionBoundary: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None: ...


class FailureReporter(Protocol):
    def report_event_failure(self, event: RewardEvent, error: BaseException, *, transient: bool) -> None: ...
