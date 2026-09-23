"""Selección del contexto mínimo que se envía a la IA sobre una pregunta.

Código real solo del fragmento de la pregunta. De la clase y de sus dependencias directas
(tipos del proyecto usados en campos o parámetros) se envía un resumen generado desde el
modelo: anotaciones, campos y firmas de métodos, sin cuerpos. Nunca el proyecto entero.
"""

import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from codequest.core.analysis.java.models import JavaClass, TypeKind
from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.snippets import SnippetRef, read_snippet

MAX_SNIPPET_LINES = 60
MAX_RELATED_CLASSES = 2
MAX_OUTLINE_MEMBERS = 30
MAX_CONTEXT_CHARS = 8000
_TYPE_NAME = re.compile(r"[A-Z]\w*")


@dataclass(frozen=True, slots=True)
class ContextPart:
    title: str  # "UserController.java · líneas 25–28" o "Resumen de UserService"
    text: str
    is_source: bool  # True: código real del proyecto; False: resumen generado


@dataclass(frozen=True, slots=True)
class CodeContext:
    parts: tuple[ContextPart, ...]

    @property
    def char_count(self) -> int:
        return sum(len(p.text) for p in self.parts)

    def render(self) -> str:
        """Texto que se envía a la IA."""
        return "\n\n".join(f"### {p.title}\n{p.text}" for p in self.parts)

    def summary(self) -> list[str]:
        """Descripción para el estudiante de lo que se enviará."""
        return [f"{p.title} ({'código' if p.is_source else 'solo firmas, sin código'})" for p in self.parts]


class ContextBuilder:
    def __init__(self, model: ProjectModel) -> None:
        self._model = model
        self._by_name = {c.name: c for c in model.main_classes}
        self._by_qualified = {c.qualified_name: c for c in model.classes}

    def build(self, class_name: str, snippet: SnippetRef | None) -> CodeContext:
        cls = self._by_qualified.get(class_name)
        parts: list[ContextPart] = []
        if snippet is not None:
            parts.append(self._snippet_part(snippet))
        if cls is not None:
            parts.append(ContextPart(f"Resumen de {cls.name}", outline(cls), is_source=False))
            for related in self._related(cls):
                part = ContextPart(f"Resumen de {related.name}", outline(related), is_source=False)
                if sum(len(p.text) for p in parts) + len(part.text) > MAX_CONTEXT_CHARS:
                    break
                parts.append(part)
        return CodeContext(tuple(parts))

    def _snippet_part(self, ref: SnippetRef) -> ContextPart:
        end = min(ref.end_line, ref.start_line + MAX_SNIPPET_LINES - 1)
        snippet = read_snippet(Path(self._model.info.root), ref.file, ref.start_line, end)
        numbered = "\n".join(f"{snippet.start_line + i:>4} | {line}"
                             for i, line in enumerate(snippet.text.splitlines()))
        title = f"{PurePosixPath(ref.file).name} · líneas {snippet.start_line}–{snippet.end_line}"
        if ref.focus_lines:
            title += f" (la pregunta trata sobre la línea {ref.focus_lines[0]})"
        return ContextPart(title, numbered[:MAX_CONTEXT_CHARS], is_source=True)

    def _related(self, cls: JavaClass) -> list[JavaClass]:
        """Tipos del proyecto que la clase usa en campos, constructores o parámetros."""
        type_texts = [f.type for f in cls.fields]
        type_texts += [p.type for m in cls.methods for p in m.parameters]
        type_texts += [m.return_type or "" for m in cls.methods]
        type_texts += list(cls.interfaces) + ([cls.superclass] if cls.superclass else [])
        related: list[JavaClass] = []
        for text in type_texts:
            for name in _TYPE_NAME.findall(text):
                other = self._by_name.get(name)
                if other is not None and other is not cls and other not in related:
                    related.append(other)
                if len(related) == MAX_RELATED_CLASSES:
                    return related
        return related


def outline(cls: JavaClass) -> str:
    """Resumen de una clase sin cuerpos de métodos: lo justo para entender cómo se usa."""
    lines = [f"// {cls.qualified_name}"]
    lines += [a.display for a in cls.annotations]
    header = " ".join([*cls.modifiers, cls.kind.value, cls.name])
    if cls.superclass:
        header += f" extends {cls.superclass}"
    if cls.interfaces:
        header += (" extends " if cls.kind is TypeKind.INTERFACE else " implements ") + ", ".join(cls.interfaces)
    lines.append(header + " {")
    if cls.enum_constants:
        lines.append("    " + ", ".join(cls.enum_constants) + ";")
    members = 0
    for f in cls.fields:
        annotations = " ".join(a.display for a in f.annotations)
        lines.append("    " + " ".join(p for p in (annotations, *f.modifiers, f.type, f.name) if p) + ";")
        members += 1
    for m in cls.methods:
        if members >= MAX_OUTLINE_MEMBERS:
            lines.append("    // …")
            break
        annotations = " ".join(a.display for a in m.annotations)
        params = ", ".join(" ".join([*(a.display for a in p.annotations), p.type, p.name]) for p in m.parameters)
        signature = " ".join(x for x in (annotations, *m.modifiers, m.return_type or "", f"{m.name}({params})") if x)
        lines.append(f"    {signature};")
        members += 1
    lines.append("}")
    return "\n".join(lines)
