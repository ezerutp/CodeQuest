"""Tarjeta desplegable de un concepto: resumen siempre visible, explicación al hacer clic."""

from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from codequest.core.knowledge.models import Concept, ConceptSource
from codequest.ui.formatting import inline_code_html, plural
from codequest.ui.icons import icon
from codequest.ui.theme import current_palette
from codequest.ui.widgets import Card, Chip, ClickableCard, IconText, muted

SOURCE_LABELS = {ConceptSource.USER: "Añadido por ti", ConceptSource.AI: "Generado con IA"}
_CHEVRON_SIZE = 18


class ConceptCard(ClickableCard):
    def __init__(self, concept: Concept, usages: int, on_delete: Callable[[Concept], None] | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent, padding=16)
        self.body.setSpacing(6)
        self.setToolTip("Clic para ver la explicación")

        head = QHBoxLayout()
        head.setSpacing(8)
        title = QLabel(inline_code_html(f"`{concept.title}`"))
        title.setTextFormat(Qt.TextFormat.RichText)
        title.setProperty("role", "h2")
        head.addWidget(title)
        head.addWidget(Chip(concept.topic.label, tone="muted"))
        if concept.source in SOURCE_LABELS:
            head.addWidget(Chip(SOURCE_LABELS[concept.source], tone="accent",
                                icon="ai" if concept.source is ConceptSource.AI else "book"))
        head.addStretch(1)
        head.addWidget(muted(plural(usages, "uso", "usos"), word_wrap=False))
        self._chevron = QLabel()
        head.addWidget(self._chevron)
        self.body.addLayout(head)
        self.body.addWidget(muted(concept.summary))

        self._details = QWidget()
        details = QVBoxLayout(self._details)
        details.setContentsMargins(0, 6, 0, 0)
        details.setSpacing(8)
        for paragraph in (p.strip() for p in concept.explanation.split("\n\n") if p.strip()):
            label = QLabel(inline_code_html(paragraph))
            label.setWordWrap(True)
            label.setTextFormat(Qt.TextFormat.RichText)
            details.addWidget(label)
        analogy = Card(variant="analogy", padding=12)
        analogy.body.addWidget(IconText("analogy", concept.analogy, color=current_palette().syntax_annotation,
                                        role="body"))
        details.addWidget(analogy)
        if on_delete is not None:
            actions = QHBoxLayout()
            actions.addStretch(1)
            delete = QPushButton("Borrar este concepto")
            delete.setIcon(icon("delete"))
            delete.setProperty("variant", "ghost")
            delete.setToolTip("Lo quita de tu carpeta local. Podrás volver a generarlo con IA.")
            delete.clicked.connect(lambda: on_delete(concept))
            actions.addWidget(delete)
            details.addLayout(actions)
        self._details.hide()
        self.body.addWidget(self._details)

        self._update_chevron()
        self.clicked.connect(self._toggle)

    def _toggle(self) -> None:
        self._details.setVisible(self._details.isHidden())
        self._update_chevron()

    def _update_chevron(self) -> None:
        name = "chevron-down" if self._details.isHidden() else "chevron-up"
        self._chevron.setPixmap(icon(name).pixmap(_CHEVRON_SIZE, _CHEVRON_SIZE))
