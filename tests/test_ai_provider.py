from types import SimpleNamespace

import pytest

anthropic = pytest.importorskip("anthropic")  # dependencia opcional: pip install 'codequest[ai]'
httpx2 = pytest.importorskip("httpx2")

from codequest.core.ai.anthropic_provider import DEFAULT_MODEL, FALLBACK_BETA, AnthropicProvider  # noqa: E402
from codequest.core.ai.base import AIError, AIErrorKind, AIRequest  # noqa: E402


class FakeMessages:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.calls: list[dict] = []
        self._response = response
        self._error = error

    def create(self, **params):
        self.calls.append(params)
        if self._error:
            raise self._error
        return self._response


def _client(messages: FakeMessages):
    return SimpleNamespace(beta=SimpleNamespace(messages=messages))


def _response(text: str, stop_reason: str = "end_turn"):
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        stop_reason=stop_reason, model=DEFAULT_MODEL,
        usage=SimpleNamespace(input_tokens=10, output_tokens=5),
    )


SCHEMA = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"],
          "additionalProperties": False}


def test_structured_request_parameters_and_parsing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEQUEST_AI_MODEL", raising=False)
    messages = FakeMessages(_response('{"a": "hola"}'))
    provider = AnthropicProvider(client=_client(messages))

    result = provider.complete(AIRequest(system="sys", prompt="p", json_schema=SCHEMA))

    params = messages.calls[0]
    assert params["model"] == DEFAULT_MODEL
    assert params["system"] == "sys"
    assert params["messages"] == [{"role": "user", "content": "p"}]
    assert params["output_config"] == {"format": {"type": "json_schema", "schema": SCHEMA}}
    assert params["betas"] == [FALLBACK_BETA] and params["fallbacks"] == "default"
    assert result.data == {"a": "hola"} and result.text == '{"a": "hola"}'


def test_plain_text_request_has_no_output_format() -> None:
    messages = FakeMessages(_response("texto"))

    result = AnthropicProvider(client=_client(messages)).complete(AIRequest(system="s", prompt="p"))

    assert "output_config" not in messages.calls[0]
    assert result.text == "texto" and result.data is None


def test_model_can_be_overridden_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEQUEST_AI_MODEL", "claude-sonnet-5")
    assert AnthropicProvider(client=_client(FakeMessages())).model == "claude-sonnet-5"


@pytest.mark.parametrize(("stop_reason", "kind"), [("refusal", AIErrorKind.REFUSED),
                                                  ("max_tokens", AIErrorKind.INVALID_OUTPUT)])
def test_stop_reasons(stop_reason: str, kind: AIErrorKind) -> None:
    provider = AnthropicProvider(client=_client(FakeMessages(_response("{}", stop_reason))))
    with pytest.raises(AIError) as info:
        provider.complete(AIRequest(system="s", prompt="p", json_schema=SCHEMA))
    assert info.value.kind is kind


def test_invalid_json_is_reported() -> None:
    provider = AnthropicProvider(client=_client(FakeMessages(_response("no es json"))))
    with pytest.raises(AIError) as info:
        provider.complete(AIRequest(system="s", prompt="p", json_schema=SCHEMA))
    assert info.value.kind is AIErrorKind.INVALID_OUTPUT


def _status_error(cls, status: int):
    request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("error", response=httpx2.Response(status, request=request), body=None)


@pytest.mark.parametrize(("error", "kind"), [
    (lambda: _status_error(anthropic.AuthenticationError, 401), AIErrorKind.AUTH),
    (lambda: _status_error(anthropic.RateLimitError, 429), AIErrorKind.RATE_LIMIT),
    (lambda: _status_error(anthropic.InternalServerError, 500), AIErrorKind.SERVICE),
    (lambda: anthropic.APIConnectionError(request=httpx2.Request("POST", "https://x")), AIErrorKind.NETWORK),
    (lambda: anthropic.APITimeoutError(request=httpx2.Request("POST", "https://x")), AIErrorKind.NETWORK),
])
def test_sdk_errors_are_translated(error, kind: AIErrorKind) -> None:
    provider = AnthropicProvider(client=_client(FakeMessages(error=error())))
    with pytest.raises(AIError) as info:
        provider.complete(AIRequest(system="s", prompt="p"))
    assert info.value.kind is kind
    assert "sk-" not in str(info.value)
