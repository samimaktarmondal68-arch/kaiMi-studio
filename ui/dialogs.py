"""First-run welcome dialog for KaiMi Studio.

Shows on first launch to guide new users through the application.
"""

import customtkinter as ctk

from core.theme import Dark, Fonts, Radius, Spacing
from core.version import APP_NAME, VERSION, CODENAME


class FirstRunDialog(ctk.CTkToplevel):

    def __init__(self, master, on_close=None):
        super().__init__(master)

        self.title(f"Welcome to {APP_NAME}")
        self.geometry("520x580")
        self.resizable(False, False)
        self.configure(fg_color=Dark.BG)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._on_close = on_close
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=Dark.BG,
            scrollbar_button_color=Dark.BORDER,
            scrollbar_button_hover_color=Dark.TEXT_MUTED,
        )
        scroll.pack(fill="both", expand=True)

        # Header
        ctk.CTkLabel(
            scroll, text=f"Welcome to {APP_NAME}",
            font=Fonts.HEADING, text_color=Dark.PRIMARY,
        ).pack(padx=Spacing.X8, pady=(Spacing.X8, Spacing.X2))

        ctk.CTkLabel(
            scroll, text=f"v{VERSION} \u2014 {CODENAME}",
            font=Fonts.BODY, text_color=Dark.TEXT_SECONDARY,
        ).pack(padx=Spacing.X8, pady=(0, Spacing.X6))

        # Steps
        steps = [
            ("\U0001F3E0", "Create a Project", "Start from the Dashboard. Give your project a name, topic, and language."),
            ("\U0001F50D", "Select a Provider", "Go to Provider Settings and configure your AI provider (Gemini, OpenAI, etc.)."),
            ("\U0001F9E0", "Generate Research", "Open your project and let AI research your topic automatically."),
            ("\U0001F4DD", "Write the Script", "The AI will create a structured script based on the research."),
            ("\U0001F3AC", "Build Storyboard", "Generate scene-by-scene visual breakdowns."),
            ("\U0001F5BC\uFE0F", "Create Image Prompts", "Get detailed prompts for each scene illustration."),
            ("\U0001F4E4", "Export", "Download your completed project as TXT, PDF, DOCX, or ZIP."),
        ]

        for icon, title, desc in steps:
            card = ctk.CTkFrame(
                scroll, fg_color=Dark.CARD, corner_radius=Radius.MD,
                border_width=1, border_color=Dark.BORDER, height=60,
            )
            card.pack(fill="x", padx=Spacing.X8, pady=(0, Spacing.X3))
            card.pack_propagate(False)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=Spacing.X4, pady=Spacing.X3)

            icon_bg = ctk.CTkFrame(inner, width=32, height=32, corner_radius=Radius.SM, fg_color=Dark.SURFACE)
            icon_bg.pack(side="left", padx=(0, Spacing.X3))
            icon_bg.pack_propagate(False)
            ctk.CTkLabel(icon_bg, text=icon, font=(Fonts.FAMILY, 14), fg_color="transparent").pack(expand=True)

            text_col = ctk.CTkFrame(inner, fg_color="transparent")
            text_col.pack(side="left", fill="both", expand=True)

            ctk.CTkLabel(
                text_col, text=title,
                font=Fonts.CARD_TITLE, text_color=Dark.TEXT,
            ).pack(anchor="w")

            ctk.CTkLabel(
                text_col, text=desc,
                font=Fonts.SMALL, text_color=Dark.TEXT_SECONDARY,
            ).pack(anchor="w")

        # Keyboard shortcuts hint
        ctk.CTkLabel(
            scroll, text="Tip: Press Ctrl+K to search projects, Ctrl+S to save.",
            font=Fonts.SMALL, text_color=Dark.TEXT_MUTED,
        ).pack(padx=Spacing.X8, pady=(Spacing.X4, Spacing.X3))

        # Buttons
        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(fill="x", padx=Spacing.X8, pady=(Spacing.X2, Spacing.X8))

        ctk.CTkButton(
            btn_frame, text="Don't show again",
            font=Fonts.BODY, fg_color=Dark.SURFACE,
            hover_color=Dark.HOVER, text_color=Dark.TEXT_SECONDARY,
            height=38, corner_radius=Radius.MD,
            command=self._on_close,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="Get Started",
            font=Fonts.BODY_BOLD, fg_color=Dark.PRIMARY,
            hover_color=Dark.PRIMARY_HOVER, text_color="#FFFFFF",
            height=38, corner_radius=Radius.MD,
            command=self._on_close,
        ).pack(side="right")

    def _on_close(self):
        if self._on_close:
            self._on_close()
        self.grab_release()
        self.destroy()
