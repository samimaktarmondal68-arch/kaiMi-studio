# Copyright 2026 KaiMi. All Rights Reserved.
# This file is proprietary software. Unauthorized copying, modification
# or redistribution is prohibited.
"""Toast notification system for KaiMi Studio.

Bottom-right stacked notifications with auto-dismiss and animation.
"""

import customtkinter as ctk
from core.theme import Dark, Fonts, Radius, Spacing


class NotificationService:
    _instance = None
    _notifications: list = []

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self._root = None
        self._container = None

    def set_root(self, root):
        self._root = root
        NotificationService._notifications.clear()
        if self._container is not None:
            self._container.destroy()
        self._container = ctk.CTkFrame(root, fg_color="transparent")
        self._container.place(relx=1.0, rely=1.0, x=-Spacing.X5, y=-Spacing.X5, anchor="se")

    def show(self, message: str, notification_type: str = "info", duration: int = 3000):
        if self._container is None:
            return

        colors = {
            "success": (Dark.SUCCESS, "#0F291A", "\u2714"),
            "warning": (Dark.WARNING, "#2A1F0A", "\u26A0"),
            "error": (Dark.ERROR, "#2A1215", "\u2716"),
            "info": (Dark.PRIMARY, "#1A1535", "\u2139"),
        }
        accent, bg, icon = colors.get(notification_type, colors["info"])

        toast = ctk.CTkFrame(
            self._container,
            fg_color=Dark.CARD,
            corner_radius=Radius.MD,
            border_width=1,
            border_color=Dark.BORDER,
            width=340,
        )
        toast.pack(fill="x", pady=Spacing.X1)

        inner = ctk.CTkFrame(toast, fg_color="transparent")
        inner.pack(fill="x", padx=Spacing.X4, pady=Spacing.X3)

        icon_label = ctk.CTkLabel(
            inner, text=icon, font=(Fonts.FAMILY, 14),
            text_color=accent, width=24,
        )
        icon_label.pack(side="left", padx=(0, Spacing.X2))

        msg = ctk.CTkLabel(
            inner, text=message, font=Fonts.SMALL,
            text_color=Dark.TEXT, anchor="w", wraplength=260,
        )
        msg.pack(side="left", fill="both", expand=True)

        close_btn = ctk.CTkButton(
            inner, text="\u2715", width=20, height=20,
            fg_color="transparent", hover_color=Dark.HOVER,
            text_color=Dark.TEXT_MUTED, font=(Fonts.FAMILY, 10),
            command=lambda: self._dismiss(toast),
        )
        close_btn.pack(side="right")

        accent_bar = ctk.CTkFrame(toast, fg_color=accent, height=2, corner_radius=1)
        accent_bar.pack(fill="x", padx=Spacing.X4, pady=(0, Spacing.X2))

        NotificationService._notifications.append(toast)
        self._reposition()

        toast.after(duration, lambda: self._dismiss(toast))

        toast.configure(fg_color=Dark.CARD)
        toast.after(10, lambda: toast.configure(fg_color=Dark.CARD))

    def _dismiss(self, toast):
        if toast in NotificationService._notifications:
            NotificationService._notifications.remove(toast)
            toast.after(150, lambda: self._safe_destroy(toast))
            self._reposition()

    def _safe_destroy(self, widget):
        try:
            widget.destroy()
        except Exception:
            pass

    def _reposition(self):
        for i, toast in enumerate(NotificationService._notifications):
            try:
                toast.pack_forget()
                toast.pack(fill="x", pady=Spacing.X1)
            except Exception:
                pass

    def success(self, message: str, duration: int = 3000):
        self.show(message, "success", duration)

    def warning(self, message: str, duration: int = 4000):
        self.show(message, "warning", duration)

    def error(self, message: str, duration: int = 5000):
        self.show(message, "error", duration)

    def info(self, message: str, duration: int = 3000):
        self.show(message, "info", duration)
