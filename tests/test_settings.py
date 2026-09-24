import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from codequest.core.ai.base import AIProvider, AIRequest, AIResponse
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.knowledge.store import KnowledgeStore
from codequest.core.settings import Settings, SettingsStore
from codequest.services.explain_service import ExplainService
from codequest.services.knowledge_service import KnowledgeService


def test_missing_file_gives_defaults(tmp_path: Path) -> None:
    assert SettingsStore(tmp_path / "settings.json").load() == Settings()


def test_roundtrip(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "nested" / "settings.json")
    store.save(Settings(ai_enabled=False, ai_model="claude-sonnet-5"))

    assert store.load() == Settings(ai_enabled=False, ai_model="claude-sonnet-5")
    assert list((tmp_path / "nested").glob(".settings-*")) == []  # sin temporales huérfanos


@pytest.mark.parametrize("content", ["{roto", "[1, 2]", '"texto"'])
def test_corrupt_file_gives_defaults(tmp_path: Path, content: str) -> None:
    path = tmp_path / "settings.json"
    path.write_text(content)
    assert SettingsStore(path).load() == Settings()


def test_invalid_values_and_unknown_keys_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"ai_enabled": "sí", "ai_model": "  ", "tema": "claro"}))
    assert SettingsStore(path).load() == Settings()


def test_env_model_overrides_saved_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("anthropic")
    from codequest.core.ai.anthropic_provider import DEFAULT_MODEL, AnthropicProvider

    client = SimpleNamespace()
    monkeypatch.delenv("CODEQUEST_AI_MODEL", raising=False)
    assert AnthropicProvider(model="claude-haiku-4-5", client=client).model == "claude-haiku-4-5"
    assert AnthropicProvider(client=client).model == DEFAULT_MODEL
    monkeypatch.setenv("CODEQUEST_AI_MODEL", "claude-sonnet-5")
    assert AnthropicProvider(model="claude-haiku-4-5", client=client).model == "claude-sonnet-5"


class Fake(AIProvider):
    name = "Fake"

    def complete(self, request: AIRequest) -> AIResponse:
        return AIResponse("x", None, "fake")


def test_services_switch_provider_at_runtime(tmp_path: Path) -> None:
    knowledge = KnowledgeService(KnowledgeBase.default(), KnowledgeStore(tmp_path), Fake())
    explain = ExplainService(Fake())
    explain._cache["k"] = "vieja"

    for service in (knowledge, explain):
        service.set_provider(None)
    assert not knowledge.can_generate and not explain.can_explain
    assert explain._cache == {}  # otra configuración de IA: fuera las explicaciones previas

    for service in (knowledge, explain):
        service.set_provider(Fake())
    assert knowledge.can_generate and explain.can_explain


@pytest.mark.parametrize(("value", "expected"), [(14, 14), (9, 9), (20, 20), (8, 11), (21, 11), ("12", 11), (True, 11)])
def test_editor_font_size_is_validated(tmp_path: Path, value: object, expected: int) -> None:
    path = tmp_path / "settings.json"
    path.write_text(json.dumps({"editor_font_size": value}))
    assert SettingsStore(path).load().editor_font_size == expected
