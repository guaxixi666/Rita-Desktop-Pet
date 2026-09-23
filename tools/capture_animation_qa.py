"""Render native Qt animation contact sheets for visual release QA."""

from __future__ import annotations

from math import ceil
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.pet.states import PetState
from codex_usage_pet.skins.loader import SkinRepository
from codex_usage_pet.ui.pet_widget import PetWidget


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "artifacts" / "animations"
CELL = 256
GAP = 8


def render_frames(widget: PetWidget, activity: PetActivity, output: Path) -> None:
    asset = widget.skin.asset_for(activity)
    columns = min(4, asset.frame_count)
    rows = ceil(asset.frame_count / columns)
    image = QImage(
        columns * CELL + (columns + 1) * GAP,
        rows * CELL + (rows + 1) * GAP,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(QColor("#17171D"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor("#87364E"), 1))
    widget.activity = activity
    for index in range(asset.frame_count):
        widget._frame_index = index
        widget._prepare_visual()
        frame = widget.grab()
        column = index % columns
        row = index // columns
        cell = QRect(
            GAP + column * CELL,
            GAP + row * CELL,
            CELL,
            CELL,
        )
        painter.fillRect(cell, QColor("#24222B"))
        painter.drawRoundedRect(cell.adjusted(0, 0, -1, -1), 10, 10)
        anchor = QPoint(cell.center().x(), cell.bottom() - 8)
        top_left = anchor - QPoint(
            round(widget.anchor_offset.x()),
            round(widget.anchor_offset.y()),
        )
        painter.drawPixmap(top_left, frame)
    painter.end()
    if not image.save(str(output), "PNG"):
        raise OSError(f"Cannot save {output}")


def render_state_poses(widget: PetWidget, output: Path) -> None:
    states = [PetState.NORMAL, PetState.LOW, PetState.CRITICAL, PetState.EMPTY]
    image = QImage(4 * CELL + 5 * GAP, CELL + 2 * GAP, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(QColor("#17171D"))
    painter = QPainter(image)
    painter.setPen(QPen(QColor("#87364E"), 1))
    for index, state in enumerate(states):
        widget.set_state(state)
        frame = widget.grab()
        cell = QRect(GAP + index * CELL, GAP, CELL, CELL)
        painter.fillRect(cell, QColor("#24222B"))
        painter.drawRoundedRect(cell.adjusted(0, 0, -1, -1), 10, 10)
        anchor = QPoint(cell.center().x(), cell.bottom() - 8)
        top_left = anchor - QPoint(round(widget.anchor_offset.x()), round(widget.anchor_offset.y()))
        painter.drawPixmap(top_left, frame)
    painter.end()
    if not image.save(str(output), "PNG"):
        raise OSError(f"Cannot save {output}")


def main() -> int:
    app = QApplication.instance() or QApplication([])
    repository = SkinRepository([ROOT / "skins"])
    skin = repository.scan()["rita_umbral_rose"]
    widget = PetWidget(skin)
    widget.show()
    app.processEvents()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for activity in (
        PetActivity.BLINK,
        PetActivity.HOVER,
        PetActivity.CLICK,
        PetActivity.WAVE,
        PetActivity.STRETCH,
        PetActivity.SLEEP_REACT,
    ):
        render_frames(widget, activity, OUTPUT / f"{activity.value}-contact.png")
    render_state_poses(widget, OUTPUT / "state-poses.png")
    widget.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
