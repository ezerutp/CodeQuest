"""Proveedor de IA con el SDK oficial de Anthropic (dependencia opcional: pip install 'codequest[ai]')."""

import json
import logging
import os
from typing import Any

from codequest.core.ai.base import AIError, AIErrorKind, AIProvider, AIRequest, AIResponse

log = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5"
MODEL_ENV = "CODEQUEST_AI_MODEL"
# Si el modelo declina una petición, la API la reintenta en el modelo recomendado para ese caso.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
DEFAULT_TIMEOUT_S = 120.0


class AnthropicProvider(AIProvider):
    name = "Claude"

    def __init__(self, model: str | None = None, client: Any = None, timeout: float = DEFAULT_TIMEOUT_S) -> None:
        self.model = model or os.environ.get(MODEL_ENV, "").strip() or DEFAULT_MODEL
        if client is None:
            import anthropic  # import diferido: el paquete es opcional

            # Sin api_key explícita: el SDK la lee del entorno. CodeQuest nunca la guarda ni la registra.
            client = anthropic.Anthropic(timeout=timeout, max_retries=2)
        self._client = client

    def complete(self, request: AIRequest) -> AIResponse:
        params: dict[str, Any] = {
            "model": self.model,
            "max_tokens": request.max_tokens,
            "system": request.system,
            "messages": [{"role": "user", "content": request.prompt}],
            "betas": [FALLBACK_BETA],
            "fallbacks": "default",
        }
        if request.json_schema is not None:
            params["output_config"] = {"format": {"type": "json_schema", "schema": request.json_schema}}

        response = self._send(params)
        log.info("IA %s: request_id=%s tokens in=%s out=%s stop=%s", response.model,
                 getattr(response, "_request_id", None), response.usage.input_tokens,
                 response.usage.output_tokens, response.stop_reason)

        if response.stop_reason == "refusal":
            raise AIError(AIErrorKind.REFUSED)
        if response.stop_reason == "max_tokens":
            raise AIError(AIErrorKind.INVALID_OUTPUT, "respuesta truncada")
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        data = None
        if request.json_schema is not None:
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise AIError(AIErrorKind.INVALID_OUTPUT, "JSON inválido") from exc
            if not isinstance(data, dict):
                raise AIError(AIErrorKind.INVALID_OUTPUT, "se esperaba un objeto JSON")
        return AIResponse(text=text, data=data, model=response.model,
                          input_tokens=response.usage.input_tokens, output_tokens=response.usage.output_tokens)

    def _send(self, params: dict[str, Any]) -> Any:
        import anthropic

        try:
            return self._client.beta.messages.create(**params)
        except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
            raise AIError(AIErrorKind.AUTH) from exc
        except anthropic.RateLimitError as exc:
            raise AIError(AIErrorKind.RATE_LIMIT) from exc
        except (anthropic.APITimeoutError, anthropic.APIConnectionError) as exc:
            raise AIError(AIErrorKind.NETWORK) from exc
        except anthropic.APIStatusError as exc:
            log.warning("Error de la API de IA: %s %s", exc.status_code, getattr(exc, "message", ""))
            raise AIError(AIErrorKind.SERVICE, f"HTTP {exc.status_code}") from exc
