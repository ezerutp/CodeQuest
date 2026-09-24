"""Generación local de preguntas (sin IA) a partir de reglas y la base de conocimiento."""

import random
from collections import defaultdict
from collections.abc import Mapping, Sequence

from codequest.core.analysis.model import ProjectModel
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.questions.models import Question, QuestionDraft
from codequest.core.questions.rules import DEFAULT_RULES, QuestionRule

CHOICES_PER_QUESTION = 4
TRUE_FALSE_CHOICES = ("Verdadero", "Falso")


class ChoiceStyle:
    MULTIPLE = "multiple"  # 4 alternativas
    TRUE_FALSE = "true_false"  # una afirmación: verdadera o falsa
    NONE = "none"  # respuesta libre


class QuestionGenerator:
    def __init__(self, kb: KnowledgeBase, rules: Sequence[QuestionRule] = DEFAULT_RULES,
                 style: str = ChoiceStyle.MULTIPLE) -> None:
        self._kb = kb
        self._rules = tuple(rules)
        self._style = style

    def drafts(self, model: ProjectModel, class_name: str | None = None,
               concept_ids: frozenset[str] | None = None) -> list[QuestionDraft]:
        seen: set[str] = set()
        result: list[QuestionDraft] = []
        for rule in self._rules:
            for draft in rule.drafts(model, self._kb):
                if draft.key in seen or (class_name and draft.class_name != class_name):
                    continue
                if concept_ids is not None and draft.concept.id not in concept_ids:
                    continue
                seen.add(draft.key)
                result.append(draft)
        return result

    def generate(self, model: ProjectModel, limit: int = 10, class_name: str | None = None,
                 rng: random.Random | None = None, priorities: Mapping[str, float] | None = None,
                 avoid_keys: frozenset[str] = frozenset(),
                 concept_ids: frozenset[str] | None = None) -> list[Question]:
        """Hasta `limit` preguntas, variando conceptos: 10 controllers no dan 10 preguntas de @RestController.

        `priorities` ordena los conceptos (menor = antes; los que faltan valen 1.0) y `avoid_keys`
        manda al final de cada concepto las preguntas vistas hace poco.
        """
        rng = rng or random.Random()
        priorities = priorities or {}
        by_concept: dict[str, list[QuestionDraft]] = defaultdict(list)
        for draft in self.drafts(model, class_name, concept_ids):
            by_concept[draft.concept.id].append(draft)

        groups = list(by_concept.values())
        rng.shuffle(groups)  # desempate aleatorio entre conceptos de igual prioridad
        groups.sort(key=lambda g: priorities.get(g[0].concept.id, 1.0))
        for group in groups:
            rng.shuffle(group)
            # `pop()` saca del final: las no vistas recientemente deben quedar al final.
            group.sort(key=lambda d: d.key not in avoid_keys)

        picked: list[QuestionDraft] = []
        while groups and len(picked) < limit:  # round-robin entre conceptos, respetando la prioridad
            for group in list(groups):
                picked.append(group.pop())
                if not group:
                    groups.remove(group)
                if len(picked) == limit:
                    break
        if self._style == ChoiceStyle.NONE:
            return [Question(key=d.key, prompt=d.prompt, concept=d.concept, class_name=d.class_name,
                             snippet=d.snippet, mutation=d.mutation) for d in picked]
        if self._style == ChoiceStyle.TRUE_FALSE:
            # Mitad verdaderas y mitad falsas en orden aleatorio: con un 50 % independiente por
            # pregunta salen rachas y el estudiante aprendería a adivinar "casi siempre es falso".
            truths = [i % 2 == 0 for i in range(len(picked))]
            rng.shuffle(truths)
            return [self._build_statement(d, is_true, rng) for d, is_true in zip(picked, truths, strict=True)]
        return [self._build_choices(d, rng) for d in picked]

    @staticmethod
    def _build_statement(draft: QuestionDraft, is_true: bool, rng: random.Random) -> Question:
        """Afirmación verdadera (el resumen del concepto) o falsa (uno de sus distractores)."""
        text = draft.concept.summary if is_true else rng.choice(draft.concept.distractors)
        lead = draft.statement_lead or draft.concept.title
        statement = f"{lead} {text[:1].lower()}{text[1:]}"
        return Question(
            key=f"tf:{draft.key}",
            prompt=statement,
            concept=draft.concept,
            class_name=draft.class_name,
            snippet=draft.snippet,
            choices=TRUE_FALSE_CHOICES,
            correct_index=0 if is_true else 1,
        )

    @staticmethod
    def _build_choices(draft: QuestionDraft, rng: random.Random) -> Question:
        # Solo distractores escritos a mano: el resumen de otro concepto puede ser
        # parcialmente cierto (un @Service también "registra un bean") y generar ambigüedad.
        wrong = rng.sample(draft.concept.distractors, CHOICES_PER_QUESTION - 1)
        choices = [draft.concept.summary, *wrong]
        rng.shuffle(choices)
        return Question(
            key=draft.key,
            prompt=draft.prompt,
            concept=draft.concept,
            class_name=draft.class_name,
            snippet=draft.snippet,
            choices=tuple(choices),
            correct_index=choices.index(draft.concept.summary),
        )
