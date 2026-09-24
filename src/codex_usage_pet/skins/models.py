from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.pet.action_policy import ActionPolicy, default_action_policy

DEFAULT_SKIN_ID = "rita_umbral_rose"


@dataclass(frozen=True, slots=True)
class SkinTheme:
    background: str = "#17171D"
    panel: str = "#24222B"
    progress_track: str = "#35313A"
    primary: str = "#C05A78"
    highlight: str = "#DA7892"
    critical: str = "#87364E"
    empty: str = "#958594"
    low: str = "#E8C3CD"
    text_primary: str = "#F3ECEE"
    text_secondary: str = "#BDAFB5"
    border: str = "#87364E"
    decorator: str = "✿"


@dataclass(frozen=True, slots=True)
class SkinStateAsset:
    activity: PetActivity | str
    path: Path
    cell: tuple[int, int] | None = None
    grid: tuple[int, int] = (1, 1)
    offset_x: float = 0.0
    offset_y: float = 0.0
    frames: tuple[tuple[int, int], ...] = ()
    fps: float = 0.0
    frame_durations_ms: tuple[int, ...] = ()
    loop: bool = False
    cooldown_ms: int = 0
    interruptible: bool = True
    fallback_from: PetActivity | str | None = None

    @property
    def frame_count(self) -> int:
        return len(self.frames) or 1

    @property
    def duration_ms(self) -> int:
        if self.frame_durations_ms:
            return sum(self.frame_durations_ms)
        if self.frame_count <= 1 or self.fps <= 0:
            return 0
        return round(self.frame_count * 1000 / self.fps)

    def frame_duration_ms(self, index: int) -> int:
        """Return this frame's display time; explicit timing outranks FPS."""
        if self.frame_durations_ms:
            duration = self.frame_durations_ms[index % len(self.frame_durations_ms)]
            if duration > 0:
                return duration
        if self.fps > 0:
            return max(33, round(1000 / self.fps))
        # A malformed optional skin must not freeze halfway through a
        # multi-frame action. Static poses intentionally do not need a timer.
        return 100 if self.frame_count > 1 else 0

    def cell_at(self, index: int) -> tuple[int, int]:
        if self.frames:
            return self.frames[index % len(self.frames)]
        return self.cell or (0, 0)


@dataclass(frozen=True, slots=True)
class SkinPack:
    id: str
    name: str
    author: str
    version: str
    description: str
    root: Path
    preview_path: Path | None
    theme: SkinTheme
    states: dict[PetActivity | str, SkinStateAsset] = field(default_factory=dict)
    action_policy: ActionPolicy = field(default_factory=default_action_policy)
    preferred_width: int = 222
    preferred_height: int = 222
    anchor_x: float = 0.0
    anchor_y: float = -3.0

    def asset_for(self, activity: PetActivity | str) -> SkinStateAsset:
        return self.states[self.resolve_activity(activity)]

    def has_explicit_state(self, activity: PetActivity | str) -> bool:
        key = self.resolve_activity(activity, required=False)
        asset = self.states.get(key) if key is not None else None
        return asset is not None and asset.fallback_from is None

    @property
    def supported_actions(self) -> set[str]:
        return {
            item.value if isinstance(item, PetActivity) else item
            for item, asset in self.states.items()
            if asset.fallback_from is None
        }

    def resolve_activity(
        self, activity: PetActivity | str, *, required: bool = True
    ) -> PetActivity | str | None:
        if isinstance(activity, PetActivity) and activity in self.states:
            return activity
        value = activity.value if isinstance(activity, PetActivity) else str(activity)
        try:
            known = PetActivity(value)
        except ValueError:
            known = None
        if known is not None and known in self.states:
            return known
        if value in self.states:
            return value
        if required:
            raise KeyError(value)
        return None
