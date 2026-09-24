"""Parser Java basado en tree-sitter: estructura de tipos, anotaciones, campos, métodos y llamadas.

tree-sitter construye el árbol sintáctico completo y tolera código a medio escribir (marca los
trozos rotos como ERROR y sigue). Aquí solo se traduce ese árbol a los modelos inmutables de
`models.py`: el resto de CodeQuest no conoce tree-sitter.
"""

import logging
import re
from collections.abc import Iterator
from dataclasses import dataclass, field

import tree_sitter_java
from tree_sitter import Language, Node, Parser

from codequest.core.analysis.base import SourceParser
from codequest.core.analysis.java.models import (
    JavaAnnotation,
    JavaClass,
    JavaField,
    JavaMethod,
    JavaParameter,
    MethodCall,
    SourceSpan,
    TypeKind,
)
from codequest.core.project.models import SourceFile

log = logging.getLogger(__name__)

JAVA = Language(tree_sitter_java.language())

_TYPE_KINDS = {
    "class_declaration": TypeKind.CLASS,
    "interface_declaration": TypeKind.INTERFACE,
    "enum_declaration": TypeKind.ENUM,
    "record_declaration": TypeKind.RECORD,
    "annotation_type_declaration": TypeKind.ANNOTATION,
}
_ANNOTATIONS = frozenset({"annotation", "marker_annotation"})
_SPACES = re.compile(r"\s+")
_SPACE_AROUND_BRACKETS = re.compile(r"\s*([<>\[\]])\s*")
_SPACE_AROUND_COMMA = re.compile(r"\s*,\s*")


def normalize_type(text: str) -> str:
    """'Map< String ,  List<X> >' -> 'Map<String, List<X>>'."""
    text = _SPACES.sub(" ", text).strip()
    text = _SPACE_AROUND_BRACKETS.sub(r"\1", text)
    return _SPACE_AROUND_COMMA.sub(", ", text)


class TreeSitterJavaParser(SourceParser):
    def __init__(self) -> None:
        self._parser = Parser(JAVA)

    def supports(self, file: SourceFile) -> bool:
        return file.extension == ".java"

    def parse(self, file: SourceFile, text: str) -> list[JavaClass]:
        source = text.encode("utf-8")
        tree = self._parser.parse(source)
        if tree.root_node.has_error:
            log.debug("%s tiene errores de sintaxis; se analiza lo reconocible", file.relative_path)
        return _FileReader(file, source, tree.root_node).read()


@dataclass
class _TypeBuilder:
    """Acumula los miembros de un tipo mientras se recorre su cuerpo."""

    name: str
    kind: TypeKind
    enclosing: str | None
    node: Node
    fields: list[JavaField] = field(default_factory=list)
    methods: list[JavaMethod] = field(default_factory=list)
    enum_constants: list[str] = field(default_factory=list)

    @property
    def path(self) -> str:
        return f"{self.enclosing}.{self.name}" if self.enclosing else self.name


class _FileReader:
    def __init__(self, file: SourceFile, source: bytes, root: Node) -> None:
        self._file = file
        self._source = source
        self._root = root
        self._line_starts = [0] + [i + 1 for i, b in enumerate(source) if b == 0x0A]
        self._package = ""
        self._imports: list[str] = []
        self._classes: list[JavaClass] = []

    def read(self) -> list[JavaClass]:
        for node in self._root.named_children:
            if node.type == "package_declaration":
                self._package = self._text(_first(node, "scoped_identifier", "identifier"))
            elif node.type == "import_declaration":
                self._add_import(node)
            elif node.type in _TYPE_KINDS:
                self._read_type(node, enclosing=None)
        return self._classes

    def _add_import(self, node: Node) -> None:
        name = _first(node, "scoped_identifier", "identifier")
        if name is not None:
            suffix = ".*" if any(c.type == "asterisk" for c in node.children) else ""
            self._imports.append(self._text(name) + suffix)

    # --- tipos --------------------------------------------------------------------

    def _read_type(self, node: Node, enclosing: str | None) -> None:
        name = node.child_by_field_name("name")
        if name is None:
            return
        builder = _TypeBuilder(self._text(name), _TYPE_KINDS[node.type], enclosing, node)
        position = len(self._classes)  # el tipo va antes que sus tipos anidados
        if builder.kind is TypeKind.RECORD and (components := node.child_by_field_name("parameters")):
            builder.fields.extend(self._record_component(p) for p in components.named_children
                                  if p.type == "formal_parameter")
        if body := node.child_by_field_name("body"):
            self._read_body(body, builder)
        self._classes.insert(position, self._build(builder))

    def _read_body(self, body: Node, owner: _TypeBuilder) -> None:
        for member in body.named_children:
            kind = member.type
            if kind in _TYPE_KINDS:
                self._read_type(member, owner.path)
            elif kind in ("field_declaration", "constant_declaration"):
                self._add_fields(member, owner)
            elif kind in ("method_declaration", "annotation_type_element_declaration"):
                self._add_method(member, owner, is_constructor=False)
            elif kind == "constructor_declaration":
                self._add_method(member, owner, is_constructor=True)
            elif kind == "enum_constant":
                if name := member.child_by_field_name("name"):
                    owner.enum_constants.append(self._text(name))
            elif kind == "enum_body_declarations":
                self._read_body(member, owner)

    def _build(self, b: _TypeBuilder) -> JavaClass:
        node = b.node
        modifiers, annotations = self._modifiers(node)
        superclass: str | None = None
        interfaces: tuple[str, ...] = ()
        if b.kind is TypeKind.INTERFACE:
            interfaces = self._type_list(_first(node, "extends_interfaces"))
        else:
            if (extends := node.child_by_field_name("superclass")) and extends.named_children:
                superclass = self._type(extends.named_children[0])
            interfaces = self._type_list(node.child_by_field_name("interfaces"))
        return JavaClass(
            name=b.name,
            package=self._package,
            kind=b.kind,
            file=self._file.relative_path,
            is_test=self._file.is_test,
            start_line=self._line(node),
            end_line=self._end_line(node),
            modifiers=modifiers,
            annotations=annotations,
            imports=tuple(self._imports),
            superclass=superclass,
            interfaces=interfaces,
            fields=tuple(b.fields),
            methods=tuple(b.methods),
            enum_constants=tuple(b.enum_constants),
            enclosing=b.enclosing,
        )

    def _type_list(self, node: Node | None) -> tuple[str, ...]:
        if node is None or (types := _first(node, "type_list")) is None:
            return ()
        return tuple(self._type(t) for t in types.named_children)

    # --- miembros -----------------------------------------------------------------

    def _add_fields(self, node: Node, owner: _TypeBuilder) -> None:
        modifiers, annotations = self._modifiers(node)
        type_node = node.child_by_field_name("type")
        if type_node is None:
            return
        field_type = self._type(type_node)
        start, end = self._line(node), self._end_line(node)
        for declarator in node.children_by_field_name("declarator"):
            if name := declarator.child_by_field_name("name"):
                dims = declarator.child_by_field_name("dimensions")
                owner.fields.append(JavaField(self._text(name), field_type + (self._type(dims) if dims else ""),
                                              modifiers, annotations, start, end))

    def _add_method(self, node: Node, owner: _TypeBuilder, is_constructor: bool) -> None:
        name = node.child_by_field_name("name")
        if name is None:
            return
        modifiers, annotations = self._modifiers(node)
        return_type = None
        if not is_constructor and (type_node := node.child_by_field_name("type")):
            return_type = self._type(type_node)
            if dims := node.child_by_field_name("dimensions"):
                return_type += self._type(dims)
        params = node.child_by_field_name("parameters")
        parameters = tuple(self._parameter(p) for p in params.named_children
                           if p.type in ("formal_parameter", "spread_parameter")) if params else ()
        throws = _first(node, "throws")
        body = node.child_by_field_name("body")
        owner.methods.append(JavaMethod(
            name=self._text(name),
            return_type=return_type,
            parameters=parameters,
            modifiers=modifiers,
            annotations=annotations,
            throws=tuple(self._type(t) for t in throws.named_children) if throws else (),
            start_line=self._line(node),
            end_line=self._end_line(node),
            has_body=body is not None,
            calls=tuple(self._calls(body)) if body is not None else (),
        ))

    def _parameter(self, node: Node) -> JavaParameter:
        _, annotations = self._modifiers(node)
        type_node = node.child_by_field_name("type") or _first(node, *_TYPE_NODES)
        param_type = self._type(type_node) if type_node else "?"
        name = node.child_by_field_name("name")
        if node.type == "spread_parameter":  # String... tags
            param_type += "..."
            declarator = _first(node, "variable_declarator")
            name = declarator.child_by_field_name("name") if declarator else None
        if dims := node.child_by_field_name("dimensions"):
            param_type += self._type(dims)
        return JavaParameter(self._text(name) if name else "?", param_type, annotations)

    def _record_component(self, node: Node) -> JavaField:
        param = self._parameter(node)
        line = self._line(node)
        return JavaField(param.name, param.type, ("private", "final"), param.annotations, line, line)

    def _calls(self, body: Node) -> Iterator[MethodCall]:
        """Llamadas del cuerpo en orden de aparición, sin entrar en clases anónimas o locales."""
        stack = [body]
        while stack:
            node = stack.pop()
            if node.type == "method_invocation" and (name := node.child_by_field_name("name")):
                receiver = node.child_by_field_name("object")
                arguments = node.child_by_field_name("arguments")
                yield MethodCall(
                    name=self._text(name),
                    receiver=self._text(receiver) if receiver else None,
                    arguments=" ".join(self._text(arguments)[1:-1].split()) if arguments else "",
                    name_span=self._span(name),
                )
            stack.extend(c for c in reversed(node.named_children) if c.type != "class_body")

    # --- modificadores y anotaciones ---------------------------------------------------

    def _modifiers(self, node: Node) -> tuple[tuple[str, ...], tuple[JavaAnnotation, ...]]:
        modifiers_node = _first(node, "modifiers")
        if modifiers_node is None:
            return (), ()
        words: list[str] = []
        annotations: list[JavaAnnotation] = []
        for child in modifiers_node.children:
            if child.type in _ANNOTATIONS:
                annotations.append(self._annotation(child))
            elif not child.is_extra:  # comentarios entre modificadores
                words.append(self._text(child))
        return tuple(words), tuple(annotations)

    def _annotation(self, node: Node) -> JavaAnnotation:
        name = node.child_by_field_name("name")
        args = node.child_by_field_name("arguments")
        arguments = " ".join(self._text(args)[1:-1].split()) if args else None
        name_text = self._text(name) if name else ""
        name_span = None
        if name is not None:
            start = self._span(node)
            end = self._span(name)
            name_span = SourceSpan(start.line, start.column, end.end_line, end.end_column)
        return JavaAnnotation(name_text.rsplit(".", 1)[-1], arguments, self._line(node),
                              span=self._span(node), name_span=name_span)

    # --- utilidades ---------------------------------------------------------------------

    def _text(self, node: Node) -> str:
        return self._source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _type(self, node: Node) -> str:
        return normalize_type(self._text(node))

    def _line(self, node: Node) -> int:
        return node.start_point.row + 1

    def _end_line(self, node: Node) -> int:
        return node.end_point.row + 1

    def _span(self, node: Node) -> SourceSpan:
        start, end = node.start_point, node.end_point
        return SourceSpan(start.row + 1, self._column(start.row, start.column),
                          end.row + 1, self._column(end.row, end.column))

    def _column(self, row: int, byte_column: int) -> int:
        """tree-sitter cuenta bytes UTF-8; el resto de CodeQuest, caracteres ("año" mide 3, no 4)."""
        start = self._line_starts[row]
        return len(self._source[start:start + byte_column].decode("utf-8", errors="replace"))


_TYPE_NODES = ("type_identifier", "generic_type", "scoped_type_identifier", "array_type", "integral_type",
               "floating_point_type", "boolean_type")


def _first(node: Node, *types: str) -> Node | None:
    return next((c for c in node.children if c.type in types), None)
