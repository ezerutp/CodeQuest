"""Vista de una ronda de Alternativas: enunciado, código real, 4 opciones y explicación."""

import logging
from collections.abc import Callable
from pathlib import PurePosixPath

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from codequest.core.analysis.snippets import CodeSnippet, SnippetRef
from codequest.core.games.base import Evaluation, GameSession, Outcome
from codequest.core.games.catalog import mode_title
from codequest.core.questions.generator import TRUE_FALSE_CHOICES
from codequest.ui.formatting import inline_code_html
from codequest.ui.icons import icon
from codequest.ui.pages.learn.feedback import FeedbackPanel
from codequest.ui.widgets import Card, Chip, ChoiceButton, CodeEditor, IconText, section_title
from codequest.ui.widgets.choice_button import LETTERS

log = logging.getLogger(__name__)

SnippetLoader = Callable[[SnippetRef], CodeSnippet]
MAX_EDITOR_LINES = 16


class GameView(QWidget):
    finished = Signal(object)  # GameSession
    answered = Signal(object)  # Evaluation: para guardar el progreso
    open_class = Signal(str)  # nombre cualificado
    content_changed = Signal()  # la altura cambió: la página debe reajustar su scroll
    explain_requested = Signal(object)  # Evaluation

    def __init__(self, load_snippet: SnippetLoader, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._load_snippet = load_snippet
        self._session: GameSession | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(14)
        layout.addLayout(self._build_top_bar())
        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        layout.addWidget(self._progress)

        question_card = Card(padding=22)
        question_card.body.setSpacing(14)
        self._prompt = QLabel()
        self._prompt.setObjectName("QuestionPrompt")
        self._prompt.setWordWrap(True)
        self._prompt.setTextFormat(Qt.TextFormat.RichText)
        question_card.body.addWidget(self._prompt)
        self._snippet_label = QLabel()
        self._snippet_label.setObjectName("EditorHeader")
        question_card.body.addWidget(self._snippet_label)
        self._editor = CodeEditor(read_only=True)
        self._editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        question_card.body.addWidget(self._editor)
        layout.addWidget(question_card)

        self._choices: list[ChoiceButton] = []
        for index in range(4):
            choice = ChoiceButton(index)
            choice.clicked.connect(lambda i=index: self._answer(i))
            self._choices.append(choice)
            layout.addWidget(choice)

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
        self._dont_know = QPushButton("No sé la respuesta")
        self._dont_know.setIcon(icon("dont-know"))
        self._dont_know.setProperty("variant", "ghost")
        self._dont_know.setToolTip("Muestra la respuesta con una explicación (atajo: 0)")
        self._dont_know.clicked.connect(self._skip)
        row.addWidget(self._dont_know)
        row.addStretch(1)
        self._next = QPushButton("Siguiente")
        self._next.setIcon(icon("next", color="#ffffff", color_on="#ffffff"))
        self._next.setIconSize(QSize(18, 18))
        self._next.setLayoutDirection(Qt.LayoutDirection.RightToLeft)  # icono a la derecha
        self._next.setProperty("variant", "primary")
        self._next.setToolTip("Atajo: Enter")
        self._next.clicked.connect(self._go_next)
        self._next.hide()
        row.addWidget(self._next)
        return row

    def _install_shortcuts(self) -> None:
        for index, letter in enumerate(LETTERS[:4]):
            for key in (str(index + 1), letter):
                shortcut = QShortcut(QKeySequence(key), self)
                shortcut.activated.connect(lambda i=index: self._answer(i))
        QShortcut(QKeySequence("0"), self).activated.connect(self._skip)
        for key in ("Return", "Enter"):
            QShortcut(QKeySequence(key), self).activated.connect(self._go_next)

    # --- IA ------------------------------------------------------------------------

    def set_ai_available(self, available: bool, provider_name: str | None) -> None:
        self._feedback.set_ai_available(available, provider_name)

    def show_ai_loading(self, question_key: str) -> None:
        if self._feedback.current_key() == question_key:
            self._feedback.show_ai_loading()

    def show_ai_answer(self, question_key: str, text: str) -> None:
        # Si el estudiante ya pasó a otra pregunta, la respuesta llega tarde: se descarta.
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

    def _show_question(self) -> None:
        session = self._session
        if session is None or session.current is None:
            return
        question = session.current
        title = mode_title(session.mode.mode_id).upper()
        self._counter.setText(f"{title} · PREGUNTA {session.position + 1} DE {session.total}")
        self._progress.setValue(session.position)
        self._score.setText(f"{session.correct_count} correctas")
        is_statement = question.choices == TRUE_FALSE_CHOICES
        self._prompt.setText(inline_code_html(f"«{question.prompt}»" if is_statement else question.prompt))

        self._show_snippet(question.snippet)
        for index, choice in enumerate(self._choices):
            visible = index < len(question.choices)
            choice.setVisible(visible)
            if not visible:
                continue
            choice.set_text(question.choices[index])
            choice.set_letter(question.choices[index][0] if is_statement else LETTERS[index])
            choice.set_state("idle")
            choice.setEnabled(True)
        self._dont_know.setEnabled(True)
        self._next.hide()
        self._feedback.hide()
        self.content_changed.emit()

    def _show_snippet(self, ref: SnippetRef | None) -> None:
        visible = ref is not None
        self._editor.setVisible(visible)
        self._snippet_label.setVisible(visible)
        if ref is None:
            return
        try:
            snippet = self._load_snippet(ref)
        except (OSError, ValueError) as exc:  # el archivo cambió o desapareció desde el análisis
            log.warning("No se pudo leer el fragmento %s: %s", ref, exc)
            snippet = CodeSnippet(ref.file, 1, 1, f"// No se pudo leer {ref.file}: {exc}")
        self._snippet_label.setText(
            f"{PurePosixPath(snippet.file).name}  ·  líneas {snippet.start_line}–{snippet.end_line}"
        )
        self._editor.set_code(snippet.text, first_line=snippet.start_line)
        self._editor.highlight_lines(ref.focus_lines, scroll=False)
        lines = min(snippet.line_count, MAX_EDITOR_LINES)
        self._editor.setFixedHeight(lines * self._editor.fontMetrics().lineSpacing() + 26)

    def _answer(self, index: int) -> None:
        # Los atajos 3/4 no aplican cuando la pregunta tiene solo 2 opciones (Verdadero/Falso).
        if self._can_answer() and index < len(self._session.current.choices):
            evaluation = self._session.answer(index)
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
        question = evaluation.question
        for choice in self._choices:
            choice.setEnabled(False)
            if choice.index == question.correct_index:
                choice.set_state("correct")
            elif evaluation.outcome is Outcome.INCORRECT and choice.index == evaluation.answer:
                choice.set_state("incorrect")
            else:
                choice.set_state("dimmed")
        self._dont_know.setEnabled(False)
        self._score.setText(f"{self._session.correct_count} correctas")
        self._progress.setValue(self._session.position + 1)

        self._feedback.show_evaluation(evaluation, self._choices[question.correct_index].letter)
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
