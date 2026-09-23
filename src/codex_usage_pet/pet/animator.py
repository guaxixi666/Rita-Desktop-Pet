from __future__ import annotations

from enum import Enum

from .states import PetState


class PetActivity(str, Enum):
    IDLE = "idle"
    WALK = "walk"
    SIT = "sit"
    STRETCH = "stretch"
    CRITICAL = "critical"
    SLEEP = "sleep"


class PetBehaviorController:
    """Deterministic low-frequency pose scheduler driven by quota state."""

    _NORMAL_SEQUENCE = (
        (PetActivity.IDLE, 8),
        (PetActivity.WALK, 6),
        (PetActivity.IDLE, 6),
        (PetActivity.STRETCH, 4),
    )

    def __init__(self) -> None:
        self.quota_state = PetState.NORMAL
        self.activity = PetActivity.IDLE
        self._sequence_index = 0
        self._ticks_in_activity = 0

    def set_quota_state(self, state: PetState) -> PetActivity:
        self.quota_state = state
        self._sequence_index = 0
        self._ticks_in_activity = 0
        self.activity = self._forced_activity(state)
        return self.activity

    def advance(self) -> PetActivity:
        forced = self._forced_activity(self.quota_state)
        if self.quota_state is not PetState.NORMAL:
            self.activity = forced
            return self.activity

        activity, duration = self._NORMAL_SEQUENCE[self._sequence_index]
        self.activity = activity
        self._ticks_in_activity += 1
        if self._ticks_in_activity >= duration:
            self._ticks_in_activity = 0
            self._sequence_index = (self._sequence_index + 1) % len(self._NORMAL_SEQUENCE)
        return self.activity

    @staticmethod
    def _forced_activity(state: PetState) -> PetActivity:
        return {
            PetState.NORMAL: PetActivity.IDLE,
            PetState.LOW: PetActivity.SIT,
            PetState.CRITICAL: PetActivity.CRITICAL,
            PetState.EMPTY: PetActivity.SLEEP,
            PetState.RECOVERED: PetActivity.STRETCH,
        }[state]

