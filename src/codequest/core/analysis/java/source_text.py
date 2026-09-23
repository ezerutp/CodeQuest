"""Utilidades para recorrer código Java sin un parser completo.

El texto "enmascarado" sustituye comentarios y contenido de strings por espacios,
conservando posiciones y saltos de línea: así un "{" dentro de un string o un "class"
dentro de un comentario no confunden al analizador, y los offsets siguen sirviendo
para leer el texto original.
"""

import re
from bisect import bisect_right
from functools import lru_cache

_MASKABLE = re.compile(
    r'//[^\n]*'                    # comentario de línea
    r'|/\*.*?(?:\*/|\Z)'           # comentario de bloque
    r'|"""(?:\\.|.)*?(?:"""|\Z)'   # text block
    r'|"(?:\\.|[^"\\\n])*"?'       # string
    r"|'(?:\\.|[^'\\\n])*'?",      # char
    re.DOTALL,
)
_OPEN_TO_CLOSE = {"(": ")", "{": "}", "[": "]", "<": ">"}
# Para cada apertura, una regex que solo encuentra ese par: así `matching` salta
# directamente de un delimitador al siguiente en vez de recorrer carácter a carácter.
_PAIR_PATTERNS = {o: re.compile(re.escape(o) + "|" + re.escape(c)) for o, c in _OPEN_TO_CLOSE.items()}
_SPACES = re.compile(r"\s+")
_SPACE_AROUND_BRACKETS = re.compile(r"\s*([<>\[\]])\s*")
_SPACE_AROUND_COMMA = re.compile(r"\s*,\s*")


def _blank(text: str) -> str:
    return re.sub(r"[^\n]", " ", text)


def _mask_match(match: re.Match[str]) -> str:
    token = match.group(0)
    if token.startswith("/"):
        return _blank(token)
    quote = 3 if token.startswith('"""') else 1
    if len(token) <= quote * 2:
        return token
    return token[:quote] + _blank(token[quote:-quote]) + token[-quote:]


def mask_source(text: str) -> str:
    return _MASKABLE.sub(_mask_match, text)


class LineIndex:
    """Convierte offsets en números de línea (1-based)."""

    def __init__(self, text: str) -> None:
        self._newlines = [m.start() for m in re.finditer("\n", text)]

    def line_of(self, offset: int) -> int:
        return bisect_right(self._newlines, offset - 1) + 1


def matching(masked: str, open_index: int) -> int:
    """Índice del cierre que corresponde a masked[open_index]. Si no existe, el final."""
    opener = masked[open_index]
    depth = 0
    for match in _PAIR_PATTERNS[opener].finditer(masked, open_index):
        depth += 1 if match.group() == opener else -1
        if depth == 0:
            return match.start()
    return len(masked) - 1


def split_top_level(masked: str, start: int, end: int, separator: str = ",",
                    brackets: str = "(<[{") -> list[tuple[int, int]]:
    """Divide masked[start:end] por `separator` fuera de paréntesis/genéricos. Devuelve spans."""
    closers = {_OPEN_TO_CLOSE[b] for b in brackets}
    spans: list[tuple[int, int]] = []
    depth = 0
    part_start = start
    for i in range(start, end):
        c = masked[i]
        if c in brackets:
            depth += 1
        elif c in closers:
            depth = max(0, depth - 1)
        elif c == separator and depth == 0:
            spans.append((part_start, i))
            part_start = i + 1
    spans.append((part_start, end))
    return [(s, e) for s, e in spans if masked[s:e].strip()]


@lru_cache(maxsize=32)
def _delimiters(char: str, brackets: str) -> re.Pattern[str]:
    chars = {char, *brackets, *(_OPEN_TO_CLOSE[b] for b in brackets)}
    return re.compile("[" + "".join(re.escape(c) for c in sorted(chars)) + "]")


def find_top_level(masked: str, start: int, end: int, char: str, brackets: str = "([{") -> int:
    """Primer índice de `char` fuera de paréntesis en masked[start:end], o -1."""
    depth = 0
    for match in _delimiters(char, brackets).finditer(masked, start, end):
        c = match.group()
        if c == char and depth == 0:
            return match.start()
        if c in brackets:
            depth += 1
        elif c != char:
            depth = max(0, depth - 1)
    return -1


@lru_cache(maxsize=4096)  # los mismos tipos (String, Long, List<User>...) se repiten mucho
def normalize_type(text: str) -> str:
    """'Map< String ,  List<X> >' -> 'Map<String, List<X>>'."""
    text = _SPACES.sub(" ", text).strip()
    text = _SPACE_AROUND_BRACKETS.sub(r"\1", text)
    return _SPACE_AROUND_COMMA.sub(", ", text)
