from __future__ import annotations

from enum import Enum

from .states import PetState


class PetActivity(str, Enum):
    IDLE = "idle"
    WALK = "walk"
    SIT = "sit"
    SIT_TRANSITION = "sit_transition"
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
    """Stores the selected base pose; action policy owns state-to-pose choice."""

    def __init__(self) -> None:
        self.quota_state = PetState.NORMAL
        self.activity = PetActivity.IDLE

    def set_quota_state(
        self, state: PetState, base_activity: PetActivity | str = PetActivity.IDLE
    ) -> PetActivity | str:
        self.quota_state = state
        self.activity = base_activity
        return self.activity

    def advance(self) -> PetActivity | str:
        return self.activity

