"""About page for KaiMi Studio.

Design:
    - Dashboard design language
    - Professional branding with logo, version, copyright
    - Card-based layout with details
"""

import customtkinter as ctk

from core.theme import Dark, Fonts, Radius, Spacing
from core.version import (
    APP_NAME, VERSION, AUTHOR, YEAR, BUILD, CODENAME,
    COPYRIGHT, APP_DESCRIPTION,
)


class AboutPage(ctk.CTkFrame):

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
            scroll, text="About",
            font=Fonts.TITLE, text_color=Dark.TEXT,
        ).pack(anchor="w", padx=Spacing.X12, pady=(Spacing.X8, Spacing.X5))

        # Logo card
        logo_card = ctk.CTkFrame(
            scroll, fg_color=Dark.CARD, corner_radius=Radius.LG,
            border_width=1, border_color=Dark.BORDER, height=120,
        )
        logo_card.pack(fill="x", padx=Spacing.X12, pady=(0, Spacing.X4))
        logo_card.pack_propagate(False)

        logo_inner = ctk.CTkFrame(logo_card, fg_color="transparent")
        logo_inner.pack(fill="both", expand=True, padx=Spacing.X6, pady=Spacing.X5)

        ctk.CTkLabel(
            logo_inner, text=APP_NAME,
            font=Fonts.HEADING, text_color=Dark.PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            logo_inner, text=f"v{VERSION} ({BUILD}) \u2014 {CODENAME}",
            font=Fonts.BODY, text_color=Dark.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.X1, 0))

        ctk.CTkLabel(
            logo_inner, text=APP_DESCRIPTION,
            font=Fonts.SMALL, text_color=Dark.TEXT_MUTED,
        ).pack(anchor="w", pady=(Spacing.X2, 0))

        # Details card
        details_card = ctk.CTkFrame(
            scroll, fg_color=Dark.CARD, corner_radius=Radius.LG,
            border_width=1, border_color=Dark.BORDER,
        )
        details_card.pack(fill="x", padx=Spacing.X12, pady=(0, Spacing.X4))

        details = [
            ("Version", f"v{VERSION}"),
            ("Build", BUILD),
            ("Codename", CODENAME),
            ("Author", AUTHOR),
            ("Copyright", COPYRIGHT),
            ("Python", self._python_version()),
        ]

        for label, value in details:
            row = ctk.CTkFrame(details_card, fg_color="transparent", height=38)
            row.pack(fill="x", padx=Spacing.X6, pady=Spacing.X1)
            row.pack_propagate(False)

            ctk.CTkLabel(
                row, text=label,
                font=Fonts.SMALL, text_color=Dark.TEXT_MUTED,
                width=120, anchor="w",
            ).pack(side="left")

            ctk.CTkLabel(
                row, text=value,
                font=Fonts.BODY_BOLD, text_color=Dark.TEXT,
            ).pack(side="left")

        ctk.CTkFrame(details_card, fg_color="transparent").pack(pady=Spacing.X2)

    @staticmethod
    def _python_version() -> str:
        import sys
        return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
