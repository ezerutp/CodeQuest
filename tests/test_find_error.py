import hashlib
import random
from pathlib import Path

import pytest

from codequest.core.ai.base import AIProvider, AIRequest, AIResponse
from codequest.core.ai.code_explainer import CodeExplainer
from codequest.core.ai.context import ContextBuilder
from codequest.core.analysis.model import ProjectModel
from codequest.core.games.base import Outcome
from codequest.core.games.catalog import FIND_ERROR, mode_info
from codequest.core.games.find_error import FindErrorMode
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.questions.models import CodeMutation
from codequest.core.questions.mutations import FindErrorRule
from codequest.services.learning_service import LearningService
from codequest.services.project_service import ProjectService

SHOP = Path(__file__).parent / "fixtures" / "shop"


@pytest.fixture(scope="module")
def service() -> ProjectService:
    return ProjectService()


@pytest.fixture(scope="module")
def model(service: ProjectService) -> ProjectModel:
    return service.analyze(service.detect(SHOP))


def _drafts(model: ProjectModel):
    return list(FindErrorRule().drafts(model, KnowledgeBase.default()))


def _mutated_line(service: ProjectService, model: ProjectModel, draft) -> tuple[str, str]:
    snippet = service.read_snippet(model, draft.snippet)
    index = draft.mutation.line - snippet.start_line
    mutated = draft.mutation.apply(snippet.text, snippet.start_line)
    return snippet.text.split("\n")[index].strip(), mutated.split("\n")[index].strip()


def _by_key(model: ProjectModel, suffix: str):
    return next(d for d in _drafts(model) if d.key.endswith(suffix))


def test_rule_mutates_known_annotations_inside_the_snippet(service: ProjectService, model: ProjectModel) -> None:
    drafts = _drafts(model)
    assert len(drafts) >= 10
    assert len({d.key for d in drafts}) == len(drafts)
    for draft in drafts:
        assert draft.snippet.start_line <= draft.mutation.line <= draft.snippet.end_line
        assert not draft.snippet.focus_lines  # resaltar la línea regalaría la respuesta
        original, mutated = _mutated_line(service, model, draft)
        assert original != mutated and draft.mutation.replace in mutated


def test_mapping_swap_keeps_the_route(service: ProjectService, model: ProjectModel) -> None:
    original, mutated = _mutated_line(service, model, _by_key(model, "UserController#getUser()"))
    assert (original, mutated) == ('@GetMapping("/{id}")', '@PostMapping("/{id}")')


def test_other_swaps_drop_arguments_that_would_give_the_change_away(service: ProjectService,
                                                                    model: ProjectModel) -> None:
    _, mutated = _mutated_line(service, model, _by_key(model, "UserController#delete():id"))
    assert "@RequestBody Long id" in mutated
    _, mutated = _mutated_line(service, model, _by_key(model, "User#orders"))
    assert mutated.startswith("@ManyToOne") and "mappedBy" not in mutated


def test_relations_are_only_inverted_when_the_type_contradicts_them(model: ProjectModel) -> None:
    swaps = {d.key: d.mutation.replace for d in _drafts(model) if d.concept.id.startswith("jpa.") and "#" in d.key}
    assert swaps["error:jpa.one-to-many:com.example.shop.entity.User#orders"] == "@ManyToOne"
    assert swaps["error:jpa.many-to-one:com.example.shop.entity.Order#user"] == "@OneToMany"


def test_explanations_name_the_real_member(model: ProjectModel) -> None:
    draft = _by_key(model, "UserController#create():dto")
    assert "`dto`" in draft.mutation.explanation and "{" not in draft.mutation.explanation


def test_apply_respects_word_boundaries_and_detects_stale_code() -> None:
    mutation = CodeMutation(line=11, find="@Id", replace="@Column", explanation="")
    assert mutation.apply("@IdClass(X.class)\n@Id\nLong id;", first_line=10) == "@IdClass(X.class)\n@Column\nLong id;"
    with pytest.raises(ValueError):
        mutation.apply("@IdClass(X.class)\nLong id;", first_line=10)
    with pytest.raises(ValueError):
        mutation.apply("@Id", first_line=40)  # la línea ya no está en el fragmento


def test_mode_evaluates_the_chosen_line(model: ProjectModel) -> None:
    session = LearningService(rng=random.Random(3)).start_session(model, FIND_ERROR)
    assert mode_info(FIND_ERROR).available and not mode_info(FIND_ERROR).uses_ai
    assert 0 < session.total <= 6
    question = session.current
    assert question.mutation is not None and question.is_free_text
    assert session.answer(question.mutation.line).outcome is Outcome.CORRECT
    session.next()
    assert session.answer(session.current.mutation.line + 1).outcome is Outcome.INCORRECT
    session.next()
    assert session.skip().outcome is Outcome.SKIPPED


def test_round_varies_concepts(model: ProjectModel) -> None:
    session = LearningService(rng=random.Random(1)).start_session(model, FIND_ERROR)
    assert len({q.concept.id for q in session.questions}) == session.total


def test_playing_never_touches_the_project(service: ProjectService, model: ProjectModel) -> None:
    def digest() -> dict[Path, str]:
        return {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in SHOP.rglob("*") if p.is_file()}

    before = digest()
    for draft in _drafts(model):
        _mutated_line(service, model, draft)
    assert digest() == before


def test_ai_explanation_of_a_missed_error_describes_the_change(model: ProjectModel) -> None:
    class FakeProvider(AIProvider):
        name = "Fake"

        def __init__(self) -> None:
            self.requests: list[AIRequest] = []

        def complete(self, request: AIRequest) -> AIResponse:
            self.requests.append(request)
            return AIResponse(text="Explicación.", data=None, model="fake")

    question = LearningService(rng=random.Random(3)).start_session(model, FIND_ERROR).current
    evaluation = FindErrorMode().evaluate(question, question.mutation.line + 1)
    provider = FakeProvider()
    context = ContextBuilder(model).build(question.class_name, question.snippet)
    assert CodeExplainer(provider).explain(evaluation, context) == "Explicación."
    prompt = provider.requests[0].prompt
    assert question.mutation.replace in prompt and f"línea {question.mutation.line + 1}" in prompt
