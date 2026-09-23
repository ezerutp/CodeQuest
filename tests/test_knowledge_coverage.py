from pathlib import Path

import pytest

from codequest.core.analysis.java.models import JavaAnnotation, JavaClass, TypeKind
from codequest.core.analysis.model import ProjectModel
from codequest.core.analysis.roles import ComponentRole
from codequest.core.knowledge.base import KnowledgeBase
from codequest.core.knowledge.coverage import GapKind, build_report
from codequest.core.project.models import ProjectInfo
from codequest.services.project_service import ProjectService


def _model(*classes: JavaClass) -> ProjectModel:
    return ProjectModel(info=ProjectInfo(root=Path("/p"), name="p"), files=(), classes=classes,
                        roles={c.qualified_name: ComponentRole.OTHER for c in classes})


def _cls(name: str, annotations: tuple[str, ...] = (), imports: tuple[str, ...] = (),
         interfaces: tuple[str, ...] = (), superclass: str | None = None,
         kind: TypeKind = TypeKind.CLASS) -> JavaClass:
    return JavaClass(name=name, package="app", kind=kind, file=f"{name}.java", is_test=False, start_line=1,
                     end_line=9, annotations=tuple(JavaAnnotation(a, None, 1) for a in annotations),
                     imports=imports, interfaces=interfaces, superclass=superclass)


@pytest.fixture(scope="module")
def kb() -> KnowledgeBase:
    return KnowledgeBase.default()


def test_counts_known_concepts_and_gaps(kb: KnowledgeBase) -> None:
    model = _model(
        _cls("UserService", ("Service", "Slf4j"), imports=("lombok.extern.slf4j.Slf4j",)),
        _cls("OrderService", ("Service", "Slf4j", "Override")),
        _cls("JwtFilter", ("Component",), imports=("org.springframework.web.filter.OncePerRequestFilter",),
             superclass="OncePerRequestFilter"),
    )

    report = build_report(model, kb)

    assert [(u.concept.title, u.usages) for u in report.used] == [("@Service", 2), ("@Component", 1)]
    assert [(g.kind, g.display, g.qualified_name, g.usages) for g in report.gaps] == [
        (GapKind.ANNOTATION, "@Slf4j", "lombok.extern.slf4j.Slf4j", 2),
        (GapKind.SUPERTYPE, "OncePerRequestFilter", "org.springframework.web.filter.OncePerRequestFilter", 1),
    ]
    assert report.gaps[0].classes == ("app.UserService", "app.OrderService")
    assert (report.known_count, report.total_count) == (2, 4)


def test_ignores_java_basics_and_project_types(kb: KnowledgeBase) -> None:
    model = _model(
        _cls("Audited", kind=TypeKind.ANNOTATION),
        _cls("Base"),
        _cls("A", ("Audited", "Override", "Deprecated"), interfaces=("Serializable", "Comparable<A>")),
        _cls("B", superclass="Base", interfaces=("java.util.function.Supplier<String>",),
             imports=("java.util.function.Supplier",)),
        _cls("C", superclass="RuntimeException"),
    )

    assert build_report(model, kb).gaps == ()


def test_fixture_project_gaps(kb: KnowledgeBase, shop_project: Path) -> None:
    service = ProjectService()
    model = service.analyze(service.detect(shop_project))

    gaps = {g.display for g in build_report(model, kb).gaps}

    assert gaps == {"@Enumerated", "@Param"}
