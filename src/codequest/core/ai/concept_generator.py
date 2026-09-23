"""Genera con IA conceptos para los huecos de la base de conocimiento.

Privacidad: el prompt solo contiene el nombre del elemento, su tipo (anotación o
supertipo) y su import (p. ej. "lombok.Data"). Nunca código ni nombres del proyecto.
"""

import json
import logging

from codequest.core.ai.base import AIError, AIErrorKind, AIProvider, AIRequest
from codequest.core.knowledge.coverage import GapKind, KnowledgeGap
from codequest.core.knowledge.models import Concept, ConceptMatch, ConceptSource, Topic
from codequest.core.knowledge.validation import MIN_DISTRACTORS, concept_problems

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "Eres un profesor de programación que escribe material para CodeQuest, una aplicación que ayuda a "
    "estudiantes de Java y Spring Boot a entender el código de sus propios proyectos. Escribes en español "
    "neutro, claro y cercano, para alguien que está empezando. Eres riguroso: nunca inventas "
    "comportamiento que no conoces con certeza."
)

_TOPICS = [t.value for t in Topic]

CONCEPT_SCHEMA = {
    "type": "object",
    "properties": {
        "known": {"type": "boolean"},
        "title": {"type": "string"},
        "topic": {"type": "string", "enum": _TOPICS},
        "summary": {"type": "string"},
        "explanation": {"type": "string"},
        "analogy": {"type": "string"},
        "distractors": {"type": "array", "items": {"type": "string"}},
        "youtube_query": {"type": "string"},
    },
    "required": ["known", "title", "topic", "summary", "explanation", "analogy", "distractors", "youtube_query"],
    "additionalProperties": False,
}

_RULES = f"""\
Devuelve un objeto JSON con estos campos:
- known: false si no conoces este elemento con certeza (en ese caso, el resto puede ir vacío). No adivines.
- title: "@Nombre" si es una anotación, o el nombre del tipo si es un supertipo.
- topic: uno de {", ".join(_TOPICS)}. Usa "other" si ninguno encaja (por ejemplo, Lombok).
- summary: UNA frase corta (entre 60 y 90 caracteres) que responde "¿qué hace?". Será la respuesta \
correcta de una pregunta de alternativas.
- distractors: exactamente {MIN_DISTRACTORS} afirmaciones FALSAS pero verosímiles sobre este mismo elemento, \
con el mismo estilo y una longitud parecida a summary (entre 60 y 95 caracteres). Deben ser claramente \
falsas: nada parcialmente cierto, y no describas lo que hace otra anotación real de Spring.
- explanation: dos párrafos separados por una línea en blanco: qué hace, y cuándo y por qué se usa.
- analogy: una o dos frases que lo comparen con algo cotidiano.
- youtube_query: una búsqueda corta para encontrar videos sobre el tema.

Ejemplo del estilo esperado (para otro elemento):
{{example}}
"""

_EXAMPLE = {
    "known": True,
    "title": "@Transactional",
    "topic": "transactions",
    "summary": "Hace que las operaciones de base de datos se ejecuten dentro de una transacción.",
    "explanation": "@Transactional le indica a Spring que todo lo que el método hace en la base de datos forma "
                   "parte de una sola transacción.\n\nSi una operación falla a mitad, Spring revierte también "
                   "las anteriores, para que los datos no queden a medias.",
    "analogy": "Es como guardar la partida solo cuando todas las acciones de la misión se completaron.",
    "distractors": [
        "Convierte el método en un endpoint HTTP que se puede llamar desde el navegador.",
        "Hace que el resultado del método se convierta automáticamente en JSON.",
        "Inyecta automáticamente el repositorio que usa el método.",
    ],
    "youtube_query": "Spring @Transactional explicado",
}


def concept_id_for(gap: KnowledgeGap) -> str:
    return f"ai.{(gap.qualified_name or gap.name).lower()}"


def describe_gap(gap: KnowledgeGap) -> str:
    """Exactamente lo que se envía a la IA sobre un hueco (también se muestra al usuario)."""
    kind = "Anotación" if gap.kind is GapKind.ANNOTATION else "Supertipo (clase o interfaz que se extiende)"
    where = gap.qualified_name or "paquete desconocido (import con comodín o del mismo paquete)"
    return f"{kind}: {gap.display} · {where}"


class ConceptGenerator:
    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    def generate(self, gap: KnowledgeGap) -> Concept:
        """Genera y valida un concepto. Lanza AIError si la IA no puede producir uno válido."""
        prompt = self._prompt(gap)
        concept = self._request(gap, prompt)
        problems = concept_problems(concept)
        if problems:
            # Un único reintento explicando qué falló (normalmente, la regla de longitud).
            log.info("Concepto %s inválido (%s); reintentando", concept.id, problems)
            retry = (f"{prompt}\n\nTu respuesta anterior no era válida por esto: {'; '.join(problems)}.\n"
                     f"Respuesta anterior:\n{self._as_json(concept)}\nCorrígela.")
            concept = self._request(gap, retry)
            if problems := concept_problems(concept):
                raise AIError(AIErrorKind.INVALID_OUTPUT, "; ".join(problems))
        return concept

    def _prompt(self, gap: KnowledgeGap) -> str:
        rules = _RULES.replace("{example}", json.dumps(_EXAMPLE, ensure_ascii=False, indent=2))
        return f"Escribe el concepto para este elemento de Java:\n{describe_gap(gap)}\n\n{rules}"

    def _request(self, gap: KnowledgeGap, prompt: str) -> Concept:
        response = self._provider.complete(AIRequest(system=SYSTEM_PROMPT, prompt=prompt, json_schema=CONCEPT_SCHEMA))
        data = response.data or {}
        if not data.get("known", False):
            raise AIError(AIErrorKind.NOT_KNOWN)
        try:
            topic = Topic(data.get("topic", Topic.OTHER.value))
        except ValueError:
            topic = Topic.OTHER
        is_annotation = gap.kind is GapKind.ANNOTATION
        return Concept(
            id=concept_id_for(gap),
            title=str(data.get("title") or gap.display).strip(),
            topic=topic,
            summary=str(data.get("summary", "")).strip(),
            explanation=str(data.get("explanation", "")).strip(),
            analogy=str(data.get("analogy", "")).strip(),
            distractors=tuple(str(d).strip() for d in data.get("distractors", []) if str(d).strip())[:MIN_DISTRACTORS],
            youtube_query=str(data.get("youtube_query", "")).strip(),
            # matches lo decide CodeQuest, no la IA: el concepto explica exactamente el hueco.
            matches=ConceptMatch(annotations=(gap.name,) if is_annotation else (),
                                 supertypes=() if is_annotation else (gap.name,)),
            source=ConceptSource.AI,
        )

    @staticmethod
    def _as_json(concept: Concept) -> str:
        return json.dumps({"summary": concept.summary, "distractors": list(concept.distractors)},
                          ensure_ascii=False)
