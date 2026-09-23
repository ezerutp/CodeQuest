from PySide6.QtCore import Signal
from PySide6.QtWidgets import QGridLayout, QWidget

from codequest.core.games.catalog import GAME_MODES
from codequest.ui.widgets.mode_card import ModeCard


class ModeGrid(QWidget):
    """Cuadrícula de modos de juego del catálogo. Emite el id del modo elegido."""

    mode_selected = Signal(str)

    def __init__(self, columns: int = 3, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(12)
        for index, mode in enumerate(GAME_MODES):
            card = ModeCard(
                f"mode.{mode.id}", mode.title, mode.description,
                badge="IA" if mode.uses_ai else "Local",
                badge_icon="ai" if mode.uses_ai else "local",
                available=mode.available,
            )
            card.setMinimumHeight(130)
            card.clicked.connect(lambda mode_id=mode.id: self.mode_selected.emit(mode_id))
            grid.addWidget(card, index // columns, index % columns)
        for column in range(columns):
            grid.setColumnStretch(column, 1)
