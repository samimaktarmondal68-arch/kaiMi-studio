# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Premium sidebar navigation for KaiMi Studio.

Design:
    - Dark sidebar with subtle border
    - Official KaiMi gradient logo (canvas-rendered)
    - Navigation items with canvas-drawn icons
    - Purple active pill
    - User profile card with premium badge
    - Help section
    - Hover animations and keyboard focus states
    - Responsive at 1200, 1400, 1600 px
"""

import customtkinter as ctk
from tkinter import Canvas
import math

from core.theme import Dark, Fonts, Radius, Spacing, Layout
from core.version import APP_NAME, VERSION


class KaiMiLogo(ctk.CTkFrame):
    """Official KaiMi logo mark — stylized K with gradient."""

    def __init__(self, master, size=28):
        super().__init__(master, width=size, height=size, fg_color="transparent")
        self.pack_propagate(False)
        self._size = size
        self._render()

    def _render(self):
        s = self._size
        canvas = Canvas(
            self, width=s, height=s,
            bg=Dark.SIDEBAR, highlightthickness=0,
        )
        canvas.pack(fill="both", expand=True)

        m = s / 2
        p = s * 0.12

        # Gradient background circle
        for i in range(24):
            ratio = i / 24
            r = int(109 + (77 - 109) * ratio)
            g = int(74 + (168 - 74) * ratio)
            b = 255
            color = f"#{r:02x}{g:02x}{b:02x}"
            half = m * (1 - ratio * 0.15)
            canvas.create_oval(m - half, m - half, m + half, m + half, fill=color, outline=color)

        # Stylized "K" letterform
        kw = s * 0.1  # stroke width
        # Vertical bar
        canvas.create_rectangle(
            p + s * 0.08, p + s * 0.15,
            p + s * 0.08 + kw, s - p - s * 0.15,
            fill="#FFFFFF", outline="",
        )
        # Upper diagonal
        canvas.create_polygon(
            p + s * 0.08 + kw + 1, m,
            s - p - s * 0.08, p + s * 0.15,
            s - p - s * 0.08 - kw * 0.7, p + s * 0.15,
            p + s * 0.08 + kw + 1, m - kw * 0.5,
            fill="#FFFFFF", outline="",
        )
        # Lower diagonal
        canvas.create_polygon(
            p + s * 0.08 + kw + 1, m,
            s - p - s * 0.08, s - p - s * 0.15,
            s - p - s * 0.08 - kw * 0.7, s - p - s * 0.15,
            p + s * 0.08 + kw + 1, m + kw * 0.5,
            fill="#FFFFFF", outline="",
        )


# ── Icon drawing functions ────────────────────────────────────────────

def _icon_dashboard(canvas, s, c):
    m = s / 2
    p = s * 0.18
    gap = 2
    hw = (s - 2 * p - gap) / 2
    canvas.create_rectangle(p, p, p + hw, p + hw, fill=c, outline="")
    canvas.create_rectangle(p + hw + gap, p, s - p, p + hw, fill=c, outline="")
    canvas.create_rectangle(p, p + hw + gap, p + hw, s - p, fill=c, outline="")
    canvas.create_rectangle(p + hw + gap, p + hw + gap, s - p, s - p, fill=c, outline="")


def _icon_projects(canvas, s, c):
    p = s * 0.15
    canvas.create_rectangle(p, p + 4, s - p, s - p, fill="", outline=c, width=2)
    canvas.create_rectangle(p + 3, p, s * 0.55, p + 6, fill="", outline=c, width=2)


def _icon_workflow(canvas, s, c):
    m = s / 2
    r = s * 0.32
    canvas.create_oval(m - r, m - r, m + r, m + r, outline=c, width=2)
    canvas.create_arc(m - r - 2, m - r - 2, m + r + 2, m + r + 2, start=30, extent=60, style="arc", outline=c, width=2)


def _icon_templates(canvas, s, c):
    p = s * 0.15
    gap = 3
    hw = (s - 2 * p - gap) / 2
    canvas.create_rectangle(p, p, p + hw, p + hw, fill="", outline=c, width=2)
    canvas.create_rectangle(p + hw + gap, p, s - p, p + hw, fill="", outline=c, width=2)
    canvas.create_rectangle(p, p + hw + gap, p + hw, s - p, fill="", outline=c, width=2)
    canvas.create_rectangle(p + hw + gap, p + hw + gap, s - p, s - p, fill="", outline=c, width=2)


def _icon_exports(canvas, s, c):
    m = s / 2
    p = s * 0.18
    canvas.create_line(m, p, m, s - p - 4, fill=c, width=2)
    canvas.create_polygon(m - 5, p + 7, m, p, m + 5, p + 7, fill=c, outline=c)
    canvas.create_line(p + 2, s - p, s - p - 2, s - p, fill=c, width=2)


def _icon_provider(canvas, s, c):
    m = s / 2
    r = s * 0.25
    canvas.create_oval(m - r, m - r - 1, m + r, m + r - 1, outline=c, width=2)
    canvas.create_line(m - 4, m + r + 3, m + 4, m + r + 3, fill=c, width=2)
    canvas.create_line(m - 2, m + r + 6, m + 2, m + r + 6, fill=c, width=1)


def _icon_settings(canvas, s, c):
    m = s / 2
    r_outer = s * 0.34
    r_inner = s * 0.18
    canvas.create_oval(m - r_outer, m - r_outer, m + r_outer, m + r_outer, outline=c, width=2)
    canvas.create_oval(m - r_inner, m - r_inner, m + r_inner, m + r_inner, outline=c, width=2)
    for angle in range(0, 360, 45):
        rad = math.radians(angle)
        x1 = m + (r_inner - 2) * math.cos(rad)
        y1 = m + (r_inner - 2) * math.sin(rad)
        x2 = m + (r_outer + 2) * math.cos(rad)
        y2 = m + (r_outer + 2) * math.sin(rad)
        canvas.create_line(x1, y1, x2, y2, fill=c, width=2)


def _icon_help(canvas, s, c):
    m = s / 2
    r = s * 0.34
    canvas.create_oval(m - r, m - r, m + r, m + r, outline=c, width=2)
    canvas.create_text(m, m + 1, text="?", fill=c, font=("Segoe UI", int(s * 0.36), "bold"))


def _icon_whatsnew(canvas, s, c):
    m = s / 2
    points = []
    for i in range(5):
        angle = math.radians(-90 + i * 72)
        r = s * 0.36
        points.append((m + r * math.cos(angle), m + r * math.sin(angle)))
        angle2 = math.radians(-90 + i * 72 + 36)
        r2 = s * 0.14
        points.append((m + r2 * math.cos(angle2), m + r2 * math.sin(angle2)))
    flat = [coord for pt in points for coord in pt]
    canvas.create_polygon(flat, fill=c, outline=c)


def _icon_about(canvas, s, c):
    m = s / 2
    r = s * 0.34
    canvas.create_oval(m - r, m - r, m + r, m + r, outline=c, width=2)
    canvas.create_line(m, m - r * 0.45, m, m + 0.5, fill=c, width=2)
    canvas.create_oval(m - 1.5, m + 2.5, m + 1.5, m + 5.5, fill=c, outline=c)


ICON_DRAW = {
    "dashboard": _icon_dashboard,
    "projects": _icon_projects,
    "workflow": _icon_workflow,
    "templates": _icon_templates,
    "exports": _icon_exports,
    "provider": _icon_provider,
    "settings": _icon_settings,
    "help": _icon_help,
    "whatsnew": _icon_whatsnew,
    "about": _icon_about,
}


# ── Nav item ──────────────────────────────────────────────────────────

class NavItem(ctk.CTkFrame):
    """Frame-based navigation item with icon canvas + label and smooth hover."""

    def __init__(self, master, icon_name, label, on_click=None, icon_size=18):
        super().__init__(master, fg_color="transparent", height=38, cursor="hand2")
        self.pack_propagate(False)
        self._on_click = on_click
        self._label = label
        self._is_active = False
        self._hover_job = None
        self._current_bg = Dark.SIDEBAR
        self._target_bg = Dark.SIDEBAR

        self.configure(width=Layout.SIDEBAR_WIDTH - 32)

        self._icon_canvas = Canvas(
            self, width=icon_size, height=icon_size,
            bg=Dark.SIDEBAR, highlightthickness=0,
        )
        self._icon_canvas.place(x=12, rely=0.5, anchor="w")
        self._icon_size = icon_size

        draw_fn = ICON_DRAW.get(icon_name)
        if draw_fn:
            draw_fn(self._icon_canvas, icon_size, Dark.TEXT_SECONDARY)

        self._text = ctk.CTkLabel(
            self, text=label, font=(Fonts.FAMILY, 13),
            text_color=Dark.TEXT_SECONDARY, anchor="w", fg_color="transparent",
        )
        self._text.place(x=38, rely=0.5, anchor="w")
        self._text.configure(width=Layout.SIDEBAR_WIDTH - 80)

        self.bind("<Button-1>", self._click)
        self._text.bind("<Button-1>", self._click)
        self._icon_canvas.bind("<Button-1>", self._click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _click(self, event=None):
        if self._on_click:
            self._on_click(self._label)

    def _on_enter(self, event=None):
        if not self._is_active:
            self._animate_bg(Dark.HOVER)
            self._text.configure(text_color=Dark.TEXT)

    def _on_leave(self, event=None):
        if not self._is_active:
            self._animate_bg(Dark.SIDEBAR)
            self._text.configure(text_color=Dark.TEXT_SECONDARY)

    def _animate_bg(self, target):
        if self._hover_job:
            self.after_cancel(self._hover_job)
        self._target_bg = target
        self._step_bg(6)

    def _step_bg(self, steps_left):
        if steps_left <= 0:
            self.configure(fg_color=self._target_bg)
            return
        self.configure(fg_color=self._target_bg)
        self._hover_job = self.after(25, lambda: self._step_bg(steps_left - 1))

    def set_active(self, active: bool):
        self._is_active = active
        if active:
            self.configure(fg_color=Dark.PRIMARY)
            self._text.configure(text_color=Dark.TEXT)
        else:
            self.configure(fg_color="transparent")
            self._text.configure(text_color=Dark.TEXT_SECONDARY)


# ── Sidebar ───────────────────────────────────────────────────────────

class Sidebar(ctk.CTkFrame):

    def __init__(self, master, navigate):
        super().__init__(
            master,
            width=Layout.SIDEBAR_WIDTH,
            fg_color=Dark.SIDEBAR,
            corner_radius=0,
        )
        self.pack_propagate(False)
        self.navigate = navigate
        self._nav_items: dict[str, NavItem] = {}

        self._build_logo()
        self._build_main_nav()
        self._build_help_nav()
        self._build_profile()

        # Version at very bottom
        ctk.CTkLabel(
            self,
            text=f"v{VERSION}",
            font=(Fonts.FAMILY, 10),
            text_color=Dark.TEXT_MUTED,
        ).pack(side="bottom", pady=(0, Spacing.X4))

    def _build_logo(self):
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(fill="x", padx=Spacing.X4, pady=(Spacing.X6, Spacing.X5))

        KaiMiLogo(frame, size=28).pack(side="left", padx=(Spacing.X4, Spacing.X3))

        ctk.CTkLabel(
            frame,
            text=APP_NAME,
            font=(Fonts.FAMILY, 17, "bold"),
            text_color=Dark.TEXT,
        ).pack(side="left")

    def _build_main_nav(self):
        nav = ctk.CTkFrame(self, fg_color="transparent")
        nav.pack(fill="x", padx=Spacing.X2, pady=(0, 0))

        self._section_label(nav, "MAIN")

        from ui.dashboard import Dashboard
        from ui.projects import ProjectsPage
        from ui.workspace import WorkspacePage
        from ui.templates import TemplatesPage
        from ui.export import ExportPage
        from ui.settings_page import SettingsPage

        items = [
            ("dashboard", "Dashboard", Dashboard),
            ("projects", "Projects", ProjectsPage),
            ("workflow", "Workflow", WorkspacePage),
            ("templates", "Templates", TemplatesPage),
            ("exports", "Exports", ExportPage),
        ]

        for icon, label, page in items:
            item = NavItem(nav, icon, label, on_click=lambda t=label, p=page: self.navigate(p, t))
            item.pack(fill="x", padx=Spacing.X2, pady=1)
            self._nav_items[label] = item

        # Separator
        ctk.CTkFrame(nav, fg_color=Dark.BORDER, height=1).pack(
            fill="x", padx=Spacing.X3, pady=Spacing.X4
        )

        self._section_label(nav, "SYSTEM")

        item = NavItem(nav, "settings", "Settings",
                       on_click=lambda label="Settings": self.navigate(SettingsPage, "Settings"))
        item.pack(fill="x", padx=Spacing.X2, pady=1)
        self._nav_items["Settings"] = item

    def _build_help_nav(self):
        help_frame = ctk.CTkFrame(self, fg_color="transparent")
        help_frame.pack(fill="x", padx=Spacing.X2, pady=(0, 0))

        ctk.CTkFrame(help_frame, fg_color=Dark.BORDER, height=1).pack(
            fill="x", padx=Spacing.X3, pady=Spacing.X4
        )

        self._section_label(help_frame, "HELP")

        from ui.whats_new import WhatsNewPage
        from ui.about import AboutPage

        help_items = [
            ("help", "Help & Docs", None),
            ("whatsnew", "What's New", WhatsNewPage),
            ("about", "About", AboutPage),
        ]

        for icon, label, page in help_items:
            target = page
            item = NavItem(help_frame, icon, label,
                           on_click=lambda t=label, p=target: self.navigate(p, t) if p else None)
            item.pack(fill="x", padx=Spacing.X2, pady=1)
            self._nav_items[label] = item

    def _section_label(self, parent, text: str):
        ctk.CTkLabel(
            parent,
            text=text,
            font=(Fonts.FAMILY, 10, "bold"),
            text_color=Dark.TEXT_MUTED,
        ).pack(anchor="w", padx=Spacing.X4, pady=(Spacing.X3, Spacing.X2))

    def _build_profile(self):
        ctk.CTkFrame(self, fg_color=Dark.BORDER, height=1).pack(
            fill="x", padx=Spacing.X4, pady=Spacing.X3
        )

        card = ctk.CTkFrame(
            self,
            fg_color=Dark.CARD,
            corner_radius=Radius.MD,
            border_width=1,
            border_color=Dark.BORDER,
            height=60,
        )
        card.pack(fill="x", padx=Spacing.X3, pady=(0, Spacing.X2))
        card.pack_propagate(False)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=Spacing.X3, pady=Spacing.X3)

        avatar = ctk.CTkFrame(inner, width=34, height=34, corner_radius=17, fg_color=Dark.PRIMARY)
        avatar.pack(side="left", padx=(0, Spacing.X2))
        avatar.pack_propagate(False)

        ctk.CTkLabel(avatar, text="K", font=(Fonts.FAMILY, 13, "bold"), text_color=Dark.TEXT).pack(expand=True)

        info = ctk.CTkFrame(inner, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True)

        name_row = ctk.CTkFrame(info, fg_color="transparent")
        name_row.pack(fill="x")

        ctk.CTkLabel(name_row, text="KaiMi User", font=(Fonts.FAMILY, 12, "bold"), text_color=Dark.TEXT).pack(side="left")

        ctk.CTkLabel(
            name_row, text="PRO", font=(Fonts.FAMILY, 8, "bold"),
            text_color="#FFD700", fg_color=Dark.SURFACE,
            corner_radius=4, padx=4, pady=1,
        ).pack(side="left", padx=(Spacing.X2, 0))

        ctk.CTkLabel(info, text="user@kaimi.ai", font=(Fonts.FAMILY, 10), text_color=Dark.TEXT_MUTED).pack(anchor="w")

    def set_active(self, title: str) -> None:
        for name, item in self._nav_items.items():
            item.set_active(name == title)
