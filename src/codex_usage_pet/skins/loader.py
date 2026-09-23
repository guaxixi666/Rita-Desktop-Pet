from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import fields
from pathlib import Path
from typing import Any

from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.services.paths import app_data_dir, resource_path

from .models import DEFAULT_SKIN_ID, SkinPack, SkinStateAsset, SkinTheme

LOGGER = logging.getLogger(__name__)
_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_COLOR_PATTERN = re.compile(r"^#[0-9a-fA-F]{6}$")
_FALLBACKS = {
    PetActivity.WALK: (PetActivity.IDLE,),
    PetActivity.SIT: (PetActivity.IDLE,),
    PetActivity.STRETCH: (PetActivity.IDLE,),
    PetActivity.CRITICAL: (PetActivity.SIT, PetActivity.IDLE),
    PetActivity.SLEEP: (PetActivity.IDLE,),
    PetActivity.HOVER: (PetActivity.IDLE,),
    PetActivity.CLICK: (PetActivity.IDLE,),
    PetActivity.BLINK: (PetActivity.IDLE,),
    PetActivity.LOOK_LEFT: (PetActivity.IDLE,),
    PetActivity.LOOK_RIGHT: (PetActivity.IDLE,),
    PetActivity.WAVE: (PetActivity.IDLE,),
    PetActivity.SLEEP_REACT: (PetActivity.SLEEP, PetActivity.IDLE),
}


class InvalidSkinError(ValueError):
    pass


def user_skin_dir() -> Path:
    return app_data_dir() / "skins"


def default_skin_roots() -> list[Path]:
    roots = [resource_path("skins")]
    if getattr(sys, "frozen", False):
        portable = Path(sys.executable).resolve().parent / "skins"
        if portable not in roots:
            roots.append(portable)
    personal = user_skin_dir()
    if personal not in roots:
        roots.append(personal)
    return roots


class SkinRepository:
    def __init__(self, roots: list[Path] | None = None) -> None:
        self.roots = roots or default_skin_roots()
        self.packs: dict[str, SkinPack] = {}

    def scan(self) -> dict[str, SkinPack]:
        found: dict[str, SkinPack] = {}
        for root in self.roots:
            if not root.exists():
                continue
            for manifest in sorted(root.glob("*/skin.json")):
                try:
                    pack = load_skin(manifest)
                except (InvalidSkinError, OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                    LOGGER.warning("Invalid skin skipped: %s (%s)", manifest.parent.name, type(exc).__name__)
                    continue
                if pack.id in found:
                    LOGGER.info("Skin loaded: %s (override from %s)", pack.id, manifest.parent)
                else:
                    LOGGER.info("Skin loaded: %s", pack.id)
                found[pack.id] = pack
        self.packs = found
        return dict(found)

    def default(self) -> SkinPack:
        if DEFAULT_SKIN_ID in self.packs:
            return self.packs[DEFAULT_SKIN_ID]
        if self.packs:
            return next(iter(self.packs.values()))
        raise InvalidSkinError("No valid skin packs were found")


def load_skin(manifest: Path) -> SkinPack:
    root = manifest.parent.resolve()
    raw = json.loads(manifest.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise InvalidSkinError("skin.json must contain an object")
    skin_id = str(raw.get("id", ""))
    if not _ID_PATTERN.fullmatch(skin_id):
        raise InvalidSkinError("invalid skin id")
    name = str(raw.get("name", "")).strip()
    if not name:
        raise InvalidSkinError("skin name is required")

    theme = _parse_theme(raw.get("theme"))
    state_payload = raw.get("states")
    if not isinstance(state_payload, dict) or "idle" not in state_payload:
        raise InvalidSkinError("an idle state is required")
    parsed: dict[PetActivity, SkinStateAsset] = {}
    for activity in PetActivity:
        value = state_payload.get(activity.value)
        if value is None:
            continue
        parsed[activity] = _parse_state(root, activity, value)
    if PetActivity.IDLE not in parsed:
        raise InvalidSkinError("idle asset is invalid")

    resolved = dict(parsed)
    for activity in PetActivity:
        if activity in resolved:
            continue
        for fallback in _FALLBACKS.get(activity, (PetActivity.IDLE,)):
            if fallback in resolved:
                source = resolved[fallback]
                resolved[activity] = SkinStateAsset(
                    activity=activity,
                    path=source.path,
                    cell=source.cell,
                    grid=source.grid,
                    offset_x=source.offset_x,
                    offset_y=source.offset_y,
                    frames=source.frames,
                    fps=source.fps,
                    loop=source.loop,
                    cooldown_ms=source.cooldown_ms,
                    interruptible=source.interruptible,
                    fallback_from=fallback,
                )
                LOGGER.info("Skin fallback: %s %s -> %s", skin_id, activity.value, fallback.value)
                break

    preview = raw.get("preview")
    preview_path = _safe_asset(root, str(preview)) if preview else None
    if preview_path is not None and not preview_path.is_file():
        preview_path = None
    return SkinPack(
        id=skin_id,
        name=name,
        author=str(raw.get("author", "Unknown")),
        version=str(raw.get("version", "1.0")),
        description=str(raw.get("description", "")),
        root=root,
        preview_path=preview_path,
        theme=theme,
        states=resolved,
        preferred_width=_bounded_int(raw.get("preferred_width"), 222, 80, 320),
        preferred_height=_bounded_int(raw.get("preferred_height"), 222, 80, 320),
        anchor_x=_bounded_float(raw.get("anchor_x"), 0.0, -160.0, 160.0),
        anchor_y=_bounded_float(raw.get("anchor_y"), -3.0, -160.0, 160.0),
    )


def _parse_theme(value: Any) -> SkinTheme:
    raw = value if isinstance(value, dict) else {}
    defaults = SkinTheme()
    values: dict[str, str] = {}
    for item in fields(SkinTheme):
        candidate = raw.get(item.name, getattr(defaults, item.name))
        if item.name == "decorator":
            values[item.name] = str(candidate)[:3] or defaults.decorator
        else:
            text = str(candidate)
            values[item.name] = text if _COLOR_PATTERN.fullmatch(text) else getattr(defaults, item.name)
    return SkinTheme(**values)


def _parse_state(root: Path, activity: PetActivity, value: Any) -> SkinStateAsset:
    data = {"file": value} if isinstance(value, str) else value
    if not isinstance(data, dict) or not (data.get("file") or data.get("source")):
        raise InvalidSkinError(f"invalid {activity.value} state")
    path = _safe_asset(root, str(data.get("file") or data["source"]))
    if not path.is_file():
        raise InvalidSkinError(f"missing asset for {activity.value}")
    grid_raw = data.get("grid", [1, 1])
    cell_raw = data.get("cell")
    grid = _pair(grid_raw, (1, 1), minimum=1)
    cell = _pair(cell_raw, (0, 0), minimum=0) if cell_raw is not None else None
    if cell is not None and (cell[0] >= grid[0] or cell[1] >= grid[1]):
        raise InvalidSkinError(f"cell outside grid for {activity.value}")
    frames_raw = data.get("frames")
    frames: tuple[tuple[int, int], ...] = ()
    if isinstance(frames_raw, list):
        parsed_frames = tuple(_pair(item, (0, 0), minimum=0) for item in frames_raw)
        if any(frame[0] >= grid[0] or frame[1] >= grid[1] for frame in parsed_frames):
            raise InvalidSkinError(f"animation frame outside grid for {activity.value}")
        frames = parsed_frames
    elif isinstance(frames_raw, int) and frames_raw > 0:
        frames = tuple((index % grid[0], index // grid[0]) for index in range(frames_raw))
        if any(frame[1] >= grid[1] for frame in frames):
            raise InvalidSkinError(f"animation frame outside grid for {activity.value}")
    fps = _bounded_float(data.get("fps"), 0.0, 0.0, 30.0)
    if frames and len(frames) > 1 and fps <= 0:
        raise InvalidSkinError(f"animated state requires fps for {activity.value}")
    return SkinStateAsset(
        activity=activity,
        path=path,
        cell=cell,
        grid=grid,
        offset_x=_bounded_float(data.get("offset_x"), 0.0, -160.0, 160.0),
        offset_y=_bounded_float(data.get("offset_y"), 0.0, -160.0, 160.0),
        frames=frames,
        fps=fps,
        loop=bool(data.get("loop", False)),
        cooldown_ms=_bounded_int(data.get("cooldown"), 0, 0, 600_000),
        interruptible=bool(data.get("interruptible", True)),
    )


def _safe_asset(root: Path, relative: str) -> Path:
    candidate = (root / relative).resolve()
    if not candidate.is_relative_to(root):
        raise InvalidSkinError("asset path escapes skin directory")
    return candidate


def _pair(value: Any, default: tuple[int, int], minimum: int) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return default
    return (max(minimum, int(value[0])), max(minimum, int(value[1])))


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
