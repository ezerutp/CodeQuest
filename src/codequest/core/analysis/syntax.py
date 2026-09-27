"""Consultas sintácticas con tree-sitter (Java, TypeScript, TSX): tokens y errores de sintaxis.

Sirven para evaluar código que escribe el estudiante sin compilarlo. Funcionan también con
fragmentos incompletos (una cabecera de clase sin su `}`): tree-sitter marca lo que falta y sigue.
"""

from collections.abc import Iterator
from functools import cache
from pathlib import PurePosixPath

from tree_sitter import Language, Node, Parser

from codequest.core.analysis.java.parser import JAVA
from codequest.core.analysis.typescript.parser import TS, TSX

_COMMENTS = frozenset({"line_comment", "block_comment", "comment"})
_GRAMMARS = {".ts": TS, ".tsx": TSX, ".jsx": TSX, ".js": TSX}


def grammar_for(file: str) -> Language:
    """Gramática según la extensión del archivo; Java por defecto."""
    return _GRAMMARS.get(PurePosixPath(file).suffix, JAVA)


@cache
def _parser(grammar: Language) -> Parser:
    return Parser(grammar)


def _leaves(node: Node) -> Iterator[Node]:
    stack = [node]
    while stack:
        current = stack.pop()
        if current.type in _COMMENTS:
            continue
        if current.child_count == 0:
            if not current.is_missing:  # tokens que tree-sitter "inventa" para recuperarse
                yield current
        else:
            stack.extend(reversed(current.children))


def tokens_by_line(text: str, grammar: Language = JAVA) -> dict[int, tuple[str, ...]]:
    """{índice de línea (desde 0): tokens} de las líneas con código, sin espacios ni comentarios."""
    source = text.encode("utf-8")
    lines: dict[int, list[str]] = {}
    for leaf in _leaves(_parser(grammar).parse(source).root_node):
        lines.setdefault(leaf.start_point.row, []).append(source[leaf.start_byte:leaf.end_byte].decode("utf-8"))
    return {row: tuple(tokens) for row, tokens in sorted(lines.items())}


def tokens(text: str, grammar: Language = JAVA) -> tuple[str, ...]:
    """Tokens del texto: dos versiones iguales salvo por espacios y comentarios dan lo mismo."""
    return tuple(t for line in tokens_by_line(text, grammar).values() for t in line)


def syntax_error_lines(text: str, grammar: Language = JAVA) -> list[int]:
    """Líneas (desde 1) con un error de sintaxis o un token que falta, en orden."""
    lines: set[int] = set()
    stack = [_parser(grammar).parse(text.encode("utf-8")).root_node]
    while stack:
        node = stack.pop()
        if not node.has_error:
            continue
        if node.is_error or node.is_missing:
            lines.add(node.start_point.row + 1)
        stack.extend(node.children)
    return sorted(lines)
