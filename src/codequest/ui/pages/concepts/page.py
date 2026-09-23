"""Página "Conceptos": qué sabe explicar CodeQuest de tu proyecto y qué no conoce aún."""

import logging
from pathlib import Path

from PySide6.QtCore import QSize, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout, QWidget

from codequest.app.context import AppContext
from codequest.core.analysis.model import ProjectModel
from codequest.core.knowledge.coverage import KnowledgeGap, KnowledgeReport
from codequest.core.knowledge.models import Concept, ConceptSource
from codequest.services.knowledge_service import GenerationResult, KnowledgeService
from codequest.ui.formatting import inline_code_html, plural
from codequest.ui.icons import icon
from codequest.ui.pages.base import Page
from codequest.ui.pages.concepts.concept_card import ConceptCard
from codequest.ui.theme import current_palette
from codequest.ui.widgets import Card, IconText, StatTile, heading, mono, muted, section_title

log = logging.getLogger(__name__)

PRIVACY_NOTE = ("Solo se enviará el nombre y el import de cada elemento (por ejemplo, `lombok.Data`). "
                "Nunca se envía código ni nombres de tu proyecto.")


class ConceptsPage(Page):
    generate_requested = Signal(object)  # tuple[KnowledgeGap, ...]
    delete_requested = Signal(str)  # id del concepto

    def __init__(self, knowledge: KnowledgeService, knowledge_dir: Path | None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._knowledge = knowledge
        self._knowledge_dir = knowledge_dir
        self._supported = True
        self._report: KnowledgeReport | None = None
        self._generating = False
        self._generate_button: QPushButton | None = None
        self._result: GenerationResult | None = None

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
            self._report = None
            self._result = None
            self._show_message("Analizando tu proyecto…" if self._supported
                               else "Los conceptos están disponibles para proyectos Java.")

    def set_report(self, report: KnowledgeReport) -> None:
        self._report = report
        self._rebuild()

    # --- generación con IA ----------------------------------------------------------

    def show_generation_started(self, total: int) -> None:
        self._generating = True
        self._result = None
        self.show_generation_progress(0, total)

    def show_generation_progress(self, done: int, total: int) -> None:
        if self._generate_button is not None:
            self._generate_button.setEnabled(False)
            self._generate_button.setText(f"Generando {min(done + 1, total)} de {total}…")

    def show_generation_result(self, result: GenerationResult | None, report: KnowledgeReport) -> None:
        """`result` None si la tarea falló por completo (el error ya se mostró)."""
        self._generating = False
        self._result = result
        self.set_report(report)

    # --- construcción -------------------------------------------------------------

    def _rebuild(self) -> None:
        report = self._report
        if report is None:
            return
        kb = self._knowledge.kb
        counts = kb.source_counts()
        self._used_tile.set_value(report.known_count)
        self._gaps_tile.set_value(len(report.gaps))
        self._kb_tile.set_value(len(kb.concepts))
        self._kb_tile.setToolTip(
            f"Integrados: {counts[ConceptSource.BUILTIN]} · Tuyos: {counts[ConceptSource.USER]} · "
            f"Generados con IA: {counts[ConceptSource.AI]}"
        )

        self._clear()
        if self._result is not None:
            self._add_result(self._result)
        if kb.issues:
            self._add_issues()
        if report.gaps:
            self._add_gaps(report.gaps)
        self._content_layout.addWidget(section_title("Conceptos de tu proyecto"))
        if report.used:
            for usage in report.used:
                deletable = usage.concept.source is ConceptSource.AI
                self._content_layout.addWidget(
                    ConceptCard(usage.concept, usage.usages, on_delete=self._confirm_delete if deletable else None)
                )
        else:
            self._content_layout.addWidget(muted("Tu proyecto no usa ninguno de los conceptos que conozco."))
        self.content_changed()

    def _add_gaps(self, gaps: tuple[KnowledgeGap, ...]) -> None:
        self._content_layout.addWidget(section_title("Aún no los conozco"))
        notice = Card(padding=16)
        notice.body.setSpacing(10)
        palette = current_palette()
        intro = (f"Tu proyecto usa {plural(len(gaps), 'elemento', 'elementos')} para los que todavía no tengo "
                 "explicación, así que no generan preguntas.")
        if self._knowledge.can_generate:
            notice.body.addWidget(IconText("gap", f"{intro} Puedo aprenderlos con {self._knowledge.provider_name}.",
                                           color=palette.syntax_annotation, role="body"))
            privacy = IconText("ai", inline_code_html(PRIVACY_NOTE), color=palette.syntax_annotation)
            privacy.label.setTextFormat(Qt.TextFormat.RichText)
            notice.body.addWidget(privacy)
            row = QHBoxLayout()
            row.addStretch(1)
            self._generate_button = QPushButton(f"Completar con IA ({len(gaps)})")
            self._generate_button.setIcon(icon("ai", color="#ffffff", color_on="#ffffff"))
            self._generate_button.setIconSize(QSize(18, 18))
            self._generate_button.setProperty("variant", "primary")
            self._generate_button.setEnabled(not self._generating)
            self._generate_button.clicked.connect(lambda: self._confirm_generate(gaps))
            row.addWidget(self._generate_button)
            notice.body.addLayout(row)
        else:
            self._generate_button = None
            notice.body.addWidget(IconText(
                "gap", f"{intro} Si defines ANTHROPIC_API_KEY podré aprenderlos con IA. Mientras tanto puedes "
                       "añadir tus propios conceptos en YAML en esta carpeta:",
                color=palette.syntax_annotation, role="body",
            ))
        if self._knowledge_dir is not None:
            notice.body.addLayout(self._folder_row())
        self._content_layout.addWidget(notice)
        for gap in gaps:
            self._content_layout.addWidget(self._gap_card(gap))

    def _folder_row(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addWidget(mono(str(self._knowledge_dir)))
        row.addStretch(1)
        open_dir = QPushButton("Abrir carpeta")
        open_dir.setIcon(icon("folder-open"))
        open_dir.setProperty("variant", "ghost")
        open_dir.clicked.connect(self._open_knowledge_dir)
        row.addWidget(open_dir)
        return row

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

    def _add_result(self, result: GenerationResult) -> None:
        palette = current_palette()
        if result.created:
            titles = ", ".join(c.title for c in result.created)
            card = Card(variant="success", padding=16)
            card.body.addWidget(IconText(
                "correct", f"Aprendí {plural(len(result.created), 'concepto nuevo', 'conceptos nuevos')}: {titles}. "
                           "Ya aparecen en tus rondas de práctica.",
                color=palette.success, role="body",
            ))
            self._content_layout.addWidget(card)
        if result.failed:
            lines = "\n".join(f"• {gap.display}: {message}" for gap, message in result.failed)
            card = Card(variant="warning", padding=16)
            card.body.addWidget(IconText("warning", f"No pude generar algunos conceptos:\n{lines}",
                                         color=palette.warning, role="body"))
            self._content_layout.addWidget(card)

    def _add_issues(self) -> None:
        card = Card(variant="warning", padding=16)
        lines = "\n".join(f"• {issue.location}: {issue.message}" for issue in self._knowledge.kb.issues)
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
        self._generate_button = None
        while (item := self._content_layout.takeAt(0)) is not None:
            if widget := item.widget():
                widget.hide()
                widget.deleteLater()

    # --- acciones -------------------------------------------------------------------

    def _confirm_generate(self, gaps: tuple[KnowledgeGap, ...]) -> None:
        preview = "\n".join(f"• {line}" for line in KnowledgeService.privacy_preview(gaps))
        answer = QMessageBox.question(
            self, "Completar con IA",
            f"Se enviará a {self._knowledge.provider_name} esta información para generar "
            f"{plural(len(gaps), 'concepto', 'conceptos')}:\n\n{preview}\n\n"
            "No se envía código ni nombres de tu proyecto. Los conceptos generados se guardan en tu "
            "carpeta local y se reutilizan sin volver a llamar a la IA.\n\n¿Continuar?",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.generate_requested.emit(gaps)

    def _confirm_delete(self, concept: Concept) -> None:
        answer = QMessageBox.question(
            self, "Borrar concepto",
            f"¿Borrar {concept.title} de tu carpeta local? Volverá a aparecer como pendiente y podrás "
            "generarlo otra vez con IA.",
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.delete_requested.emit(concept.id)

    def _open_knowledge_dir(self) -> None:
        # Carpeta de datos de CodeQuest (no del proyecto): crearla vacía es seguro.
        try:
            self._knowledge_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            log.warning("No se pudo crear %s: %s", self._knowledge_dir, exc)
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._knowledge_dir)))
