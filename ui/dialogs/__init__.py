from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QDialog, QFrame,
    QHBoxLayout, QLabel, QLineEdit, QPushButton, QRadioButton,
    QScrollArea, QTextEdit, QVBoxLayout, QWidget,
)

from core.project_manager import ProjectManager
from core.templates import get_template, get_template_names, TemplateConfig
from core.theme import Fonts, Spacing, Radius
from core.version import APP_NAME, VERSION, CODENAME
from ..theme_pyside import ThemeManager


def _dialog_styles():
    c = ThemeManager.instance().colors()
    return f"""
        QDialog {{
            background-color: {c.BG};
            color: {c.TEXT};
            font-family: "{Fonts.FAMILY}", "{Fonts.FAMILY_ALT}", sans-serif;
        }}
        QLabel {{
            color: {c.TEXT};
        }}
        QLineEdit {{
            background-color: {c.INPUT_BG};
            color: {c.TEXT};
            border: 1px solid {c.INPUT_BORDER};
            border-radius: 12px;
            padding: 10px 16px;
            font-size: 14px;
            min-height: 20px;
        }}
        QLineEdit:focus {{
            border: 2px solid {c.PRIMARY};
        }}
        QTextEdit {{
            background-color: {c.INPUT_BG};
            color: {c.TEXT};
            border: 1px solid {c.INPUT_BORDER};
            border-radius: 12px;
            padding: 10px 16px;
            font-size: 14px;
            min-height: 60px;
            max-height: 80px;
        }}
        QTextEdit:focus {{
            border: 2px solid {c.PRIMARY};
        }}
        QComboBox {{
            background-color: {c.INPUT_BG};
            color: {c.TEXT};
            border: 1px solid {c.INPUT_BORDER};
            border-radius: 12px;
            padding: 10px 16px;
            font-size: 14px;
            min-height: 20px;
        }}
        QComboBox::drop-down {{
            border: none;
            width: 32px;
        }}
        QComboBox QAbstractItemView {{
            background-color: {c.CARD};
            color: {c.TEXT};
            border: 1px solid {c.BORDER};
            border-radius: 12px;
            selection-background-color: {c.PRIMARY_LIGHT};
            padding: 8px;
        }}
        QComboBox QAbstractItemView::item {{
            padding: 8px 12px;
            border-radius: 8px;
        }}
        QComboBox QAbstractItemView::item:hover {{
            background-color: {c.HOVER};
        }}
        QRadioButton {{
            color: {c.TEXT};
            font-size: 14px;
            spacing: 8px;
        }}
        QRadioButton::indicator {{
            width: 18px;
            height: 18px;
            border-radius: 9px;
            border: 2px solid {c.TEXT_MUTED};
        }}
        QRadioButton::indicator:checked {{
            background-color: {c.PRIMARY};
            border: 2px solid {c.PRIMARY};
        }}
        QPushButton#primary {{
            background-color: {c.PRIMARY};
            color: {c.TEXT_ON_PRIMARY};
            border: none;
            border-radius: 12px;
            padding: 10px 24px;
            font-size: 14px;
            font-weight: bold;
        }}
        QPushButton#primary:hover {{
            background-color: {c.PRIMARY_HOVER};
        }}
        QPushButton#secondary {{
            background-color: transparent;
            color: {c.TEXT};
            border: 1px solid {c.BORDER};
            border-radius: 12px;
            padding: 10px 24px;
            font-size: 14px;
        }}
        QPushButton#secondary:hover {{
            background-color: {c.SURFACE};
            border: 1px solid {c.PRIMARY};
        }}
        QFrame#card {{
            background-color: {c.CARD};
            border: 1px solid {c.BORDER};
            border-radius: 16px;
        }}
    """


class NewProjectDialog(QDialog):

    def __init__(self, parent=None, on_project_created=None):
        super().__init__(parent)
        self.setWindowTitle("New Project")
        self.setMinimumWidth(560)
        self.setModal(True)
        self.manager = ProjectManager()
        self._on_project_created = on_project_created
        self._build()
        self.setStyleSheet(_dialog_styles())

    def _build(self):
        c = ThemeManager.instance().colors()
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        title = QLabel("New Project")
        title.setStyleSheet(f"{Fonts.section_title(c.TEXT)}")
        layout.addWidget(title)

        form = QWidget()
        form_layout = QVBoxLayout(form)
        form_layout.setSpacing(12)

        def make_field(label_text, widget):
            row = QVBoxLayout()
            row.setSpacing(4)
            lbl = QLabel(label_text)
            lbl.setStyleSheet(f"{Fonts.caption_bold(c.TEXT_SECONDARY)}")
            row.addWidget(lbl)
            row.addWidget(widget)
            return row

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., AI in Education")
        form_layout.addLayout(make_field("Project Name", self.name_input))

        self.template_combo = QComboBox()
        self.template_combo.addItems(get_template_names())
        self.template_combo.currentTextChanged.connect(self._on_template_changed)
        form_layout.addLayout(make_field("Template", self.template_combo))

        self.template_desc = QLabel("")
        self.template_desc.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} padding: 0 4px;")
        self.template_desc.setWordWrap(True)
        form_layout.addWidget(self.template_desc)

        self.output_folder_label = QLabel(f"Output: projects/<name>/")
        self.output_folder_label.setStyleSheet(f"{Fonts.tiny(c.TEXT_MUTED)} padding: 0 4px;")
        form_layout.addWidget(self.output_folder_label)

        self.description_input = QTextEdit()
        self.description_input.setPlaceholderText("Optional project description...")
        self.description_input.setMaximumHeight(80)
        form_layout.addLayout(make_field("Description (optional)", self.description_input))

        self.topic_input = QLineEdit()
        self.topic_input.setPlaceholderText("e.g., The impact of AI on modern education")
        form_layout.addLayout(make_field("Topic", self.topic_input))

        self.platform_combo = QComboBox()
        self.platform_combo.addItems(["YouTube", "TikTok", "Instagram", "Other"])
        form_layout.addLayout(make_field("Platform", self.platform_combo))

        video_type = QComboBox()
        video_type.addItems(["Educational", "Entertainment", "Documentary", "Tutorial", "Other"])
        form_layout.addLayout(make_field("Video Type", video_type))

        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "Spanish", "French", "German", "Chinese", "Japanese", "Arabic", "Hindi", "Portuguese"])
        form_layout.addLayout(make_field("Language", self.language_combo))

        format_container = QWidget()
        format_container_layout = QHBoxLayout(format_container)
        format_container_layout.setContentsMargins(0, 0, 0, 0)
        self.format_long = QRadioButton("Long Form")
        self.format_shorts = QRadioButton("Shorts")
        self.format_long.setChecked(True)
        format_container_layout.addWidget(self.format_long)
        format_container_layout.addWidget(self.format_shorts)
        format_container_layout.addStretch()
        form_layout.addLayout(make_field("Format", format_container))

        form_layout.addSpacing(8)
        self.create_btn = QPushButton("Create Project")
        self.create_btn.setObjectName("primary")
        self.create_btn.clicked.connect(self._on_create)
        form_layout.addWidget(self.create_btn)

        scroll = QScrollArea()
        scroll.setWidget(form)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        layout.addWidget(scroll)

        self._on_template_changed(self.template_combo.currentText())

    def _on_template_changed(self, template_name: str):
        template = get_template(template_name)
        c = ThemeManager.instance().colors()
        if template:
            desc = (
                f"Platform: {template.platform}  |  Type: {template.video_type}  |  "
                f"Script: {template.script_min}-{template.script_max} chars  |  "
                f"Duration: {template.duration_preset or 'Flexible'}"
            )
            self.template_desc.setText(desc)
            self.template_desc.setStyleSheet(f"{Fonts.tiny(c.PRIMARY)} padding: 0 4px;")

            idx = self.platform_combo.findText(template.platform)
            if idx >= 0:
                self.platform_combo.setCurrentIndex(idx)

            if template.duration_preset:
                is_shorts = "second" in template.duration_preset.lower()
                self.format_shorts.setChecked(is_shorts)
                self.format_long.setChecked(not is_shorts)

        self.name_input.textChanged.connect(
            lambda: self.output_folder_label.setText(
                f"Output: projects/{self.name_input.text().strip() or '<name>'}/"
            )
        )

    def _on_create(self):
        name = self.name_input.text().strip()
        topic = self.topic_input.text().strip()
        if not name:
            return
        if not topic:
            return
        template_name = self.template_combo.currentText()
        template = get_template(template_name)
        try:
            self.manager.create_project(
                name=name,
                topic=topic,
                template_name=template_name,
                platform=self.platform_combo.currentText(),
                language=self.language_combo.currentText(),
                script_min=template.script_min if template else 4500,
                script_max=template.script_max if template else 5000,
                duration_preset=template.duration_preset if template else "",
                description=self.description_input.toPlainText().strip(),
            )
            self.accept()
            if self._on_project_created:
                self._on_project_created(name)
        except Exception as e:
            from core.notifications import NotificationService
            NotificationService.get().error(str(e))


class FirstRunDialog(QDialog):

    def __init__(self, parent=None, on_close=None):
        super().__init__(parent)
        self.setWindowTitle(f"Welcome to {APP_NAME}")
        self.setMinimumSize(520, 580)
        self.setModal(True)
        self.setStyleSheet(_dialog_styles())
        self._on_close_callback = on_close
        self._build()

    def _build(self):
        c = ThemeManager.instance().colors()
        layout = QVBoxLayout(self)
        layout.setSpacing(20)
        layout.setContentsMargins(32, 32, 32, 32)

        title = QLabel(f"Welcome to {APP_NAME}")
        title.setStyleSheet(f"{Fonts.css(28, 'bold', c.PRIMARY)}")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        subtitle = QLabel(f"v{VERSION} \u2014 {CODENAME}")
        subtitle.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        subtitle.setAlignment(Qt.AlignCenter)
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(12)

        steps = [
            ("\U0001F3E0", "Create a Project", "Set up your project with topic, platform, and script target."),
            ("\U0001F4DD", "Generate Script", "One click generates a complete script with automatic research."),
            ("\U0001F3A4", "Voice / Transcript", "Optional: upload audio for transcription with timestamps."),
            ("\U0001F5BC\uFE0F", "Image Prompts", "Generate production-ready image prompts."),
            ("\U0001F4E4", "Export TXT", "Export your script and prompts as a TXT file."),
        ]

        for icon, step_title, desc in steps:
            card = QFrame()
            card.setObjectName("card")
            card.setAttribute(Qt.WA_StyledBackground, True)
            card.setFixedHeight(80)

            card_layout = QHBoxLayout(card)
            card_layout.setContentsMargins(16, 12, 16, 12)
            card_layout.setSpacing(12)

            icon_lbl = QLabel(icon)
            icon_lbl.setStyleSheet(f"font-size: 24px; background: transparent;")
            card_layout.addWidget(icon_lbl)

            text_layout = QVBoxLayout()
            text_layout.setSpacing(2)
            step_lbl = QLabel(step_title)
            step_lbl.setStyleSheet(f"{Fonts.subtitle(c.TEXT)} background: transparent;")
            text_layout.addWidget(step_lbl)
            desc_lbl = QLabel(desc)
            desc_lbl.setStyleSheet(f"{Fonts.caption(c.TEXT_SECONDARY)} background: transparent;")
            desc_lbl.setWordWrap(True)
            text_layout.addWidget(desc_lbl)
            card_layout.addLayout(text_layout, 1)

            scroll_layout.addWidget(card)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        close_btn = QPushButton("Get Started")
        close_btn.setObjectName("primary")
        close_btn.setFixedHeight(40)
        close_btn.clicked.connect(self._on_close)
        layout.addWidget(close_btn)

    def _on_close(self):
        if self._on_close_callback:
            self._on_close_callback()
        self.accept()
