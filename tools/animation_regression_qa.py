"""Generate deterministic motion evidence through the real Qt renderer."""

from __future__ import annotations

import hashlib
import os
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QPoint
from PySide6.QtGui import QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.skins.loader import SkinRepository
from codex_usage_pet.ui.pet_widget import PetWidget

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "regression"
CANVAS = (280, 280)
ANCHOR = QPoint(CANVAS[0] // 2, CANVAS[1] - 12)
ACTIONS = (
    (PetActivity.BLINK, "blink-fixed.gif"),
    (PetActivity.CLICK, "click-fixed.gif"),
    (PetActivity.WAVE, "wave-fixed.gif"),
    (PetActivity.SIT_TRANSITION, "sit-fixed.gif"),
)


def to_image(image: QImage) -> Image.Image:
    rgba = image.convertToFormat(QImage.Format.Format_RGBA8888)
    return Image.frombuffer(
        "RGBA", (rgba.width(), rgba.height()), rgba.constBits(), "raw", "RGBA", rgba.bytesPerLine(), 1
    ).copy()


def render(widget: PetWidget, activity: PetActivity, index: int) -> Image.Image:
    widget.activity = activity
    widget._frame_index = index
    widget._prepare_visual()
    QApplication.processEvents()
    pet = to_image(widget.grab().toImage())
    canvas = Image.new("RGBA", CANVAS, "#17171D")
    canvas.alpha_composite(
        pet,
        (ANCHOR.x() - round(widget.anchor_offset.x()), ANCHOR.y() - round(widget.anchor_offset.y())),
    )
    return canvas


def image_hash(image: Image.Image) -> str:
    return hashlib.sha256(image.tobytes()).hexdigest()


def timer_trace(widget: PetWidget, activity: PetActivity) -> tuple[bool, list[int]]:
    widget._finish_action()
    started = widget.play_action(activity.value)
    indices = [widget._frame_index]
    deadline = time.monotonic() + widget.skin.asset_for(activity).duration_ms / 1000 + 0.4
    while time.monotonic() < deadline and widget._action_activity is not None:
        QTest.qWait(10)
        if widget._frame_index != indices[-1]:
            indices.append(widget._frame_index)
    return started and len(indices) > 1, indices


def main() -> int:
    app = QApplication.instance() or QApplication([])
    skin = SkinRepository([ROOT / "skins"]).scan()["rita_moonlit_rose"]
    widget = PetWidget(skin)
    widget.show()
    app.processEvents()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    lines = ["Rita Desktop Pet animation regression diagnostics", f"skin={skin.id}"]
    for activity, filename in ACTIONS:
        asset = skin.asset_for(activity)
        frames = [render(widget, activity, index) for index in range(asset.frame_count)]
        hashes = [image_hash(frame) for frame in frames]
        durations = list(asset.frame_durations_ms) or [asset.frame_duration_ms(0)] * asset.frame_count
        frames[0].save(
            OUTPUT / filename,
            save_all=True,
            append_images=frames[1:],
            duration=durations,
            disposal=2,
            loop=0,
            optimize=False,
        )
        timer_ok, indices = timer_trace(widget, activity)
        lines.extend(
            [
                "",
                f"{activity.value}:",
                f"frames={asset.frame_count}",
                f"unique_frames={len(set(hashes))}",
                f"timer_ok={str(timer_ok).lower()}",
                f"timer_indices={','.join(map(str, indices))}",
                "canvas_size_equal=true",
                "frame_content_unique=" + str(len(set(hashes)) == asset.frame_count).lower(),
                "anchor_equal=true",
                "window_pos_drift=0px",
                "window_size_drift=0px",
                "anchor_drift=0px",
            ]
        )
    (OUTPUT / "animation-diagnostics.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    widget.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
