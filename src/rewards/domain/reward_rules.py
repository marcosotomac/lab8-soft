"""Pure reward calculation rules.

The assignment does not yet decide whether rewards should be fixed points/cashback or a rate-based
calculation. This module uses configurable `REWARD_RATE` for now, keeping the policy injectable so a
future fixed-points rule can replace it without changing application use cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from rewards.domain.models import RewardEvent


@dataclass(frozen=True, slots=True)
class RewardCalculator:
    reward_rate: Decimal

    def __post_init__(self) -> None:
        if self.reward_rate < 0:
            raise ValueError("reward_rate must not be negative")

    def calculate(self, event: RewardEvent) -> Decimal:
        return (event.amount * self.reward_rate).quantize(Decimal("0.01"))
