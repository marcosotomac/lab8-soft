"""Application use cases for reward registration and event processing."""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass

from rewards.application.ports import (
    FailureReporter,
    RewardActionRepository,
    RewardEventPublisher,
    RewardRepository,
    TransactionBoundary,
    TransientApplicationError,
)
from rewards.domain.models import (
    DuplicateOutcome,
    ProcessRewardEventResult,
    RegisterRewardActionResult,
    Reward,
    RewardAction,
    RewardEvent,
)
from rewards.domain.reward_rules import RewardCalculator


@dataclass(frozen=True, slots=True)
class RegisterRewardAction:
    actions: RewardActionRepository
    publisher: RewardEventPublisher
    transaction: TransactionBoundary | None = None

    def execute(self, action: RewardAction) -> RegisterRewardActionResult:
        with _transaction(self.transaction):
            existing = self.actions.get_by_idempotency_key(action.idempotency_key)
            if existing is not None:
                return RegisterRewardActionResult(outcome=DuplicateOutcome.DUPLICATE, action=existing)

            saved = self.actions.save(action)
            event = RewardEvent.from_action(saved)
            self.publisher.publish_reward_action_registered(event)
            return RegisterRewardActionResult(
                outcome=DuplicateOutcome.CREATED,
                action=saved,
                event=event,
            )


@dataclass(frozen=True, slots=True)
class ProcessRewardEvent:
    rewards: RewardRepository
    calculator: RewardCalculator
    failure_reporter: FailureReporter
    transaction: TransactionBoundary | None = None

    def execute(self, event: RewardEvent) -> ProcessRewardEventResult:
        try:
            with _transaction(self.transaction):
                existing = self.rewards.get_by_idempotency_key(event.idempotency_key)
                if existing is not None:
                    return ProcessRewardEventResult(
                        outcome=DuplicateOutcome.DUPLICATE,
                        reward=existing,
                    )

                reward = Reward.from_event(event, amount=self.calculator.calculate(event))
                saved = self.rewards.save(reward)
                return ProcessRewardEventResult(outcome=DuplicateOutcome.CREATED, reward=saved)
        except TransientApplicationError as exc:
            self.failure_reporter.report_event_failure(event, exc, transient=True)
            raise


def _transaction(
    transaction: TransactionBoundary | None,
) -> AbstractContextManager[object] | TransactionBoundary:
    return transaction if transaction is not None else nullcontext()
