"""Abstracción de proveedores de IA. La UI y los servicios solo conocen esto, nunca el SDK."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AIErrorKind(StrEnum):
    AUTH = "auth"  # key inválida o sin permisos
    RATE_LIMIT = "rate_limit"
    NETWORK = "network"  # sin conexión o timeout
    SERVICE = "service"  # error del servidor o petición rechazada por la API
    REFUSED = "refused"  # el modelo declinó responder
    INVALID_OUTPUT = "invalid_output"  # respuesta truncada o que no cumple lo pedido
    NOT_KNOWN = "not_known"  # el modelo no conoce el tema con certeza: no se inventa nada
    UNAVAILABLE = "unavailable"  # no hay proveedor configurado


_MESSAGES = {
    AIErrorKind.AUTH: "La API key no es válida o no tiene permisos. Revisa ANTHROPIC_API_KEY.",
    AIErrorKind.RATE_LIMIT: "Se alcanzó el límite de uso de la IA. Espera un momento y vuelve a intentarlo.",
    AIErrorKind.NETWORK: "No se pudo conectar con la IA. Revisa tu conexión a internet.",
    AIErrorKind.SERVICE: "El servicio de IA devolvió un error. Vuelve a intentarlo más tarde.",
    AIErrorKind.REFUSED: "La IA no quiso responder a esta petición.",
    AIErrorKind.INVALID_OUTPUT: "La respuesta de la IA no tenía el formato esperado.",
    AIErrorKind.NOT_KNOWN: "La IA no lo conoce con certeza, así que prefiero no inventar una explicación.",
    AIErrorKind.UNAVAILABLE: "La IA no está configurada.",
}


class AIError(Exception):
    """Error de IA con un mensaje apto para mostrar al estudiante (nunca incluye la key)."""

    def __init__(self, kind: AIErrorKind, detail: str = "") -> None:
        self.kind = kind
        self.detail = detail
        super().__init__(_MESSAGES[kind] + (f" ({detail})" if detail else ""))

    @property
    def user_message(self) -> str:
        return _MESSAGES[self.kind]


@dataclass(frozen=True, slots=True)
class AIRequest:
    system: str
    prompt: str
    json_schema: dict[str, Any] | None = None  # si se indica, la respuesta es JSON que lo cumple
    max_tokens: int = 4000


@dataclass(frozen=True, slots=True)
class AIResponse:
    text: str
    data: dict[str, Any] | None  # JSON ya parseado cuando la petición traía `json_schema`
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class AIProvider(ABC):
    name: str  # "Claude"

    @abstractmethod
    def complete(self, request: AIRequest) -> AIResponse:
        """Llamada bloqueante: ejecutarla siempre fuera del hilo de la UI. Lanza AIError."""
