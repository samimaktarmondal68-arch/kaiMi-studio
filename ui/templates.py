# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Templates page for KaiMi Studio.

Design:
    - Dashboard design language
    - Empty state with icon
    - Consistent typography and spacing
"""

import customtkinter as ctk

from core.theme import Dark, Fonts, Radius, Spacing


class TemplatesPage(ctk.CTkFrame):

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
            scroll, text="Templates",
            font=Fonts.TITLE, text_color=Dark.TEXT,
        ).pack(anchor="w", padx=Spacing.X12, pady=(Spacing.X8, Spacing.X2))

        ctk.CTkLabel(
            scroll, text="Reusable project templates for common video formats.",
            font=Fonts.BODY, text_color=Dark.TEXT_SECONDARY,
        ).pack(anchor="w", padx=Spacing.X12, pady=(0, Spacing.X6))

        # Empty state card
        empty_card = ctk.CTkFrame(
            scroll, fg_color=Dark.CARD, corner_radius=Radius.LG,
            border_width=1, border_color=Dark.BORDER,
        )
        empty_card.pack(fill="x", padx=Spacing.X12)

        inner = ctk.CTkFrame(empty_card, fg_color="transparent")
        inner.pack(expand=True, pady=Spacing.X12)

        icon_bg = ctk.CTkFrame(inner, width=56, height=56, corner_radius=Radius.LG, fg_color=Dark.SURFACE)
        icon_bg.pack()
        icon_bg.pack_propagate(False)
        ctk.CTkLabel(icon_bg, text="\U0001F4F1", font=("Segoe UI", 28), fg_color="transparent").pack(expand=True)

        ctk.CTkLabel(
            inner, text="No Templates Yet",
            font=Fonts.SECTION, text_color=Dark.TEXT,
        ).pack(pady=(Spacing.X4, Spacing.X2))

        ctk.CTkLabel(
            inner, text="Templates will let you quickly start new projects\nwith pre-configured settings.",
            font=Fonts.BODY, text_color=Dark.TEXT_MUTED,
            justify="center",
        ).pack()
