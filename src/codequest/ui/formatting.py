"""Traducción de modelos del núcleo a textos/estados de presentación."""

from codequest.core.ai.availability import AIStatus
from codequest.core.analysis.roles import ComponentRole
from codequest.ui.theme import current_palette


def ai_indicator(ai: AIStatus) -> tuple[str, str]:
    """Devuelve (texto, estado) para un StatusIndicator."""
    if ai.available:
        return f"{ai.provider} conectada", "on"
    if ai.provider:
        return f"{ai.provider}: falta configuración", "warn"
    return "Modo local", "off"


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
