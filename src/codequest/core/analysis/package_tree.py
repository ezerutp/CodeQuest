"""Árbol de paquetes para el explorador, con paquetes intermedios compactados.

"com" -> "example" -> "shop" (sin clases en los dos primeros) se muestra como un solo
nodo "com.example.shop", igual que las carpetas compactas de VS Code.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from codequest.core.analysis.java.models import JavaClass


@dataclass
class PackageNode:
    name: str  # texto a mostrar: "controller" o "com.example.shop"
    full_name: str  # paquete completo: "com.example.shop.controller"
    packages: list["PackageNode"] = field(default_factory=list)
    classes: list[JavaClass] = field(default_factory=list)

    def class_count(self) -> int:
        return len(self.classes) + sum(p.class_count() for p in self.packages)


def display_name(cls: JavaClass) -> str:
    """Nombre de la clase tal y como se ve en el árbol: "Outer.Inner" para anidadas."""
    return f"{cls.enclosing}.{cls.name}" if cls.enclosing else cls.name


def build_package_tree(classes: Iterable[JavaClass]) -> PackageNode:
    root = PackageNode(name="", full_name="")
    index: dict[str, PackageNode] = {"": root}
    for cls in classes:
        _ensure(cls.package, index).classes.append(cls)
    _sort(root)
    root.packages = [_compact(p) for p in root.packages]
    return root


def _ensure(package: str, index: dict[str, PackageNode]) -> PackageNode:
    if package in index:
        return index[package]
    parent_name, _, segment = package.rpartition(".")
    parent = _ensure(parent_name, index)
    node = PackageNode(name=segment, full_name=package)
    parent.packages.append(node)
    index[package] = node
    return node


def _compact(node: PackageNode) -> PackageNode:
    while not node.classes and len(node.packages) == 1:
        child = node.packages[0]
        node = PackageNode(f"{node.name}.{child.name}", child.full_name, child.packages, child.classes)
    node.packages = [_compact(p) for p in node.packages]
    return node


def _sort(node: PackageNode) -> None:
    node.packages.sort(key=lambda p: p.name.lower())
    node.classes.sort(key=lambda c: display_name(c).lower())
    for child in node.packages:
        _sort(child)
