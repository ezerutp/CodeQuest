from pathlib import Path

import pytest

from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.knowledge.loader import KnowledgeFormatError, load_builtin, load_directory, parse_concepts
from codequest.core.knowledge.models import ConceptSource, Topic
from codequest.core.knowledge.validation import concept_problems

VALID = """
version: 1
concepts:
  - id: lombok.data
    title: "@Data"
    topic: other
    matches:
      annotations: [Data]
    summary: Genera getters, setters, equals, hashCode y toString de la clase.
    explanation: |
      Primer párrafo.

      Segundo párrafo.
    analogy: Es como un sello que rellena por ti los formularios repetitivos.
    distractors:
      - Guarda automáticamente la clase en la base de datos al crearla.
      - Convierte la clase en un DTO que solo puede leerse desde la API REST.
      - Marca la clase como inmutable para que ningún campo pueda cambiar.
    youtube_query: Lombok @Data explicado
"""


def _write(directory: Path, name: str, text: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / name).write_text(text, encoding="utf-8")


# --- contenido integrado -------------------------------------------------------------

def test_builtin_knowledge_loads_and_is_indexed() -> None:
    kb = KnowledgeBase.default()

    assert len(kb.concepts) >= 37
    assert kb.for_annotation("Transactional").title == "@Transactional"
    assert kb.for_annotation("RestControllerAdvice") is kb.for_annotation("ControllerAdvice")
    assert kb.for_supertype("JpaRepository").id == "data.jpa-repository"
    assert kb.for_annotation("NoExiste") is None
    assert set(kb.source_counts()) == {ConceptSource.BUILTIN}


def test_every_builtin_concept_passes_quality_rules() -> None:
    for concept in load_builtin():
        assert concept_problems(concept) == [], concept.id
        assert "\n\n" not in concept.summary


def test_explanations_keep_paragraphs() -> None:
    concept = KnowledgeBase.default().get("spring.transactional")
    assert concept.explanation.count("\n\n") >= 2 and not concept.explanation.endswith("\n")


# --- formato ---------------------------------------------------------------------------

def test_parse_valid_concept() -> None:
    (concept,) = parse_concepts(VALID, ConceptSource.USER, "test.yaml")

    assert concept.topic is Topic.OTHER
    assert concept.matches.annotations == ("Data",)
    assert concept.explanation == "Primer párrafo.\n\nSegundo párrafo."
    assert concept.source is ConceptSource.USER


@pytest.mark.parametrize(("change", "error"), [
    (("summary: Genera", "summary: ''  #"), "summary"),
    (("      - Marca la clase como inmutable para que ningún campo pueda cambiar.\n", ""), "distractores"),
    (("topic: other", "topic: marte"), "tema desconocido"),
    (("      annotations: [Data]", "      annotations: []"), "matches"),
    (("version: 1", "version: 9"), "versión"),
    (("Genera getters, setters, equals, hashCode y toString de la clase.",
      "Genera getters, setters, equals, hashCode, toString, un constructor con todos los campos requeridos y más."),
     "más larga"),
])
def test_invalid_concepts_are_rejected(change: tuple[str, str], error: str) -> None:
    with pytest.raises(KnowledgeFormatError, match=error):
        parse_concepts(VALID.replace(*change), ConceptSource.USER, "test.yaml")


def test_rejects_broken_yaml() -> None:
    with pytest.raises(KnowledgeFormatError, match="YAML inválido"):
        parse_concepts("concepts: [", ConceptSource.USER, "x.yaml")


# --- capas -----------------------------------------------------------------------------

def test_user_directory_adds_concepts(tmp_path: Path) -> None:
    _write(tmp_path, "lombok.yaml", VALID)

    kb = KnowledgeBase.load(tmp_path)

    assert kb.for_annotation("Data").source is ConceptSource.USER
    assert kb.source_counts()[ConceptSource.USER] == 1
    assert kb.issues == []


def test_ai_generated_files_keep_their_source(tmp_path: Path) -> None:
    _write(tmp_path, "lombok.yaml", "source: ai\n" + VALID)

    assert KnowledgeBase.load(tmp_path).for_annotation("Data").source is ConceptSource.AI


def test_user_file_cannot_claim_to_be_builtin(tmp_path: Path) -> None:
    _write(tmp_path, "fake.yaml", "source: builtin\n" + VALID)

    kb = KnowledgeBase.load(tmp_path)

    assert kb.for_annotation("Data") is None
    assert "builtin" in kb.issues[0].message


def test_builtin_wins_over_user_duplicates(tmp_path: Path) -> None:
    override = VALID.replace("id: lombok.data", "id: my.transactional").replace("[Data]", "[Transactional]")
    _write(tmp_path, "override.yaml", override)

    kb = KnowledgeBase.load(tmp_path)

    assert kb.for_annotation("Transactional").source is ConceptSource.BUILTIN
    assert kb.get("my.transactional") is None
    assert "@Transactional" in kb.issues[0].message


def test_invalid_user_file_is_skipped_and_reported(tmp_path: Path) -> None:
    _write(tmp_path, "good.yaml", VALID)
    _write(tmp_path, "broken.yaml", "concepts: [")

    kb = KnowledgeBase.load(tmp_path)

    assert kb.for_annotation("Data") is not None
    assert [(i.location, i.message) for i in kb.issues] == [
        ("broken.yaml", "YAML inválido en la línea 2: did not find expected node content"),
    ]


def test_missing_user_directory_is_fine(tmp_path: Path) -> None:
    concepts, issues = load_directory(tmp_path / "no-existe")
    assert concepts == [] and issues == []


def test_duplicated_builtin_content_is_a_bug() -> None:
    (concept,) = parse_concepts(VALID, ConceptSource.BUILTIN, "a.yaml")
    with pytest.raises(ValueError, match="integrado duplicado"):
        KnowledgeBase([concept, concept])
