from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from codex_usage_pet.pet.action_policy import ActionCandidate, ActionEvent, ActionPolicy, ActionSelector, parse_action_policy
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.skins.loader import SkinRepository


class FirstChoiceRandom:
    def choices(self, population, *, weights, k):  # type: ignore[no-untyped-def]
        return [population[0]]

    def randint(self, low: int, _high: int) -> int:
        return low

    def random(self) -> float:
        return 0.0


@pytest.fixture(scope="module")
def app() -> QApplication:
    return QApplication.instance() or QApplication([])


def _selector(event: ActionEvent, *candidates: ActionCandidate) -> ActionSelector:
    return ActionSelector(ActionPolicy(pools={event.value: tuple(candidates)}), rng=FirstChoiceRandom())  # type: ignore[arg-type]


def _packs():
    return SkinRepository([Path(__file__).parents[1] / "skins"]).scan()


def test_click_and_random_idle_are_the_only_runtime_events() -> None:
    assert set(ActionEvent) == {ActionEvent.CLICK, ActionEvent.IDLE_RANDOM}


def test_quota_state_never_filters_click_or_idle_action() -> None:
    selector = _selector(ActionEvent.CLICK, ActionCandidate("wave", 1, allowed_states=frozenset({PetState.NORMAL})))
    for state in PetState:
        assert selector.choose(ActionEvent.CLICK, state=state, supported_actions={"wave"}).action == "wave"


def test_only_missing_assets_and_cooldown_filter_candidates() -> None:
    selector = _selector(
        ActionEvent.CLICK,
        ActionCandidate("missing", 100),
        ActionCandidate("wave", 1, cooldown_min_ms=1000, cooldown_max_ms=1000),
    )
    first = selector.choose(ActionEvent.CLICK, state=PetState.EMPTY, supported_actions={"wave"}, now=10)
    selector.commit(first, now=10)
    blocked = selector.choose(ActionEvent.CLICK, state=PetState.NORMAL, supported_actions={"wave"}, now=10.5)
    ready = selector.choose(ActionEvent.CLICK, state=PetState.CRITICAL, supported_actions={"wave"}, now=11)
    assert first.action == "wave"
    assert blocked.action is None
    assert ready.action == "wave"


def test_recent_history_avoids_immediate_repeat() -> None:
    selector = _selector(ActionEvent.IDLE_RANDOM, ActionCandidate("blink", 10), ActionCandidate("wave", 10))
    first = selector.choose(ActionEvent.IDLE_RANDOM, state=PetState.NORMAL, supported_actions={"blink", "wave"})
    selector.commit(first)
    second = selector.choose(ActionEvent.IDLE_RANDOM, state=PetState.EMPTY, supported_actions={"blink", "wave"})
    assert (first.action, second.action) == ("blink", "wave")


def test_none_and_empty_pool_are_safe() -> None:
    none = _selector(ActionEvent.CLICK, ActionCandidate("none", 10)).choose(
        ActionEvent.CLICK, state=PetState.EMPTY, supported_actions=set()
    )
    empty = ActionSelector(ActionPolicy(), rng=FirstChoiceRandom()).choose(  # type: ignore[arg-type]
        ActionEvent.CLICK, state=PetState.NORMAL, supported_actions=set()
    )
    assert none.action is None and none.reason == "none"
    assert empty.action is None and empty.reason == "empty"


def test_overrides_and_legacy_action_ids_are_normalized() -> None:
    selector = _selector(ActionEvent.CLICK, ActionCandidate("surprised", 10), ActionCandidate("wave", 10))
    selector.set_overrides({"click": ["click"], "hover": ["hover"]})
    assert selector.overrides == {"click": ["surprised"]}
    assert selector.choose(
        ActionEvent.CLICK, state=PetState.EMPTY, supported_actions={"surprised", "wave"}
    ).action == "surprised"


def test_bundled_pools_have_quality_choices_and_no_state_filters() -> None:
    for skin in _packs().values():
        click = skin.action_policy.pool(ActionEvent.CLICK)
        idle = skin.action_policy.pool(ActionEvent.IDLE_RANDOM)
        assert len(click) == len(idle) == 7
        assert all(candidate.allowed_states is None for candidate in (*click, *idle))
        assert {candidate.action for candidate in click if candidate.action != "none"} == {
            "smile", "surprised", "wave", "tidy_hair", "sit", "sleepy"
        }
        assert {candidate.action for candidate in idle if candidate.action != "none"} == {
            "blink", "smile", "wave", "tidy_hair", "sit", "sleepy"
        }


def test_concise_click_schema_is_supported() -> None:
    policy = parse_action_policy({"click": [{"action": "wave", "weight": 7, "cooldown": 1000}]})
    assert policy.pool(ActionEvent.CLICK) == (ActionCandidate("wave", 7, 1000, 1000),)
