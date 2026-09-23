from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from codequest.ui.widgets.style_utils import set_style_property


class StatusIndicator(QWidget):
    """Punto de color + texto. Estados: "on", "off", "warn"."""

    def __init__(self, text: str = "", state: str = "off", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self._dot = QLabel()
        self._dot.setObjectName("StatusDot")
        self._text = QLabel()
        self._text.setObjectName("StatusText")
        layout.addWidget(self._dot)
        layout.addWidget(self._text, 1)
        self.set_status(text, state)

    def set_status(self, text: str, state: str, tooltip: str = "") -> None:
        self._dot.setText("●" if state == "on" else "○")
        set_style_property(self._dot, "state", state)
        self._text.setText(text)
        self.setToolTip(tooltip)
