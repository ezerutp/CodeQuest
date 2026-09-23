"""Traducción de modelos del núcleo a textos/estados de presentación."""

from codequest.core.ai.availability import AIStatus


def ai_indicator(ai: AIStatus) -> tuple[str, str]:
    """Devuelve (texto, estado) para un StatusIndicator."""
    if ai.available:
        return f"{ai.provider} conectada", "on"
    if ai.provider:
        return f"{ai.provider}: falta configuración", "warn"
    return "Modo local", "off"
