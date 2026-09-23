from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from codex_usage_pet.pet.animator import PetActivity

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
    activity: PetActivity
    path: Path
    cell: tuple[int, int] | None = None
    grid: tuple[int, int] = (1, 1)
    offset_x: float = 0.0
    offset_y: float = 0.0
    frames: tuple[tuple[int, int], ...] = ()
    fps: float = 0.0
    loop: bool = False
    cooldown_ms: int = 0
    interruptible: bool = True
    fallback_from: PetActivity | None = None

    @property
    def frame_count(self) -> int:
        return len(self.frames) or 1

    @property
    def duration_ms(self) -> int:
        if self.frame_count <= 1 or self.fps <= 0:
            return 0
        return round(self.frame_count * 1000 / self.fps)

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
    states: dict[PetActivity, SkinStateAsset] = field(default_factory=dict)
    preferred_width: int = 222
    preferred_height: int = 222
    anchor_x: float = 0.0
    anchor_y: float = -3.0

    def asset_for(self, activity: PetActivity) -> SkinStateAsset:
        return self.states[activity]

    def has_explicit_state(self, activity: PetActivity) -> bool:
        asset = self.states.get(activity)
        return asset is not None and asset.fallback_from is None
