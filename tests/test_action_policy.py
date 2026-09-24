from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from codex_usage_pet.pet.action_policy import (
    ActionCandidate,
    ActionEvent,
    ActionPolicy,
    ActionSelector,
    default_action_policy,
    parse_action_policy,
)
from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.skins.loader import SkinRepository
from codex_usage_pet.ui.pet_widget import PetWidget


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


def _selector(
    event: ActionEvent,
    *candidates: ActionCandidate,
    avoid_repeat: bool = True,
) -> ActionSelector:
    return ActionSelector(
        ActionPolicy(
            pools={event.value: tuple(candidates)},
            avoid_immediate_repeat=avoid_repeat,
        ),
        rng=FirstChoiceRandom(),  # type: ignore[arg-type]
    )


def _packs():
    repository = SkinRepository([Path(__file__).parents[1] / "skins"])
    return repository.scan()


def test_hover_pool_is_not_fixed_to_blink() -> None:
    selector = _selector(
        ActionEvent.HOVER,
        ActionCandidate("blink", 10),
        ActionCandidate("hover", 10),
    )
    first = selector.choose(
        ActionEvent.HOVER, state=PetState.NORMAL, supported_actions={"blink", "hover"}
    )
    selector.commit(first, now=1)
    second = selector.choose(
        ActionEvent.HOVER, state=PetState.NORMAL, supported_actions={"blink", "hover"}
    )
    assert (first.action, second.action) == ("blink", "hover")


def test_click_and_recovered_can_select_multiple_actions() -> None:
    for event in (ActionEvent.CLICK, ActionEvent.RECOVERED):
        selector = _selector(
            event,
            ActionCandidate("wave", 10),
            ActionCandidate("stretch", 10),
        )
        state = PetState.NORMAL if event is ActionEvent.CLICK else PetState.RECOVERED
        first = selector.choose(event, state=state, supported_actions={"wave", "stretch"})
        selector.commit(first, now=1)
        second = selector.choose(event, state=state, supported_actions={"wave", "stretch"})
        assert {first.action, second.action} == {"wave", "stretch"}


def test_unsupported_and_wrong_state_actions_are_filtered() -> None:
    selector = _selector(
        ActionEvent.CLICK,
        ActionCandidate("missing", 100),
        ActionCandidate("wave", 1, allowed_states=frozenset({PetState.NORMAL})),
    )
    normal = selector.choose(
        ActionEvent.CLICK, state=PetState.NORMAL, supported_actions={"wave"}
    )
    empty = selector.choose(
        ActionEvent.CLICK, state=PetState.EMPTY, supported_actions={"wave"}
    )
    assert normal.action == "wave"
    assert empty.action is None
    assert empty.reason == "empty"


def test_cooldown_filters_action_until_available() -> None:
    selector = _selector(
        ActionEvent.CLICK,
        ActionCandidate("wave", 10, cooldown_min_ms=1000, cooldown_max_ms=1000),
    )
    first = selector.choose(
        ActionEvent.CLICK, state=PetState.NORMAL, supported_actions={"wave"}, now=10
    )
    selector.commit(first, now=10)
    blocked = selector.choose(
        ActionEvent.CLICK, state=PetState.NORMAL, supported_actions={"wave"}, now=10.5
    )
    ready = selector.choose(
        ActionEvent.CLICK, state=PetState.NORMAL, supported_actions={"wave"}, now=11
    )
    assert first.action == "wave"
    assert blocked.action is None
    assert ready.action == "wave"


def test_only_action_can_repeat_but_multiple_actions_avoid_immediate_repeat() -> None:
    single = _selector(ActionEvent.IDLE_RANDOM, ActionCandidate("blink", 10))
    first = single.choose(
        ActionEvent.IDLE_RANDOM, state=PetState.NORMAL, supported_actions={"blink"}
    )
    single.commit(first)
    assert (
        single.choose(
            ActionEvent.IDLE_RANDOM, state=PetState.NORMAL, supported_actions={"blink"}
        ).action
        == "blink"
    )

    multiple = _selector(
        ActionEvent.IDLE_RANDOM,
        ActionCandidate("blink", 10),
        ActionCandidate("wave", 10),
    )
    selected = multiple.choose(
        ActionEvent.IDLE_RANDOM,
        state=PetState.NORMAL,
        supported_actions={"blink", "wave"},
    )
    multiple.commit(selected)
    assert (
        multiple.choose(
            ActionEvent.IDLE_RANDOM,
            state=PetState.NORMAL,
            supported_actions={"blink", "wave"},
        ).action
        == "wave"
    )


def test_none_and_empty_pool_are_safe() -> None:
    none_selector = _selector(ActionEvent.HOVER, ActionCandidate("none", 10))
    none = none_selector.choose(
        ActionEvent.HOVER, state=PetState.NORMAL, supported_actions=set()
    )
    empty = ActionSelector(ActionPolicy(), rng=FirstChoiceRandom()).choose(  # type: ignore[arg-type]
        ActionEvent.HOVER, state=PetState.NORMAL, supported_actions=set()
    )
    assert none.action is None and none.reason == "none"
    assert empty.action is None and empty.reason == "empty"


def test_user_override_and_restore_default() -> None:
    selector = _selector(
        ActionEvent.CLICK,
        ActionCandidate("click", 10),
        ActionCandidate("wave", 10),
    )
    selector.set_overrides({ActionEvent.CLICK.value: ["wave"]})
    assert (
        selector.choose(
            ActionEvent.CLICK,
            state=PetState.NORMAL,
            supported_actions={"click", "wave"},
        ).action
        == "wave"
    )
    selector.set_overrides(None)
    assert (
        selector.choose(
            ActionEvent.CLICK,
            state=PetState.NORMAL,
            supported_actions={"click", "wave"},
        ).action
        == "click"
    )


def test_bundled_skins_have_different_personality() -> None:
    packs = _packs()
    umbral = packs["rita_umbral_rose"].action_policy
    moonlit = packs["rita_moonlit_rose"].action_policy
    assert umbral.idle_trigger_probability != moonlit.idle_trigger_probability
    assert umbral.pool(ActionEvent.IDLE_RANDOM) != moonlit.pool(ActionEvent.IDLE_RANDOM)


def test_concise_top_level_action_pools_schema_is_supported() -> None:
    policy = parse_action_policy(
        {"hover": [{"action": "blink", "weight": 7, "cooldown": 1000}]}
    )
    assert policy.pool(ActionEvent.HOVER) == (
        ActionCandidate("blink", 7, 1000, 1000),
    )


def test_low_enter_idle_exit_sequence_uses_policy(app) -> None:
    skin = _packs()["rita_umbral_rose"]
    pools = dict(default_action_policy().pools)
    pools[ActionEvent.LOW_ON_ENTER.value] = (ActionCandidate("sit_transition", 100),)
    pools[ActionEvent.LOW_IDLE.value] = (ActionCandidate("sit", 100),)
    pools[ActionEvent.LOW_ON_EXIT.value] = (ActionCandidate("wave", 100),)
    policy_skin = replace(skin, action_policy=replace(default_action_policy(), pools=pools))
    widget = PetWidget(policy_skin, rng=FirstChoiceRandom())  # type: ignore[arg-type]

    widget.set_state(PetState.LOW)
    assert widget.activity is PetActivity.SIT_TRANSITION
    for _ in range(widget.skin.asset_for(PetActivity.SIT_TRANSITION).frame_count):
        widget._advance_frame()
    assert widget.activity is PetActivity.SIT

    widget.set_state(PetState.NORMAL)
    assert widget.activity is PetActivity.WAVE
    for _ in range(widget.skin.asset_for(PetActivity.WAVE).frame_count):
        widget._advance_frame()
    assert widget.activity is PetActivity.IDLE


def test_critical_cannot_be_overridden_by_random_idle(app) -> None:
    widget = PetWidget(_packs()["rita_umbral_rose"], rng=FirstChoiceRandom())  # type: ignore[arg-type]
    widget.set_state(PetState.CRITICAL)
    activity = widget.activity
    widget._run_idle_action()
    assert widget.activity is activity
    assert widget._action_activity is None
