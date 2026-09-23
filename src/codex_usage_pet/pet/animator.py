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
    HOVER = "hover"
    CLICK = "click"
    BLINK = "blink"
    LOOK_LEFT = "look_left"
    LOOK_RIGHT = "look_right"
    WAVE = "wave"
    SLEEP_REACT = "sleep_react"


class PetBehaviorController:
    """Quota-driven base pose; optional interactions are scheduled by the UI."""

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
        self.activity = self._forced_activity(self.quota_state)
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

