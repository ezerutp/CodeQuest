"""Ventana principal: barra lateral + páginas apiladas."""

import logging
import os
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from codequest.app.constants import APP_NAME
from codequest.app.context import AppContext
from codequest.core.ai.anthropic_provider import AVAILABLE_MODELS, DEFAULT_MODEL, MODEL_ENV
from codequest.core.ai.factory import create_provider
from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.package_tree import display_name
from codequest.core.games.base import Evaluation
from codequest.core.games.catalog import MULTIPLE_CHOICE, mode_info
from codequest.core.knowledge.models import ConceptSource
from codequest.core.project.models import ProjectInfo
from codequest.core.settings import Settings, SettingsStore
from codequest.services.explain_service import ExplainService
from codequest.services.knowledge_service import GenerationResult, KnowledgeService
from codequest.services.learning_service import LearningService
from codequest.services.progress_service import ProgressService
from codequest.services.project_service import ProjectService
from codequest.ui.dialogs import confirm, warn
from codequest.ui.navigation import PageId, Sidebar
from codequest.ui.pages.base import Page
from codequest.ui.pages.concepts.page import ConceptsPage
from codequest.ui.pages.dashboard import DashboardPage
from codequest.ui.pages.explorer.page import ProjectExplorerPage
from codequest.ui.pages.learn.page import LearnPage
from codequest.ui.pages.progress.page import ProgressPage
from codequest.ui.pages.settings.page import DataPaths, SettingsPage
from codequest.ui.widgets.code_editor import set_editor_font_size
from codequest.ui.workers import AnalysisRunner, BackgroundTask

log = logging.getLogger(__name__)

class MainWindow(QMainWindow):
    def __init__(self, context: AppContext, service: ProjectService,
                 learning: LearningService | None = None, knowledge_dir: Path | None = None,
                 knowledge: KnowledgeService | None = None, explain: ExplainService | None = None,
                 progress: ProgressService | None = None, settings_store: SettingsStore | None = None,
                 data_paths: DataPaths | None = None) -> None:
        super().__init__()
        self._settings_store = settings_store
        self._settings = settings_store.load() if settings_store else Settings()
        self._context = replace(context, ai_enabled=self._settings.ai_enabled)
        set_editor_font_size(self._settings.editor_font_size)  # antes de crear los editores
        self._service = service
        self._learning = learning or LearningService()
        self._knowledge = knowledge or KnowledgeService(self._learning.kb, store=None, provider=None)
        self._explain = explain or ExplainService(None)
        self._progress = progress or ProgressService(None)
        self._percent_before_round = 0
        self._code_consent = False  # consentimiento para enviar código, por proyecto y sesión
        self._explaining_key: str | None = None
        self._grading_key: str | None = None
        self._last_mode = MULTIPLE_CHOICE
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
        self._learn.play_again.connect(lambda: self._start_round(self._last_scope, self._last_mode))
        self._learn.go_home.connect(lambda: self.show_page(PageId.HOME))
        self._learn.open_class.connect(self._open_class)
        self._learn.explain_requested.connect(self._explain_with_code)
        self._learn.explanation_submitted.connect(self._grade_explanation)
        self._learn.answered.connect(self._progress.record)
        self._learn.round_finished.connect(self._on_round_finished)
        self._learn.set_ai_available(self._explain.can_explain, self._explain.provider_name)
        self._add_page(PageId.LEARN, self._learn)

        self._explorer = ProjectExplorerPage(load_source=lambda model, cls: service.read_source(model, cls, True))
        self._explorer.practice_requested.connect(lambda cls: self._start_round(cls.qualified_name))
        self._add_page(PageId.PROJECT, self._explorer)
        self._progress_page = ProgressPage()
        self._progress_page.start_requested.connect(lambda: self._start_round(None))
        self._progress_page.review_requested.connect(self._start_review)
        self._add_page(PageId.PROGRESS, self._progress_page)
        self._concepts = ConceptsPage(self._knowledge, knowledge_dir)
        self._concepts.generate_requested.connect(self._generate_concepts)
        self._concepts.delete_requested.connect(self._delete_concept)
        self._add_page(PageId.CONCEPTS, self._concepts)
        self._ai_task = BackgroundTask(self)
        self._ai_task.progress.connect(self._concepts.show_generation_progress)
        self._ai_task.finished.connect(self._on_concepts_generated)
        self._ai_task.failed.connect(self._on_ai_task_failed)
        self._explain_task = BackgroundTask(self)
        self._explain_task.finished.connect(self._on_explanation_ready)
        self._explain_task.failed.connect(self._on_explanation_failed)
        self._grade_task = BackgroundTask(self)
        self._grade_task.finished.connect(
            lambda feedback: self._grading_key and self._learn.apply_feedback(self._grading_key, feedback))
        self._grade_task.failed.connect(
            lambda message: self._grading_key and self._learn.show_grading_error(self._grading_key, message))
        self._settings_page = SettingsPage(AVAILABLE_MODELS, data_paths or DataPaths(None, knowledge_dir, None, None))
        self._settings_page.ai_enabled_changed.connect(self._set_ai_enabled)
        self._settings_page.ai_model_changed.connect(self._set_ai_model)
        self._settings_page.reset_progress_requested.connect(self._reset_progress)
        self._settings_page.editor_font_size_changed.connect(self._set_editor_font_size)
        self._add_page(PageId.SETTINGS, self._settings_page)

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
        self._refresh_settings()

    # --- configuración -------------------------------------------------------------

    def _refresh_settings(self) -> None:
        counts = self._learning.kb.source_counts()
        env_model = os.environ.get(MODEL_ENV, "").strip() or None
        self._settings_page.set_state(
            self._context, self._settings,
            effective_model=env_model or self._settings.ai_model or DEFAULT_MODEL, env_model=env_model,
            knowledge_counts=(counts[ConceptSource.USER], counts[ConceptSource.AI]),
            progress_error=None if self._progress.available else (
                self._progress.error or "el guardado del progreso no está disponible"),
        )

    def _save_settings(self, settings: Settings) -> None:
        self._settings = settings
        if self._settings_store is None:
            return
        try:
            self._settings_store.save(settings)
        except OSError as exc:
            log.warning("No se pudieron guardar los ajustes: %s", exc)
            warn(self, "No se pudieron guardar los ajustes.", details=f"Se aplican solo en esta sesión. ({exc})")

    def _configure_ai(self) -> None:
        """Aplica los ajustes de IA en caliente: mismo proveedor para conceptos y explicaciones."""
        provider = create_provider(self._context.ai, self._settings.ai_model) if self._context.ai_active else None
        self._knowledge.set_provider(provider)
        self._explain.set_provider(provider)
        self._learn.set_ai_available(self._explain.can_explain, self._explain.provider_name)

    def _set_ai_enabled(self, enabled: bool) -> None:
        self._save_settings(self._settings.with_changes(ai_enabled=enabled))
        self._context = replace(self._context, ai_enabled=enabled)
        self._configure_ai()
        self._apply_context()
        self._refresh_knowledge()

    def _set_ai_model(self, model: str | None) -> None:
        self._save_settings(self._settings.with_changes(ai_model=model))
        self._configure_ai()
        self._refresh_settings()

    def _set_editor_font_size(self, size: int) -> None:
        self._save_settings(self._settings.with_changes(editor_font_size=size))
        set_editor_font_size(size)

    def _reset_progress(self) -> None:
        name = self._context.project.name
        if not confirm(
            self, "Borrar progreso", f"¿Borrar todo tu progreso en {name}?",
            details="Se eliminan tus respuestas, sesiones y dominio de este proyecto. No se puede deshacer. "
                    "Los demás proyectos no se tocan.",
            confirm_text="Borrar progreso", icon_name="delete",
        ):
            return
        self._progress.reset()
        self._refresh_knowledge()
        self._refresh_settings()

    def _set_project(self, project: ProjectInfo) -> None:
        """Cambia el proyecto activo y lanza su análisis en segundo plano."""
        self._context = replace(self._context, project=project)
        self._model = None
        self._explain.clear()
        self._code_consent = False  # otro proyecto, otro código: se vuelve a preguntar
        self._progress.finish()  # una ronda a medias del proyecto anterior queda cerrada
        if project.is_supported:
            self._progress.open_project(project)
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
        """Recalcula cobertura y progreso (tras el análisis, una ronda o un cambio de conceptos)."""
        if self._model is None:
            return
        report = self._learning.knowledge_report(self._model)
        overview = self._progress.overview(report)
        self._dashboard.set_knowledge(report)
        self._dashboard.set_progress(overview, self._progress.error)
        self._progress_page.set_overview(overview, self._progress.sessions(), self._progress.error)
        self._concepts.set_report(report, overview.history)
        self._refresh_settings()

    def _current_percent(self) -> int:
        if self._model is None:
            return 0
        return self._progress.overview(self._learning.knowledge_report(self._model)).percent

    def _on_round_finished(self, _session) -> None:
        self._progress.finish()
        after = self._current_percent()
        self._learn.show_progress_change(self._percent_before_round, after)
        self._refresh_knowledge()

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
        warn(self, "No se pudo completar la generación con IA.", details=message)
        if self._model is not None:
            self._concepts.show_generation_result(None, self._learning.knowledge_report(self._model))

    def _explain_with_code(self, evaluation: Evaluation) -> None:
        key = evaluation.question.key
        if self._model is None:
            return
        if (cached := self._explain.cached(evaluation)) is not None:
            self._learn.show_ai_answer(key, cached)
            return
        try:
            context = self._explain.build_context(self._model, evaluation)
        except (OSError, ValueError) as exc:  # el archivo cambió o desapareció desde el análisis
            self._learn.show_ai_error(key, f"No se pudo leer el código: {exc}")
            return
        if not self._ensure_code_consent(context, "Explícamelo con mi código",
                                         "Para explicarte este concepto con tu código", "Enviar y explicar"):
            return
        if not self._explain_task.start(lambda _progress, _cancel: self._explain.explain(evaluation, context)):
            self._learn.show_ai_error(key, "Espera a que termine la explicación anterior.")
            return
        self._explaining_key = key
        self._learn.show_ai_loading(key)

    def _ensure_code_consent(self, context, title: str, purpose: str, confirm_text: str) -> bool:
        """Antes de enviar código a la IA, una vez por proyecto y sesión, con la lista exacta."""
        if self._code_consent:
            return True
        items = "\n".join(f"• {line}" for line in context.summary())
        if not confirm(
            self, title, f"{purpose} se enviará a {self._explain.provider_name}:\n\n{items}",
            details="Solo el fragmento del ejercicio va como código; del resto se envían las firmas. "
                    "No volveré a preguntarte durante esta sesión con este proyecto.",
            confirm_text=confirm_text, icon_name="ai",
        ):
            return False
        self._code_consent = True
        return True

    def _grade_explanation(self, question, text: str) -> None:
        """Modo "Explícame este código": la IA evalúa la respuesta en segundo plano."""
        if self._model is None:
            return
        try:
            context = self._explain.context_for(self._model, question)
        except (OSError, ValueError) as exc:
            self._learn.show_grading_error(question.key, f"No se pudo leer el código: {exc}")
            return
        if not self._ensure_code_consent(context, "Explícame este código",
                                         "Para evaluar tu explicación", "Enviar y evaluar"):
            return
        if not self._grade_task.start(lambda _progress, _cancel: self._explain.grade(question, text, context)):
            return
        self._grading_key = question.key
        self._learn.show_grading(question.key)

    def _on_explanation_ready(self, text: str) -> None:
        if self._explaining_key is not None:
            self._learn.show_ai_answer(self._explaining_key, text)

    def _on_explanation_failed(self, message: str) -> None:
        if self._explaining_key is not None:
            self._learn.show_ai_error(self._explaining_key, message)

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
        if mode.uses_ai and not self._explain.can_explain:
            self._learn.show_mode_select(
                f"«{mode.title}» necesita IA para evaluar tus respuestas. Define ANTHROPIC_API_KEY y "
                "actívala en Configuración; mientras tanto, prueba con Alternativas.")
            self.show_page(PageId.LEARN)
            return
        self._start_round(None, mode_id)

    def _start_review(self, concept_ids: frozenset[str]) -> None:
        """Ronda solo con los conceptos que el estudiante falló la última vez."""
        self._start_round(None, concept_ids=concept_ids)

    def _start_round(self, class_name: str | None, mode_id: str = MULTIPLE_CHOICE,
                     concept_ids: frozenset[str] | None = None) -> None:
        """Nueva ronda sobre todo el proyecto o sobre una clase concreta."""
        self.show_page(PageId.LEARN)
        if self._model is None:
            notice = ("Estoy analizando tu proyecto; en unos segundos podrás empezar."
                      if self._context.project.is_supported else
                      "Los ejercicios están disponibles para proyectos Java.")
            self._learn.show_mode_select(notice)
            return
        all_ids = [c.id for c in self._learning.kb.concepts]
        session = self._learning.start_session(
            self._model, mode_id, class_name=class_name,
            priorities=self._progress.priorities(all_ids), avoid_keys=self._progress.recent_keys(),
            concept_ids=concept_ids,
        )
        cls = next((c for c in self._model.classes if c.qualified_name == class_name), None)
        label = display_name(cls) if cls else ("Repaso" if concept_ids is not None else None)
        if not session.questions:
            target = f"la clase {label}" if label else "este proyecto"
            self._learn.show_mode_select(
                f"Todavía no tengo preguntas sobre {target}: sus anotaciones no están en mi base de "
                "conocimiento. Prueba con otra clase o con todo el proyecto."
            )
            return
        self._last_scope = class_name
        self._last_mode = mode_id
        self._percent_before_round = self._current_percent()
        self._progress.start(session)
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
            warn(self, "No se pudo abrir el proyecto.", details=str(exc))
            return
        self._set_project(project)
        self.show_page(PageId.HOME)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (API de Qt)
        self._runner.shutdown()
        self._ai_task.shutdown()
        self._explain_task.shutdown()
        self._grade_task.shutdown()
        super().closeEvent(event)
