from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def shop_project() -> Path:
    """Proyecto Spring Boot de ejemplo (Maven) con casos difíciles para el parser."""
    return FIXTURES / "shop"
