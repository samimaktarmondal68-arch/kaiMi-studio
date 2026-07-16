import customtkinter as ctk


class KButton(ctk.CTkButton):

    def __init__(self, master, text="", command=None):

        super().__init__(
            master,
            text=text,
            command=command,
            height=48,
            corner_radius=15,
            font=("Segoe UI", 15, "bold")
        )


class KLabel(ctk.CTkLabel):

    def __init__(self, master, text="", size=18):

        super().__init__(
            master,
            text=text,
            font=("Segoe UI", size, "bold")
        )


class KFrame(ctk.CTkFrame):

    def __init__(self, master):

        super().__init__(
            master,
            corner_radius=18
        )