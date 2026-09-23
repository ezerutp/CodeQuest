from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from codequest.ui.icons import icon_label


class IconText(QWidget):
    """Icono a la izquierda + texto con salto de línea."""

    def __init__(self, icon: str, text: str = "", color: str | None = None, role: str = "muted",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)
        layout.addWidget(icon_label(icon, size=18, color=color), 0, Qt.AlignmentFlag.AlignTop)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setProperty("role", role)
        layout.addWidget(self.label, 1)

    def set_text(self, text: str) -> None:
        self.label.setText(text)
