import random
from collections import Counter
from pathlib import Path

import pytest

from codequest.core.analysis.model import ProjectModel
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.questions.generator import CHOICES_PER_QUESTION, QuestionGenerator
from codequest.services.project_service import ProjectService


@pytest.fixture(scope="module")
def shop_model() -> ProjectModel:
    service = ProjectService()
    return service.analyze(service.detect(Path(__file__).parent / "fixtures" / "shop"))


@pytest.fixture(scope="module")
def generator() -> QuestionGenerator:
    return QuestionGenerator(KnowledgeBase.default())


def test_drafts_cover_classes_fields_methods_parameters_and_supertypes(shop_model, generator) -> None:
    prompts = {d.key: d.prompt for d in generator.drafts(shop_model)}

    assert prompts["spring.rest-controller:com.example.shop.controller.UserController"] == (
        "¿Qué función cumple `@RestController` en la clase `UserController`?"
    )
    update_key = "spring.transactional:com.example.shop.service.UserServiceImpl#updateUser(Long, UserDTO, String...)"
    assert prompts[update_key] == (
        "En tu método `updateUser()` de `UserServiceImpl`, ¿qué propósito tiene `@Transactional`?"
    )
    assert prompts["jpa.one-to-many:com.example.shop.entity.User#orders"] == (
        "En el campo `orders` de `User`, ¿qué indica `@OneToMany`?"
    )
    assert prompts["spring.path-variable:com.example.shop.controller.UserController#getUser(Long):id"] == (
        "En `getUser()`, ¿qué hace `@PathVariable` con el parámetro `id`?"
    )
    assert prompts["data.jpa-repository:com.example.shop.repository.UserRepository"] == (
        "¿Qué obtiene `UserRepository` al extender `JpaRepository<User, Long>`?"
    )


def test_unknown_annotations_and_test_classes_produce_no_questions(shop_model, generator) -> None:
    drafts = generator.drafts(shop_model)

    assert not any("Override" in d.prompt or "SuppressWarnings" in d.prompt for d in drafts)
    assert not any(d.class_name.endswith("UserControllerTest") for d in drafts)


def test_snippet_points_at_real_code(shop_model, generator) -> None:
    draft = next(d for d in generator.drafts(shop_model) if d.key.startswith("spring.get-mapping:")
                 and "getUser" in d.key)

    assert (draft.snippet.start_line, draft.snippet.end_line, draft.snippet.focus_lines) == (25, 28, (25,))


def test_generated_questions_have_one_correct_choice(shop_model, generator) -> None:
    questions = generator.generate(shop_model, limit=50, rng=random.Random(7))

    for q in questions:
        assert len(q.choices) == CHOICES_PER_QUESTION == len(set(q.choices))
        assert q.correct_choice == q.concept.summary
        assert sum(c == q.concept.summary for c in q.choices) == 1


def test_round_varies_concepts(shop_model, generator) -> None:
    questions = generator.generate(shop_model, limit=10, rng=random.Random(3))

    concepts = Counter(q.concept.id for q in questions)
    assert len(questions) == 10
    assert max(concepts.values()) == 1  # hay más de 10 conceptos: ninguno se repite


def test_filter_by_class(shop_model, generator) -> None:
    questions = generator.generate(shop_model, limit=50, class_name="com.example.shop.entity.User")

    assert questions and all(q.class_name == "com.example.shop.entity.User" for q in questions)
    assert generator.generate(shop_model, class_name="com.example.shop.util.DateUtils") == []


def test_same_seed_same_round(shop_model, generator) -> None:
    first = generator.generate(shop_model, rng=random.Random(42))
    second = generator.generate(shop_model, rng=random.Random(42))

    assert [(q.key, q.choices) for q in first] == [(q.key, q.choices) for q in second]
