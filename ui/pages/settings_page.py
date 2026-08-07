from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QFrame, QHBoxLayout,
    QLabel, QLineEdit, QScrollArea,
    QVBoxLayout, QWidget,
)

from core.notifications import NotificationService
from core.settings import AppSettings
from core.task_manager import TaskManager
from core.theme import Fonts
from core.version import (
    APP_NAME,
    APP_DESCRIPTION,
    AUTHOR,
    BUILD,
    COPYRIGHT,
    ENGINE_VERSION,
    OFFICIAL_EMAIL,
    VERSION,
    WORKFLOW_VERSION,
)
from ui.theme_pyside import ThemeManager
from ui.widgets import CardTitle, ModernButton, MutedLabel, ModernCard, PageTitle, SectionLabel


class _ConnectionBridge(QObject):
    """Marshals background-thread connection test results to the GUI thread.

    TaskManager runs callbacks on the worker thread; emitting a Qt signal
    from there is safe because the connection to the SettingsPage (a widget
    on the main thread) is queued.
    """

    done = Signal(bool, str)
    failed = Signal(str)


class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.settings = AppSettings()
        self.task_manager = TaskManager()
        self._loading_providers = False
        self._connection_bridge = _ConnectionBridge()
        self._connection_bridge.done.connect(self._on_connection_result)
        self._connection_bridge.failed.connect(self._on_connection_error)
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
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        header = PageTitle("Settings")
        layout.addWidget(header)

        subtitle = MutedLabel("Configure your workspace preferences")
        layout.addWidget(subtitle)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QScrollArea.NoFrame)

        scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setContentsMargins(0, 0, 0, 0)
        self._scroll_layout.setSpacing(12)

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
        lbl.setStyleSheet(f"{Fonts.label(c.TEXT)} min-width: 100px;")
        row.addWidget(lbl)

        widget.setFixedHeight(36)
        row.addWidget(widget)
        row.addStretch()
        return row

    def _build_appearance(self):
        c = ThemeManager.instance().colors()
        card = ModernCard()
        card.content_layout.setSpacing(8)

        title = SectionLabel("Appearance")
        card.content_layout.addWidget(title)

        desc = MutedLabel("Switch between dark and light themes")
        card.content_layout.addWidget(desc)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Dark", "Light"])
        current = self.settings.get_theme()
        self.theme_combo.setCurrentText(current.title() if current else "Dark")
        self.theme_combo.setMinimumWidth(220)
        self.theme_combo.currentTextChanged.connect(self._on_theme_selected)

        card.content_layout.addLayout(self._make_field_row("Theme", self.theme_combo))
        self._scroll_layout.addWidget(card)

    def _build_language(self):
        c = ThemeManager.instance().colors()
        card = ModernCard()
        card.content_layout.setSpacing(8)

        title = SectionLabel("Language")
        card.content_layout.addWidget(title)

        desc = MutedLabel("Select your preferred language")
        card.content_layout.addWidget(desc)

        self.language_combo = QComboBox()
        self.language_combo.addItems(["English", "Spanish", "French", "German", "Chinese", "Japanese"])
        self.language_combo.setMinimumWidth(220)

        card.content_layout.addLayout(self._make_field_row("Language", self.language_combo))
        self._scroll_layout.addWidget(card)

    def _build_provider(self):
        card = ModernCard()
        card.content_layout.setSpacing(8)

        title = SectionLabel("AI Provider")
        card.content_layout.addWidget(title)

        desc = MutedLabel("Configure the AI provider and model for generation")
        card.content_layout.addWidget(desc)

        self.provider_combo = QComboBox()
        self.provider_combo.setEditable(False)
        self.provider_combo.setMinimumWidth(220)
        self.provider_combo.currentTextChanged.connect(self._on_provider_changed)
        card.content_layout.addLayout(self._make_field_row("Provider", self.provider_combo))

        self.model_input = QLineEdit()
        self.model_input.setPlaceholderText("Enter model name")
        self.model_input.setMinimumWidth(260)
        card.content_layout.addLayout(self._make_field_row("Model", self.model_input))

        self.base_url_input = QLineEdit()
        self.base_url_input.setPlaceholderText("Enter base URL")
        self.base_url_input.setMinimumWidth(260)
        card.content_layout.addLayout(self._make_field_row("Base URL", self.base_url_input))

        self.api_key_input = QLineEdit()
        self.api_key_input.setEchoMode(QLineEdit.Password)
        self.api_key_input.setPlaceholderText("Enter API key")
        self.api_key_input.setMinimumWidth(260)
        card.content_layout.addLayout(self._make_field_row("API Key", self.api_key_input))

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self.save_provider_btn = ModernButton("Save Provider", primary=True)
        self.save_provider_btn.clicked.connect(self._save_provider)
        buttons.addWidget(self.save_provider_btn)

        self.test_connection_btn = ModernButton("Test Connection", primary=False)
        self.test_connection_btn.clicked.connect(self._test_connection)
        buttons.addWidget(self.test_connection_btn)

        buttons.addStretch()
        card.content_layout.addLayout(buttons)

        self.provider_status = MutedLabel("")
        self.provider_status.setWordWrap(True)
        card.content_layout.addWidget(self.provider_status)

        self._load_providers()
        self._scroll_layout.addWidget(card)

    def _build_about(self):
        c = ThemeManager.instance().colors()
        card = ModernCard()
        card.content_layout.setSpacing(6)

        title = SectionLabel("About")
        card.content_layout.addWidget(title)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(12)

        from core.branding import logo_pixmap
        brand_logo = QLabel()
        brand_logo.setPixmap(logo_pixmap(96))
        brand_logo.setFixedSize(96, 96)
        brand_logo.setAttribute(Qt.WA_TransparentForMouseEvents)
        brand_row.addWidget(brand_logo)

        brand_text = QVBoxLayout()
        brand_text.setSpacing(2)
        name = CardTitle(APP_NAME)
        brand_text.addWidget(name)
        desc = MutedLabel(APP_DESCRIPTION)
        brand_text.addWidget(desc)
        brand_row.addLayout(brand_text, 1)
        card.content_layout.addLayout(brand_row)

        card.content_layout.addLayout(
            self._make_identity_row("Version", VERSION)
        )
        card.content_layout.addLayout(
            self._make_identity_row("Build", BUILD)
        )
        card.content_layout.addLayout(
            self._make_identity_row("Engine", ENGINE_VERSION)
        )
        card.content_layout.addLayout(
            self._make_identity_row("Workflow", WORKFLOW_VERSION)
        )
        card.content_layout.addLayout(
            self._make_identity_row("Author", AUTHOR)
        )

        email_row = QHBoxLayout()
        email_row.setSpacing(16)
        email_lbl = QLabel("Official Email")
        email_lbl.setStyleSheet(f"{Fonts.label(c.TEXT)} min-width: 100px;")
        email_row.addWidget(email_lbl)
        email_value = QLabel(OFFICIAL_EMAIL)
        email_value.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        email_row.addWidget(email_value)
        email_row.addStretch()
        self.email_copy_btn = ModernButton("Copy", primary=False)
        self.email_copy_btn.clicked.connect(self._copy_official_email)
        email_row.addWidget(self.email_copy_btn)
        card.content_layout.addLayout(email_row)

        copyright_lbl = MutedLabel(COPYRIGHT)
        card.content_layout.addWidget(copyright_lbl)

        buttons = QHBoxLayout()
        buttons.setSpacing(12)
        self.about_dialog_btn = ModernButton("About KaiMi Studio", primary=False)
        self.about_dialog_btn.clicked.connect(self._open_about_dialog)
        buttons.addWidget(self.about_dialog_btn)
        buttons.addStretch()
        card.content_layout.addLayout(buttons)

        self._scroll_layout.addWidget(card)

    def _make_identity_row(self, label_text: str, value_text: str) -> QHBoxLayout:
        """Read-only identity row used by the About card."""
        c = ThemeManager.instance().colors()
        row = QHBoxLayout()
        row.setSpacing(16)

        lbl = QLabel(label_text)
        lbl.setStyleSheet(f"{Fonts.label(c.TEXT)} min-width: 100px;")
        row.addWidget(lbl)

        value = QLabel(value_text)
        value.setStyleSheet(f"{Fonts.body(c.TEXT_SECONDARY)}")
        row.addWidget(value)
        row.addStretch()
        return row

    def _copy_official_email(self):
        """Copy the official email to the clipboard with feedback."""
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(OFFICIAL_EMAIL)
        NotificationService.get().info("Official email copied to clipboard.")

    def _open_about_dialog(self):
        """Open the professional About dialog."""
        from ui.dialogs.about_dialog import AboutDialog
        dialog = AboutDialog(self)
        dialog.exec()

    def _on_theme_selected(self, value):
        mode = value.lower()
        self.settings.set_theme(mode)
        ThemeManager.instance().set_mode(mode)

    # ── Provider configuration ───────────────────────────────────────

    def _load_providers(self):
        """Populate the provider combo box and load the active provider's fields."""
        self._loading_providers = True
        try:
            from providers.provider_manager import ProviderManager
            pm = ProviderManager()
            names = pm.get_registered_providers()
            self.provider_combo.clear()
            for name in names:
                meta = pm.get_provider_metadata(name)
                self.provider_combo.addItem(meta.get("display_name", name.title()), name)

            active = pm.get_active_provider_name()
            idx = self.provider_combo.findData(active)
            if idx >= 0:
                self.provider_combo.setCurrentIndex(idx)
        except ImportError:
            self.provider_combo.addItem("Gemini", "gemini")
            self.provider_combo.addItem("Anthropic", "anthropic")
        finally:
            self._loading_providers = False
        self._load_provider_fields()

    def _current_provider_name(self) -> str:
        """Return the canonical name of the provider currently selected."""
        return str(self.provider_combo.currentData() or "").strip().lower()

    def _on_provider_changed(self, *args):
        # Browsing the dropdown only loads that provider's fields for
        # editing; the selection becomes active only via Save Provider.
        if self._loading_providers:
            return
        if not self._current_provider_name():
            return
        self._load_provider_fields()

    def _load_provider_fields(self):
        """Load saved model, base URL, and API key for the selected provider."""
        name = self._current_provider_name()
        if not name:
            return

        from providers.provider_manager import ProviderManager
        pm = ProviderManager()
        meta = pm.get_provider_metadata(name)
        display = meta.get("display_name", name.title())
        requires_key = meta.get("requires_key", True)

        self.model_input.setText(pm.get_provider_model(name))
        self.base_url_input.setText(pm.get_provider_base_url(name))

        saved_key = pm.get_provider_api_key(name)
        self.api_key_input.setText(saved_key)

        if requires_key:
            self.api_key_input.setEnabled(True)
            self.api_key_input.setPlaceholderText("Enter API key")
            if saved_key:
                self._set_provider_status(f"{display} API key is configured.", "success")
            else:
                self._set_provider_status(f"No API key saved for {display}.", "warning")
        else:
            self.api_key_input.setEnabled(False)
            self.api_key_input.setText("")
            self.api_key_input.setPlaceholderText("No API key required (local provider)")
            self._set_provider_status(
                f"{display} is a local provider — no API key required.", "info"
            )

    def _save_provider(self):
        """Persist the provider selection, API key, base URL, and model."""
        name = self._current_provider_name()
        if not name:
            return

        from providers.provider_manager import ProviderManager
        pm = ProviderManager()
        meta = pm.get_provider_metadata(name)
        display = meta.get("display_name", name.title())
        requires_key = meta.get("requires_key", True)

        stored = pm.get_provider_config(name)
        model = self.model_input.text().strip() or stored.get("model", "")
        base_url = self.base_url_input.text().strip() or stored.get("base_url", "")
        api_key = self.api_key_input.text().strip()
        if not api_key:
            api_key = pm.get_provider_api_key(name)

        pm.set_active_provider(name)
        pm.save_provider_config(name, api_key=api_key, base_url=base_url, model=model)

        if requires_key and not api_key:
            self._set_provider_status(f"{display} saved, but no API key is set yet.", "warning")
        else:
            self._set_provider_status(f"{display} configuration saved.", "success")
        NotificationService.get().success(f"{display} configuration saved.")

    def _test_connection(self):
        """Save the current config, then test the selected provider."""
        name = self._current_provider_name()
        if not name:
            return

        self._save_provider()

        from providers.provider_manager import ProviderManager
        pm = ProviderManager()
        meta = pm.get_provider_metadata(name)
        display = meta.get("display_name", name.title())

        self.test_connection_btn.setText("Testing...")
        self.test_connection_btn.setEnabled(False)
        self._set_provider_status(f"Testing connection to {display}...", "info")

        def run_task(task_manager):
            return pm.test_provider_connection(name)

        def on_complete(result):
            ok, message = result
            self._connection_bridge.done.emit(bool(ok), str(message))

        def on_error(exc):
            self._connection_bridge.failed.emit(f"{display} connection failed: {exc}")

        self.task_manager.run_task(
            task_name=f"Test {display} Connection",
            task_func=run_task,
            on_complete=on_complete,
            on_error=on_error,
        )

    def _on_connection_result(self, ok, message):
        """Show the provider-specific result of a connection test."""
        self.test_connection_btn.setText("Test Connection")
        self.test_connection_btn.setEnabled(True)
        self._set_provider_status(message, "success" if ok else "error")
        if ok:
            NotificationService.get().success(message)
        else:
            NotificationService.get().error(message)

    def _on_connection_error(self, message):
        self.test_connection_btn.setText("Test Connection")
        self.test_connection_btn.setEnabled(True)
        self._set_provider_status(message, "error")
        NotificationService.get().error(message)

    def _set_provider_status(self, message, level="info"):
        """Update the provider status label with the given message and color."""
        c = ThemeManager.instance().colors()
        colors = {
            "success": c.SUCCESS,
            "warning": c.WARNING,
            "error": c.ERROR,
            "info": c.TEXT_SECONDARY,
        }
        color = colors.get(level, c.TEXT_SECONDARY)
        self.provider_status.setText(message)
        self.provider_status.setStyleSheet(Fonts.body(color))
