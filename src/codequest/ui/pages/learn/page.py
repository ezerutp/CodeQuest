"""Página "Aprender": elegir modo → jugar la ronda → ver el resumen."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from codequest.core.analysis.model import ProjectModel
from codequest.core.games.base import GameSession
from codequest.ui.pages.base import Page
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

        self._summary = SummaryView()
        self._summary.play_again.connect(self.play_again)
        self._summary.go_home.connect(self.go_home)
        self.layout_.addWidget(self._summary)
        self._views = (self._select, self._game, self._summary)
        self._show(self._select)

    def set_ai_available(self, available: bool, provider_name: str | None) -> None:
        self._game.set_ai_available(available, provider_name)

    def show_ai_loading(self, question_key: str) -> None:
        self._game.show_ai_loading(question_key)

    def show_ai_answer(self, question_key: str, text: str) -> None:
        self._game.show_ai_answer(question_key, text)

    def show_ai_error(self, question_key: str, message: str) -> None:
        self._game.show_ai_error(question_key, message)

    def set_model(self, model: ProjectModel | None) -> None:
        if model is None:  # cambió el proyecto: la ronda en curso ya no aplica
            self.show_mode_select()

    def show_mode_select(self, notice: str | None = None) -> None:
        self._notice_text.set_text(notice or "")
        self._notice.setVisible(bool(notice))
        self._show(self._select)

    def start(self, session: GameSession, scope_label: str | None) -> None:
        self._game.start(session, scope_label)
        self._show(self._game)

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
