"""Caso de uso: crear rondas de práctica sobre el proyecto analizado."""

import random

from codequest.core.analysis.model import ProjectModel
from codequest.core.games.base import BaseGameMode, GameSession
from codequest.core.games.catalog import MULTIPLE_CHOICE
from codequest.core.games.multiple_choice import MultipleChoiceMode
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.questions.generator import QuestionGenerator

ROUND_SIZE = 10


class LearningService:
    def __init__(self, kb: KnowledgeBase | None = None, rng: random.Random | None = None) -> None:
        self.kb = kb or KnowledgeBase.default()
        self._generator = QuestionGenerator(self.kb)
        self._rng = rng or random.Random()
        self._modes: dict[str, BaseGameMode] = {MULTIPLE_CHOICE: MultipleChoiceMode()}

    def available_questions(self, model: ProjectModel, class_name: str | None = None) -> int:
        return len(self._generator.drafts(model, class_name))

    def start_session(self, model: ProjectModel, mode_id: str = MULTIPLE_CHOICE,
                      class_name: str | None = None, size: int = ROUND_SIZE) -> GameSession:
        """Nueva ronda. Puede no tener preguntas (p. ej. una clase sin anotaciones conocidas)."""
        mode = self._modes[mode_id]
        questions = self._generator.generate(model, limit=size, class_name=class_name, rng=self._rng)
        return GameSession(mode=mode, questions=questions, scope=class_name)
