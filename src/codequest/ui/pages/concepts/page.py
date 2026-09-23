"""Página "Conceptos": qué sabe explicar CodeQuest de tu proyecto y qué no conoce aún."""

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from codequest.app.context import AppContext
from codequest.core.analysis.model import ProjectModel
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.knowledge.coverage import KnowledgeGap, KnowledgeReport
from codequest.core.knowledge.models import ConceptSource
from codequest.ui.formatting import inline_code_html, plural
from codequest.ui.icons import icon
from codequest.ui.pages.base import Page
from codequest.ui.pages.concepts.concept_card import ConceptCard
from codequest.ui.theme import current_palette
from codequest.ui.widgets import Card, IconText, StatTile, heading, mono, muted, section_title

log = logging.getLogger(__name__)


class ConceptsPage(Page):
    def __init__(self, kb: KnowledgeBase, knowledge_dir: Path | None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._kb = kb
        self._knowledge_dir = knowledge_dir
        self._supported = True

        self.layout_.addWidget(heading("Conceptos"))
        self.layout_.addWidget(muted("Lo que CodeQuest sabe explicarte de tu proyecto, y lo que todavía no."))

        stats = QHBoxLayout()
        stats.setSpacing(12)
        self._used_tile = StatTile("Conceptos que usa tu proyecto")
        self._gaps_tile = StatTile("Aún no los conozco")
        self._kb_tile = StatTile("En la base de conocimiento")
        for tile in (self._used_tile, self._gaps_tile, self._kb_tile):
            stats.addWidget(tile)
        self.layout_.addLayout(stats)

        # Contenido que depende del análisis: se reconstruye en cada informe.
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(12)
        self.layout_.addWidget(self._content)
        self._show_message("Analizando tu proyecto…")

    # --- datos ----------------------------------------------------------------

    def set_context(self, context: AppContext) -> None:
        self._supported = context.project.is_supported

    def set_model(self, model: ProjectModel | None) -> None:
        if model is None:
            self._show_message("Analizando tu proyecto…" if self._supported
                               else "Los conceptos están disponibles para proyectos Java.")

    def set_report(self, report: KnowledgeReport) -> None:
        counts = self._kb.source_counts()
        self._used_tile.set_value(report.known_count)
        self._gaps_tile.set_value(len(report.gaps))
        self._kb_tile.set_value(len(self._kb.concepts))
        self._kb_tile.setToolTip(
            f"Integrados: {counts[ConceptSource.BUILTIN]} · Tuyos: {counts[ConceptSource.USER]} · "
            f"Generados con IA: {counts[ConceptSource.AI]}"
        )

        self._clear()
        if self._kb.issues:
            self._add_issues()
        if report.gaps:
            self._add_gaps(report.gaps)
        self._content_layout.addWidget(section_title("Conceptos de tu proyecto"))
        if report.used:
            for usage in report.used:
                self._content_layout.addWidget(ConceptCard(usage.concept, usage.usages))
        else:
            self._content_layout.addWidget(muted("Tu proyecto no usa ninguno de los conceptos que conozco."))
        self.content_changed()

    # --- secciones --------------------------------------------------------------

    def _add_gaps(self, gaps: tuple[KnowledgeGap, ...]) -> None:
        self._content_layout.addWidget(section_title("Aún no los conozco"))
        notice = Card(padding=16)
        notice.body.addWidget(IconText(
            "gap",
            f"Tu proyecto usa {plural(len(gaps), 'elemento', 'elementos')} para los que todavía no tengo "
            "explicación, así que no generan preguntas. Pronto podré aprenderlos con IA; mientras tanto "
            "puedes añadir tus propios conceptos en YAML.",
            color=current_palette().syntax_annotation, role="body",
        ))
        if self._knowledge_dir is not None:
            row = QHBoxLayout()
            row.addWidget(mono(str(self._knowledge_dir)))
            row.addStretch(1)
            open_dir = QPushButton("Abrir carpeta")
            open_dir.setIcon(icon("folder-open"))
            open_dir.setProperty("variant", "ghost")
            open_dir.clicked.connect(self._open_knowledge_dir)
            row.addWidget(open_dir)
            notice.body.addLayout(row)
        self._content_layout.addWidget(notice)
        for gap in gaps:
            self._content_layout.addWidget(self._gap_card(gap))

    def _gap_card(self, gap: KnowledgeGap) -> Card:
        card = Card(padding=14)
        card.body.setSpacing(4)
        head = QHBoxLayout()
        title = QLabel(inline_code_html(f"`{gap.display}`"))
        title.setTextFormat(Qt.TextFormat.RichText)
        head.addWidget(title)
        if gap.qualified_name:
            head.addWidget(mono(gap.qualified_name))
        head.addStretch(1)
        head.addWidget(muted(plural(gap.usages, "uso", "usos"), word_wrap=False))
        card.body.addLayout(head)
        where = ", ".join(name.rsplit(".", 1)[-1] for name in gap.classes)
        more = gap.usages > len(gap.classes)
        card.body.addWidget(muted(f"En {where}{'…' if more else ''}"))
        return card

    def _add_issues(self) -> None:
        card = Card(variant="warning", padding=16)
        lines = "\n".join(f"• {issue.location}: {issue.message}" for issue in self._kb.issues)
        card.body.addWidget(IconText("warning", f"Algunos conceptos de tu carpeta no se pudieron cargar:\n{lines}",
                                     color=current_palette().warning, role="body"))
        self._content_layout.addWidget(card)

    def _show_message(self, text: str) -> None:
        for tile in (self._used_tile, self._gaps_tile, self._kb_tile):
            tile.set_value("—")
        self._clear()
        self._content_layout.addWidget(muted(text))
        self.content_changed()

    def _clear(self) -> None:
        while (item := self._content_layout.takeAt(0)) is not None:
            if widget := item.widget():
                widget.hide()
                widget.deleteLater()

    def _open_knowledge_dir(self) -> None:
        # Carpeta de datos de CodeQuest (no del proyecto): crearla vacía es seguro.
        try:
            self._knowledge_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log.warning("No se pudo crear %s: %s", self._knowledge_dir, exc)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._knowledge_dir)))
