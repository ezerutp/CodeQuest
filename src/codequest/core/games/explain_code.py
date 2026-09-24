from codequest.core.ai.explanation_grader import ExplanationFeedback, Verdict
from codequest.core.games.base import BaseGameMode, Evaluation, Outcome
from codequest.core.games.catalog import EXPLAIN_CODE
from codequest.core.questions.models import Question

_OUTCOMES = {Verdict.CORRECT: Outcome.CORRECT, Verdict.PARTIAL: Outcome.PARTIAL,
             Verdict.INCORRECT: Outcome.INCORRECT}


class ExplainCodeMode(BaseGameMode):
    """El estudiante explica un fragmento con sus palabras. La valoración de la IA se obtiene
    antes, en segundo plano; aquí solo se traduce a un resultado (la sesión sigue siendo síncrona)."""

    mode_id = EXPLAIN_CODE

    def evaluate(self, question: Question, answer: ExplanationFeedback) -> Evaluation:
        return Evaluation(question, _OUTCOMES[answer.verdict], answer, used_ai=True)
