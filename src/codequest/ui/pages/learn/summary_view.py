"""Resumen al terminar una ronda: puntuación y conceptos para repasar."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from codequest.core.games.base import GameSession, Outcome
from codequest.ui.formatting import inline_code_html
from codequest.ui.icons import icon, icon_label
from codequest.ui.theme import current_palette
from codequest.ui.widgets import Card, heading, muted, section_title


def _message(ratio: float) -> str:
    if ratio == 1:
        return "¡Ronda perfecta! Conoces muy bien esta parte de tu proyecto."
    if ratio >= 0.7:
        return "¡Muy bien! Repasa los conceptos de abajo y estarás al 100 %."
    if ratio >= 0.4:
        return "Vas por buen camino. Los conceptos de abajo son los que más conviene repasar."
    return ("Cada pregunta que no sabías es algo nuevo que ya aprendiste. "
            "Repasa las explicaciones y vuelve a intentarlo.")


class SummaryView(QWidget):
    play_again = Signal()
    go_home = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        card = Card(variant="hero", padding=28)
        card.body.setSpacing(8)
        card.body.addWidget(icon_label("trophy", size=36, color=current_palette().warning))
        card.body.addWidget(heading("Ronda terminada"))
        self._score = QLabel()
        self._score.setObjectName("ScoreValue")
        card.body.addWidget(self._score)
        self._message = muted("")
        card.body.addWidget(self._message)

        buttons = QHBoxLayout()
        again = QPushButton("Otra ronda")
        again.setIcon(icon("replay", color="#ffffff", color_on="#ffffff"))
        again.setIconSize(QSize(18, 18))
        again.setProperty("variant", "primary")
        again.clicked.connect(self.play_again)
        home = QPushButton("Volver al inicio")
        home.setIcon(icon("home"))
        home.clicked.connect(self.go_home)
        buttons.addWidget(again)
        buttons.addWidget(home)
        buttons.addStretch(1)
        card.body.addSpacing(8)
        card.body.addLayout(buttons)
        layout.addWidget(card)

        self._review_title = section_title("Para repasar")
        layout.addWidget(self._review_title)
        self._review = QVBoxLayout()
        self._review.setSpacing(8)
        review_holder = QWidget()
        review_holder.setLayout(self._review)
        self._review.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(review_holder)

    def show_session(self, session: GameSession) -> None:
        total = max(session.total, 1)
        self._score.setText(f"{session.correct_count} / {session.total}")
        self._message.setText(_message(session.correct_count / total))

        while (item := self._review.takeAt(0)) is not None:
            if widget := item.widget():
                widget.hide()
                widget.deleteLater()
        to_review = session.to_review()
        self._review_title.setVisible(bool(to_review))
        for evaluation in to_review:
            concept = evaluation.question.concept
            row = Card(padding=14)
            head = QHBoxLayout()
            skipped = evaluation.outcome is Outcome.SKIPPED
            palette = current_palette()
            head.addWidget(icon_label("explain" if skipped else "incorrect", size=18,
                                      color=palette.syntax_annotation if skipped else palette.danger))
            title = QLabel(inline_code_html(f"`{concept.title}` · {concept.topic.value}"))
            title.setTextFormat(Qt.TextFormat.RichText)
            head.addWidget(title, 1)
            row.body.addLayout(head)
            row.body.addWidget(muted(concept.summary))
            self._review.addWidget(row)
