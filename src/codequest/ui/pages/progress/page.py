"""Página "Progreso": dominio del proyecto, por tema, lo que conviene repasar y el historial."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from codequest.app.context import AppContext
from codequest.core.analysis.model import ProjectModel
from codequest.core.persistence.progress import MASTERY_WINDOW, SessionSummary
from codequest.services.progress_service import ProgressOverview
from codequest.ui.formatting import inline_code_html, plural, session_date
from codequest.ui.icons import icon
from codequest.ui.pages.base import Page
from codequest.ui.widgets import Card, Meter, StatTile, heading, muted, section_title


class ProgressPage(Page):
    start_requested = Signal()
    review_requested = Signal(object)  # frozenset[str] de ids de concepto

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._supported = True
        self._project_name = ""
        self.layout_.addWidget(heading("Progreso"))
        self._subtitle = muted("")
        self.layout_.addWidget(self._subtitle)

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(16)
        self.layout_.addWidget(self._content)
        self._show_message("Analizando tu proyecto…")

    # --- datos ----------------------------------------------------------------

    def set_context(self, context: AppContext) -> None:
        self._supported = context.project.is_supported
        self._project_name = context.project.name
        self._subtitle.setText(f"Cómo vas con {self._project_name}.")

    def set_model(self, model: ProjectModel | None) -> None:
        if model is None:
            self._show_message("Analizando tu proyecto…" if self._supported
                               else "El progreso está disponible para proyectos Java.")

    def set_overview(self, overview: ProgressOverview, sessions: list[SessionSummary],
                     saving_error: str | None = None) -> None:
        self._clear()
        if saving_error:
            self._content_layout.addWidget(muted(f"No se puede guardar tu progreso ({saving_error})."))
        if not overview.has_history:
            self._add_empty()
            self.content_changed()
            return
        self._add_hero(overview)
        self._add_kpis(overview)
        self._add_topics(overview)
        if overview.weak:
            self._add_review(overview)
        if sessions:
            self._add_history(sessions)
        self.content_changed()

    # --- secciones --------------------------------------------------------------

    def _add_hero(self, overview: ProgressOverview) -> None:
        card = Card(variant="hero", padding=24)
        card.body.setSpacing(4)
        value = QLabel(f"{overview.percent} %")
        value.setObjectName("HeroValue")
        card.body.addWidget(value)
        card.body.addWidget(muted(f"de dominio en {self._project_name}"))
        card.body.addSpacing(6)
        card.body.addWidget(muted(f"Dominas un concepto cuando aciertas sus últimas {MASTERY_WINDOW} preguntas. "
                                  "El porcentaje es la media de todos los conceptos que usa tu proyecto."))
        self._content_layout.addWidget(card)

    def _add_kpis(self, overview: ProgressOverview) -> None:
        history = overview.history
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        for label, value in (
            ("Conceptos dominados", f"{overview.mastered} / {overview.total}"),
            ("Conceptos practicados", f"{overview.practiced} / {overview.total}"),
            ("Respuestas", str(history.attempts)),
            ("Aciertos", f"{round(100 * history.accuracy)} %"),
        ):
            layout.addWidget(StatTile(label, value))
        self._content_layout.addWidget(row)

    def _add_topics(self, overview: ProgressOverview) -> None:
        self._content_layout.addWidget(section_title("Dominio por tema"))
        card = Card(padding=20)
        card.body.setSpacing(16)
        for topic in overview.topics:
            detail = f"{topic.mastered} de {plural(topic.total, 'concepto dominado', 'conceptos dominados')}"
            card.body.addWidget(Meter(
                topic.topic.label, topic.percent, detail=detail,
                tooltip=f"{topic.topic.label}: dominio medio del {topic.percent} % en "
                        f"{plural(topic.total, 'concepto', 'conceptos')} de tu proyecto",
            ))
        self._content_layout.addWidget(card)

    def _add_review(self, overview: ProgressOverview) -> None:
        self._content_layout.addWidget(section_title("Para repasar"))
        card = Card(padding=18)
        names = ", ".join(f"`{c.title}`" for c in overview.weak)
        text = QLabel(inline_code_html(f"La última vez fallaste o no sabías: {names}."))
        text.setWordWrap(True)
        text.setTextFormat(Qt.TextFormat.RichText)
        row = QHBoxLayout()
        row.addWidget(text, 1)
        review = QPushButton(f"Repasar lo que me cuesta ({len(overview.weak)})")
        review.setIcon(icon("replay", color="#ffffff", color_on="#ffffff"))
        review.setIconSize(QSize(18, 18))
        review.setProperty("variant", "primary")
        ids = frozenset(c.id for c in overview.weak)
        review.clicked.connect(lambda: self.review_requested.emit(ids))
        row.addWidget(review, 0, Qt.AlignmentFlag.AlignVCenter)
        card.body.addLayout(row)
        self._content_layout.addWidget(card)

    def _add_history(self, sessions: list[SessionSummary]) -> None:
        self._content_layout.addWidget(section_title("Últimas sesiones"))
        card = Card(padding=18)
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        grid.setVerticalSpacing(10)
        for column, title in enumerate(("FECHA", "PRÁCTICA", "RESULTADO")):
            header = QLabel(title)
            header.setObjectName("TableHeader")
            if column == 2:  # los resultados son números: alineados a la derecha, igual que su columna
                header.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(header, 0, column)
        for row, session in enumerate(sessions, start=1):
            scope = session.scope.rsplit(".", 1)[-1] if session.scope else "Todo el proyecto"
            percent = round(100 * session.correct / session.answered) if session.answered else 0
            grid.addWidget(QLabel(session_date(session.started_at)), row, 0)
            grid.addWidget(QLabel(f"Alternativas · {scope}"), row, 1)
            result = QLabel(f"{session.correct} de {session.answered} · {percent} %")
            result.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            grid.addWidget(result, row, 2)
        grid.setColumnStretch(1, 1)
        card.body.addLayout(grid)
        self._content_layout.addWidget(card)

    def _add_empty(self) -> None:
        card = Card(padding=40)
        card.body.setSpacing(12)
        title = QLabel("Todavía no has practicado este proyecto")
        title.setProperty("role", "h2")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = muted("Responde una ronda y aquí verás tu dominio por tema, lo que conviene repasar y tu historial.")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        start = QPushButton("Empezar a aprender")
        start.setIcon(icon("play", color="#ffffff", color_on="#ffffff"))
        start.setProperty("variant", "primary")
        start.clicked.connect(self.start_requested)
        card.body.addWidget(title)
        card.body.addWidget(hint)
        card.body.addWidget(start, 0, Qt.AlignmentFlag.AlignHCenter)
        self._content_layout.addWidget(card)

    def _show_message(self, text: str) -> None:
        self._clear()
        self._content_layout.addWidget(muted(text))
        self.content_changed()

    def _clear(self) -> None:
        while (item := self._content_layout.takeAt(0)) is not None:
            if widget := item.widget():
                widget.hide()
                widget.deleteLater()
