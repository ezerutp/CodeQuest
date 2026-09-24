"""Medidor de una proporción (0-100 %): etiqueta, barra y valor.

Relleno en el color de acento y pista en un tono de la misma familia (`accent_soft`),
para que la proporción se lea en toda la barra. El valor va en color de texto.
"""

from PySide6.QtWidgets import QGridLayout, QLabel, QProgressBar, QWidget


class Meter(QWidget):
    def __init__(self, label: str, percent: int, detail: str = "", tooltip: str = "",
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(4)

        name = QLabel(label)
        name.setObjectName("MeterLabel")
        value = QLabel(f"{percent} %")
        value.setObjectName("MeterValue")
        bar = QProgressBar()
        bar.setObjectName("Meter")
        bar.setRange(0, 100)
        bar.setValue(max(0, min(100, percent)))
        bar.setTextVisible(False)
        grid.addWidget(name, 0, 0)
        grid.addWidget(value, 0, 1)
        grid.addWidget(bar, 1, 0, 1, 2)
        if detail:
            note = QLabel(detail)
            note.setProperty("role", "muted")
            grid.addWidget(note, 2, 0, 1, 2)
        grid.setColumnStretch(0, 1)
        self.setToolTip(tooltip)
