"""Main application window for KaiMi Studio.

Design:
    - Clean dark background
    - Sidebar + content layout
    - Smooth page transitions
"""

import os
import sys
import customtkinter as ctk
from pathlib import Path

from core.theme import Dark, Layout
from core.settings import AppSettings
from core.shortcuts import KeyboardShortcuts
from core.notifications import NotificationService
from ui.sidebar import Sidebar
from ui.dashboard import Dashboard


def _get_icon_path() -> Path:
    """Resolve the application icon path (handles both dev and frozen/PyInstaller)."""
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parent.parent
    return base / "assets" / "icons" / "kaimi.ico"


class HomeWindow:

    def __init__(self):
        self._settings = AppSettings()

        ctk.set_appearance_mode(self._settings.get_theme())
        ctk.set_default_color_theme("blue")

        self.app = ctk.CTk()
        self.app.title("KaiMi Studio")
        self.app.minsize(1200, 700)
        self.app.configure(fg_color=Dark.BG)
        self.app._show_page = self.show_page

        self._restore_window_geometry()
        self._set_window_icon()

        self.build_ui()

    def _restore_window_geometry(self):
        w, h = self._settings.get_window_geometry()
        self.app.geometry(f"{w}x{h}")

    def _set_window_icon(self):
        try:
            icon_path = _get_icon_path()
            if icon_path.exists():
                self.app.iconbitmap(str(icon_path))
        except Exception:
            pass

    def build_ui(self):
        NotificationService.get().set_root(self.app)

        self.sidebar = Sidebar(self.app, self.show_page)
        self.sidebar.pack(side="left", fill="y")

        # Main Content Container
        self.container = ctk.CTkFrame(
            self.app,
            fg_color=Dark.BG,
            corner_radius=0,
        )
        self.container.pack(side="left", fill="both", expand=True)

        # Load Dashboard
        self.show_page(Dashboard, "Dashboard")

        KeyboardShortcuts(self.app, self)

    def show_page(self, page_class, title=None, **kwargs):
        for widget in self.container.winfo_children():
            widget.destroy()

        page = page_class(self.container, **kwargs)
        page.pack(fill="both", expand=True)
        self.current_page = page

        self.sidebar.set_active(title or page_class.__name__)

    def run(self):
        self.app.mainloop()
