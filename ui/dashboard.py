# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Premium dashboard page for KaiMi Studio.

Design:
    - Top toolbar with search and new project button
    - Welcome header with clean typography
    - Four premium stat cards with icons, metrics, trends, hover
    - Recent projects panel
    - Workflow overview
    - Provider status
    - Premium banner
"""

import customtkinter as ctk
from tkinter import Canvas
from datetime import datetime

from core.theme import Dark, Fonts, Radius, Spacing
from core.version import APP_NAME
from core.project_manager import ProjectManager
from core.workflow import WORKFLOW_STAGES
from providers.provider_manager import ProviderManager
from ui.dialogs import NewProjectDialog
from ui.workspace import WorkspacePage


# -- Stat card icon drawing functions ------------------------------

def _draw_stat_projects(canvas, s, c):
    p = s * 0.18
    canvas.create_rectangle(p, p + 5, s - p, s - p, fill="", outline=c, width=2)
    canvas.create_rectangle(p + 4, p, s * 0.58, p + 7, fill="", outline=c, width=2)


def _draw_stat_progress(canvas, s, c):
    m = s / 2
    r = s * 0.36
    canvas.create_oval(m - r, m - r, m + r, m + r, outline=c, width=2.5)
    canvas.create_arc(m - r, m - r, m + r, m + r, start=90, extent=120, style="arc", outline=c, width=2.5)


def _draw_stat_done(canvas, s, c):
    m = s / 2
    r = s * 0.36
    canvas.create_oval(m - r, m - r, m + r, m + r, outline=c, width=2.5)
    canvas.create_line(m - r * 0.45, m, m - r * 0.05, m + r * 0.4, fill=c, width=2.5)
    canvas.create_line(m - r * 0.05, m + r * 0.4, m + r * 0.5, m - r * 0.35, fill=c, width=2.5)


def _draw_stat_ai(canvas, s, c):
    m = s / 2
    r = s * 0.3
    canvas.create_oval(m - r, m - r - 1, m + r, m + r - 1, outline=c, width=2.5)
    canvas.create_oval(m - 2.5, m - r - 5, m + 2.5, m - r - 1, fill=c, outline="")
    canvas.create_line(m - 5, m + r + 3, m + 5, m + r + 3, fill=c, width=2)
    canvas.create_line(m - 3, m + r + 6, m + 3, m + r + 6, fill=c, width=1.5)


STAT_ICONS = {
    "projects": _draw_stat_projects,
    "progress": _draw_stat_progress,
    "done": _draw_stat_done,
    "ai": _draw_stat_ai,
}


# -- Components -----------------------------------------------------

class SearchBar(ctk.CTkFrame):

    def __init__(self, master, **kwargs):
        super().__init__(
            master, height=40, fg_color=Dark.INPUT_BG,
            corner_radius=Radius.MD, border_width=1,
            border_color=Dark.INPUT_BORDER, **kwargs,
        )
        self.pack_propagate(False)

        icon = Canvas(self, width=16, height=16, bg=Dark.INPUT_BG, highlightthickness=0)
        icon.pack(side="left", padx=(Spacing.X3, Spacing.X2))
        icon.create_oval(3, 3, 11, 11, outline=Dark.TEXT_MUTED, width=1.5)
        icon.create_line(10, 10, 14, 14, fill=Dark.TEXT_MUTED, width=1.5)

        self._entry = ctk.CTkEntry(
            self, placeholder_text="Search projects, templates...",
            fg_color="transparent", border_width=0,
            text_color=Dark.TEXT, placeholder_text_color=Dark.TEXT_MUTED,
            font=Fonts.INPUT,
        )
        self._entry.pack(side="left", fill="both", expand=True, padx=(0, Spacing.X2))

        hint = ctk.CTkFrame(self, fg_color=Dark.SURFACE, corner_radius=Radius.SM, width=44, height=24)
        hint.pack(side="right", padx=(0, Spacing.X2))
        hint.pack_propagate(False)
        ctk.CTkLabel(hint, text="Ctrl+K", font=(Fonts.FAMILY, 10), text_color=Dark.TEXT_MUTED).pack(expand=True)


class TopToolbar(ctk.CTkFrame):

    def __init__(self, master, on_new_project=None, **kwargs):
        super().__init__(master, fg_color="transparent", height=48, **kwargs)
        self.pack_propagate(False)
        self._on_new_project = on_new_project

        search = SearchBar(self)
        search.pack(side="left", fill="y", padx=(0, Spacing.X3))
        search.configure(width=700)

        ctk.CTkButton(
            self, text="+ New Project", height=40, width=150,
            corner_radius=Radius.MD, fg_color=Dark.PRIMARY,
            hover_color=Dark.PRIMARY_HOVER, text_color=Dark.TEXT,
            font=Fonts.BUTTON, command=self._on_new_project,
        ).pack(side="right")

        try:
            self.winfo_toplevel().bind("<Control-k>", lambda e: search._entry.focus_set())
        except Exception:
            pass


class WelcomeHeader(ctk.CTkFrame):

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        hour = datetime.now().hour
        greeting = "Good Morning" if hour < 12 else "Good Afternoon" if hour < 17 else "Good Evening"

        ctk.CTkLabel(self, text=greeting, font=(Fonts.FAMILY, 36, "bold"), text_color=Dark.TEXT).pack(anchor="w")
        ctk.CTkLabel(
            self, text=f"Welcome to {APP_NAME}  \u2014  Creative Intelligence Workspace",
            font=(Fonts.FAMILY, 16), text_color=Dark.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.X1, 0))
        now = datetime.now().strftime("%B %d, %Y  \u2022  %H:%M")
        ctk.CTkLabel(self, text=now, font=Fonts.SMALL, text_color=Dark.TEXT_MUTED).pack(anchor="w", pady=(Spacing.X1, 0))


class StatCard(ctk.CTkFrame):

    def __init__(self, master, title, value, icon_name="projects", trend="", trend_up=True):
        super().__init__(
            master, fg_color=Dark.CARD, corner_radius=Radius.LG,
            border_width=1, border_color=Dark.BORDER, height=140,
        )
        self.pack_propagate(False)
        self._base_bg = Dark.CARD
        self._hover_bg = "#131B2E"
        self._base_border = Dark.BORDER
        self._hover_border = Dark.PRIMARY
        self._anim_job = None

        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        # Icon
        icon_size = 28
        icon_bg = ctk.CTkFrame(self, width=40, height=40, corner_radius=Radius.SM, fg_color="#15102A")
        icon_bg.place(x=20, y=18)
        icon_bg.pack_propagate(False)
        self._icon_bg = icon_bg

        ic = Canvas(icon_bg, width=icon_size, height=icon_size, bg="#15102A", highlightthickness=0)
        ic.pack(expand=True)
        draw_fn = STAT_ICONS.get(icon_name)
        if draw_fn:
            draw_fn(ic, icon_size, Dark.PRIMARY)

        ctk.CTkLabel(self, text=title, font=Fonts.SMALL_BOLD, text_color=Dark.TEXT_SECONDARY).place(x=20, y=68)
        ctk.CTkLabel(self, text=value, font=(Fonts.FAMILY, 32, "bold"), text_color=Dark.TEXT).place(x=20, y=92)

        if trend:
            color = Dark.SUCCESS if trend_up else Dark.ERROR
            arrow = "\u25B2" if trend_up else "\u25BC"
            bg = "#0F291A" if trend_up else "#2A1215"
            pill = ctk.CTkFrame(self, fg_color=bg, corner_radius=Radius.SM)
            pill.place(relx=1.0, rely=1.0, x=-16, y=-16, anchor="se")
            ctk.CTkLabel(pill, text=f"{arrow} {trend}", font=(Fonts.FAMILY, 11, "bold"), text_color=color, padx=8, pady=3).pack()

    def _on_enter(self, e=None):
        self._animate(self._hover_bg, self._hover_border, 8)

    def _on_leave(self, e=None):
        self._animate(self._base_bg, self._base_border, 8)

    def _animate(self, target_bg, target_border, steps):
        if self._anim_job:
            self.after_cancel(self._anim_job)
        self.configure(fg_color=target_bg, border_color=target_border)


# -- Workflow Overview Panel -----------------------------------------

class CircularProgress(ctk.CTkFrame):
    """Circular progress indicator with entrance animation."""

    def __init__(self, master, size=140, progress=0.0, **kwargs):
        super().__init__(master, width=size, height=size, fg_color="transparent", **kwargs)
        self.pack_propagate(False)
        self._size = size
        self._target_progress = progress
        self._progress = 0.0
        self._canvas = Canvas(
            self, width=size, height=size, bg=Dark.CARD, highlightthickness=0,
        )
        self._canvas.pack(fill="both", expand=True)
        self._anim_steps = 0
        self._anim_total = 30
        self.after(100, self._start_animation)

    def _start_animation(self):
        self._anim_steps = 0
        self._animate_frame()

    def _animate_frame(self):
        if self._anim_steps >= self._anim_total:
            self._progress = self._target_progress
            self._render_circle()
            return
        self._anim_steps += 1
        t = self._anim_steps / self._anim_total
        ease = 1 - (1 - t) ** 3
        self._progress = self._target_progress * ease
        self._render_circle()
        self.after(16, self._animate_frame)

    def _render_circle(self):
        self._canvas.delete("all")
        s = self._size
        m = s / 2
        r = s * 0.38
        lw = 10

        self._canvas.create_arc(
            m - r, m - r, m + r, m + r,
            start=0, extent=359.9, style="arc",
            outline=Dark.BORDER, width=lw,
        )

        extent = 360 * self._progress
        if extent > 0:
            self._canvas.create_arc(
                m - r, m - r, m + r, m + r,
                start=90, extent=-extent, style="arc",
                outline=Dark.PRIMARY, width=lw,
            )

        pct = int(self._progress * 100)
        self._canvas.create_text(
            m, m - 5, text=f"{pct}%", fill=Dark.TEXT,
            font=(Fonts.FAMILY, 26, "bold"),
        )
        self._canvas.create_text(
            m, m + 18, text="Complete", fill=Dark.TEXT_MUTED,
            font=(Fonts.FAMILY, 11),
        )

    def set_progress(self, value):
        self._target_progress = value
        self._anim_steps = 0
        self._animate_frame()


class WorkflowOverview(ctk.CTkFrame):
    """Workflow overview panel with circular progress and stage bars."""

    def __init__(self, master, workflow_state=None, **kwargs):
        super().__init__(
            master, fg_color=Dark.CARD, corner_radius=Radius.LG,
            border_width=1, border_color=Dark.BORDER, **kwargs,
        )
        self._state = workflow_state or {}
        self._build()

    def _build(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=Spacing.X6, pady=(Spacing.X5, Spacing.X3))
        ctk.CTkLabel(header, text="Workflow Overview", font=Fonts.SECTION, text_color=Dark.TEXT).pack(side="left")
        ctk.CTkLabel(header, text="Pipeline", font=Fonts.SMALL, text_color=Dark.TEXT_MUTED).pack(side="right")

        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="x", padx=Spacing.X6, pady=(0, Spacing.X6))

        # Left: circular progress
        completed = sum(1 for v in self._state.values() if v == "COMPLETED")
        total = max(len(self._state), 1)
        progress = completed / total

        circle_frame = ctk.CTkFrame(content, fg_color="transparent")
        circle_frame.pack(side="left", padx=(0, Spacing.X6))

        CircularProgress(circle_frame, size=140, progress=progress).pack()

        ctk.CTkLabel(
            circle_frame, text=f"{completed}/{total} Stages",
            font=Fonts.SMALL, text_color=Dark.TEXT_MUTED,
        ).pack(pady=(Spacing.X2, 0))

        # Right: stage progress bars
        bars_frame = ctk.CTkFrame(content, fg_color="transparent")
        bars_frame.pack(side="left", fill="both", expand=True)

        # Only show first 4 stages (Research, Script, Storyboard, Image Prompts)
        display_stages = WORKFLOW_STAGES[:4]
        stage_colors = {
            "Research": Dark.SECONDARY,
            "Script": "#8B5CF6",
            "Storyboard": Dark.WARNING,
            "Image Prompts": "#06B6D4",
        }

        for idx, stage in enumerate(display_stages):
            state = self._state.get(stage, "LOCKED")
            color = stage_colors.get(stage, Dark.TEXT_SECONDARY)

            row = ctk.CTkFrame(bars_frame, fg_color="transparent", height=32)
            row.pack(fill="x", pady=3)
            row.pack_propagate(False)

            # Label
            ctk.CTkLabel(
                row, text=stage, font=(Fonts.FAMILY, 12, "bold"),
                text_color=Dark.TEXT_SECONDARY, width=110, anchor="w",
            ).pack(side="left")

            # Progress bar background
            bar_bg = ctk.CTkFrame(row, fg_color=Dark.SURFACE, height=8, corner_radius=4)
            bar_bg.pack(side="left", fill="x", expand=True, padx=(Spacing.X3, Spacing.X3))
            bar_bg.pack_propagate(False)

            # Progress bar fill with animation
            if state == "COMPLETED":
                fill_pct = 1.0
            elif state == "AVAILABLE":
                fill_pct = 0.3
            else:
                fill_pct = 0.0

            if fill_pct > 0:
                bar_fill = ctk.CTkFrame(bar_bg, fg_color=color, height=8, corner_radius=4)
                bar_fill.pack(side="left", anchor="w")
                delay = 150 + idx * 100

                def _animate_bar(b=bar_fill, p=fill_pct, parent=bar_bg):
                    target_w = max(int(parent.winfo_width() * p), 8)
                    parent.update_idletasks()
                    current_w = 0
                    steps = 20

                    def _step(step):
                        nonlocal current_w
                        if step >= steps:
                            b.configure(width=target_w)
                            return
                        t = step / steps
                        ease = 1 - (1 - t) ** 3
                        new_w = int(target_w * ease)
                        b.configure(width=max(new_w, 2))
                        parent.after(16, lambda: _step(step + 1))
                    _step(0)

                bar_bg.after(delay, _animate_bar)

            # Status badge
            badge_colors = {
                "COMPLETED": (Dark.SUCCESS, "#0F291A"),
                "AVAILABLE": (Dark.PRIMARY, "#1A1535"),
                "LOCKED": (Dark.TEXT_MUTED, Dark.SURFACE),
            }
            bc, bbg = badge_colors.get(state, (Dark.TEXT_MUTED, Dark.SURFACE))
            badge = ctk.CTkFrame(row, fg_color=bbg, corner_radius=Radius.SM, width=78, height=22)
            badge.pack(side="right")
            badge.pack_propagate(False)
            ctk.CTkLabel(badge, text=state.title(), font=(Fonts.FAMILY, 10, "bold"), text_color=bc).pack(expand=True)


# -- Provider Status Panel -------------------------------------------

class ProviderCard(ctk.CTkFrame):
    """Single provider status card with smooth hover and click to open settings."""

    def __init__(self, master, name, model="", is_active=False, is_configured=False, on_click=None, **kwargs):
        super().__init__(
            master, fg_color=Dark.SURFACE, corner_radius=Radius.MD,
            border_width=1, border_color=Dark.PRIMARY if is_active else Dark.BORDER,
            height=76, cursor="hand2", **kwargs,
        )
        self.pack_propagate(False)
        self._base_bg = Dark.SURFACE
        self._hover_bg = Dark.CARD
        self._base_border = Dark.PRIMARY if is_active else Dark.BORDER
        self._hover_border = Dark.PRIMARY
        self._on_click = on_click

        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=Spacing.X5, pady=Spacing.X4)

        # Left: status dot + provider info
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left", fill="both", expand=True)

        top_row = ctk.CTkFrame(left, fg_color="transparent")
        top_row.pack(fill="x")

        # Online indicator
        dot_color = Dark.SUCCESS if is_configured else Dark.TEXT_MUTED
        dot = Canvas(top_row, width=10, height=10, bg=Dark.SURFACE, highlightthickness=0)
        dot.pack(side="left", padx=(0, Spacing.X2))
        dot.create_oval(1, 1, 9, 9, fill=dot_color, outline="")

        display_name = name.title()
        ctk.CTkLabel(top_row, text=display_name, font=(Fonts.FAMILY, 14, "bold"), text_color=Dark.TEXT).pack(side="left")

        if is_active:
            active_pill = ctk.CTkFrame(top_row, fg_color=Dark.PRIMARY, corner_radius=Radius.SM)
            active_pill.pack(side="left", padx=(Spacing.X3, 0))
            ctk.CTkLabel(
                active_pill, text="Active", font=(Fonts.FAMILY, 10, "bold"),
                text_color=Dark.TEXT, padx=8, pady=2,
            ).pack()

        # Model name
        model_text = model if model else "No model configured"
        ctk.CTkLabel(left, text=model_text, font=Fonts.SMALL, text_color=Dark.TEXT_MUTED).pack(anchor="w", pady=(Spacing.X1, 0))

        # Right: configured status
        status_color = Dark.SUCCESS if is_configured else Dark.TEXT_MUTED
        status_text = "Configured" if is_configured else "Not Set"
        ctk.CTkLabel(inner, text=status_text, font=Fonts.SMALL_BOLD, text_color=status_color).pack(side="right")

        # Bind click to all child widgets
        for child in self._all_children(self):
            child.bind("<Button-1>", self._click)

    def _all_children(self, widget):
        """Recursively collect all descendant widgets."""
        children = []
        for child in widget.winfo_children():
            children.append(child)
            children.extend(self._all_children(child))
        return children

    def _click(self, event=None):
        if self._on_click:
            self._on_click()

    def _on_enter(self, e=None):
        self.configure(fg_color=self._hover_bg, border_color=self._hover_border)

    def _on_leave(self, e=None):
        self.configure(fg_color=self._base_bg, border_color=self._base_border)


class ProviderStatus(ctk.CTkFrame):
    """Provider status panel showing all registered providers."""

    def __init__(self, master, **kwargs):
        super().__init__(
            master, fg_color=Dark.CARD, corner_radius=Radius.LG,
            border_width=1, border_color=Dark.BORDER, **kwargs,
        )
        self._build()

    def _build(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=Spacing.X6, pady=(Spacing.X5, Spacing.X3))
        ctk.CTkLabel(header, text="Provider Status", font=Fonts.SECTION, text_color=Dark.TEXT).pack(side="left")

        try:
            pm = ProviderManager()
            active_name = pm.get_active_provider_name()
            registered = pm.get_registered_providers()
        except Exception:
            active_name = ""
            registered = []

        # Provider cards
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=Spacing.X6, pady=(0, Spacing.X3))

        for name in registered:
            try:
                model = pm.get_provider_model(name)
                configured = pm.validate_provider_configuration(name)
            except Exception:
                model = ""
                configured = False

            is_active = (name == active_name)
            ProviderCard(
                cards_frame, name=name, model=model,
                is_active=is_active, is_configured=configured,
                on_click=self._open_settings,
            ).pack(fill="x", pady=(0, Spacing.X2))

        # Add Provider button
        ctk.CTkButton(
            self, text="+ Add Provider", height=36,
            corner_radius=Radius.MD, fg_color="transparent",
            hover_color=Dark.HOVER, text_color=Dark.PRIMARY,
            border_width=1, border_color=Dark.PRIMARY,
            font=Fonts.BUTTON,
            command=self._open_settings,
        ).pack(padx=Spacing.X6, pady=(Spacing.X2, Spacing.X5))

    def _open_settings(self):
        try:
            root = self.winfo_toplevel()
            if hasattr(root, "_show_page"):
                from ui.settings_page import SettingsPage
                root._show_page(SettingsPage, "Settings")
        except Exception as e:
            from core.logger import get_logger
            get_logger().error("ProviderStatus", f"_open_settings failed: {e}")


# -- Dashboard ------------------------------------------------------

class Dashboard(ctk.CTkFrame):

    def __init__(self, master):
        super().__init__(master, fg_color=Dark.BG)
        self.pm = ProjectManager()
        self._build()

    def _build(self):
        toolbar = TopToolbar(self, on_new_project=self.new_project)
        toolbar.pack(fill="x", padx=Spacing.X10, pady=(Spacing.X5, Spacing.X2))

        header = WelcomeHeader(self)
        header.pack(fill="x", padx=Spacing.X10, pady=(Spacing.X1, Spacing.X4))

        scroll = ctk.CTkScrollableFrame(
            self, fg_color=Dark.BG,
            scrollbar_button_color=Dark.BORDER,
            scrollbar_button_hover_color=Dark.TEXT_MUTED,
        )
        scroll.pack(fill="both", expand=True)

        self._build_statistics(scroll)

        # Two-column layout for Workflow Overview + Provider Status
        mid_row = ctk.CTkFrame(scroll, fg_color="transparent")
        mid_row.pack(fill="x", padx=Spacing.X10, pady=(0, Spacing.X5))

        # Workflow Overview (left, wider) with shadow
        workflow_outer = ctk.CTkFrame(mid_row, fg_color="transparent")
        workflow_outer.pack(side="left", fill="both", expand=True, padx=(0, Spacing.X3))

        workflow_shadow = ctk.CTkFrame(workflow_outer, fg_color="#0A0E1A", corner_radius=Radius.LG, height=4)
        workflow_shadow.pack(fill="x", padx=4, pady=(0, 2))

        try:
            pm_proj = ProjectManager()
            recent = pm_proj.get_recent_projects(1)
            wf_state = recent[0].get("workflow_state", {}) if recent else {}
        except Exception:
            wf_state = {}
        WorkflowOverview(workflow_outer, workflow_state=wf_state).pack(fill="both", expand=True)

        # Provider Status (right, fixed width) with shadow
        provider_outer = ctk.CTkFrame(mid_row, fg_color="transparent", width=340)
        provider_outer.pack(side="right", fill="y")
        provider_outer.pack_propagate(False)

        provider_shadow = ctk.CTkFrame(provider_outer, fg_color="#0A0E1A", corner_radius=Radius.LG, height=4)
        provider_shadow.pack(fill="x", padx=4, pady=(0, 2))

        ProviderStatus(provider_outer).pack(fill="both", expand=True)

        self._build_recent_projects(scroll)
        self._build_premium_banner(scroll)

    def _build_statistics(self, parent):
        cards_row = ctk.CTkFrame(parent, fg_color="transparent")
        cards_row.pack(fill="x", padx=Spacing.X10, pady=(0, Spacing.X5))

        total = self.pm.get_project_count()
        recent = self.pm.get_recent_projects(100)
        in_progress = sum(
            1 for p in recent
            if isinstance(p, dict) and p.get("status") not in ("Export", "Research", "")
        )

        stats = [
            ("Total Projects", str(total), "projects", "", True),
            ("In Progress", str(in_progress), "progress", "", True),
            ("Completed", "0", "done", "0%", True),
            ("AI Provider", "Ready", "ai", "Online", True),
        ]

        for title, value, icon, trend, trend_up in stats:
            StatCard(cards_row, title=title, value=value, icon_name=icon, trend=trend, trend_up=trend_up).pack(
                side="left", fill="x", expand=True, padx=(0, Spacing.X3)
            )

    def _build_recent_projects(self, parent):
        card = ctk.CTkFrame(
            parent, fg_color=Dark.CARD, corner_radius=Radius.LG,
            border_width=1, border_color=Dark.BORDER,
        )
        card.pack(fill="x", padx=Spacing.X10, pady=(0, Spacing.X8))
        # Shadow layer under the card
        shadow = ctk.CTkFrame(
            parent, fg_color="#0A0E1A", corner_radius=Radius.LG,
            height=4,
        )

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=Spacing.X6, pady=(Spacing.X5, Spacing.X3))

        ctk.CTkLabel(header, text="Recent Projects", font=Fonts.SECTION, text_color=Dark.TEXT).pack(side="left")

        ctk.CTkLabel(
            header, text="View All \u2192", font=Fonts.SMALL,
            text_color=Dark.PRIMARY, cursor="hand2",
        ).pack(side="right")

        projects = self.pm.get_recent_projects()

        if not projects:
            ctk.CTkLabel(
                card, text="No projects yet. Create one to get started.",
                font=Fonts.BODY, text_color=Dark.TEXT_MUTED,
            ).pack(padx=Spacing.X6, pady=Spacing.X8)
            return

        for project in projects:
            if not isinstance(project, dict):
                continue
            name = project.get("name", "Untitled")
            status = project.get("status", "Research")
            created = project.get("created", "")
            topic = project.get("topic", "")

            status_colors = {
                "Research": Dark.SECONDARY,
                "Script": "#8B5CF6",
                "Storyboard": Dark.WARNING,
                "Image Prompts": "#06B6D4",
                "Export": Dark.SUCCESS,
            }
            sc = status_colors.get(status, Dark.TEXT_SECONDARY)

            item = ctk.CTkFrame(card, fg_color=Dark.SURFACE, corner_radius=Radius.MD, height=64)
            item.pack(fill="x", padx=Spacing.X5, pady=Spacing.X1)
            item.pack_propagate(False)
            item._base_bg = Dark.SURFACE
            item._hover_bg = Dark.HOVER

            inner = ctk.CTkFrame(item, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=Spacing.X4, pady=Spacing.X3)

            # Left: icon + text
            left = ctk.CTkFrame(inner, fg_color="transparent")
            left.pack(side="left", fill="both", expand=True)

            # Project icon (colored square with initial)
            icon_bg = ctk.CTkFrame(left, width=32, height=32, corner_radius=Radius.SM, fg_color=sc)
            icon_bg.pack(side="left", padx=(0, Spacing.X3))
            icon_bg.pack_propagate(False)
            ctk.CTkLabel(icon_bg, text=name[0].upper(), font=(Fonts.FAMILY, 14, "bold"), text_color=Dark.TEXT).pack(expand=True)

            text_col = ctk.CTkFrame(left, fg_color="transparent")
            text_col.pack(side="left", fill="both", expand=True)

            name_label = ctk.CTkLabel(text_col, text=name, font=(Fonts.FAMILY, 14, "bold"), text_color=Dark.TEXT)
            name_label.pack(anchor="w")

            meta_parts = []
            if topic:
                meta_parts.append(topic)
            if created:
                meta_parts.append(created)
            meta_text = "  \u2022  ".join(meta_parts) if meta_parts else ""
            ctk.CTkLabel(text_col, text=meta_text, font=Fonts.TINY, text_color=Dark.TEXT_MUTED).pack(anchor="w")

            # Right: status pill + 3-dot menu
            right = ctk.CTkFrame(inner, fg_color="transparent")
            right.pack(side="right")

            pill = ctk.CTkFrame(right, fg_color=sc, corner_radius=Radius.FULL)
            pill.pack(side="left", padx=(0, Spacing.X3))
            ctk.CTkLabel(pill, text=status, font=(Fonts.FAMILY, 10, "bold"), text_color=Dark.TEXT, padx=10, pady=4).pack()

            menu_btn = ctk.CTkButton(
                right, text="\u22EE", width=28, height=28,
                fg_color="transparent", hover_color=Dark.HOVER,
                text_color=Dark.TEXT_MUTED, font=(Fonts.FAMILY, 16),
                corner_radius=Radius.SM,
            )
            menu_btn.pack(side="right")

            def _enter(e, w=item, n=name_label):
                w.configure(fg_color=w._hover_bg, border_width=1, border_color=Dark.BORDER)
                n.configure(text_color=Dark.PRIMARY)
            def _leave(e, w=item, n=name_label):
                w.configure(fg_color=w._base_bg, border_width=0)
                n.configure(text_color=Dark.TEXT)
            item.bind("<Enter>", _enter)
            item.bind("<Leave>", _leave)
            inner.bind("<Enter>", _enter)
            inner.bind("<Leave>", _leave)
            left.bind("<Enter>", _enter)
            left.bind("<Leave>", _leave)
            text_col.bind("<Enter>", _enter)
            text_col.bind("<Leave>", _leave)

    def _build_premium_banner(self, parent):
        banner = ctk.CTkFrame(
            parent, fg_color="#110D24", corner_radius=Radius.LG,
            border_width=1, border_color="#2A1F52", height=80,
        )
        banner.pack(fill="x", padx=Spacing.X10, pady=(0, Spacing.X8))
        banner.pack_propagate(False)

        inner = ctk.CTkFrame(banner, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=Spacing.X6, pady=Spacing.X4)

        text_col = ctk.CTkFrame(inner, fg_color="transparent")
        text_col.pack(side="left", fill="both", expand=True)

        ctk.CTkLabel(
            text_col, text="Upgrade to KaiMi Pro",
            font=(Fonts.FAMILY, 16, "bold"), text_color=Dark.PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            text_col,
            text="Unlock unlimited projects, advanced AI providers, priority support, and more.",
            font=Fonts.SMALL, text_color=Dark.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(Spacing.X1, 0))

        ctk.CTkButton(
            inner, text="Learn More",
            font=(Fonts.FAMILY, 13, "bold"), text_color="#FFFFFF",
            fg_color=Dark.PRIMARY, hover_color="#7C5CFF",
            corner_radius=Radius.SM, width=120, height=36, cursor="hand2",
        ).pack(side="right", padx=(Spacing.X4, 0))

    def refresh_dashboard(self):
        for widget in self.winfo_children():
            widget.destroy()
        self._build()

    def _handle_project_created(self, project_name):
        self.refresh_dashboard()
        self.winfo_toplevel()._show_page(WorkspacePage, "Workspace", initial_project_name=project_name)

    def new_project(self):
        NewProjectDialog(self, on_project_created=self._handle_project_created)
