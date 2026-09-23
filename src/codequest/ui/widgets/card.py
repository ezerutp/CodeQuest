from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget


class Card(QFrame):
    """Contenedor con fondo, borde y radio. `variant`: None, "hero" o "warning"."""

    def __init__(self, parent: QWidget | None = None, variant: str | None = None, padding: int = 20) -> None:
        super().__init__(parent)
        self.setObjectName("Card")
        if variant:
            self.setProperty("variant", variant)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(padding, padding, padding, padding)
        self.body.setSpacing(10)


class ClickableCard(Card):
    """Card que se comporta como botón: hover en QSS y señal `clicked`."""

    clicked = Signal()

    def __init__(self, parent: QWidget | None = None, padding: int = 18) -> None:
        super().__init__(parent, padding=padding)
        self.setProperty("interactive", True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def setEnabled(self, enabled: bool) -> None:  # noqa: N802 (API de Qt)
        super().setEnabled(enabled)
        self.setCursor(Qt.CursorShape.PointingHandCursor if enabled else Qt.CursorShape.ArrowCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() is Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.clicked.emit()
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.clicked.emit()
            return
        super().keyPressEvent(event)
