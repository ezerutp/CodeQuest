from codequest.core.games.base import BaseGameMode, Evaluation, Outcome
from codequest.core.games.catalog import MULTIPLE_CHOICE
from codequest.core.questions.models import Question


class MultipleChoiceMode(BaseGameMode):
    mode_id = MULTIPLE_CHOICE

    def evaluate(self, question: Question, answer: int) -> Evaluation:
        if not 0 <= answer < len(question.choices):
            raise ValueError(f"Alternativa fuera de rango: {answer}")
        outcome = Outcome.CORRECT if answer == question.correct_index else Outcome.INCORRECT
        return Evaluation(question, outcome, answer)
