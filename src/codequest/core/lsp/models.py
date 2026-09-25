"""Modelos inmutables del servidor de lenguaje: lo que la UI necesita, sin detalles del protocolo."""

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class ServerState(StrEnum):
    NOT_INSTALLED = "not_installed"  # jdtls no está descargado
    NO_JAVA = "no_java"  # falta un JDK compatible
    STOPPED = "stopped"  # instalado, sin arrancar (p. ej. el proyecto no es Java)
    STARTING = "starting"
    READY = "ready"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class ServerStatus:
    state: ServerState
    detail: str = ""  # texto para el estudiante (versión de Java, motivo del fallo…)

    @property
    def is_ready(self) -> bool:
        return self.state is ServerState.READY


@dataclass(frozen=True, slots=True)
class CompletionItem:
    label: str  # lo que se muestra: "eliminar(Long id) : void"
    insert_text: str  # lo que se escribe: "eliminar"
    kind: str = "text"  # method, field, class, constant…
    detail: str = ""


# Tipos de CompletionItemKind del protocolo LSP que mostramos con un nombre propio.
_KINDS = {2: "method", 3: "function", 4: "constructor", 5: "field", 6: "variable", 7: "class", 8: "interface",
          9: "module", 10: "property", 13: "enum", 14: "keyword", 15: "snippet", 20: "enum_member",
          21: "constant", 25: "type_parameter"}


def completion_items(result: Any) -> list[CompletionItem]:
    """Convierte la respuesta de `textDocument/completion` (lista o CompletionList)."""
    raw = result.get("items", []) if isinstance(result, dict) else result or []
    items: list[CompletionItem] = []
    for entry in raw:
        if not isinstance(entry, dict) or not entry.get("label"):
            continue
        edit = entry.get("textEdit")
        text = edit.get("newText") if isinstance(edit, dict) else None
        items.append(CompletionItem(
            label=str(entry["label"]),
            insert_text=str(text or entry.get("insertText") or entry.get("filterText") or entry["label"]),
            kind=_KINDS.get(entry.get("kind", 0), "text"),
            detail=str(entry.get("detail") or ""),
        ))
    return items
