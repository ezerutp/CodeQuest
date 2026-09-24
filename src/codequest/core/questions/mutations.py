"""Errores creíbles para "Encuentra el error".

Cada mutación cambia un tramo de una sola línea (una anotación o el nombre de una llamada) y explica
por qué, en ese contexto, el resultado es un error. Las posiciones exactas vienen del parser
(tree-sitter); la mutación es solo una receta que se aplica sobre una copia en memoria del fragmento
(`CodeMutation.apply`), nunca sobre el archivo del estudiante.
"""

import re
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import dataclass, replace

from codequest.core.analysis.java.conventions import simple_type_name
from codequest.core.analysis.java.models import JavaAnnotation, JavaClass, JavaMethod, MethodCall, SourceSpan
from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.package_tree import display_name
from codequest.core.analysis.roles import ComponentRole
from codequest.core.analysis.snippets import SnippetRef
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.knowledge.models import Concept
from codequest.core.questions.models import CodeMutation, QuestionDraft
from codequest.core.questions.rules import MAX_HEADER_LINES, MAX_METHOD_LINES, QuestionRule

PROMPT = "Hay algo extraño en este código. ¿En qué línea está el error?"
FIX_PROMPT = "Este código tiene un error. Corrígelo para que vuelva a funcionar."
FIELD_CONTEXT_LINES = 4  # líneas vecinas alrededor de un campo: que el error no sea la única línea
_COLLECTION = re.compile(r"\b(List|Set|Collection|Iterable|Map)\s*<")


@dataclass(frozen=True, slots=True)
class Swap:
    target: str  # lo que sustituye al original: una anotación (sin "@") o un nombre de método
    explanation: str  # plantilla con {cls}, {member}, {param}, {field}, {call} o {receiver}
    applies: Callable[[str], bool] = lambda _type: True  # recibe el tipo del campo o parámetro
    keep_arguments: bool = False  # la ruta de un @GetMapping("/x") sigue teniendo sentido en @PostMapping


def _is_collection(type_: str) -> bool:
    return bool(_COLLECTION.search(type_))


# Anotación original -> sustitución que la convierte en un error.
ANNOTATION_SWAPS: dict[str, Swap] = {
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

# Método de un repositorio de Spring Data -> el que hace lo contrario.
REPOSITORY_SWAPS: dict[str, Swap] = {
    "save": Swap(
        "delete",
        "`{member}` debe guardar los datos con `{call}`. Con `delete` los borraría de la base de datos "
        "en vez de guardarlos."),
    "saveAll": Swap(
        "deleteAll",
        "`{member}` debe guardar todos esos registros con `{call}`. Con `deleteAll` los borraría."),
    "findById": Swap(
        "deleteById",
        "`{member}` necesita leer el registro con `{call}`. `deleteById` lo borraría, y además no devuelve "
        "nada con lo que seguir trabajando."),
    "findAll": Swap(
        "deleteAll",
        "`{member}` necesita leer todos los registros con `{call}`. `deleteAll` vaciaría la tabla entera."),
    "deleteById": Swap(
        "findById",
        "`{member}` debe eliminar el registro con `{call}`. Con `findById` solo lo buscaría: el registro "
        "seguiría en la base de datos."),
    "delete": Swap(
        "save",
        "`{member}` debe eliminar el registro con `{call}`. Con `save` lo volvería a guardar."),
}


class FindErrorRule(QuestionRule):
    """Un borrador por cada anotación o llamada a un repositorio con una sustitución creíble."""

    def drafts(self, model: ProjectModel, kb: KnowledgeBase) -> Iterator[QuestionDraft]:
        repositories = _repository_concepts(model, kb)
        for cls in model.main_classes:
            name = display_name(cls)
            yield from _annotation_drafts(cls, cls.annotations, _header(cls), kb, "", {"cls": name})
            for field in cls.fields:
                region = SnippetRef(cls.file, max(cls.start_line, field.start_line - FIELD_CONTEXT_LINES),
                                    min(cls.end_line, field.end_line + FIELD_CONTEXT_LINES))
                yield from _annotation_drafts(cls, field.annotations, region, kb, field.name,
                                              {"cls": name, "field": field.name}, field.type)
            for method in cls.methods:
                yield from _method_drafts(cls, name, method, kb, repositories)


def _method_drafts(cls: JavaClass, name: str, method: JavaMethod, kb: KnowledgeBase,
                   repositories: dict[str, Concept]) -> Iterator[QuestionDraft]:
    region = SnippetRef(cls.file, method.start_line, min(method.end_line, method.start_line + MAX_METHOD_LINES))
    member = f"{method.name}()"
    values = {"cls": name, "member": member}
    yield from _annotation_drafts(cls, method.annotations, region, kb, member, values)
    for param in method.parameters:
        yield from _annotation_drafts(cls, param.annotations, region, kb, f"{member}:{param.name}",
                                      {**values, "param": param.name}, param.type)
    yield from _call_drafts(cls, method, region, repositories, values)


def _annotation_drafts(cls: JavaClass, annotations: tuple[JavaAnnotation, ...], region: SnippetRef,
                       kb: KnowledgeBase, member: str, values: dict[str, str],
                       member_type: str = "") -> Iterator[QuestionDraft]:
    present = {a.name for a in annotations}
    for ann in annotations:
        swap = ANNOTATION_SWAPS.get(ann.name)
        concept = kb.for_annotation(ann.name)
        # Si el elemento ya tiene la anotación destino (p. ej. `@Id @Column`), el cambio no se notaría.
        if swap is None or concept is None or swap.target in present or not swap.applies(member_type):
            continue
        # Con los argumentos se cambia solo el nombre; sin ellos, toda la anotación: `@RequestBody("id")`
        # o `@ManyToOne(mappedBy = …)` delatarían el cambio.
        span = ann.name_span if swap.keep_arguments else ann.span
        original = f"@{ann.name}"
        # Nombres cualificados (`@org.x.Id`) o anotaciones en varias líneas: mejor no tocarlas.
        if (span is None or not span.is_single_line or ann.name_span is None
                or ann.name_span.end_column - ann.name_span.column != len(original)):
            continue
        yield _draft(f"error:{concept.id}:{cls.qualified_name}#{member}", concept, cls, region, span, original,
                     f"@{swap.target}", swap.explanation, values)


def _call_drafts(cls: JavaClass, method: JavaMethod, region: SnippetRef, repositories: dict[str, Concept],
                 values: dict[str, str]) -> Iterator[QuestionDraft]:
    types = {f.name: f.type for f in cls.fields} | {p.name: p.type for p in method.parameters}
    seen: Counter[str] = Counter()
    for call in method.calls:
        swap = REPOSITORY_SWAPS.get(call.name)
        receiver = _receiver(call)
        concept = repositories.get(simple_type_name(types.get(receiver or "", "")))
        if swap is None or concept is None:
            continue
        base = f"error:{concept.id}:{cls.qualified_name}#{values['member']}:{receiver}.{call.name}"
        seen[base] += 1
        key = base if seen[base] == 1 else f"{base}:{seen[base]}"
        call_text = f"{receiver}.{call.name}({call.arguments})"
        yield _draft(key, concept, cls, region, call.name_span, call.name, swap.target, swap.explanation,
                     {**values, "call": call_text, "receiver": receiver or ""})


def _draft(key: str, concept: Concept, cls: JavaClass, region: SnippetRef, span: SourceSpan, original: str,
           replacement: str, template: str, values: dict[str, str]) -> QuestionDraft:
    return QuestionDraft(
        key=key, prompt=PROMPT, concept=concept, class_name=cls.qualified_name, snippet=region,
        mutation=CodeMutation(
            line=span.line, column=span.column, end_column=span.end_column, original=original,
            replacement=replacement,
            explanation=template.format(**{"member": "", "param": "", "field": "", "call": "", "receiver": "",
                                           **values}),
        ),
    )


def _receiver(call: MethodCall) -> str | None:
    """`userRepository` o `this.userRepository` -> "userRepository"; otras expresiones no cuentan."""
    receiver = (call.receiver or "").removeprefix("this.")
    return receiver if receiver.isidentifier() else None


def _repository_concepts(model: ProjectModel, kb: KnowledgeBase) -> dict[str, Concept]:
    """Repositorios del proyecto (nombre simple) -> concepto de Spring Data que heredan."""
    found: dict[str, Concept] = {}
    for cls in model.classes:
        if model.role_of(cls) is ComponentRole.REPOSITORY:
            concept = next((c for t in cls.interfaces if (c := kb.for_supertype(simple_type_name(t)))), None)
            if concept is not None:
                found[cls.name] = concept
    return found


def _header(cls: JavaClass) -> SnippetRef:
    """Cabecera de la clase con algo de cuerpo: el error no debe ser la última línea visible."""
    members = [*cls.fields, *cls.methods]
    first_member = min((m.start_line for m in members), default=cls.end_line)
    end = min(first_member + 2, cls.start_line + MAX_HEADER_LINES, cls.end_line)
    return SnippetRef(cls.file, cls.start_line, max(cls.start_line, end))


class FixCodeRule(QuestionRule):
    """Los mismos errores que "Encuentra el error", pero para corregirlos editando el código."""

    def __init__(self, source: QuestionRule | None = None) -> None:
        self._source = source or FindErrorRule()

    def drafts(self, model: ProjectModel, kb: KnowledgeBase) -> Iterator[QuestionDraft]:
        for draft in self._source.drafts(model, kb):
            # Clave propia: acertar un modo no debe hacer que el otro evite la pregunta como "reciente".
            yield replace(draft, key="fix:" + draft.key.removeprefix("error:"), prompt=FIX_PROMPT)


FIND_ERROR_RULES: tuple[QuestionRule, ...] = (FindErrorRule(),)
FIX_CODE_RULES: tuple[QuestionRule, ...] = (FixCodeRule(),)
