import customtkinter as ctk

from core.project_manager import ProjectManager


class WorkspacePage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="#202020")
        self.manager = ProjectManager()
        self.selected_name = None
        self.build()

    def build(self):
        ctk.CTkLabel(self, text="AI Workspace", font=("Segoe UI", 30, "bold")).pack(anchor="w", padx=44, pady=(38, 6))
        ctk.CTkLabel(self, text="Organize the creative brief and production notes for a project.", text_color="gray").pack(anchor="w", padx=44, pady=(0, 20))
        toolbar = ctk.CTkFrame(self, fg_color="transparent")
        toolbar.pack(fill="x", padx=44, pady=(0, 14))
        names = [p["name"] for p in self.manager.get_projects()] or ["No projects available"]
        self.project_menu = ctk.CTkOptionMenu(toolbar, values=names, command=self.load_project, width=320)
        self.project_menu.pack(side="left")
        ctk.CTkButton(toolbar, text="Save notes", command=self.save).pack(side="right")
        self.editor = ctk.CTkTextbox(self, font=("Consolas", 14), corner_radius=14)
        self.editor.pack(fill="both", expand=True, padx=44, pady=(0, 38))
        self.load_project(names[0])

    def load_project(self, name):
        self.selected_name = name if name != "No projects available" else None
        self.editor.delete("1.0", "end")
        if not self.selected_name:
            self.editor.insert("1.0", "Create a project to begin drafting research, scripts, and prompts.")
            return
        path = self.manager.PROJECTS_DIR / self.selected_name / "script.md"
        self.editor.insert("1.0", path.read_text(encoding="utf-8") if path.exists() else "")

    def save(self):
        if self.selected_name:
            path = self.manager.PROJECTS_DIR / self.selected_name / "script.md"
            path.write_text(self.editor.get("1.0", "end-1c"), encoding="utf-8")
