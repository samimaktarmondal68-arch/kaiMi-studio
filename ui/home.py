import customtkinter as ctk

from ui.sidebar import Sidebar
from ui.dashboard import Dashboard
from ui.projects import ProjectsPage
from ui.workspace import WorkspacePage
from ui.assets import AssetsPage
from ui.export import ExportPage
from ui.settings_page import SettingsPage


class HomeWindow:

    def __init__(self):

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.app = ctk.CTk()
        self.app.title("KaiMi Studio")
        self.app.geometry("1500x900")
        self.app.minsize(1200, 700)

        self.build_ui()

    def build_ui(self):

        # Sidebar
        self.sidebar = Sidebar(self.app, self.show_page)
        self.sidebar.pack(
            side="left",
            fill="y"
        )

        # Main Content Container
        self.container = ctk.CTkFrame(
            self.app,
            fg_color="transparent"
        )

        self.container.pack(
            side="left",
            fill="both",
            expand=True
        )

        # Load Dashboard
        self.show_page(Dashboard, "Dashboard")

    def show_page(self, page_class, title=None):

        # Remove previous page
        for widget in self.container.winfo_children():
            widget.destroy()

        page = page_class(self.container)

        page.pack(
            fill="both",
            expand=True
        )

        self.sidebar.set_active(title or page_class.__name__)

    def run(self):
        self.app.mainloop()
