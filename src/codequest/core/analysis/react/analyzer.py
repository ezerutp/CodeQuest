"""Analizador de React: asigna roles a clases TypeScript/TSX según su función."""

import logging
from collections.abc import Sequence

from codequest.core.analysis.base import FrameworkAnalyzer
from codequest.core.analysis.react.roles import ReactRole
from codequest.core.analysis.typescript.models import TSClass
from codequest.core.project.models import Framework, ProjectInfo

log = logging.getLogger(__name__)


class ReactAnalyzer(FrameworkAnalyzer):
    """Clasifica clases TypeScript/TSX en roles de React."""

    def supports(self, info: ProjectInfo) -> bool:
        return info.framework is Framework.REACT

    def classify(self, classes: Sequence[TSClass]) -> dict[str, ReactRole]:
        roles: dict[str, ReactRole] = {}
        for cls in classes:
            roles[cls.qualified_name] = self._classify(cls)
        return roles

    def _classify(self, cls: TSClass) -> ReactRole:
        if cls.is_hook:
            return ReactRole.HOOK
        if cls.is_component:
            return ReactRole.COMPONENT
        if cls.kind.value == "interface":
            return ReactRole.TYPE
        if cls.kind.value == "type":
            return ReactRole.TYPE
        if cls.kind.value == "enum":
            return ReactRole.ENUM
        if cls.kind.value == "class":
            # Clase que no es componente ni hook: puede ser un servicio o utilidad
            if any(m in ("static",) for m in cls.modifiers) or cls.name.startswith("use"):
                return ReactRole.HOOK
            return ReactRole.SERVICE
        return ReactRole.UTILITY
