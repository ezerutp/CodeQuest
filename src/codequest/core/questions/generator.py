"""Generación local de preguntas (sin IA) a partir de reglas y la base de conocimiento."""

import random
from collections import defaultdict
from collections.abc import Sequence

from codequest.core.analysis.model import ProjectModel
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.questions.models import Question, QuestionDraft
from codequest.core.questions.rules import DEFAULT_RULES, QuestionRule

CHOICES_PER_QUESTION = 4


class QuestionGenerator:
    def __init__(self, kb: KnowledgeBase, rules: Sequence[QuestionRule] = DEFAULT_RULES) -> None:
        self._kb = kb
        self._rules = tuple(rules)

    def drafts(self, model: ProjectModel, class_name: str | None = None) -> list[QuestionDraft]:
        seen: set[str] = set()
        result: list[QuestionDraft] = []
        for rule in self._rules:
            for draft in rule.drafts(model, self._kb):
                if draft.key in seen or (class_name and draft.class_name != class_name):
                    continue
                seen.add(draft.key)
                result.append(draft)
        return result

    def generate(self, model: ProjectModel, limit: int = 10, class_name: str | None = None,
                 rng: random.Random | None = None) -> list[Question]:
        """Hasta `limit` preguntas, variando conceptos: 10 controllers no dan 10 preguntas de @RestController."""
        rng = rng or random.Random()
        by_concept: dict[str, list[QuestionDraft]] = defaultdict(list)
        for draft in self.drafts(model, class_name):
            by_concept[draft.concept.id].append(draft)

        groups = list(by_concept.values())
        rng.shuffle(groups)
        for group in groups:
            rng.shuffle(group)

        picked: list[QuestionDraft] = []
        while groups and len(picked) < limit:  # round-robin entre conceptos
            for group in list(groups):
                picked.append(group.pop())
                if not group:
                    groups.remove(group)
                if len(picked) == limit:
                    break
        return [self._with_choices(d, rng) for d in picked]

    @staticmethod
    def _with_choices(draft: QuestionDraft, rng: random.Random) -> Question:
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
