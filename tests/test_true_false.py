import random
from pathlib import Path

import pytest

from codequest.core.analysis.model import ProjectModel
from codequest.core.games.base import Outcome
from codequest.core.games.catalog import TRUE_FALSE
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.questions.generator import TRUE_FALSE_CHOICES, ChoiceStyle, QuestionGenerator
from codequest.services.learning_service import LearningService
from codequest.services.project_service import ProjectService


@pytest.fixture(scope="module")
def model() -> ProjectModel:
    service = ProjectService()
    return service.analyze(service.detect(Path(__file__).parent / "fixtures" / "shop"))


def _generate(model: ProjectModel, seed: int, limit: int = 10):
    kb = KnowledgeBase.default()
    return QuestionGenerator(kb, style=ChoiceStyle.TRUE_FALSE).generate(model, limit=limit, rng=random.Random(seed))


def test_statements_use_summary_when_true_and_distractor_when_false(model: ProjectModel) -> None:
    for question in _generate(model, seed=1):
        concept = question.concept
        assert question.choices == TRUE_FALSE_CHOICES and question.key.startswith("tf:")
        claim = question.prompt.lower()
        if question.correct_index == 0:
            assert concept.summary.lower() in claim
        else:
            assert any(d.lower() in claim for d in concept.distractors)
            assert concept.summary.lower() not in claim


@pytest.mark.parametrize("seed", range(5))
def test_rounds_are_balanced_between_true_and_false(model: ProjectModel, seed: int) -> None:
    truths = [q.correct_index == 0 for q in _generate(model, seed)]
    assert abs(truths.count(True) - truths.count(False)) <= 1


def test_statement_reads_as_a_sentence_about_the_code(model: ProjectModel) -> None:
    question = next(q for q in _generate(model, seed=2, limit=50) if "updateUser" in q.key)
    assert question.prompt.startswith("En tu método `updateUser()` de `UserServiceImpl`, `@Transactional` ")
    assert question.prompt[len("En tu método `updateUser()` de `UserServiceImpl`, `@Transactional` ")].islower()


def test_supertype_statement(model: ProjectModel) -> None:
    question = next(q for q in _generate(model, seed=3, limit=50) if q.concept.id == "data.jpa-repository")
    assert question.prompt.startswith("Al extender `JpaRepository<User, Long>`, `UserRepository` ")


def test_true_false_round_via_learning_service(model: ProjectModel) -> None:
    session = LearningService(rng=random.Random(4)).start_session(model, TRUE_FALSE)

    assert session.total == 10 and session.mode.mode_id == TRUE_FALSE
    first = session.current
    assert session.answer(first.correct_index).outcome is Outcome.CORRECT
    session.next()
    assert session.answer(1 - session.current.correct_index).outcome is Outcome.INCORRECT
    with pytest.raises(ValueError):
        session.next()
        session.answer(2)  # solo hay dos opciones
