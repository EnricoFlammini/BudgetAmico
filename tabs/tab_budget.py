import flet as ft
from db.gestione_db import (
    ottieni_anni_mesi_storicizzati,
    ottieni_dati_analisi_mensile,
    ottieni_dati_analisi_annuale,
    ottieni_riepilogo_budget_mensile
)
import datetime
from utils.styles import AppStyles, AppColors, PageConstants


class BudgetTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.page = controller.page
        
        # --- Controlli di Navigazione ---
        self.seg_view_mode = ft.SegmentedButton(
            selected={"dettaglio"},
            on_change=self._on_view_mode_change,
            segments=[
                ft.Segment(
                    value="dettaglio",
                    label=ft.Text("Gestione Budget"),
                    icon=ft.Icon(ft.Icons.LIST)
                ),
                ft.Segment(
                    value="mensile",
                    label=ft.Text("Analisi Mensile"),
                    icon=ft.Icon(ft.Icons.PIE_CHART)
                ),
                ft.Segment(
                    value="annuale",
                    label=ft.Text("Analisi Annuale"),
                    icon=ft.Icon(ft.Icons.BAR_CHART)
                ),
            ]
        )
        
        # --- Controlli Filtro ---
        self.dd_mese = ft.Dropdown(
            label="Mese",
            width=150,
            on_change=self._on_filter_change,
            text_size=14,
            options=[]
        )
        self.dd_anno = ft.Dropdown(
            label="Anno",
            width=100,
            on_change=self._on_filter_change,
            text_size=14,
            options=[]
        )
        
        # --- Contenitore Principale ---
        self.container_content = ft.Column(expand=True, scroll=ft.ScrollMode.ADAPTIVE)
        
        self.content = ft.Column(
            controls=[
                AppStyles.section_header("Budget & Analisi"),
                ft.Container(
                    content=ft.Row([
                        self.seg_view_mode,
                        ft.Container(width=20),
                        self.dd_mese,
                        self.dd_anno
                    ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, wrap=True),
                    padding=ft.padding.only(bottom=10)
                ),
                AppStyles.page_divider(),
                self.container_content
            ],
            expand=True
        )

    def update_view_data(self, is_initial_load=False):
        """Inizializza filtri e carica dati."""
        self._popola_filtri()
        self._aggiorna_contenuto()

    def _popola_filtri(self):
        """Popola i dropdown Anno e Mese."""
        today = datetime.date.today()
        current_year = today.year
        current_month = today.month
        
        # Anni (Corrente +/- 2)
        self.dd_anno.options = [
            ft.dropdown.Option(str(y)) for y in range(current_year - 2, current_year + 3)
        ]
        if not self.dd_anno.value:
            self.dd_anno.value = str(current_year)
            
        # Mesi
        self.dd_mese.options = [
            ft.dropdown.Option(str(i), datetime.date(2000, i, 1).strftime("%B")) 
            for i in range(1, 13)
        ]
        if not self.dd_mese.value:
            self.dd_mese.value = str(current_month)

    def _on_view_mode_change(self, e):
        """Gestisce cambio vista (Mensile/Annuale)."""
        self.controller.show_loading("Elaborazione...")
        try:
            mode = list(self.seg_view_mode.selected)[0]
            # Mostra il mese solo se non siamo in vista annuale
            self.dd_mese.visible = (mode != "annuale")
            self._aggiorna_contenuto()
            self.page.update()
        finally:
            self.controller.hide_loading()

    def _on_filter_change(self, e):
        """Gestisce cambio filtri."""
        self.controller.show_loading("Elaborazione...")
        try:
            self._aggiorna_contenuto()
            self.page.update()
        finally:
            self.controller.hide_loading()

    def _aggiorna_contenuto(self):
        """Carica i dati dal DB e aggiorna la UI."""
        self.container_content.controls.clear()
        
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia:
            self.container_content.controls.append(ft.Text("Nessuna famiglia selezionata."))
            return

        master_key_b64 = self.controller.page.session.get("master_key")
        id_utente = self.controller.get_user_id()
        anno = int(self.dd_anno.value)
        
        mode = list(self.seg_view_mode.selected)[0]
        
        if mode == "dettaglio":
            mese = int(self.dd_mese.value)
            dati_budget = ottieni_riepilogo_budget_mensile(id_famiglia, anno, mese, master_key_b64, id_utente)
            self._costruisci_vista_dettaglio(dati_budget)
        elif mode == "mensile":
            mese = int(self.dd_mese.value)
            dati = ottieni_dati_analisi_mensile(id_famiglia, anno, mese, master_key_b64, id_utente)
            self._costruisci_vista_mensile(dati)
        else:
            dati = ottieni_dati_analisi_annuale(id_famiglia, anno, master_key_b64, id_utente)
            self._costruisci_vista_annuale(dati, anno)

    def _costruisci_vista_mensile(self, dati):
        if not dati:
            self.container_content.controls.append(ft.Text("Errore nel caricamento dati mensili.", color=AppColors.ERROR))
            return

        loc = self.controller.loc
        
        # Cards
        delta_color = AppColors.SUCCESS if dati['delta_budget_spese'] >= 0 else AppColors.ERROR
        risparmio_color = AppColors.SUCCESS if dati['risparmio'] >= 0 else AppColors.ERROR
        
        # Dati confronto (media annuale)
        dati_conf = dati.get('dati_confronto') or {}
        
        row_cards = ft.Row([
            self._crea_summary_card("Entrate Mensili", dati['entrate'], ft.Icons.ATTACH_MONEY, AppColors.SUCCESS, 
                                    confronto={'valore': dati_conf.get('media_entrate_mensili', 0), 'label': 'Media Annua'}),
            self._crea_summary_card("Spese Totali", dati['spese_totali'], ft.Icons.MONEY_OFF, AppColors.ERROR,
                                    confronto={'valore': dati_conf.get('media_spese_mensili', 0), 'label': 'Media Annua'}),
            self._crea_summary_card("Budget Totale", dati['budget_totale'], ft.Icons.ACCOUNT_BALANCE, AppColors.PRIMARY,
                                    confronto={'valore': dati_conf.get('media_budget_mensile', 0), 'label': 'Media Annua'}),
            self._crea_summary_card("Risparmio", dati['risparmio'], ft.Icons.SAVINGS, risparmio_color, is_delta=True,
                                    confronto={'valore': dati_conf.get('media_differenza_entrate_spese', 0), 'label': 'Media Annua'}),
            self._crea_summary_card("Delta (Budget - Spese)", dati['delta_budget_spese'], ft.Icons.DIFFERENCE, delta_color, is_delta=True,
                                    confronto={'valore': dati_conf.get('media_delta_budget_spese', 0), 'label': 'Media Annua'}),
        ], wrap=True, alignment=ft.MainAxisAlignment.CENTER, spacing=20)
        
        # Filtra categoria Entrate
        spese_per_categoria = [c for c in dati['spese_per_categoria'] if "entrat" not in c['nome_categoria'].lower()]
        
        # Preparazione dati grafico
        # Se Entrate > Spese -> 100% = Entrate (Spese + Risparmio)
        # Se Spese > Entrate -> 100% = Spese
        totale_entrate = dati['entrate']
        totale_spese = dati['spese_totali']
        
        base_calcolo = max(totale_entrate, totale_spese)
        
        dati_grafico = []
        
        # Aggiungi categorie spese
        for cat in spese_per_categoria:
            percentuale = (cat['importo'] / base_calcolo * 100) if base_calcolo > 0 else 0
            dati_grafico.append({
                'nome_categoria': cat['nome_categoria'],
                'importo': cat['importo'],
                'percentuale': percentuale
            })

        # Aggiungi Risparmio al grafico SOLO se positivo (cioè Entrate > Spese)
        risparmio_effettivo = totale_entrate - totale_spese
        if risparmio_effettivo > 0:
            percentuale_risparmio = (risparmio_effettivo / base_calcolo * 100) if base_calcolo > 0 else 0
            dati_grafico.append({
                'nome_categoria': "Risparmio",
                'importo': risparmio_effettivo,
                'percentuale': percentuale_risparmio
            })

        titolo_grafico = "Ripartizione Entrate" if totale_entrate >= totale_spese else "Ripartizione Spese (Deficit)"

        # Grafico
        chart_container = self._crea_grafico_torta(dati_grafico, titolo_grafico)
        
        # Lista Dettagli (mostra solo spese, con percentuali ricalcolate su Entrate? O su spese totali? 
        # Solitamente nella lista dettagli si vuole vedere quanto incide sulla spesa o sulle entrate.
        # Lasciamo la lista dettagli com'era (incidenza su spese totali) o la aggioniamo?
        # Il request era specifica "nel grafico voglio vedere...". Lascio la lista dettagli invariata (spese).
        lista_dettagli = ft.Column(spacing=10)
        for cat in spese_per_categoria:
             lista_dettagli.controls.append(self._crea_riga_dettaglio_categoria(cat))

        self.container_content.controls.extend([
            ft.Container(height=10),
            row_cards,
            ft.Divider(height=30, color=ft.Colors.TRANSPARENT),
            ft.ResponsiveRow([
                 ft.Column([chart_container], col={"sm": 12, "md": 6}),
                 ft.Column([
                     ft.Text("Dettaglio Categorie", size=18, weight=ft.FontWeight.BOLD),
                     lista_dettagli
                 ], col={"sm": 12, "md": 6})
            ])
        ])

    def _costruisci_vista_annuale(self, dati, anno):
        if not dati:
             self.container_content.controls.append(ft.Text("Errore nel caricamento dati annuali.", color=AppColors.ERROR))
             return
        
        delta_color = AppColors.SUCCESS if dati['media_delta_budget_spese'] >= 0 else AppColors.ERROR
        risparmio_color = AppColors.SUCCESS if dati['media_differenza_entrate_spese'] >= 0 else AppColors.ERROR

        # Dati confronto (anno precedente)
        dati_conf = dati.get('dati_confronto')
        label_conf = f"Media {anno-1}"
        
        def get_conf(key):
             if not dati_conf: return None
             return {'valore': dati_conf.get(key, 0), 'label': label_conf}

        row_cards = ft.Row([
            self._crea_summary_card("Media Entrate Mensili", dati['media_entrate_mensili'], ft.Icons.ATTACH_MONEY, AppColors.SUCCESS,
                                    confronto=get_conf('media_entrate_mensili')),
            self._crea_summary_card("Media Spese Mensili", dati['media_spese_mensili'], ft.Icons.MONEY_OFF, AppColors.ERROR,
                                    confronto=get_conf('media_spese_mensili')),
            self._crea_summary_card("Media Budget Mensile", dati['media_budget_mensile'], ft.Icons.ACCOUNT_BALANCE, AppColors.PRIMARY,
                                    confronto=get_conf('media_budget_mensile')),
            self._crea_summary_card("Risparmio Medio", dati['media_differenza_entrate_spese'], ft.Icons.SAVINGS, risparmio_color, is_delta=True,
                                    confronto=get_conf('media_differenza_entrate_spese')),
            self._crea_summary_card("Media Delta (Budget - Spese)", dati['media_delta_budget_spese'], ft.Icons.DIFFERENCE, delta_color, is_delta=True,
                                    confronto=get_conf('media_delta_budget_spese')),
        ], wrap=True, alignment=ft.MainAxisAlignment.CENTER, spacing=20)

        # Filtra categoria Entrate
        spese_annuali = [c for c in dati['spese_per_categoria_annuali'] if "entrat" not in c['nome_categoria'].lower()]

        # Preparazione dati grafico (Media Entrate = 100% o Media Spese se Deficit)
        totale_entrate_media = dati['media_entrate_mensili']
        totale_spese_media = dati['media_spese_mensili']
        
        base_calcolo = max(totale_entrate_media, totale_spese_media)
        
        dati_grafico = []
        
        # Aggiungi categorie spese (usando i valori medi)
        for cat in spese_annuali:
            # Usa 'importo_media' calcolato dal DB
            importo_medio = cat.get('importo_media', cat['importo']) # Fallback safe
            percentuale = (importo_medio / base_calcolo * 100) if base_calcolo > 0 else 0
            dati_grafico.append({
                'nome_categoria': cat['nome_categoria'],
                'importo': importo_medio,
                'percentuale': percentuale
            })

        # Aggiungi Risparmio al grafico SOLO se positivo
        media_risparmio = totale_entrate_media - totale_spese_media
        if media_risparmio > 0:
            percentuale_risparmio = (media_risparmio / base_calcolo * 100) if base_calcolo > 0 else 0
            dati_grafico.append({
                'nome_categoria': "Risparmio",
                'importo': media_risparmio,
                'percentuale': percentuale_risparmio
            })

        titolo_grafico = f"Ripartizione Media {anno}"
        if totale_entrate_media < totale_spese_media:
            titolo_grafico += " (Deficit)"

        chart_container = self._crea_grafico_torta(dati_grafico, titolo_grafico)

        # Lista Dettagli
        lista_dettagli = ft.Column(spacing=10)
        for cat in spese_annuali:
             # Adatta il dizionario per usare 'importo_media' come 'importo' per la visualizzazione standard
             cat_view = cat.copy()
             cat_view['importo'] = cat.get('importo_media', cat['importo'])
             # Percentuale rispetto al totale spese per la lista (come nel mensile) o rispetto alla base?
             # Manteniamo coerenza con il DB: la percentuale nel DB è rispetto alle spese totali. 
             # Se vogliamo coerenza visuale con il grafico, ricalcoliamo. 
             # Ma la lista solitamente dettaglia le spese. Lasciamo il valore del DB o ricalcoliamo su spese.
             # Dato che nel DB ho aggiornato 'percentuale' basandosi su media_spese_mensili, uso quello.
             lista_dettagli.controls.append(self._crea_riga_dettaglio_categoria(cat_view))

        self.container_content.controls.extend([
            ft.Container(height=10),
            row_cards,
            ft.Divider(height=30, color=ft.Colors.TRANSPARENT),
            ft.ResponsiveRow([
                 ft.Column([chart_container], col={"sm": 12, "md": 6}),
                 ft.Column([
                     ft.Text(f"Dettaglio Media {anno}", size=18, weight=ft.FontWeight.BOLD),
                     lista_dettagli
                 ], col={"sm": 12, "md": 6})
            ])
        ])

    def _crea_summary_card(self, titolo, valore, icona, colore_icona, is_delta=False, confronto=None):
        loc = self.controller.loc
        valore_str = loc.format_currency(valore)
        if is_delta:
             valore_str = ("+" if valore > 0 else "") + valore_str
             
        content_list = [
            ft.Icon(icona, color=colore_icona, size=30),
            ft.Text(titolo, size=12, color=AppColors.TEXT_SECONDARY, text_align=ft.TextAlign.CENTER),
            ft.Text(valore_str, size=18, weight=ft.FontWeight.BOLD, color=ft.Colors.ON_SURFACE)
        ]
        
        if confronto:
            confronto_valore = confronto.get('valore', 0)
            confronto_label = confronto.get('label', '')
            confronto_str = loc.format_currency(confronto_valore)
            content_list.append(
                ft.Text(f"{confronto_label}: {confronto_str}", size=11, color=AppColors.TEXT_SECONDARY)
            )

        return AppStyles.card_container(
            content=ft.Column(content_list, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
            padding=15,
            width=200
        )

    def _crea_grafico_torta(self, dati_categorie, titolo):
        if not dati_categorie:
            return ft.Container(content=ft.Text("Nessun dato da visualizzare"), padding=20)
            
        sections = []
        # Colori ciclici per le categorie
        colors = [
            ft.Colors.BLUE, ft.Colors.RED, ft.Colors.GREEN, ft.Colors.ORANGE, 
            ft.Colors.PURPLE, ft.Colors.CYAN, ft.Colors.TEAL, ft.Colors.PINK,
            ft.Colors.INDIGO, ft.Colors.AMBER, ft.Colors.LIME, ft.Colors.BROWN
        ]
        
        for i, cat in enumerate(dati_categorie):
            valore = cat['importo']
            percentuale = cat['percentuale']
            c = colors[i % len(colors)]
            
            sections.append(
                ft.PieChartSection(
                    valore,
                    title=f"{percentuale:.1f}%",
                    color=c,
                    radius=100,
                    title_style=ft.TextStyle(size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                    badge=ft.Container(
                        ft.Text(cat['nome_categoria'], size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD), 
                        bgcolor=ft.Colors.with_opacity(0.7, ft.Colors.BLACK), 
                        padding=5, 
                        border_radius=5
                    ),
                    badge_position=0.9
                )
            )
            
        chart = ft.PieChart(
            sections=sections,
            sections_space=2,
            center_space_radius=40,
            expand=True
        )
        
        return ft.Column([
            ft.Text(titolo, size=16, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
            ft.Container(content=chart, height=300)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _crea_riga_dettaglio_categoria(self, cat):
        loc = self.controller.loc
        return ft.Row([
            ft.Text(cat['nome_categoria'], expand=True),
            ft.Text(f"{cat['percentuale']:.1f}%", width=50, color=AppColors.TEXT_SECONDARY),
            ft.Text(loc.format_currency(cat['importo']), width=100, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.RIGHT)
        ])

    def _costruisci_vista_dettaglio(self, budget_data):
        if not budget_data:
            self.container_content.controls.append(
                AppStyles.empty_state(ft.Icons.MONEY_OFF, "Nessun budget definito per questo mese.")
            )
            return

        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        
        # Ordina per nome categoria e filtra "Entrate"
        sorted_cats = sorted(
            [c for c in budget_data.items() if "entrat" not in c[1]['nome_categoria'].lower()],
            key=lambda x: x[1]['nome_categoria'].lower()
        )
        
        lista_categorie = ft.Column(spacing=10)
        for cat_id, cat_data in sorted_cats:
            lista_categorie.controls.append(self._crea_widget_categoria(cat_data, theme))
            
        self.container_content.controls.append(lista_categorie)

    def _crea_widget_categoria(self, cat_data, theme):
        loc = self.controller.loc
        
        # Calcoli per la categoria aggregata
        limite_cat = cat_data['importo_limite_totale']
        spesa_cat = cat_data['spesa_totale_categoria']
        rimanente_cat = (limite_cat - spesa_cat)
        percentuale_cat = (spesa_cat / limite_cat) if limite_cat > 0 else 0
        if percentuale_cat > 1: percentuale_cat = 1
        
        colore_cat = theme.primary
        if percentuale_cat > 0.9:
            colore_cat = AppColors.ERROR
        elif percentuale_cat > 0.7:
            colore_cat = AppColors.WARNING

        # Creazione dei widget per le sottocategorie
        sottocategorie_widgets = []
        for sub_data in cat_data['sottocategorie']:
            sottocategorie_widgets.append(self._crea_widget_sottocategoria(sub_data, theme))

        content = ft.Column([
            ft.Row([
                AppStyles.subheader_text(cat_data['nome_categoria']),
                ft.Text(
                    f"Residuo: {loc.format_currency(rimanente_cat)}",
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=colore_cat
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            AppStyles.caption_text(
                f"Speso {loc.format_currency(spesa_cat)} su {loc.format_currency(limite_cat)}"),
            ft.ProgressBar(value=percentuale_cat, color=colore_cat, bgcolor=AppColors.SURFACE_VARIANT),
            ft.Divider(height=10, color=ft.Colors.OUTLINE_VARIANT),
            ft.Column(sottocategorie_widgets, spacing=8)
        ])
        
        return AppStyles.card_container(content, padding=15)

    def _crea_widget_sottocategoria(self, sub_data, theme):
        loc = self.controller.loc
        limite = sub_data['importo_limite']
        spesa = sub_data['spesa_totale']
        rimanente = (limite - spesa)
        percentuale = (spesa / limite) if limite > 0 else 0
        if percentuale > 1: percentuale = 1

        colore_progress = theme.primary
        if percentuale > 0.9:
            colore_progress = AppColors.ERROR
        elif percentuale > 0.7:
            colore_progress = AppColors.WARNING

        return ft.Column([
            ft.Row([
                AppStyles.body_text(sub_data['nome_sottocategoria']),
                ft.Text(f"{loc.format_currency(rimanente)}", color=colore_progress, size=14)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.ProgressBar(value=percentuale, color=colore_progress, bgcolor=AppColors.SURFACE_VARIANT, height=5)
        ])