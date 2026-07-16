import customtkinter as ctk
from core.project_manager import ProjectManager


class AssetsPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="#202020")
        ctk.CTkLabel(self, text="Assets", font=("Segoe UI", 30, "bold")).pack(anchor="w", padx=44, pady=(38, 8))
        ctk.CTkLabel(self, text="Images and audio generated or added to each project.", text_color="gray").pack(anchor="w", padx=44, pady=(0, 20))
        content = ctk.CTkScrollableFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=40, pady=(0, 35))
        manager = ProjectManager()
        count = 0
        for project in manager.get_projects():
            for category in ("images", "audio"):
                folder = manager.PROJECTS_DIR / project["name"] / category
                for asset in folder.iterdir() if folder.exists() else []:
                    ctk.CTkLabel(content, text=f"{project['name']}  /  {category}  /  {asset.name}", anchor="w").pack(fill="x", padx=12, pady=8)
                    count += 1
        if not count:
            ctk.CTkLabel(content, text="No assets yet. Generated images and voice files will appear here.", text_color="gray").pack(pady=48)
