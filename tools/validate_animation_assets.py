"""Validate Skin Pack animation geometry, alpha hygiene, timing, and foot anchors."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "animations" / "validation.json"
ACTIONS = ("blink", "smile", "surprised", "wave", "tidy_hair", "sit", "sleepy")


def _frame_boxes(
    image: Image.Image,
    grid: tuple[int, int],
    frames: int | list[list[int]],
) -> list[tuple[int, int, int, int]]:
    columns, rows = grid
    width, height = image.size
    boxes = []
    cells = (
        [(index % columns, index // columns) for index in range(frames)]
        if isinstance(frames, int)
        else [(int(column), int(row)) for column, row in frames]
    )
    for column, row in cells:
        boxes.append(
            (
                round(column * width / columns),
                round(row * height / rows),
                round((column + 1) * width / columns),
                round((row + 1) * height / rows),
            )
        )
    return boxes


def main() -> int:
    report: dict[str, object] = {"ok": True, "skins": {}}
    for skin_dir in sorted((ROOT / "skins").glob("rita_*_rose")):
        manifest = json.loads((skin_dir / "skin.json").read_text(encoding="utf-8"))
        skin_report: dict[str, object] = {}
        for action in ACTIONS:
            state = manifest["states"][action]
            path = skin_dir / (state.get("source") or state.get("file"))
            image = Image.open(path).convert("RGBA")
            grid = tuple(state.get("grid", [1, 1]))
            frames = state.get("frames", 1)
            count = len(frames) if isinstance(frames, list) else int(frames)
            durations = state.get("frame_durations_ms", [])
            bottoms: list[int] = []
            empty_frames: list[int] = []
            edge_frames: list[int] = []
            residue = 0
            for index, box in enumerate(_frame_boxes(image, grid, frames)):
                frame = image.crop(box)
                alpha = frame.getchannel("A")
                bounds = alpha.point(lambda value: 255 if value > 15 else 0).getbbox()
                if bounds is None:
                    empty_frames.append(index)
                    continue
                bottoms.append(bounds[3] - 1)
                if bounds[0] <= 0 or bounds[1] <= 0 or bounds[2] >= frame.width or bounds[3] >= frame.height:
                    edge_frames.append(index)
                residue += sum(
                    1
                    for red, green, blue, alpha_value in frame.get_flattened_data()
                    if alpha_value == 0 and (red or green or blue)
                )
            bottom_drift = max(bottoms) - min(bottoms) if bottoms else 0
            errors: list[str] = []
            if empty_frames:
                errors.append(f"empty frames: {empty_frames}")
            if bottom_drift > 1:
                errors.append(f"anchor drift: {bottom_drift}px")
            if residue:
                errors.append(f"transparent RGB residue: {residue}px")
            if durations and len(durations) != count:
                errors.append("duration count mismatch")
            if edge_frames:
                errors.append(f"unsafe edge contact: {edge_frames}")
            skin_report[action] = {
                "path": str(path.relative_to(ROOT)),
                "frames": count,
                "grid": list(grid),
                "total_duration_ms": sum(durations) if durations else None,
                "bottom_drift_px": bottom_drift,
                "transparent_rgb_residue_px": residue,
                "errors": errors,
            }
            if errors:
                report["ok"] = False
        report["skins"][skin_dir.name] = skin_report  # type: ignore[index]
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUTPUT)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
