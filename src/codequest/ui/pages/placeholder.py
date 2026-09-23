from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from codequest.ui.icons import icon_label
from codequest.ui.pages.base import Page
from codequest.ui.theme import current_palette
from codequest.ui.widgets import Card, heading, muted


class PlaceholderPage(Page):
    """Página temporal para secciones que aún no están implementadas."""

    def __init__(self, icon: str, title: str, description: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.layout_.addWidget(heading(title))
        card = Card(padding=48)
        card.body.setSpacing(12)
        card.body.addWidget(icon_label(icon, size=44, color=current_palette().accent), 0, Qt.AlignmentFlag.AlignHCenter)
        for widget in (muted(description), muted("En construcción: llegará en un próximo incremento.")):
            widget.setAlignment(Qt.AlignmentFlag.AlignCenter)
            card.body.addWidget(widget)
        self.layout_.addWidget(card)
