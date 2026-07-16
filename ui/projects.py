import customtkinter as ctk
from tkinter import messagebox

from core.project_manager import ProjectManager
from ui.dialogs import NewProjectDialog


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

    def refresh(self):
        for widget in self.listing.winfo_children():
            widget.destroy()
        projects = self.manager.get_recent_projects(100)
        if not projects:
            ctk.CTkLabel(self.listing, text="No projects yet. Start with a new idea.", text_color="gray", font=("Segoe UI", 17)).pack(pady=45)
            return
        for project in projects:
            card = ctk.CTkFrame(self.listing, corner_radius=14, fg_color="#2A2A2A")
            card.pack(fill="x", pady=7, padx=4)
            ctk.CTkLabel(card, text=project.get("name", "Untitled"), font=("Segoe UI", 19, "bold")).grid(row=0, column=0, sticky="w", padx=18, pady=(14, 3))
            ctk.CTkLabel(card, text=f"{project.get('topic', 'No topic')}  •  {project.get('language', 'English')}  •  {project.get('style', 'General')}", text_color="#B5B5B5").grid(row=1, column=0, sticky="w", padx=18, pady=(0, 14))
            ctk.CTkLabel(card, text=project.get("status", "Research"), text_color="#61D889").grid(row=0, column=1, padx=16)
            ctk.CTkButton(card, text="Delete", width=75, fg_color="#6E3030", hover_color="#8B3A3A", command=lambda p=project: self.delete(p)).grid(row=1, column=1, padx=16, pady=(0, 12))
            card.grid_columnconfigure(0, weight=1)

    def new_project(self):
        dialog = NewProjectDialog(self)
        dialog.bind("<Destroy>", lambda event: self.after(100, self.refresh), add="+")

    def delete(self, project):
        name = project["name"]
        if messagebox.askyesno("Delete project", f'Delete "{name}" and all its files?'):
            self.manager.delete_project(name)
            self.refresh()
