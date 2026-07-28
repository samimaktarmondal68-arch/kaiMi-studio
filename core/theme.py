"""Master Design System for KaiMi Studio v1.0.

Colors, typography, spacing, and component styles centralized here.
Design: premium desktop app inspired by Notion, Cursor, ChatGPT Desktop.
"""


class Dark:
    BG = "#101827"
    SIDEBAR = "#0F172A"
    CARD = "#1B2432"
    BORDER = "#263244"
    SURFACE = "#1B2432"
    DIVIDER = "#263244"

    PRIMARY = "#22C55E"
    PRIMARY_HOVER = "#16A34A"
    PRIMARY_LIGHT = "#0D231A"
    TEXT_ON_PRIMARY = "#FFFFFF"

    SECONDARY = "#38BDF8"
    SECONDARY_LIGHT = "#0C2230"

    SUCCESS = "#22C55E"
    SUCCESS_LIGHT = "#0D231A"

    WARNING = "#F59E0B"
    WARNING_LIGHT = "#251E15"

    ERROR = "#EF4444"
    ERROR_HOVER = "#B91C1C"
    ERROR_LIGHT = "#251212"

    INFO = "#38BDF8"
    INFO_LIGHT = "#0C2230"

    TEXT = "#F8FAFC"
    TEXT_SECONDARY = "#94A3B8"
    TEXT_MUTED = "#64748B"
    DISABLED_TEXT = "#64748B"

    INPUT_BG = "#1E293B"
    INPUT_BORDER = "#334155"
    INPUT_FOCUS = "#22C55E"

    HOVER = "#1E293B"
    ACTIVE_ITEM = "#0D231A"

    STAGE_SCRIPT = "#8B5CF6"
    STAGE_VOICE = "#06B6D4"
    STAGE_IMAGE_PROMPTS = "#F59E0B"
    STAGE_EXPORT = "#22C55E"

    GRADIENT_START = "#22C55E"
    GRADIENT_MID = "#16A34A"
    GRADIENT_END = "#38BDF8"

    SCROLLBAR = "#334155"
    SCROLLBAR_HOVER = "#475569"


class Light:
    BG = "#F8FAFC"
    SIDEBAR = "#FFFFFF"
    CARD = "#FFFFFF"
    BORDER = "#E5E7EB"
    SURFACE = "#F1F5F9"
    DIVIDER = "#E5E7EB"

    PRIMARY = "#22C55E"
    PRIMARY_HOVER = "#16A34A"
    PRIMARY_LIGHT = "#DCFCE7"
    TEXT_ON_PRIMARY = "#FFFFFF"

    SECONDARY = "#0EA5E9"
    SECONDARY_LIGHT = "#E0F2FE"

    SUCCESS = "#16A34A"
    SUCCESS_LIGHT = "#DCFCE7"

    WARNING = "#D97706"
    WARNING_LIGHT = "#FEF3C7"

    ERROR = "#DC2626"
    ERROR_HOVER = "#B91C1C"
    ERROR_LIGHT = "#FEE2E2"

    INFO = "#0EA5E9"
    INFO_LIGHT = "#E0F2FE"

    TEXT = "#111827"
    TEXT_SECONDARY = "#6B7280"
    TEXT_MUTED = "#9CA3AF"
    DISABLED_TEXT = "#9CA3AF"

    INPUT_BG = "#F1F5F9"
    INPUT_BORDER = "#D1D5DB"
    INPUT_FOCUS = "#22C55E"

    HOVER = "#F1F5F9"
    ACTIVE_ITEM = "#DCFCE7"

    STAGE_SCRIPT = "#8B5CF6"
    STAGE_VOICE = "#06B6D4"
    STAGE_IMAGE_PROMPTS = "#F59E0B"
    STAGE_EXPORT = "#22C55E"

    GRADIENT_START = "#22C55E"
    GRADIENT_MID = "#16A34A"
    GRADIENT_END = "#0EA5E9"

    SCROLLBAR = "#D1D5DB"
    SCROLLBAR_HOVER = "#9CA3AF"


class Fonts:
    FAMILY = "Segoe UI"
    FAMILY_ALT = "Inter"

    TITLE = (FAMILY, 32, "bold")
    SECTION = (FAMILY, 22, "semibold")
    CARD_TITLE = (FAMILY, 18, "medium")
    BODY = (FAMILY, 14)
    BODY_BOLD = (FAMILY, 14, "bold")
    SMALL = (FAMILY, 12)
    SMALL_BOLD = (FAMILY, 12, "bold")
    TINY = (FAMILY, 11)
    BUTTON = (FAMILY, 14, "bold")
    INPUT = (FAMILY, 14)
    HEADING = (FAMILY, 22, "semibold")

    @classmethod
    def css(cls, size, weight="normal", color=None, family=None):
        """Generate a CSS font string for use in stylesheets."""
        fam = family or cls.FAMILY
        parts = [f'font-family: "{fam}", sans-serif', f"font-size: {size}px", f"font-weight: {weight}"]
        if color:
            parts.append(f"color: {color}")
        return "; ".join(parts) + ";"

    @classmethod
    def display_title(cls, color=None):
        return cls.css(32, "bold", color)

    @classmethod
    def page_title(cls, color=None):
        return cls.css(28, "bold", color)

    @classmethod
    def section_title(cls, color=None):
        return cls.css(22, "600", color)

    @classmethod
    def card_title(cls, color=None):
        return cls.css(18, "600", color)

    @classmethod
    def subtitle(cls, color=None):
        return cls.css(16, "600", color)

    @classmethod
    def body(cls, color=None):
        return cls.css(14, "normal", color)

    @classmethod
    def body_bold(cls, color=None):
        return cls.css(14, "bold", color)

    @classmethod
    def caption(cls, color=None):
        return cls.css(12, "normal", color)

    @classmethod
    def caption_bold(cls, color=None):
        return cls.css(12, "bold", color)

    @classmethod
    def tiny(cls, color=None):
        return cls.css(11, "normal", color)

    @classmethod
    def label(cls, color=None):
        return cls.css(14, "500", color)

    @classmethod
    def section_label(cls, color=None):
        return cls.css(11, "600", color)


class Spacing:
    X1 = 4
    X2 = 8
    X3 = 12
    X4 = 16
    X6 = 24
    X8 = 32
    X10 = 40
    X12 = 48


class Radius:
    SM = 8
    MD = 12
    LG = 16
    XL = 20
    FULL = 9999


class Layout:
    WINDOW_WIDTH = 1600
    WINDOW_HEIGHT = 1000
    SIDEBAR_WIDTH = 240
    SIDEBAR_COLLAPSED = 64
    TOPBAR_HEIGHT = 56
    CARD_MIN_HEIGHT = 120


class Shadows:
    SM = "#080C18"
    MD = "#060A14"
    LG = "#040810"
    GLOW_PRIMARY = "#22C55E"


class Theme:
    dark = Dark
    light = Light
    fonts = Fonts
    spacing = Spacing
    radius = Radius
    layout = Layout
    shadows = Shadows

    STAGE_NAMES = ["Script", "Voice", "Image Prompts", "Export"]

    @classmethod
    def get_colors(cls, mode: str = "dark") -> type:
        if mode == "light":
            return Light
        return Dark

    @classmethod
    def get_stage_color(cls, colors_class, stage_name: str) -> str:
        attr = f"STAGE_{stage_name.upper().replace(' ', '_')}"
        return getattr(colors_class, attr, colors_class.PRIMARY)
