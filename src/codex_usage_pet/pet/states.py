from __future__ import annotations

from enum import Enum


class PetState(str, Enum):
    NORMAL = "normal"
    LOW = "low"
    CRITICAL = "critical"
    EMPTY = "empty"
    RECOVERED = "recovered"


def state_for_remaining(remaining_percent: float | None) -> PetState:
    if remaining_percent is None:
        return PetState.NORMAL
    if remaining_percent <= 0:
        return PetState.EMPTY
    if remaining_percent < 10:
        return PetState.CRITICAL
    if remaining_percent <= 30:
        return PetState.LOW
    return PetState.NORMAL


class PetStateTracker:
    def __init__(self) -> None:
        self.previous_remaining: float | None = None

    def update(self, remaining_percent: float | None) -> PetState:
        state = state_for_remaining(remaining_percent)
        previous = self.previous_remaining
        self.previous_remaining = remaining_percent
        if (
            previous is not None
            and remaining_percent is not None
            and remaining_percent > 30
            and (previous <= 10 or remaining_percent - previous >= 40)
        ):
            return PetState.RECOVERED
        return state

