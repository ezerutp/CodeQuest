"""Reglas de calidad que cumple todo concepto, venga de donde venga."""

from codequest.core.knowledge.models import Concept

MIN_DISTRACTORS = 3
# La respuesta correcta no debe destacar por longitud: se acertaría sin saber.
MAX_SUMMARY_LENGTH_RATIO = 1.10


def concept_problems(concept: Concept) -> list[str]:
    """Lista de problemas (vacía si el concepto es válido)."""
    problems: list[str] = []
    for name in ("id", "title", "summary", "explanation", "analogy", "youtube_query"):
        if not getattr(concept, name).strip():
            problems.append(f"falta el campo '{name}'")
    if not (concept.matches.annotations or concept.matches.supertypes):
        problems.append("'matches' debe indicar al menos una anotación o supertipo")
    distractors = [d.strip() for d in concept.distractors if d.strip()]
    if len(set(distractors)) < MIN_DISTRACTORS:
        problems.append(f"necesita al menos {MIN_DISTRACTORS} distractores distintos")
    if concept.summary in distractors:
        problems.append("la respuesta correcta aparece entre los distractores")
    if distractors and len(concept.summary) > MAX_SUMMARY_LENGTH_RATIO * max(map(len, distractors)):
        problems.append("la respuesta correcta es notablemente más larga que los distractores")
    return problems
