"""Caso de uso: crear rondas de práctica sobre el proyecto analizado."""

import random
from collections.abc import Mapping

from codequest.core.analysis.model import ProjectModel
from codequest.core.games.base import BaseGameMode, GameSession
from codequest.core.games.catalog import EXPLAIN_CODE, FIND_ERROR, FIX_CODE, MULTIPLE_CHOICE, TRUE_FALSE
from codequest.core.games.explain_code import ExplainCodeMode
from codequest.core.games.find_error import FindErrorMode
from codequest.core.games.fix_code import FixCodeMode
from codequest.core.games.multiple_choice import MultipleChoiceMode, TrueFalseMode
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.knowledge.coverage import KnowledgeReport, build_report
from codequest.core.questions.generator import ChoiceStyle, QuestionGenerator
from codequest.core.questions.mutations import FIND_ERROR_RULES, FIX_CODE_RULES
from codequest.core.questions.rules import EXPLAIN_RULES

ROUND_SIZE = 10
# Escribir o leer un fragmento entero cuesta más que elegir: rondas más cortas.
ROUND_SIZES = {EXPLAIN_CODE: 5, FIND_ERROR: 6, FIX_CODE: 5}


class LearningService:
    def __init__(self, kb: KnowledgeBase | None = None, rng: random.Random | None = None) -> None:
        self.kb = kb or KnowledgeBase.default()
        self._generator = QuestionGenerator(self.kb)
        self._generators = {
            MULTIPLE_CHOICE: self._generator,
            EXPLAIN_CODE: QuestionGenerator(self.kb, EXPLAIN_RULES, style=ChoiceStyle.NONE),
            TRUE_FALSE: QuestionGenerator(self.kb, style=ChoiceStyle.TRUE_FALSE),
            FIND_ERROR: QuestionGenerator(self.kb, FIND_ERROR_RULES, style=ChoiceStyle.NONE),
            FIX_CODE: QuestionGenerator(self.kb, FIX_CODE_RULES, style=ChoiceStyle.NONE),
        }
        self._rng = rng or random.Random()
        self._modes: dict[str, BaseGameMode] = {
            MULTIPLE_CHOICE: MultipleChoiceMode(), TRUE_FALSE: TrueFalseMode(), EXPLAIN_CODE: ExplainCodeMode(),
            FIND_ERROR: FindErrorMode(), FIX_CODE: FixCodeMode(),
        }

    def knowledge_report(self, model: ProjectModel) -> KnowledgeReport:
        """Conceptos que usa el proyecto y anotaciones/supertipos que aún no conocemos."""
        return build_report(model, self.kb)

    def available_questions(self, model: ProjectModel, class_name: str | None = None) -> int:
        return len(self._generator.drafts(model, class_name))

    def start_session(self, model: ProjectModel, mode_id: str = MULTIPLE_CHOICE,
                      class_name: str | None = None, size: int | None = None,
                      priorities: Mapping[str, float] | None = None,
                      avoid_keys: frozenset[str] = frozenset(),
                      concept_ids: frozenset[str] | None = None) -> GameSession:
        """Nueva ronda. Puede no tener preguntas (p. ej. una clase sin anotaciones conocidas).

        Con historial, `priorities` pone primero lo que cuesta y `avoid_keys` evita repetir lo reciente.
        """
        mode = self._modes[mode_id]
        size = size or ROUND_SIZES.get(mode_id, ROUND_SIZE)
        questions = self._generators[mode_id].generate(model, limit=size, class_name=class_name, rng=self._rng,
                                             priorities=priorities, avoid_keys=avoid_keys,
                                             concept_ids=concept_ids)
        return GameSession(mode=mode, questions=questions, scope=class_name)
