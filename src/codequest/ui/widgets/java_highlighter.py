"""Resaltado de sintaxis Java: traduce los tokens del lexer (core) a formatos de Qt."""

from PySide6.QtGui import (
    QColor,
    QFont,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextDocument,
)

from codequest.core.analysis.java.lexer import LineState, TokenKind, tokenize_line
from codequest.ui.theme import Palette, current_palette


def _formats(palette: Palette) -> dict[TokenKind, QTextCharFormat]:
    colors = {
        TokenKind.KEYWORD: palette.syntax_keyword,
        TokenKind.TYPE: palette.syntax_type,
        TokenKind.STRING: palette.syntax_string,
        TokenKind.NUMBER: palette.syntax_number,
        TokenKind.COMMENT: palette.syntax_comment,
        TokenKind.ANNOTATION: palette.syntax_annotation,
    }
    formats: dict[TokenKind, QTextCharFormat] = {}
    for kind, color in colors.items():
        fmt = QTextCharFormat()
        fmt.setForeground(QColor(color))
        if kind is TokenKind.COMMENT:
            fmt.setFontItalic(True)
        if kind is TokenKind.KEYWORD:
            fmt.setFontWeight(QFont.Weight.Medium)
        formats[kind] = fmt
    return formats


class JavaHighlighter(QSyntaxHighlighter):
    def __init__(self, document: QTextDocument, palette: Palette | None = None) -> None:
        super().__init__(document)
        self._formats = _formats(palette or current_palette())

    def highlightBlock(self, text: str) -> None:  # noqa: N802 (API de Qt)
        previous = self.previousBlockState()
        state = LineState(previous) if previous in (s.value for s in LineState) else LineState.NORMAL
        tokens, new_state = tokenize_line(text, state)
        for token in tokens:
            self.setFormat(token.start, token.length, self._formats[token.kind])
        self.setCurrentBlockState(int(new_state))
