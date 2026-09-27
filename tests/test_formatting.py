from datetime import datetime, timedelta

from codequest.core.analysis.react.roles import ReactRole
from codequest.core.analysis.roles import ComponentRole
from codequest.ui.formatting import role_count, role_label, session_date


def test_session_date_relative_labels_in_local_time() -> None:
    now = datetime(2026, 9, 23, 18, 0).astimezone()
    today = now.replace(hour=9, minute=5)

    assert session_date(today.isoformat(), now) == "Hoy · 09:05"
    assert session_date((today - timedelta(days=1)).isoformat(), now) == "Ayer · 09:05"
    assert session_date((today - timedelta(days=11)).isoformat(), now) == "12 sep · 09:05"


def test_role_labels_distinguish_java_and_react_roles() -> None:
    # Son StrEnum con valores iguales ("service"): no deben mezclar etiquetas.
    assert role_label(ComponentRole.SERVICE) == "Service"
    assert role_label(ReactRole.SERVICE) == "Servicio"
    assert role_label(ReactRole.TYPE, plural=True) == "Tipos"
    assert role_count(ReactRole.HOOK, 1) == "1 Hook"
    assert all(role_label(r) for r in ReactRole)
