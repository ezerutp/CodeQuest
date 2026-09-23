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
from codequest.core.analysis.package_tree import display_name
from codequest.core.games.catalog import MULTIPLE_CHOICE, mode_info
from codequest.core.project.models import ProjectInfo
from codequest.services.knowledge_service import GenerationResult, KnowledgeService
from codequest.services.learning_service import LearningService
from codequest.services.project_service import ProjectService
from codequest.ui.navigation import PageId, Sidebar
from codequest.ui.pages.base import Page
from codequest.ui.pages.concepts.page import ConceptsPage
from codequest.ui.pages.dashboard import DashboardPage
from codequest.ui.pages.explorer.page import ProjectExplorerPage
from codequest.ui.pages.learn.page import LearnPage
from codequest.ui.pages.placeholder import PlaceholderPage
from codequest.ui.workers import AnalysisRunner, BackgroundTask

log = logging.getLogger(__name__)

# Secciones aún no implementadas. El id de página coincide con el nombre de su icono.
PLACEHOLDER_PAGES: tuple[tuple[PageId, str, str], ...] = (
    (PageId.PROGRESS, "Progreso", "Tu dominio por tema, XP y rachas."),
    (PageId.SETTINGS, "Configuración", "IA, apariencia y datos."),
)


class MainWindow(QMainWindow):
    def __init__(self, context: AppContext, service: ProjectService,
                 learning: LearningService | None = None, knowledge_dir: Path | None = None,
                 knowledge: KnowledgeService | None = None) -> None:
        super().__init__()
        self._context = context
        self._service = service
        self._learning = learning or LearningService()
        self._knowledge = knowledge or KnowledgeService(self._learning.kb, store=None, provider=None)
        self._model: ProjectModel | None = None
        self._last_scope: str | None = None  # clase de la última ronda, para "Otra ronda"

        self.resize(1320, 860)
        self.setMinimumSize(1024, 680)

        self._sidebar = Sidebar()
        self._stack = QStackedWidget()
        self._pages: dict[PageId, Page] = {}

        self._dashboard = DashboardPage()
        self._dashboard.change_project_requested.connect(self._choose_project)
        self._dashboard.continue_requested.connect(lambda: self._start_round(None))
        self._dashboard.mode_selected.connect(self._start_mode)
        self._dashboard.concepts_requested.connect(lambda: self.show_page(PageId.CONCEPTS))
        self._add_page(PageId.HOME, self._dashboard)

        self._learn = LearnPage(load_snippet=lambda ref: service.read_snippet(self._model, ref))
        self._learn.mode_selected.connect(self._start_mode)
        self._learn.play_again.connect(lambda: self._start_round(self._last_scope))
        self._learn.go_home.connect(lambda: self.show_page(PageId.HOME))
        self._learn.open_class.connect(self._open_class)
        self._add_page(PageId.LEARN, self._learn)

        self._explorer = ProjectExplorerPage(load_source=lambda model, cls: service.read_source(model, cls, True))
        self._explorer.practice_requested.connect(lambda cls: self._start_round(cls.qualified_name))
        self._add_page(PageId.PROJECT, self._explorer)
        self._concepts = ConceptsPage(self._knowledge, knowledge_dir)
        self._concepts.generate_requested.connect(self._generate_concepts)
        self._concepts.delete_requested.connect(self._delete_concept)
        self._add_page(PageId.CONCEPTS, self._concepts)
        self._ai_task = BackgroundTask(self)
        self._ai_task.progress.connect(self._concepts.show_generation_progress)
        self._ai_task.finished.connect(self._on_concepts_generated)
        self._ai_task.failed.connect(self._on_ai_task_failed)
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
        self._refresh_knowledge()

    # --- conocimiento e IA ---------------------------------------------------------

    def _refresh_knowledge(self) -> None:
        if self._model is None:
            return
        report = self._learning.knowledge_report(self._model)
        self._dashboard.set_knowledge(report)
        self._concepts.set_report(report)

    def _generate_concepts(self, gaps) -> None:
        if not self._knowledge.can_generate or self._ai_task.is_running:
            return
        self._concepts.show_generation_started(len(gaps))
        self._ai_task.start(lambda progress, cancel: self._knowledge.generate(gaps, progress, cancel))

    def _on_concepts_generated(self, result: GenerationResult) -> None:
        # Hilo principal: aquí sí se modifica la base de conocimiento.
        self._knowledge.register(result.created)
        report = self._learning.knowledge_report(self._model) if self._model else None
        if report is not None:
            self._dashboard.set_knowledge(report)
            self._concepts.show_generation_result(result, report)

    def _on_ai_task_failed(self, message: str) -> None:
        QMessageBox.warning(self, APP_NAME, f"No se pudo completar la generación con IA:\n{message}")
        if self._model is not None:
            self._concepts.show_generation_result(None, self._learning.knowledge_report(self._model))

    def _delete_concept(self, concept_id: str) -> None:
        if self._knowledge.delete(concept_id):
            self._refresh_knowledge()

    # --- aprendizaje ------------------------------------------------------------

    def _start_mode(self, mode_id: str) -> None:
        mode = mode_info(mode_id)
        if not mode.available:
            self._learn.show_mode_select(f"«{mode.title}» llegará en una próxima versión. "
                                         "Mientras tanto, prueba con Alternativas.")
            self.show_page(PageId.LEARN)
            return
        self._start_round(None, mode_id)

    def _start_round(self, class_name: str | None, mode_id: str = MULTIPLE_CHOICE) -> None:
        """Nueva ronda sobre todo el proyecto o sobre una clase concreta."""
        self.show_page(PageId.LEARN)
        if self._model is None:
            notice = ("Estoy analizando tu proyecto; en unos segundos podrás empezar."
                      if self._context.project.is_supported else
                      "Los ejercicios están disponibles para proyectos Java.")
            self._learn.show_mode_select(notice)
            return
        session = self._learning.start_session(self._model, mode_id, class_name=class_name)
        cls = next((c for c in self._model.classes if c.qualified_name == class_name), None)
        label = display_name(cls) if cls else None
        if not session.questions:
            target = f"la clase {label}" if label else "este proyecto"
            self._learn.show_mode_select(
                f"Todavía no tengo preguntas sobre {target}: sus anotaciones no están en mi base de "
                "conocimiento. Prueba con otra clase o con todo el proyecto."
            )
            return
        self._last_scope = class_name
        self._learn.start(session, label)

    def _open_class(self, qualified_name: str) -> None:
        self.show_page(PageId.PROJECT)
        self._explorer.show_class(qualified_name)

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
        self._ai_task.shutdown()
        super().closeEvent(event)
