# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Export page for KaiMi Studio.

Multi-format export: TXT, Markdown, DOCX, PDF, JSON, ZIP.
"""

import customtkinter as ctk

from core.theme import Dark, Fonts, Radius, Spacing
from core.project_manager import ProjectManager
from core.export_service import ExportService
from core.notifications import NotificationService


class ExportPage(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color=Dark.BG)
        self.manager = ProjectManager()
        self.export_service = ExportService(self.manager)
        self._selected_project = None
        self._selected_format = "zip"
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=Spacing.X10, pady=(Spacing.X5, Spacing.X2))

        ctk.CTkLabel(
            header, text="Export",
            font=Fonts.TITLE, text_color=Dark.TEXT,
        ).pack(side="left")

        ctk.CTkLabel(
            header, text="Export projects in multiple formats.",
            font=Fonts.BODY, text_color=Dark.TEXT_MUTED,
        ).pack(side="left", padx=Spacing.X5)

        scroll = ctk.CTkScrollableFrame(
            self, fg_color=Dark.BG,
            scrollbar_button_color=Dark.BORDER,
            scrollbar_button_hover_color=Dark.TEXT_MUTED,
        )
        scroll.pack(fill="both", expand=True, padx=Spacing.X10, pady=(0, Spacing.X8))

        projects = self.manager.get_projects()
        if not projects:
            empty = ctk.CTkFrame(scroll, fg_color="transparent")
            empty.pack(expand=True, pady=80)
            ctk.CTkLabel(
                empty, text="No projects to export.",
                font=Fonts.BODY, text_color=Dark.TEXT_MUTED,
            ).pack()
            return

        format_card = ctk.CTkFrame(
            scroll, fg_color=Dark.CARD, corner_radius=Radius.LG,
            border_width=1, border_color=Dark.BORDER,
        )
        format_card.pack(fill="x", pady=(0, Spacing.X4))

        ctk.CTkLabel(
            format_card, text="Export Format",
            font=Fonts.CARD_TITLE, text_color=Dark.TEXT,
        ).pack(anchor="w", padx=Spacing.X5, pady=(Spacing.X4, Spacing.X3))

        fmt_row = ctk.CTkFrame(format_card, fg_color="transparent")
        fmt_row.pack(fill="x", padx=Spacing.X5, pady=(0, Spacing.X4))

        self._fmt_buttons = {}
        for fmt, label in [("zip", "ZIP Archive"), ("txt", "Plain Text"), ("markdown", "Markdown"), ("json", "JSON"), ("docx", "DOCX"), ("pdf", "PDF")]:
            btn = ctk.CTkButton(
                fmt_row, text=label, height=36,
                fg_color=Dark.SURFACE if fmt != self._selected_format else Dark.PRIMARY,
                hover_color=Dark.HOVER,
                text_color=Dark.TEXT if fmt == self._selected_format else Dark.TEXT_SECONDARY,
                font=Fonts.BUTTON, corner_radius=Radius.SM,
                command=lambda f=fmt: self._select_format(f),
            )
            btn.pack(side="left", padx=(0, Spacing.X2))
            self._fmt_buttons[fmt] = btn

        for project in projects:
            self._build_project_row(scroll, project)

    def _build_project_row(self, parent, project):
        name = project.get("name", "Untitled")
        stage = project.get("status", "Research")

        row = ctk.CTkFrame(
            parent, fg_color=Dark.CARD, corner_radius=Radius.MD,
            border_width=1, border_color=Dark.BORDER, height=64,
        )
        row.pack(fill="x", pady=Spacing.X1)
        row.pack_propagate(False)

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=Spacing.X4, pady=Spacing.X3)

        icon_bg = ctk.CTkFrame(inner, width=28, height=28, corner_radius=Radius.SM, fg_color=Dark.PRIMARY)
        icon_bg.pack(side="left", padx=(0, Spacing.X3))
        icon_bg.pack_propagate(False)
        ctk.CTkLabel(icon_bg, text="\U0001F4E5", font=("Segoe UI", 12), fg_color="transparent").pack(expand=True)

        text_frame = ctk.CTkFrame(inner, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(text_frame, text=name, font=(Fonts.FAMILY, 13, "bold"), text_color=Dark.TEXT).pack(anchor="w")
        ctk.CTkLabel(text_frame, text=stage, font=Fonts.TINY, text_color=Dark.TEXT_MUTED).pack(anchor="w")

        ctk.CTkButton(
            inner, text="Export", width=100, height=32,
            fg_color=Dark.PRIMARY, hover_color=Dark.PRIMARY_HOVER,
            text_color=Dark.TEXT, font=Fonts.BUTTON,
            corner_radius=Radius.SM,
            command=lambda p=project: self._do_export(p),
        ).pack(side="right")

    def _select_format(self, fmt):
        self._selected_format = fmt
        for f, btn in self._fmt_buttons.items():
            if f == fmt:
                btn.configure(fg_color=Dark.PRIMARY, text_color=Dark.TEXT)
            else:
                btn.configure(fg_color=Dark.SURFACE, text_color=Dark.TEXT_SECONDARY)

    def _do_export(self, project):
        name = project.get("name", "")
        try:
            result = self.export_service.export_project(project, fmt=self._selected_format)
            NotificationService.get().success(f"Exported {name} as {self._selected_format.upper()}")
        except Exception as e:
            NotificationService.get().error(f"Export failed: {e}")
