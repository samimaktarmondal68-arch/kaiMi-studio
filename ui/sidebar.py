import customtkinter as ctk


class Sidebar(ctk.CTkFrame):

    def __init__(self, master, navigate):

        super().__init__(
            master,
            width=260,
            fg_color="#161616",
            corner_radius=0
        )

        self.pack_propagate(False)
        self.navigate = navigate
        self.buttons = {}

        title = ctk.CTkLabel(

            self,

            text="KaiMi Studio",

            font=("Segoe UI",24,"bold")

        )

        title.pack(pady=(40,30))

        from ui.dashboard import Dashboard
        from ui.projects import ProjectsPage
        from ui.workspace import WorkspacePage
        from ui.assets import AssetsPage
        from ui.export import ExportPage
        from ui.settings_page import SettingsPage

        pages = {
            "Dashboard": Dashboard,
            "Video Projects": ProjectsPage,
            "AI Workspace": WorkspacePage,
            "Assets": AssetsPage,
            "Export": ExportPage,
            "Settings": SettingsPage,
        }
        

        for text, page in pages.items():

            btn = ctk.CTkButton(

                self,

                text=text,

                width=200,

                height=42,

                corner_radius=12,
                fg_color="transparent",
                hover_color="#303030",
                anchor="w",
                command=lambda p=page, t=text: self.navigate(p, t)

            )

            btn.pack(pady=7)
            self.buttons[text] = btn

    def set_active(self, title):
        for name, button in self.buttons.items():
            button.configure(fg_color="#2E5EAA" if name == title else "transparent")
