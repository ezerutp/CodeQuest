from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from codequest.app.context import AppContext


class Page(QScrollArea):
    """Página desplazable con el contenido centrado y ancho máximo legible."""

    MAX_CONTENT_WIDTH = 1120
    MIN_SIDE_MARGIN = 40

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Page")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        # El centrado se hace con márgenes calculados en resizeEvent: un QHBoxLayout
        # con stretches calcula mal la altura de las etiquetas con salto de línea.
        # layout_ es el layout raíz a propósito: Qt no invalida la caché de altura
        # de los sub-layouts anidados y el contenido salía recortado.
        self._viewport_widget = QWidget()
        self.layout_ = QVBoxLayout(self._viewport_widget)
        self.layout_.setSpacing(16)
        self.layout_.setAlignment(Qt.AlignmentFlag.AlignTop)
        self._update_margins()
        self.setWidget(self._viewport_widget)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 (API de Qt)
        super().resizeEvent(event)
        self._update_margins()

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        QTimer.singleShot(0, self.sync_content_size)

    def sync_content_size(self) -> None:
        """Reajusta el alto del contenido al estado actual de sus layouts.

        Qt aplica las fuentes del QSS al mostrar los widgets; el scroll area no se
        entera y mantiene el alto medido con la fuente por defecto (texto recortado).
        Llamar tras mostrar la página o tras cambiar su contenido.
        """
        self.setWidgetResizable(True)

    def _update_margins(self) -> None:
        width = self.viewport().width()
        side = max(self.MIN_SIDE_MARGIN, (width - self.MAX_CONTENT_WIDTH) // 2)
        self.layout_.setContentsMargins(side, 36, side, 40)

    def set_context(self, context: AppContext) -> None:
        """Las páginas que muestran datos del proyecto lo sobrescriben."""
