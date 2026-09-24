"""Pantalla de inicio: resumen del proyecto, estado de la IA y modos de juego."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from codequest.app.context import AppContext
from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.roles import ComponentRole
from codequest.core.knowledge.coverage import KnowledgeReport
from codequest.services.progress_service import ProgressOverview
from codequest.ui.formatting import ai_detail, ai_indicator, duration, inline_code_html, plural, role_count
from codequest.ui.icons import icon
from codequest.ui.pages.base import Page
from codequest.ui.theme import current_palette
from codequest.ui.widgets import (
    Card,
    Chip,
    IconText,
    ModeGrid,
    StatTile,
    StatusIndicator,
    heading,
    mono,
    muted,
    section_title,
)

# Roles con tarjeta propia; el resto se muestra como chips ("4 Enums", "2 DTOs"...).
STAT_ROLES: tuple[tuple[ComponentRole, str], ...] = (
    (ComponentRole.ENTITY, "Entities"),
    (ComponentRole.CONTROLLER, "Controllers"),
    (ComponentRole.SERVICE, "Services"),
    (ComponentRole.REPOSITORY, "Repositories"),
)
EXTRA_ROLES: tuple[ComponentRole, ...] = (
    ComponentRole.DTO, ComponentRole.ENUM, ComponentRole.EXCEPTION, ComponentRole.CONFIGURATION,
    ComponentRole.UTILITY, ComponentRole.MAPPER, ComponentRole.COMPONENT, ComponentRole.ANNOTATION,
)


class DashboardPage(Page):
    change_project_requested = Signal()
    concepts_requested = Signal()
    mode_selected = Signal(str)
    continue_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._greeting = heading("Exploremos tu proyecto")
        self.layout_.addWidget(self._greeting)

        self._warning_card = self._build_warning_card()
        self.layout_.addWidget(self._warning_card)
        self.layout_.addWidget(self._build_hero())

        self.layout_.addSpacing(8)
        self.layout_.addWidget(section_title("Tu proyecto en números"))
        self._analysis_bar = QProgressBar()
        self._analysis_bar.hide()
        self.layout_.addWidget(self._analysis_bar)
        self.layout_.addLayout(self._build_stats())
        self._extras = QWidget()
        self._extras_row = QHBoxLayout(self._extras)
        self._extras_row.setContentsMargins(0, 0, 0, 0)
        self._extras_row.setSpacing(6)
        self._extras.hide()
        self.layout_.addWidget(self._extras)
        self._analysis_status = muted("")
        self.layout_.addWidget(self._analysis_status)
        self._knowledge = self._build_knowledge_card()
        self.layout_.addWidget(self._knowledge)

        self.layout_.addSpacing(8)
        self.layout_.addWidget(section_title("Asistente de IA"))
        self.layout_.addWidget(self._build_ai_card())

        self.layout_.addSpacing(8)
        self.layout_.addWidget(section_title("Modos de juego"))
        modes = ModeGrid()
        modes.mode_selected.connect(self.mode_selected)
        self.layout_.addWidget(modes)

    # --- construcción -------------------------------------------------------

    def _build_warning_card(self) -> Card:
        card = Card(variant="warning", padding=16)
        self._warning_text = IconText("warning", color=current_palette().warning, role="body")
        card.body.addWidget(self._warning_text)
        card.hide()
        return card

    def _build_hero(self) -> Card:
        card = Card(variant="hero", padding=28)
        card.body.setSpacing(12)

        top = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(8)
        self._project_name = heading("", level=1, word_wrap=False)
        self._chips = QHBoxLayout()
        self._chips.setSpacing(6)
        self._project_path = mono("")
        title_box.addWidget(self._project_name)
        title_box.addLayout(self._chips)
        title_box.addWidget(self._project_path)
        top.addLayout(title_box, 1)

        change = QPushButton("Cambiar proyecto")
        change.setIcon(icon("folder"))
        change.setProperty("variant", "ghost")
        change.clicked.connect(self.change_project_requested)
        top.addWidget(change, 0)
        card.body.addLayout(top)

        card.body.addSpacing(8)
        bottom = QHBoxLayout()
        progress_box = QVBoxLayout()
        progress_box.setSpacing(6)
        progress_box.addWidget(section_title("Progreso"))
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setValue(0)
        self._progress_label = muted("Todavía no has practicado este proyecto.")
        progress_box.addWidget(self._progress)
        progress_box.addWidget(self._progress_label)
        self._weak_label = QLabel()
        self._weak_label.setWordWrap(True)
        self._weak_label.setTextFormat(Qt.TextFormat.RichText)
        self._weak_label.hide()
        progress_box.addWidget(self._weak_label)
        bottom.addLayout(progress_box, 1)
        bottom.addSpacing(32)

        self._continue = QPushButton("Empezar a aprender")
        self._continue.setIcon(icon("play", color="#ffffff", color_on="#ffffff"))
        self._continue.setIconSize(QSize(18, 18))
        self._continue.setProperty("variant", "primary")
        self._continue.clicked.connect(self.continue_requested)
        bottom.addWidget(self._continue, 0)
        card.body.addLayout(bottom)
        return card

    def _build_stats(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setSpacing(12)
        self._files_tile = StatTile("Archivos")
        row.addWidget(self._files_tile)
        self._role_tiles: dict[ComponentRole, StatTile] = {}
        for role, label in STAT_ROLES:
            tile = StatTile(label)
            self._role_tiles[role] = tile
            row.addWidget(tile)
        return row

    def set_progress(self, overview: ProgressOverview, saving_error: str | None = None) -> None:
        history = overview.history
        self._progress.setValue(overview.percent)
        if history.has_history:
            self._greeting.setText("Volvamos a tu proyecto")
            self._continue.setText("Continuar aprendiendo")
            self._progress_label.setText(
                f"{overview.percent} % · Dominas {overview.mastered} de {overview.total} conceptos · "
                f"{plural(history.attempts, 'respuesta', 'respuestas')} · "
                f"{round(100 * history.accuracy)} % de aciertos"
            )
        else:
            self._greeting.setText("Exploremos tu proyecto")
            self._continue.setText("Empezar a aprender")
            self._progress_label.setText("Todavía no has practicado este proyecto.")
        if saving_error:
            self._progress_label.setText(f"No se puede guardar tu progreso ({saving_error}). Puedes seguir "
                                         "practicando, pero no se recordará.")
        if overview.weak:
            names = ", ".join(f"`{c.title}`" for c in overview.weak)
            self._weak_label.setText(inline_code_html(f"Todavía te cuesta: {names}"))
        self._weak_label.setVisible(bool(overview.weak))
        self.content_changed()

    def _build_knowledge_card(self) -> Card:
        card = Card(padding=16)
        row = QHBoxLayout()
        self._knowledge_text = IconText("book", color=current_palette().syntax_annotation, role="body")
        row.addWidget(self._knowledge_text, 1)
        see = QPushButton("Ver conceptos")
        see.setIcon(icon("concepts"))
        see.setProperty("variant", "ghost")
        see.clicked.connect(self.concepts_requested)
        row.addWidget(see)
        card.body.addLayout(row)
        card.hide()
        return card

    def set_knowledge(self, report: KnowledgeReport) -> None:
        text = f"Conozco {report.known_count} de los {report.total_count} conceptos que usa tu proyecto."
        if report.gaps:
            names = ", ".join(g.display for g in report.gaps[:4]) + ("…" if len(report.gaps) > 4 else "")
            text += f" Todavía no sé explicarte: {names}"
        self._knowledge_text.set_text(text)
        self._knowledge.setVisible(report.total_count > 0)
        self.content_changed()

    def _build_ai_card(self) -> Card:
        card = Card(padding=18)
        self._ai_indicator = StatusIndicator()
        self._ai_detail = muted("")
        privacy = IconText("local", "Tu código se procesa localmente. Solo se enviarán fragmentos a la IA "
                                    "cuando un ejercicio lo indique con la marca IA.")
        card.body.addWidget(self._ai_indicator)
        card.body.addWidget(self._ai_detail)
        card.body.addWidget(privacy)
        return card

    # --- datos ----------------------------------------------------------------

    def set_context(self, context: AppContext) -> None:
        project = context.project
        self._project_name.setText(project.name)
        self._project_path.setText(str(project.root))
        self._project_path.setToolTip(str(project.root))

        while (item := self._chips.takeAt(0)) is not None:
            if widget := item.widget():
                widget.hide()
                widget.deleteLater()
        stack = project.stack or ("Tipo de proyecto desconocido",)
        for index, label in enumerate(stack):
            self._chips.addWidget(Chip(label, tone="accent" if index == 0 else None))
        self._chips.addStretch(1)

        if project.warnings:
            prefix = ("Este directorio no parece un proyecto de código." if not project.is_code_project
                      else "Algunas cosas no se detectaron:")
            self._warning_text.set_text(prefix + "\n" + "\n".join(f"• {w}" for w in project.warnings))
            self._warning_card.show()
        else:
            self._warning_card.hide()

        self._continue.setEnabled(project.is_supported)
        self._continue.setToolTip("" if project.is_supported else "El MVP soporta proyectos Java.")

        text, state = ai_indicator(context.ai, context.ai_enabled)
        self._ai_indicator.set_status(text, state)
        self._ai_detail.setText(ai_detail(context.ai, context.ai_enabled))

    # --- análisis -------------------------------------------------------------

    def show_analysis_started(self) -> None:
        self._reset_stats()
        self._analysis_bar.setRange(0, 0)  # indeterminada hasta conocer el total
        self._analysis_bar.show()
        self._analysis_status.setText("Analizando tu proyecto…")

    def show_analysis_progress(self, done: int, total: int) -> None:
        self._analysis_bar.setRange(0, max(total, 1))
        self._analysis_bar.setValue(done)
        self._analysis_status.setText(f"Analizando tu proyecto… {done} de {total} archivos")

    def show_analysis_failed(self, message: str) -> None:
        self._analysis_bar.hide()
        self._analysis_status.setText(f"No se pudo analizar el proyecto: {message}")

    def show_analysis_unavailable(self) -> None:
        self._reset_stats()
        self._analysis_bar.hide()
        self._analysis_status.setText("El análisis de código está disponible para proyectos Java.")

    def set_model(self, model: ProjectModel | None) -> None:
        if model is None:
            return
        self._analysis_bar.hide()
        counts = model.role_counts()
        self._files_tile.set_value(len(model.files))
        for role, tile in self._role_tiles.items():
            tile.set_value(counts[role])

        self._clear_extras()
        extras = [(role, counts[role]) for role in EXTRA_ROLES if counts[role]]
        if extras:
            self._extras_row.addWidget(muted("También encontré:", word_wrap=False))
            for role, count in extras:
                self._extras_row.addWidget(Chip(role_count(role, count)))
            self._extras_row.addStretch(1)
        self._extras.setVisible(bool(extras))

        parts = [
            plural(len(model.main_classes), "clase analizada", "clases analizadas"),
            f"en {duration(model.duration_seconds)}",
        ]
        if model.errors:
            parts.append(plural(len(model.errors), "archivo no se pudo leer", "archivos no se pudieron leer"))
        if model.truncated:
            parts.append("el proyecto es muy grande y se analizó parcialmente")
        self._analysis_status.setText(" · ".join(parts))
        self.content_changed()

    def _reset_stats(self) -> None:
        self._knowledge.hide()
        self._files_tile.set_value("—")
        for tile in self._role_tiles.values():
            tile.set_value("—")
        self._clear_extras()
        self._extras.hide()

    def _clear_extras(self) -> None:
        while (item := self._extras_row.takeAt(0)) is not None:
            if widget := item.widget():
                widget.hide()
                widget.deleteLater()
