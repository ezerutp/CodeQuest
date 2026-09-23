"""Lectura de fragmentos de código del proyecto. Solo lectura, siempre dentro de la raíz."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class CodeSnippet:
    file: str  # ruta relativa POSIX
    start_line: int  # 1-based, inclusive
    end_line: int
    text: str

    @property
    def line_count(self) -> int:
        return self.end_line - self.start_line + 1


@dataclass(frozen=True, slots=True)
class SnippetRef:
    """Referencia a un fragmento sin su texto: las preguntas no guardan código."""

    file: str
    start_line: int
    end_line: int
    focus_lines: tuple[int, ...] = ()  # líneas a resaltar (numeración del archivo)


def read_snippet(root: Path, relative_path: str, start_line: int = 1, end_line: int | None = None) -> CodeSnippet:
    """Lee las líneas [start_line, end_line] de un archivo del proyecto.

    Lanza ValueError si la ruta sale de la raíz del proyecto (p. ej. "../../etc/passwd").
    """
    root = root.resolve()
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root):
        raise ValueError(f"La ruta queda fuera del proyecto: {relative_path}")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, start_line)
    end = len(lines) if end_line is None else min(end_line, len(lines))
    return CodeSnippet(relative_path, start, max(start, end), "\n".join(lines[start - 1:end]))
