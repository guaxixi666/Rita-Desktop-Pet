from codex_usage_pet.pet.states import PetState, PetStateTracker, state_for_remaining


def test_thresholds() -> None:
    assert state_for_remaining(75) is PetState.NORMAL
    assert state_for_remaining(30) is PetState.LOW
    assert state_for_remaining(10) is PetState.LOW
    assert state_for_remaining(9.9) is PetState.CRITICAL
    assert state_for_remaining(0) is PetState.EMPTY


def test_low_to_high_is_recovered_once() -> None:
    tracker = PetStateTracker()
    assert tracker.update(5) is PetState.CRITICAL
    assert tracker.update(85) is PetState.RECOVERED
    assert tracker.update(85) is PetState.NORMAL


def test_high_to_low() -> None:
    tracker = PetStateTracker()
    assert tracker.update(80) is PetState.NORMAL
    assert tracker.update(20) is PetState.LOW

