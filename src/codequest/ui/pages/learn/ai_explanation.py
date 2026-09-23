"""Bloque "Explícamelo con mi código": pide a la IA una explicación sobre el código real."""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QWidget

from codequest.ui.formatting import inline_code_html
from codequest.ui.icons import icon
from codequest.ui.theme import current_palette
from codequest.ui.widgets import Card, IconText, muted


def paragraphs_html(text: str) -> str:
    return "".join(f"<p>{inline_code_html(p.strip())}</p>" for p in text.split("\n\n") if p.strip())


class AIExplanationBox(Card):
    requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent, variant="ai", padding=16)
        self.body.setSpacing(8)
        palette = current_palette()

        head = QHBoxLayout()
        head.addWidget(IconText("ai", "<b>Explícamelo con mi código</b>", color=palette.syntax_annotation,
                                role="body"), 1)
        self._button = QPushButton()
        self._button.setIcon(icon("ai", color="#ffffff", color_on="#ffffff"))
        self._button.setIconSize(QSize(16, 16))
        self._button.setProperty("variant", "primary")
        self._button.clicked.connect(self.requested)
        head.addWidget(self._button, 0, Qt.AlignmentFlag.AlignTop)
        self.body.addLayout(head)

        self._note = muted("")
        self.body.addWidget(self._note)
        self._answer = QLabel()
        self._answer.setObjectName("FeedbackBody")
        self._answer.setWordWrap(True)
        self._answer.setTextFormat(Qt.TextFormat.RichText)
        self._answer.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body.addWidget(self._answer)
        self._provider = "la IA"

    def set_provider(self, name: str) -> None:
        self._provider = name

    def reset(self) -> None:
        self._button.setEnabled(True)
        self._button.setText("Explicar")
        self._button.show()
        self._note.setText(f"Esta respuesta utilizará IA: se enviará a {self._provider} el fragmento de esta "
                           "pregunta y solo las firmas (sin código) de las clases relacionadas.")
        self._note.show()
        self._answer.hide()

    def show_loading(self) -> None:
        self._button.setEnabled(False)
        self._button.setText("Pensando…")

    def show_answer(self, text: str) -> None:
        self._button.hide()
        self._note.setText(f"Explicación generada por {self._provider} a partir de tu código.")
        self._answer.setText(paragraphs_html(text))
        self._answer.show()

    def show_error(self, message: str) -> None:
        self._button.setEnabled(True)
        self._button.setText("Reintentar")
        self._note.setText(f"No se pudo generar la explicación. {message}")
