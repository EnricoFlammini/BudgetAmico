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


class PageConstants:
    """Costanti per layout standard delle pagine."""
    # Padding standard per tutti i tab
    PAGE_PADDING = ft.padding.only(left=10, top=10, right=10, bottom=80)
    # Spaziatura tra sezioni
    SECTION_SPACING = 10
    # Padding per le card
    CARD_PADDING = 15
    # Border radius per le card
    CARD_BORDER_RADIUS = 12

class AppStyles:
    """Stili riutilizzabili per componenti UI."""

    @staticmethod
    def card_container(content: ft.Control, padding: int = 15, on_click=None, data=None, width: int = None, height: int = None) -> ft.Container:
        """
        Crea un contenitore stile 'Card' standardizzato.
        """
        return ft.Container(
            content=content,
            padding=padding,
            width=width,
            height=height,
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
    def title_text(text: str, color: str = None, **kwargs) -> ft.Text:
        """Titoli principali delle pagine (es. 'Budget & Analisi')."""
        return ft.Text(text, size=24, weight=ft.FontWeight.BOLD, color=color, font_family="Roboto", **kwargs)

    @staticmethod
    def section_header_text(text: str, color: str = None, **kwargs) -> ft.Text:
        """Intestazioni di sezione (es. 'Ultime Transazioni')."""
        return ft.Text(text, size=20, weight=ft.FontWeight.BOLD, color=color, font_family="Roboto", **kwargs)

    @staticmethod
    def subheader_text(text: str, color: str = None, **kwargs) -> ft.Text:
        """Sottotitoli o titoli di card."""
        return ft.Text(text, size=16, weight=ft.FontWeight.W_600, color=color, font_family="Roboto", **kwargs)

    @staticmethod
    def body_text(text: str, color: str = None, weight: ft.FontWeight = ft.FontWeight.NORMAL, size: int = 14, **kwargs) -> ft.Text:
        """Testo normale del corpo."""
        return ft.Text(text, size=size, color=color, weight=weight, font_family="Roboto", **kwargs)

    @staticmethod
    def small_text(text: str, color: str = None, **kwargs) -> ft.Text:
        """Testo piccolo per didascalie o note secondarie."""
        if color is None:
            color = AppColors.TEXT_SECONDARY
        return ft.Text(text, size=12, color=color, font_family="Roboto", **kwargs)

    @staticmethod
    def data_text(text: str, color: str = None, size: int = 14, **kwargs) -> ft.Text:
        """Testo per visualizzare dati/valori (es. importi in tabella)."""
        return ft.Text(text, size=size, weight=ft.FontWeight.BOLD, color=color, font_family="Roboto", **kwargs)
    
    @staticmethod
    def caption_text(text: str) -> ft.Text:
         # Deprecato: usa small_text, mantenuto per compatibilità
        return AppStyles.small_text(text)
    
    @staticmethod
    def currency_text(text: str, color: str = None, size: int = 16, **kwargs) -> ft.Text:
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
            color=color,
            font_family="Roboto",
            **kwargs
        )
    
    @staticmethod
    def big_currency_text(text: str, color: str = None, **kwargs) -> ft.Text:
        """Restituisce un testo grande per patrimonio netto con stile bold.
        
        Args:
            text: Il testo già formattato (es. "€ 1.234,56")
            color: Colore opzionale. Se None, usa SUCCESS (verde)
        """
        if color is None:
            color = AppColors.SUCCESS
        return ft.Text(
            text,
            size=36, # Aumentato per maggiore impatto
            weight=ft.FontWeight.BOLD,
            color=color,
            font_family="Roboto",
            **kwargs
        )
    
    @staticmethod
    def section_header(title: str, action_button: ft.Control = None, title_color: str = None) -> ft.Row:
        """Crea header di sezione con titolo e pulsante azione opzionale.
        
        Args:
            title: Testo del titolo della sezione
            action_button: Pulsante opzionale (es. IconButton per aggiungere)
            title_color: Colore opzionale per il titolo
        """
        controls = [AppStyles.section_header_text(title, color=title_color)]
        if action_button:
            controls.append(action_button)
        return ft.Row(controls, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

    @staticmethod
    def page_divider() -> ft.Divider:
        """Separatore standard tra sezioni."""
        return ft.Divider(color=ft.Colors.OUTLINE_VARIANT)

    @staticmethod
    def month_filter_dropdown(on_change, label: str = "Filtra per mese") -> ft.Dropdown:
        """Dropdown standard per filtro mese.
        
        Args:
            on_change: Callback per il cambio selezione
            label: Etichetta del dropdown
        """
        return ft.Dropdown(
            label=label,
            on_change=on_change,
            border_color=ft.Colors.OUTLINE,
            text_size=14,
            content_padding=10
        )

    @staticmethod
    def empty_state(icon: str, message: str) -> ft.Column:
        """Stato vuoto con icona e messaggio centrato.
        
        Args:
            icon: Icona da mostrare (es. ft.Icons.INFO_OUTLINE)
            message: Messaggio da visualizzare
        """
        return ft.Column(
            [
                ft.Icon(icon, size=50, color=AppColors.TEXT_SECONDARY),
                AppStyles.subheader_text(message)
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            alignment=ft.MainAxisAlignment.CENTER,
            expand=True
        )

    @staticmethod
    def scrollable_list(spacing: int = 10) -> ft.Column:
        """Crea una colonna scrollabile per liste di elementi.
        
        Args:
            spacing: Spaziatura tra elementi
        """
        return ft.Column(
            expand=True,
            scroll=ft.ScrollMode.ADAPTIVE,
            spacing=spacing
        )


class LoadingOverlay(ft.Container):
    """
    Overlay modale di caricamento semplice.
    Solo uno spinner centrato, senza background.
    """
    
    def __init__(self, messaggio: str = "Attendere..."):
        self.messaggio_text = ft.Text(
            messaggio, 
            size=14, 
            color=ft.Colors.ON_SURFACE
        )
        
        super().__init__(
            content=ft.Column(
                [
                    ft.ProgressRing(
                        width=40,
                        height=40,
                        stroke_width=3,
                        color=ft.Colors.PRIMARY
                    ),
                    ft.Container(height=10),
                    self.messaggio_text,
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            alignment=ft.Alignment(0, 0),
            expand=True,
            visible=False,
        )
    
    def show(self, messaggio: str = None):
        """Mostra l'overlay con un messaggio opzionale."""
        if messaggio:
            self.messaggio_text.value = messaggio
        self.visible = True
    
    def hide(self):
        """Nasconde l'overlay."""
        self.visible = False
