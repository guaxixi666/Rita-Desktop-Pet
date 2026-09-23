from __future__ import annotations

from PySide6.QtGui import QColor, QFont

from codex_usage_pet.skins.models import SkinTheme

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
DEFAULT_THEME = SkinTheme()

FONT_FAMILY = "Segoe UI Variable, Segoe UI, Microsoft YaHei UI"


def font(point_size: int, weight: QFont.Weight = QFont.Weight.Normal) -> QFont:
    value = QFont("Segoe UI Variable", point_size, weight)
    value.setFamilies(["Segoe UI Variable", "Segoe UI", "Microsoft YaHei UI"])
    return value


def rgba(hex_color: str, alpha: int) -> str:
    color = QColor(hex_color)
    return f"rgba({color.red()},{color.green()},{color.blue()},{alpha})"


def menu_style(palette: SkinTheme) -> str:
    return f"""
QMenu {{
    background: {palette.panel};
    color: {palette.text_primary};
    border: 1px solid {palette.border};
    border-radius: 9px;
    padding: 6px;
    font-family: '{FONT_FAMILY}';
    font-size: 12px;
}}
QMenu::item {{ padding: 7px 26px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {rgba(palette.primary, 72)}; color: {palette.text_primary}; }}
QMenu::item:checked {{ color: {palette.low}; }}
QMenu::separator {{ height: 1px; background: {rgba(palette.primary, 55)}; margin: 5px 8px; }}
QMenu::indicator {{ width: 10px; height: 10px; }}
QMenu::indicator:checked {{ background: {palette.primary}; border-radius: 5px; }}
"""


MENU_STYLE = menu_style(DEFAULT_THEME)
