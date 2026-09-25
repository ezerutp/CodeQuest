"""Traducción de modelos del núcleo a textos/estados de presentación."""

import html
import re
from datetime import datetime, timedelta

from codequest.core.ai.availability import AIStatus
from codequest.core.analysis.roles import ComponentRole
from codequest.core.lsp.jdtls import DOWNLOAD_SIZE_MB
from codequest.core.lsp.models import ServerState, ServerStatus
from codequest.ui.theme import current_palette


def ai_indicator(ai: AIStatus, enabled: bool = True) -> tuple[str, str]:
    """Devuelve (texto, estado) para un StatusIndicator."""
    if ai.available and not enabled:
        return "IA desactivada", "off"
    if ai.available:
        return f"{ai.provider} conectada", "on"
    if ai.provider:
        return f"{ai.provider}: falta configuración", "warn"
    return "Modo local", "off"


def language_server_indicator(status: ServerStatus) -> tuple[str, str, str]:
    """(texto, estado, detalle) del servidor de lenguaje Java para un StatusIndicator."""
    match status.state:
        case ServerState.NOT_INSTALLED:
            return "No instalado", "off", (
                f"Descárgalo para ver sugerencias mientras escribes código, como en VS Code. Son unos "
                f"{DOWNLOAD_SIZE_MB} MB y se guardan en la carpeta de datos de CodeQuest.")
        case ServerState.NO_JAVA:
            return "Falta Java", "warn", status.detail
        case ServerState.STARTING:
            return "Iniciando…", "warn", status.detail or "La primera vez puede tardar unos minutos."
        case ServerState.READY:
            return "Listo", "on", "Las sugerencias están disponibles en los ejercicios de este proyecto."
        case ServerState.FAILED:
            return "No se pudo iniciar", "warn", f"{status.detail}. Hay más detalles en el registro (logs)."
        case _:
            detail = f" ({status.detail})" if status.detail else ""
            return "Instalado", "off", f"Se inicia al abrir un proyecto Java{detail}."


# (singular, plural) por rol, para textos como "3 Enums" o "1 Excepción".
ROLE_LABELS: dict[ComponentRole, tuple[str, str]] = {
    ComponentRole.ENTITY: ("Entity", "Entities"),
    ComponentRole.CONTROLLER: ("Controller", "Controllers"),
    ComponentRole.SERVICE: ("Service", "Services"),
    ComponentRole.REPOSITORY: ("Repository", "Repositories"),
    ComponentRole.DTO: ("DTO", "DTOs"),
    ComponentRole.CONFIGURATION: ("Configuración", "Configuraciones"),
    ComponentRole.ENUM: ("Enum", "Enums"),
    ComponentRole.EXCEPTION: ("Excepción", "Excepciones"),
    ComponentRole.UTILITY: ("Utilidad", "Utilidades"),
    ComponentRole.MAPPER: ("Mapper", "Mappers"),
    ComponentRole.COMPONENT: ("Componente", "Componentes"),
    ComponentRole.ANNOTATION: ("Anotación propia", "Anotaciones propias"),
    ComponentRole.OTHER: ("Otra clase", "Otras clases"),
}


def role_count(role: ComponentRole, count: int) -> str:
    singular, plural = ROLE_LABELS[role]
    return f"{count} {singular if count == 1 else plural}"


def plural(count: int, singular: str, plural_form: str) -> str:
    return f"{count} {singular if count == 1 else plural_form}"


def duration(seconds: float) -> str:
    return f"{seconds * 1000:.0f} ms" if seconds < 1 else f"{seconds:.1f} s".replace(".", ",")


def role_color(role: ComponentRole) -> str:
    """Color del icono de un rol en el explorador (ayuda a escanear el árbol)."""
    p = current_palette()
    return {
        ComponentRole.ENTITY: p.syntax_number,
        ComponentRole.CONTROLLER: p.syntax_annotation,
        ComponentRole.SERVICE: p.syntax_type,
        ComponentRole.REPOSITORY: p.success,
        ComponentRole.DTO: p.syntax_string,
        ComponentRole.ENUM: p.warning,
        ComponentRole.EXCEPTION: p.danger,
    }.get(role, p.text_muted)


_INLINE_CODE = re.compile(r"`([^`]+)`")


def inline_code_html(text: str) -> str:
    """Texto con `código` entre backticks -> HTML para QLabel, con el código en monoespaciada."""
    color = current_palette().syntax_annotation
    style = f"font-family: 'JetBrains Mono', 'Source Code Pro', monospace; color: {color};"
    return _INLINE_CODE.sub(lambda m: f'<span style="{style}">{m.group(1)}</span>', html.escape(text))


_MONTHS = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")


def session_date(iso: str, now: datetime | None = None) -> str:
    """'2026-09-23T19:05:00+00:00' -> 'Hoy · 14:05' en hora local (o 'Ayer', o '12 sep')."""
    moment = datetime.fromisoformat(iso).astimezone()
    today = (now or datetime.now().astimezone()).date()
    clock = moment.strftime("%H:%M")
    if moment.date() == today:
        return f"Hoy · {clock}"
    if moment.date() == today - timedelta(days=1):
        return f"Ayer · {clock}"
    return f"{moment.day} {_MONTHS[moment.month - 1]} · {clock}"


def ai_detail(ai: AIStatus, enabled: bool = True) -> str:
    if ai.available and not enabled:
        return "Desactivada en Configuración. Todo funciona en modo local."
    return ai.detail
