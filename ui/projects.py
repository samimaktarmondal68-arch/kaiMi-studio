import customtkinter as ctk
from tkinter import messagebox

from core.project_manager import ProjectManager
from ui.dialogs import NewProjectDialog
from ui.workspace import WorkspacePage

STAGE_COLORS: dict[str, str] = {
    "Research":      "#3B82F6",
    "Script":        "#8B5CF6",
    "Storyboard":    "#F97316",
    "Image Prompts": "#06B6D4",
    "Images":        "#EAB308",
    "Voice Over":    "#EC4899",
    "Video Editing": "#EF4444",
    "Thumbnail":     "#14B8A6",
    "Export":        "#22C55E",
}

CARD_BASE = "#2A2A2A"
CARD_HOVER = "#333333"


class ProjectsPage(ctk.CTkFrame):
    """A lightweight project library with project metadata and management actions."""

    def __init__(self, master):
        super().__init__(master, fg_color="#202020")
        self.manager = ProjectManager()
        self.build()

    def build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=44, pady=(38, 22))
        ctk.CTkLabel(header, text="Video Projects", font=("Segoe UI", 30, "bold")).pack(side="left")
        ctk.CTkButton(header, text="+ New Project", command=self.new_project).pack(side="right")

        self.listing = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.listing.pack(fill="both", expand=True, padx=40, pady=(0, 35))
        self.refresh()

    # ==========================================================
    # REFRESH
    # ==========================================================

    def refresh(self):
        for widget in self.listing.winfo_children():
            widget.destroy()

        projects = self.manager.get_recent_projects(100)

        if not projects:
            empty_frame = ctk.CTkFrame(self.listing, fg_color="transparent")
            empty_frame.pack(expand=True, pady=80)

            ctk.CTkLabel(
                empty_frame,
                text="📁",
                font=("Segoe UI", 56),
            ).pack()

            ctk.CTkLabel(
                empty_frame,
                text="No Projects Yet",
                font=("Segoe UI", 24, "bold"),
            ).pack(pady=(16, 6))

            ctk.CTkLabel(
                empty_frame,
                text="Create your first AI video project.",
                font=("Segoe UI", 15),
                text_color="#9CA3AF",
            ).pack()
            return

        for project in projects:
            self._build_card(project)

    # ==========================================================
    # BUILD CARD
    # ==========================================================

    def _build_card(self, project: dict) -> None:
        name = project.get("name", "Untitled")
        topic = project.get("topic", "No topic")
        language = project.get("language", "English")
        style = project.get("style", "General")
        stage = project.get("status", "Research")
        badge_color = STAGE_COLORS.get(stage, "#3B82F6")

        card = ctk.CTkFrame(
            self.listing,
            corner_radius=14,
            fg_color=CARD_BASE,
        )
        card.pack(fill="x", pady=7, padx=4)

        # --- hover effect ---
        card._orig_color = CARD_BASE
        card.bind("<Enter>", lambda e, c=card: c.configure(fg_color=CARD_HOVER))
        card.bind("<Leave>", lambda e, c=card: c.configure(fg_color=c._orig_color))

        # --- left column: name + topic ---
        left = ctk.CTkFrame(card, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True, padx=18, pady=(14, 14))

        ctk.CTkLabel(
            left,
            text=name,
            font=("Segoe UI", 19, "bold"),
        ).pack(anchor="w")

        ctk.CTkLabel(
            left,
            text=topic,
            font=("Segoe UI", 13),
            text_color="#B5B5B5",
        ).pack(anchor="w", pady=(4, 0))

        modified = self.manager.get_last_modified(name)
        ctk.CTkLabel(
            left,
            text=f"Last modified: {modified}",
            font=("Segoe UI", 12),
            text_color="#6B7280",
        ).pack(anchor="w", pady=(6, 0))

        # --- right column: meta + stage badge ---
        right = ctk.CTkFrame(card, fg_color="transparent")
        right.pack(side="right", padx=18, pady=(14, 14))

        meta = ctk.CTkFrame(right, fg_color="transparent")
        meta.pack(side="left", padx=(0, 14))

        ctk.CTkLabel(
            meta,
            text=f"{language}  •  {style}",
            font=("Segoe UI", 13),
            text_color="#9CA3AF",
        ).pack()

        badge = ctk.CTkFrame(
            right,
            fg_color=badge_color,
            corner_radius=10,
        )
        badge.pack(side="left")

        ctk.CTkLabel(
            badge,
            text=stage,
            font=("Segoe UI", 13, "bold"),
            text_color="#FFFFFF",
        ).pack(padx=14, pady=5)

        # --- delete button ---
        ctk.CTkButton(
            card,
            text="Delete",
            width=75,
            fg_color="#6E3030",
            hover_color="#8B3A3A",
            command=lambda p=project: self.delete(p),
        ).pack(side="right", padx=(0, 18), pady=(14, 14))

        # --- click to open workspace (after all children exist) ---
        card.bind("<Button-1>", lambda e, n=name: self._open_workspace(n))
        for child in (left, right, meta, badge):
            child.bind("<Button-1>", lambda e, n=name: self._open_workspace(n))
            for grandchild in child.winfo_children():
                grandchild.bind("<Button-1>", lambda e, n=name: self._open_workspace(n))

    # ==========================================================
    # NEW PROJECT
    # ==========================================================

    def _handle_project_created(self, project_name: str) -> None:
        self.refresh()
        self._open_workspace(project_name)

    def new_project(self):
        NewProjectDialog(self, on_project_created=self._handle_project_created)

    # ==========================================================
    # DELETE
    # ==========================================================

    def delete(self, project):
        name = project["name"]
        if messagebox.askyesno("Delete project", f'Delete "{name}" and all its files?'):
            self.manager.delete_project(name)
            self.refresh()

    # ==========================================================
    # OPEN WORKSPACE
    # ==========================================================

    def _open_workspace(self, project_name: str) -> None:
        self.winfo_toplevel()._show_page(WorkspacePage, "AI Workspace", initial_project_name=project_name)
