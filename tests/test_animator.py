from codex_usage_pet.pet.animator import PetActivity, PetBehaviorController
from codex_usage_pet.pet.states import PetState


def test_action_policy_can_supply_each_quota_base_pose() -> None:
    controller = PetBehaviorController()
    assert controller.set_quota_state(PetState.LOW, PetActivity.SIT) is PetActivity.SIT
    assert controller.advance() is PetActivity.SIT
    assert (
        controller.set_quota_state(PetState.CRITICAL, PetActivity.CRITICAL)
        is PetActivity.CRITICAL
    )
    assert controller.set_quota_state(PetState.EMPTY, PetActivity.SLEEP) is PetActivity.SLEEP
    assert (
        controller.set_quota_state(PetState.RECOVERED, PetActivity.STRETCH)
        is PetActivity.STRETCH
    )


def test_normal_base_pose_remains_static_idle() -> None:
    controller = PetBehaviorController()
    controller.set_quota_state(PetState.NORMAL)
    seen = {controller.advance() for _ in range(30)}
    assert seen == {PetActivity.IDLE}


def test_return_to_normal_restarts_at_idle() -> None:
    controller = PetBehaviorController()
    controller.set_quota_state(PetState.EMPTY)
    assert controller.set_quota_state(PetState.NORMAL) is PetActivity.IDLE

