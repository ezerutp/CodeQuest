"""Abstracciones de los modos de juego y de una partida."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from codequest.core.games.catalog import ModeInfo, mode_info
from codequest.core.questions.models import Question


class Outcome(StrEnum):
    CORRECT = "correct"
    INCORRECT = "incorrect"
    SKIPPED = "skipped"  # el estudiante pulsó "No sé"


@dataclass(frozen=True, slots=True)
class Evaluation:
    question: Question
    outcome: Outcome
    answer: Any = None  # índice elegido, texto escrito… según el modo; None si "No sé"
    used_ai: bool = False

    @property
    def is_correct(self) -> bool:
        return self.outcome is Outcome.CORRECT


class BaseGameMode(ABC):
    """Un tipo de ejercicio. Cada modo sabe evaluar la respuesta a una pregunta."""

    mode_id: str

    @property
    def info(self) -> ModeInfo:
        return mode_info(self.mode_id)

    @abstractmethod
    def evaluate(self, question: Question, answer: Any) -> Evaluation: ...

    def skip(self, question: Question) -> Evaluation:
        """ "No sé": nunca obligamos a adivinar."""
        return Evaluation(question, Outcome.SKIPPED)


class SessionError(RuntimeError):
    pass


@dataclass
class GameSession:
    """Una ronda de preguntas de un modo. No depende de la UI ni de la persistencia.

    Ciclo por pregunta: `answer()` o `skip()` → el estudiante lee la explicación → `next()`.
    """

    mode: BaseGameMode
    questions: list[Question]
    scope: str | None = None  # clase practicada, o None para todo el proyecto
    results: list[Evaluation] = field(default_factory=list)
    _position: int = field(default=0, init=False, repr=False)

    @property
    def position(self) -> int:
        """Índice (0-based) de la pregunta actual."""
        return self._position

    @property
    def total(self) -> int:
        return len(self.questions)

    @property
    def current(self) -> Question | None:
        return self.questions[self._position] if self._position < self.total else None

    @property
    def is_answered(self) -> bool:
        """La pregunta actual ya tiene respuesta (se está mostrando su explicación)."""
        return len(self.results) > self._position

    @property
    def is_finished(self) -> bool:
        return self._position >= self.total

    @property
    def correct_count(self) -> int:
        return sum(r.is_correct for r in self.results)

    @property
    def streak(self) -> int:
        """Aciertos consecutivos más recientes."""
        count = 0
        for result in reversed(self.results):
            if not result.is_correct:
                break
            count += 1
        return count

    def answer(self, answer: Any) -> Evaluation:
        return self._record(self.mode.evaluate(self._require_open(), answer))

    def skip(self) -> Evaluation:
        return self._record(self.mode.skip(self._require_open()))

    def next(self) -> Question | None:
        if not self.is_answered:
            raise SessionError("Responde la pregunta actual antes de continuar")
        self._position += 1
        return self.current

    def to_review(self) -> list[Evaluation]:
        """Fallos y "No sé": lo que conviene repasar."""
        return [r for r in self.results if not r.is_correct]

    def _require_open(self) -> Question:
        question = self.current
        if question is None:
            raise SessionError("La ronda ya terminó")
        if self.is_answered:
            raise SessionError("Esta pregunta ya fue respondida")
        return question

    def _record(self, evaluation: Evaluation) -> Evaluation:
        self.results.append(evaluation)
        return evaluation
