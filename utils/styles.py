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
    def currency_text(text: str, color: str = None, size: int = 16) -> ft.Text:
        """Restituisce un testo formattato come valuta con stile bold.
        
        Args:
            text: Il testo già formattato (es. "€ 1.234,56")
            color: Colore opzionale. Se None, usa SUCCESS (verde)
            size: Dimensione del font (default 16)
        """
        if color is None:
            color = AppColors.SUCCESS
        return ft.Text(
            text,
            size=size,
            weight=ft.FontWeight.BOLD,
            color=color
        )
    
    @staticmethod
    def big_currency_text(text: str, color: str = None) -> ft.Text:
        """Restituisce un testo grande per patrimonio netto con stile bold.
        
        Args:
            text: Il testo già formattato (es. "€ 1.234,56")
            color: Colore opzionale. Se None, usa SUCCESS (verde)
        """
        if color is None:
            color = AppColors.SUCCESS
        return ft.Text(
            text,
            size=28,
            weight=ft.FontWeight.BOLD,
            color=color
        )


class LoadingOverlay(ft.Container):
    """
    Overlay modale di caricamento.
    Mostra uno spinner circolare con un messaggio personalizzabile.
    Sfondo trasparente con rettangolo opaco al centro.
    """
    
    def __init__(self, messaggio: str = "Attendere..."):
        self.messaggio_text = ft.Text(
            messaggio, 
            size=16, 
            weight=ft.FontWeight.W_500,
            color=ft.Colors.WHITE
        )
        
        # Rettangolo opaco centrale con spinner e messaggio
        self.spinner_box = ft.Container(
            content=ft.Column(
                [
                    ft.ProgressRing(
                        width=50,
                        height=50,
                        stroke_width=4,
                        color=ft.Colors.WHITE
                    ),
                    ft.Container(height=15),
                    self.messaggio_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            width=200,
            height=150,
            padding=20,
            border_radius=15,
            bgcolor=ft.Colors.with_opacity(0.92, ft.Colors.BLACK),
            shadow=ft.BoxShadow(
                spread_radius=2,
                blur_radius=20,
                color=ft.Colors.with_opacity(0.5, ft.Colors.BLACK),
            ),
        )
        
        super().__init__(
            content=self.spinner_box,
            alignment=ft.alignment.center,
            expand=True,
        )
        self.visible = False
    
    def show(self, messaggio: str = None):
        """Mostra l'overlay con un messaggio opzionale."""
        if messaggio:
            self.messaggio_text.value = messaggio
        self.visible = True
    
    def hide(self):
        """Nasconde l'overlay."""
        self.visible = False
