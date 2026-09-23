"""Fábricas de etiquetas con los roles tipográficos definidos en base.qss."""

from PySide6.QtWidgets import QLabel


def _label(text: str, role: str, word_wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", role)
    label.setWordWrap(word_wrap)
    return label


def heading(text: str, level: int = 1, word_wrap: bool = True) -> QLabel:
    return _label(text, f"h{level}", word_wrap=word_wrap)


def section_title(text: str) -> QLabel:
    return _label(text.upper(), "section")


def muted(text: str, word_wrap: bool = True) -> QLabel:
    return _label(text, "muted", word_wrap=word_wrap)


def mono(text: str) -> QLabel:
    return _label(text, "mono")
