import customtkinter as ctk
from core.project_manager import ProjectManager


class ExportPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="#202020")
        ctk.CTkLabel(self, text="Export", font=("Segoe UI", 30, "bold")).pack(anchor="w", padx=44, pady=(38, 8))
        ctk.CTkLabel(self, text="Completed videos and deliverables will be available here.", text_color="gray").pack(anchor="w", padx=44)
        box = ctk.CTkFrame(self, corner_radius=16)
        box.pack(fill="both", expand=True, padx=44, pady=28)
        manager = ProjectManager()
        exports = []
        for project in manager.get_projects():
            folder = manager.PROJECTS_DIR / project["name"] / "exports"
            exports.extend((project["name"], item.name) for item in folder.iterdir() if folder.exists() and item.is_file())
        if exports:
            for project, filename in exports:
                ctk.CTkLabel(box, text=f"{project}  —  {filename}", font=("Segoe UI", 16)).pack(anchor="w", padx=22, pady=12)
        else:
            ctk.CTkLabel(box, text="Nothing exported yet.", text_color="gray", font=("Segoe UI", 18)).pack(expand=True)
