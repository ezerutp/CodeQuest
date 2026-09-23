import json
import threading
from pathlib import Path

import pytest

from codequest.core.ai.base import AIError, AIErrorKind, AIProvider, AIRequest, AIResponse
from codequest.core.ai.concept_generator import ConceptGenerator, concept_id_for, describe_gap
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.knowledge.coverage import GapKind, KnowledgeGap
from codequest.core.knowledge.loader import load_directory
from codequest.core.knowledge.models import ConceptSource, Topic
from codequest.core.knowledge.store import KnowledgeStore
from codequest.services.knowledge_service import KnowledgeService

GOOD = {
    "known": True,
    "title": "@Slf4j",
    "topic": "other",
    "summary": "Crea en la clase un logger llamado log listo para escribir mensajes.",
    "explanation": "Lombok genera el campo log.\n\nAsí no declaras el logger a mano.",
    "analogy": "Es como tener un cuaderno de bitácora ya abierto en cada clase.",
    "distractors": [
        "Registra automáticamente cada petición HTTP en la base de datos.",
        "Convierte la clase en un servicio de logs accesible desde la API.",
        "Desactiva los mensajes de error de la clase en producción.",
    ],
    "youtube_query": "Lombok @Slf4j",
}

SLF4J = KnowledgeGap(GapKind.ANNOTATION, "Slf4j", "lombok.extern.slf4j.Slf4j", 2,
                     ("com.acme.SecretBillingService", "com.acme.PaymentController"))
FILTER = KnowledgeGap(GapKind.SUPERTYPE, "OncePerRequestFilter", "org.springframework.web.filter.OncePerRequestFilter",
                      1, ("com.acme.JwtFilter",))


class FakeProvider(AIProvider):
    name = "Fake"

    def __init__(self, *responses: dict | AIError) -> None:
        self.requests: list[AIRequest] = []
        self._responses = list(responses)

    def complete(self, request: AIRequest) -> AIResponse:
        self.requests.append(request)
        item = self._responses.pop(0)
        if isinstance(item, AIError):
            raise item
        return AIResponse(text=json.dumps(item), data=item, model="fake")


def test_generates_valid_ai_concept_with_matches_from_gap() -> None:
    concept = ConceptGenerator(FakeProvider(GOOD)).generate(SLF4J)

    assert concept.id == "ai.lombok.extern.slf4j.slf4j" == concept_id_for(SLF4J)
    assert concept.source is ConceptSource.AI
    assert concept.topic is Topic.OTHER
    assert concept.matches.annotations == ("Slf4j",) and concept.matches.supertypes == ()


def test_supertype_gap_matches_supertypes() -> None:
    concept = ConceptGenerator(FakeProvider({**GOOD, "title": "OncePerRequestFilter"})).generate(FILTER)
    assert concept.matches.supertypes == ("OncePerRequestFilter",) and concept.matches.annotations == ()


def test_prompt_never_contains_project_code_or_class_names() -> None:
    provider = FakeProvider(GOOD)
    ConceptGenerator(provider).generate(SLF4J)

    sent = provider.requests[0].system + provider.requests[0].prompt
    assert "lombok.extern.slf4j.Slf4j" in sent and "@Slf4j" in sent
    assert "SecretBillingService" not in sent and "PaymentController" not in sent
    assert describe_gap(SLF4J) in provider.requests[0].prompt


def test_retries_once_when_quality_rules_fail() -> None:
    too_long = {**GOOD, "summary": GOOD["summary"] + " Además genera constructores, getters y muchas cosas más."}
    provider = FakeProvider(too_long, GOOD)

    concept = ConceptGenerator(provider).generate(SLF4J)

    assert concept.summary == GOOD["summary"]
    assert len(provider.requests) == 2 and "no era válida" in provider.requests[1].prompt


def test_gives_up_after_second_invalid_answer() -> None:
    bad = {**GOOD, "distractors": ["solo uno"]}
    with pytest.raises(AIError) as info:
        ConceptGenerator(FakeProvider(bad, bad)).generate(SLF4J)
    assert info.value.kind is AIErrorKind.INVALID_OUTPUT


def test_unknown_elements_are_not_invented() -> None:
    provider = FakeProvider({**GOOD, "known": False})
    with pytest.raises(AIError) as info:
        ConceptGenerator(provider).generate(SLF4J)
    assert info.value.kind is AIErrorKind.NOT_KNOWN
    assert len(provider.requests) == 1  # no se reintenta: no se debe inventar


# --- servicio + carpeta del usuario ----------------------------------------------------

def _service(tmp_path: Path, provider: AIProvider | None) -> KnowledgeService:
    return KnowledgeService(KnowledgeBase.default(), KnowledgeStore(tmp_path), provider)


def test_generate_saves_files_without_touching_kb_until_register(tmp_path: Path) -> None:
    service = _service(tmp_path, FakeProvider(GOOD, {**GOOD, "title": "OncePerRequestFilter"}))
    progress: list[tuple[int, int]] = []

    result = service.generate([SLF4J, FILTER], on_progress=lambda d, t: progress.append((d, t)))

    assert [c.id for c in result.created] == [concept_id_for(SLF4J), concept_id_for(FILTER)]
    assert result.failed == [] and progress[-1] == (2, 2)
    assert service.kb.for_annotation("Slf4j") is None  # aún no registrado (hilo del worker)
    service.register(result.created)
    assert service.kb.for_annotation("Slf4j").source is ConceptSource.AI

    reloaded, issues = load_directory(tmp_path)  # lo guardado se vuelve a cargar tal cual
    assert issues == [] and {c.source for c in reloaded} == {ConceptSource.AI}
    assert {c.id for c in reloaded} == {c.id for c in result.created}


def test_network_error_stops_the_batch(tmp_path: Path) -> None:
    service = _service(tmp_path, FakeProvider(AIError(AIErrorKind.NETWORK), GOOD))

    result = service.generate([SLF4J, FILTER])

    assert result.created == []
    assert [(g.name, msg) for g, msg in result.failed] == [
        ("Slf4j", AIError(AIErrorKind.NETWORK).user_message),
        ("OncePerRequestFilter", "No se intentó."),
    ]


def test_invalid_output_skips_only_that_gap(tmp_path: Path) -> None:
    service = _service(tmp_path, FakeProvider({**GOOD, "known": False}, {**GOOD, "title": "OncePerRequestFilter"}))

    result = service.generate([SLF4J, FILTER])

    assert [c.matches.supertypes for c in result.created] == [("OncePerRequestFilter",)]
    assert result.failed[0][0] is SLF4J


def test_unexpected_error_only_skips_that_gap(tmp_path: Path) -> None:
    class Flaky(FakeProvider):
        def complete(self, request):
            if "Slf4j" in request.prompt:
                raise RuntimeError("boom")
            return super().complete(request)

    result = _service(tmp_path, Flaky({**GOOD, "title": "OncePerRequestFilter"})).generate([SLF4J, FILTER])

    assert [g.name for g, _ in result.failed] == ["Slf4j"]
    assert len(result.created) == 1


def test_cancellation(tmp_path: Path) -> None:
    cancel = threading.Event()
    cancel.set()
    result = _service(tmp_path, FakeProvider(GOOD)).generate([SLF4J], cancel=cancel)
    assert result.cancelled and result.created == []


def test_without_provider_generation_is_unavailable(tmp_path: Path) -> None:
    service = _service(tmp_path, None)
    assert not service.can_generate
    with pytest.raises(AIError) as info:
        service.generate([SLF4J])
    assert info.value.kind is AIErrorKind.UNAVAILABLE


def test_delete_ai_concept_removes_file_and_index(tmp_path: Path) -> None:
    service = _service(tmp_path, FakeProvider(GOOD))
    result = service.generate([SLF4J])
    service.register(result.created)

    assert service.delete(concept_id_for(SLF4J))
    assert service.kb.for_annotation("Slf4j") is None
    assert list(tmp_path.glob("*.yaml")) == []


def test_builtin_concepts_cannot_be_deleted(tmp_path: Path) -> None:
    service = _service(tmp_path, None)
    assert not service.delete("spring.transactional")
    assert service.kb.for_annotation("Transactional") is not None


def test_store_never_saves_builtin(tmp_path: Path) -> None:
    builtin = KnowledgeBase.default().get("spring.transactional")
    with pytest.raises(ValueError):
        KnowledgeStore(tmp_path).save(builtin)


def test_privacy_preview_matches_what_is_sent() -> None:
    assert KnowledgeService.privacy_preview([SLF4J]) == [
        "Anotación: @Slf4j · lombok.extern.slf4j.Slf4j",
    ]
