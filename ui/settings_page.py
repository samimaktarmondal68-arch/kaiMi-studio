# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Settings page for KaiMi Studio.

Provides:
    - Appearance (theme persistence)
    - AI Provider configuration
    - Application settings (autosave, recent projects)
    - Export preferences
"""

import customtkinter as ctk

from core.theme import Dark, Fonts, Radius, Spacing
from core.version import VERSION
from core.settings import AppSettings
from providers.provider_manager import ProviderManager


class SettingsPage(ctk.CTkFrame):
    """Settings page with appearance, provider, and general settings."""

    def __init__(self, master):
        super().__init__(master, fg_color=Dark.BG)
        self._provider_manager = ProviderManager()
        self._app_settings = AppSettings()
        self._key_visible = False
        self._model_options: list[str] = []

        # Scrollable content
        scroll = ctk.CTkScrollableFrame(
            self,
            fg_color=Dark.BG,
            scrollbar_button_color=Dark.BORDER,
            scrollbar_button_hover_color=Dark.TEXT_MUTED,
        )
        scroll.pack(fill="both", expand=True)

        # Page title
        ctk.CTkLabel(
            scroll,
            text="Settings",
            font=Fonts.TITLE,
            text_color=Dark.TEXT,
        ).pack(anchor="w", padx=Spacing.X12, pady=(Spacing.X8, Spacing.X5))

        # Appearance card
        self._build_appearance_card(scroll)

        # Application card
        self._build_application_card(scroll)

        # Export card
        self._build_export_card(scroll)

        # Provider card
        self._build_provider_card(scroll)

        # Save All button
        self._build_save_all(scroll)

        # Footer
        ctk.CTkLabel(
            scroll,
            text=f"KaiMi Studio  \u2022  v{VERSION}",
            font=Fonts.SMALL,
            text_color=Dark.TEXT_MUTED,
        ).pack(anchor="w", padx=Spacing.X12, pady=Spacing.X8)

    # ── Appearance Card ──────────────────────────────────────────────

    def _build_appearance_card(self, parent) -> None:
        card = ctk.CTkFrame(
            parent,
            fg_color=Dark.CARD,
            corner_radius=Radius.LG,
            border_width=1,
            border_color=Dark.BORDER,
        )
        card.pack(fill="x", padx=Spacing.X12, pady=(0, Spacing.X4))

        ctk.CTkLabel(
            card,
            text="Appearance",
            font=Fonts.SECTION,
            text_color=Dark.TEXT,
        ).pack(anchor="w", padx=Spacing.X6, pady=(Spacing.X5, Spacing.X3))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=Spacing.X6, pady=(0, Spacing.X5))

        ctk.CTkLabel(
            row,
            text="Theme",
            font=Fonts.BODY,
            text_color=Dark.TEXT_SECONDARY,
        ).pack(side="left")

        current_theme = self._app_settings.get_theme().title()
        self._theme_var = ctk.StringVar(value=current_theme)

        mode = ctk.CTkOptionMenu(
            row,
            values=["Dark", "Light", "System"],
            variable=self._theme_var,
            command=self._on_theme_changed,
            fg_color=Dark.INPUT_BG,
            button_color=Dark.PRIMARY,
            button_hover_color=Dark.PRIMARY_HOVER,
            dropdown_fg_color=Dark.CARD,
            dropdown_hover_color=Dark.HOVER,
            width=160,
            height=36,
            font=Fonts.BODY,
        )
        mode.pack(side="right")

    def _on_theme_changed(self, value: str) -> None:
        ctk.set_appearance_mode(value.lower())
        self._app_settings.set_theme(value.lower())

    # ── Application Card ─────────────────────────────────────────────

    def _build_application_card(self, parent) -> None:
        card = ctk.CTkFrame(
            parent,
            fg_color=Dark.CARD,
            corner_radius=Radius.LG,
            border_width=1,
            border_color=Dark.BORDER,
        )
        card.pack(fill="x", padx=Spacing.X12, pady=(0, Spacing.X4))

        ctk.CTkLabel(
            card,
            text="Application",
            font=Fonts.SECTION,
            text_color=Dark.TEXT,
        ).pack(anchor="w", padx=Spacing.X6, pady=(Spacing.X5, Spacing.X3))

        # Autosave row
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=Spacing.X6, pady=(0, Spacing.X3))

        ctk.CTkLabel(
            row,
            text="Autosave",
            font=Fonts.BODY,
            text_color=Dark.TEXT_SECONDARY,
        ).pack(side="left")

        self._autosave_var = ctk.StringVar(value="On" if self._app_settings.get("autosave_enabled", True) else "Off")
        autosave_menu = ctk.CTkOptionMenu(
            row,
            values=["On", "Off"],
            variable=self._autosave_var,
            fg_color=Dark.INPUT_BG,
            button_color=Dark.PRIMARY,
            button_hover_color=Dark.PRIMARY_HOVER,
            dropdown_fg_color=Dark.CARD,
            dropdown_hover_color=Dark.HOVER,
            width=160,
            height=36,
            font=Fonts.BODY,
        )
        autosave_menu.pack(side="right")

        # Autosave interval row
        row2 = ctk.CTkFrame(card, fg_color="transparent")
        row2.pack(fill="x", padx=Spacing.X6, pady=(0, Spacing.X3))

        ctk.CTkLabel(
            row2,
            text="Autosave Interval (seconds)",
            font=Fonts.BODY,
            text_color=Dark.TEXT_SECONDARY,
        ).pack(side="left")

        current_interval = str(self._app_settings.get("autosave_interval", 30))
        self._interval_var = ctk.StringVar(value=current_interval)
        interval_menu = ctk.CTkOptionMenu(
            row2,
            values=["15", "30", "60", "120"],
            variable=self._interval_var,
            fg_color=Dark.INPUT_BG,
            button_color=Dark.PRIMARY,
            button_hover_color=Dark.PRIMARY_HOVER,
            dropdown_fg_color=Dark.CARD,
            dropdown_hover_color=Dark.HOVER,
            width=160,
            height=36,
            font=Fonts.BODY,
        )
        interval_menu.pack(side="right")

    # ── Export Card ───────────────────────────────────────────────────

    def _build_export_card(self, parent) -> None:
        card = ctk.CTkFrame(
            parent,
            fg_color=Dark.CARD,
            corner_radius=Radius.LG,
            border_width=1,
            border_color=Dark.BORDER,
        )
        card.pack(fill="x", padx=Spacing.X12, pady=(0, Spacing.X4))

        ctk.CTkLabel(
            card,
            text="Export",
            font=Fonts.SECTION,
            text_color=Dark.TEXT,
        ).pack(anchor="w", padx=Spacing.X6, pady=(Spacing.X5, Spacing.X3))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=Spacing.X6, pady=(0, Spacing.X5))

        ctk.CTkLabel(
            row,
            text="Default Export Format",
            font=Fonts.BODY,
            text_color=Dark.TEXT_SECONDARY,
        ).pack(side="left")

        current_fmt = self._app_settings.get("export_format", "zip").title()
        self._export_fmt_var = ctk.StringVar(value=current_fmt)
        fmt_menu = ctk.CTkOptionMenu(
            row,
            values=["Zip", "Markdown", "Txt", "Json", "Docx", "Pdf"],
            variable=self._export_fmt_var,
            fg_color=Dark.INPUT_BG,
            button_color=Dark.PRIMARY,
            button_hover_color=Dark.PRIMARY_HOVER,
            dropdown_fg_color=Dark.CARD,
            dropdown_hover_color=Dark.HOVER,
            width=160,
            height=36,
            font=Fonts.BODY,
        )
        fmt_menu.pack(side="right")

    # ── Provider Card ────────────────────────────────────────────────

    def _build_provider_card(self, parent) -> None:
        self._card = ctk.CTkFrame(
            parent,
            fg_color=Dark.CARD,
            corner_radius=Radius.LG,
            border_width=1,
            border_color=Dark.BORDER,
        )
        self._card.pack(fill="x", padx=Spacing.X12, pady=(0, Spacing.X4))

        # Header
        header = ctk.CTkFrame(self._card, fg_color="transparent")
        header.pack(fill="x", padx=Spacing.X6, pady=(Spacing.X5, Spacing.X3))

        ctk.CTkLabel(
            header,
            text="AI Provider",
            font=Fonts.SECTION,
            text_color=Dark.TEXT,
        ).pack(side="left")

        # Status pill
        self._status_pill = ctk.CTkLabel(
            header,
            text="Not Configured",
            font=Fonts.SMALL_BOLD,
            text_color=Dark.ERROR,
            fg_color=Dark.ERROR_LIGHT,
            corner_radius=Radius.SM,
            padx=Spacing.X3,
            pady=Spacing.X1,
        )
        self._status_pill.pack(side="right")

        # Provider selector
        self._build_provider_selector()
        self._build_api_key_row()
        self._build_base_url_row()
        self._build_model_row()
        self._build_action_buttons()

        self._load_current_config()

    def _build_provider_selector(self) -> None:
        row = ctk.CTkFrame(self._card, fg_color="transparent")
        row.pack(fill="x", padx=Spacing.X6, pady=(0, Spacing.X3))

        ctk.CTkLabel(
            row,
            text="Provider",
            font=Fonts.SMALL_BOLD,
            text_color=Dark.TEXT_SECONDARY,
        ).pack(side="left")

        self._provider_names = self._provider_manager.get_registered_providers()
        display_names = [n.title() for n in self._provider_names]

        self._provider_var = ctk.StringVar(value=self._get_current_display_name())
        self._provider_menu = ctk.CTkOptionMenu(
            row,
            values=display_names,
            variable=self._provider_var,
            command=self._on_provider_changed,
            fg_color=Dark.INPUT_BG,
            button_color=Dark.PRIMARY,
            button_hover_color=Dark.PRIMARY_HOVER,
            dropdown_fg_color=Dark.CARD,
            dropdown_hover_color=Dark.HOVER,
            width=200,
            height=36,
            font=Fonts.BODY,
        )
        self._provider_menu.pack(side="right")

    def _build_api_key_row(self) -> None:
        row = ctk.CTkFrame(self._card, fg_color="transparent")
        row.pack(fill="x", padx=Spacing.X6, pady=(0, Spacing.X3))

        ctk.CTkLabel(
            row,
            text="API Key",
            font=Fonts.SMALL_BOLD,
            text_color=Dark.TEXT_SECONDARY,
        ).pack(side="left")

        entry_frame = ctk.CTkFrame(row, fg_color="transparent")
        entry_frame.pack(side="right")

        self._api_key_entry = ctk.CTkEntry(
            entry_frame,
            width=320,
            height=36,
            show="\u2022",
            placeholder_text="Enter API key",
            fg_color=Dark.INPUT_BG,
            border_color=Dark.INPUT_BORDER,
            text_color=Dark.TEXT,
            font=Fonts.INPUT,
            corner_radius=Radius.SM,
        )
        self._api_key_entry.pack(side="left", padx=(0, Spacing.X2))

        self._show_hide_btn = ctk.CTkButton(
            entry_frame,
            text="Show",
            width=60,
            height=36,
            fg_color=Dark.INPUT_BG,
            hover_color=Dark.HOVER,
            text_color=Dark.TEXT_SECONDARY,
            font=Fonts.SMALL,
            corner_radius=Radius.SM,
            command=self._toggle_key_visibility,
        )
        self._show_hide_btn.pack(side="left")

    def _build_base_url_row(self) -> None:
        self._base_url_frame = ctk.CTkFrame(self._card, fg_color="transparent")
        self._base_url_frame.pack(fill="x", padx=Spacing.X6, pady=(0, Spacing.X3))

        ctk.CTkLabel(
            self._base_url_frame,
            text="Base URL",
            font=Fonts.SMALL_BOLD,
            text_color=Dark.TEXT_SECONDARY,
        ).pack(side="left")

        self._base_url_entry = ctk.CTkEntry(
            self._base_url_frame,
            width=380,
            height=36,
            placeholder_text="https://opencode.ai/zen",
            fg_color=Dark.INPUT_BG,
            border_color=Dark.INPUT_BORDER,
            text_color=Dark.TEXT,
            font=Fonts.INPUT,
            corner_radius=Radius.SM,
        )
        self._base_url_entry.pack(side="right")

    def _build_model_row(self) -> None:
        self._model_frame = ctk.CTkFrame(self._card, fg_color="transparent")
        self._model_frame.pack(fill="x", padx=Spacing.X6, pady=(0, Spacing.X3))

        ctk.CTkLabel(
            self._model_frame,
            text="Model",
            font=Fonts.SMALL_BOLD,
            text_color=Dark.TEXT_SECONDARY,
        ).pack(side="left")

        model_controls = ctk.CTkFrame(self._model_frame, fg_color="transparent")
        model_controls.pack(side="right")

        self._model_var = ctk.StringVar(value="")
        self._model_menu = ctk.CTkOptionMenu(
            model_controls,
            values=["Click Load or enter model manually"],
            variable=self._model_var,
            fg_color=Dark.INPUT_BG,
            button_color=Dark.PRIMARY,
            button_hover_color=Dark.PRIMARY_HOVER,
            dropdown_fg_color=Dark.CARD,
            dropdown_hover_color=Dark.HOVER,
            width=220,
            height=36,
            font=Fonts.BODY,
        )
        self._model_menu.pack(side="left", padx=(0, Spacing.X2))

        self._model_entry = ctk.CTkEntry(
            model_controls,
            width=180,
            height=36,
            placeholder_text="Or type model name",
            fg_color=Dark.INPUT_BG,
            border_color=Dark.INPUT_BORDER,
            text_color=Dark.TEXT,
            font=Fonts.INPUT,
            corner_radius=Radius.SM,
        )
        self._model_entry.pack(side="left", padx=(0, Spacing.X2))

        self._load_models_btn = ctk.CTkButton(
            model_controls,
            text="Load",
            width=60,
            height=36,
            fg_color=Dark.PRIMARY,
            hover_color=Dark.PRIMARY_HOVER,
            text_color=Dark.TEXT,
            font=Fonts.SMALL_BOLD,
            corner_radius=Radius.SM,
            command=self._load_models,
        )
        self._load_models_btn.pack(side="left")

    def _build_action_buttons(self) -> None:
        btn_row = ctk.CTkFrame(self._card, fg_color="transparent")
        btn_row.pack(fill="x", padx=Spacing.X6, pady=(Spacing.X4, Spacing.X6))

        self._save_btn = ctk.CTkButton(
            btn_row,
            text="Save Configuration",
            width=160,
            height=40,
            fg_color=Dark.PRIMARY,
            hover_color=Dark.PRIMARY_HOVER,
            text_color=Dark.TEXT,
            font=Fonts.BUTTON,
            corner_radius=Radius.MD,
            command=self._save_config,
        )
        self._save_btn.pack(side="left")

        self._test_btn = ctk.CTkButton(
            btn_row,
            text="Test Connection",
            width=140,
            height=40,
            fg_color="transparent",
            hover_color=Dark.HOVER,
            text_color=Dark.SECONDARY,
            font=Fonts.BUTTON,
            corner_radius=Radius.MD,
            border_width=1,
            border_color=Dark.SECONDARY,
            command=self._test_connection,
        )
        self._test_btn.pack(side="left", padx=Spacing.X3)

        self._feedback_label = ctk.CTkLabel(
            btn_row,
            text="",
            font=Fonts.SMALL,
            text_color=Dark.TEXT_SECONDARY,
        )
        self._feedback_label.pack(side="left", padx=Spacing.X3)

    # ── Save All ─────────────────────────────────────────────────────

    def _build_save_all(self, parent) -> None:
        card = ctk.CTkFrame(
            parent,
            fg_color=Dark.CARD,
            corner_radius=Radius.LG,
            border_width=1,
            border_color=Dark.BORDER,
        )
        card.pack(fill="x", padx=Spacing.X12, pady=(0, Spacing.X4))

        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=Spacing.X6, pady=Spacing.X5)

        self._save_all_btn = ctk.CTkButton(
            row,
            text="Save All Settings",
            width=200,
            height=44,
            fg_color=Dark.PRIMARY,
            hover_color=Dark.PRIMARY_HOVER,
            text_color=Dark.TEXT,
            font=Fonts.BUTTON,
            corner_radius=Radius.MD,
            command=self._save_all_settings,
        )
        self._save_all_btn.pack(side="left")

        self._save_all_feedback = ctk.CTkLabel(
            row,
            text="",
            font=Fonts.SMALL,
            text_color=Dark.TEXT_SECONDARY,
        )
        self._save_all_feedback.pack(side="left", padx=Spacing.X4)

    def _save_all_settings(self) -> None:
        """Save all settings (appearance, application, export, provider)."""
        try:
            # Save appearance
            theme = self._theme_var.get().lower()
            self._app_settings.set_theme(theme)
            ctk.set_appearance_mode(theme)

            # Save application settings
            self._app_settings.set("autosave_enabled", self._autosave_var.get() == "On")
            self._app_settings.set("autosave_interval", int(self._interval_var.get()))

            # Save export settings
            self._app_settings.set("export_format", self._export_fmt_var.get().lower())

            # Save provider settings
            self._save_config()

            self._save_all_feedback.configure(
                text="All settings saved.", text_color=Dark.SUCCESS
            )
        except Exception as e:
            self._save_all_feedback.configure(
                text=f"Error: {e}", text_color=Dark.ERROR
            )

    # ── Helpers ──────────────────────────────────────────────────────

    def _get_active_name(self) -> str:
        display = self._provider_var.get()
        for name in self._provider_names:
            if name.title() == display:
                return name
        return self._provider_manager.get_active_provider_name()

    def _get_current_display_name(self) -> str:
        active = self._provider_manager.get_active_provider_name()
        return active.title() if active else self._provider_names[0].title()

    def _show_base_url(self, provider_name: str) -> bool:
        return self._provider_manager.show_base_url(provider_name)

    def _requires_key(self, provider_name: str) -> bool:
        return self._provider_manager.provider_requires_key(provider_name)

    # ── Events ───────────────────────────────────────────────────────

    def _on_provider_changed(self, display_name: str) -> None:
        name = self._get_active_name()

        self._api_key_entry.delete(0, "end")
        key = self._provider_manager.get_provider_api_key(name)
        if key:
            self._api_key_entry.insert(0, key)

        base_url = self._provider_manager.get_provider_base_url(name)
        self._base_url_entry.delete(0, "end")
        if base_url:
            self._base_url_entry.insert(0, base_url)

        model = self._provider_manager.get_provider_model(name)
        self._model_entry.delete(0, "end")
        if model:
            self._model_entry.insert(0, model)
            self._model_var.set(model)
        else:
            self._model_var.set("")

        if self._show_base_url(name):
            self._base_url_frame.pack(fill="x", padx=Spacing.X6, pady=(0, Spacing.X3), after=self._api_key_entry.master.master)
        else:
            self._base_url_frame.pack_forget()

        if self._requires_key(name):
            self._api_key_entry.master.pack(fill="x", padx=Spacing.X6, pady=(0, Spacing.X3))
        else:
            self._api_key_entry.master.pack_forget()

        self._refresh_status()
        self._feedback_label.configure(text="")

        if key or not self._requires_key(name):
            self._load_models()

    def _load_current_config(self) -> None:
        name = self._get_active_name()

        key = self._provider_manager.get_provider_api_key(name)
        if key:
            self._api_key_entry.insert(0, key)

        base_url = self._provider_manager.get_provider_base_url(name)
        if base_url:
            self._base_url_entry.insert(0, base_url)

        model = self._provider_manager.get_provider_model(name)
        if model:
            self._model_entry.insert(0, model)
            self._model_var.set(model)

        if not self._show_base_url(name):
            self._base_url_frame.pack_forget()

        if not self._requires_key(name):
            self._api_key_entry.master.pack_forget()

        self._refresh_status()

        if key or not self._requires_key(name):
            self._load_models()

    def _refresh_status(self) -> None:
        name = self._get_active_name()
        configured = self._provider_manager.validate_provider_configuration(name)
        if configured:
            self._status_pill.configure(
                text="Configured",
                text_color=Dark.SUCCESS,
                fg_color=Dark.SUCCESS_LIGHT,
            )
        else:
            self._status_pill.configure(
                text="Not Configured",
                text_color=Dark.ERROR,
                fg_color=Dark.ERROR_LIGHT,
            )

    def _toggle_key_visibility(self) -> None:
        self._key_visible = not self._key_visible
        self._api_key_entry.configure(show="" if self._key_visible else "\u2022")
        self._show_hide_btn.configure(text="Hide" if self._key_visible else "Show")

    def _save_config(self) -> None:
        name = self._get_active_name()
        api_key = self._api_key_entry.get().strip() if self._requires_key(name) else ""
        base_url = self._base_url_entry.get().strip() if self._show_base_url(name) else ""
        model = self._model_entry.get().strip() or self._model_var.get().strip()

        if self._requires_key(name) and not api_key:
            self._feedback_label.configure(text="API key cannot be empty.", text_color=Dark.ERROR)
            return

        self._provider_manager.save_provider_config(
            provider_name=name,
            api_key=api_key,
            base_url=base_url,
            model=model,
        )
        self._provider_manager.set_active_provider(name)
        self._refresh_status()
        self._feedback_label.configure(text="Saved.", text_color=Dark.SUCCESS)

        self._load_models()

    def _test_connection(self) -> None:
        name = self._get_active_name()
        api_key = self._api_key_entry.get().strip() if self._requires_key(name) else "local"

        if self._requires_key(name) and not api_key:
            self._feedback_label.configure(text="Enter an API key first.", text_color=Dark.ERROR)
            return

        self._feedback_label.configure(text="Testing...", text_color=Dark.TEXT_MUTED)
        self._test_btn.configure(state="disabled")

        base_url = self._base_url_entry.get().strip() if self._show_base_url(name) else ""
        model = self._model_entry.get().strip() or self._model_var.get().strip()

        def run_test():
            self._provider_manager.save_provider_config(
                provider_name=name,
                api_key=api_key,
                base_url=base_url,
                model=model,
            )
            success, message = self._provider_manager.test_provider_connection(name)

            def update_ui():
                self._test_btn.configure(state="normal")
                color = Dark.SUCCESS if success else Dark.ERROR
                self._feedback_label.configure(text=message, text_color=color)
                self._refresh_status()

                if success:
                    self._load_models()

            self.after(0, update_ui)

        import threading
        threading.Thread(target=run_test, daemon=True).start()

    def _load_models(self) -> None:
        name = self._get_active_name()
        api_key = self._provider_manager.get_provider_api_key(name)

        if self._requires_key(name) and not api_key:
            self._feedback_label.configure(text="Set an API key first.", text_color=Dark.ERROR)
            return

        self._feedback_label.configure(text="Loading models...", text_color=Dark.TEXT_MUTED)
        self._load_models_btn.configure(state="disabled")

        def run_load():
            error_message = None
            models = []

            try:
                models = self._provider_manager.list_models(name)
            except Exception as exc:
                error_message = f"{type(exc).__name__}: {exc}"

            def update_ui():
                self._load_models_btn.configure(state="normal")
                if models:
                    self._model_menu.configure(values=models)
                    self._model_options = models
                    current = self._model_var.get()
                    if current not in models:
                        self._model_var.set(models[0])
                    self._feedback_label.configure(text=f"Loaded {len(models)} models.", text_color=Dark.SUCCESS)
                elif error_message:
                    self._feedback_label.configure(
                        text=f"Failed: {error_message[:80]}",
                        text_color=Dark.ERROR,
                    )
                else:
                    self._feedback_label.configure(
                        text="No models found. Enter model manually.",
                        text_color=Dark.TEXT_MUTED,
                    )

            self.after(0, update_ui)

        import threading
        threading.Thread(target=run_load, daemon=True).start()
