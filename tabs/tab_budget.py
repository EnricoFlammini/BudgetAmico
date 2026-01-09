import flet as ft
from db.gestione_db import (
    ottieni_anni_mesi_storicizzati,
    ottieni_dati_analisi_mensile,
    ottieni_dati_analisi_annuale,
    ottieni_riepilogo_budget_mensile
)
import datetime
from utils.styles import AppStyles, AppColors, PageConstants
from utils.async_task import AsyncTask


class BudgetTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.controller.page = controller.page
        
        # --- Controlli di Navigazione ---
        # --- Controlli di Navigazione ---
        segments_list = [
            ft.Segment(value="dettaglio", label=AppStyles.body_text("Gestione Budget"), icon=ft.Icon(ft.Icons.LIST)),
            ft.Segment(value="mensile", label=AppStyles.body_text("Analisi Mensile"), icon=ft.Icon(ft.Icons.PIE_CHART)),
            ft.Segment(value="annuale", label=AppStyles.body_text("Analisi Annuale"), icon=ft.Icon(ft.Icons.BAR_CHART)),
        ]
        


        self.seg_view_mode = ft.SegmentedButton(
            selected={"dettaglio"},
            on_change=self._on_view_mode_change,
            segments=segments_list
        )
        

        
        # --- Controlli Filtro ---
        self.dd_mese = ft.Dropdown(
            label="Mese",
            width=150,
            text_size=14,
            options=[]
        )
        self.dd_mese.on_change = self._on_filter_change
        self.dd_anno = ft.Dropdown(
            label="Anno",
            width=100,
            text_size=14,
            options=[]
        )
        self.dd_anno.on_change = self._on_filter_change
        
        # --- Contenitore Principale ---
        self.container_content = ft.Column(expand=True, scroll=ft.ScrollMode.ADAPTIVE)
        
        self.content = ft.Column(
            controls=[
                AppStyles.title_text("Budget & Analisi"),
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
        if not self.dd_anno.options:
            self.dd_anno.options = [
                ft.dropdown.Option(str(y)) for y in range(current_year - 2, current_year + 3)
            ]
        if not self.dd_anno.value:
            self.dd_anno.value = str(current_year)
            
        # Mesi
        if not self.dd_mese.options:
            self.dd_mese.options = [
                ft.dropdown.Option(str(i), datetime.date(2000, i, 1).strftime("%B")) 
                for i in range(1, 13)
            ]
        if not self.dd_mese.value:
            self.dd_mese.value = str(current_month)

    def _on_view_mode_change(self, e):
        """Gestisce cambio vista (Mensile/Annuale)."""
        mode = list(self.seg_view_mode.selected)[0]
        # Mostra il mese solo se non siamo in vista annuale
        self.dd_mese.visible = (mode != "annuale")
        # Mostra anno sempre (tranne casi particolari non più esistenti)
        self.dd_anno.visible = True
        if self.controller.page:
            self.controller.page.update()
        self._aggiorna_contenuto()

    def _on_filter_change(self, e):
        """Gestisce cambio filtri."""
        self._aggiorna_contenuto()

    def _aggiorna_contenuto(self):
        """Carica i dati dal DB e aggiorna la UI in asincrono."""
        # 1. Mostra Loading
        self.container_content.controls.clear()
        self.container_content.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.ProgressRing(color=AppColors.PRIMARY),
                    AppStyles.body_text("Elaborazione budget...", color=AppColors.TEXT_SECONDARY)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.Alignment(0, 0),
                padding=50
            )
        )
        if self.controller.page:
            self.controller.page.update()

        id_famiglia = self.controller.get_family_id()
        if not id_famiglia:
            self.container_content.controls.clear()
            self.container_content.controls.append(AppStyles.body_text("Nessuna famiglia selezionata."))
            if self.controller.page:
                self.controller.page.update()
            return

        master_key_b64 = self.controller.page.session.get("master_key")
        id_utente = self.controller.get_user_id()
        anno = int(self.dd_anno.value)
        mode = list(self.seg_view_mode.selected)[0]
        


        mese = int(self.dd_mese.value) if self.dd_mese.value else 1
        
        # 2. Avvia Task
        task = AsyncTask(
            target=self._fetch_data,
            args=(mode, id_famiglia, anno, mese, master_key_b64, id_utente),
            callback=self._on_data_loaded,
            error_callback=self._on_error
        )
        task.start()

    def _fetch_data(self, mode, id_famiglia, anno, mese, master_key_b64, id_utente):
        if mode == "dettaglio":
            return {'mode': mode, 'dati': ottieni_riepilogo_budget_mensile(id_famiglia, anno, mese, master_key_b64, id_utente)}
        elif mode == "mensile":
            return {'mode': mode, 'dati': ottieni_dati_analisi_mensile(id_famiglia, anno, mese, master_key_b64, id_utente)}
        else:
            return {'mode': mode, 'dati': ottieni_dati_analisi_annuale(id_famiglia, anno, master_key_b64, id_utente), 'anno': anno}

    def _on_data_loaded(self, result):
        try:
            self.container_content.controls.clear()
            
            mode = result['mode']
            dati = result['dati']
            
            if mode == "dettaglio":
                self._costruisci_vista_dettaglio(dati)
            elif mode == "mensile":
                self._costruisci_vista_mensile(dati)
            else:
                self._costruisci_vista_annuale(dati, result['anno'])
                
            if self.page:
                self.page.update()
        except Exception as e:
            self._on_error(e)

    def _on_error(self, e):
        print(f"Errore BudgetTab: {e}")
        try:
            self.container_content.controls.clear()
            self.container_content.controls.append(AppStyles.body_text(f"Errore during il caricamento: {e}", color=AppColors.ERROR))
            if self.page:
                self.page.update()
        except:
            pass

    def _costruisci_vista_mensile(self, dati):
        if not dati:
            self.container_content.controls.append(AppStyles.body_text("Errore nel caricamento dati mensili.", color=AppColors.ERROR))
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
        
        spese_per_categoria = [c for c in dati['spese_per_categoria'] if "entrat" not in c['nome_categoria'].lower()]
        
        totale_entrate = dati['entrate']
        totale_spese = dati['spese_totali']
        base_calcolo = max(totale_entrate, totale_spese)
        
        dati_grafico = []
        for cat in spese_per_categoria:
            percentuale = (cat['importo'] / base_calcolo * 100) if base_calcolo > 0 else 0
            dati_grafico.append({
                'nome_categoria': cat['nome_categoria'],
                'importo': cat['importo'],
                'percentuale': percentuale
            })

        risparmio_effettivo = totale_entrate - totale_spese
        if risparmio_effettivo > 0:
            percentuale_risparmio = (risparmio_effettivo / base_calcolo * 100) if base_calcolo > 0 else 0
            dati_grafico.append({
                'nome_categoria': "Risparmio",
                'importo': risparmio_effettivo,
                'percentuale': percentuale_risparmio
            })

        titolo_grafico = "Ripartizione Entrate" if totale_entrate >= totale_spese else "Ripartizione Spese (Deficit)"

        chart_container = self._crea_grafico_torta(dati_grafico, titolo_grafico)
        
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
                     AppStyles.subheader_text("Dettaglio Categorie"),
                     lista_dettagli
                 ], col={"sm": 12, "md": 6})
            ])
        ])

    def _costruisci_vista_annuale(self, dati, anno):
        if not dati:
             self.container_content.controls.append(AppStyles.body_text("Errore nel caricamento dati annuali.", color=AppColors.ERROR))
             return
        
        delta_color = AppColors.SUCCESS if dati['media_delta_budget_spese'] >= 0 else AppColors.ERROR
        risparmio_color = AppColors.SUCCESS if dati['media_differenza_entrate_spese'] >= 0 else AppColors.ERROR

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

        spese_annuali = [c for c in dati['spese_per_categoria_annuali'] if "entrat" not in c['nome_categoria'].lower()]

        totale_entrate_media = dati['media_entrate_mensili']
        totale_spese_media = dati['media_spese_mensili']
        
        base_calcolo = max(totale_entrate_media, totale_spese_media)
        
        dati_grafico = []
        for cat in spese_annuali:
            importo_medio = cat.get('importo_media', cat['importo'])
            percentuale = (importo_medio / base_calcolo * 100) if base_calcolo > 0 else 0
            dati_grafico.append({
                'nome_categoria': cat['nome_categoria'],
                'importo': importo_medio,
                'percentuale': percentuale
            })

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

        lista_dettagli = ft.Column(spacing=10)
        for cat in spese_annuali:
             cat_view = cat.copy()
             cat_view['importo'] = cat.get('importo_media', cat['importo'])
             lista_dettagli.controls.append(self._crea_riga_dettaglio_categoria(cat_view))

        self.container_content.controls.extend([
            ft.Container(height=10),
            row_cards,
            ft.Divider(height=30, color=ft.Colors.TRANSPARENT),
            ft.ResponsiveRow([
                 ft.Column([chart_container], col={"sm": 12, "md": 6}),
                 ft.Column([
                     AppStyles.subheader_text(f"Dettaglio Media {anno}"),
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
            AppStyles.small_text(titolo, color=AppColors.TEXT_SECONDARY),
            AppStyles.currency_text(valore_str, size=18, color=ft.Colors.ON_SURFACE)
        ]
        
        if confronto:
            confronto_valore = confronto.get('valore', 0)
            confronto_label = confronto.get('label', '')
            confronto_str = loc.format_currency(confronto_valore)
            content_list.append(
                AppStyles.small_text(f"{confronto_label}: {confronto_str}", color=AppColors.TEXT_SECONDARY)
            )

        return AppStyles.card_container(
            content=ft.Column(content_list, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=5),
            padding=15,
            width=200
        )

    def _crea_grafico_torta(self, dati_categorie, titolo):
        if not dati_categorie:
            return ft.Container(content=AppStyles.body_text("Nessun dato da visualizzare"), padding=20)
            
        sections = []
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
                        ft.Text(cat['nome_categoria'], size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD, font_family="Roboto"), 
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
            AppStyles.subheader_text(titolo),
            ft.Container(content=chart, height=300)
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER)

    def _crea_riga_dettaglio_categoria(self, cat):
        loc = self.controller.loc
        return ft.Row([
            AppStyles.body_text(cat['nome_categoria']),
            AppStyles.small_text(f"{cat['percentuale']:.1f}%", color=AppColors.TEXT_SECONDARY),
            AppStyles.data_text(loc.format_currency(cat['importo']))
        ])

    def _costruisci_vista_dettaglio(self, budget_data):
        if not budget_data:
            self.container_content.controls.append(
                AppStyles.empty_state(ft.Icons.MONEY_OFF, "Nessun budget definito per questo mese.")
            )
            return

        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        
        sorted_cats = sorted(
            [c for c in budget_data.items() if "entrat" not in c[1]['nome_categoria'].lower()],
            key=lambda x: x[1]['nome_categoria'].lower()
        )
        
        # Calculate Totals
        tot_limite = 0
        tot_spesa = 0
        
        lista_categorie = ft.Column(spacing=10)
        
        for cat_id, cat_data in sorted_cats:
            tot_limite += cat_data['importo_limite_totale']
            tot_spesa += cat_data['spesa_totale_categoria']
            lista_categorie.controls.append(self._crea_widget_categoria(cat_data, theme))
            
        # Add Global Summary Card
        # Removed condition to always show totals
        # if tot_limite > 0: 
        global_data = {
            'nome_categoria': "Budget Totale",
            'importo_limite_totale': tot_limite,
            'spesa_totale_categoria': tot_spesa,
            'sottocategorie': []
        }
        # Insert at the top with a bit of separation
        lista_categorie.controls.insert(0, ft.Column([
            self._crea_widget_categoria(global_data, theme, is_global=True),
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT)
        ]))

        self.container_content.controls.append(lista_categorie)

    def _crea_widget_categoria(self, cat_data, theme, is_global=False):
        loc = self.controller.loc
        limite_cat = cat_data['importo_limite_totale']
        spesa_cat = cat_data['spesa_totale_categoria']
        if limite_cat > 0:
            percentuale_cat = spesa_cat / limite_cat
        else:
            # Se non c'è budget ma c'è spesa, la consideriamo come "Fuori Budget" (Rosso)
            # Impostiamo una percentuale alta (> 1.1) per far scattare il colore ERROR
            percentuale_cat = 2.0 if spesa_cat > 0 else 0.0
        
        # New Color Logic
        if percentuale_cat <= 1.0:
            colore_cat = AppColors.SUCCESS # Green
        elif percentuale_cat <= 1.1:
            colore_cat = AppColors.WARNING # Yellow
        else:
            colore_cat = AppColors.ERROR   # Red

        # Clamp percentage for progress bar (max 1.0)
        progress_value = min(percentuale_cat, 1.0)
        
        # Determine Status Text
        if limite_cat > 0:
            status_text = f"{percentuale_cat*100:.1f}%"
        else:
            status_text = ">100%" if spesa_cat > 0 else "0.0%"

        sottocategorie_container = ft.Column(spacing=5, visible=False)
        has_subcategories = len(cat_data.get('sottocategorie', [])) > 0
        
        for sub_data in cat_data.get('sottocategorie', []):
            sottocategorie_container.controls.append(self._crea_widget_sottocategoria(sub_data, theme))

        # Icon for expansion (only if subcategories exist)
        icon_expand = ft.Icon(ft.Icons.KEYBOARD_ARROW_DOWN, size=24, opacity=1 if has_subcategories else 0)

        def toggle_subcategory(e):
            if not has_subcategories: return
            sottocategorie_container.visible = not sottocategorie_container.visible
            icon_expand.name = ft.Icons.KEYBOARD_ARROW_UP if sottocategorie_container.visible else ft.Icons.KEYBOARD_ARROW_DOWN
            if self.page:
                self.page.update()

        # Header Content
        name_size = 20 if is_global else 16
        name_weight = ft.FontWeight.W_900 if is_global else ft.FontWeight.BOLD
        
        header_content = ft.Container(
            content=ft.Column([
            ft.Row([
                    ft.Text(cat_data['nome_categoria'], size=name_size, weight=name_weight, expand=True, font_family="Roboto"),
                    icon_expand
                ]),
                ft.Container(height=5),
                ft.ProgressBar(value=progress_value, color=colore_cat, bgcolor=AppColors.SURFACE_VARIANT, height=10 if is_global else 8, border_radius=4),
                ft.Container(height=5),
                ft.Row([
                    AppStyles.body_text(f"{loc.format_currency(spesa_cat)} / {loc.format_currency(limite_cat)}", color=AppColors.TEXT_SECONDARY),
                    AppStyles.data_text(status_text, color=colore_cat)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ]),
            on_click=toggle_subcategory if has_subcategories else None,
            padding=15 if is_global else 10,
            border_radius=10,
            ink=has_subcategories
        )

        card = AppStyles.card_container(
            content=ft.Column([
                header_content,
                sottocategorie_container
            ], spacing=0),
            padding=0 
        )
        
        if is_global:
            # Highlight global card slightly
            card.border = ft.border.all(2, colore_cat)
            
        return card

    def _crea_widget_sottocategoria(self, sub_data, theme):
        loc = self.controller.loc
        limite = sub_data['importo_limite']
        spesa = sub_data['spesa_totale']
        if limite > 0:
            percentuale = spesa / limite
            status_text = f"{percentuale*100:.1f}%"
        else:
            percentuale = 2.0 if spesa > 0 else 0.0
            status_text = ">100%" if spesa > 0 else "0.0%"
        
        # Same Color Logic
        if percentuale <= 1.0:
            colore_progress = AppColors.SUCCESS
        elif percentuale <= 1.1:
            colore_progress = AppColors.WARNING
        else:
            colore_progress = AppColors.ERROR

        progress_value = min(percentuale, 1.0)

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    AppStyles.body_text(sub_data['nome_sottocategoria'], expand=True),
                    AppStyles.data_text(status_text, color=colore_progress, size=12)
                ]),
                ft.ProgressBar(value=progress_value, color=colore_progress, bgcolor=AppColors.SURFACE_VARIANT, height=4),
                ft.Row([
                    AppStyles.small_text(f"{loc.format_currency(spesa)} / {loc.format_currency(limite)}", color=AppColors.TEXT_SECONDARY)
                ], alignment=ft.MainAxisAlignment.END)
            ]),
            padding=ft.padding.only(left=20, right=10, top=5, bottom=5),
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.BLACK) # Slight background for differentiation
        )