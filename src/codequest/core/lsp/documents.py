"""Documentos en memoria: el fragmento editado dentro de su archivo y posiciones del protocolo LSP."""

from collections import Counter
from collections.abc import Iterable

from codequest.core.lsp.models import Diagnostic


def splice(file_text: str, first_line: int, original: str, edited: str) -> str:
    """El archivo con las líneas del fragmento `original` (que empieza en `first_line`) sustituidas
    por `edited`. Nada se escribe en disco."""
    lines = file_text.split("\n")
    start = first_line - 1
    return "\n".join([*lines[:start], edited, *lines[start + original.count("\n") + 1:]])


def utf16_column(line: str, column: int) -> int:
    """Columna en caracteres -> columna en unidades UTF-16 (LSP cuenta así por defecto: un emoji o
    un carácter fuera del plano básico ocupa dos)."""
    return len(line[:column].encode("utf-16-le")) // 2


def new_errors(current: Iterable[Diagnostic], baseline: Iterable[Diagnostic], first_line: int,
               line_count: int) -> list[Diagnostic]:
    """Errores de compilación dentro del fragmento (líneas `first_line`… de `line_count` líneas) que no
    estaban en la versión de partida. Se comparan por mensaje, no por línea: si el estudiante añade o
    quita líneas, los errores que ya estaban cambian de línea pero no de mensaje."""
    known = Counter(d.message for d in baseline if d.is_error)
    result: list[Diagnostic] = []
    for diagnostic in sorted(current, key=lambda d: d.line):
        if not diagnostic.is_error or not first_line <= diagnostic.line < first_line + line_count:
            continue
        if known[diagnostic.message] > 0:
            known[diagnostic.message] -= 1
        else:
            result.append(diagnostic)
    return result
