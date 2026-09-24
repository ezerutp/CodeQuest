"""Reglas que convierten hechos del código en preguntas.

Cada regla recorre el ProjectModel y, para lo que reconoce (una anotación conocida, un
repositorio de Spring Data…), produce borradores con enunciado, concepto y fragmento.
"""

from abc import ABC, abstractmethod
from collections.abc import Iterator

from codequest.core.analysis.java.conventions import simple_type_name
from codequest.core.analysis.java.models import JavaAnnotation, JavaClass, JavaField, JavaMethod
from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.package_tree import display_name
from codequest.core.analysis.snippets import SnippetRef
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.questions.models import QuestionDraft

MAX_METHOD_LINES = 18
MAX_HEADER_LINES = 10


class QuestionRule(ABC):
    @abstractmethod
    def drafts(self, model: ProjectModel, kb: KnowledgeBase) -> Iterator[QuestionDraft]: ...


class AnnotationPurposeRule(QuestionRule):
    """"¿Qué hace @X aquí?" para cada anotación conocida en clases, campos, métodos y parámetros."""

    def drafts(self, model: ProjectModel, kb: KnowledgeBase) -> Iterator[QuestionDraft]:
        for cls in model.main_classes:
            name = display_name(cls)
            header = _header_snippet(cls)
            for ann in cls.annotations:
                if concept := kb.for_annotation(ann.name):
                    yield QuestionDraft(
                        key=_key(concept.id, cls),
                        prompt=f"¿Qué función cumple `@{ann.name}` en la clase `{name}`?",
                        concept=concept, class_name=cls.qualified_name, snippet=_focus(header, ann),
                    )
            for field in cls.fields:
                snippet = SnippetRef(cls.file, field.start_line, field.end_line)
                for ann in field.annotations:
                    if concept := kb.for_annotation(ann.name):
                        yield QuestionDraft(
                            key=_key(concept.id, cls, field.name),
                            prompt=f"En el campo `{field.name}` de `{name}`, ¿qué indica `@{ann.name}`?",
                            concept=concept, class_name=cls.qualified_name, snippet=_focus(snippet, ann),
                        )
            for method in cls.methods:
                yield from self._method_drafts(cls, name, method, kb)

    def _method_drafts(self, cls: JavaClass, name: str, method: JavaMethod,
                       kb: KnowledgeBase) -> Iterator[QuestionDraft]:
        snippet = SnippetRef(cls.file, method.start_line, min(method.end_line, method.start_line + MAX_METHOD_LINES))
        member = f"{method.name}({', '.join(p.type for p in method.parameters)})"
        where = f"el constructor de `{name}`" if method.is_constructor else f"tu método `{method.name}()` de `{name}`"
        for ann in method.annotations:
            if concept := kb.for_annotation(ann.name):
                yield QuestionDraft(
                    key=_key(concept.id, cls, member),
                    prompt=f"En {where}, ¿qué propósito tiene `@{ann.name}`?",
                    concept=concept, class_name=cls.qualified_name, snippet=_focus(snippet, ann),
                )
        for param in method.parameters:
            for ann in param.annotations:
                if concept := kb.for_annotation(ann.name):
                    yield QuestionDraft(
                        key=_key(concept.id, cls, f"{member}:{param.name}"),
                        prompt=f"En `{method.name}()`, ¿qué hace `@{ann.name}` con el parámetro `{param.name}`?",
                        concept=concept, class_name=cls.qualified_name, snippet=_focus(snippet, ann),
                    )


class SupertypeRule(QuestionRule):
    """"¿Qué obtiene UserRepository al extender JpaRepository?"."""

    def drafts(self, model: ProjectModel, kb: KnowledgeBase) -> Iterator[QuestionDraft]:
        for cls in model.main_classes:
            for supertype in (*cls.interfaces, *([cls.superclass] if cls.superclass else [])):
                if concept := kb.for_supertype(simple_type_name(supertype)):
                    header = _header_snippet(cls)
                    yield QuestionDraft(
                        key=_key(concept.id, cls),
                        prompt=f"¿Qué obtiene `{display_name(cls)}` al extender `{supertype}`?",
                        concept=concept, class_name=cls.qualified_name,
                        snippet=SnippetRef(header.file, header.start_line, header.end_line, (header.start_line,)),
                    )


class ExplainMethodRule(QuestionRule):
    """"Explica con tus palabras qué hace este método" para métodos reales y significativos.

    Solo métodos con cuerpo, de tamaño razonable y con una anotación conocida: el concepto
    sirve para el progreso y orienta al evaluador. Se descartan getters/setters y constructores.
    """

    MIN_LINES = 3
    MAX_LINES = 40

    def drafts(self, model: ProjectModel, kb: KnowledgeBase) -> Iterator[QuestionDraft]:
        for cls in model.main_classes:
            name = display_name(cls)
            for method in cls.methods:
                lines = method.end_line - method.start_line + 1
                if (method.is_constructor or not method.has_body
                        or not self.MIN_LINES <= lines <= self.MAX_LINES):
                    continue
                concept = next((c for a in method.annotations if (c := kb.for_annotation(a.name))), None)
                if concept is None:
                    continue
                member = f"{method.name}({', '.join(p.type for p in method.parameters)})"
                yield QuestionDraft(
                    key=f"explain:{cls.qualified_name}#{member}",
                    prompt=f"Explica con tus propias palabras qué hace el método `{method.name}()` de `{name}`.",
                    concept=concept, class_name=cls.qualified_name,
                    snippet=SnippetRef(cls.file, method.start_line, method.end_line),
                )


DEFAULT_RULES: tuple[QuestionRule, ...] = (AnnotationPurposeRule(), SupertypeRule())
EXPLAIN_RULES: tuple[QuestionRule, ...] = (ExplainMethodRule(),)


def _key(concept_id: str, cls: JavaClass, member: str = "") -> str:
    return f"{concept_id}:{cls.qualified_name}" + (f"#{member}" if member else "")


def _focus(snippet: SnippetRef, annotation: JavaAnnotation) -> SnippetRef:
    return SnippetRef(snippet.file, snippet.start_line, snippet.end_line, (annotation.line,))


def _header_snippet(cls: JavaClass) -> SnippetRef:
    """Cabecera de la clase: anotaciones y declaración, hasta antes del primer miembro."""
    members: list[JavaField | JavaMethod] = [*cls.fields, *cls.methods]
    first_member = min((m.start_line for m in members), default=cls.end_line + 1)
    end = min(first_member - 1, cls.start_line + MAX_HEADER_LINES, cls.end_line)
    return SnippetRef(cls.file, cls.start_line, max(cls.start_line, end))
