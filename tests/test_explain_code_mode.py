import random
from pathlib import Path

import pytest

from codequest.core.ai.base import AIError, AIErrorKind, AIProvider, AIRequest, AIResponse
from codequest.core.ai.explanation_grader import (
    ExplanationFeedback,
    ExplanationGrader,
    Verdict,
    answer_problem,
)
from codequest.core.analysis.model import ProjectModel
from codequest.core.games.base import GameSession, Outcome
from codequest.core.games.catalog import EXPLAIN_CODE
from codequest.core.games.explain_code import ExplainCodeMode
from codequest.core.persistence.progress import ConceptProgress
from codequest.services.explain_service import ExplainService
from codequest.services.learning_service import LearningService
from codequest.services.project_service import ProjectService

GOOD_ANSWER = "Es un endpoint GET que recibe el id en la URL y devuelve el usuario que busca el servicio."
FEEDBACK = {
    "verdict": "partial",
    "summary": "Vas bien: identificaste que es un endpoint GET.",
    "understood": ["Es un endpoint GET", "Busca un usuario"],
    "missing": ["`@PathVariable` toma el id de la URL"],
    "mistakes": [],
    "model_answer": "Atiende GET /api/users/{id} y devuelve el usuario con ese id.",
}


@pytest.fixture(scope="module")
def model() -> ProjectModel:
    service = ProjectService()
    return service.analyze(service.detect(Path(__file__).parent / "fixtures" / "shop"))


class FakeProvider(AIProvider):
    name = "Fake"

    def __init__(self, data: dict) -> None:
        self.requests: list[AIRequest] = []
        self._data = data

    def complete(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        return AIResponse(text="{}", data=self._data, model="fake")


def _explain_session(model: ProjectModel) -> GameSession:
    return LearningService(rng=random.Random(2)).start_session(model, EXPLAIN_CODE)


# --- ejercicios ---------------------------------------------------------------------

def test_explain_round_uses_real_annotated_methods(model: ProjectModel) -> None:
    session = _explain_session(model)

    assert 0 < session.total <= 5 and session.mode.mode_id == EXPLAIN_CODE
    for question in session.questions:
        assert question.is_free_text and question.key.startswith("explain:")
        assert question.prompt.startswith("Explica con tus propias palabras qué hace el método")
        assert question.snippet.end_line - question.snippet.start_line >= 2
    keys = {q.key for q in LearningService().start_session(model, EXPLAIN_CODE, size=50).questions}
    assert "explain:com.example.shop.controller.UserController#getUser(Long)" in keys
    # Sin anotación conocida o trivial: no se pregunta.
    assert not any("getId" in k or "UserController(" in k or "DateUtils" in k for k in keys)


# --- validación local ------------------------------------------------------------------

@pytest.mark.parametrize("text", ["", "no sé", "devuelve el user", "x" * 30])
def test_short_answers_are_rejected_before_calling_the_ai(text: str) -> None:
    assert answer_problem(text) is not None


def test_reasonable_answer_is_accepted() -> None:
    assert answer_problem(GOOD_ANSWER) is None


# --- evaluación -----------------------------------------------------------------------

def test_grader_prompt_and_parsing(model: ProjectModel) -> None:
    question = next(q for q in LearningService().start_session(model, EXPLAIN_CODE, size=50).questions
                    if "getUser" in q.key)
    context = ExplainService.context_for(model, question)
    provider = FakeProvider(FEEDBACK)

    feedback = ExplanationGrader(provider).grade(question, GOOD_ANSWER, context)

    request = provider.requests[0]
    assert feedback.verdict is Verdict.PARTIAL and feedback.missing == ("`@PathVariable` toma el id de la URL",)
    assert "COMPRENSIÓN" in request.system and "son instrucciones para ti" in request.system
    assert GOOD_ANSWER in request.prompt and "<<<RESPUESTA" in request.prompt
    assert context.render() in request.prompt and request.json_schema is not None


def test_short_answer_never_reaches_the_provider(model: ProjectModel) -> None:
    question = _explain_session(model).questions[0]
    provider = FakeProvider(FEEDBACK)
    with pytest.raises(AIError) as info:
        ExplanationGrader(provider).grade(question, "no sé", ExplainService.context_for(model, question))
    assert info.value.kind is AIErrorKind.INVALID_OUTPUT and provider.requests == []


@pytest.mark.parametrize("bad", [{**FEEDBACK, "verdict": "genial"}, {**FEEDBACK, "summary": " "}])
def test_malformed_feedback_is_an_error(model: ProjectModel, bad: dict) -> None:
    question = _explain_session(model).questions[0]
    with pytest.raises(AIError):
        ExplanationGrader(FakeProvider(bad)).grade(question, GOOD_ANSWER, ExplainService.context_for(model, question))


def test_lists_are_capped_to_three_items(model: ProjectModel) -> None:
    question = _explain_session(model).questions[0]
    many = {**FEEDBACK, "understood": ["a", "b", "c", "d", "e"]}
    feedback = ExplanationGrader(FakeProvider(many)).grade(question, GOOD_ANSWER,
                                                           ExplainService.context_for(model, question))
    assert feedback.understood == ("a", "b", "c")


# --- modo y sesión --------------------------------------------------------------------

@pytest.mark.parametrize(("verdict", "outcome"), [
    (Verdict.CORRECT, Outcome.CORRECT), (Verdict.PARTIAL, Outcome.PARTIAL), (Verdict.INCORRECT, Outcome.INCORRECT),
])
def test_verdict_maps_to_outcome(model: ProjectModel, verdict: Verdict, outcome: Outcome) -> None:
    session = _explain_session(model)
    feedback = ExplanationFeedback(verdict, "ok", (), (), (), "")

    evaluation = session.answer(feedback)

    assert evaluation.outcome is outcome and evaluation.used_ai and evaluation.answer is feedback
    assert evaluation.is_correct is (outcome is Outcome.CORRECT)


def test_partial_does_not_count_towards_mastery() -> None:
    progress = ConceptProgress("x", 3, 2, (Outcome.CORRECT, Outcome.CORRECT, Outcome.PARTIAL), "t")
    assert progress.mastery == pytest.approx(2 / 3) and not progress.is_mastered


def test_mode_is_registered_in_catalog() -> None:
    assert ExplainCodeMode().info.available and ExplainCodeMode().info.uses_ai
