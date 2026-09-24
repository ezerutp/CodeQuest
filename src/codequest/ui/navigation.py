"""Barra lateral de navegación."""

from enum import StrEnum

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import QButtonGroup, QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from codequest.app.constants import APP_NAME
from codequest.app.context import AppContext
from codequest.ui.formatting import ai_detail, ai_indicator
from codequest.ui.icons import icon, icon_label
from codequest.ui.theme import current_palette
from codequest.ui.widgets import StatusIndicator, section_title


class PageId(StrEnum):
    HOME = "home"
    LEARN = "learn"
    PROJECT = "project"
    PROGRESS = "progress"
    CONCEPTS = "concepts"
    SETTINGS = "settings"


NAV_ITEMS: tuple[tuple[PageId, str, str], ...] = (
    (PageId.HOME, "home", "Inicio"),
    (PageId.LEARN, "learn", "Aprender"),
    (PageId.PROJECT, "project", "Mi proyecto"),
    (PageId.PROGRESS, "progress", "Progreso"),
    (PageId.CONCEPTS, "concepts", "Conceptos"),
    (PageId.SETTINGS, "settings", "Configuración"),
)


class Sidebar(QFrame):
    page_selected = Signal(PageId)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(232)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 18, 12, 0)
        layout.setSpacing(2)

        layout.addLayout(self._build_logo())
        layout.addSpacing(18)

        self._buttons: dict[PageId, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        for page_id, icon_name, text in NAV_ITEMS:
            button = QPushButton(f"  {text}")
            button.setIcon(icon(icon_name))
            button.setIconSize(QSize(18, 18))
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _=False, p=page_id: self.page_selected.emit(p))
            self._group.addButton(button)
            self._buttons[page_id] = button
            layout.addWidget(button)

        layout.addStretch(1)
        layout.addWidget(self._build_footer())

    def _build_logo(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(8, 0, 0, 0)
        mark = icon_label("logo", size=22, color=current_palette().accent)
        name = QLabel(APP_NAME)
        name.setObjectName("SidebarLogo")
        row.addWidget(mark)
        row.addWidget(name)
        row.addStretch(1)
        return row

    def _build_footer(self) -> QFrame:
        footer = QFrame()
        footer.setObjectName("SidebarFooter")
        box = QVBoxLayout(footer)
        box.setContentsMargins(8, 14, 8, 16)
        box.setSpacing(4)
        box.addWidget(section_title("Proyecto actual"))
        self._project_name = QLabel()
        self._project_name.setObjectName("SidebarProjectName")
        box.addWidget(self._project_name)
        box.addSpacing(10)
        box.addWidget(section_title("IA"))
        self._ai_status = StatusIndicator()
        box.addWidget(self._ai_status)
        return footer

    def select(self, page_id: PageId) -> None:
        self._buttons[page_id].setChecked(True)

    def set_context(self, context: AppContext) -> None:
        name = context.project.name
        metrics = self._project_name.fontMetrics()
        self._project_name.setText(metrics.elidedText(name, Qt.TextElideMode.ElideMiddle, 200))
        self._project_name.setToolTip(str(context.project.root))
        text, state = ai_indicator(context.ai, context.ai_enabled)
        self._ai_status.set_status(text, state, ai_detail(context.ai, context.ai_enabled))
