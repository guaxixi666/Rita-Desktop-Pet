"""Deterministic hatch-pet-style anchor QA for Rita Desktop Pet skins."""

from __future__ import annotations

import json
import math
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPen
from PySide6.QtWidgets import QApplication

from codex_usage_pet.pet.animator import PetActivity
from codex_usage_pet.services.settings import AppSettings, SettingsStore
from codex_usage_pet.services.startup import StartupManager
from codex_usage_pet.skins.loader import SkinRepository
from codex_usage_pet.ui.pet_window import PetWindow


OUTPUT = ROOT / "artifacts" / "animations" / "debug"
CELL = 286
GAP = 10


def _mapped_points(window: PetWindow) -> tuple[QPointF, QPointF, QPointF, QRectF]:
    pet = window.pet
    asset = pet.skin.asset_for(pet.activity)
    cell = asset.cell_at(pet._frame_index)
    key = (asset.path, cell, asset.grid)
    bounds = pet._frame_bounds[key]
    scale_x = pet.skin.preferred_width / pet._current_frame_pixmap.width()
    scale_y = pet.skin.preferred_height / pet._current_frame_pixmap.height()
    visible = QRectF(
        pet._target.left() + bounds.left() * scale_x,
        pet._target.top() + bounds.top() * scale_y,
        bounds.width() * scale_x,
        bounds.height() * scale_y,
    )
    raw_foot = pet._frame_anchors[key]
    foot = QPointF(
        pet._target.left() + raw_foot.x() * scale_x,
        pet._target.top() + raw_foot.y() * scale_y,
    )
    face = QPointF(visible.center().x(), visible.top() + visible.height() * 0.32)
    head = QPointF(visible.center().x(), visible.top())
    return foot, face, head, visible


def _render_sequence(
    window: PetWindow,
    name: str,
    sequence: list[tuple[PetActivity | str, int]],
) -> None:
    columns = min(4, len(sequence))
    rows = math.ceil(len(sequence) / columns)
    image = QImage(
        columns * CELL + (columns + 1) * GAP,
        rows * CELL + (rows + 1) * GAP,
        QImage.Format.Format_ARGB32_Premultiplied,
    )
    image.fill(QColor("#17171D"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    for index, (activity, frame_index) in enumerate(sequence):
        window.pet.activity = activity
        window.pet._frame_index = frame_index
        window.pet._prepare_visual()
        window.pet.update()
        QApplication.processEvents()
        grabbed = window.pet.grab()
        foot, _face, _head, visible = _mapped_points(window)
        column, row = index % columns, index // columns
        cell = QRect(GAP + column * CELL, GAP + row * CELL, CELL, CELL)
        origin = QPointF(cell.left() + (CELL - window.pet.width()) / 2, cell.top() + 18)
        painter.fillRect(cell, QColor("#24222B"))
        painter.setPen(QPen(QColor("#87364E"), 1))
        painter.drawRect(QRectF(origin, window.pet.size()))
        canvas = QRectF(
            origin.x() + window.pet.anchor_offset.x() - window.pet.CANVAS_WIDTH / 2,
            origin.y() + window.pet.anchor_offset.y() - window.pet.CANVAS_HEIGHT,
            window.pet.CANVAS_WIDTH,
            window.pet.CANVAS_HEIGHT,
        )
        pen = QPen(QColor("#958594"), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawRect(canvas)
        painter.drawPixmap(origin, grabbed)
        painter.setPen(QPen(QColor("#DA7892"), 1))
        painter.drawRect(visible.translated(origin))
        anchor = foot + origin
        painter.drawLine(QPointF(anchor.x() - 7, anchor.y()), QPointF(anchor.x() + 7, anchor.y()))
        painter.drawLine(QPointF(anchor.x(), anchor.y() - 7), QPointF(anchor.x(), anchor.y() + 7))
        painter.setPen(QColor("#F3ECEE"))
        label = activity.value if isinstance(activity, PetActivity) else activity
        painter.drawText(cell.adjusted(8, 5, -8, -5), f"{label} · {frame_index + 1}")
    painter.end()
    output = OUTPUT / f"{name}.png"
    if not image.save(str(output), "PNG"):
        raise OSError(f"无法保存 {output}")


def main() -> int:
    app = QApplication.instance() or QApplication([])
    repository = SkinRepository([ROOT / "skins"])
    packs = repository.scan()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    report: dict[str, object] = {"logical_canvas": [232, 244], "skins": {}}
    for skin_id, skin in sorted(packs.items()):
        window = PetWindow(
            AppSettings(show_usage=False),
            SettingsStore(Path(tempfile.gettempdir()) / f"codex-pet-anchor-{skin_id}.json"),
            StartupManager(registry=None),
            skin_manager=None,
        )
        if window.current_skin.id != skin_id:
            window.current_skin = skin
            window.pet.apply_skin(skin)
            window._on_pet_bounds_changed()
        window._move_to_anchor(QPoint(600, 600), clamp=False)
        initial = [window.x(), window.y(), window.width(), window.height()]
        skin_report: dict[str, object] = {
            "pet_window_geometry": initial,
            "union_bounds": [
                round(window.pet.skin_union_bounds.x(), 3),
                round(window.pet.skin_union_bounds.y(), 3),
                round(window.pet.skin_union_bounds.width(), 3),
                round(window.pet.skin_union_bounds.height(), 3),
            ],
            "actions": {},
        }
        for activity in skin.states:
            asset = skin.asset_for(activity)
            points: list[tuple[QPointF, QPointF, QPointF]] = []
            for frame_index in range(asset.frame_count):
                window.pet.activity = activity
                window.pet._frame_index = frame_index
                window.pet._prepare_visual()
                foot, face, head, _visible = _mapped_points(window)
                points.append((foot, face, head))
                assert [window.x(), window.y(), window.width(), window.height()] == initial
            first = points[0]
            drift = lambda slot: max(  # noqa: E731
                math.hypot(point[slot].x() - first[slot].x(), point[slot].y() - first[slot].y())
                for point in points
            )
            key = activity.value if isinstance(activity, PetActivity) else str(activity)
            skin_report["actions"][key] = {
                "frames": asset.frame_count,
                "foot_drift_px": round(drift(0), 3),
                "face_drift_px": round(drift(1), 3),
                "head_top_drift_px": round(drift(2), 3),
            }
        skin_report["final_pet_window_geometry"] = [window.x(), window.y(), window.width(), window.height()]
        report["skins"][skin_id] = skin_report
        if skin_id == "rita_umbral_rose":
            idle: list[tuple[PetActivity | str, int]] = [(PetActivity.IDLE, 0)]
            for activity, filename in (
                ("smile", "idle-hover-idle"),
                ("surprised", "idle-click-idle"),
                ("wave", "idle-wave-idle"),
            ):
                asset = skin.asset_for(activity)
                _render_sequence(window, filename, idle + [(activity, i) for i in range(asset.frame_count)] + idle)
            for activity, filename in (("sit", "idle-sit"), ("sleepy", "idle-sleepy")):
                asset = skin.asset_for(activity)
                _render_sequence(
                    window,
                    filename,
                    idle + [(activity, i) for i in range(asset.frame_count)] + idle,
                )
        window.deleteLater()
    (OUTPUT / "anchor-drift-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
