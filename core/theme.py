"""Master Design System for KaiMi Studio.

This module defines the permanent visual language for the entire application.
Colors, typography, spacing, and component styles are all centralized here.

Design Philosophy:
    Modern. Minimal. Premium. Professional. Futuristic. Elegant.

    Inspired by Cursor, Linear, Arc Browser, Raycast, ChatGPT Desktop, Notion.
"""


class Dark:
    """Dark mode color palette."""

    BG = "#070B16"
    SIDEBAR = "#0C1224"
    CARD = "#111827"
    BORDER = "#1D2740"
    SURFACE = "#0F1729"

    PRIMARY = "#6D4AFF"
    PRIMARY_HOVER = "#7E5EFF"
    PRIMARY_LIGHT = "#6D4AFF20"

    SECONDARY = "#4DA8FF"
    SECONDARY_LIGHT = "#4DA8FF20"

    SUCCESS = "#22C55E"
    SUCCESS_LIGHT = "#22C55E20"

    WARNING = "#F59E0B"
    WARNING_LIGHT = "#F59E0B20"

    ERROR = "#EF4444"
    ERROR_LIGHT = "#EF444420"

    TEXT = "#F8FAFC"
    TEXT_SECONDARY = "#94A3B8"
    TEXT_MUTED = "#64748B"

    INPUT_BG = "#1E293B"
    INPUT_BORDER = "#334155"
    INPUT_FOCUS = "#6D4AFF"

    HOVER = "#1A2332"
    ACTIVE_ITEM = "#6D4AFF18"

    GRADIENT_START = "#6D4AFF"
    GRADIENT_MID = "#8B5CF6"
    GRADIENT_END = "#4DA8FF"


class Light:
    """Light mode color palette."""

    BG = "#F6F8FC"
    SIDEBAR = "#EEF2F8"
    CARD = "#FFFFFF"
    BORDER = "#E2E8F0"
    SURFACE = "#F8FAFC"

    PRIMARY = "#6D4AFF"
    PRIMARY_HOVER = "#5A3AE0"
    PRIMARY_LIGHT = "#6D4AFF12"

    SECONDARY = "#4DA8FF"
    SECONDARY_LIGHT = "#4DA8FF12"

    SUCCESS = "#16A34A"
    SUCCESS_LIGHT = "#16A34A12"

    WARNING = "#D97706"
    WARNING_LIGHT = "#D9770612"

    ERROR = "#DC2626"
    ERROR_LIGHT = "#DC262612"

    TEXT = "#0F172A"
    TEXT_SECONDARY = "#64748B"
    TEXT_MUTED = "#94A3B8"

    INPUT_BG = "#F1F5F9"
    INPUT_BORDER = "#CBD5E1"
    INPUT_FOCUS = "#6D4AFF"

    HOVER = "#F1F5F9"
    ACTIVE_ITEM = "#6D4AFF10"

    GRADIENT_START = "#6D4AFF"
    GRADIENT_MID = "#8B5CF6"
    GRADIENT_END = "#4DA8FF"


class Fonts:
    """Typography system. Inter primary, Segoe UI fallback."""

    FAMILY = "Segoe UI"
    FAMILY_ALT = "Inter"

    TITLE = (FAMILY, 32, "bold")
    SECTION = (FAMILY, 22, "bold")
    CARD_TITLE = (FAMILY, 18, "bold")
    BODY = (FAMILY, 15)
    BODY_BOLD = (FAMILY, 15, "bold")
    SMALL = (FAMILY, 13)
    SMALL_BOLD = (FAMILY, 13, "bold")
    TINY = (FAMILY, 11)
    BUTTON = (FAMILY, 14, "bold")
    INPUT = (FAMILY, 14)


class Spacing:
    """8-point spacing system."""

    X1 = 4
    X2 = 8
    X3 = 12
    X4 = 16
    X5 = 20
    X6 = 24
    X7 = 28
    X8 = 32
    X10 = 40
    X12 = 48
    X14 = 56


class Radius:
    """Border radius constants."""

    SM = 8
    MD = 12
    LG = 16
    XL = 20
    FULL = 9999


class Layout:
    """Layout dimensions."""

    WINDOW_WIDTH = 1600
    WINDOW_HEIGHT = 1000
    SIDEBAR_WIDTH = 240
    SIDEBAR_COLLAPSED = 64
    TOPBAR_HEIGHT = 56
    CARD_MIN_HEIGHT = 120


class Shadows:
    """Shadow colors for different elevation levels."""

    SM = "#080C18"
    MD = "#060A14"
    LG = "#040810"
    GLOW_PRIMARY = "#6D4AFF"


class Theme:
    """Unified theme accessor.

    Usage:
        Theme.dark.BG
        Theme.fonts.TITLE
        Theme.spacing.X4
    """

    dark = Dark
    light = Light
    fonts = Fonts
    spacing = Spacing
    radius = Radius
    layout = Layout
    shadows = Shadows

    @classmethod
    def get_colors(cls, mode: str = "dark") -> type:
        """Return Dark or Light palette based on mode string."""
        if mode == "light":
            return Light
        return Dark
