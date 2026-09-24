from __future__ import annotations

import random
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .states import PetState

NONE_ACTION = "none"


class ActionEvent(str, Enum):
    HOVER = "hover"
    CLICK = "click"
    IDLE_RANDOM = "idle_random"
    RECOVERED = "recovered"
    NORMAL_IDLE = "normal_idle"
    LOW_ON_ENTER = "low_on_enter"
    LOW_IDLE = "low_idle"
    LOW_ON_EXIT = "low_on_exit"
    CRITICAL_ON_ENTER = "critical_on_enter"
    CRITICAL_IDLE = "critical_idle"
    CRITICAL_ON_EXIT = "critical_on_exit"
    EMPTY_ON_ENTER = "empty_on_enter"
    EMPTY_IDLE = "empty_idle"
    EMPTY_ON_EXIT = "empty_on_exit"


@dataclass(frozen=True, slots=True)
class ActionCandidate:
    action: str
    weight: int = 1
    cooldown_min_ms: int = 0
    cooldown_max_ms: int = 0
    allowed_states: frozenset[PetState] | None = None


@dataclass(frozen=True, slots=True)
class ActionPolicy:
    pools: dict[str, tuple[ActionCandidate, ...]] = field(default_factory=dict)
    idle_trigger_probability: float = 0.7
    idle_interval_min_ms: int = 45_000
    idle_interval_max_ms: int = 150_000
    avoid_immediate_repeat: bool = True
    history_size: int = 3

    def pool(self, event: ActionEvent | str) -> tuple[ActionCandidate, ...]:
        key = event.value if isinstance(event, ActionEvent) else str(event)
        return self.pools.get(key, ())


@dataclass(frozen=True, slots=True)
class ActionDecision:
    event: str
    candidate: ActionCandidate | None
    reason: str

    @property
    def action(self) -> str | None:
        if self.candidate is None or self.candidate.action == NONE_ACTION:
            return None
        return self.candidate.action


def _candidate(
    action: str,
    weight: int,
    states: tuple[PetState, ...] | None = None,
    cooldown: tuple[int, int] = (0, 0),
) -> ActionCandidate:
    return ActionCandidate(
        action=action,
        weight=weight,
        cooldown_min_ms=cooldown[0],
        cooldown_max_ms=cooldown[1],
        allowed_states=frozenset(states) if states else None,
    )


def default_action_policy() -> ActionPolicy:
    normal = (PetState.NORMAL,)
    low = (PetState.LOW,)
    critical = (PetState.CRITICAL,)
    empty = (PetState.EMPTY,)
    recovered = (PetState.RECOVERED,)
    return ActionPolicy(
        pools={
            ActionEvent.HOVER.value: (
                _candidate("blink", 40, normal, (5_000, 15_000)),
                _candidate("hover", 40, normal, (3_000, 8_000)),
                _candidate(NONE_ACTION, 20, normal),
            ),
            ActionEvent.CLICK.value: (
                _candidate("click", 45, (PetState.NORMAL, PetState.LOW), (1_000, 2_000)),
                _candidate("wave", 20, (PetState.NORMAL, PetState.LOW), (30_000, 90_000)),
                _candidate("stretch", 20, (PetState.NORMAL, PetState.LOW), (60_000, 150_000)),
                _candidate("sleep_react", 80, empty, (2_000, 5_000)),
                _candidate(NONE_ACTION, 15, (PetState.NORMAL, PetState.LOW, PetState.EMPTY)),
            ),
            ActionEvent.IDLE_RANDOM.value: (
                _candidate("blink", 45, normal, (5_000, 15_000)),
                _candidate("wave", 15, normal, (60_000, 180_000)),
                _candidate("stretch", 25, normal, (90_000, 240_000)),
                _candidate(NONE_ACTION, 15, normal),
            ),
            ActionEvent.RECOVERED.value: (
                _candidate("wave", 30, recovered),
                _candidate("hover", 25, recovered),
                _candidate("stretch", 35, recovered),
                _candidate(NONE_ACTION, 10, recovered),
            ),
            ActionEvent.NORMAL_IDLE.value: (_candidate("idle", 100, normal),),
            ActionEvent.LOW_ON_ENTER.value: (
                _candidate("sit_transition", 80, low),
                _candidate(NONE_ACTION, 20, low),
            ),
            ActionEvent.LOW_IDLE.value: (
                _candidate("sit", 90, low),
                _candidate("idle", 10, low),
            ),
            ActionEvent.LOW_ON_EXIT.value: (_candidate(NONE_ACTION, 100, low),),
            ActionEvent.CRITICAL_ON_ENTER.value: (_candidate(NONE_ACTION, 100, critical),),
            ActionEvent.CRITICAL_IDLE.value: (
                _candidate("critical", 90, critical),
                _candidate("sit", 10, critical),
            ),
            ActionEvent.CRITICAL_ON_EXIT.value: (_candidate(NONE_ACTION, 100, critical),),
            ActionEvent.EMPTY_ON_ENTER.value: (_candidate(NONE_ACTION, 100, empty),),
            ActionEvent.EMPTY_IDLE.value: (_candidate("sleep", 100, empty),),
            ActionEvent.EMPTY_ON_EXIT.value: (_candidate(NONE_ACTION, 100, empty),),
        }
    )


def parse_action_policy(value: Any) -> ActionPolicy:
    defaults = default_action_policy()
    if value is None:
        return defaults
    if not isinstance(value, dict):
        raise ValueError("action_policy must be an object")
    pools = dict(defaults.pools)
    event_names = {item.value for item in ActionEvent}
    if "pools" in value or "action_pools" in value:
        raw_pools = value.get("pools", value.get("action_pools", {}))
    elif any(str(key) in event_names for key in value):
        # Also accept the concise top-level `action_pools` payload passed by
        # older manifests: {"hover": [...], "click": [...]}.
        raw_pools = value
    else:
        raw_pools = {}
    if not isinstance(raw_pools, dict):
        raise ValueError("action policy pools must be an object")
    for event, raw_candidates in raw_pools.items():
        event_name = str(event)
        if event_name not in event_names:
            continue
        if not isinstance(raw_candidates, list):
            raise ValueError(f"action pool {event_name} must be a list")
        parsed: list[ActionCandidate] = []
        for raw_candidate in raw_candidates:
            if not isinstance(raw_candidate, dict):
                raise ValueError(f"invalid candidate in {event_name}")
            action = str(raw_candidate.get("action", "")).strip().lower()
            if not action:
                raise ValueError(f"missing action in {event_name}")
            weight = _bounded_int(raw_candidate.get("weight"), 1, 1, 10_000)
            cooldown = raw_candidate.get("cooldown", [0, 0])
            if isinstance(cooldown, (int, float)):
                low = high = _bounded_int(cooldown, 0, 0, 3_600_000)
            elif isinstance(cooldown, (list, tuple)) and len(cooldown) == 2:
                low = _bounded_int(cooldown[0], 0, 0, 3_600_000)
                high = _bounded_int(cooldown[1], low, low, 3_600_000)
            else:
                raise ValueError(f"invalid cooldown in {event_name}")
            raw_states = raw_candidate.get("allowed_states")
            allowed: frozenset[PetState] | None = None
            if raw_states is not None:
                if not isinstance(raw_states, list):
                    raise ValueError(f"allowed_states must be a list in {event_name}")
                try:
                    allowed = frozenset(PetState(str(item).lower()) for item in raw_states)
                except ValueError as exc:
                    raise ValueError(f"invalid allowed state in {event_name}") from exc
            parsed.append(ActionCandidate(action, weight, low, high, allowed))
        pools[event_name] = tuple(parsed)
    interval_min = _bounded_int(value.get("idle_interval_min"), 45, 5, 3600) * 1000
    interval_max = _bounded_int(value.get("idle_interval_max"), 150, interval_min // 1000, 7200) * 1000
    return ActionPolicy(
        pools=pools,
        idle_trigger_probability=_bounded_float(
            value.get("idle_trigger_probability"), 0.7, 0.0, 1.0
        ),
        idle_interval_min_ms=interval_min,
        idle_interval_max_ms=interval_max,
        avoid_immediate_repeat=bool(value.get("avoid_immediate_repeat", True)),
        history_size=_bounded_int(value.get("history_size"), 3, 1, 10),
    )


class ActionSelector:
    def __init__(
        self,
        policy: ActionPolicy,
        *,
        rng: random.Random | None = None,
        overrides: dict[str, list[str]] | None = None,
    ) -> None:
        self.policy = policy
        self.rng = rng or random.Random()
        self.overrides = overrides or {}
        self._cooldowns: dict[str, float] = {}
        self._history: deque[str] = deque(maxlen=policy.history_size)

    @property
    def history(self) -> tuple[str, ...]:
        return tuple(self._history)

    def set_policy(self, policy: ActionPolicy) -> None:
        self.policy = policy
        self._history = deque(self._history, maxlen=policy.history_size)

    def set_overrides(self, overrides: dict[str, list[str]] | None) -> None:
        self.overrides = overrides or {}

    def choose(
        self,
        event: ActionEvent | str,
        *,
        state: PetState,
        supported_actions: set[str],
        now: float | None = None,
        use_cooldown: bool = True,
        avoid_repeat: bool = True,
    ) -> ActionDecision:
        event_name = event.value if isinstance(event, ActionEvent) else str(event)
        moment = time.monotonic() if now is None else now
        candidates = list(self.policy.pool(event_name))
        if event_name in self.overrides:
            enabled = set(self.overrides[event_name])
            candidates = [candidate for candidate in candidates if candidate.action in enabled]
        candidates = [
            candidate
            for candidate in candidates
            if (candidate.allowed_states is None or state in candidate.allowed_states)
            and (candidate.action == NONE_ACTION or candidate.action in supported_actions)
            and (
                not use_cooldown
                or candidate.action == NONE_ACTION
                or moment >= self._cooldowns.get(candidate.action, float("-inf"))
            )
        ]
        real_actions = {candidate.action for candidate in candidates if candidate.action != NONE_ACTION}
        if (
            avoid_repeat
            and self.policy.avoid_immediate_repeat
            and self._history
            and len(real_actions) > 1
        ):
            last = self._history[-1]
            without_last = [candidate for candidate in candidates if candidate.action != last]
            if without_last:
                candidates = without_last
        if not candidates:
            return ActionDecision(event_name, None, "empty")
        selected = self.rng.choices(
            candidates,
            weights=[candidate.weight for candidate in candidates],
            k=1,
        )[0]
        reason = "none" if selected.action == NONE_ACTION else "selected"
        return ActionDecision(event_name, selected, reason)

    def commit(
        self,
        decision: ActionDecision,
        *,
        now: float | None = None,
        fallback_cooldown_ms: int = 0,
    ) -> None:
        candidate = decision.candidate
        if candidate is None or candidate.action == NONE_ACTION:
            return
        moment = time.monotonic() if now is None else now
        low = candidate.cooldown_min_ms
        high = candidate.cooldown_max_ms
        cooldown_ms = self.rng.randint(low, high) if high > 0 else fallback_cooldown_ms
        if cooldown_ms > 0:
            self._cooldowns[candidate.action] = moment + cooldown_ms / 1000
        self._history.append(candidate.action)


def persistent_event(state: PetState) -> ActionEvent:
    return {
        PetState.NORMAL: ActionEvent.NORMAL_IDLE,
        PetState.LOW: ActionEvent.LOW_IDLE,
        PetState.CRITICAL: ActionEvent.CRITICAL_IDLE,
        PetState.EMPTY: ActionEvent.EMPTY_IDLE,
        PetState.RECOVERED: ActionEvent.NORMAL_IDLE,
    }[state]


def enter_event(state: PetState) -> ActionEvent | None:
    return {
        PetState.NORMAL: None,
        PetState.LOW: ActionEvent.LOW_ON_ENTER,
        PetState.CRITICAL: ActionEvent.CRITICAL_ON_ENTER,
        PetState.EMPTY: ActionEvent.EMPTY_ON_ENTER,
        PetState.RECOVERED: ActionEvent.RECOVERED,
    }[state]


def exit_event(state: PetState) -> ActionEvent | None:
    return {
        PetState.NORMAL: None,
        PetState.LOW: ActionEvent.LOW_ON_EXIT,
        PetState.CRITICAL: ActionEvent.CRITICAL_ON_EXIT,
        PetState.EMPTY: ActionEvent.EMPTY_ON_EXIT,
        PetState.RECOVERED: None,
    }[state]


def _bounded_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return default


def _bounded_float(value: Any, default: float, low: float, high: float) -> float:
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return default
