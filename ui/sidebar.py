import customtkinter as ctk


class Sidebar(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(
            master,
            width=260,
            fg_color="#161616",
            corner_radius=0
        )

        self.pack_propagate(False)

        title = ctk.CTkLabel(

            self,

            text="KaiMi Studio",

            font=("Segoe UI",24,"bold")

        )

        title.pack(pady=(40,30))

        buttons = [
    "Dashboard",
    "Video Projects",
    "AI Workspace",
    "Assets",
    "Export",
    "Settings",
]
        

        for text in buttons:

            btn = ctk.CTkButton(

                self,

                text=text,

                width=200,

                height=42,

                corner_radius=12

            )

            btn.pack(pady=7)