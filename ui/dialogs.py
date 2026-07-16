import customtkinter as ctk
from tkinter import messagebox

from core.project_manager import ProjectManager


class NewProjectDialog(ctk.CTkToplevel):

    def __init__(self, master):
        super().__init__(master)

        self.manager = ProjectManager()

        self.title("New Project")
        self.geometry("520x560")
        self.resizable(False, False)

        self.grab_set()
        self.focus()

        # -----------------------------
        # Title
        # -----------------------------

        title = ctk.CTkLabel(
            self,
            text="Create New Project",
            font=("Segoe UI", 28, "bold")
        )

        title.pack(pady=(25, 20))

        # -----------------------------
        # Project Name
        # -----------------------------

        self.name = ctk.CTkEntry(
            self,
            width=380,
            placeholder_text="Project Name"
        )

        self.name.pack(pady=10)

        # -----------------------------
        # Topic
        # -----------------------------

        self.topic = ctk.CTkEntry(
            self,
            width=380,
            placeholder_text="Video Topic"
        )

        self.topic.pack(pady=10)

        # -----------------------------
        # Language
        # -----------------------------

        self.language = ctk.CTkOptionMenu(
            self,
            values=[
                "English",
                "Hindi",
                "Bengali"
            ],
            width=380
        )

        self.language.pack(pady=10)

        # -----------------------------
        # Style
        # -----------------------------

        self.style = ctk.CTkOptionMenu(
            self,
            values=[
                "Educational",
                "Storytelling",
                "Documentary"
            ],
            width=380
        )

        self.style.pack(pady=10)

        # -----------------------------
        # Create Button
        # -----------------------------

        self.create_button = ctk.CTkButton(
            self,
            text="Create Project",
            width=250,
            height=45,
            command=self.create_project
        )

        self.create_button.pack(pady=35)

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

        except Exception as e:

            messagebox.showerror(
                "Error",
                str(e)
            )