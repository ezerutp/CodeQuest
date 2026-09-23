"""Clasificación de clases Java por convenciones generales (sin framework)."""

from collections.abc import Mapping, Sequence

from codequest.core.analysis.base import FrameworkAnalyzer
from codequest.core.analysis.java.models import JavaClass, TypeKind
from codequest.core.analysis.roles import ComponentRole
from codequest.core.project.models import ProjectInfo

_EXCEPTION_BASES = frozenset({"Exception", "RuntimeException", "Throwable", "Error"})

# (sufijos del nombre, segmentos de paquete, rol). Se evalúan en orden.
_NAME_RULES: tuple[tuple[tuple[str, ...], frozenset[str], ComponentRole], ...] = (
    (("Exception",), frozenset({"exception", "exceptions"}), ComponentRole.EXCEPTION),
    (("DTO", "Dto", "Request", "Response", "Payload"),
     frozenset({"dto", "dtos", "payload", "payloads"}), ComponentRole.DTO),
    (("Mapper",), frozenset({"mapper", "mappers"}), ComponentRole.MAPPER),
    (("Util", "Utils", "Helper", "Helpers"), frozenset({"util", "utils", "helper", "helpers"}),
     ComponentRole.UTILITY),
    (("Config", "Configuration"), frozenset({"config", "configuration"}), ComponentRole.CONFIGURATION),
)


def simple_type_name(type_name: str) -> str:
    """'org.x.JpaRepository<User, Long>' -> 'JpaRepository'."""
    return type_name.split("<", 1)[0].strip().rsplit(".", 1)[-1]


class JavaConventionsAnalyzer(FrameworkAnalyzer):
    """Roles deducibles sin conocer el framework: enums, excepciones, DTO, utilidades..."""

    def supports(self, project: ProjectInfo) -> bool:
        return True

    def classify(self, classes: Sequence[JavaClass]) -> Mapping[str, ComponentRole]:
        by_name = {c.name: c for c in classes}
        return {c.qualified_name: self.role_for(c, by_name) for c in classes}

    def role_for(self, cls: JavaClass, by_name: Mapping[str, JavaClass]) -> ComponentRole:
        if cls.kind is TypeKind.ENUM:
            return ComponentRole.ENUM
        if cls.kind is TypeKind.ANNOTATION:
            return ComponentRole.ANNOTATION
        if self._extends_exception(cls, by_name):
            return ComponentRole.EXCEPTION
        if cls.kind is TypeKind.INTERFACE:
            # Sin anotaciones ni herencia conocida, una interfaz no se clasifica por
            # su paquete: evita contar dos veces UserService + UserServiceImpl.
            return ComponentRole.OTHER
        packages = set(cls.package.split("."))
        for suffixes, package_names, role in _NAME_RULES:
            if cls.name.endswith(suffixes) or packages & package_names:
                return role
        return ComponentRole.OTHER

    @staticmethod
    def _extends_exception(cls: JavaClass, by_name: Mapping[str, JavaClass]) -> bool:
        current: JavaClass | None = cls
        for _ in range(10):  # límite ante jerarquías cíclicas mal parseadas
            if current is None or current.superclass is None:
                return False
            parent = simple_type_name(current.superclass)
            if parent in _EXCEPTION_BASES or parent.endswith("Exception"):
                return True
            current = by_name.get(parent)
        return False
