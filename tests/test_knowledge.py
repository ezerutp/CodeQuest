import pytest

from codequest.core.knowledge.base import ANNOTATION_CONCEPTS, KnowledgeBase
from codequest.core.knowledge.models import Concept, Topic
from codequest.core.knowledge.spring import CONCEPTS


def test_default_knowledge_base_is_consistent() -> None:
    kb = KnowledgeBase.default()  # valida índices y distractores al construirse

    assert len(kb.concepts) == len(CONCEPTS)
    assert kb.for_annotation("Transactional").title == "@Transactional"
    assert kb.for_supertype("JpaRepository").id == "data.jpa-repository"
    assert kb.for_annotation("NoExiste") is None


def test_every_concept_is_reachable_and_complete() -> None:
    kb = KnowledgeBase.default()
    reachable = set(ANNOTATION_CONCEPTS.values()) | {"data.jpa-repository", "data.crud-repository"}

    for concept in kb.concepts:
        assert concept.id in reachable, f"{concept.id} no está en ningún índice"
        assert concept.summary and concept.explanation and concept.analogy and concept.youtube_query


def test_correct_answer_does_not_stand_out_by_length() -> None:
    """Si la correcta fuera notablemente más larga, se podría acertar sin saber."""
    too_long = [c.id for c in CONCEPTS if len(c.summary) > 1.10 * max(len(d) for d in c.distractors)]
    assert too_long == []


def _concept(**overrides) -> Concept:
    base = dict(id="x", title="@X", topic=Topic.WEB, summary="ok", explanation="e", analogy="a",
                distractors=("d1", "d2", "d3"), youtube_query="q")
    return Concept(**{**base, **overrides})


def test_rejects_concepts_with_too_few_distractors() -> None:
    with pytest.raises(ValueError, match="distractores"):
        KnowledgeBase([_concept(distractors=("d1", "d1", "d2"))], {}, {})


def test_rejects_summary_among_distractors() -> None:
    with pytest.raises(ValueError, match="correcta"):
        KnowledgeBase([_concept(distractors=("ok", "d2", "d3"))], {}, {})


def test_rejects_index_pointing_to_unknown_concept() -> None:
    with pytest.raises(ValueError, match="inexistentes"):
        KnowledgeBase([_concept()], {"Foo": "no-existe"}, {})
