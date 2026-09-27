"""Modelos del código TypeScript/TSX. Guardan estructura y posiciones, no el código."""

from dataclasses import dataclass
from enum import StrEnum


class TSTypeKind(StrEnum):
    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"
    TYPE_ALIAS = "type"
    FUNCTION = "function"


@dataclass(frozen=True, slots=True)
class TSSourceSpan:
    """Tramo del archivo: líneas reales (desde 1) y columnas en caracteres (desde 0, fin exclusivo)."""

    line: int
    column: int
    end_line: int
    end_column: int


@dataclass(frozen=True, slots=True)
class TSField:
    name: str
    type: str
    modifiers: tuple[str, ...]
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class TSMethod:
    name: str
    return_type: str | None
    parameters: tuple[str, ...]  # "name: Type"
    modifiers: tuple[str, ...]
    start_line: int
    end_line: int
    has_body: bool = True


@dataclass(frozen=True, slots=True)
class TSClass:
    name: str
    kind: TSTypeKind
    file: str  # ruta relativa POSIX del archivo fuente
    is_test: bool
    start_line: int
    end_line: int
    modifiers: tuple[str, ...] = ()
    imports: tuple[str, ...] = ()
    superclass: str | None = None
    interfaces: tuple[str, ...] = ()
    fields: tuple[TSField, ...] = ()
    methods: tuple[TSMethod, ...] = ()
    is_component: bool = False  # función que retorna JSX
    is_hook: bool = False  # función que llama a useState/useEffect/etc.
    enclosing: str | None = None

    @property
    def qualified_name(self) -> str:
        parts = [p for p in (self.enclosing, self.name) if p]
        return ".".join(parts)
