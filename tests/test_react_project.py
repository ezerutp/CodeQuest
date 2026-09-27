"""Un proyecto React: análisis, informe de conocimiento y preguntas de todos los modos."""

import random
from pathlib import Path

import pytest

from codequest.core.ai.context import ContextBuilder
from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.react.roles import ReactRole
from codequest.core.games.catalog import COMPARISON, EXPLAIN_CODE, FIND_ERROR, FIX_CODE, MULTIPLE_CHOICE, TRUE_FALSE
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.project.models import Framework
from codequest.core.questions.generator import QuestionGenerator
from codequest.core.questions.react import REACT_RULES
from codequest.services.learning_service import LearningService
from codequest.services.project_service import ProjectService


@pytest.fixture
def react_project(tmp_path: Path) -> Path:
    (tmp_path / "package.json").write_text('{"dependencies": {"react": "^18.0.0"}}')
    src = tmp_path / "src"
    src.mkdir()
    (src / "App.tsx").write_text("""
import { useState } from 'react';
export default function App() {
  const [n, setN] = useState(0);
  return (<button onClick={() => setN(n + 1)}>{n}</button>);
}
""")
    (src / "api.ts").write_text("""
export interface User { id: number; name: string }
export class ApiClient extends BaseClient {
  private base = '/api';
  constructor(base: string) { super(); this.base = base; }
  getUser(id: number): Promise<User> { return fetch(this.base); }
}
export const useUsers = () => useState<User[]>([]);
""")
    return tmp_path


@pytest.fixture
def react_model(react_project: Path) -> ProjectModel:
    service = ProjectService()
    return service.analyze(service.detect(react_project))


def test_react_project_is_analyzed(react_model: ProjectModel) -> None:
    assert react_model.info.framework is Framework.REACT
    assert react_model.role_of(next(c for c in react_model.classes if c.name == "App")) is ReactRole.COMPONENT
    assert react_model.java_classes == ()


@pytest.mark.parametrize("mode", [MULTIPLE_CHOICE, TRUE_FALSE, EXPLAIN_CODE, FIND_ERROR, FIX_CODE, COMPARISON])
def test_every_game_mode_has_react_questions(react_model: ProjectModel, mode: str) -> None:
    learning = LearningService(rng=random.Random(1))

    session = learning.start_session(react_model, mode)

    assert session.questions, mode
    for question in session.questions:
        assert question.class_name in {"App", "useUsers"}
        ContextBuilder(react_model).build(question.class_name, question.snippet)
        if question.mutation is not None:  # la mutación se aplica sobre el fragmento real
            snippet = ProjectService.read_snippet(react_model, question.snippet)
            assert question.mutation.apply(snippet.text, snippet.start_line) != snippet.text


def test_hook_questions_point_to_the_real_call(react_model: ProjectModel) -> None:
    drafts = QuestionGenerator(KnowledgeBase.default(), REACT_RULES).drafts(react_model, class_name="App")
    by_concept = {d.concept.id: d for d in drafts}

    use_state = by_concept["react.use-state"]
    assert use_state.prompt == "¿Qué hace `useState` en el componente `App`?"
    assert use_state.snippet.focus_lines == (4,)
    assert "react.use-state" in {u.concept.id for u in LearningService().knowledge_report(react_model).used}


def test_find_error_does_not_reveal_the_line(react_model: ProjectModel) -> None:
    for question in LearningService().start_session(react_model, FIND_ERROR).questions:
        assert question.snippet.focus_lines == ()
        assert question.mutation.original in {"useState"}
