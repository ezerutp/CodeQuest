from datetime import datetime, timedelta

from codequest.ui.formatting import session_date


def test_session_date_relative_labels_in_local_time() -> None:
    now = datetime(2026, 9, 23, 18, 0).astimezone()
    today = now.replace(hour=9, minute=5)

    assert session_date(today.isoformat(), now) == "Hoy · 09:05"
    assert session_date((today - timedelta(days=1)).isoformat(), now) == "Ayer · 09:05"
    assert session_date((today - timedelta(days=11)).isoformat(), now) == "12 sep · 09:05"
