"""What's New page for KaiMi Studio.

Design:
    - Dashboard design language
    - Card-based feature entries
    - Consistent typography and spacing
"""

import customtkinter as ctk

from core.theme import Dark, Fonts, Radius, Spacing
from core.version import VERSION, CODENAME


class WhatsNewPage(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color=Dark.BG)
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=Dark.BG,
            scrollbar_button_color=Dark.BORDER,
            scrollbar_button_hover_color=Dark.TEXT_MUTED,
        )
        scroll.pack(fill="both", expand=True)

        ctk.CTkLabel(
            scroll, text="What's New",
            font=Fonts.TITLE, text_color=Dark.TEXT,
        ).pack(anchor="w", padx=Spacing.X12, pady=(Spacing.X8, Spacing.X2))

        ctk.CTkLabel(
            scroll, text=f"v{VERSION} \u2014 {CODENAME}",
            font=Fonts.BODY, text_color=Dark.PRIMARY,
        ).pack(anchor="w", padx=Spacing.X12, pady=(0, Spacing.X6))

        entries = [
            ("\U0001F680", "Multi-Provider AI", "Use Gemini, OpenAI-compatible, or custom providers with automatic failover."),
            ("\U0001F3A8", "Full Pipeline", "Research \u2192 Script \u2192 Storyboard \u2192 Image Prompts with guided workflow."),
            ("\U0001F4BE", "Autosave", "Automatic project saves every 30 seconds. Never lose work."),
            ("\U0001F50D", "Global Search", "Find any project instantly with Ctrl+K."),
            ("\U0001F4E4", "Multi-Format Export", "Export as TXT, Markdown, JSON, ZIP, DOCX, or PDF."),
            ("\u23F0", "Keyboard Shortcuts", "Ctrl+N, Ctrl+S, Ctrl+K, and stage navigation shortcuts."),
            ("\U0001F4C2", "Version History", "Compare and restore previous versions of any stage."),
            ("\U0001F6E0\uFE0F", "Background Tasks", "Non-blocking AI generation with progress updates."),
        ]

        for icon, title, desc in entries:
            card = ctk.CTkFrame(
                scroll, fg_color=Dark.CARD, corner_radius=Radius.LG,
                border_width=1, border_color=Dark.BORDER, height=72,
            )
            card.pack(fill="x", padx=Spacing.X12, pady=(0, Spacing.X3))
            card.pack_propagate(False)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=Spacing.X5, pady=Spacing.X4)

            icon_bg = ctk.CTkFrame(inner, width=36, height=36, corner_radius=Radius.SM, fg_color=Dark.SURFACE)
            icon_bg.pack(side="left", padx=(0, Spacing.X3))
            icon_bg.pack_propagate(False)
            ctk.CTkLabel(icon_bg, text=icon, font=(Fonts.FAMILY, 16), fg_color="transparent").pack(expand=True)

            text_col = ctk.CTkFrame(inner, fg_color="transparent")
            text_col.pack(side="left", fill="both", expand=True)

            ctk.CTkLabel(
                text_col, text=title,
                font=Fonts.CARD_TITLE, text_color=Dark.TEXT,
            ).pack(anchor="w")

            ctk.CTkLabel(
                text_col, text=desc,
                font=Fonts.BODY, text_color=Dark.TEXT_SECONDARY,
            ).pack(anchor="w")
