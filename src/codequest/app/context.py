"""Estado global de solo lectura que la UI necesita mostrar."""

from dataclasses import dataclass

from codequest.core.ai.availability import AIStatus
from codequest.core.project.models import ProjectInfo


@dataclass(frozen=True, slots=True)
class AppContext:
    project: ProjectInfo
    ai: AIStatus
