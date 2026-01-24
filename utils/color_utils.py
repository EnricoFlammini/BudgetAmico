
import flet as ft
import hashlib

def get_color_from_string(input_str: str) -> str:
    """
    Generates a consistent Material color from a string input.
    Uses md_colors (Material Design colors) to pick a nice color.
    """
# Simply pick from a curated list of nice dark/vibrant colors
MATERIAL_COLORS = [
    # Mixed order for better variety when assigning sequentially
    ft.Colors.RED_700,
    ft.Colors.BLUE_700,
    ft.Colors.GREEN_700,
    ft.Colors.ORANGE_800,
    ft.Colors.PURPLE_700,
    ft.Colors.TEAL_700,
    ft.Colors.PINK_700,
    ft.Colors.INDIGO_700,
    ft.Colors.AMBER_900,
    ft.Colors.CYAN_800,
    ft.Colors.DEEP_ORANGE_800,
    ft.Colors.LIGHT_BLUE_800,
    ft.Colors.LIME_900,
    ft.Colors.BLUE_GREY_700,
    ft.Colors.DEEP_PURPLE_700,
    ft.Colors.BROWN_700,
    
    # Second Pass (Lighter/Different Shades)
    ft.Colors.RED_900,
    ft.Colors.BLUE_900,
    ft.Colors.GREEN_900,
    ft.Colors.ORANGE_900,
    ft.Colors.PURPLE_900,
    ft.Colors.TEAL_900,
    ft.Colors.PINK_900,
    ft.Colors.INDIGO_900,
    ft.Colors.YELLOW_900,
    ft.Colors.CYAN_900,
    ft.Colors.DEEP_ORANGE_900,
    ft.Colors.LIGHT_BLUE_900,
    ft.Colors.LIGHT_GREEN_900,
    ft.Colors.BLUE_GREY_900,
    ft.Colors.DEEP_PURPLE_900,
    ft.Colors.BROWN_800,

    # Accents
    ft.Colors.RED_ACCENT_700,
    ft.Colors.BLUE_ACCENT_700,
    ft.Colors.AMBER_800, # Amber instead of Green Accent which is too bright
    ft.Colors.PURPLE_ACCENT_700,
    ft.Colors.PINK_ACCENT_700,
    ft.Colors.DEEP_PURPLE_ACCENT_700,
    ft.Colors.INDIGO_ACCENT_700,
    ft.Colors.TEAL_ACCENT_700,
    ft.Colors.DEEP_ORANGE_ACCENT_700,
]

def get_color_from_string(input_str: str) -> str:
    """
    Generates a consistent Material color from a string input.
    Uses md_colors (Material Design colors) to pick a nice color.
    """
    if not input_str:
        return ft.Colors.BLUE_GREY_700
        
    # Simple hash
    hash_val = int(hashlib.md5(input_str.encode()).hexdigest(), 16)
    return MATERIAL_COLORS[hash_val % len(MATERIAL_COLORS)]

def get_type_color(tipo: str) -> str:
    """
    Returns a specific color for an account/card type.
    """
    tipo = tipo.lower()
    
    if "contanti" in tipo:
        return ft.Colors.GREEN_ACCENT_400
    elif "corrente" in tipo:
        return ft.Colors.BLUE_ACCENT_400
    elif "risparmio" in tipo or "deposito" in tipo:
        return ft.Colors.AMBER_ACCENT_400
    elif "investimento" in tipo:
        return ft.Colors.PURPLE_ACCENT_400
    elif "credito" in tipo:
        return ft.Colors.RED_ACCENT_400
    elif "debito" in tipo or "prepagata" in tipo:
        return ft.Colors.CYAN_ACCENT_400
    else:
        return ft.Colors.GREY_400
