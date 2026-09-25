"""Vista de "Corrige el código": el fragmento real con un error, en un editor para arreglarlo."""

import logging
from collections.abc import Callable
from pathlib import PurePosixPath

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from codequest.core.analysis.snippets import SnippetRef
from codequest.core.games.base import Evaluation, GameSession, Outcome
from codequest.core.games.catalog import mode_title
from codequest.core.games.fix_code import CodeFix, FixKind, FixResult, check_fix
from codequest.core.lsp.documents import new_errors, splice, utf16_column
from codequest.core.lsp.models import CompletionList, Diagnostic
from codequest.core.questions.models import Question
from codequest.ui.icons import icon, icon_label
from codequest.ui.pages.learn.feedback import FeedbackPanel
from codequest.ui.pages.learn.game_view import MAX_EDITOR_LINES, SnippetLoader
from codequest.ui.theme import current_palette
from codequest.ui.widgets import Card, Chip, CodeEditor, IconText, muted, section_title
from codequest.ui.widgets.style_utils import set_style_property
from codequest.ui.workers import LatestOnlyTask

log = logging.getLogger(__name__)

HINT = ("Edita el código aquí mismo. «Probar» (Ctrl+Shift+Enter) revisa tu versión sin enviarla; "
        "«Comprobar» (Ctrl+Enter) la envía. Tu archivo no se modifica.")
COMPLETION_HINT = " Escribe «.» o pulsa Ctrl+Espacio para ver sugerencias."
STALE_HINT = "Este fragmento cambió desde el análisis: pulsa «No sé» para ver el error."
EXTRA_LINES = 2  # espacio para que el estudiante añada líneas sin que el editor salte

# (archivo relativo al proyecto, texto completo en memoria, línea, columna UTF-16) -> sugerencias.
# Bloquea: se llama desde un worker.
CompletionSource = Callable[[str, str, int, int], CompletionList]
# (archivo relativo, texto completo en memoria) -> errores de compilación; None si jdtls no está listo.
DiagnosticsSource = Callable[[str, str], tuple[Diagnostic, ...] | None]
# Resultados de «Probar» que merecen preguntar al compilador (los demás ya lo dicen todo).
COMPILE_CHECKED = (FixKind.OTHER_CHANGES, FixKind.STILL_BROKEN)


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


def trial_message(result: FixResult) -> tuple[str, str]:
    """Tono y texto del resultado de «Probar». No dice en qué línea está el error: encontrarlo
    sigue siendo parte del ejercicio."""
    match result.kind:
        case FixKind.FIXED:
            return "success", "Tu versión está bien: pulsa «Comprobar» para enviarla."
        case FixKind.OTHER_CHANGES:
            return "warning", ("Arreglaste el error, pero también cambiaste otras partes. "
                               "Puedes deshacer lo que no hacía falta tocar.")
        case FixKind.SYNTAX_ERROR if result.error_line is not None:
            return "danger", f"Error de sintaxis en la línea {result.error_line}."
        case FixKind.SYNTAX_ERROR:
            return "danger", "Error de sintaxis: falta cerrar algo (una llave, un paréntesis o un «;»)."
        case FixKind.UNCHANGED:
            return "info", "Todavía no has cambiado nada."
        case _:
            return "warning", "La sintaxis es correcta, pero el error sigue ahí."


_TRIAL_ICONS = {"success": "correct", "danger": "incorrect", "warning": "warning", "info": "info"}


class FixCodeView(QWidget):
    finished = Signal(object)  # GameSession
    answered = Signal(object)  # Evaluation: para guardar el progreso
    open_class = Signal(str)  # nombre cualificado
    content_changed = Signal()
    explain_requested = Signal(object)  # Evaluation

    def __init__(self, load_snippet: SnippetLoader, complete: CompletionSource | None = None,
                 diagnose: DiagnosticsSource | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._load_snippet = load_snippet
        self._complete = complete
        self._diagnose = diagnose
        self._completion_available = False
        self._compiler_ready = False
        self._completions = LatestOnlyTask(self)
        self._completions.finished.connect(lambda answer: self._editor.show_completions(*answer))
        # Errores de compilación: los de la versión con el error (de partida) y los de cada «Probar».
        self._compiler = LatestOnlyTask(self)
        self._compiler.finished.connect(self._on_compiled)
        self._baseline: tuple[Diagnostic, ...] | None = None
        self._trial_token = 0
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
        self._editor.try_requested.connect(self._try)
        self._editor.completion_requested.connect(self._request_completions)
        self._editor.textChanged.connect(self._clear_trial)
        card.body.addWidget(self._editor)
        card.body.addWidget(self._build_trial())
        layout.addWidget(card)

        layout.addLayout(self._build_actions())
        self._feedback = FeedbackPanel()
        self._feedback.open_class.connect(self.open_class)
        self._feedback.explain_requested.connect(self.explain_requested)
        self._feedback.hide()
        layout.addWidget(self._feedback)
        for key in ("Ctrl+Return", "Ctrl+Enter"):  # con el foco fuera del editor
            QShortcut(QKeySequence(key), self).activated.connect(self._confirm)
        for key in ("Ctrl+Shift+Return", "Ctrl+Shift+Enter"):
            QShortcut(QKeySequence(key), self).activated.connect(self._try)

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

    def _build_trial(self) -> QWidget:
        self._trial = QWidget()
        row = QHBoxLayout(self._trial)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self._trial_icon = icon_label("info")
        row.addWidget(self._trial_icon, 0, Qt.AlignmentFlag.AlignVCenter)
        self._trial_text = QLabel()
        self._trial_text.setObjectName("TrialResult")
        self._trial_text.setWordWrap(True)
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(self._trial_text)
        self._compile_note = muted("")  # "Revisando con el compilador…" / "no encontró errores"
        self._compile_note.hide()
        texts.addWidget(self._compile_note)
        row.addLayout(texts, 1)
        self._trial.hide()
        return self._trial

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
        self._try_button = QPushButton("Probar")
        self._try_button.setIcon(icon("play"))
        self._try_button.setToolTip("Revisa tu versión sin enviarla (no cuenta como intento). Atajo: Ctrl+Shift+Enter")
        self._try_button.clicked.connect(self._try)
        row.addWidget(self._try_button)
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

    # --- sugerencias (jdtls, opcional) --------------------------------------------------

    def set_language_server_ready(self, ready: bool) -> None:
        """jdtls listo (o no): sugerencias en el editor y errores de compilación en «Probar»."""
        self._completion_available = ready and self._complete is not None
        self._editor.set_completion_enabled(self._completion_available)
        self._compiler_ready = ready and self._diagnose is not None
        if self._session is not None and not self._session.is_answered and self._original is not None:
            self._hint.setText(self._hint_text())
            self._request_baseline()
            self.content_changed.emit()

    def _hint_text(self) -> str:
        return HINT + (COMPLETION_HINT if self._completion_available else "")

    def _request_completions(self, token: int) -> None:
        """El editor pide sugerencias: se le envían a jdtls con el fragmento editado dentro de su
        archivo (en memoria) y la posición real del cursor en ese archivo."""
        complete, question = self._complete, self._session.current if self._session else None
        if complete is None or question is None or self._original is None or self._file_text is None:
            return
        edited = self.edited_code()
        row, column = self._editor.cursor_position()
        text = splice(self._file_text, self._first_line, self._original, edited)
        line = self._first_line - 1 + row
        character = utf16_column(edited.split("\n")[row], column)
        path = question.snippet.file
        self._completions.submit(lambda _progress, _cancel: (token, complete(path, text, line, character)))

    def _compile_inputs(self) -> tuple[DiagnosticsSource, str, str] | None:
        """(función, archivo, texto de partida en memoria) si se puede preguntar al compilador."""
        question = self._session.current if self._session else None
        if (not self._compiler_ready or self._diagnose is None or question is None or self._original is None
                or self._file_text is None):
            return None
        return self._diagnose, question.snippet.file, splice(self._file_text, self._first_line, self._original,
                                                             self._mutated)

    def _request_baseline(self) -> None:
        """Errores de la versión con el error, antes de que el estudiante toque nada: así «Probar» solo
        muestra los que él introduce y no delata la línea del error original."""
        inputs = self._compile_inputs()
        if inputs is None or self._baseline is not None:
            return
        diagnose, path, start = inputs
        key = self._session.current.key
        self._compiler.submit(lambda _progress, _cancel: ("baseline", key, diagnose(path, start)))

    def _request_compile(self) -> None:
        inputs = self._compile_inputs()
        if inputs is None:
            return
        diagnose, path, start = inputs
        edited = self.edited_code()
        text = splice(self._file_text, self._first_line, self._original, edited)
        token, key, baseline = self._trial_token, self._session.current.key, self._baseline

        def compile_(_progress: object, _cancel: object) -> tuple:
            base = baseline if baseline is not None else diagnose(path, start)
            return "trial", (token, key), base, diagnose(path, text), edited.count("\n") + 1

        self._compile_note.setText("Revisando con el compilador…")
        self._compile_note.show()
        self._compiler.submit(compile_)

    def _on_compiled(self, answer: tuple) -> None:
        question = self._session.current if self._session else None
        if question is None:
            return
        if answer[0] == "baseline":
            _, key, errors = answer
            if key == question.key and errors is not None:
                self._baseline = errors
            return
        _, (token, key), baseline, current, line_count = answer
        if key != question.key:
            return
        if baseline is not None and self._baseline is None:
            self._baseline = baseline
        if token != self._trial_token or self._trial.isHidden() or not self._can_answer():
            return
        if baseline is None or current is None:  # jdtls dejó de estar listo
            self._compile_note.hide()
        elif errors := new_errors(current, baseline, self._first_line, line_count):
            first = errors[0]
            more = f" (y {len(errors) - 1} más)" if len(errors) > 1 else ""
            self._show_trial("danger", f"Error de compilación en la línea {first.line}{more}: «{first.message}».",
                             first.line)
            self._compile_note.setText("Lo dice el compilador de Java (jdtls).")
        else:
            self._compile_note.setText("El compilador no encontró errores nuevos.")
        self.content_changed.emit()

    def shutdown(self) -> None:
        self._compiler.shutdown()
        self._completions.shutdown()

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
        self._baseline = None
        self._prepare(question)
        ready = self._original is not None
        self._editor.set_read_only(not ready)
        self._hint.setText(self._hint_text() if ready else STALE_HINT)
        self._check.setEnabled(ready)
        self._check.show()
        self._try_button.setEnabled(ready)
        self._try_button.show()
        self._reset.setEnabled(ready)
        self._dont_know.setEnabled(True)
        self._next.hide()
        self._feedback.hide()
        self._editor.setFocus()
        self._request_baseline()
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

    def _try(self) -> None:
        """«Probar»: evalúa la versión del estudiante sin registrar la respuesta."""
        if not self._can_answer() or self._original is None:
            return
        result = check_fix(self._session.current, self._fix())
        self._trial_token += 1
        self._compile_note.hide()
        syntax_line = result.error_line if result.kind is FixKind.SYNTAX_ERROR else None
        self._show_trial(*trial_message(result), syntax_line)
        if result.kind in COMPILE_CHECKED:
            self._request_compile()
        log.debug("Probar %s: %s", self._session.current.key, result.kind)
        self.content_changed.emit()

    def _show_trial(self, tone: str, text: str, error_line: int | None) -> None:
        palette = current_palette()
        color = {"success": palette.success, "danger": palette.danger,
                 "warning": palette.warning}.get(tone, palette.text_muted)
        self._trial_icon.setPixmap(icon(_TRIAL_ICONS[tone], color).pixmap(18, 18))
        self._trial_text.setText(text)
        set_style_property(self._trial_text, "tone", tone)
        self._trial.show()
        self._editor.mark_lines({error_line: palette.danger_soft} if error_line is not None else {})

    def _clear_trial(self) -> None:
        """Al editar, el resultado de la última prueba deja de valer."""
        self._trial_token += 1  # un resultado del compilador que llegue tarde ya no vale
        if not self._trial.isHidden():
            self._trial.hide()
            if self._can_answer():
                self._editor.mark_lines({})
            self.content_changed.emit()

    def _fix(self) -> CodeFix:
        assert self._original is not None
        return CodeFix(self.edited_code(), self._original, self._first_line, self._file_text)

    def _confirm(self) -> None:
        if self._session is not None and self._session.is_answered:
            self._go_next()
        else:
            self._answer()

    def _answer(self) -> None:
        if self._can_answer() and self._original is not None:
            evaluation = self._session.answer(self._fix())
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
        self._try_button.hide()
        self._trial.hide()
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
