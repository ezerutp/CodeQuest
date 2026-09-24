"""Retroalimentación educativa tras responder (o pulsar "No sé")."""

from urllib.parse import quote_plus

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QWidget

from codequest.core.games.base import Evaluation, Outcome
from codequest.core.knowledge.models import Concept
from codequest.core.questions.generator import TRUE_FALSE_CHOICES
from codequest.ui.formatting import inline_code_html
from codequest.ui.icons import icon
from codequest.ui.pages.learn.ai_explanation import AIExplanationBox, paragraphs_html
from codequest.ui.theme import current_palette
from codequest.ui.widgets import Card, IconText
from codequest.ui.widgets.style_utils import set_style_property

YOUTUBE_SEARCH = "https://www.youtube.com/results?search_query="

_STATEMENT_TITLES = {
    Outcome.CORRECT: "¡Correcto! La afirmación es {letter}.",
    Outcome.INCORRECT: "No exactamente: la afirmación es {letter}.",
    Outcome.SKIPPED: "La afirmación es {letter}.",
}

_ERROR_TITLES = {
    Outcome.CORRECT: "¡Correcto! El error estaba en la línea {line}.",
    Outcome.INCORRECT: "No exactamente: el error estaba en la línea {line}.",
    Outcome.SKIPPED: "El error estaba en la línea {line}.",
}

_TITLES = {
    Outcome.CORRECT: ("¡Correcto!", "success", "correct"),
    Outcome.INCORRECT: ("No exactamente. La respuesta correcta es la {letter}.", "danger", "incorrect"),
    Outcome.SKIPPED: ("La respuesta correcta es la {letter}.", "info", "explain"),
}


class FeedbackPanel(Card):
    open_class = Signal(str)
    explain_requested = Signal(object)  # Evaluation

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, padding=22)
        self.body.setSpacing(12)
        self._concept: Concept | None = None
        self._class_name = ""
        self._evaluation: Evaluation | None = None

        header = QHBoxLayout()
        header.setSpacing(10)
        self._icon = QLabel()
        self._title = QLabel()
        self._title.setObjectName("FeedbackTitle")
        self._title.setWordWrap(True)
        header.addWidget(self._icon)
        header.addWidget(self._title, 1)
        self.body.addLayout(header)

        self._change = self._build_change()
        self._change.hide()
        self.body.addWidget(self._change)

        self._concept_title = QLabel()
        self._concept_title.setProperty("role", "h2")
        self.body.addWidget(self._concept_title)
        self._explanation = QLabel()
        self._explanation.setObjectName("FeedbackBody")
        self._explanation.setWordWrap(True)
        self.body.addWidget(self._explanation)

        analogy = Card(variant="analogy", padding=16)
        analogy.body.setSpacing(6)
        analogy.body.addWidget(IconText("analogy", "<b>Analogía</b>", color=current_palette().syntax_annotation,
                                        role="body"))
        self._analogy = QLabel()
        self._analogy.setObjectName("FeedbackBody")
        self._analogy.setWordWrap(True)
        analogy.body.addWidget(self._analogy)
        self.body.addWidget(analogy)

        self._ai = AIExplanationBox()
        self._ai.requested.connect(lambda: self._evaluation and self.explain_requested.emit(self._evaluation))
        self._ai.hide()
        self._ai_enabled = False
        self.body.addWidget(self._ai)

        actions = QHBoxLayout()
        youtube = QPushButton("Buscar en YouTube")
        youtube.setIcon(icon("youtube"))
        youtube.setToolTip("Abre una búsqueda de videos sobre este concepto en tu navegador")
        youtube.clicked.connect(self._open_youtube)
        actions.addWidget(youtube)
        explorer = QPushButton("Ver la clase en Mi proyecto")
        explorer.setIcon(icon("project"))
        explorer.setProperty("variant", "ghost")
        explorer.clicked.connect(lambda: self._class_name and self.open_class.emit(self._class_name))
        actions.addWidget(explorer)
        actions.addStretch(1)
        self.body.addLayout(actions)

    def _build_change(self) -> QWidget:
        """"Encuentra el error": la línea real frente a la modificada y por qué falla."""
        box = QWidget()
        grid = QGridLayout(box)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(8)
        self._original = QLabel()
        self._mutated = QLabel()
        for row, (caption, label, tone) in enumerate((("Tu código", self._original, "added"),
                                                      ("Con el error", self._mutated, "removed"))):
            title = QLabel(caption)
            title.setProperty("role", "muted")
            grid.addWidget(title, row, 0)
            label.setObjectName("DiffLine")
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            set_style_property(label, "tone", tone)
            grid.addWidget(label, row, 1)
        grid.setColumnStretch(1, 1)
        self._change_explanation = QLabel()
        self._change_explanation.setObjectName("FeedbackBody")
        self._change_explanation.setWordWrap(True)
        self._change_explanation.setTextFormat(Qt.TextFormat.RichText)
        grid.addWidget(self._change_explanation, 2, 0, 1, 2)
        return box

    def show_change(self, original: str, mutated: str) -> None:
        """Muestra la comparación; llamar después de `show_evaluation` con una pregunta con mutación."""
        self._original.setText(original.strip())
        self._mutated.setText(mutated.strip())
        self._change.show()

    def show_evaluation(self, evaluation: Evaluation, correct_letter: str = "") -> None:
        concept = evaluation.question.concept
        self._concept = concept
        self._class_name = evaluation.question.class_name
        self._evaluation = evaluation
        self._ai.reset()
        self._ai.setVisible(self._ai_enabled)

        title, tone, icon_name = _TITLES[evaluation.outcome]
        question = evaluation.question
        is_statement = question.choices == TRUE_FALSE_CHOICES
        if is_statement:
            title = _STATEMENT_TITLES[evaluation.outcome]
            correct_letter = "verdadera" if question.correct_index == 0 else "falsa"
        palette = current_palette()
        color = {"success": palette.success, "danger": palette.danger, "info": palette.syntax_annotation}[tone]
        self._icon.setPixmap(icon(icon_name, color).pixmap(22, 22))
        mutation = question.mutation
        if mutation is not None:
            title = _ERROR_TITLES[evaluation.outcome]
            self._change_explanation.setText(inline_code_html(mutation.explanation))
        self._change.hide()
        self._title.setText(title.format(letter=correct_letter, line=mutation.line if mutation else ""))
        set_style_property(self._title, "tone", tone)
        set_style_property(self, "variant", "success" if tone == "success" else "danger" if tone == "danger" else None)

        self._concept_title.setText(inline_code_html(f"`{concept.title}`"))
        explanation = concept.explanation
        if is_statement and question.correct_index == 1:
            # Afirmación falsa: primero lo que hace de verdad, luego la explicación completa.
            explanation = f"Lo que hace en realidad: {concept.summary}\n\n{explanation}"
        self._explanation.setText(paragraphs_html(explanation))
        self._analogy.setText(inline_code_html(concept.analogy))

    # --- IA ------------------------------------------------------------------------

    def set_ai_available(self, available: bool, provider_name: str | None) -> None:
        self._ai_enabled = available
        self._ai.set_provider(provider_name or "la IA")
        self._ai.setVisible(available and self._evaluation is not None)

    def current_key(self) -> str | None:
        return self._evaluation.question.key if self._evaluation else None

    def show_ai_loading(self) -> None:
        self._ai.show_loading()

    def show_ai_answer(self, text: str) -> None:
        self._ai.show_answer(text)

    def show_ai_error(self, message: str) -> None:
        self._ai.show_error(message)

    def _open_youtube(self) -> None:
        if self._concept is not None:
            QDesktopServices.openUrl(QUrl(YOUTUBE_SEARCH + quote_plus(self._concept.youtube_query)))
