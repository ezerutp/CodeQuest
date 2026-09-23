from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from codequest.ui.icons import icon_label
from codequest.ui.theme import current_palette
from codequest.ui.widgets.card import ClickableCard
from codequest.ui.widgets.chip import Chip


class ModeCard(ClickableCard):
    """Tarjeta de un modo de juego. Los modos no disponibles se muestran deshabilitados."""

    def __init__(
        self,
        icon: str,
        title: str,
        description: str,
        badge: str | None = None,
        badge_icon: str | None = None,
        available: bool = True,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.body.setSpacing(6)

        top = QHBoxLayout()
        palette = current_palette()
        top.addWidget(icon_label(icon, size=28, color=palette.accent if available else palette.text_subtle))
        top.addStretch(1)
        if badge:
            top.addWidget(Chip(badge, tone="muted", icon=badge_icon))
        self.body.addLayout(top)

        title_label = QLabel(title)
        title_label.setObjectName("ModeTitle")
        desc_label = QLabel(description)
        desc_label.setObjectName("ModeDescription")
        desc_label.setWordWrap(True)
        self.body.addWidget(title_label)
        self.body.addWidget(desc_label)
        self.body.addStretch(1)

        self.setEnabled(available)
        if not available:
            self.setToolTip("Disponible en una próxima versión")
