from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QResizeEvent, QShowEvent
from PySide6.QtWidgets import QScrollArea, QVBoxLayout, QWidget

from codequest.app.context import AppContext
from codequest.core.analysis.model import ProjectModel


class _ColumnLayout(QVBoxLayout):
    """Columna que inserta siempre antes de un stretch final.

    Así el contenido más corto que la ventana queda arriba en vez de estirarse (el
    scroll area da al widget al menos la altura visible). Es un único layout, sin
    anidar: Qt no invalida bien la caché de altura de los sub-layouts.
    """

    def __init__(self, parent: QWidget, fill_height: bool) -> None:
        super().__init__(parent)
        self._has_tail = not fill_height
        if self._has_tail:
            super().addStretch(1)

    def _insert_index(self) -> int:
        return self.count() - 1 if self._has_tail else self.count()

    def addWidget(self, widget: QWidget, stretch: int = 0,  # noqa: N802 (API de Qt)
                  alignment: Qt.AlignmentFlag = Qt.AlignmentFlag(0)) -> None:
        self.insertWidget(self._insert_index(), widget, stretch, alignment)

    def addLayout(self, layout, stretch: int = 0) -> None:  # noqa: N802
        self.insertLayout(self._insert_index(), layout, stretch)

    def addSpacing(self, size: int) -> None:  # noqa: N802
        self.insertSpacing(self._insert_index(), size)


class Page(QScrollArea):
    """Página desplazable con el contenido centrado y ancho máximo legible."""

    MAX_CONTENT_WIDTH = 1120
    MIN_SIDE_MARGIN = 40
    # True para páginas tipo herramienta (explorador, editor) cuyo contenido ocupa todo el
    # alto disponible y tiene su propio scroll interno.
    FILL_HEIGHT = False

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
        self.layout_: QVBoxLayout = _ColumnLayout(self._viewport_widget, self.FILL_HEIGHT)
        self.layout_.setSpacing(16)
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

    def content_changed(self) -> None:
        """Llamar tras añadir o quitar widgets dinámicamente."""
        QTimer.singleShot(0, self.sync_content_size)

    def set_context(self, context: AppContext) -> None:
        """Las páginas que muestran datos del proyecto lo sobrescriben."""

    def set_model(self, model: ProjectModel | None) -> None:
        """Recibe el resultado del análisis (None mientras se analiza otro proyecto)."""
