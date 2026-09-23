from PySide6.QtWidgets import QLabel, QWidget

from codequest.ui.widgets.card import Card


class StatTile(Card):
    """Métrica grande con su etiqueta, p. ej. "10 / Entities"."""

    def __init__(self, label: str, value: str = "—", parent: QWidget | None = None) -> None:
        super().__init__(parent, padding=16)
        self.body.setSpacing(2)
        self._value = QLabel(value)
        self._value.setObjectName("StatValue")
        self._label = QLabel(label)
        self._label.setObjectName("StatLabel")
        self.body.addWidget(self._value)
        self.body.addWidget(self._label)

    def set_value(self, value: int | str) -> None:
        self._value.setText(str(value))
