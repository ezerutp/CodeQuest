"""Pantalla de inicio: resumen del proyecto, estado de la IA y modos de juego."""

from dataclasses import dataclass

from PySide6.QtCore import QSize, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QProgressBar, QPushButton, QVBoxLayout, QWidget

from codequest.app.context import AppContext
from codequest.ui.formatting import ai_indicator
from codequest.ui.icons import icon
from codequest.ui.pages.base import Page
from codequest.ui.theme import current_palette
from codequest.ui.widgets import (
    Card,
    Chip,
    IconText,
    ModeCard,
    StatTile,
    StatusIndicator,
    heading,
    mono,
    muted,
    section_title,
)


@dataclass(frozen=True, slots=True)
class ModeInfo:
    key: str
    title: str
    description: str
    uses_ai: bool = False
    available: bool = False


GAME_MODES: tuple[ModeInfo, ...] = (
    ModeInfo("multiple_choice", "Alternativas", "Responde preguntas sobre tu propio código.", available=True),
    ModeInfo("explain_code", "Explícame este código", "Describe con tus palabras qué hace un fragmento.", uses_ai=True),
    ModeInfo("find_error", "Encuentra el error", "Descubre el error escondido en código real."),
    ModeInfo("fix_code", "Corrige el código", "Edita el fragmento hasta que funcione."),
    ModeInfo("comparison", "Comparaciones", "@Controller vs @RestController, Entity vs DTO…"),
    ModeInfo("random", "Desafío aleatorio", "No sabes qué ejercicio aparecerá."),
)

STAT_KEYS: tuple[tuple[str, str], ...] = (
    ("files", "Archivos"),
    ("entities", "Entities"),
    ("controllers", "Controllers"),
    ("services", "Services"),
    ("repositories", "Repositories"),
)


class DashboardPage(Page):
    change_project_requested = Signal()
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
        self.layout_.addLayout(self._build_stats())
        self._stats_note = muted("El análisis de clases se conectará en el siguiente incremento.")
        self.layout_.addWidget(self._stats_note)

        self.layout_.addSpacing(8)
        self.layout_.addWidget(section_title("Asistente de IA"))
        self.layout_.addWidget(self._build_ai_card())

        self.layout_.addSpacing(8)
        self.layout_.addWidget(section_title("Modos de juego"))
        self.layout_.addLayout(self._build_modes())

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
        self._stats: dict[str, StatTile] = {}
        for key, label in STAT_KEYS:
            tile = StatTile(label)
            self._stats[key] = tile
            row.addWidget(tile)
        return row

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

    def _build_modes(self) -> QGridLayout:
        grid = QGridLayout()
        grid.setSpacing(12)
        columns = 3
        for index, mode in enumerate(GAME_MODES):
            card = ModeCard(
                f"mode.{mode.key}", mode.title, mode.description,
                badge="IA" if mode.uses_ai else "Local",
                badge_icon="ai" if mode.uses_ai else "local",
                available=mode.available,
            )
            card.setMinimumHeight(130)
            card.clicked.connect(lambda key=mode.key: self.mode_selected.emit(key))
            grid.addWidget(card, index // columns, index % columns)
        for column in range(columns):
            grid.setColumnStretch(column, 1)
        return grid

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

        text, state = ai_indicator(context.ai)
        self._ai_indicator.set_status(text, state)
        self._ai_detail.setText(context.ai.detail)
