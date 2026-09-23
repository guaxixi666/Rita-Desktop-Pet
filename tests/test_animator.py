from codex_usage_pet.pet.animator import PetActivity, PetBehaviorController
from codex_usage_pet.pet.states import PetState


def test_quota_states_force_expected_pose() -> None:
    controller = PetBehaviorController()
    assert controller.set_quota_state(PetState.LOW) is PetActivity.SIT
    assert controller.advance() is PetActivity.SIT
    assert controller.set_quota_state(PetState.CRITICAL) is PetActivity.CRITICAL
    assert controller.set_quota_state(PetState.EMPTY) is PetActivity.SLEEP
    assert controller.set_quota_state(PetState.RECOVERED) is PetActivity.STRETCH


def test_normal_base_pose_remains_static_idle() -> None:
    controller = PetBehaviorController()
    controller.set_quota_state(PetState.NORMAL)
    seen = {controller.advance() for _ in range(30)}
    assert seen == {PetActivity.IDLE}


def test_return_to_normal_restarts_at_idle() -> None:
    controller = PetBehaviorController()
    controller.set_quota_state(PetState.EMPTY)
    assert controller.set_quota_state(PetState.NORMAL) is PetActivity.IDLE

