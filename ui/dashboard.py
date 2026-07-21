import customtkinter as ctk
from ui.components.stat_card import StatCard
from ui.dialogs import NewProjectDialog
from ui.workspace import WorkspacePage
from core.project_manager import ProjectManager
from core.version import VERSION


class Dashboard(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master)

        self.pm = ProjectManager()

        self.build()

    # ==========================================================
    # BUILD
    # ==========================================================

    def build(self):

        self.configure(fg_color="#202020")

        # ------------------------------------------------------
        # Header
        # ------------------------------------------------------

        header = ctk.CTkFrame(
            self,
            fg_color="#181818",
            height=80
        )

        header.pack(fill="x")
        header.pack_propagate(False)

        ctk.CTkLabel(
            header,
            text="KaiMi Studio",
            font=("Segoe UI", 24, "bold")
        ).pack(side="left", padx=25)

        ctk.CTkLabel(
            header,
            text="🟢 AI ONLINE",
            text_color="#4CAF50",
            font=("Segoe UI", 16, "bold")
        ).pack(side="right", padx=25)

        # ------------------------------------------------------
        # Main Content
        # ------------------------------------------------------

        content = ctk.CTkFrame(
            self,
            fg_color="transparent"
        )

        content.pack(
            fill="both",
            expand=True,
            padx=50,
            pady=40
        )

        ctk.CTkLabel(
            content,
            text="Welcome Back, Kai",
            font=("Segoe UI", 34, "bold")
        ).pack(anchor="w")

        ctk.CTkLabel(
            content,
            text="Creative Intelligence Workspace",
            font=("Segoe UI", 18),
            text_color="gray"
        ).pack(anchor="w", pady=(0, 25))

        # ------------------------------------------------------
        # Buttons
        # ------------------------------------------------------

        button_frame = ctk.CTkFrame(
            content,
            fg_color="transparent"
        )

        button_frame.pack(anchor="w")

        ctk.CTkButton(
            button_frame,
            text="+ New Project",
            width=200,
            height=45,
            corner_radius=12,
            command=self.new_project
        ).pack(side="left")

        ctk.CTkButton(
            button_frame,
            text="Refresh",
            width=120,
            height=45,
            corner_radius=12,
            command=self.refresh_dashboard
        ).pack(side="left", padx=15)

        # ------------------------------------------------------
        # Statistics
        # ------------------------------------------------------

        self.stats_frame = ctk.CTkFrame(
            content,
            fg_color="transparent"
        )

        self.stats_frame.pack(fill="x", pady=35)

        self.load_statistics()

        # ------------------------------------------------------
        # Bottom Section
        # ------------------------------------------------------

        bottom = ctk.CTkFrame(
            content,
            fg_color="transparent"
        )

        bottom.pack(fill="both", expand=True)

        # ------------------------------------------------------
        # Recent Projects
        # ------------------------------------------------------

        recent = ctk.CTkFrame(
            bottom,
            width=500,
            corner_radius=15
        )

        recent.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(0, 20)
        )

        recent.pack_propagate(False)

        ctk.CTkLabel(
            recent,
            text="Recent Projects",
            font=("Segoe UI", 22, "bold")
        ).pack(anchor="w", padx=20, pady=(20, 15))

        projects = self.pm.get_recent_projects()

        if len(projects) == 0:

            ctk.CTkLabel(
                recent,
                text="No projects created yet.",
                text_color="gray"
            ).pack(anchor="w", padx=20)

        else:

            for project in projects:

                if not isinstance(project, dict):
                    continue

                project_name = project.get("name", "Untitled Project")
                project_status = project.get("status", "Research")
                project_created = project.get("created", "Unknown date")

                item = ctk.CTkFrame(
                    recent,
                    fg_color="#2B2B2B",
                    corner_radius=10
                )

                item.pack(
                    fill="x",
                    padx=15,
                    pady=6
                )

                ctk.CTkLabel(
                    item,
                    text=project_name,
                    font=("Segoe UI", 16, "bold")
                ).pack(anchor="w", padx=12, pady=(10, 0))

                ctk.CTkLabel(
                    item,
                    text=project_status,
                    text_color="#4CAF50"
                ).pack(anchor="w", padx=12)

                ctk.CTkLabel(
                    item,
                    text=project_created,
                    text_color="gray"
                ).pack(anchor="w", padx=12, pady=(0, 10))

        # ------------------------------------------------------
        # Workspace Information
        # ------------------------------------------------------

        info = ctk.CTkFrame(
            bottom,
            width=320,
            corner_radius=15
        )

        info.pack(side="right", fill="y")

        info.pack_propagate(False)

        ctk.CTkLabel(
            info,
            text="Workspace",
            font=("Segoe UI", 22, "bold")
        ).pack(anchor="w", padx=20, pady=(20, 15))

        storage = self.get_storage_size()

        labels = [
            ("Storage Used", storage),
            ("Projects Folder", "projects/"),
            ("AI Status", "Ready"),
            ("Version", f"v{VERSION}")
        ]

        for title, value in labels:

            row = ctk.CTkFrame(
                info,
                fg_color="transparent"
            )

            row.pack(fill="x", padx=20, pady=10)

            ctk.CTkLabel(
                row,
                text=title,
                font=("Segoe UI", 15)
            ).pack(anchor="w")

            ctk.CTkLabel(
                row,
                text=value,
                font=("Segoe UI", 16, "bold")
            ).pack(anchor="w")

    # ==========================================================
    # STATISTICS
    # ==========================================================

    def load_statistics(self):

        for widget in self.stats_frame.winfo_children():
            widget.destroy()

        projects = self.pm.get_project_count()

        stats = [
            ("Projects", str(projects), "📁"),
            ("Videos Created", "0", "🎬"),
            ("AI Status", "Ready", "🤖"),
        ]

        for title, value, icon in stats:
            StatCard(
                self.stats_frame,
                title=title,
                value=value,
                icon=icon,
            ).pack(
                side="left",
                padx=15,
            )

    # ==========================================================
    # STORAGE
    # ==========================================================

    def get_storage_size(self):

        total = 0

        for file in self.pm.PROJECTS_DIR.rglob("*"):

            if file.is_file():
                total += file.stat().st_size

        mb = total / (1024 * 1024)

        return f"{mb:.2f} MB"

    # ==========================================================
    # REFRESH
    # ==========================================================

    def refresh_dashboard(self):

        for widget in self.winfo_children():
            widget.destroy()

        self.build()

    # ==========================================================
    # NEW PROJECT
    # ==========================================================

    def _handle_project_created(self, project_name: str):
        self.refresh_dashboard()
        self.winfo_toplevel()._show_page(
            WorkspacePage,
            "AI Workspace",
            initial_project_name=project_name
        )

    def new_project(self):

        NewProjectDialog(self, on_project_created=self._handle_project_created)
