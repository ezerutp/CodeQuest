"""Una alternativa de respuesta: letra + texto con salto de línea y estados de corrección."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from codequest.ui.widgets.card import ClickableCard
from codequest.ui.widgets.style_utils import set_style_property

LETTERS = "ABCDEFGH"


class ChoiceButton(ClickableCard):
    """Estados: "idle", "correct", "incorrect" o "dimmed" (las no elegidas tras responder)."""

    def __init__(self, index: int, parent: QWidget | None = None) -> None:
        super().__init__(parent, padding=0)
        self.setObjectName("Choice")
        self.index = index
        row = QHBoxLayout()
        row.setContentsMargins(14, 12, 16, 12)
        row.setSpacing(14)
        self._letter = QLabel(LETTERS[index])
        self._letter.setObjectName("ChoiceLetter")
        self._letter.setFixedSize(28, 28)
        self._letter.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._text = QLabel()
        self._text.setObjectName("ChoiceText")
        self._text.setWordWrap(True)
        self._text.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        row.addWidget(self._letter, 0, Qt.AlignmentFlag.AlignTop)
        row.addWidget(self._text, 1)
        self.body.addLayout(row)
        self.set_state("idle")

    @property
    def letter(self) -> str:
        return LETTERS[self.index]

    def set_text(self, text: str) -> None:
        self._text.setText(text)

    def set_state(self, state: str) -> None:
        set_style_property(self, "state", state)
        for child in (self._letter, self._text):
            child.style().unpolish(child)
            child.style().polish(child)
