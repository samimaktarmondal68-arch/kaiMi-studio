import customtkinter as ctk
from tkinter import messagebox
from typing import Callable, Optional

from core.project_manager import ProjectManager


class NewProjectDialog(ctk.CTkToplevel):

    def __init__(self, master, on_project_created: Optional[Callable[[str], None]] = None):
        super().__init__(master)

        self.manager = ProjectManager()
        self.on_project_created = on_project_created

        self.title("New Project")
        self.geometry("560x660")
        self.resizable(False, False)
        self.configure(fg_color="#202020")

        self.grab_set()
        self.focus_set()

        main = ctk.CTkFrame(self, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=22, pady=20)

        title = ctk.CTkLabel(
            main,
            text="Create New Project",
            font=("Segoe UI", 28, "bold")
        )
        title.pack(anchor="w")

        description = ctk.CTkLabel(
            main,
            text="Create a new AI video production project.",
            font=("Segoe UI", 13),
            text_color="#B5B5B5"
        )
        description.pack(anchor="w", pady=(6, 18))

        form_frame = ctk.CTkFrame(main, fg_color="transparent")
        form_frame.pack(fill="both", expand=True)

        info_section = ctk.CTkFrame(
            form_frame,
            fg_color="#2A2A2A",
            corner_radius=16
        )
        info_section.pack(fill="x", pady=(0, 16))

        ctk.CTkLabel(
            info_section,
            text="Project Information",
            font=("Segoe UI", 17, "bold")
        ).pack(anchor="w", padx=18, pady=(18, 10))

        info_content = ctk.CTkFrame(info_section, fg_color="transparent")
        info_content.pack(fill="x", padx=18, pady=(0, 16))

        ctk.CTkLabel(
            info_content,
            text="Project Name",
            font=("Segoe UI", 13, "bold")
        ).pack(anchor="w")

        self.name = ctk.CTkEntry(
            info_content,
            width=380,
            placeholder_text="Project Name",
            height=38
        )
        self.name.pack(fill="x", pady=(6, 14))

        ctk.CTkLabel(
            info_content,
            text="Video Topic",
            font=("Segoe UI", 13, "bold")
        ).pack(anchor="w")

        self.topic = ctk.CTkEntry(
            info_content,
            width=380,
            placeholder_text="Video Topic",
            height=38
        )
        self.topic.pack(fill="x", pady=(6, 0))

        settings_section = ctk.CTkFrame(
            form_frame,
            fg_color="#2A2A2A",
            corner_radius=16
        )
        settings_section.pack(fill="x")

        ctk.CTkLabel(
            settings_section,
            text="Production Settings",
            font=("Segoe UI", 17, "bold")
        ).pack(anchor="w", padx=18, pady=(18, 10))

        settings_content = ctk.CTkFrame(settings_section, fg_color="transparent")
        settings_content.pack(fill="x", padx=18, pady=(0, 16))

        ctk.CTkLabel(
            settings_content,
            text="Language",
            font=("Segoe UI", 13, "bold")
        ).pack(anchor="w")

        self.language = ctk.CTkOptionMenu(
            settings_content,
            values=[
                "English",
                "Hindi",
                "Bengali"
            ],
            width=380,
            height=38
        )
        self.language.pack(fill="x", pady=(6, 14))

        ctk.CTkLabel(
            settings_content,
            text="Style",
            font=("Segoe UI", 13, "bold")
        ).pack(anchor="w")

        self.style = ctk.CTkOptionMenu(
            settings_content,
            values=[
                "Educational",
                "Storytelling",
                "Documentary"
            ],
            width=380,
            height=38
        )
        self.style.pack(fill="x", pady=(6, 0))

        button_frame = ctk.CTkFrame(main, fg_color="transparent")
        button_frame.pack(fill="x", pady=(16, 0))

        self.cancel_button = ctk.CTkButton(
            button_frame,
            text="Cancel",
            width=120,
            height=45,
            fg_color="#3A3A3A",
            hover_color="#4A4A4A",
            command=self.destroy
        )
        self.cancel_button.pack(side="right", padx=(10, 0))

        self.create_button = ctk.CTkButton(
            button_frame,
            text="Create Project",
            width=250,
            height=45,
            command=self.create_project
        )
        self.create_button.pack(side="right")

        self._ensure_content_fits()

    def _ensure_content_fits(self):
        self.update_idletasks()
        required_height = self.winfo_reqheight() + 12
        current_height = self.winfo_height()
        if required_height > current_height:
            self.geometry(f"560x{required_height}")

    # =====================================
    # Create Project
    # =====================================

    def create_project(self):

        name = self.name.get().strip()
        topic = self.topic.get().strip()
        language = self.language.get()
        style = self.style.get()

        if name == "":
            messagebox.showwarning(
                "Missing Information",
                "Please enter a project name."
            )
            return

        if topic == "":
            messagebox.showwarning(
                "Missing Information",
                "Please enter a video topic."
            )
            return

        try:

            project_path = self.manager.create_project(
                name=name,
                topic=topic,
                language=language,
                style=style
            )

            messagebox.showinfo(
                "Success",
                f"Project created successfully!\n\n{project_path}"
            )

            self.destroy()

            if self.on_project_created is not None:
                self.on_project_created(name)

        except Exception as e:

            messagebox.showerror(
                "Error",
                str(e)
            )