"""Parser TypeScript/TSX basado en tree-sitter: clases, interfaces, funciones, componentes React.

tree-sitter-typescript construye el árbol sintáctico completo y tolera código a medio escribir.
Aquí solo se traduce ese árbol a los modelos inmutables de `models.py`.
"""

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field

import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from codequest.core.analysis.base import SourceParser
from codequest.core.analysis.typescript.models import (
    TSCall,
    TSClass,
    TSField,
    TSMethod,
    TSSourceSpan,
    TSTypeKind,
)
from codequest.core.project.models import SourceFile

log = logging.getLogger(__name__)

TS = Language(tree_sitter_typescript.language_typescript())
TSX = Language(tree_sitter_typescript.language_tsx())

_TYPE_KINDS = {
    "class_declaration": TSTypeKind.CLASS,
    "interface_declaration": TSTypeKind.INTERFACE,
    "enum_declaration": TSTypeKind.ENUM,
    "type_alias_declaration": TSTypeKind.TYPE_ALIAS,
}
_SPACES = re.compile(r"\s+")
_HOOK_NAMES = frozenset({"useState", "useEffect", "useContext", "useReducer", "useMemo", "useCallback",
                         "useRef", "useLayoutEffect", "useImperativeHandle", "useTransition"})
_CUSTOM_HOOK = re.compile(r"use[A-Z]\w*")  # convención de React: los hooks empiezan por "use"
_JSX = frozenset({"jsx_element", "jsx_self_closing_element", "jsx_fragment"})
_FUNCTION_VALUES = frozenset({"arrow_function", "function_expression", "function"})
_WRAPPERS = frozenset({b"memo", b"forwardRef"})  # memo(() => …), React.forwardRef(function …)


def normalize_ts_type(text: str) -> str:
    """'Map< string , number >' -> 'Map<string, number>'."""
    text = _SPACES.sub(" ", text).strip()
    text = re.sub(r"\s*,\s*", ", ", text)
    text = re.sub(r"\s*([<>\[\]])\s*", r"\1", text)
    return text


class TreeSitterTypeScriptParser(SourceParser):
    """Parser para archivos .ts y .tsx. Usa tree-sitter-typescript."""

    def __init__(self) -> None:
        self._parser_ts = Parser(TS)
        self._parser_tsx = Parser(TSX)

    def supports(self, file: SourceFile) -> bool:
        return file.extension in (".ts", ".tsx")

    def parse(self, file: SourceFile, text: str) -> list[TSClass]:
        source = text.encode("utf-8")
        # Para .tsx necesitamos el parser TSX; para .ts el parser TS es suficiente
        parser = self._parser_tsx if file.extension == ".tsx" else self._parser_ts
        tree = parser.parse(source)
        if tree.root_node.has_error:
            log.debug("%s tiene errores de sintaxis; se analiza lo reconocible", file.relative_path)
        return _FileReader(file, source, tree.root_node).read()


@dataclass
class _TypeBuilder:
    """Acumula los miembros de un tipo mientras se recorre su cuerpo."""

    name: str
    kind: TSTypeKind
    enclosing: str | None
    node: Node
    fields: list[TSField] = field(default_factory=list)
    methods: list[TSMethod] = field(default_factory=list)

    @property
    def path(self) -> str:
        return f"{self.enclosing}.{self.name}" if self.enclosing else self.name


class _FileReader:
    def __init__(self, file: SourceFile, source: bytes, root: Node) -> None:
        self._file = file
        self._source = source
        self._root = root
        self._line_starts = [0] + [i + 1 for i, b in enumerate(source) if b == 0x0A]
        self._imports: list[str] = []
        self._classes: list[TSClass] = []

    def read(self) -> list[TSClass]:
        for node in self._root.named_children:
            if node.type == "import_statement":
                self._add_import(node)
            elif node.type in _TYPE_KINDS:
                self._read_type(node, enclosing=None)
            elif node.type == "function_declaration":
                self._read_function(node)
            elif node.type in ("lexical_declaration", "variable_declaration"):
                self._read_variables(node)
            elif node.type == "export_statement":
                self._read_export(node)
        return self._classes

    def _add_import(self, node: Node) -> None:
        if source := node.child_by_field_name("source"):
            self._imports.append(self._text(source).strip('"\''))

    def _read_export(self, node: Node) -> None:
        """export default function Foo() {} / export class Bar {} / export interface Baz {}"""
        if declaration := node.child_by_field_name("declaration"):
            if declaration.type in _TYPE_KINDS:
                self._read_type(declaration, enclosing=None)
            elif declaration.type == "function_declaration":
                self._read_function(declaration, extra_modifiers=("export",))
            elif declaration.type in ("lexical_declaration", "variable_declaration"):
                self._read_variables(declaration, exported=True)
        # export { A, B } no declara nada nuevo

    def _read_type(self, node: Node, enclosing: str | None) -> None:
        name = node.child_by_field_name("name")
        if name is None:
            return
        builder = _TypeBuilder(self._text(name), _TYPE_KINDS[node.type], enclosing, node)
        if body := node.child_by_field_name("body"):
            self._read_body(body, builder)
        self._classes.append(self._build(builder))

    def _read_variables(self, node: Node, exported: bool = False) -> None:
        """const Header = () => <h1/>; también envuelto: memo(() => …), forwardRef(function …)."""
        for declarator in node.named_children:
            if declarator.type != "variable_declarator":
                continue
            name = declarator.child_by_field_name("name")
            value = _unwrap_function(declarator.child_by_field_name("value"))
            if name is not None and name.type == "identifier" and value is not None:
                self._read_function(value, name=self._text(name), span=node,
                                    extra_modifiers=("export",) if exported else ())

    def _read_function(self, node: Node, name: str | None = None, span: Node | None = None,
                       extra_modifiers: tuple[str, ...] = ()) -> None:
        """Función declarada o asignada a una constante (posiblemente componente React o hook).

        `span` es el nodo cuyas líneas se muestran (la declaración `const …` completa).
        """
        if name is None:
            name_node = node.child_by_field_name("name")
            if name_node is None:
                return
            name = self._text(name_node)
        span = span or node
        modifiers = (*extra_modifiers, *self._modifiers(node))
        params = node.child_by_field_name("parameters")
        parameters = tuple(self._parameter(p) for p in params.named_children
                           if p.type in ("required_parameter", "optional_parameter")) if params else ()
        return_type = None
        if type_node := node.child_by_field_name("return_type"):
            return_type = self._type_from_annotation(type_node)
        body = node.child_by_field_name("body")
        # Reglas de React: los hooks se llaman useX; un componente puede usar hooks y devolver null
        # (p. ej. los de react-leaflet), así que PascalCase + hooks también es un componente.
        uses_hooks = self._uses_hooks(body)
        is_component = self._returns_jsx(body) or (name[:1].isupper() and uses_hooks)
        is_hook = not is_component and _CUSTOM_HOOK.fullmatch(name) is not None
        self._classes.append(TSClass(
            name=name,
            kind=TSTypeKind.FUNCTION,
            file=self._file.relative_path,
            is_test=self._file.is_test,
            start_line=self._line(span),
            end_line=self._end_line(span),
            modifiers=modifiers,
            imports=tuple(self._imports),
            fields=(),
            methods=(TSMethod(
                name=name,
                return_type=return_type,
                parameters=parameters,
                modifiers=modifiers,
                start_line=self._line(span),
                end_line=self._end_line(span),
                has_body=body is not None,
                calls=self._calls(body),
            ),),
            is_component=is_component,
            is_hook=is_hook,
        ))

    def _read_body(self, body: Node, owner: _TypeBuilder) -> None:
        for member in body.named_children:
            kind = member.type
            if kind in _TYPE_KINDS:
                self._read_type(member, owner.path)
            elif kind in ("property_definition", "property_signature", "public_field_definition"):
                owner.fields.append(self._field(member))
            elif kind == "method_definition":
                owner.methods.append(self._method(member))

    def _build(self, b: _TypeBuilder) -> TSClass:
        node = b.node
        modifiers = self._modifiers(node)
        superclass: str | None = None
        interfaces: tuple[str, ...] = ()
        if b.kind is TSTypeKind.INTERFACE:
            interfaces = self._type_list(node.child_by_field_name("extends"))
        else:
            if extends := node.child_by_field_name("extends"):
                superclass = self._type(extends)
            interfaces = self._type_list(node.child_by_field_name("implements"))
        return TSClass(
            name=b.name,
            kind=b.kind,
            file=self._file.relative_path,
            is_test=self._file.is_test,
            start_line=self._line(node),
            end_line=self._end_line(node),
            modifiers=modifiers,
            imports=tuple(self._imports),
            superclass=superclass,
            interfaces=interfaces,
            fields=tuple(b.fields),
            methods=tuple(b.methods),
            enclosing=b.enclosing,
        )

    def _field(self, node: Node) -> TSField:
        name = node.child_by_field_name("name")
        type_node = node.child_by_field_name("type")
        modifiers = self._modifiers(node)
        return TSField(
            name=self._text(name) if name else "?",
            type=self._type_from_annotation(type_node) if type_node else "any",
            modifiers=modifiers,
            start_line=self._line(node),
            end_line=self._end_line(node),
        )

    def _method(self, node: Node) -> TSMethod:
        name = node.child_by_field_name("name")
        params = node.child_by_field_name("parameters")
        parameters = tuple(self._parameter(p) for p in params.named_children
                           if p.type in ("required_parameter", "optional_parameter")) if params else ()
        return_type = None
        if type_node := node.child_by_field_name("return_type"):
            return_type = self._type_from_annotation(type_node)
        body = node.child_by_field_name("body")
        return TSMethod(
            name=self._text(name) if name else "?",
            return_type=return_type,
            parameters=parameters,
            modifiers=self._modifiers(node),
            start_line=self._line(node),
            end_line=self._end_line(node),
            has_body=body is not None,
            calls=self._calls(body),
        )

    def _calls(self, body: Node | None) -> tuple[TSCall, ...]:
        """Llamadas con nombre (`f()` o `obj.f()`), en orden de aparición."""
        if body is None:
            return ()
        calls: list[TSCall] = []
        for node in _walk(body):
            if node.type != "call_expression":
                continue
            func = node.child_by_field_name("function")
            receiver = None
            if func is not None and func.type == "member_expression":
                obj = func.child_by_field_name("object")
                receiver = self._text(obj) if obj is not None else None
                func = func.child_by_field_name("property")
            if func is not None and func.type in ("identifier", "property_identifier"):
                calls.append(TSCall(self._text(func), receiver, self._span(func)))
        return tuple(calls)

    def _parameter(self, node: Node) -> str:
        pattern = node.child_by_field_name("pattern")
        type_node = node.child_by_field_name("type")
        param_type = self._type_from_annotation(type_node) if type_node else "any"
        optional = "?" if node.type == "optional_parameter" else ""
        return f"{self._pattern(pattern) if pattern else '?'}{optional}: {param_type}"

    def _pattern(self, node: Node) -> str:
        """Nombre de un parámetro; los desestructurados se resumen a sus nombres: "{ label, size }"."""
        match node.type:
            case "object_pattern":
                return "{ " + ", ".join(self._pattern(c) for c in node.named_children) + " }"
            case "array_pattern":
                return "[" + ", ".join(self._pattern(c) for c in node.named_children) + "]"
            case "rest_pattern":
                return "..." + "".join(self._pattern(c) for c in node.named_children)
            case "object_assignment_pattern" | "assignment_pattern":  # con valor por defecto
                left = node.child_by_field_name("left")
                return self._pattern(left) if left else self._text(node)
            case "pair_pattern":  # { a: { deep } } → se muestra la clave
                key = node.child_by_field_name("key")
                return self._text(key) if key else self._text(node)
            case _:
                return self._text(node)

    def _type_from_annotation(self, node: Node) -> str:
        """Extrae el tipo de un type_annotation (sin los ':')."""
        # type_annotation tiene como primer hijo ':' y luego el tipo real
        for child in node.children:
            if child.type != ":":
                return self._type(child)
        return "any"

    def _returns_jsx(self, body: Node | None) -> bool:
        """True si la función devuelve JSX: `return (<div/>)`, `cond ? <a/> : null` o `() => <b/>`."""
        if body is None:
            return False
        if body.type != "statement_block":  # arrow function con expresión: () => <h1/>
            return _is_jsx(body)
        return any(node.type == "return_statement" and any(_is_jsx(c) for c in node.named_children)
                   for node in _walk(body))

    def _uses_hooks(self, body: Node | None) -> bool:
        """True si el cuerpo llama a useState/useEffect/etc."""
        if body is None:
            return False
        for node in _walk(body):
            if node.type == "call_expression":
                func = node.child_by_field_name("function")
                if func and func.type == "member_expression":  # React.useState(…)
                    func = func.child_by_field_name("property")
                if func and func.type in ("identifier", "property_identifier"):
                    text = self._text(func)
                    if text in _HOOK_NAMES or _CUSTOM_HOOK.fullmatch(text):
                        return True
        return False

    def _modifiers(self, node: Node) -> tuple[str, ...]:
        modifiers: list[str] = []
        for child in node.children:
            if child.type in ("public", "private", "protected", "readonly", "static", "abstract", "async"):
                modifiers.append(self._text(child))
            elif child.type == "export_statement":
                modifiers.append("export")
            elif child.type == "default":
                modifiers.append("default")
        return tuple(modifiers)

    def _type_list(self, node: Node | None) -> tuple[str, ...]:
        if node is None:
            return ()
        return tuple(self._type(t) for t in node.named_children)

    # --- utilidades ---------------------------------------------------------------------

    def _text(self, node: Node) -> str:
        return self._source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _type(self, node: Node) -> str:
        return normalize_ts_type(self._text(node))

    def _line(self, node: Node) -> int:
        return node.start_point.row + 1

    def _end_line(self, node: Node) -> int:
        return node.end_point.row + 1

    def _span(self, node: Node) -> TSSourceSpan:
        start, end = node.start_point, node.end_point
        return TSSourceSpan(start.row + 1, self._column(start.row, start.column),
                            end.row + 1, self._column(end.row, end.column))

    def _column(self, row: int, byte_column: int) -> int:
        """tree-sitter cuenta bytes UTF-8; el resto de CodeQuest, caracteres ("año" mide 3, no 4)."""
        start = self._line_starts[row]
        return len(self._source[start:start + byte_column].decode("utf-8", errors="replace"))


def _is_jsx(node: Node | None) -> bool:
    """JSX, aunque vaya entre paréntesis o dentro de un ternario / `&&`."""
    if node is None:
        return False
    match node.type:
        case t if t in _JSX:
            return True
        case "parenthesized_expression":
            return any(_is_jsx(c) for c in node.named_children)
        case "ternary_expression":
            return _is_jsx(node.child_by_field_name("consequence")) or _is_jsx(node.child_by_field_name("alternative"))
        case "binary_expression":
            return _is_jsx(node.child_by_field_name("right"))
        case _:
            return False


def _unwrap_function(node: Node | None) -> Node | None:
    """La función de `() => …`, `function () {…}` o de un envoltorio como memo(…)/forwardRef(…)."""
    while node is not None:
        if node.type in _FUNCTION_VALUES:
            return node
        if node.type == "call_expression":
            func = node.child_by_field_name("function")
            callee = func.child_by_field_name("property") if func and func.type == "member_expression" else func
            if callee is None or callee.text not in _WRAPPERS:
                return None
            node = node.child_by_field_name("arguments")
        elif node.type not in ("parenthesized_expression", "as_expression", "arguments"):
            return None
        node = node.named_children[0] if node is not None and node.named_children else None
    return None


def _walk(node: Node) -> Iterator[Node]:
    """Recorre el árbol en profundidad."""
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.named_children))
