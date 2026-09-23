import importlib.util

from codequest.core.ai.availability import detect_ai_status


def test_local_mode_without_key() -> None:
    status = detect_ai_status({})
    assert not status.available
    assert status.provider is None


def test_blank_key_counts_as_missing() -> None:
    assert not detect_ai_status({"ANTHROPIC_API_KEY": "   "}).available


def test_key_is_never_exposed_in_status() -> None:
    secret = "sk-ant-test-1234567890abcdef"
    status = detect_ai_status({"ANTHROPIC_API_KEY": secret})
    assert status.provider == "Claude"
    assert secret not in repr(status)
    assert status.available == (importlib.util.find_spec("anthropic") is not None)
