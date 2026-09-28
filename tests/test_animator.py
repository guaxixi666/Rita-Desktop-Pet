from codex_usage_pet.pet.animator import PetActivity, PetBehaviorController
from codex_usage_pet.pet.states import PetState


def test_quota_state_cannot_change_base_pose() -> None:
    controller = PetBehaviorController()
    for state, requested in (
        (PetState.LOW, PetActivity.SIT),
        (PetState.CRITICAL, PetActivity.CRITICAL),
        (PetState.EMPTY, PetActivity.SLEEP),
        (PetState.RECOVERED, PetActivity.STRETCH),
    ):
        assert controller.set_quota_state(state, requested) is PetActivity.IDLE
        assert controller.advance() is PetActivity.IDLE


def test_normal_base_pose_remains_static_idle() -> None:
    controller = PetBehaviorController()
    controller.set_quota_state(PetState.NORMAL)
    seen = {controller.advance() for _ in range(30)}
    assert seen == {PetActivity.IDLE}


def test_return_to_normal_restarts_at_idle() -> None:
    controller = PetBehaviorController()
    controller.set_quota_state(PetState.EMPTY)
    assert controller.set_quota_state(PetState.NORMAL) is PetActivity.IDLE

