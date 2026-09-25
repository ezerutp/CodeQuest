"""Documentos en memoria: el fragmento editado dentro de su archivo y posiciones del protocolo LSP."""


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
