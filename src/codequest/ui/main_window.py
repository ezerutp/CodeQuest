"""Ventana principal: barra lateral + páginas apiladas."""

import logging
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMainWindow, QMessageBox, QStackedWidget, QWidget

from codequest.app.constants import APP_NAME
from codequest.app.context import AppContext
from codequest.core.project.models import ProjectInfo
from codequest.ui.navigation import PageId, Sidebar
from codequest.ui.pages.base import Page
from codequest.ui.pages.dashboard import DashboardPage
from codequest.ui.pages.placeholder import PlaceholderPage

log = logging.getLogger(__name__)

ProjectDetectFn = Callable[[Path], ProjectInfo]

# Secciones aún no implementadas. El id de página coincide con el nombre de su icono.
PLACEHOLDER_PAGES: tuple[tuple[PageId, str, str], ...] = (
    (PageId.LEARN, "Aprender", "Elige un modo de juego y practica con tu código."),
    (PageId.PROJECT, "Mi proyecto", "Explora las clases de tu proyecto."),
    (PageId.PROGRESS, "Progreso", "Tu dominio por tema, XP y rachas."),
    (PageId.CONCEPTS, "Conceptos", "Las anotaciones y patrones de tu proyecto."),
    (PageId.SETTINGS, "Configuración", "IA, apariencia y datos."),
)


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext, detect_project: ProjectDetectFn) -> None:
        super().__init__()
        self._context = context
        self._detect_project = detect_project

        self.resize(1320, 860)
        self.setMinimumSize(1024, 680)

        self._sidebar = Sidebar()
        self._stack = QStackedWidget()
        self._pages: dict[PageId, Page] = {}

        self._dashboard = DashboardPage()
        self._dashboard.change_project_requested.connect(self._choose_project)
        self._dashboard.continue_requested.connect(lambda: self.show_page(PageId.LEARN))
        self._dashboard.mode_selected.connect(lambda _key: self.show_page(PageId.LEARN))
        self._add_page(PageId.HOME, self._dashboard)
        for page_id, title, description in PLACEHOLDER_PAGES:
            self._add_page(page_id, PlaceholderPage(page_id.value, title, description))

        self._sidebar.page_selected.connect(self.show_page)

        central = QWidget()
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self._sidebar)
        layout.addWidget(self._stack, 1)
        self.setCentralWidget(central)

        self._apply_context()
        self.show_page(PageId.HOME)

    def _add_page(self, page_id: PageId, page: Page) -> None:
        self._pages[page_id] = page
        self._stack.addWidget(page)

    def show_page(self, page_id: PageId) -> None:
        self._stack.setCurrentWidget(self._pages[page_id])
        self._sidebar.select(page_id)

    def _apply_context(self) -> None:
        self.setWindowTitle(f"{self._context.project.name} — {APP_NAME}")
        self._sidebar.set_context(self._context)
        for page in self._pages.values():
            page.set_context(self._context)
            QTimer.singleShot(0, page.sync_content_size)

    def _choose_project(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Elige el proyecto que quieres estudiar", str(self._context.project.root)
        )
        if not directory:
            return
        try:
            project = self._detect_project(Path(directory))
        except OSError as exc:
            log.warning("No se pudo abrir el proyecto %s: %s", directory, exc)
            QMessageBox.warning(self, APP_NAME, f"No se pudo abrir el proyecto:\n{exc}")
            return
        self._context = replace(self._context, project=project)
        self._apply_context()
        self.show_page(PageId.HOME)
