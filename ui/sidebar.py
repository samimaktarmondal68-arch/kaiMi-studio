from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget,
)

from .theme_pyside import ThemeManager
from .widgets import IconProvider
from core.pipeline_events import get_pipeline_events
from core.pipeline_service import get_pipeline_service, StageStatus
from core.theme import Fonts, Spacing, Radius
from core.version import VERSION

STAGE_LABELS = ["Script", "Voice", "Image Prompts", "Export"]
NAV_ICONS = {
    "Dashboard": "dashboard",
    "Projects": "projects",
    "Asset Manager": "assets",
    "Script": "script",
    "Voice": "voice",
    "Image Prompts": "image",
    "Export": "export",
    "Settings": "settings",
}

NAV_GLOBAL = [
    ("dashboard", "Dashboard"),
    ("projects", "Projects"),
    ("assets", "Asset Manager"),
]

BUTTON_HEIGHT = 36
STAGE_BUTTON_HEIGHT = 30


class _AboutLabel(QLabel):
    """Clickable version label that opens the About dialog."""

    clicked = Signal()

    def __init__(self, text: str):
        super().__init__(text)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("About KaiMi Studio")

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class Sidebar(QFrame):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(240)
        self._page_map = {}
        self._nav_buttons = {}
        self._project_name = None
        self._workflow_state = {}
        self._nav_controller = None
        self._events = get_pipeline_events()
        self._events.stage_completed.connect(self._on_pipeline_event)
        self._events.project_updated.connect(self._on_pipeline_event)
        self._events.health_changed.connect(self._on_pipeline_event)

        self._build_shadow()
        self._build_layout()

    def set_nav_controller(self, controller):
        self._nav_controller = controller

    def _build_shadow(self):
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(40)
        shadow.setOffset(4, 0)
        shadow.setColor(QColor(0, 0, 0, 80))
        self.setGraphicsEffect(shadow)

    def _build_layout(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(2)
        layout.setContentsMargins(12, 16, 12, 12)

        self._build_brand(layout)
        layout.addSpacing(10)
        self._build_separator(layout)
        layout.addSpacing(4)

        section_label = QLabel("Navigation")
        section_label.setObjectName("muted")
        c = ThemeManager.instance().colors()
        section_label.setStyleSheet(
            f"padding: 3px 12px; {Fonts.section_label(c.TEXT_MUTED)}"
        )
        layout.addWidget(section_label)

        self._build_global_nav(layout)

        self.project_section_widget = QWidget()
        self.project_layout = QVBoxLayout(self.project_section_widget)
        self.project_layout.setContentsMargins(0, 0, 0, 0)
        self.project_layout.setSpacing(2)

        layout.addSpacing(2)
        self._build_separator(layout)
        layout.addSpacing(2)

        project_header = QLabel("Current Project")
        project_header.setObjectName("muted")
        c = ThemeManager.instance().colors()
        project_header.setStyleSheet(
            f"padding: 3px 12px; {Fonts.section_label(c.TEXT_MUTED)}"
        )
        self.project_layout.addWidget(project_header)

        self.project_name_widget = QLabel("")
        c = ThemeManager.instance().colors()
        self.project_name_widget.setStyleSheet(
            f"padding: 1px 12px 3px 12px; {Fonts.tiny(c.TEXT)} font-weight: 600;"
        )
        self.project_layout.addWidget(self.project_name_widget)

        self.progress_widget = QWidget()
        self.progress_layout = QVBoxLayout(self.progress_widget)
        self.progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_layout.setSpacing(1)
        self.project_layout.addWidget(self.progress_widget)

        self.project_section_widget.setVisible(False)
        layout.addWidget(self.project_section_widget)

        layout.addSpacerItem(QSpacerItem(0, 0, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self._build_separator(layout)

        settings_btn = self._create_nav_button("settings", "Settings")
        self._nav_buttons["Settings"] = settings_btn
        layout.addWidget(settings_btn)

        version = _AboutLabel(f"v{VERSION}")
        version.setObjectName("muted")
        version.setAlignment(Qt.AlignCenter)
        c = ThemeManager.instance().colors()
        version.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} padding: 2px;")
        version.clicked.connect(self._open_about)
        layout.addWidget(version)

    def _build_brand(self, layout):
        c = ThemeManager.instance().colors()

        # Official logo lockup above the wordmark (56px, aspect ratio
        # preserved, never oversized — navigation stays the primary focus).
        from core.branding import logo_pixmap
        logo_label = QLabel()
        logo_label.setPixmap(logo_pixmap(56))
        logo_label.setFixedSize(56, 56)
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setAttribute(Qt.WA_TransparentForMouseEvents)
        layout.addWidget(logo_label, 0, Qt.AlignHCenter)
        layout.addSpacing(2)

        brand = QLabel("KaiMi Studio")
        brand.setAlignment(Qt.AlignCenter)
        brand.setStyleSheet(
            f"{Fonts.css(18, 'bold', c.PRIMARY)} letter-spacing: -0.3px;"
        )
        layout.addWidget(brand)

        subtitle = QLabel("AI Creator Workspace")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet(
            f"{Fonts.tiny(c.TEXT_MUTED)} "
            f"padding: 0px 12px; letter-spacing: 0.2px;"
        )
        layout.addWidget(subtitle)

    def _build_separator(self, layout):
        c = ThemeManager.instance().colors()
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet(f"border: none; background-color: {c.BORDER};")
        sep.setFixedHeight(1)
        layout.addWidget(sep)

    def _build_global_nav(self, layout):
        for icon_name, label in NAV_GLOBAL:
            btn = self._create_nav_button(icon_name, label)
            self._nav_buttons[label] = btn
            layout.addWidget(btn)

    def _create_nav_button(self, icon_name, label):
        btn = QPushButton(f"  {label}")
        btn.setObjectName("nav_item")
        btn.setFlat(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(BUTTON_HEIGHT)
        btn.setAttribute(Qt.WA_StyledBackground, True)
        c = ThemeManager.instance().colors()
        btn.setIcon(IconProvider.icon(icon_name, 18, c.TEXT_SECONDARY))
        btn.setIconSize(QSize(18, 18))
        self._style_nav_inactive(btn)
        btn.clicked.connect(lambda checked=False, l=label: self._on_nav_click(l))
        return btn

    def _style_nav_inactive(self, btn):
        c = ThemeManager.instance().colors()
        btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: {c.TEXT_SECONDARY};
                border: none;
                border-radius: 8px;
                padding: 6px 12px;
                text-align: left;
                {Fonts.body(c.TEXT_SECONDARY)}
            }}
            QPushButton:hover {{
                background-color: {c.HOVER};
                color: {c.TEXT};
            }}
            """
        )

    def set_page_map(self, page_map: dict):
        self._page_map = page_map

    def _on_pipeline_event(self, *args):
        if self._project_name:
            self._update_progress()

    def set_project_context(self, project_name=None, workflow_state=None):
        self._project_name = project_name
        if project_name:
            pipeline = get_pipeline_service()
            self._workflow_state = pipeline.get_pipeline_state(project_name)
            self.project_name_widget.setText(project_name)
            self.project_name_widget.setVisible(True)
            self._update_progress()
            self.project_section_widget.setVisible(True)
        else:
            self._workflow_state = workflow_state or {}
            self.project_section_widget.setVisible(False)

    def _update_progress(self):
        for i in reversed(range(self.progress_layout.count())):
            w = self.progress_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        c = ThemeManager.instance().colors()
        for stage in STAGE_LABELS:
            state = self._workflow_state.get(stage, StageStatus.BLOCKED)
            icon_name = NAV_ICONS.get(stage, "")
            if state == StageStatus.COMPLETED:
                icon_name = "check_circle"
                color = c.SUCCESS
            elif state == StageStatus.IN_PROGRESS:
                icon_name = "circle"
                color = c.PRIMARY
            elif state == StageStatus.NOT_STARTED:
                icon_name = "circle"
                color = c.PRIMARY
            elif state == StageStatus.FAILED:
                icon_name = "warning"
                color = c.ERROR
            else:
                icon_name = "circle_empty"
                color = c.TEXT_MUTED

            item = QPushButton(f"  {stage}")
            item.setFlat(True)
            item.setCursor(Qt.PointingHandCursor)
            item.setFixedHeight(STAGE_BUTTON_HEIGHT)
            item.setIcon(IconProvider.icon(icon_name, 14, color))
            item.setIconSize(QSize(14, 14))
            item.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: transparent;
                    color: {color};
                    border: none;
                    border-radius: 8px;
                    padding: 4px 12px;
                    text-align: left;
                    {Fonts.caption(color)}
                }}
                QPushButton:hover {{
                    background-color: {c.HOVER};
                }}
                """
            )
            item.clicked.connect(lambda checked=False, s=stage: self._on_nav_click(s))
            self.progress_layout.addWidget(item)

            self._nav_buttons[stage] = item

    def _open_about(self):
        """Open the About dialog on the owning MainWindow."""
        parent = self.parent()
        for _ in range(8):
            if hasattr(parent, "show_about_dialog"):
                parent.show_about_dialog()
                return
            parent = parent.parent() if parent else None
            if parent is None:
                return

    def _on_nav_click(self, label):
        if label not in self._page_map:
            return
        if self._nav_controller:
            self._nav_controller.navigate_to(label)
        else:
            parent = self.parent()
            for _ in range(5):
                if hasattr(parent, 'navigate_to'):
                    parent.navigate_to(label)
                    return
                parent = parent.parent() if parent else None
                if parent is None:
                    return

    def set_active(self, label: str):
        c = ThemeManager.instance().colors()
        for name, btn in self._nav_buttons.items():
            if name == label:
                icon_name = NAV_ICONS.get(name, "")
                btn.setIcon(IconProvider.icon(icon_name, 18, c.PRIMARY))
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: {c.PRIMARY_LIGHT};
                        color: {c.PRIMARY};
                        border: none;
                        border-radius: 8px;
                        padding: 6px 12px;
                        text-align: left;
                        {Fonts.body(c.PRIMARY)} font-weight: 600;
                    }}
                    QPushButton:hover {{
                        background-color: {c.PRIMARY_LIGHT};
                    }}
                    """
                )
            else:
                icon_name = NAV_ICONS.get(name, "")
                btn.setIcon(IconProvider.icon(icon_name, 18, c.TEXT_SECONDARY))
                self._style_nav_inactive(btn)

    def update_theme(self):
        c = ThemeManager.instance().colors()

        self._build_shadow()

        for lbl in self.findChildren(QLabel):
            text = lbl.text()
            if text == "KaiMi Studio":
                lbl.setStyleSheet(
                    f"{Fonts.css(18, 'bold', c.PRIMARY)} letter-spacing: -0.3px;"
                )
            elif text == "AI Creator Workspace":
                lbl.setStyleSheet(
                    f"{Fonts.tiny(c.TEXT_MUTED)} "
                    f"padding: 0px 12px; letter-spacing: 0.2px;"
                )
            elif text in ("Navigation", "Current Project"):
                lbl.setStyleSheet(
                    f"padding: 3px 12px; {Fonts.section_label(c.TEXT_MUTED)}"
                )
            elif text.startswith("v") and len(text) < 12:
                lbl.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} padding: 2px;")

        if self.project_name_widget:
            self.project_name_widget.setStyleSheet(
                f"padding: 1px 12px 3px 12px; {Fonts.tiny(c.TEXT)} font-weight: 600;"
            )

        for sep in self.findChildren(QFrame):
            if sep.frameShape() == QFrame.HLine:
                sep.setStyleSheet(f"border: none; background-color: {c.BORDER};")

        # Update nav button icons on theme change
        for name, btn in self._nav_buttons.items():
            icon_name = NAV_ICONS.get(name, "")
            if icon_name:
                # Check if this button is active
                style = btn.styleSheet()
                icon_color = c.PRIMARY if "PRIMARY" in style and "background" in style else c.TEXT_SECONDARY
                btn.setIcon(IconProvider.icon(icon_name, 18, icon_color))

        self.set_active(self._get_current_active())

        self._update_progress()

    def _get_current_active(self):
        for name, btn in self._nav_buttons.items():
            style = btn.styleSheet()
            if "PRIMARY_LIGHT" in style:
                return name
        return None
