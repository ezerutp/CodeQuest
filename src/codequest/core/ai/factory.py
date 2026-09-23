"""Crea el proveedor de IA según el estado detectado al arrancar."""

import logging

from codequest.core.ai.availability import AIStatus
from codequest.core.ai.base import AIProvider

log = logging.getLogger(__name__)


def create_provider(status: AIStatus) -> AIProvider | None:
    if not status.available:
        return None
    try:
        from codequest.core.ai.anthropic_provider import AnthropicProvider

        return AnthropicProvider()
    except Exception as exc:  # p. ej. SDK roto o credenciales ilegibles: la app sigue sin IA
        log.warning("No se pudo iniciar el proveedor de IA: %s", type(exc).__name__)
        return None
