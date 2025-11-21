import flet as ft

class AppColors:
    """Palette colori centralizzata."""
    # Colori semantici che si adattano al tema (chiaro/scuro)
    # Nota: Flet gestisce automaticamente primary, secondary, ecc. in base al seed color.
    # Qui definiamo colori specifici per stati o elementi non coperti dal tema base.
    
    # Colori per stati (usando colori standard di Material Design)
    SUCCESS = ft.Colors.GREEN_600
    ERROR = ft.Colors.RED_600
    WARNING = ft.Colors.ORANGE_600
    INFO = ft.Colors.BLUE_600
    
    # Colori per testo secondario/disabilitato
    TEXT_SECONDARY = ft.Colors.ON_SURFACE_VARIANT
    TEXT_DISABLED = ft.Colors.OUTLINE
    
    # Colori per sfondi specifici
    SURFACE_VARIANT = "surfaceVariant"
    
    # Colori del tema (alias per comodità e coerenza)
    PRIMARY = "primary"
    ON_PRIMARY = "onPrimary"
    SECONDARY = "secondary"
    ON_SECONDARY = "onSecondary"

class AppStyles:
    """Stili riutilizzabili per componenti UI."""

    @staticmethod
    def card_container(content: ft.Control, padding: int = 15, on_click=None, data=None) -> ft.Container:
        """
        Crea un contenitore stile 'Card' standardizzato.
        """
        return ft.Container(
            content=content,
            padding=padding,
            border_radius=12,  # Bordi più arrotondati per un look moderno
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            bgcolor=ft.Colors.SURFACE, # Usa il colore surface del tema
            # Ombra leggera per dare profondità (opzionale, può appesantire se troppe card)
            # shadow=ft.BoxShadow(
            #     spread_radius=0,
            #     blur_radius=2,
            #     color=ft.Colors.with_opacity(0.1, ft.Colors.SHADOW),
            #     offset=ft.Offset(0, 1),
            # ),
            on_click=on_click,
            data=data,
            ink=True if on_click else False, # Effetto ripple se cliccabile
        )

    @staticmethod
    def header_text(text: str) -> ft.Text:
        return ft.Text(text, size=24, weight=ft.FontWeight.BOLD)

    @staticmethod
    def subheader_text(text: str, color: str = None) -> ft.Text:
        return ft.Text(text, size=18, weight=ft.FontWeight.W_600, color=color)

    @staticmethod
    def body_text(text: str, color: str = None) -> ft.Text:
        return ft.Text(text, size=14, color=color)

    @staticmethod
    def caption_text(text: str) -> ft.Text:
        return ft.Text(text, size=12, color=AppColors.TEXT_SECONDARY)
    
    @staticmethod
    def currency_text(value: float, loc_manager, size: int = 16) -> ft.Text:
        """Restituisce un testo formattato come valuta con colore verde/rosso."""
        color = AppColors.SUCCESS if value >= 0 else AppColors.ERROR
        return ft.Text(
            loc_manager.format_currency(value),
            size=size,
            weight=ft.FontWeight.BOLD,
            color=color
        )
