"""Detección de proveedores de IA disponibles.

Solo se comprueba si la variable de entorno existe: la key nunca se copia a
este módulo, ni se imprime, ni se registra.
"""

import importlib.util
import os
from collections.abc import Mapping
from dataclasses import dataclass

ANTHROPIC_KEY_ENV = "ANTHROPIC_API_KEY"


@dataclass(frozen=True, slots=True)
class AIStatus:
    available: bool
    provider: str | None
    detail: str


def detect_ai_status(env: Mapping[str, str] | None = None) -> AIStatus:
    env = os.environ if env is None else env
    if not env.get(ANTHROPIC_KEY_ENV, "").strip():
        return AIStatus(False, None, f"Define {ANTHROPIC_KEY_ENV} para activar las funciones con IA.")
    if importlib.util.find_spec("anthropic") is None:
        return AIStatus(False, "Claude", "Key encontrada, pero falta el paquete: pip install 'codequest[ai]'.")
    return AIStatus(True, "Claude", "Las respuestas abiertas se evaluarán con Claude.")
