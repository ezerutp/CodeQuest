from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from codequest.ui.icons import icon_label


class Chip(QFrame):
    """Etiqueta tipo píldora con icono opcional. `tone`: None, "accent" o "muted"."""

    def __init__(self, text: str, tone: str | None = None, icon: str | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Chip")
        if tone:
            self.setProperty("tone", tone)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(9, 3, 10, 3)
        layout.setSpacing(5)
        if icon:
            layout.addWidget(icon_label(icon, size=13))
        label = QLabel(text)
        label.setObjectName("ChipText")
        layout.addWidget(label)
