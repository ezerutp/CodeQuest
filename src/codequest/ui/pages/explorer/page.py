"""Página "Mi proyecto": explorador de clases al estilo de un IDE."""

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QSplitter, QStackedWidget, QWidget

from codequest.app.context import AppContext
from codequest.core.analysis.java.models import JavaClass
from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.snippets import CodeSnippet
from codequest.ui.formatting import plural
from codequest.ui.icons import icon_label
from codequest.ui.pages.base import Page
from codequest.ui.pages.explorer.class_detail import ClassDetail
from codequest.ui.pages.explorer.class_tree import ClassTree
from codequest.ui.theme import current_palette
from codequest.ui.widgets import Card, heading, muted

SourceLoader = Callable[[ProjectModel, JavaClass], CodeSnippet]


class ProjectExplorerPage(Page):
    MAX_CONTENT_WIDTH = 1800
    FILL_HEIGHT = True

    practice_requested = Signal(object)  # JavaClass

    def __init__(self, load_source: SourceLoader, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._model: ProjectModel | None = None
        self._supported = True

        self.layout_.addWidget(heading("Mi proyecto"))
        self._subtitle = muted("")
        self.layout_.addWidget(self._subtitle)

        self._stack = QStackedWidget()
        self._empty = self._build_empty()
        self._stack.addWidget(self._empty)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)
        tree_card = Card(padding=12)
        tree_card.setMinimumWidth(220)
        self._tree = ClassTree()
        tree_card.body.addWidget(self._tree)
        splitter.addWidget(tree_card)

        self._detail = ClassDetail(lambda cls: load_source(self._model, cls))
        self._detail.practice_requested.connect(self.practice_requested)
        splitter.addWidget(self._detail)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([280, 1000])
        self._stack.addWidget(splitter)

        self.layout_.addWidget(self._stack, 1)
        self._tree.class_selected.connect(self._on_class_selected)

    def _build_empty(self) -> Card:
        card = Card(padding=48)
        card.body.addStretch(1)
        card.body.addWidget(icon_label("project", size=44, color=current_palette().accent), 0,
                            Qt.AlignmentFlag.AlignHCenter)
        self._empty_text = muted("")
        self._empty_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card.body.addWidget(self._empty_text)
        card.body.addStretch(1)
        return card

    def set_context(self, context: AppContext) -> None:
        self._supported = context.project.is_supported
        if self._model is None:
            self._show_empty()

    def set_model(self, model: ProjectModel | None) -> None:
        self._model = model
        self._detail.clear()
        self._tree.set_model(model)
        if model is None or not model.main_classes:
            self._show_empty()
            return
        packages = {c.package for c in model.main_classes}
        self._subtitle.setText(
            f"{model.info.name} · {plural(len(model.main_classes), 'clase', 'clases')} en "
            f"{plural(len(packages), 'paquete', 'paquetes')}"
        )
        self._stack.setCurrentIndex(1)

    def show_class(self, qualified_name: str) -> None:
        self._tree.select_class(qualified_name)

    def _show_empty(self) -> None:
        self._stack.setCurrentIndex(0)
        if not self._supported:
            self._subtitle.setText("")
            self._empty_text.setText("El explorador está disponible para proyectos Java.")
        elif self._model is None:
            self._subtitle.setText("")
            self._empty_text.setText("Analizando tu proyecto…")
        else:
            self._empty_text.setText("No se encontraron clases Java en este proyecto.")

    def _on_class_selected(self, cls: JavaClass) -> None:
        if self._model is not None:
            self._detail.show_class(cls, self._model.role_of(cls))
