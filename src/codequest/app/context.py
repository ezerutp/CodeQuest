"""Estado global de solo lectura que la UI necesita mostrar."""

from dataclasses import dataclass

from codequest.core.ai.availability import AIStatus
from codequest.core.project.models import ProjectInfo


@dataclass(frozen=True, slots=True)
class AppContext:
    project: ProjectInfo
    ai: AIStatus
    ai_enabled: bool = True  # el usuario puede apagar la IA en Configuración aunque haya key

    @property
    def ai_active(self) -> bool:
        return self.ai.available and self.ai_enabled
