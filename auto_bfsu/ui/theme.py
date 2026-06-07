import customtkinter as ctk

# ====================================================================
# AutoBFSU Unified Styling Design System (Design Tokens)
# ====================================================================

# Premium iOS-style Dark Mode Color Palette
COLOR_BG = "#1C1C1E"              # Deep dark background
COLOR_CARD = "#2C2C2E"            # Card/Panel background
COLOR_BORDER = "#3A3A3C"          # Thin border lines

COLOR_TEXT_PRIMARY = "#FFFFFF"
COLOR_TEXT_SECONDARY = "#8E8E93"  # Standard Gray
COLOR_TEXT_LIGHT = "#E5E5EA"
COLOR_TEXT_MUTED = "#D1D1D6"

COLOR_ACCENT = "#0A84FF"          # Bright iOS Blue
COLOR_ACCENT_HOVER = "#0066CC"

# Category-specific indicator colors
COLOR_BLUE = "#3A86FF"
COLOR_RED = "#FF453A"
COLOR_ORANGE = "#FF9F0A"

# Font definitions
FONT_FAMILY = "Microsoft YaHei"

def get_font(size=13, weight="normal"):
    """Factory helper to generate CTkFonts consistently."""
    return ctk.CTkFont(family=FONT_FAMILY, size=size, weight=weight)
