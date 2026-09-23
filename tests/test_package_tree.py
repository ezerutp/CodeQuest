from codequest.core.analysis.java.models import JavaClass, TypeKind
from codequest.core.analysis.package_tree import build_package_tree, display_name


def cls(package: str, name: str, enclosing: str | None = None) -> JavaClass:
    return JavaClass(name=name, package=package, kind=TypeKind.CLASS, file="x.java", is_test=False,
                     start_line=1, end_line=1, enclosing=enclosing)


def test_compacts_single_child_packages_and_sorts() -> None:
    root = build_package_tree([
        cls("com.example.shop.service", "UserService"),
        cls("com.example.shop.controller", "UserController"),
        cls("com.example.shop", "ShopApplication"),
        cls("com.example.shop.controller", "AdminController"),
    ])

    (shop,) = root.packages
    assert (shop.name, shop.full_name) == ("com.example.shop", "com.example.shop")
    assert [c.name for c in shop.classes] == ["ShopApplication"]
    assert [p.name for p in shop.packages] == ["controller", "service"]
    assert [c.name for c in shop.packages[0].classes] == ["AdminController", "UserController"]
    assert root.class_count() == 4


def test_compacts_nested_chains_below_the_root() -> None:
    root = build_package_tree([cls("app.web.api.v1", "A"), cls("app.core", "B")])

    (app,) = root.packages
    assert [p.name for p in app.packages] == ["core", "web.api.v1"]


def test_default_package_and_nested_class_names() -> None:
    inner = cls("p", "Inner", enclosing="Outer")
    root = build_package_tree([cls("", "Main"), inner])

    assert [c.name for c in root.classes] == ["Main"]
    assert display_name(inner) == "Outer.Inner"
