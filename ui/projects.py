"""Projects page for KaiMi Studio.

Features: search, sort, filter, duplicate, rename, archive, favorite.
"""

import customtkinter as ctk
from tkinter import messagebox

from core.theme import Dark, Fonts, Radius, Spacing
from core.project_manager import ProjectManager
from core.notifications import NotificationService
from ui.dialogs import NewProjectDialog
from ui.workspace import WorkspacePage

STAGE_COLORS = {
    "Research": Dark.SECONDARY,
    "Script": "#8B5CF6",
    "Storyboard": Dark.WARNING,
    "Image Prompts": "#06B6D4",
    "Export": Dark.SUCCESS,
}

SORT_OPTIONS = ["last_modified", "name", "status", "created"]
FILTER_OPTIONS = ["All", "Research", "Script", "Storyboard", "Image Prompts", "Export"]


class ProjectsPage(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color=Dark.BG)
        self.manager = ProjectManager()
        self._search_query = ""
        self._sort_by = "last_modified"
        self._sort_reverse = True
        self._filter_status = "All"
        self.build()

    def build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=Spacing.X10, pady=(Spacing.X5, Spacing.X2))

        ctk.CTkLabel(
            header, text="Video Projects",
            font=Fonts.TITLE, text_color=Dark.TEXT,
        ).pack(side="left")

        ctk.CTkButton(
            header, text="+ New Project", width=150, height=38,
            fg_color=Dark.PRIMARY, hover_color=Dark.PRIMARY_HOVER,
            text_color=Dark.TEXT, font=Fonts.BUTTON,
            corner_radius=Radius.SM, command=self.new_project,
        ).pack(side="right")

        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=Spacing.X10, pady=(0, Spacing.X2))

        self.search_entry = ctk.CTkEntry(
            toolbar, placeholder_text="Search projects...",
            width=300, height=36,
            fg_color=Dark.INPUT_BG, border_color=Dark.INPUT_BORDER,
            text_color=Dark.TEXT, font=Fonts.INPUT,
            corner_radius=Radius.SM,
        )
        self.search_entry.pack(side="left")
        self.search_entry.bind("<KeyRelease>", lambda e: self._apply_filters())

        self.sort_var = ctk.StringVar(value="Last Modified")
        ctk.CTkOptionMenu(
            toolbar, variable=self.sort_var,
            values=["Last Modified", "Name", "Status", "Created"],
            command=self._on_sort_change,
            fg_color=Dark.INPUT_BG, button_color=Dark.PRIMARY,
            button_hover_color=Dark.PRIMARY_HOVER,
            dropdown_fg_color=Dark.CARD, dropdown_hover_color=Dark.HOVER,
            text_color=Dark.TEXT, font=Fonts.BODY, width=150,
        ).pack(side="left", padx=Spacing.X3)

        self.filter_var = ctk.StringVar(value="All")
        ctk.CTkOptionMenu(
            toolbar, variable=self.filter_var,
            values=FILTER_OPTIONS,
            command=self._on_filter_change,
            fg_color=Dark.INPUT_BG, button_color=Dark.PRIMARY,
            button_hover_color=Dark.PRIMARY_HOVER,
            dropdown_fg_color=Dark.CARD, dropdown_hover_color=Dark.HOVER,
            text_color=Dark.TEXT, font=Fonts.BODY, width=140,
        ).pack(side="left", padx=Spacing.X3)

        self.count_label = ctk.CTkLabel(
            toolbar, text="", font=Fonts.SMALL, text_color=Dark.TEXT_MUTED,
        )
        self.count_label.pack(side="right")

        self.listing = ctk.CTkScrollableFrame(
            self, fg_color=Dark.BG,
            scrollbar_button_color=Dark.BORDER,
            scrollbar_button_hover_color=Dark.TEXT_MUTED,
        )
        self.listing.pack(fill="both", expand=True, padx=Spacing.X10, pady=(0, Spacing.X8))
        self.refresh()

    def refresh(self):
        for widget in self.listing.winfo_children():
            widget.destroy()

        projects = self.manager.search_projects(self._search_query)
        projects = self.manager.filter_projects(projects, self._filter_status)
        projects = self.manager.sort_projects(projects, self._sort_by, self._sort_reverse)

        favorites = [p for p in projects if p.get("favorite")]
        regular = [p for p in projects if not p.get("favorite")]
        display = favorites + regular

        self.count_label.configure(text=f"{len(display)} project{'s' if len(display) != 1 else ''}")

        if not display:
            empty = ctk.CTkFrame(self.listing, fg_color="transparent")
            empty.pack(expand=True, pady=80)
            icon_bg = ctk.CTkFrame(empty, width=56, height=56, corner_radius=Radius.LG, fg_color=Dark.SURFACE)
            icon_bg.pack()
            icon_bg.pack_propagate(False)
            ctk.CTkLabel(icon_bg, text="\U0001F4C1", font=("Segoe UI", 28), fg_color="transparent").pack(expand=True)
            ctk.CTkLabel(empty, text="No Projects Found", font=Fonts.SECTION, text_color=Dark.TEXT).pack(pady=(Spacing.X4, Spacing.X2))
            ctk.CTkLabel(empty, text="Create your first AI video project.", font=Fonts.BODY, text_color=Dark.TEXT_MUTED).pack()
            return

        for project in display:
            self._build_card(project)

    def _build_card(self, project):
        name = project.get("name", "Untitled")
        topic = project.get("topic", "No topic")
        language = project.get("language", "English")
        style = project.get("style", "General")
        stage = project.get("status", "Research")
        is_fav = project.get("favorite", False)
        badge_color = STAGE_COLORS.get(stage, Dark.PRIMARY)

        card = ctk.CTkFrame(
            self.listing, fg_color=Dark.CARD, corner_radius=Radius.LG,
            border_width=1, border_color=Dark.BORDER, height=80,
        )
        card.pack(fill="x", pady=Spacing.X2, padx=0)
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=Spacing.X5, pady=Spacing.X4)

        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)

        icon_bg = ctk.CTkFrame(left, width=32, height=32, corner_radius=Radius.SM, fg_color=badge_color)
        icon_bg.pack(side="left", padx=(0, Spacing.X3))
        icon_bg.pack_propagate(False)
        ctk.CTkLabel(icon_bg, text=name[0].upper(), font=(Fonts.FAMILY, 14, "bold"), text_color=Dark.TEXT).pack(expand=True)

        text_col = ctk.CTkFrame(left, fg_color="transparent")
        text_col.pack(side="left", fill="both", expand=True)

        name_label = ctk.CTkLabel(text_col, text=name, font=(Fonts.FAMILY, 14, "bold"), text_color=Dark.TEXT)
        name_label.pack(anchor="w")

        meta_parts = [topic]
        if language and style:
            meta_parts.append(f"{language}  \u2022  {style}")
        meta_text = "  \u2022  ".join(meta_parts)
        ctk.CTkLabel(text_col, text=meta_text, font=Fonts.TINY, text_color=Dark.TEXT_MUTED).pack(anchor="w")

        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right")

        if is_fav:
            fav_btn = ctk.CTkButton(
                right, text="\u2605", width=28, height=28,
                fg_color="transparent", text_color="#FFD700",
                font=(Fonts.FAMILY, 16), hover_color=Dark.HOVER,
                command=lambda n=name: self._toggle_favorite(n),
            )
            fav_btn.pack(side="left", padx=(0, Spacing.X1))
        else:
            fav_btn = ctk.CTkButton(
                right, text="\u2606", width=28, height=28,
                fg_color="transparent", text_color=Dark.TEXT_MUTED,
                font=(Fonts.FAMILY, 16), hover_color=Dark.HOVER,
                command=lambda n=name: self._toggle_favorite(n),
            )
            fav_btn.pack(side="left", padx=(0, Spacing.X1))

        pill = ctk.CTkFrame(right, fg_color=badge_color, corner_radius=Radius.FULL)
        pill.pack(side="left", padx=(0, Spacing.X3))
        ctk.CTkLabel(pill, text=stage, font=(Fonts.FAMILY, 10, "bold"), text_color=Dark.TEXT, padx=10, pady=4).pack()

        menu_btn = ctk.CTkButton(
            right, text="\u22EE", width=28, height=28,
            fg_color="transparent", hover_color=Dark.HOVER,
            text_color=Dark.TEXT_MUTED, font=(Fonts.FAMILY, 16),
            corner_radius=Radius.SM,
            command=lambda p=project, n=name: self._show_context_menu(p, n),
        )
        menu_btn.pack(side="right")

        card._base_bg = Dark.CARD
        card._hover_bg = Dark.HOVER

        def _enter(e):
            card.configure(fg_color=card._hover_bg, border_color=Dark.PRIMARY)
            name_label.configure(text_color=Dark.PRIMARY)

        def _leave(e):
            card.configure(fg_color=card._base_bg, border_color=Dark.BORDER)
            name_label.configure(text_color=Dark.TEXT)

        card.bind("<Enter>", _enter)
        card.bind("<Leave>", _leave)
        for w in [inner, left, text_col, right]:
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)
            for c in w.winfo_children():
                c.bind("<Enter>", _enter)
                c.bind("<Leave>", _leave)

        card.bind("<Button-1>", lambda e, n=name: self._open_workspace(n))
        for w in [inner, left, text_col]:
            w.bind("<Button-1>", lambda e, n=name: self._open_workspace(n))
            for c in w.winfo_children():
                c.bind("<Button-1>", lambda e, n=name: self._open_workspace(n))

    def _show_context_menu(self, project, name):
        menu = ctk.CTkToplevel(self)
        menu.title("")
        menu.geometry("200x220")
        menu.resizable(False, False)
        menu.configure(fg_color=Dark.CARD)
        menu.grab_set()
        menu.overrideredirect(True)

        try:
            x = self.winfo_pointerx()
            y = self.winfo_pointery()
            menu.geometry(f"+{x}+{y}")
        except Exception:
            pass

        items = [
            ("Open", lambda: self._open_and_close(menu, name)),
            ("Rename", lambda: self._rename_and_close(menu, name)),
            ("Duplicate", lambda: self._duplicate_and_close(menu, name)),
            ("Archive", lambda: self._archive_and_close(menu, name)),
            ("Delete", lambda: self._delete_and_close(menu, name, project)),
        ]

        for label, cmd in items:
            color = Dark.ERROR if label == "Delete" else Dark.TEXT
            ctk.CTkButton(
                menu, text=label, height=36, fg_color="transparent",
                hover_color=Dark.HOVER, text_color=color, font=Fonts.BODY,
                anchor="w", corner_radius=0, command=cmd,
            ).pack(fill="x", padx=Spacing.X2, pady=1)

    def _open_and_close(self, menu, name):
        menu.destroy()
        self._open_workspace(name)

    def _rename_and_close(self, menu, name):
        menu.destroy()
        self._rename_project(name)

    def _duplicate_and_close(self, menu, name):
        menu.destroy()
        self._duplicate_project(name)

    def _archive_and_close(self, menu, name):
        menu.destroy()
        self._archive_project(name)

    def _delete_and_close(self, menu, name, project):
        menu.destroy()
        self._delete_project(project)

    def _rename_project(self, name):
        dialog = ctk.CTkInputDialog(text="New name:", title="Rename Project")
        new_name = dialog.get_input()
        if new_name and new_name.strip() and new_name.strip() != name:
            try:
                self.manager.rename_project(name, new_name.strip())
                NotificationService.get().success(f"Renamed to {new_name.strip()}")
                self.refresh()
            except Exception as e:
                NotificationService.get().error(str(e))

    def _duplicate_project(self, name):
        dialog = ctk.CTkInputDialog(text="Duplicate name:", title="Duplicate Project")
        new_name = dialog.get_input()
        if new_name and new_name.strip():
            try:
                self.manager.duplicate_project(name, new_name.strip())
                NotificationService.get().success(f"Duplicated as {new_name.strip()}")
                self.refresh()
            except Exception as e:
                NotificationService.get().error(str(e))

    def _archive_project(self, name):
        self.manager.archive_project(name)
        NotificationService.get().info(f"Archived {name}")
        self.refresh()

    def _toggle_favorite(self, name):
        self.manager.toggle_favorite(name)
        self.refresh()

    def _delete_project(self, project):
        name = project.get("name", "")
        if messagebox.askyesno("Delete project", f'Delete "{name}" and all its files?'):
            self.manager.delete_project(name)
            NotificationService.get().info(f"Deleted {name}")
            self.refresh()

    def _on_sort_change(self, value):
        sort_map = {"Last Modified": "last_modified", "Name": "name", "Status": "status", "Created": "created"}
        self._sort_by = sort_map.get(value, "last_modified")
        self.refresh()

    def _on_filter_change(self, value):
        self._filter_status = value
        self.refresh()

    def _apply_filters(self):
        self._search_query = self.search_entry.get().strip()
        self.refresh()

    def _handle_project_created(self, project_name):
        self.refresh()
        self._open_workspace(project_name)

    def new_project(self):
        NewProjectDialog(self, on_project_created=self._handle_project_created)

    def _open_workspace(self, project_name):
        self.winfo_toplevel()._show_page(WorkspacePage, "Workflow", initial_project_name=project_name)
