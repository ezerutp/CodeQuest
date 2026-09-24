import random
from pathlib import Path

import pytest

from codequest.core.analysis.model import ProjectModel
from codequest.core.games.base import Outcome
from codequest.core.games.catalog import COMPARISON, mode_info
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.knowledge.comparisons import load_builtin_comparisons, parse_comparisons
from codequest.core.knowledge.loader import KnowledgeFormatError
from codequest.core.questions.comparisons import ComparisonRule
from codequest.services.learning_service import LearningService
from codequest.services.project_service import ProjectService


@pytest.fixture(scope="module")
def model() -> ProjectModel:
    service = ProjectService()
    return service.analyze(service.detect(Path(__file__).parent / "fixtures" / "shop"))


def _drafts(model: ProjectModel):
    return list(ComparisonRule().drafts(model, KnowledgeBase.default()))


def test_builtin_comparisons_are_valid_and_anchored_to_known_concepts() -> None:
    kb = KnowledgeBase.default()
    comparisons = load_builtin_comparisons()
    assert len(comparisons) >= 15
    for comparison in comparisons:
        assert kb.get(comparison.concept_id) is not None, comparison.id
        # La respuesta correcta nunca es la más larga: se acertaría sin saber.
        assert len(comparison.summary) <= max(map(len, comparison.distractors)), comparison.id


def test_invalid_comparison_is_rejected() -> None:
    text = """
version: 1
comparisons:
- id: compare.x
  concept: spring.service
  versus: '@Component'
  summary: Una respuesta correcta muchísimo más larga que cualquiera de los distractores que la acompañan.
  explanation: x
  analogy: x
  youtube_query: x
  distractors: [corta uno, corta dos, corta tres]
"""
    with pytest.raises(KnowledgeFormatError, match="más larga"):
        parse_comparisons(text, "test.yaml")
    with pytest.raises(KnowledgeFormatError, match="faltan"):
        parse_comparisons("comparisons:\n- id: compare.y\n", "test.yaml")


def test_only_comparisons_of_concepts_the_project_uses(model: ProjectModel) -> None:
    drafts = _drafts(model)
    keys = {d.key for d in drafts}
    assert "compare:compare.rest-controller-vs-controller:com.example.shop.controller.UserController" in keys
    assert not any("controller-vs-rest-controller" in k for k in keys)  # el proyecto no usa @Controller
    assert len(keys) == len(drafts)


def test_question_uses_real_code_and_counts_for_the_anchor_concept(model: ProjectModel) -> None:
    draft = next(d for d in _drafts(model) if "entity-vs-dto" in d.key and d.class_name.endswith(".User"))
    assert draft.prompt == "En `User` usas `@Entity`. ¿Qué lo diferencia de un DTO?"
    assert draft.concept.id == "jpa.entity" and draft.concept.title == "@Entity vs un DTO"
    assert "transporta datos" in draft.concept.summary
    assert draft.snippet is not None and draft.snippet.focus_lines


def test_versus_with_words_marks_only_the_code() -> None:
    from codequest.core.questions.comparisons import _as_code

    assert _as_code("@Controller") == "`@Controller`"
    assert _as_code("@ExceptionHandler dentro de un controlador") == "`@ExceptionHandler` dentro de un controlador"
    assert _as_code("un DTO") == "un DTO"


def test_mode_plays_like_multiple_choice(model: ProjectModel) -> None:
    info = mode_info(COMPARISON)
    assert info.available and not info.uses_ai
    session = LearningService(rng=random.Random(2)).start_session(model, COMPARISON)
    assert 0 < session.total <= 8
    question = session.current
    assert len(question.choices) == 4 and question.choices[question.correct_index] == question.concept.summary
    assert session.answer(question.correct_index).outcome is Outcome.CORRECT
    assert len({q.concept.id for q in session.questions}) == session.total  # varía los conceptos
