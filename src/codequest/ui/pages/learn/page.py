"""Página "Aprender": elegir modo → jugar la ronda → ver el resumen."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from codequest.core.ai.explanation_grader import ExplanationFeedback
from codequest.core.analysis.model import ProjectModel
from codequest.core.games.base import GameSession
from codequest.core.games.catalog import EXPLAIN_CODE, FIND_ERROR, FIX_CODE
from codequest.ui.pages.base import Page
from codequest.ui.pages.learn.explain_view import ExplainCodeView
from codequest.ui.pages.learn.find_error_view import FindErrorView
from codequest.ui.pages.learn.fix_code_view import FixCodeView
from codequest.ui.pages.learn.game_view import GameView, SnippetLoader
from codequest.ui.pages.learn.summary_view import SummaryView
from codequest.ui.widgets import Card, IconText, ModeGrid, heading, muted, section_title


class LearnPage(Page):
    mode_selected = Signal(str)
    play_again = Signal()
    go_home = Signal()
    open_class = Signal(str)
    explain_requested = Signal(object)  # Evaluation
    answered = Signal(object)  # Evaluation
    round_finished = Signal(object)  # GameSession
    explanation_submitted = Signal(object, str)  # Question, texto del estudiante

    def __init__(self, load_snippet: SnippetLoader, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._select = QWidget()
        select_layout = QVBoxLayout(self._select)
        select_layout.setContentsMargins(0, 0, 0, 0)
        select_layout.setSpacing(16)
        select_layout.addWidget(heading("Aprender"))
        select_layout.addWidget(muted("Elige cómo quieres practicar. Todas las preguntas salen de tu propio código."))
        self._notice = Card(variant="warning", padding=16)
        self._notice_text = IconText("warning", role="body")
        self._notice.body.addWidget(self._notice_text)
        self._notice.hide()
        select_layout.addWidget(self._notice)
        select_layout.addWidget(section_title("Modos de juego"))
        grid = ModeGrid()
        grid.mode_selected.connect(self.mode_selected)
        select_layout.addWidget(grid)
        self.layout_.addWidget(self._select)

        self._game = GameView(load_snippet)
        self._game.finished.connect(self._show_summary)
        self._game.open_class.connect(self.open_class)
        self._game.explain_requested.connect(self.explain_requested)
        self._game.answered.connect(self.answered)
        self._game.content_changed.connect(self.content_changed)
        self.layout_.addWidget(self._game)

        # Modos que muestran código y dan feedback con FeedbackPanel: misma conexión para todos.
        self._find_error = FindErrorView(load_snippet)
        self._fix_code = FixCodeView(load_snippet)
        self._code_views = (self._game, self._find_error, self._fix_code)
        for view in self._code_views[1:]:
            view.finished.connect(self._show_summary)
            view.open_class.connect(self.open_class)
            view.explain_requested.connect(self.explain_requested)
            view.answered.connect(self.answered)
            view.content_changed.connect(self.content_changed)
            self.layout_.addWidget(view)

        self._explain = ExplainCodeView(load_snippet)
        self._explain.finished.connect(self._show_summary)
        self._explain.answered.connect(self.answered)
        self._explain.submitted.connect(self.explanation_submitted)
        self._explain.content_changed.connect(self.content_changed)
        self.layout_.addWidget(self._explain)

        self._summary = SummaryView()
        self._summary.play_again.connect(self.play_again)
        self._summary.go_home.connect(self.go_home)
        self.layout_.addWidget(self._summary)
        self._views = (self._select, *self._code_views, self._explain, self._summary)
        self._show(self._select)

    # "Explícamelo mejor": cada vista descarta las respuestas que no son de su pregunta actual.

    def set_ai_available(self, available: bool, provider_name: str | None) -> None:
        for view in self._code_views:
            view.set_ai_available(available, provider_name)

    def show_ai_loading(self, question_key: str) -> None:
        for view in self._code_views:
            view.show_ai_loading(question_key)

    def show_ai_answer(self, question_key: str, text: str) -> None:
        for view in self._code_views:
            view.show_ai_answer(question_key, text)

    def show_ai_error(self, question_key: str, message: str) -> None:
        for view in self._code_views:
            view.show_ai_error(question_key, message)

    def set_model(self, model: ProjectModel | None) -> None:
        if model is None:  # cambió el proyecto: la ronda en curso ya no aplica
            self.show_mode_select()

    def show_mode_select(self, notice: str | None = None) -> None:
        self._notice_text.set_text(notice or "")
        self._notice.setVisible(bool(notice))
        self._show(self._select)

    def start(self, session: GameSession, scope_label: str | None) -> None:
        views = {EXPLAIN_CODE: self._explain, FIND_ERROR: self._find_error, FIX_CODE: self._fix_code}
        view = views.get(session.mode.mode_id, self._game)
        view.start(session, scope_label)
        self._show(view)

    # --- "Explícame este código": la evaluación llega desde MainWindow -------------

    def show_grading(self, question_key: str) -> None:
        self._explain.show_grading(question_key)

    def apply_feedback(self, question_key: str, feedback: ExplanationFeedback) -> None:
        self._explain.apply_feedback(question_key, feedback)

    def show_grading_error(self, question_key: str, message: str) -> None:
        self._explain.show_grading_error(question_key, message)

    def _show_summary(self, session: GameSession) -> None:
        self._summary.show_session(session)
        self._show(self._summary)
        self.round_finished.emit(session)

    def show_progress_change(self, before: int, after: int) -> None:
        self._summary.show_progress_change(before, after)
        self.content_changed()

    def _show(self, view: QWidget) -> None:
        # Vistas hermanas en el mismo layout, solo una visible: a diferencia de un
        # QStackedWidget, las ocultas no aportan altura y la página no queda estirada.
        for other in self._views:
            other.setVisible(other is view)
        self.verticalScrollBar().setValue(0)
        self.content_changed()
