"""Consulta de la base de conocimiento: por id, por anotación o por supertipo."""

from collections.abc import Iterable, Mapping

from codequest.core.knowledge.models import Concept

# Nombre simple de anotación -> id de concepto.
ANNOTATION_CONCEPTS: Mapping[str, str] = {
    "RestController": "spring.rest-controller",
    "Controller": "spring.controller",
    "RequestMapping": "spring.request-mapping",
    "GetMapping": "spring.get-mapping",
    "PostMapping": "spring.post-mapping",
    "PutMapping": "spring.put-mapping",
    "PatchMapping": "spring.patch-mapping",
    "DeleteMapping": "spring.delete-mapping",
    "PathVariable": "spring.path-variable",
    "RequestBody": "spring.request-body",
    "RequestParam": "spring.request-param",
    "Service": "spring.service",
    "Repository": "spring.repository-annotation",
    "Component": "spring.component",
    "Autowired": "spring.autowired",
    "Configuration": "spring.configuration",
    "Bean": "spring.bean",
    "Value": "spring.value",
    "SpringBootApplication": "spring.boot-application",
    "Transactional": "spring.transactional",
    "Entity": "jpa.entity",
    "Table": "jpa.table",
    "Id": "jpa.id",
    "GeneratedValue": "jpa.generated-value",
    "Column": "jpa.column",
    "OneToMany": "jpa.one-to-many",
    "ManyToOne": "jpa.many-to-one",
    "OneToOne": "jpa.one-to-one",
    "ManyToMany": "jpa.many-to-many",
    "JoinColumn": "jpa.join-column",
    "Query": "data.query",
    "Valid": "validation.valid",
    "NotBlank": "validation.not-blank",
    "ExceptionHandler": "errors.exception-handler",
    "RestControllerAdvice": "errors.controller-advice",
    "ControllerAdvice": "errors.controller-advice",
}

# Nombre simple de supertipo (extends/implements) -> id de concepto.
SUPERTYPE_CONCEPTS: Mapping[str, str] = {
    "JpaRepository": "data.jpa-repository",
    "CrudRepository": "data.crud-repository",
    "ListCrudRepository": "data.crud-repository",
}

MIN_DISTRACTORS = 3


class KnowledgeBase:
    def __init__(self, concepts: Iterable[Concept], annotation_index: Mapping[str, str],
                 supertype_index: Mapping[str, str]) -> None:
        self._concepts = {c.id: c for c in concepts}
        self._by_annotation = dict(annotation_index)
        self._by_supertype = dict(supertype_index)
        self._validate()

    @classmethod
    def default(cls) -> "KnowledgeBase":
        from codequest.core.knowledge.spring import CONCEPTS

        return cls(CONCEPTS, ANNOTATION_CONCEPTS, SUPERTYPE_CONCEPTS)

    @property
    def concepts(self) -> tuple[Concept, ...]:
        return tuple(self._concepts.values())

    def get(self, concept_id: str) -> Concept | None:
        return self._concepts.get(concept_id)

    def for_annotation(self, name: str) -> Concept | None:
        concept_id = self._by_annotation.get(name)
        return self._concepts.get(concept_id) if concept_id else None

    def for_supertype(self, name: str) -> Concept | None:
        concept_id = self._by_supertype.get(name)
        return self._concepts.get(concept_id) if concept_id else None

    def _validate(self) -> None:
        """Errores de contenido se detectan al arrancar (y en los tests), no a mitad de una partida."""
        for index in (self._by_annotation, self._by_supertype):
            missing = sorted(set(index.values()) - self._concepts.keys())
            if missing:
                raise ValueError(f"Conceptos inexistentes en el índice: {missing}")
        for concept in self._concepts.values():
            if len(set(concept.distractors)) < MIN_DISTRACTORS:
                raise ValueError(f"{concept.id}: necesita al menos {MIN_DISTRACTORS} distractores distintos")
            if concept.summary in concept.distractors:
                raise ValueError(f"{concept.id}: la respuesta correcta aparece entre los distractores")
