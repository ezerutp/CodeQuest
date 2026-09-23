"""Iconos vectoriales (Material Design Icons vía qtawesome).

Se usan nombres semánticos para que cambiar de set de iconos solo afecte a este archivo.
No usamos emojis como iconos: su renderizado a color depende de las fuentes del sistema.
"""

import qtawesome as qta
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QLabel, QWidget

from codequest.ui.theme import current_palette

ICONS: dict[str, str] = {
    "home": "mdi6.home-outline",
    "learn": "mdi6.gamepad-variant-outline",
    "project": "mdi6.folder-open-outline",
    "progress": "mdi6.chart-box-outline",
    "concepts": "mdi6.lightbulb-on-outline",
    "settings": "mdi6.cog-outline",
    "logo": "mdi6.rhombus-split",
    "folder": "mdi6.folder-swap-outline",
    "play": "mdi6.play",
    "ai": "mdi6.creation",
    "local": "mdi6.monitor",
    "warning": "mdi6.alert-outline",
    "construction": "mdi6.hammer-wrench",
    "mode.multiple_choice": "mdi6.target",
    "mode.explain_code": "mdi6.brain",
    "mode.find_error": "mdi6.bug-outline",
    "mode.fix_code": "mdi6.wrench-outline",
    "mode.comparison": "mdi6.sword-cross",
    "mode.random": "mdi6.dice-5-outline",
}


def icon(name: str, color: str | None = None, color_on: str | None = None) -> QIcon:
    palette = current_palette()
    return qta.icon(
        ICONS[name],
        color=color or palette.text_muted,
        color_on=color_on or palette.text,
        color_active=color_on or palette.text,
        color_disabled=palette.text_subtle,
    )


def icon_label(name: str, size: int = 18, color: str | None = None, parent: QWidget | None = None) -> QLabel:
    label = QLabel(parent)
    label.setPixmap(icon(name, color).pixmap(size, size))
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label
