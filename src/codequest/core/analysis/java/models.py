"""Modelos del código Java. Guardan estructura y rangos de líneas, no el código."""

import re
from dataclasses import dataclass
from enum import StrEnum

_STRING_LITERAL = re.compile(r'"((?:\\.|[^"\\])*)"')


class TypeKind(StrEnum):
    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"
    RECORD = "record"
    ANNOTATION = "@interface"


@dataclass(frozen=True, slots=True)
class JavaAnnotation:
    name: str  # nombre simple, sin "@": "GetMapping"
    arguments: str | None  # texto original entre paréntesis: '"/{id}"'
    line: int

    @property
    def display(self) -> str:
        return f"@{self.name}" if self.arguments is None else f"@{self.name}({self.arguments})"

    def string_values(self) -> tuple[str, ...]:
        """Literales de texto de los argumentos, p. ej. las rutas de @RequestMapping."""
        return tuple(_STRING_LITERAL.findall(self.arguments or ""))


@dataclass(frozen=True, slots=True)
class JavaParameter:
    name: str
    type: str
    annotations: tuple[JavaAnnotation, ...] = ()


@dataclass(frozen=True, slots=True)
class JavaField:
    name: str
    type: str
    modifiers: tuple[str, ...]
    annotations: tuple[JavaAnnotation, ...]
    start_line: int
    end_line: int


@dataclass(frozen=True, slots=True)
class JavaMethod:
    name: str
    return_type: str | None  # None en constructores
    parameters: tuple[JavaParameter, ...]
    modifiers: tuple[str, ...]
    annotations: tuple[JavaAnnotation, ...]
    throws: tuple[str, ...]
    start_line: int  # incluye las anotaciones
    end_line: int
    has_body: bool = True

    @property
    def is_constructor(self) -> bool:
        return self.return_type is None

    @property
    def signature(self) -> str:
        params = ", ".join(f"{p.type} {p.name}" for p in self.parameters)
        return f"{self.name}({params})"


@dataclass(frozen=True, slots=True)
class JavaClass:
    name: str
    package: str
    kind: TypeKind
    file: str  # ruta relativa POSIX del archivo fuente
    is_test: bool
    start_line: int
    end_line: int
    modifiers: tuple[str, ...] = ()
    annotations: tuple[JavaAnnotation, ...] = ()
    imports: tuple[str, ...] = ()
    superclass: str | None = None
    interfaces: tuple[str, ...] = ()
    fields: tuple[JavaField, ...] = ()
    methods: tuple[JavaMethod, ...] = ()
    enum_constants: tuple[str, ...] = ()
    enclosing: str | None = None  # "Outer" o "Outer.Inner" para clases anidadas

    @property
    def qualified_name(self) -> str:
        parts = [p for p in (self.package, self.enclosing, self.name) if p]
        return ".".join(parts)

    def annotation(self, name: str) -> JavaAnnotation | None:
        return next((a for a in self.annotations if a.name == name), None)

    def has_annotation(self, *names: str) -> bool:
        return any(a.name in names for a in self.annotations)
