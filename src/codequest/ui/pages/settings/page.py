"""Página "Configuración": IA, privacidad y datos locales."""

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QCheckBox, QComboBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QWidget

from codequest import __version__
from codequest.app.constants import APP_NAME
from codequest.app.context import AppContext
from codequest.core.settings import Settings
from codequest.ui.formatting import ai_detail, ai_indicator, inline_code_html
from codequest.ui.icons import icon
from codequest.ui.pages.base import Page
from codequest.ui.theme import current_palette
from codequest.ui.widgets import Card, IconText, StatusIndicator, heading, mono, muted, section_title
from codequest.ui.widgets.style_utils import repolish

PRIVACY_LINES = (
    "**Completar con IA** envía el nombre y el import de cada elemento (p. ej. `lombok.Data`). Nunca código.",
    "**Explícamelo con mi código** envía el fragmento de la pregunta y solo las firmas de las clases "
    "relacionadas, y te pide confirmación la primera vez.",
    "La API key se lee de `ANTHROPIC_API_KEY`: CodeQuest nunca la muestra, la guarda ni la registra.",
    "Tu progreso y tus conceptos se guardan solo en este equipo. CodeQuest nunca escribe en tu proyecto.",
)


@dataclass(frozen=True, slots=True)
class DataPaths:
    database: Path | None
    knowledge: Path | None
    logs: Path | None
    settings: Path | None


def _bold_html(text: str) -> str:
    """`**negrita**` + `código` -> HTML."""
    parts = text.split("**")
    return "".join(f"<b>{inline_code_html(p)}</b>" if i % 2 else inline_code_html(p) for i, p in enumerate(parts))


class SettingsPage(Page):
    ai_enabled_changed = Signal(bool)
    ai_model_changed = Signal(object)  # str | None
    reset_progress_requested = Signal()

    def __init__(self, models: tuple[tuple[str, str, str], ...], paths: DataPaths,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._updating = False
        self.layout_.addWidget(heading("Configuración"))
        self.layout_.addWidget(muted("IA, privacidad y los datos que CodeQuest guarda en este equipo."))

        self.layout_.addWidget(section_title("Asistente de IA"))
        self.layout_.addWidget(self._build_ai_card(models))
        self.layout_.addWidget(section_title("Privacidad"))
        self.layout_.addWidget(self._build_privacy_card())
        self.layout_.addWidget(section_title("Tus datos"))
        self.layout_.addWidget(self._build_data_card(paths))
        self.layout_.addWidget(section_title("Acerca de"))
        about = Card(padding=16)
        about_text = f"{APP_NAME} {__version__} · Aprende el proyecto que tú mismo construiste."
        about.body.addWidget(IconText("info", about_text, role="body"))
        self.layout_.addWidget(about)

    # --- construcción -------------------------------------------------------

    def _build_ai_card(self, models: tuple[tuple[str, str, str], ...]) -> Card:
        card = Card(padding=20)
        card.body.setSpacing(12)
        self._ai_status = StatusIndicator()
        self._ai_detail = muted("")
        card.body.addWidget(self._ai_status)
        card.body.addWidget(self._ai_detail)

        self._ai_toggle = QCheckBox("Usar IA en CodeQuest")
        self._ai_toggle.toggled.connect(self._on_toggle)
        card.body.addWidget(self._ai_toggle)

        row = QHBoxLayout()
        row.addWidget(QLabel("Modelo"))
        self._model = QComboBox()
        for model_id, name, description in models:
            self._model.addItem(name, model_id)
            self._model.setItemData(self._model.count() - 1, description, Qt.ItemDataRole.ToolTipRole)
        self._model.currentIndexChanged.connect(self._on_model)
        row.addWidget(self._model)
        self._model_hint = muted("", word_wrap=False)
        row.addWidget(self._model_hint, 1)
        card.body.addLayout(row)
        self._env_note = muted("")
        card.body.addWidget(self._env_note)
        return card

    def _build_privacy_card(self) -> Card:
        card = Card(padding=20)
        card.body.setSpacing(10)
        color = current_palette().syntax_annotation
        for line in PRIVACY_LINES:
            item = IconText("privacy", _bold_html(line), color=color, role="body")
            item.label.setTextFormat(Qt.TextFormat.RichText)
            card.body.addWidget(item)
        return card

    def _build_data_card(self, paths: DataPaths) -> Card:
        card = Card(padding=20)
        card.body.setSpacing(16)
        self._knowledge_summary = muted("", word_wrap=False)
        for icon_name, title, path, summary in (
            ("database", "Progreso", paths.database, None),
            ("book", "Conceptos locales", paths.knowledge, self._knowledge_summary),
            ("logs", "Registro (logs)", paths.logs, None),
        ):
            if path is not None:
                card.body.addWidget(self._path_row(icon_name, title, path, summary))

        danger = QHBoxLayout()
        self._reset_hint = muted("")
        danger.addWidget(self._reset_hint, 1)
        self._reset = QPushButton("Borrar el progreso de este proyecto")
        self._reset.setIcon(icon("delete", color=current_palette().danger))
        self._reset.setProperty("variant", "danger")
        self._reset.clicked.connect(self.reset_progress_requested)
        danger.addWidget(self._reset)
        card.body.addSpacing(4)
        card.body.addLayout(danger)
        return card

    def _path_row(self, icon_name: str, title: str, path: Path, summary: QLabel | None) -> QWidget:
        """Dos líneas: título (+ resumen) y la ruta debajo; el botón Abrir a la derecha."""
        row = QWidget()
        grid = QGridLayout(row)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(2)
        head = QHBoxLayout()
        head.setSpacing(8)
        head.addWidget(IconText(icon_name, f"<b>{title}</b>", role="body"))
        if summary is not None:
            head.addWidget(summary)
        head.addStretch(1)
        grid.addLayout(head, 0, 0)
        location = mono(str(path))
        location.setToolTip(str(path))
        location.setIndent(28)  # alineada con el texto, no con el icono
        grid.addWidget(location, 1, 0)
        open_button = QPushButton("Abrir")
        open_button.setIcon(icon("folder-open"))
        open_button.setProperty("variant", "ghost")
        folder = path if path.suffix == "" else path.parent
        open_button.clicked.connect(lambda: self._open(folder))
        grid.addWidget(open_button, 0, 1, 2, 1, Qt.AlignmentFlag.AlignVCenter)
        grid.setColumnStretch(0, 1)
        return row

    # --- datos ----------------------------------------------------------------

    def set_state(self, context: AppContext, settings: Settings, effective_model: str | None,
                  env_model: str | None, knowledge_counts: tuple[int, int], progress_error: str | None) -> None:
        self._updating = True
        text, state = ai_indicator(context.ai, context.ai_enabled)
        self._ai_status.set_status(text, state)
        self._ai_detail.setText(ai_detail(context.ai, context.ai_enabled))
        self._ai_toggle.setEnabled(context.ai.available)
        self._ai_toggle.setChecked(context.ai.available and settings.ai_enabled)
        self._ai_toggle.setToolTip("" if context.ai.available else context.ai.detail)

        index = self._model.findData(effective_model)
        self._model.setCurrentIndex(max(index, 0))
        self._model.setEnabled(context.ai_active and env_model is None)
        description = self._model.itemData(self._model.currentIndex(), Qt.ItemDataRole.ToolTipRole)
        self._model_hint.setText(description or "")
        if env_model:
            self._env_note.setText(inline_code_html(
                f"`CODEQUEST_AI_MODEL={env_model}` está definida y tiene prioridad sobre esta elección."))
            self._env_note.setTextFormat(Qt.TextFormat.RichText)
        self._env_note.setVisible(bool(env_model))

        user, ai = knowledge_counts
        self._knowledge_summary.setText(f"{user} tuyos · {ai} generados con IA")
        supported = context.project.is_supported
        self._reset.setEnabled(supported and progress_error is None)
        self._reset_hint.setText(
            f"No se puede borrar: {progress_error}" if progress_error else
            f"Borra las respuestas y el dominio de {context.project.name}. Los demás proyectos no se tocan."
        )
        repolish(self._reset)
        self._updating = False
        self.content_changed()

    def _on_toggle(self, checked: bool) -> None:
        if not self._updating:
            self.ai_enabled_changed.emit(checked)

    def _on_model(self, _index: int) -> None:
        if not self._updating:
            self.ai_model_changed.emit(self._model.currentData())

    @staticmethod
    def _open(folder: Path) -> None:
        # Carpetas de datos de CodeQuest (no del proyecto): crearlas vacías es seguro.
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
