"""Ventana principal: barra lateral + páginas apiladas."""

import logging
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QStackedWidget,
    QWidget,
)

from codequest.app.constants import APP_NAME
from codequest.app.context import AppContext
from codequest.core.analysis.model import ProjectModel
from codequest.core.project.models import ProjectInfo
from codequest.services.project_service import ProjectService
from codequest.ui.navigation import PageId, Sidebar
from codequest.ui.pages.base import Page
from codequest.ui.pages.dashboard import DashboardPage
from codequest.ui.pages.explorer.page import ProjectExplorerPage
from codequest.ui.pages.placeholder import PlaceholderPage
from codequest.ui.workers import AnalysisRunner

log = logging.getLogger(__name__)

# Secciones aún no implementadas. El id de página coincide con el nombre de su icono.
PLACEHOLDER_PAGES: tuple[tuple[PageId, str, str], ...] = (
    (PageId.LEARN, "Aprender", "Elige un modo de juego y practica con tu código."),
    (PageId.PROGRESS, "Progreso", "Tu dominio por tema, XP y rachas."),
    (PageId.CONCEPTS, "Conceptos", "Las anotaciones y patrones de tu proyecto."),
    (PageId.SETTINGS, "Configuración", "IA, apariencia y datos."),
)


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext, service: ProjectService) -> None:
        super().__init__()
        self._context = context
        self._service = service
        self._model: ProjectModel | None = None

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
        self._explorer = ProjectExplorerPage(load_source=lambda model, cls: service.read_source(model, cls, True))
        # "Practicar esta clase" llevará al modo de juego filtrado por clase (GCQ-03).
        self._explorer.practice_requested.connect(lambda _cls: self.show_page(PageId.LEARN))
        self._add_page(PageId.PROJECT, self._explorer)
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

        self._runner = AnalysisRunner(service, self)
        self._runner.started.connect(self._dashboard.show_analysis_started)
        self._runner.progress.connect(self._dashboard.show_analysis_progress)
        self._runner.failed.connect(self._dashboard.show_analysis_failed)
        self._runner.finished.connect(self._on_analysis_finished)

        self._set_project(context.project)
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

    def _set_project(self, project: ProjectInfo) -> None:
        """Cambia el proyecto activo y lanza su análisis en segundo plano."""
        self._context = replace(self._context, project=project)
        self._model = None
        self._apply_context()
        for page in self._pages.values():
            page.set_model(None)
        if project.is_supported:
            self._runner.start(project)
        else:
            self._runner.cancel()
            self._dashboard.show_analysis_unavailable()

    def _on_analysis_finished(self, model: ProjectModel) -> None:
        self._model = model
        if model.info != self._context.project:  # p. ej. Spring detectado por @SpringBootApplication
            self._context = replace(self._context, project=model.info)
            self._apply_context()
        for page in self._pages.values():
            page.set_model(model)

    def _choose_project(self) -> None:
        directory = QFileDialog.getExistingDirectory(
            self, "Elige el proyecto que quieres estudiar", str(self._context.project.root)
        )
        if not directory:
            return
        try:
            project = self._service.detect(Path(directory))
        except OSError as exc:
            log.warning("No se pudo abrir el proyecto %s: %s", directory, exc)
            QMessageBox.warning(self, APP_NAME, f"No se pudo abrir el proyecto:\n{exc}")
            return
        self._set_project(project)
        self.show_page(PageId.HOME)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (API de Qt)
        self._runner.shutdown()
        super().closeEvent(event)
