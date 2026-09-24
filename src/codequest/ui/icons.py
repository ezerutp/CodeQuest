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
    "search": "mdi6.magnify",
    "package": "mdi6.folder-outline",
    "file": "mdi6.file-code-outline",
    "field": "mdi6.variable",
    "method": "mdi6.function-variant",
    "practice": "mdi6.school-outline",
    "dont-know": "mdi6.help-circle-outline",
    "correct": "mdi6.check-circle",
    "incorrect": "mdi6.close-circle",
    "explain": "mdi6.lightbulb-on-outline",
    "analogy": "mdi6.lightbulb-outline",
    "youtube": "mdi6.youtube",
    "next": "mdi6.arrow-right",
    "trophy": "mdi6.trophy-outline",
    "replay": "mdi6.replay",
    "gap": "mdi6.help-rhombus-outline",
    "book": "mdi6.book-open-page-variant-outline",
    "folder-open": "mdi6.folder-open-outline",
    "chevron-down": "mdi6.chevron-down",
    "chevron-up": "mdi6.chevron-up",
    "delete": "mdi6.trash-can-outline",
    "privacy": "mdi6.shield-lock-outline",
    "database": "mdi6.database-outline",
    "logs": "mdi6.text-box-outline",
    "info": "mdi6.information-outline",
    "role.entity": "mdi6.database-outline",
    "role.controller": "mdi6.api",
    "role.service": "mdi6.cog-transfer-outline",
    "role.repository": "mdi6.archive-outline",
    "role.dto": "mdi6.package-variant-closed",
    "role.configuration": "mdi6.tune-variant",
    "role.enum": "mdi6.format-list-bulleted-type",
    "role.exception": "mdi6.alert-circle-outline",
    "role.utility": "mdi6.tools",
    "role.mapper": "mdi6.swap-horizontal",
    "role.component": "mdi6.puzzle-outline",
    "role.annotation": "mdi6.at",
    "role.other": "mdi6.code-braces",
}


def icon(name: str, color: str | None = None, color_on: str | None = None) -> QIcon:
    """Icono con color. Sin `color` usa el tono atenuado y se ilumina al activarse/marcarse
    (navegación); con `color` mantiene ese color en todos los estados salvo deshabilitado."""
    palette = current_palette()
    highlight = color_on or color or palette.text
    return qta.icon(
        ICONS[name],
        color=color or palette.text_muted,
        color_on=highlight,
        color_active=highlight,
        color_disabled=palette.text_subtle,
    )


def icon_label(name: str, size: int = 18, color: str | None = None, parent: QWidget | None = None) -> QLabel:
    label = QLabel(parent)
    label.setPixmap(icon(name, color).pixmap(size, size))
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    return label
