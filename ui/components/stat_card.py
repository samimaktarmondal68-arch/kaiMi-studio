import customtkinter as ctk


class StatCard(ctk.CTkFrame):
    def __init__(
        self,
        master,
        title: str,
        value: str,
        icon: str = "📊",
        subtitle: str = "",
        width: int = 250,
        height: int = 140,
    ) -> None:
        super().__init__(
            master=master,
            width=width,
            height=height,
            corner_radius=18,
            fg_color="#1E1E1E",
            border_width=1,
            border_color="#2E2E2E",
        )
        self.pack_propagate(False)

        self.icon_label: ctk.CTkLabel = ctk.CTkLabel(
            self,
            text=icon,
            font=("Segoe UI", 24),
            text_color="#FFFFFF",
            fg_color="transparent",
        )
        self.icon_label.pack(anchor="center", pady=(12, 8))

        self.value_label: ctk.CTkLabel = ctk.CTkLabel(
            self,
            text=value,
            font=("Segoe UI", 28, "bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
        )
        self.value_label.pack(anchor="center", pady=(0, 8))

        self.title_label: ctk.CTkLabel = ctk.CTkLabel(
            self,
            text=title,
            font=("Segoe UI", 14, "bold"),
            text_color="#E6E6E6",
            fg_color="transparent",
        )
        self.title_label.pack(anchor="center")

        self.subtitle_label: ctk.CTkLabel = ctk.CTkLabel(
            self,
            text=subtitle,
            font=("Segoe UI", 11),
            text_color="#8A8A8A",
            fg_color="transparent",
        )
        self.subtitle_label.pack(anchor="center", pady=(4, 0))
        if not subtitle:
            self.subtitle_label.pack_forget()

    def set_value(self, value: str) -> None:
        self.value_label.configure(text=value)

    def set_title(self, title: str) -> None:
        self.title_label.configure(text=title)

    def set_subtitle(self, text: str) -> None:
        self.subtitle_label.configure(text=text)
        if text:
            if not self.subtitle_label.winfo_ismapped():
                self.subtitle_label.pack(anchor="center", pady=(4, 0))
        else:
            self.subtitle_label.pack_forget()

    def set_icon(self, icon: str) -> None:
        self.icon_label.configure(text=icon)
