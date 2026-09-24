"""Modo "Encuentra el error": el estudiante señala la línea que se cambió en su código."""

from codequest.core.games.base import BaseGameMode, Evaluation, Outcome
from codequest.core.games.catalog import FIND_ERROR
from codequest.core.questions.models import Question


class FindErrorMode(BaseGameMode):
    """La respuesta es un número de línea (numeración real del archivo). Evaluación local, sin IA."""

    mode_id = FIND_ERROR

    def evaluate(self, question: Question, answer: int) -> Evaluation:
        if question.mutation is None:
            raise ValueError(f"La pregunta {question.key} no tiene un error que encontrar")
        outcome = Outcome.CORRECT if answer == question.mutation.line else Outcome.INCORRECT
        return Evaluation(question, outcome, answer)
