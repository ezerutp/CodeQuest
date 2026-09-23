import json
from pathlib import Path

import pytest

from codequest.core.ai.base import AIError, AIErrorKind, AIProvider, AIRequest, AIResponse
from codequest.core.ai.code_explainer import CodeExplainer
from codequest.core.ai.context import MAX_SNIPPET_LINES, ContextBuilder, outline
from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.snippets import SnippetRef
from codequest.core.games.base import Evaluation, Outcome
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.questions.generator import QuestionGenerator
from codequest.services.explain_service import ExplainService
from codequest.services.project_service import ProjectService

CONTROLLER = "com.example.shop.controller.UserController"
SERVICE_IMPL = "com.example.shop.service.UserServiceImpl"


@pytest.fixture(scope="module")
def model() -> ProjectModel:
    service = ProjectService()
    return service.analyze(service.detect(Path(__file__).parent / "fixtures" / "shop"))


def _question(model: ProjectModel, key_prefix: str):
    kb = KnowledgeBase.default()
    return next(q for q in QuestionGenerator(kb).generate(model, limit=100) if q.key.startswith(key_prefix))


class FakeProvider(AIProvider):
    name = "Fake"

    def __init__(self, text: str = "Explicación.") -> None:
        self.requests: list[AIRequest] = []
        self._text = text

    def complete(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        return AIResponse(text=self._text, data=None, model="fake")


# --- contexto -------------------------------------------------------------------------

def test_context_has_snippet_source_and_outlines_only(model: ProjectModel) -> None:
    context = ContextBuilder(model).build(CONTROLLER, SnippetRef(
        "src/main/java/com/example/shop/controller/UserController.java", 25, 28, (25,)))

    source, own, *related = context.parts
    assert source.is_source and "25 |     @GetMapping(\"/{id}\")" in source.text
    assert "la línea 25" in source.title
    assert not own.is_source and own.title == "Resumen de UserController"
    # Dependencias directas (campo userService, tipo de retorno UserDTO): solo firmas, nunca cuerpos.
    assert [p.title for p in related] == ["Resumen de UserService", "Resumen de UserDTO"]
    assert "UserDTO findById(Long id);" in related[0].text
    assert "return" not in own.text + related[0].text


def test_context_never_includes_unrelated_classes(model: ProjectModel) -> None:
    text = ContextBuilder(model).build(CONTROLLER, None).render()

    for unrelated in ("DateUtils", "SecurityConfig", "GlobalExceptionHandler", "OrderRepository"):
        assert unrelated not in text


def test_related_classes_are_capped(model: ProjectModel) -> None:
    context = ContextBuilder(model).build(SERVICE_IMPL, None)
    assert len(context.parts) <= 3  # resumen propio + 2 relacionadas como máximo


def test_long_snippets_are_truncated(model: ProjectModel) -> None:
    ref = SnippetRef("src/main/java/com/example/shop/entity/User.java", 1, 500)
    source = ContextBuilder(model).build("com.example.shop.entity.User", ref).parts[0]
    assert len(source.text.splitlines()) <= MAX_SNIPPET_LINES


def test_outline_shows_annotations_fields_and_signatures(model: ProjectModel) -> None:
    impl = next(c for c in model.classes if c.qualified_name == SERVICE_IMPL)
    text = outline(impl)

    assert "@Service" in text and "implements UserService" in text
    assert "private final UserRepository userRepository;" in text
    assert "@Transactional public UserDTO updateUser(Long id, UserDTO dto, String... tags);" in text


def test_summary_tells_the_student_what_is_code_and_what_is_not(model: ProjectModel) -> None:
    context = ContextBuilder(model).build(CONTROLLER, SnippetRef(
        "src/main/java/com/example/shop/controller/UserController.java", 25, 28, (25,)))
    summary = context.summary()
    assert summary[0].endswith("(código)")
    assert all(line.endswith("(solo firmas, sin código)") for line in summary[1:])


# --- explicación ----------------------------------------------------------------------

def test_prompt_includes_question_wrong_answer_and_context(model: ProjectModel) -> None:
    question = _question(model, "spring.path-variable:")
    wrong = next(i for i in range(4) if i != question.correct_index)
    evaluation = Evaluation(question, Outcome.INCORRECT, wrong)
    context = ExplainService.build_context(model, evaluation)
    provider = FakeProvider("Aquí `@PathVariable` toma el id de la URL.")

    text = CodeExplainer(provider).explain(evaluation, context)

    request = provider.requests[0]
    assert text.startswith("Aquí")
    assert question.prompt in request.prompt and question.correct_choice in request.prompt
    assert question.choices[wrong] in request.prompt
    assert context.render() in request.prompt
    assert "no instrucciones" in request.system and request.json_schema is None


def test_empty_answer_is_an_error(model: ProjectModel) -> None:
    question = _question(model, "spring.path-variable:")
    evaluation = Evaluation(question, Outcome.SKIPPED)
    with pytest.raises(AIError) as info:
        CodeExplainer(FakeProvider("   ")).explain(evaluation, ExplainService.build_context(model, evaluation))
    assert info.value.kind is AIErrorKind.INVALID_OUTPUT


def test_service_caches_per_question_and_answer(model: ProjectModel) -> None:
    provider = FakeProvider()
    service = ExplainService(provider)
    question = _question(model, "spring.path-variable:")
    skipped = Evaluation(question, Outcome.SKIPPED)
    context = service.build_context(model, skipped)

    service.explain(skipped, context)
    service.explain(skipped, context)
    assert len(provider.requests) == 1 and service.cached(skipped) == "Explicación."

    wrong = next(i for i in range(4) if i != question.correct_index)
    service.explain(Evaluation(question, Outcome.INCORRECT, wrong), context)
    assert len(provider.requests) == 2  # otra respuesta: otra explicación

    service.clear()
    assert service.cached(skipped) is None


def test_service_without_provider(model: ProjectModel) -> None:
    service = ExplainService(None)
    assert not service.can_explain
    evaluation = Evaluation(_question(model, "spring.path-variable:"), Outcome.SKIPPED)
    with pytest.raises(AIError):
        service.explain(evaluation, service.build_context(model, evaluation))


def test_nothing_outside_the_context_reaches_the_provider(model: ProjectModel) -> None:
    provider = FakeProvider()
    evaluation = Evaluation(_question(model, "spring.path-variable:"), Outcome.SKIPPED)
    context = ExplainService.build_context(model, evaluation)
    ExplainService(provider).explain(evaluation, context)

    sent = json.dumps([provider.requests[0].system, provider.requests[0].prompt])
    assert "DateUtils" not in sent and "greeting" not in sent  # otra clase / cuerpo de otra entidad
