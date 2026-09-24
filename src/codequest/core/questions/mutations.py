"""Errores creíbles para "Encuentra el error".

Cada mutación cambia una anotación por otra en una sola línea y explica por qué, en ese
contexto, el resultado es un error. Solo es una receta: se aplica sobre una copia en memoria
del fragmento (`CodeMutation.apply`), nunca sobre el archivo del estudiante.
"""

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

from codequest.core.analysis.java.models import JavaAnnotation, JavaClass, JavaMethod
from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.package_tree import display_name
from codequest.core.analysis.snippets import SnippetRef
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.questions.models import CodeMutation, QuestionDraft
from codequest.core.questions.rules import MAX_HEADER_LINES, MAX_METHOD_LINES, QuestionRule

PROMPT = "Hay algo extraño en este código. ¿En qué línea está el error?"
FIELD_CONTEXT_LINES = 4  # líneas vecinas alrededor de un campo: que el error no sea la única línea
_COLLECTION = re.compile(r"\b(List|Set|Collection|Iterable|Map)\s*<")


@dataclass(frozen=True, slots=True)
class Swap:
    target: str  # anotación que sustituye a la original (sin "@")
    explanation: str  # plantilla con {cls}, {member}, {param} o {field}
    applies: Callable[[str], bool] = lambda _type: True  # recibe el tipo del campo o parámetro
    keep_arguments: bool = False  # la ruta de un @GetMapping("/x") sigue teniendo sentido en @PostMapping


def _is_collection(type_: str) -> bool:
    return bool(_COLLECTION.search(type_))


# Anotación original -> sustitución que la convierte en un error.
SWAPS: dict[str, Swap] = {
    "GetMapping": Swap(
        "PostMapping",
        "`{member}` consulta datos, así que debe responder a peticiones GET. Con `@PostMapping` solo "
        "respondería a POST, y abrir la ruta desde el navegador daría un error 405.",
        keep_arguments=True),
    "PostMapping": Swap(
        "GetMapping",
        "`{member}` recibe datos del cliente para procesarlos: eso es un POST. Con `@GetMapping` "
        "respondería a GET, que no debe cambiar nada y normalmente no lleva cuerpo.",
        keep_arguments=True),
    "PutMapping": Swap(
        "GetMapping",
        "`{member}` actualiza un recurso. Con `@GetMapping` una simple consulta a la ruta intentaría "
        "modificar datos, y el cuerpo con los datos nuevos no llegaría.",
        keep_arguments=True),
    "DeleteMapping": Swap(
        "GetMapping",
        "`{member}` elimina un recurso. Con `@GetMapping` cualquier visita a la ruta (un enlace, un "
        "buscador que la rastrea) borraría datos: GET nunca debe modificar nada.",
        keep_arguments=True),
    "PathVariable": Swap(
        "RequestBody",
        "`{param}` forma parte de la URL (como el 42 de `/users/42`). Con `@RequestBody` Spring lo "
        "buscaría en el cuerpo JSON de la petición, que aquí no existe."),
    "RequestBody": Swap(
        "PathVariable",
        "`{param}` llega como JSON en el cuerpo de la petición. Con `@PathVariable` Spring lo buscaría "
        "en la URL y la petición fallaría al no encontrarlo."),
    "RestController": Swap(
        "Service",
        "`{cls}` atiende peticiones HTTP. Con `@Service` Spring la registraría como un servicio más y "
        "sus rutas dejarían de existir: todas las peticiones darían 404."),
    "Entity": Swap(
        "Component",
        "`{cls}` representa una tabla de la base de datos. Sin `@Entity`, JPA no la reconoce: no se "
        "mapea la tabla y los repositorios de `{cls}` fallan al arrancar."),
    "Id": Swap(
        "Column",
        "`{field}` es la clave primaria. Con `@Column` en lugar de `@Id` la entidad se queda sin "
        "identificador y la aplicación no arranca: toda entidad necesita un `@Id`."),
    "OneToMany": Swap(
        "ManyToOne",
        "`{field}` es una colección: un `{cls}` tiene muchos elementos. `@ManyToOne` espera un único "
        "objeto, así que la relación queda al revés.",
        applies=_is_collection),
    "ManyToOne": Swap(
        "OneToMany",
        "`{field}` es un único objeto: muchos `{cls}` apuntan a uno. `@OneToMany` espera una colección, "
        "así que la relación queda al revés.",
        applies=lambda type_: not _is_collection(type_)),
}


class FindErrorRule(QuestionRule):
    """Un borrador por cada anotación conocida que tiene una sustitución creíble en su contexto."""

    def drafts(self, model: ProjectModel, kb: KnowledgeBase) -> Iterator[QuestionDraft]:
        for cls in model.main_classes:
            name = display_name(cls)
            header = _header(cls)
            yield from _drafts(cls, cls.annotations, header, kb, "", {"cls": name})
            for field in cls.fields:
                region = SnippetRef(cls.file, max(cls.start_line, field.start_line - FIELD_CONTEXT_LINES),
                                    min(cls.end_line, field.end_line + FIELD_CONTEXT_LINES))
                yield from _drafts(cls, field.annotations, region, kb, field.name,
                                   {"cls": name, "field": field.name}, field.type)
            for method in cls.methods:
                yield from _method_drafts(cls, name, method, kb)


def _method_drafts(cls: JavaClass, name: str, method: JavaMethod, kb: KnowledgeBase) -> Iterator[QuestionDraft]:
    region = SnippetRef(cls.file, method.start_line, min(method.end_line, method.start_line + MAX_METHOD_LINES))
    member = f"{method.name}()"
    values = {"cls": name, "member": member}
    yield from _drafts(cls, method.annotations, region, kb, member, values)
    for param in method.parameters:
        yield from _drafts(cls, param.annotations, region, kb, f"{member}:{param.name}",
                           {**values, "param": param.name}, param.type)


def _drafts(cls: JavaClass, annotations: tuple[JavaAnnotation, ...], region: SnippetRef, kb: KnowledgeBase,
            member: str, values: dict[str, str], member_type: str = "") -> Iterator[QuestionDraft]:
    present = {a.name for a in annotations}
    for ann in annotations:
        swap = SWAPS.get(ann.name)
        concept = kb.for_annotation(ann.name)
        # Si el elemento ya tiene la anotación destino (p. ej. `@Id @Column`), el cambio no se notaría.
        if swap is None or concept is None or swap.target in present or not swap.applies(member_type):
            continue
        if not region.start_line <= ann.line <= region.end_line:
            continue
        yield QuestionDraft(
            key=f"error:{concept.id}:{cls.qualified_name}#{member}",
            prompt=PROMPT, concept=concept, class_name=cls.qualified_name, snippet=region,
            mutation=CodeMutation(
                line=ann.line, find=f"@{ann.name}", replace=f"@{swap.target}",
                explanation=swap.explanation.format(**{"member": "", "param": "", "field": "", **values}),
                drop_arguments=not swap.keep_arguments,
            ),
        )


def _header(cls: JavaClass) -> SnippetRef:
    """Cabecera de la clase con algo de cuerpo: el error no debe ser la última línea visible."""
    members = [*cls.fields, *cls.methods]
    first_member = min((m.start_line for m in members), default=cls.end_line)
    end = min(first_member + 2, cls.start_line + MAX_HEADER_LINES, cls.end_line)
    return SnippetRef(cls.file, cls.start_line, max(cls.start_line, end))


FIND_ERROR_RULES: tuple[QuestionRule, ...] = (FindErrorRule(),)
