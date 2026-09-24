"""Vista de "Encuentra el error": código real con una línea cambiada; el estudiante la señala."""

import logging
from pathlib import PurePosixPath

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from codequest.core.games.base import Evaluation, GameSession, Outcome
from codequest.core.games.catalog import mode_title
from codequest.core.questions.models import Question
from codequest.ui.icons import icon
from codequest.ui.pages.learn.feedback import FeedbackPanel
from codequest.ui.pages.learn.game_view import MAX_EDITOR_LINES, SnippetLoader
from codequest.ui.theme import current_palette
from codequest.ui.widgets import Card, Chip, CodeEditor, IconText, muted, section_title

log = logging.getLogger(__name__)

HINT = "Haz clic en la línea que crees que está mal y pulsa «Comprobar»."


class FindErrorView(QWidget):
    finished = Signal(object)  # GameSession
    answered = Signal(object)  # Evaluation: para guardar el progreso
    open_class = Signal(str)  # nombre cualificado
    content_changed = Signal()
    explain_requested = Signal(object)  # Evaluation

    def __init__(self, load_snippet: SnippetLoader, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._load_snippet = load_snippet
        self._session: GameSession | None = None
        self._selected: int | None = None
        self._lines: tuple[str, str] | None = None  # (original, con el error) de la línea cambiada
        self._loading = False  # set_code mueve el cursor: no es una elección del estudiante

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(self._build_top_bar())
        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        layout.addWidget(self._progress)

        card = Card(padding=22)
        card.body.setSpacing(12)
        self._prompt = QLabel()
        self._prompt.setObjectName("QuestionPrompt")
        self._prompt.setWordWrap(True)
        card.body.addWidget(self._prompt)
        card.body.addWidget(muted(HINT))
        self._snippet_label = QLabel()
        self._snippet_label.setObjectName("EditorHeader")
        card.body.addWidget(self._snippet_label)
        self._editor = CodeEditor(read_only=True)
        self._editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._editor.viewport().setCursor(Qt.CursorShape.PointingHandCursor)
        self._editor.cursorPositionChanged.connect(self._select_cursor_line)
        card.body.addWidget(self._editor)
        self._selection = QLabel()
        self._selection.setObjectName("SelectedLine")
        card.body.addWidget(self._selection)
        layout.addWidget(card)

        layout.addLayout(self._build_actions())
        self._feedback = FeedbackPanel()
        self._feedback.open_class.connect(self.open_class)
        self._feedback.explain_requested.connect(self.explain_requested)
        self._feedback.hide()
        layout.addWidget(self._feedback)
        self._install_shortcuts()

    # --- construcción -------------------------------------------------------

    def _build_top_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(8)
        self._counter = section_title("")
        row.addWidget(self._counter)
        self._scope = Chip("", tone="muted", icon="project")
        row.addWidget(self._scope)
        row.addStretch(1)
        self._score = QLabel()
        self._score.setProperty("role", "muted")
        row.addWidget(self._score)
        row.addSpacing(12)
        row.addWidget(IconText("local", "Procesado localmente"))
        return row

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._dont_know = QPushButton("No sé dónde está")
        self._dont_know.setIcon(icon("dont-know"))
        self._dont_know.setProperty("variant", "ghost")
        self._dont_know.setToolTip("Muestra el error con una explicación (atajo: 0)")
        self._dont_know.clicked.connect(self._skip)
        row.addWidget(self._dont_know)
        row.addStretch(1)
        self._check = QPushButton("Comprobar")
        self._check.setIcon(icon("correct", color="#ffffff", color_on="#ffffff"))
        self._check.setProperty("variant", "primary")
        self._check.setToolTip("Atajo: Enter")
        self._check.clicked.connect(self._answer)
        row.addWidget(self._check)
        self._next = QPushButton("Siguiente")
        self._next.setIcon(icon("next", color="#ffffff", color_on="#ffffff"))
        self._next.setIconSize(QSize(18, 18))
        self._next.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._next.setProperty("variant", "primary")
        self._next.setToolTip("Atajo: Enter")
        self._next.clicked.connect(self._go_next)
        self._next.hide()
        row.addWidget(self._next)
        return row

    def _install_shortcuts(self) -> None:
        QShortcut(QKeySequence("0"), self).activated.connect(self._skip)
        for key in ("Return", "Enter"):
            QShortcut(QKeySequence(key), self).activated.connect(self._confirm)

    # --- IA (opcional, como en Alternativas: "Explícamelo mejor") ------------------

    def set_ai_available(self, available: bool, provider_name: str | None) -> None:
        self._feedback.set_ai_available(available, provider_name)

    def show_ai_loading(self, question_key: str) -> None:
        if self._feedback.current_key() == question_key:
            self._feedback.show_ai_loading()

    def show_ai_answer(self, question_key: str, text: str) -> None:
        if self._feedback.current_key() == question_key and self._session and self._session.is_answered:
            self._feedback.show_ai_answer(text)
            self.content_changed.emit()

    def show_ai_error(self, question_key: str, message: str) -> None:
        if self._feedback.current_key() == question_key:
            self._feedback.show_ai_error(message)
            self.content_changed.emit()

    # --- ciclo de juego ---------------------------------------------------------

    def start(self, session: GameSession, scope_label: str | None) -> None:
        self._session = session
        self._progress.setRange(0, max(session.total, 1))
        self._scope.set_text(scope_label or "Todo el proyecto")
        self._show_question()

    @property
    def selected_line(self) -> int | None:
        return self._selected

    def select_line(self, line: int) -> None:
        """Marca la línea elegida (numeración real del archivo). También la usa el cursor del editor."""
        if not self._can_answer() or self._lines is None:
            return
        self._selected = line
        self._editor.mark_lines({line: current_palette().editor_highlight_line})
        self._selection.setText(f"Línea seleccionada: {line}")
        self._check.setEnabled(True)

    def _show_question(self) -> None:
        session = self._session
        if session is None or session.current is None:
            return
        question = session.current
        title = mode_title(session.mode.mode_id).upper()
        self._counter.setText(f"{title} · EJERCICIO {session.position + 1} DE {session.total}")
        self._progress.setValue(session.position)
        self._score.setText(f"{session.correct_count} correctas")
        self._prompt.setText(question.prompt)
        self._selected = None
        self._show_snippet(question)
        self._selection.setText("Ninguna línea seleccionada." if self._lines else
                                "Este fragmento cambió desde el análisis: pulsa «No sé» para ver el error.")
        self._check.setEnabled(False)
        self._check.show()
        self._dont_know.setEnabled(True)
        self._next.hide()
        self._feedback.hide()
        self.content_changed.emit()

    def _show_snippet(self, question: Question) -> None:
        ref, mutation = question.snippet, question.mutation
        self._lines = None
        try:
            snippet = self._load_snippet(ref)
            text = mutation.apply(snippet.text, snippet.start_line)  # copia en memoria, nunca el archivo
            index = mutation.line - snippet.start_line
            self._lines = (snippet.text.split("\n")[index], text.split("\n")[index])
            first, last = snippet.start_line, snippet.end_line
        except (OSError, ValueError) as exc:  # el archivo cambió o desapareció desde el análisis
            log.warning("No se pudo preparar el ejercicio %s: %s", question.key, exc)
            text, first, last = f"// No se pudo leer {ref.file}: {exc}", 1, 1
        self._snippet_label.setText(f"{PurePosixPath(ref.file).name}  ·  líneas {first}–{last}")
        self._loading = True
        self._editor.set_code(text, first_line=first)
        self._loading = False
        lines = min(text.count("\n") + 1, MAX_EDITOR_LINES)
        self._editor.setFixedHeight(lines * self._editor.fontMetrics().lineSpacing() + 26)

    def _select_cursor_line(self) -> None:
        if not self._loading:
            self.select_line(self._editor.cursor_line())

    def _confirm(self) -> None:
        if self._session is not None and self._session.is_answered:
            self._go_next()
        else:
            self._answer()

    def _answer(self) -> None:
        if self._can_answer() and self._selected is not None:
            evaluation = self._session.answer(self._selected)
            self.answered.emit(evaluation)
            self._reveal(evaluation)

    def _skip(self) -> None:
        if self._can_answer():
            evaluation = self._session.skip()
            self.answered.emit(evaluation)
            self._reveal(evaluation)

    def _can_answer(self) -> bool:
        return self._session is not None and self._session.current is not None and not self._session.is_answered

    def _reveal(self, evaluation: Evaluation) -> None:
        mutation = evaluation.question.mutation
        palette = current_palette()
        marks = {mutation.line: palette.success_soft}
        if evaluation.outcome is Outcome.INCORRECT:
            marks[evaluation.answer] = palette.danger_soft
        self._editor.mark_lines(marks)
        self._check.hide()
        self._dont_know.setEnabled(False)
        self._score.setText(f"{self._session.correct_count} correctas")
        self._progress.setValue(self._session.position + 1)
        if evaluation.outcome is Outcome.INCORRECT:
            self._selection.setText(f"Elegiste la línea {evaluation.answer}; el cambio estaba en la {mutation.line}.")

        self._feedback.show_evaluation(evaluation)
        if self._lines is not None:
            self._feedback.show_change(*self._lines)
        self._feedback.show()
        last = self._session.position + 1 == self._session.total
        self._next.setText("Ver resultados" if last else "Siguiente")
        self._next.show()
        self._next.setFocus()
        self.content_changed.emit()

    def _go_next(self) -> None:
        session = self._session
        if session is None or not session.is_answered:
            return
        session.next()
        if session.is_finished:
            self.finished.emit(session)
        else:
            self._show_question()
