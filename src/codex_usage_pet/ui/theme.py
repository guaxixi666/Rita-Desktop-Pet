from __future__ import annotations

from PySide6.QtGui import QColor, QFont

BACKGROUND = "#17171D"
SURFACE = "#24222B"
CREAM = "#F4F0EE"
HAIR_TAUPE = "#B9AAA6"
ROSE = "#C05A78"
ROSE_HIGHLIGHT = "#DA7892"
ROSE_DEEP = "#87364E"
ROSE_PALE = "#E8C3CD"
LAVENDER_GRAY = "#958594"
TEXT = "#F3ECEE"
TEXT_MUTED = "#BDAFB5"
TRACK = "#35313A"

FONT_FAMILY = "Segoe UI Variable, Segoe UI, Microsoft YaHei UI"


def font(point_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    value = QFont("Segoe UI Variable", point_size, weight)
    value.setFamilies(["Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI"])
    return value


def rgba(hex_color: str, alpha: int) -> str:
    color = QColor(hex_color)
    return f"rgba({color.red()},{color.green()},{color.blue()},{alpha})"


MENU_STYLE = f"""
QMenu {{
    background: {SURFACE};
    color: {TEXT};
    border: 1px solid {ROSE_DEEP};
    border-radius: 9px;
    padding: 6px;
    font-family: '{FONT_FAMILY}';
    font-size: 12px;
}}
QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {rgba(ROSE, 72)}; color: {CREAM}; }}
QMenu::item:checked {{ color: {ROSE_PALE}; }}
QMenu::separator {{ height: 1px; background: {rgba(ROSE, 55)}; margin: 5px 8px; }}
QMenu::indicator {{ width: 10px; height: 10px; }}
QMenu::indicator:checked {{ background: {ROSE}; border-radius: 5px; }}
"""
