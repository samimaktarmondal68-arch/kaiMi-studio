# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Global search dialog for KaiMi Studio (Ctrl+K).

Searches projects, research, scripts, storyboards, image prompts, and templates.
Results open directly in the workspace.
"""

import customtkinter as ctk
from tkinter import Canvas

from core.theme import Dark, Fonts, Radius, Spacing
from core.project_manager import ProjectManager
from core.research_storage import ResearchStorage
from core.script_storage import ScriptStorage
from core.storyboard_storage import StoryboardStorage
from core.image_prompt_storage import ImagePromptStorage


class GlobalSearchDialog(ctk.CTkToplevel):

    def __init__(self, master, on_select=None):
        super().__init__(master)
        self.on_select = on_select
        self.pm = ProjectManager()
        self.title("Search")
        self.geometry("640x480")
        self.resizable(False, False)
        self.configure(fg_color=Dark.BG)
        self.grab_set()

        self._results = []
        self._selected_idx = 0

        self._build()
        self.search_entry.focus_set()
        self.bind("<Escape>", lambda e: self.destroy())
        self.after(50, lambda: self.search_entry.focus_set())

    def _build(self):
        search_frame = ctk.CTkFrame(self, fg_color=Dark.SURFACE, corner_radius=Radius.MD, height=56)
        search_frame.pack(fill="x", padx=Spacing.X5, pady=(Spacing.X5, 0))
        search_frame.pack_propagate(False)

        ic = Canvas(search_frame, width=18, height=18, bg=Dark.SURFACE, highlightthickness=0)
        ic.pack(side="left", padx=(Spacing.X4, Spacing.X2))
        ic.create_oval(3, 3, 13, 13, outline=Dark.TEXT_MUTED, width=2)
        ic.create_line(12, 12, 16, 16, fill=Dark.TEXT_MUTED, width=2)

        self.search_entry = ctk.CTkEntry(
            search_frame, placeholder_text="Search projects, research, scripts...",
            fg_color="transparent", border_width=0, text_color=Dark.TEXT,
            font=(Fonts.FAMILY, 16), placeholder_text_color=Dark.TEXT_MUTED,
        )
        self.search_entry.pack(side="left", fill="both", expand=True, padx=Spacing.X2)
        self.search_entry.bind("<KeyRelease>", self._on_search)
        self.search_entry.bind("<Down>", self._on_down)
        self.search_entry.bind("<Up>", self._on_up)
        self.search_entry.bind("<Return>", self._on_select)

        shortcut = ctk.CTkLabel(
            search_frame, text="ESC", font=(Fonts.FAMILY, 10),
            text_color=Dark.TEXT_MUTED, fg_color=Dark.HOVER,
            corner_radius=Radius.SM, padx=6, pady=2,
        )
        shortcut.pack(side="right", padx=Spacing.X3)

        sep = ctk.CTkFrame(self, fg_color=Dark.BORDER, height=1)
        sep.pack(fill="x", padx=Spacing.X5, pady=Spacing.X2)

        self.results_frame = ctk.CTkScrollableFrame(
            self, fg_color="transparent",
            scrollbar_button_color=Dark.BORDER,
            scrollbar_button_hover_color=Dark.TEXT_MUTED,
        )
        self.results_frame.pack(fill="both", expand=True, padx=Spacing.X5, pady=(0, Spacing.X5))

        self._show_recent_projects()

    def _show_recent_projects(self):
        for w in self.results_frame.winfo_children():
            w.destroy()

        projects = self.pm.get_recent_projects(8)
        if not projects:
            ctk.CTkLabel(
                self.results_frame, text="No projects found.",
                font=Fonts.BODY, text_color=Dark.TEXT_MUTED,
            ).pack(pady=Spacing.X8)
            return

        ctk.CTkLabel(
            self.results_frame, text="Recent Projects",
            font=Fonts.SMALL_BOLD, text_color=Dark.TEXT_MUTED, anchor="w",
        ).pack(fill="x", pady=(0, Spacing.X2))

        self._results = []
        for p in projects:
            self._add_result_row(p.get("name", ""), "Project", p)

    def _on_search(self, event=None):
        query = self.search_entry.get().strip()
        for w in self.results_frame.winfo_children():
            w.destroy()

        if not query:
            self._show_recent_projects()
            return

        self._results = []
        self._selected_idx = 0

        projects = self.pm.search_projects(query)
        for p in projects[:5]:
            self._add_result_row(p.get("name", ""), "Project", p)

        for stage_name, storage_cls in [
            ("Research", ResearchStorage),
            ("Script", ScriptStorage),
            ("Storyboard", StoryboardStorage),
            ("Image Prompts", ImagePromptStorage),
        ]:
            storage = storage_cls()
            for p in self.pm.get_projects()[:10]:
                data = storage.load(p.get("name", ""))
                self._search_stage_data(data, stage_name, p.get("name", ""), query)

        if not self._results:
            ctk.CTkLabel(
                self.results_frame, text=f"No results for \"{query}\"",
                font=Fonts.BODY, text_color=Dark.TEXT_MUTED,
            ).pack(pady=Spacing.X8)

    def _search_stage_data(self, data, stage, project_name, query):
        searchable_parts = []
        for v in data.values():
            if isinstance(v, str):
                searchable_parts.append(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        searchable_parts.extend(str(val) for val in item.values() if isinstance(val, str))

        full_text = " ".join(searchable_parts).lower()
        if query.lower() in full_text:
            self._add_result_row(f"{project_name} \u2014 {stage}", stage, {
                "name": project_name,
                "stage": stage,
            })

    def _add_result_row(self, title, category, data):
        row = ctk.CTkFrame(
            self.results_frame, fg_color="transparent",
            height=44, corner_radius=Radius.SM, cursor="hand2",
        )
        row.pack(fill="x", pady=1)
        row.pack_propagate(False)

        inner = ctk.CTkFrame(row, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=Spacing.X3, pady=Spacing.X2)

        icon_bg = ctk.CTkFrame(inner, width=28, height=28, corner_radius=Radius.SM, fg_color=Dark.SURFACE)
        icon_bg.pack(side="left", padx=(0, Spacing.X3))
        icon_bg.pack_propagate(False)
        icon_char = "\U0001F4C1" if category == "Project" else "\U0001F4DD"
        ctk.CTkLabel(icon_bg, text=icon_char, font=(Fonts.FAMILY, 12), fg_color="transparent").pack(expand=True)

        text_frame = ctk.CTkFrame(inner, fg_color="transparent")
        text_frame.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(text_frame, text=title, font=Fonts.SMALL_BOLD, text_color=Dark.TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(text_frame, text=category, font=Fonts.TINY, text_color=Dark.TEXT_MUTED, anchor="w").pack(anchor="w")

        self._results.append((row, data))

        row.bind("<Button-1>", lambda e, d=data: self._select(d))
        for child in [inner, text_frame] + list(inner.winfo_children()):
            child.bind("<Button-1>", lambda e, d=data: self._select(d))

    def _on_down(self, event=None):
        if self._results:
            self._selected_idx = min(self._selected_idx + 1, len(self._results) - 1)
            self._highlight()

    def _on_up(self, event=None):
        if self._results:
            self._selected_idx = max(self._selected_idx - 1, 0)
            self._highlight()

    def _highlight(self):
        for i, (row, _) in enumerate(self._results):
            try:
                if i == self._selected_idx:
                    row.configure(fg_color=Dark.HOVER)
                else:
                    row.configure(fg_color="transparent")
            except Exception:
                pass

    def _on_select(self, event=None):
        if self._results and self._selected_idx < len(self._results):
            _, data = self._results[self._selected_idx]
            self._select(data)

    def _select(self, data):
        if self.on_select:
            self.on_select(data)
        self.destroy()
