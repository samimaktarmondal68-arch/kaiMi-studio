# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Dialogs for KaiMi Studio.

Contains NewProjectDialog, VersionHistoryDialog, and FirstRunDialog.
"""

import customtkinter as ctk

from core.theme import Dark, Fonts, Radius, Spacing
from core.version import APP_NAME, VERSION, CODENAME


class FirstRunDialog(ctk.CTkToplevel):

    def __init__(self, master, on_close=None):
        super().__init__(master)

        self.title(f"Welcome to {APP_NAME}")
        self.geometry("520x580")
        self.resizable(False, False)
        self.configure(fg_color=Dark.BG)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

        self._on_close_callback = on_close
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(
            self, fg_color=Dark.BG,
            scrollbar_button_color=Dark.BORDER,
            scrollbar_button_hover_color=Dark.TEXT_MUTED,
        )
        scroll.pack(fill="both", expand=True)

        # Header
        ctk.CTkLabel(
            scroll, text=f"Welcome to {APP_NAME}",
            font=Fonts.HEADING, text_color=Dark.PRIMARY,
        ).pack(padx=Spacing.X8, pady=(Spacing.X8, Spacing.X2))

        ctk.CTkLabel(
            scroll, text=f"v{VERSION} \u2014 {CODENAME}",
            font=Fonts.BODY, text_color=Dark.TEXT_SECONDARY,
        ).pack(padx=Spacing.X8, pady=(0, Spacing.X6))

        # Steps
        steps = [
            ("\U0001F3E0", "Create a Project", "Start from the Dashboard. Give your project a name, topic, and language."),
            ("\U0001F50D", "Select a Provider", "Go to Settings and configure your AI provider (Gemini, OpenAI, etc.)."),
            ("\U0001F9E0", "Generate Research", "Open your project and let AI research your topic automatically."),
            ("\U0001F4DD", "Write the Script", "The AI will create a structured script based on the research."),
            ("\U0001F3AC", "Build Storyboard", "Generate scene-by-scene visual breakdowns."),
            ("\U0001F5BC\uFE0F", "Create Image Prompts", "Get detailed prompts for each scene illustration."),
            ("\U0001F4E4", "Export", "Download your completed project as TXT, PDF, DOCX, or ZIP."),
        ]

        for icon, title, desc in steps:
            card = ctk.CTkFrame(
                scroll, fg_color=Dark.CARD, corner_radius=Radius.MD,
                border_width=1, border_color=Dark.BORDER, height=60,
            )
            card.pack(fill="x", padx=Spacing.X8, pady=(0, Spacing.X3))
            card.pack_propagate(False)

            inner = ctk.CTkFrame(card, fg_color="transparent")
            inner.pack(fill="both", expand=True, padx=Spacing.X4, pady=Spacing.X3)

            icon_bg = ctk.CTkFrame(inner, width=32, height=32, corner_radius=Radius.SM, fg_color=Dark.SURFACE)
            icon_bg.pack(side="left", padx=(0, Spacing.X3))
            icon_bg.pack_propagate(False)
            ctk.CTkLabel(icon_bg, text=icon, font=(Fonts.FAMILY, 14), fg_color="transparent").pack(expand=True)

            text_col = ctk.CTkFrame(inner, fg_color="transparent")
            text_col.pack(side="left", fill="both", expand=True)

            ctk.CTkLabel(
                text_col, text=title,
                font=Fonts.CARD_TITLE, text_color=Dark.TEXT,
            ).pack(anchor="w")

            ctk.CTkLabel(
                text_col, text=desc,
                font=Fonts.SMALL, text_color=Dark.TEXT_SECONDARY,
            ).pack(anchor="w")

        # Keyboard shortcuts hint
        ctk.CTkLabel(
            scroll, text="Tip: Press Ctrl+K to search projects, Ctrl+S to save.",
            font=Fonts.SMALL, text_color=Dark.TEXT_MUTED,
        ).pack(padx=Spacing.X8, pady=(Spacing.X4, Spacing.X3))

        # Buttons
        btn_frame = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_frame.pack(fill="x", padx=Spacing.X8, pady=(Spacing.X2, Spacing.X8))

        ctk.CTkButton(
            btn_frame, text="Don't show again",
            font=Fonts.BODY, fg_color=Dark.SURFACE,
            hover_color=Dark.HOVER, text_color=Dark.TEXT_SECONDARY,
            height=38, corner_radius=Radius.MD,
            command=self._on_close,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="Get Started",
            font=Fonts.BODY_BOLD, fg_color=Dark.PRIMARY,
            hover_color=Dark.PRIMARY_HOVER, text_color="#FFFFFF",
            height=38, corner_radius=Radius.MD,
            command=self._on_close,
        ).pack(side="right")

    def _on_close(self):
        if self._on_close_callback:
            self._on_close_callback()
        self.grab_release()
        self.destroy()


class NewProjectDialog(ctk.CTkToplevel):

    def __init__(self, master, on_project_created=None):
        super().__init__(master)

        self.title("New Project")
        self.geometry("480x520")
        self.resizable(False, False)
        self.configure(fg_color=Dark.BG)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self._on_project_created = on_project_created
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="Create New Project",
            font=Fonts.HEADING, text_color=Dark.PRIMARY,
        ).pack(padx=Spacing.X8, pady=(Spacing.X8, Spacing.X2))

        ctk.CTkLabel(
            self, text="Fill in the details to start a new project.",
            font=Fonts.BODY, text_color=Dark.TEXT_SECONDARY,
        ).pack(padx=Spacing.X8, pady=(0, Spacing.X6))

        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(fill="x", padx=Spacing.X8)

        ctk.CTkLabel(form, text="Project Name", font=Fonts.SMALL_BOLD, text_color=Dark.TEXT).pack(anchor="w")
        self._name_entry = ctk.CTkEntry(
            form, placeholder_text="e.g. Photosynthesis Explained",
            font=Fonts.INPUT, fg_color=Dark.INPUT_BG, border_color=Dark.INPUT_BORDER,
            text_color=Dark.TEXT, height=38, corner_radius=Radius.MD,
        )
        self._name_entry.pack(fill="x", pady=(Spacing.X1, Spacing.X3))

        ctk.CTkLabel(form, text="Topic", font=Fonts.SMALL_BOLD, text_color=Dark.TEXT).pack(anchor="w")
        self._topic_entry = ctk.CTkEntry(
            form, placeholder_text="e.g. Photosynthesis for middle school",
            font=Fonts.INPUT, fg_color=Dark.INPUT_BG, border_color=Dark.INPUT_BORDER,
            text_color=Dark.TEXT, height=38, corner_radius=Radius.MD,
        )
        self._topic_entry.pack(fill="x", pady=(Spacing.X1, Spacing.X3))

        row = ctk.CTkFrame(form, fg_color="transparent")
        row.pack(fill="x", pady=(0, Spacing.X1))

        lang_col = ctk.CTkFrame(row, fg_color="transparent")
        lang_col.pack(side="left", fill="x", expand=True, padx=(0, Spacing.X2))
        ctk.CTkLabel(lang_col, text="Language", font=Fonts.SMALL_BOLD, text_color=Dark.TEXT).pack(anchor="w")
        self._language_menu = ctk.CTkOptionMenu(
            lang_col, values=["English", "Chinese", "Spanish", "French", "German", "Japanese"],
            font=Fonts.INPUT, fg_color=Dark.INPUT_BG, button_color=Dark.BORDER,
            button_hover_color=Dark.HOVER, text_color=Dark.TEXT, height=38, corner_radius=Radius.MD,
        )
        self._language_menu.pack(fill="x")

        style_col = ctk.CTkFrame(row, fg_color="transparent")
        style_col.pack(side="left", fill="x", expand=True, padx=(Spacing.X2, 0))
        ctk.CTkLabel(style_col, text="Style", font=Fonts.SMALL_BOLD, text_color=Dark.TEXT).pack(anchor="w")
        self._style_menu = ctk.CTkOptionMenu(
            style_col, values=["Educational", "Entertaining", "Documentary", "Tutorial", "Storytelling"],
            font=Fonts.INPUT, fg_color=Dark.INPUT_BG, button_color=Dark.BORDER,
            button_hover_color=Dark.HOVER, text_color=Dark.TEXT, height=38, corner_radius=Radius.MD,
        )
        self._style_menu.pack(fill="x")

        self._error_label = ctk.CTkLabel(
            self, text="", font=Fonts.SMALL, text_color=Dark.ERROR,
        )
        self._error_label.pack(padx=Spacing.X8, pady=(Spacing.X2, 0))

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=Spacing.X8, pady=Spacing.X8)

        ctk.CTkButton(
            btn_frame, text="Cancel", width=100,
            font=Fonts.BODY, fg_color=Dark.SURFACE,
            hover_color=Dark.HOVER, text_color=Dark.TEXT_SECONDARY,
            height=38, corner_radius=Radius.MD,
            command=self._cancel,
        ).pack(side="left")

        ctk.CTkButton(
            btn_frame, text="Create Project", width=140,
            font=Fonts.BODY_BOLD, fg_color=Dark.PRIMARY,
            hover_color=Dark.PRIMARY_HOVER, text_color="#FFFFFF",
            height=38, corner_radius=Radius.MD,
            command=self._create,
        ).pack(side="right")

        self._name_entry.focus_set()
        self.bind("<Return>", lambda e: self._create())
        self.bind("<Escape>", lambda e: self._cancel())

    def _create(self):
        name = self._name_entry.get().strip()
        topic = self._topic_entry.get().strip()
        language = self._language_menu.get()
        style = self._style_menu.get()

        if not name:
            self._error_label.configure(text="Project name is required.")
            return
        if not topic:
            self._error_label.configure(text="Topic is required.")
            return

        try:
            from core.project_manager import ProjectManager
            pm = ProjectManager()
            pm.create_project(name, topic, language, style)
        except ValueError as e:
            self._error_label.configure(text=str(e))
            return
        except FileExistsError as e:
            self._error_label.configure(text=str(e))
            return

        self.grab_release()
        self.destroy()
        if self._on_project_created:
            self._on_project_created(name)

    def _cancel(self):
        self.grab_release()
        self.destroy()


class VersionHistoryDialog(ctk.CTkToplevel):

    def __init__(self, master, project_name: str):
        super().__init__(master)

        self.title(f"Version History — {project_name}")
        self.geometry("600x520")
        self.configure(fg_color=Dark.BG)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._close)

        self._project_name = project_name
        self._build()
        self._load_snapshots()

    def _build(self):
        ctk.CTkLabel(
            self, text=f"Version History",
            font=Fonts.HEADING, text_color=Dark.PRIMARY,
        ).pack(padx=Spacing.X8, pady=(Spacing.X8, Spacing.X2))

        ctk.CTkLabel(
            self, text=f"Project: {self._project_name}",
            font=Fonts.BODY, text_color=Dark.TEXT_SECONDARY,
        ).pack(padx=Spacing.X8, pady=(0, Spacing.X4))

        self._stage_menu = ctk.CTkOptionMenu(
            self, values=["Research", "Script", "Storyboard", "Image Prompts"],
            font=Fonts.INPUT, fg_color=Dark.INPUT_BG, button_color=Dark.BORDER,
            button_hover_color=Dark.HOVER, text_color=Dark.TEXT,
            height=36, corner_radius=Radius.MD, command=self._on_stage_change,
        )
        self._stage_menu.pack(padx=Spacing.X8, pady=(0, Spacing.X3))

        self._list_frame = ctk.CTkScrollableFrame(
            self, fg_color=Dark.SURFACE,
            scrollbar_button_color=Dark.BORDER,
            scrollbar_button_hover_color=Dark.TEXT_MUTED,
        )
        self._list_frame.pack(fill="both", expand=True, padx=Spacing.X8, pady=(0, Spacing.X3))

        self._empty_label = ctk.CTkLabel(
            self._list_frame, text="No snapshots yet.",
            font=Fonts.BODY, text_color=Dark.TEXT_MUTED,
        )

        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=Spacing.X8, pady=Spacing.X4)

        ctk.CTkButton(
            btn_frame, text="Close", width=100,
            font=Fonts.BODY, fg_color=Dark.SURFACE,
            hover_color=Dark.HOVER, text_color=Dark.TEXT_SECONDARY,
            height=36, corner_radius=Radius.MD,
            command=self._close,
        ).pack(side="right")

    def _load_snapshots(self):
        for widget in self._list_frame.winfo_children():
            widget.destroy()

        stage = self._stage_menu.get()
        from core.history_manager import HistoryManager
        hm = HistoryManager()
        snapshots = hm.list_snapshots(self._project_name, stage)

        if not snapshots:
            self._empty_label = ctk.CTkLabel(
                self._list_frame, text="No snapshots yet.",
                font=Fonts.BODY, text_color=Dark.TEXT_MUTED,
            )
            self._empty_label.pack(pady=Spacing.X8)
            return

        for snap in snapshots:
            row = ctk.CTkFrame(
                self._list_frame, fg_color=Dark.CARD, corner_radius=Radius.SM,
                border_width=1, border_color=Dark.BORDER, height=50,
            )
            row.pack(fill="x", pady=(0, Spacing.X2))
            row.pack_propagate(False)

            info = ctk.CTkFrame(row, fg_color="transparent")
            info.pack(side="left", fill="both", expand=True, padx=Spacing.X3)

            ctk.CTkLabel(
                info, text=snap["created"],
                font=Fonts.BODY_BOLD, text_color=Dark.TEXT,
            ).pack(anchor="w")

            ctk.CTkLabel(
                info, text=snap["filename"],
                font=Fonts.TINY, text_color=Dark.TEXT_MUTED,
            ).pack(anchor="w")

            restore_btn = ctk.CTkButton(
                row, text="Restore", width=70, height=28,
                font=Fonts.SMALL, fg_color=Dark.PRIMARY,
                hover_color=Dark.PRIMARY_HOVER, text_color="#FFFFFF",
                corner_radius=Radius.SM,
                command=lambda s=stage, f=snap["filename"]: self._restore(s, f),
            )
            restore_btn.pack(side="right", padx=Spacing.X2)

            delete_btn = ctk.CTkButton(
                row, text="Delete", width=60, height=28,
                font=Fonts.SMALL, fg_color=Dark.ERROR,
                hover_color="#DC2626", text_color="#FFFFFF",
                corner_radius=Radius.SM,
                command=lambda s=stage, f=snap["filename"]: self._delete(s, f),
            )
            delete_btn.pack(side="right")

    def _on_stage_change(self, _choice):
        self._load_snapshots()

    def _restore(self, stage, filename):
        from core.history_manager import HistoryManager
        from core.notifications import NotificationService
        hm = HistoryManager()
        data = hm.restore_snapshot(self._project_name, stage, filename)
        if data:
            NotificationService.get().success(f"Restored {stage} snapshot.")
            self._load_snapshots()
        else:
            NotificationService.get().error("Failed to restore snapshot.")

    def _delete(self, stage, filename):
        from core.history_manager import HistoryManager
        from core.notifications import NotificationService
        hm = HistoryManager()
        if hm.delete_snapshot(self._project_name, stage, filename):
            NotificationService.get().info("Snapshot deleted.")
            self._load_snapshots()

    def _close(self):
        self.grab_release()
        self.destroy()
