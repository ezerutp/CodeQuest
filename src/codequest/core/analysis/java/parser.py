"""Parser Java ligero: estructura de tipos, anotaciones, campos y métodos.

No es un compilador. Recorre el texto enmascarado (sin comentarios ni strings)
contando llaves y paréntesis, y aplica expresiones regulares solo a cabeceras
cortas ("public class X extends Y", "public User save(User u)"). Los cuerpos de
los métodos se saltan. Se puede sustituir por otro SourceParser (p. ej. tree-sitter).
"""

import logging
import re
from dataclasses import dataclass, field

from codequest.core.analysis.base import SourceParser
from codequest.core.analysis.java.models import (
    JavaAnnotation,
    JavaClass,
    JavaField,
    JavaMethod,
    JavaParameter,
    TypeKind,
)
from codequest.core.analysis.java.source_text import (
    LineIndex,
    find_top_level,
    mask_source,
    matching,
    normalize_type,
    split_top_level,
)
from codequest.core.project.models import SourceFile

log = logging.getLogger(__name__)

MODIFIERS = frozenset({
    "public", "protected", "private", "abstract", "static", "final", "sealed", "non-sealed",
    "strictfp", "default", "synchronized", "native", "transient", "volatile",
})

_PACKAGE = re.compile(r"^\s*package\s+([\w.]+)\s*;", re.MULTILINE)
_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+(?:\.\*)?)\s*;", re.MULTILINE)
_TYPE_DECL = re.compile(
    r"((?:(?:public|protected|private|abstract|static|final|sealed|non-sealed|strictfp)\s+)*)"
    r"(class|interface|enum|record|@interface)\s+(\w+)"
)
_ANNOTATION = re.compile(r"\s*@\s*([\w.]+)\s*")  # "@ Foo" o "@org.x.Foo" + espacios
_NON_SPACE = re.compile(r"\S")
_TRAILING_NAME = re.compile(r"(\w+)\s*((?:\[\s*\]\s*)*)$")
_EXTENDS = re.compile(r"\bextends\s+(.+?)(?=\bimplements\b|\bpermits\b|$)", re.DOTALL)
_IMPLEMENTS = re.compile(r"\bimplements\s+(.+?)(?=\bpermits\b|$)", re.DOTALL)
_THROWS = re.compile(r"\bthrows\s+(.+?)(?=\bdefault\b|$)", re.DOTALL)


def _strip_modifiers(text: str) -> tuple[tuple[str, ...], str]:
    """Separa los modificadores iniciales ("private static final") del resto."""
    modifiers: list[str] = []
    while (word := re.match(r"\s*([\w-]+)\s+", text)) and word.group(1) in MODIFIERS:
        modifiers.append(word.group(1))
        text = text[word.end():]
    return tuple(modifiers), text


class RegexJavaParser(SourceParser):
    def supports(self, file: SourceFile) -> bool:
        return file.extension == ".java"

    def parse(self, file: SourceFile, text: str) -> list[JavaClass]:
        return _FileParser(file, text).parse()


@dataclass
class _TypeBuilder:
    """Acumula los miembros de un tipo mientras se recorre su cuerpo."""

    name: str
    kind: TypeKind
    enclosing: str | None
    modifiers: tuple[str, ...]
    annotations: tuple[JavaAnnotation, ...]
    superclass: str | None
    interfaces: tuple[str, ...]
    start_line: int
    fields: list[JavaField] = field(default_factory=list)
    methods: list[JavaMethod] = field(default_factory=list)
    enum_constants: list[str] = field(default_factory=list)

    @property
    def path(self) -> str:
        return f"{self.enclosing}.{self.name}" if self.enclosing else self.name


class _FileParser:
    def __init__(self, file: SourceFile, text: str) -> None:
        self._file = file
        self._text = text
        self._m = mask_source(text)
        self._lines = LineIndex(text)
        package = _PACKAGE.search(self._m)
        self._package = package.group(1) if package else ""
        self._imports = tuple(_IMPORT.findall(self._m))
        self._classes: list[JavaClass] = []

    def parse(self) -> list[JavaClass]:
        self._parse_block(0, len(self._m), owner=None)
        return self._classes

    # --- recorrido de bloques --------------------------------------------------

    def _parse_block(self, start: int, end: int, owner: _TypeBuilder | None) -> None:
        """Recorre las declaraciones de un bloque (archivo o cuerpo de un tipo)."""
        m = self._m
        header_start = start
        paren = 0
        i = start
        while i < end:
            c = m[i]
            if c == "(":
                paren += 1
            elif c == ")":
                paren = max(0, paren - 1)
            elif paren == 0 and c == ";":
                self._handle_statement(header_start, i, owner)
                header_start = i + 1
            elif paren == 0 and c == "{":
                i = self._handle_block(header_start, i, owner)
                header_start = i
                continue
            elif paren == 0 and c == "}":
                header_start = i + 1
            i += 1

    def _handle_block(self, header_start: int, brace: int, owner: _TypeBuilder | None) -> int:
        """Procesa una cabecera seguida de '{'. Devuelve dónde seguir recorriendo."""
        close = matching(self._m, brace)
        annotations, rest = self._parse_annotations(header_start, brace)
        rest_text = self._m[rest:brace]

        if decl := _TYPE_DECL.match(rest_text.lstrip()):
            offset = rest + (len(rest_text) - len(rest_text.lstrip()))
            self._parse_type(decl, offset, brace, close, annotations, header_start, owner)
            return close + 1
        if owner is None:
            return close + 1

        stripped = rest_text.strip()
        if stripped in ("", "static"):  # bloque inicializador
            return close + 1
        if self._has_initializer(rest, brace):
            # Inicializador con llaves: array, clase anónima o lambda. Sigue hasta el ';'.
            semi = self._statement_end(close + 1)
            self._add_fields(owner, header_start, rest, semi, annotations)
            return semi + 1
        paren = find_top_level(self._m, rest, brace, "(")
        if paren != -1:
            self._add_method(owner, header_start, rest, paren, brace, close, annotations, has_body=True)
        return close + 1

    def _handle_statement(self, header_start: int, semi: int, owner: _TypeBuilder | None) -> None:
        if owner is None:
            return  # package / import
        annotations, rest = self._parse_annotations(header_start, semi)
        if not self._m[rest:semi].strip():
            return
        if self._is_field_header(rest, semi):
            self._add_fields(owner, header_start, rest, semi, annotations)
            return
        paren = find_top_level(self._m, rest, semi, "(")
        if paren != -1:
            self._add_method(owner, header_start, rest, paren, semi, semi, annotations, has_body=False)

    def _statement_end(self, start: int) -> int:
        """Siguiente ';' de nivel superior a partir de `start`, saltando bloques."""
        m = self._m
        paren = 0
        i = start
        while i < len(m):
            c = m[i]
            if c == "(":
                paren += 1
            elif c == ")":
                paren = max(0, paren - 1)
            elif c == "{":
                i = matching(m, i)
            elif c == ";" and paren == 0:
                return i
            i += 1
        return len(m) - 1

    # --- tipos --------------------------------------------------------------------

    def _parse_type(self, decl: re.Match[str], offset: int, brace: int, close: int,
                    annotations: tuple[JavaAnnotation, ...], header_start: int,
                    owner: _TypeBuilder | None) -> None:
        modifiers, kind_text, name = decl.group(1).split(), decl.group(2), decl.group(3)
        kind = TypeKind(kind_text)
        tail_start = offset + decl.end()
        tail = self._m[tail_start:brace]

        # Parámetros genéricos (<T extends X>) y componentes de record ((int x, int y)).
        stripped = tail.lstrip()
        skip = len(tail) - len(stripped)
        if stripped.startswith("<"):
            skip = matching(self._m, tail_start + skip) - tail_start + 1
        components: list[JavaField] = []
        if kind is TypeKind.RECORD:
            paren = self._m.find("(", tail_start + skip, brace)
            if paren != -1:
                paren_close = matching(self._m, paren)
                components = [self._record_component(s, e) for s, e in
                              split_top_level(self._m, paren + 1, paren_close)]
                skip = paren_close - tail_start + 1
        clauses = self._m[tail_start + skip:brace]

        extends = self._type_list(_EXTENDS, clauses)
        implements = self._type_list(_IMPLEMENTS, clauses)
        if kind is TypeKind.INTERFACE:
            superclass, interfaces = None, extends
        else:
            superclass, interfaces = (extends[0] if extends else None), implements

        builder = _TypeBuilder(
            name=name,
            kind=kind,
            enclosing=owner.path if owner else None,
            modifiers=tuple(modifiers),
            annotations=annotations,
            superclass=superclass,
            interfaces=interfaces,
            start_line=self._line(header_start),
            fields=components,
        )
        position = len(self._classes)
        body_start = brace + 1
        if kind is TypeKind.ENUM:
            body_start = self._parse_enum_constants(builder, body_start, close)
        self._parse_block(body_start, close, owner=builder)
        self._classes.insert(position, self._build(builder, close))

    def _parse_enum_constants(self, builder: _TypeBuilder, start: int, close: int) -> int:
        semi = find_top_level(self._m, start, close, ";")
        end = close if semi == -1 else semi
        for s, e in split_top_level(self._m, start, end):
            _, rest = self._parse_annotations(s, e)
            if name := re.match(r"\s*(\w+)", self._m[rest:e]):
                builder.enum_constants.append(name.group(1))
        return end + 1 if semi != -1 else close

    def _build(self, b: _TypeBuilder, close: int) -> JavaClass:
        return JavaClass(
            name=b.name,
            package=self._package,
            kind=b.kind,
            file=self._file.relative_path,
            is_test=self._file.is_test,
            start_line=b.start_line,
            end_line=self._line(close),
            modifiers=b.modifiers,
            annotations=b.annotations,
            imports=self._imports,
            superclass=b.superclass,
            interfaces=b.interfaces,
            fields=tuple(b.fields),
            methods=tuple(b.methods),
            enum_constants=tuple(b.enum_constants),
            enclosing=b.enclosing,
        )

    def _type_list(self, pattern: re.Pattern[str], clauses: str) -> tuple[str, ...]:
        found = pattern.search(clauses)
        if not found:
            return ()
        text = found.group(1)
        return tuple(normalize_type(text[s:e]) for s, e in split_top_level(text, 0, len(text)))

    # --- miembros -----------------------------------------------------------------

    def _has_initializer(self, start: int, end: int) -> bool:
        """Un '=' antes del primer '(' indica un campo con inicializador."""
        equals = find_top_level(self._m, start, end, "=")
        paren = find_top_level(self._m, start, end, "(")
        return equals != -1 and (paren == -1 or equals < paren)

    def _is_field_header(self, start: int, end: int) -> bool:
        """Declaración terminada en ';': es campo si tiene inicializador o no tiene '('."""
        return self._has_initializer(start, end) or find_top_level(self._m, start, end, "(") == -1

    def _add_fields(self, owner: _TypeBuilder, header_start: int, rest: int, semi: int,
                    annotations: tuple[JavaAnnotation, ...]) -> None:
        declarators = split_top_level(self._m, rest, semi, brackets="(<[{")
        if not declarators:
            return
        first_start, first_end = declarators[0]
        modifiers, declaration = _strip_modifiers(self._before_equals(first_start, first_end))
        name_match = _TRAILING_NAME.search(declaration.strip())
        if not name_match:
            return
        field_type = normalize_type(declaration.strip()[:name_match.start()] + name_match.group(2))
        if not field_type:
            return  # p. ej. una llamada suelta; no es un campo
        names = [name_match.group(1)]
        for s, e in declarators[1:]:
            if extra := _TRAILING_NAME.search(self._before_equals(s, e).strip()):
                names.append(extra.group(1))
        start_line, end_line = self._line(header_start), self._line(semi)
        for name in names:
            owner.fields.append(JavaField(name, field_type, modifiers, annotations, start_line, end_line))

    def _before_equals(self, start: int, end: int) -> str:
        equals = find_top_level(self._m, start, end, "=")
        return self._m[start:equals if equals != -1 else end]

    def _add_method(self, owner: _TypeBuilder, header_start: int, rest: int, paren: int,
                    header_end: int, close: int, annotations: tuple[JavaAnnotation, ...],
                    has_body: bool) -> None:
        before = self._m[rest:paren]
        name_match = re.search(r"(\w+)\s*$", before)
        if not name_match:
            return
        name = name_match.group(1)
        modifiers, remaining = _strip_modifiers(before[:name_match.start()])
        remaining = remaining.strip()
        if remaining.startswith("<"):  # parámetros genéricos del método: <T> T find()
            depth = 0
            for i, c in enumerate(remaining):
                depth += (c == "<") - (c == ">")
                if depth == 0:
                    remaining = remaining[i + 1:]
                    break
        return_type = normalize_type(remaining) or None
        if return_type is None and name != owner.name:
            return  # no es un constructor ni un método reconocible

        paren_close = matching(self._m, paren)
        parameters = tuple(self._parameter(s, e) for s, e in split_top_level(self._m, paren + 1, paren_close))
        throws_match = _THROWS.search(self._m[paren_close + 1:header_end])
        throws = tuple(normalize_type(t) for t in throws_match.group(1).split(",")) if throws_match else ()

        owner.methods.append(JavaMethod(
            name=name,
            return_type=return_type,
            parameters=parameters,
            modifiers=modifiers,
            annotations=annotations,
            throws=throws,
            start_line=self._line(header_start),
            end_line=self._line(close),
            has_body=has_body,
        ))

    def _parameter(self, start: int, end: int) -> JavaParameter:
        annotations, rest = self._parse_annotations(start, end)
        text = " ".join(w for w in self._m[rest:end].split() if w != "final")
        varargs = "..." in text
        text = text.replace("...", " ")
        name_match = _TRAILING_NAME.search(text.strip())
        if not name_match:
            return JavaParameter(name="?", type=normalize_type(text), annotations=annotations)
        param_type = normalize_type(text.strip()[:name_match.start()] + name_match.group(2))
        return JavaParameter(name_match.group(1), param_type + ("..." if varargs else ""), annotations)

    def _record_component(self, start: int, end: int) -> JavaField:
        param = self._parameter(start, end)
        line = self._line(start)
        return JavaField(param.name, param.type, ("private", "final"), param.annotations, line, line)

    # --- anotaciones y utilidades ---------------------------------------------------

    def _parse_annotations(self, start: int, end: int) -> tuple[tuple[JavaAnnotation, ...], int]:
        """Lee las anotaciones al inicio de m[start:end]. Devuelve (anotaciones, offset tras ellas)."""
        m = self._m
        if m.find("@", start, end) == -1:  # caso habitual: nada que leer
            return (), start
        annotations: list[JavaAnnotation] = []
        i = start
        while (found := _ANNOTATION.match(m, i, end)) and found.group(1) != "interface":
            line = self._line(i)
            j = found.end()
            arguments = None
            if j < end and m[j] == "(":
                close = matching(m, j)
                arguments = " ".join(self._text[j + 1:close].split())
                j = close + 1
            simple_name = found.group(1).rsplit(".", 1)[-1]
            annotations.append(JavaAnnotation(simple_name, arguments, line))
            i = j
        return tuple(annotations), i

    def _line(self, offset: int) -> int:
        """Línea del primer carácter no vacío a partir de `offset`."""
        if found := _NON_SPACE.search(self._m, offset):
            offset = found.start()
        return self._lines.line_of(offset)
