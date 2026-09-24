"""Vista del modo "Explícame este código": fragmento real, respuesta libre y feedback de la IA."""

import logging
from pathlib import PurePosixPath

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from codequest.core.ai.explanation_grader import MAX_ANSWER_CHARS, ExplanationFeedback, answer_problem
from codequest.core.analysis.snippets import CodeSnippet, SnippetRef
from codequest.core.games.base import Evaluation, GameSession, Outcome
from codequest.ui.formatting import inline_code_html
from codequest.ui.icons import icon
from codequest.ui.pages.learn.ai_explanation import paragraphs_html
from codequest.ui.pages.learn.game_view import MAX_EDITOR_LINES, SnippetLoader
from codequest.ui.theme import current_palette
from codequest.ui.widgets import Card, Chip, CodeEditor, IconText, muted, section_title
from codequest.ui.widgets.style_utils import set_style_property

log = logging.getLogger(__name__)

_TITLES = {
    Outcome.CORRECT: ("Entendiste la idea principal.", "success", "correct"),
    Outcome.PARTIAL: ("Vas bien, pero te faltó algo importante.", "warning", "explain"),
    Outcome.INCORRECT: ("Todavía no: revisa la explicación de abajo.", "danger", "incorrect"),
    Outcome.SKIPPED: ("No pasa nada: así funciona este código.", "info", "explain"),
}


class ExplainCodeView(QWidget):
    submitted = Signal(object, str)  # Question, texto del estudiante
    answered = Signal(object)  # Evaluation
    finished = Signal(object)  # GameSession
    content_changed = Signal()

    def __init__(self, load_snippet: SnippetLoader, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._load_snippet = load_snippet
        self._session: GameSession | None = None
        self._grading = False

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
        self._snippet_label = QLabel()
        self._snippet_label.setObjectName("EditorHeader")
        self._editor = CodeEditor(read_only=True)
        for widget in (self._prompt, self._snippet_label, self._editor):
            question_card.body.addWidget(widget)
        layout.addWidget(question_card)

        answer_card = Card(padding=18)
        answer_card.body.setSpacing(10)
        answer_card.body.addWidget(section_title("Tu explicación"))
        self._answer = QPlainTextEdit()
        self._answer.setObjectName("AnswerBox")
        self._answer.setPlaceholderText("Escribe aquí qué hace este código y para qué sirve, como se lo "
                                        "explicarías a un compañero. No hace falta usar términos técnicos.")
        self._answer.setMinimumHeight(120)
        self._answer.textChanged.connect(self._on_text_changed)
        answer_card.body.addWidget(self._answer)
        self._hint = muted("")
        answer_card.body.addWidget(self._hint)
        answer_card.body.addLayout(self._build_actions())
        layout.addWidget(answer_card)

        self._feedback = self._build_feedback()
        self._feedback.hide()
        layout.addWidget(self._feedback)

        submit = QShortcut(QKeySequence("Ctrl+Return"), self)
        submit.activated.connect(self._submit)

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
        row.addWidget(IconText("ai", "Evaluado con IA", color=current_palette().syntax_annotation))
        return row

    def _build_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self._dont_know = QPushButton("No sé")
        self._dont_know.setIcon(icon("dont-know"))
        self._dont_know.setProperty("variant", "ghost")
        self._dont_know.setToolTip("Muestra cómo funciona este código sin evaluar nada")
        self._dont_know.clicked.connect(self._skip)
        row.addWidget(self._dont_know)
        row.addStretch(1)
        self._submit_button = QPushButton("Enviar explicación")
        self._submit_button.setIcon(icon("ai", color="#ffffff", color_on="#ffffff"))
        self._submit_button.setIconSize(QSize(18, 18))
        self._submit_button.setProperty("variant", "primary")
        self._submit_button.setToolTip("Atajo: Ctrl+Enter")
        self._submit_button.clicked.connect(self._submit)
        row.addWidget(self._submit_button)
        self._next = QPushButton("Siguiente")
        self._next.setIcon(icon("next", color="#ffffff", color_on="#ffffff"))
        self._next.setIconSize(QSize(18, 18))
        self._next.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
        self._next.setProperty("variant", "primary")
        self._next.clicked.connect(self._go_next)
        self._next.hide()
        row.addWidget(self._next)
        return row

    def _build_feedback(self) -> Card:
        card = Card(padding=22)
        card.body.setSpacing(12)
        header = QHBoxLayout()
        header.setSpacing(10)
        self._fb_icon = QLabel()
        self._fb_title = QLabel()
        self._fb_title.setObjectName("FeedbackTitle")
        self._fb_title.setWordWrap(True)
        header.addWidget(self._fb_icon)
        header.addWidget(self._fb_title, 1)
        card.body.addLayout(header)
        self._fb_summary = QLabel()
        self._fb_summary.setObjectName("FeedbackBody")
        self._fb_summary.setWordWrap(True)
        self._fb_summary.setTextFormat(Qt.TextFormat.RichText)
        card.body.addWidget(self._fb_summary)

        self._lists = QWidget()
        self._lists_layout = QVBoxLayout(self._lists)
        self._lists_layout.setContentsMargins(0, 0, 0, 0)
        self._lists_layout.setSpacing(8)
        card.body.addWidget(self._lists)

        self._model_card = Card(variant="analogy", padding=16)
        self._model_card.body.setSpacing(6)
        self._model_title = IconText("explain", "<b>Una explicación posible</b>",
                                     color=current_palette().syntax_annotation, role="body")
        self._model_card.body.addWidget(self._model_title)
        self._model_text = QLabel()
        self._model_text.setObjectName("FeedbackBody")
        self._model_text.setWordWrap(True)
        self._model_text.setTextFormat(Qt.TextFormat.RichText)
        self._model_card.body.addWidget(self._model_text)
        card.body.addWidget(self._model_card)
        return card

    # --- ciclo de juego ---------------------------------------------------------

    def start(self, session: GameSession, scope_label: str | None) -> None:
        self._session = session
        self._progress.setRange(0, max(session.total, 1))
        self._scope.set_text(scope_label or "Todo el proyecto")
        self._show_exercise()

    def _show_exercise(self) -> None:
        session = self._session
        if session is None or session.current is None:
            return
        question = session.current
        self._grading = False
        self._counter.setText(f"EXPLÍCAME ESTE CÓDIGO · EJERCICIO {session.position + 1} DE {session.total}")
        self._progress.setValue(session.position)
        self._score.setText(f"{session.correct_count} bien")
        self._prompt.setText(inline_code_html(question.prompt))
        self._show_snippet(question.snippet)
        self._answer.clear()
        self._answer.setReadOnly(False)
        self._answer.setFocus()
        self._hint.setText("Cuanto más concreta sea tu explicación, mejor feedback recibirás.")
        self._set_buttons(answering=True)
        self._feedback.hide()
        self.content_changed.emit()

    def _show_snippet(self, ref: SnippetRef | None) -> None:
        if ref is None:
            self._editor.hide()
            self._snippet_label.hide()
            return
        try:
            snippet = self._load_snippet(ref)
        except (OSError, ValueError) as exc:
            log.warning("No se pudo leer el fragmento %s: %s", ref, exc)
            snippet = CodeSnippet(ref.file, 1, 1, f"// No se pudo leer {ref.file}: {exc}")
        self._snippet_label.setText(
            f"{PurePosixPath(snippet.file).name}  ·  líneas {snippet.start_line}–{snippet.end_line}")
        self._editor.set_code(snippet.text, first_line=snippet.start_line)
        lines = min(snippet.line_count, MAX_EDITOR_LINES)
        self._editor.setFixedHeight(lines * self._editor.fontMetrics().lineSpacing() + 26)
        self._editor.show()
        self._snippet_label.show()

    def _set_buttons(self, answering: bool) -> None:
        self._dont_know.setVisible(answering)
        self._submit_button.setVisible(answering)
        self._next.setVisible(not answering)
        self._dont_know.setEnabled(answering and not self._grading)
        self._submit_button.setEnabled(answering and not self._grading)

    def _on_text_changed(self) -> None:
        if len(self._answer.toPlainText()) > MAX_ANSWER_CHARS:
            self._hint.setText(f"Máximo {MAX_ANSWER_CHARS} caracteres.")

    def _can_answer(self) -> bool:
        return (self._session is not None and self._session.current is not None
                and not self._session.is_answered and not self._grading)

    def _submit(self) -> None:
        if not self._can_answer():
            return
        text = self._answer.toPlainText()
        if (problem := answer_problem(text)) is not None:  # se valida antes de gastar una llamada
            self._hint.setText(problem)
            return
        self.submitted.emit(self._session.current, text)

    def _skip(self) -> None:
        if self._can_answer():
            evaluation = self._session.skip()
            self.answered.emit(evaluation)
            self._reveal(evaluation)

    # --- evaluación (la hace MainWindow en segundo plano) -----------------------------

    def current_key(self) -> str | None:
        return self._session.current.key if self._session and self._session.current else None

    def show_grading(self, question_key: str) -> None:
        if self.current_key() != question_key:
            return
        self._grading = True
        self._answer.setReadOnly(True)
        self._set_buttons(answering=True)
        self._submit_button.setText("Evaluando…")
        self._hint.setText("La IA está leyendo tu explicación…")

    def show_grading_error(self, question_key: str, message: str) -> None:
        if self.current_key() != question_key:
            return
        self._grading = False
        self._answer.setReadOnly(False)
        self._submit_button.setText("Enviar explicación")
        self._set_buttons(answering=True)
        self._hint.setText(f"No se pudo evaluar tu explicación. {message}")

    def apply_feedback(self, question_key: str, feedback: ExplanationFeedback) -> None:
        # Si el estudiante cambió de ronda mientras se evaluaba, el resultado ya no aplica.
        if self.current_key() != question_key or self._session is None or self._session.is_answered:
            return
        self._grading = False
        self._submit_button.setText("Enviar explicación")
        evaluation = self._session.answer(feedback)
        self.answered.emit(evaluation)
        self._reveal(evaluation)

    def _reveal(self, evaluation: Evaluation) -> None:
        palette = current_palette()
        title, tone, icon_name = _TITLES[evaluation.outcome]
        color = {"success": palette.success, "warning": palette.warning, "danger": palette.danger,
                 "info": palette.syntax_annotation}[tone]
        self._fb_icon.setPixmap(icon(icon_name, color).pixmap(22, 22))
        self._fb_title.setText(title)
        set_style_property(self._fb_title, "tone", tone)
        variant = {"success": "success", "danger": "danger", "warning": "warning"}.get(tone)
        set_style_property(self._feedback, "variant", variant)

        self._clear_lists()
        concept = evaluation.question.concept
        feedback = evaluation.answer if isinstance(evaluation.answer, ExplanationFeedback) else None
        if feedback is not None:
            self._fb_summary.setText(paragraphs_html(feedback.summary))
            self._add_list("correct", palette.success, "Lo que entendiste", feedback.understood)
            self._add_list("explain", palette.warning, "Te faltó", feedback.missing)
            self._add_list("incorrect", palette.danger, "Cuidado con", feedback.mistakes)
            self._model_text.setText(paragraphs_html(feedback.model_answer))
            self._model_card.setVisible(bool(feedback.model_answer))
        else:  # "No sé": explicación local del concepto, sin IA
            self._fb_summary.setText(paragraphs_html(f"El concepto clave aquí es `{concept.title}`: "
                                                     f"{concept.summary}"))
            self._model_text.setText(paragraphs_html(concept.explanation))
            self._model_card.show()

        self._answer.setReadOnly(True)
        self._set_buttons(answering=False)
        last = self._session.position + 1 == self._session.total
        self._next.setText("Ver resultados" if last else "Siguiente")
        self._next.setFocus()
        self._score.setText(f"{self._session.correct_count} bien")
        self._progress.setValue(self._session.position + 1)
        self._hint.setText("")
        self._feedback.show()
        self.content_changed.emit()

    def _add_list(self, icon_name: str, color: str, title: str, items: tuple[str, ...]) -> None:
        if not items:
            return
        self._lists_layout.addWidget(IconText(icon_name, f"<b>{title}</b>", color=color, role="body"))
        for item in items:
            label = QLabel(inline_code_html(f"• {item}"))
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setIndent(28)
            self._lists_layout.addWidget(label)

    def _clear_lists(self) -> None:
        while (item := self._lists_layout.takeAt(0)) is not None:
            if widget := item.widget():
                widget.hide()
                widget.deleteLater()

    def _go_next(self) -> None:
        session = self._session
        if session is None or not session.is_answered:
            return
        session.next()
        if session.is_finished:
            self.finished.emit(session)
        else:
            self._show_exercise()
