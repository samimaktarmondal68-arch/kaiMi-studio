import customtkinter as ctk


class SectionHeader(ctk.CTkFrame):
    def __init__(
        self,
        master,
        title: str,
        subtitle: str = "",
    ) -> None:
        super().__init__(master=master, fg_color="transparent")
        self.pack_propagate(False)

        self.title_label: ctk.CTkLabel = ctk.CTkLabel(
            self,
            text=title,
            font=("Segoe UI", 22, "bold"),
            text_color="#FFFFFF",
            fg_color="transparent",
        )
        self.title_label.pack(anchor="w")

        self.subtitle_label: ctk.CTkLabel = ctk.CTkLabel(
            self,
            text=subtitle,
            font=("Segoe UI", 14),
            text_color="gray",
            fg_color="transparent",
        )
        self.subtitle_label.pack(anchor="w", pady=(4, 0))
        if not subtitle:
            self.subtitle_label.pack_forget()

    def set_title(self, title: str) -> None:
        self.title_label.configure(text=title)

    def set_subtitle(self, text: str) -> None:
        self.subtitle_label.configure(text=text)
        if text:
            if not self.subtitle_label.winfo_ismapped():
                self.subtitle_label.pack(anchor="w", pady=(4, 0))
        else:
            self.subtitle_label.pack_forget()
