import customtkinter as ctk
from core.version import VERSION


class SettingsPage(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, fg_color="#202020")
        ctk.CTkLabel(self, text="Settings", font=("Segoe UI", 30, "bold")).pack(anchor="w", padx=44, pady=(38, 20))
        card = ctk.CTkFrame(self, corner_radius=16)
        card.pack(fill="x", padx=44)
        ctk.CTkLabel(card, text="Appearance", font=("Segoe UI", 19, "bold")).pack(anchor="w", padx=22, pady=(20, 6))
        mode = ctk.CTkOptionMenu(card, values=["Dark", "Light", "System"], command=lambda value: ctk.set_appearance_mode(value.lower()))
        mode.set("Dark")
        mode.pack(anchor="w", padx=22, pady=(0, 20))
        ctk.CTkLabel(self, text=f"KaiMi Studio  •  v{VERSION}", text_color="gray").pack(anchor="w", padx=48, pady=24)
