"""Vista de "Corrige el código": el fragmento real con un error, en un editor para arreglarlo."""

import logging
from pathlib import PurePosixPath

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from codequest.core.analysis.snippets import SnippetRef
from codequest.core.games.base import Evaluation, GameSession, Outcome
from codequest.core.games.catalog import mode_title
from codequest.core.games.fix_code import CodeFix, FixKind, FixResult
from codequest.core.questions.models import Question
from codequest.ui.icons import icon
from codequest.ui.pages.learn.feedback import FeedbackPanel
from codequest.ui.pages.learn.game_view import MAX_EDITOR_LINES, SnippetLoader
from codequest.ui.theme import current_palette
from codequest.ui.widgets import Card, Chip, CodeEditor, IconText, muted, section_title

log = logging.getLogger(__name__)

HINT = "Edita el código aquí mismo y pulsa «Comprobar» (Ctrl+Enter). Tu archivo no se modifica."
STALE_HINT = "Este fragmento cambió desde el análisis: pulsa «No sé» para ver el error."
EXTRA_LINES = 2  # espacio para que el estudiante añada líneas sin que el editor salte


def result_title(result: FixResult | None, line: int) -> str:
    """Título del feedback según lo que hizo el estudiante."""
    if result is None:  # "No sé"
        return f"El error estaba en la línea {line}."
    match result.kind:
        case FixKind.FIXED:
            return f"¡Correcto! Arreglaste el error de la línea {line}."
        case FixKind.OTHER_CHANGES:
            return (f"Casi: arreglaste la línea {line}, pero también cambiaste otras partes. "
                    "Compara tu versión con tu código original.")
        case FixKind.SYNTAX_ERROR if result.error_line is not None:
            return f"Todavía no: tu versión tiene un error de sintaxis en la línea {result.error_line}."
        case FixKind.SYNTAX_ERROR:
            return "Todavía no: tu versión deja algo sin cerrar (una llave, un paréntesis o un «;»)."
        case FixKind.UNCHANGED:
            return f"Todavía no: el código sigue igual. El error estaba en la línea {line}."
        case _:
            return f"Todavía no: la línea {line} sigue sin estar bien."


class FixCodeView(QWidget):
    finished = Signal(object)  # GameSession
    answered = Signal(object)  # Evaluation: para guardar el progreso
    open_class = Signal(str)  # nombre cualificado
    content_changed = Signal()
    explain_requested = Signal(object)  # Evaluation

    def __init__(self, load_snippet: SnippetLoader, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._load_snippet = load_snippet
        self._session: GameSession | None = None
        self._original: str | None = None  # fragmento real; None si no se pudo preparar el ejercicio
        self._mutated = ""
        self._file_text: str | None = None
        self._first_line = 1

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
        self._hint = muted(HINT)
        card.body.addWidget(self._hint)
        self._snippet_label = QLabel()
        self._snippet_label.setObjectName("EditorHeader")
        card.body.addWidget(self._snippet_label)
        self._editor = CodeEditor(read_only=False)
        self._editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._editor.submit_requested.connect(self._confirm)
        card.body.addWidget(self._editor)
        layout.addWidget(card)

        layout.addLayout(self._build_actions())
        self._feedback = FeedbackPanel()
        self._feedback.open_class.connect(self.open_class)
        self._feedback.explain_requested.connect(self.explain_requested)
        self._feedback.hide()
        layout.addWidget(self._feedback)
        for key in ("Ctrl+Return", "Ctrl+Enter"):  # con el foco fuera del editor
            QShortcut(QKeySequence(key), self).activated.connect(self._confirm)

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
        self._dont_know = QPushButton("No sé cómo arreglarlo")
        self._dont_know.setIcon(icon("dont-know"))
        self._dont_know.setProperty("variant", "ghost")
        self._dont_know.setToolTip("Muestra el error y cómo era tu código")
        self._dont_know.clicked.connect(self._skip)
        row.addWidget(self._dont_know)
        self._reset = QPushButton("Deshacer mis cambios")
        self._reset.setIcon(icon("replay"))
        self._reset.setProperty("variant", "ghost")
        self._reset.setToolTip("Vuelve al fragmento tal como se mostró")
        self._reset.clicked.connect(self._restore)
        row.addWidget(self._reset)
        row.addStretch(1)
        self._check = QPushButton("Comprobar")
        self._check.setIcon(icon("correct", color="#ffffff", color_on="#ffffff"))
        self._check.setProperty("variant", "primary")
        self._check.setToolTip("Atajo: Ctrl+Enter")
        self._check.clicked.connect(self._answer)
        row.addWidget(self._check)
        self._next = QPushButton("Siguiente")
        self._next.setIcon(icon("next", color="#ffffff", color_on="#ffffff"))
        self._next.setIconSize(QSize(18, 18))
        self._next.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._next.setProperty("variant", "primary")
        self._next.setToolTip("Atajo: Ctrl+Enter")
        self._next.clicked.connect(self._go_next)
        self._next.hide()
        row.addWidget(self._next)
        return row

    # --- IA (opcional: "Explícamelo mejor") ------------------------------------------

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

    def edited_code(self) -> str:
        return self._editor.code()

    def set_edited_code(self, text: str) -> None:
        """Sustituye el contenido del editor (lo usan los tests; el estudiante escribe directamente)."""
        self._editor.setPlainText(text)

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
        self._prepare(question)
        ready = self._original is not None
        self._editor.set_read_only(not ready)
        self._hint.setText(HINT if ready else STALE_HINT)
        self._check.setEnabled(ready)
        self._check.show()
        self._reset.setEnabled(ready)
        self._dont_know.setEnabled(True)
        self._next.hide()
        self._feedback.hide()
        self._editor.setFocus()
        self.content_changed.emit()

    def _prepare(self, question: Question) -> None:
        ref, mutation = question.snippet, question.mutation
        self._original = self._file_text = None
        try:
            snippet = self._load_snippet(ref)
            self._mutated = mutation.apply(snippet.text, snippet.start_line)  # copia en memoria
            self._original, self._first_line = snippet.text, snippet.start_line
        except (OSError, ValueError) as exc:  # el archivo cambió o desapareció desde el análisis
            log.warning("No se pudo preparar el ejercicio %s: %s", question.key, exc)
            self._mutated, self._first_line = f"// No se pudo leer {ref.file}: {exc}", 1
        if self._original is not None:
            try:  # el archivo completo solo sirve para comprobar la sintaxis en contexto
                self._file_text = self._load_snippet(SnippetRef.whole_file(ref.file)).text
            except (OSError, ValueError) as exc:
                log.warning("Sin contexto del archivo para %s: %s", question.key, exc)
        last = self._first_line + self._mutated.count("\n")
        self._snippet_label.setText(f"{PurePosixPath(ref.file).name}  ·  líneas {self._first_line}–{last}")
        self._editor.set_code(self._mutated, first_line=self._first_line)
        lines = min(self._mutated.count("\n") + 1 + EXTRA_LINES, MAX_EDITOR_LINES)
        self._editor.setFixedHeight(lines * self._editor.fontMetrics().lineSpacing() + 26)

    def _restore(self) -> None:
        if self._can_answer():
            self._editor.set_code(self._mutated, first_line=self._first_line)

    def _confirm(self) -> None:
        if self._session is not None and self._session.is_answered:
            self._go_next()
        else:
            self._answer()

    def _answer(self) -> None:
        if self._can_answer() and self._original is not None:
            fix = CodeFix(self.edited_code(), self._original, self._first_line, self._file_text)
            evaluation = self._session.answer(fix)
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
        result = evaluation.answer if isinstance(evaluation.answer, FixResult) else None
        self._editor.set_read_only(True)
        palette = current_palette()
        if evaluation.outcome is Outcome.SKIPPED:
            self._editor.mark_lines({mutation.line: palette.danger_soft})
        elif result is not None and result.kind is FixKind.SYNTAX_ERROR and result.error_line is not None:
            self._editor.mark_lines({result.error_line: palette.danger_soft})
        elif evaluation.outcome is Outcome.CORRECT:
            self._editor.mark_lines({mutation.line: palette.success_soft})
        self._check.hide()
        self._reset.setEnabled(False)
        self._dont_know.setEnabled(False)
        self._score.setText(f"{self._session.correct_count} correctas")
        self._progress.setValue(self._session.position + 1)

        self._feedback.show_evaluation(evaluation, custom_title=result_title(result, mutation.line))
        if self._original is not None:
            index = mutation.line - self._first_line
            self._feedback.show_change(self._original.split("\n")[index], self._mutated.split("\n")[index])
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
