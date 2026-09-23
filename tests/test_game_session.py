import pytest

from codequest.core.analysis.snippets import SnippetRef
from codequest.core.games.base import GameSession, Outcome, SessionError
from codequest.core.games.multiple_choice import MultipleChoiceMode
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.questions.models import Question


def _question(n: int) -> Question:
    concept = KnowledgeBase.default().for_annotation("Transactional")
    return Question(key=f"q{n}", prompt="?", concept=concept, class_name="C", snippet=SnippetRef("f", 1, 1),
                    choices=("a", "b", "c", "d"), correct_index=1)


def _session(n: int = 3) -> GameSession:
    return GameSession(MultipleChoiceMode(), [_question(i) for i in range(n)])


def test_full_round() -> None:
    session = _session()

    assert session.answer(1).outcome is Outcome.CORRECT
    session.next()
    assert session.answer(0).outcome is Outcome.INCORRECT
    session.next()
    assert session.skip().outcome is Outcome.SKIPPED
    assert session.next() is None

    assert session.is_finished
    assert session.correct_count == 1
    assert [e.question.key for e in session.to_review()] == ["q1", "q2"]


def test_question_stays_current_while_reviewing_explanation() -> None:
    session = _session()
    session.answer(1)

    assert session.is_answered and session.position == 0 and session.current.key == "q0"


def test_cannot_answer_twice_or_skip_ahead() -> None:
    session = _session()
    with pytest.raises(SessionError):
        session.next()
    session.answer(1)
    with pytest.raises(SessionError):
        session.answer(2)
    with pytest.raises(SessionError):
        session.skip()


def test_cannot_answer_after_finish() -> None:
    session = _session(1)
    session.skip()
    session.next()
    with pytest.raises(SessionError):
        session.answer(0)


def test_streak_counts_recent_correct_answers() -> None:
    session = _session(4)
    for choice in (0, 1, 1):
        session.answer(choice)
        session.next()

    assert session.streak == 2


def test_rejects_out_of_range_choice() -> None:
    with pytest.raises(ValueError):
        _session().answer(7)


def test_empty_session_is_finished() -> None:
    assert _session(0).is_finished
