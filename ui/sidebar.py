from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QFrame, QGraphicsDropShadowEffect, QHBoxLayout,
    QLabel, QPushButton, QSizePolicy,
    QSpacerItem, QVBoxLayout, QWidget,
)

from .theme_pyside import ThemeManager
from core.theme import Fonts, Spacing, Radius
from core.version import VERSION

STAGE_LABELS = ["Script", "Voice", "Image Prompts", "Export"]
STAGE_ICONS = {"Script": "\U0001F4DD", "Voice": "\U0001F3A4", "Image Prompts": "\U0001F5BC", "Export": "\U0001F4E4"}

NAV_GLOBAL = [
    ("\U0001F3E0", "Dashboard"),
    ("\U0001F4C1", "Projects"),
    ("\U0001F4C2", "Asset Manager"),
]

NAV_SETTINGS = [
    ("\u2699\uFE0F", "Settings"),
]

BUTTON_HEIGHT = 40
STAGE_BUTTON_HEIGHT = 34


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
        layout.setContentsMargins(12, 20, 12, 16)

        self._build_brand(layout)
        layout.addSpacing(12)
        self._build_separator(layout)
        layout.addSpacing(6)

        section_label = QLabel("Navigation")
        section_label.setObjectName("muted")
        c = ThemeManager.instance().colors()
        section_label.setStyleSheet(
            f"padding: 4px 12px; {Fonts.section_label(c.TEXT_MUTED)}"
        )
        layout.addWidget(section_label)
        layout.addSpacing(2)

        self._build_global_nav(layout)

        self.project_section_widget = QWidget()
        self.project_layout = QVBoxLayout(self.project_section_widget)
        self.project_layout.setContentsMargins(0, 0, 0, 0)
        self.project_layout.setSpacing(2)

        layout.addSpacing(4)
        self._build_separator(layout)
        layout.addSpacing(4)

        project_header = QLabel("Current Project")
        project_header.setObjectName("muted")
        c = ThemeManager.instance().colors()
        project_header.setStyleSheet(
            f"padding: 4px 12px; {Fonts.section_label(c.TEXT_MUTED)}"
        )
        self.project_layout.addWidget(project_header)

        self.project_name_widget = QLabel("")
        c = ThemeManager.instance().colors()
        self.project_name_widget.setStyleSheet(
            f"padding: 2px 12px 4px 12px; {Fonts.caption_bold(c.TEXT)}"
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
        layout.addSpacing(2)

        settings_btn = self._create_nav_button("\u2699\uFE0F", "Settings")
        self._nav_buttons["Settings"] = settings_btn
        layout.addWidget(settings_btn)

        layout.addSpacing(4)

        version = QLabel(f"v{VERSION}")
        version.setObjectName("muted")
        version.setAlignment(Qt.AlignCenter)
        c = ThemeManager.instance().colors()
        version.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} padding: 4px;")
        layout.addWidget(version)

    def _build_brand(self, layout):
        c = ThemeManager.instance().colors()
        brand = QLabel("KaiMi Studio")
        brand.setStyleSheet(
            f"{Fonts.css(20, 'bold', c.PRIMARY)} "
            f"padding: 0px 12px; letter-spacing: -0.5px;"
        )
        layout.addWidget(brand)

        subtitle = QLabel("AI Creator Workspace")
        subtitle.setStyleSheet(
            f"{Fonts.tiny(c.TEXT_MUTED)} "
            f"padding: 0px 12px; letter-spacing: 0.3px;"
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
        for icon, label in NAV_GLOBAL:
            btn = self._create_nav_button(f"  {icon}  {label}", label)
            self._nav_buttons[label] = btn
            layout.addWidget(btn)

    def _create_nav_button(self, text, label=None):
        nav_label = label if label else text.strip()
        btn = QPushButton(text)
        btn.setObjectName("nav_item")
        btn.setFlat(True)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setFixedHeight(BUTTON_HEIGHT)
        btn.setAttribute(Qt.WA_StyledBackground, True)
        self._style_nav_inactive(btn)
        btn.clicked.connect(lambda checked=False, l=nav_label: self._on_nav_click(l))
        return btn

    def _style_nav_inactive(self, btn):
        c = ThemeManager.instance().colors()
        btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                color: {c.TEXT_SECONDARY};
                border: none;
                border-radius: {Radius.MD}px;
                padding: 8px 12px;
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

    def set_project_context(self, project_name=None, workflow_state=None):
        self._project_name = project_name
        self._workflow_state = workflow_state or {}
        if project_name:
            self.project_name_widget.setText(project_name)
            self.project_name_widget.setVisible(True)
            self._update_progress()
            self.project_section_widget.setVisible(True)
        else:
            self.project_section_widget.setVisible(False)

    def _update_progress(self):
        for i in reversed(range(self.progress_layout.count())):
            w = self.progress_layout.itemAt(i).widget()
            if w:
                w.setParent(None)
                w.deleteLater()

        c = ThemeManager.instance().colors()
        for stage in STAGE_LABELS:
            state = self._workflow_state.get(stage, "LOCKED")
            icon = STAGE_ICONS.get(stage, "")
            if state == "COMPLETED":
                prefix = "\u2713"
                color = c.SUCCESS
            elif state == "AVAILABLE":
                prefix = "\u25CF"
                color = c.PRIMARY
            else:
                prefix = "\u25CB"
                color = c.TEXT_MUTED

            item = QPushButton(f"  {icon}  {stage}")
            item.setFlat(True)
            item.setCursor(Qt.PointingHandCursor)
            item.setFixedHeight(STAGE_BUTTON_HEIGHT)
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
                btn.setStyleSheet(
                    f"""
                    QPushButton {{
                        background-color: {c.PRIMARY_LIGHT};
                        color: {c.PRIMARY};
                        border: none;
                        border-radius: {Radius.MD}px;
                        padding: 8px 12px;
                        text-align: left;
                        {Fonts.body_bold(c.PRIMARY)}
                    }}
                    QPushButton:hover {{
                        background-color: {c.PRIMARY_LIGHT};
                    }}
                    """
                )
            else:
                self._style_nav_inactive(btn)

    def update_theme(self):
        c = ThemeManager.instance().colors()

        self._build_shadow()

        brand = self.findChild(QLabel, "")
        for lbl in self.findChildren(QLabel):
            text = lbl.text()
            if text == "KaiMi Studio":
                lbl.setStyleSheet(
                    f"{Fonts.css(20, 'bold', c.PRIMARY)} "
                    f"padding: 0px 12px; letter-spacing: -0.5px;"
                )
            elif text == "AI Creator Workspace":
                lbl.setStyleSheet(
                    f"{Fonts.tiny(c.TEXT_MUTED)} "
                    f"padding: 0px 12px; letter-spacing: 0.3px;"
                )
            elif text in ("Navigation", "Current Project"):
                lbl.setStyleSheet(
                    f"padding: 4px 12px; {Fonts.section_label(c.TEXT_MUTED)}"
                )
            elif text.startswith("v") and len(text) < 12:
                lbl.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} padding: 4px;")

        if self.project_name_widget:
            self.project_name_widget.setStyleSheet(
                f"padding: 2px 12px 4px 12px; {Fonts.caption_bold(c.TEXT)}"
            )

        for sep in self.findChildren(QFrame):
            if sep.frameShape() == QFrame.HLine:
                sep.setStyleSheet(f"border: none; background-color: {c.BORDER};")

        self.set_active(self._get_current_active())

        self._update_progress()

    def _get_current_active(self):
        for name, btn in self._nav_buttons.items():
            style = btn.styleSheet()
            if "PRIMARY_LIGHT" in style:
                return name
        return None
