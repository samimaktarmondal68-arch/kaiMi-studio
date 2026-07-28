from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QScrollArea,
    QVBoxLayout, QWidget,
)

from core.settings import AppSettings
from core.theme import Fonts
from ui.theme_pyside import ThemeManager
from ui.widgets import CardTitle, MutedLabel, ModernCard, PageTitle, SectionLabel


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = AppSettings()
        ThemeManager.instance().on_change(lambda _: self._on_theme_changed())
        self._build()

    def _on_theme_changed(self):
        for i in reversed(range(self._scroll_layout.count())):
            item = self._scroll_layout.itemAt(i)
            w = item.widget()
            if w:
                w.setParent(None)
                w.deleteLater()
        self._build_appearance()
        self._build_language()
        self._build_provider()
        self._build_about()
        self._scroll_layout.addStretch()

    def _build(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(32, 32, 32, 32)
        layout.setSpacing(24)

        header = PageTitle("Settings")
        layout.addWidget(header)

        subtitle = MutedLabel("Configure your workspace preferences")
        layout.addWidget(subtitle)
        layout.addSpacing(4)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(20)

        self._build_appearance()
        self._build_language()
        self._build_provider()
        self._build_about()

        self._scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

    def _make_field_row(self, label_text, widget):
        c = ThemeManager.instance().colors()
        row = QHBoxLayout()
        row.setSpacing(16)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"{Fonts.label(c.TEXT)} min-width: 120px;")
        row.addWidget(lbl)

        widget.setMinimumHeight(40)
        row.addWidget(widget)
        row.addStretch()
        return row

    def _build_appearance(self):
        c = ThemeManager.instance().colors()
        card = ModernCard()
        card.content_layout.setSpacing(16)

        title = SectionLabel("Appearance")
        card.content_layout.addWidget(title)

        desc = MutedLabel("Switch between dark and light themes")
        card.content_layout.addWidget(desc)

        card.content_layout.addSpacing(4)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        current = self.settings.get_theme()
        self.theme_combo.setCurrentText(current.title() if current else "Dark")
        self.theme_combo.currentTextChanged.connect(self._on_theme_changed)
        self.theme_combo.setMinimumWidth(220)

        card.content_layout.addLayout(self._make_field_row("Theme", self.theme_combo))
        self._scroll_layout.addWidget(card)

    def _build_language(self):
        c = ThemeManager.instance().colors()
        card = ModernCard()
        card.content_layout.setSpacing(16)

        title = SectionLabel("Language")
        card.content_layout.addWidget(title)

        desc = MutedLabel("Select your preferred language")
        card.content_layout.addWidget(desc)

        card.content_layout.addSpacing(4)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "Spanish", "French", "German", "Chinese", "Japanese"])
        self.language_combo.setMinimumWidth(220)

        card.content_layout.addLayout(self._make_field_row("Language", self.language_combo))
        self._scroll_layout.addWidget(card)

    def _build_provider(self):
        c = ThemeManager.instance().colors()
        card = ModernCard()
        card.content_layout.setSpacing(16)

        title = SectionLabel("AI Provider")
        card.content_layout.addWidget(title)

        desc = MutedLabel("Configure the AI provider and model for generation")
        card.content_layout.addWidget(desc)

        card.content_layout.addSpacing(4)

        self.provider_combo = QComboBox()
        self.provider_combo.setEditable(False)
        self.provider_combo.setMinimumWidth(220)

        card.content_layout.addLayout(self._make_field_row("Provider", self.provider_combo))

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("Enter model name")
        self.model_input.setMinimumWidth(260)

        card.content_layout.addLayout(self._make_field_row("Model", self.model_input))

        self._load_providers()
        self._scroll_layout.addWidget(card)

    def _build_about(self):
        c = ThemeManager.instance().colors()
        card = ModernCard()
        card.content_layout.setSpacing(12)

        title = SectionLabel("About")
        card.content_layout.addWidget(title)

        card.content_layout.addSpacing(4)

        name = CardTitle("KaiMi Studio")
        card.content_layout.addWidget(name)

        version = QLabel("Version 1.0.0")
        version.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        card.content_layout.addWidget(version)

        desc = MutedLabel("A desktop application for generating educational animation projects.")
        card.content_layout.addWidget(desc)

        card.content_layout.addSpacing(4)

        copyright_lbl = MutedLabel("\u00A9 2026 KaiMi. All rights reserved.")
        card.content_layout.addWidget(copyright_lbl)

        self._scroll_layout.addWidget(card)

    def _on_theme_changed(self, value):
        mode = value.lower()
        ThemeManager.instance().set_mode(mode)
        self.settings.set_theme(mode)

    def _load_providers(self):
        try:
            from providers.provider_manager import ProviderManager
            pm = ProviderManager()
            names = pm.get_registered_providers()
            self.provider_combo.clear()
            for name in names:
                self.provider_combo.addItem(name)

            active = pm.get_active_provider_name()
            if active and active in names:
                self.provider_combo.setCurrentText(active)

            model = pm.get_provider_model(active or "")
            if model:
                self.model_input.setText(model)
        except ImportError:
            self.provider_combo.addItem("OpenAI")
            self.provider_combo.addItem("Anthropic")
