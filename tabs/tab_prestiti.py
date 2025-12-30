import flet as ft
from functools import partial
from db.gestione_db import ottieni_prestiti_famiglia, elimina_prestito, ottieni_membri_famiglia
from utils.styles import AppStyles, AppColors, PageConstants
from utils.async_task import AsyncTask

class PrestitiTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.controller.page = controller.page

        self.lv_prestiti = ft.Column(
            scroll=ft.ScrollMode.ADAPTIVE,
            expand=True,
            spacing=10
        )
        self.content = ft.Column(expand=True, spacing=10)

    def update_view_data(self, is_initial_load=False):
        """
        Avvia il caricamento asincrono dei dati.
        """
        # 1. Mostra Loading State
        self.lv_prestiti.controls.clear()
        self.lv_prestiti.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.ProgressRing(color=AppColors.PRIMARY),
                    ft.Text("Caricamento prestiti...", color=AppColors.TEXT_SECONDARY)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.Alignment(0, 0),
                padding=50
            )
        )
        self.content.controls = [self.lv_prestiti]
        
        # Aggiungi header durante il caricamento per mantenere la UI consistente
        header = self._build_header()
        self.lv_prestiti.controls.insert(0, header)
        self.lv_prestiti.controls.insert(1, AppStyles.page_divider())

        if self.controller.page:
            self.controller.page.update()

        # 2. Prepara argomenti per il task
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia:
            return

        master_key_b64 = self.controller.page.session.get("master_key")
        id_utente = self.controller.get_user_id()
        
        # 3. Avvia Task Asincrono
        task = AsyncTask(
            target=self._fetch_data,
            args=(id_famiglia, master_key_b64, id_utente),
            callback=self._on_data_loaded,
            error_callback=self._on_error
        )
        task.start()

    def _fetch_data(self, id_famiglia, master_key_b64, id_utente):
        """
        Esegue le query al DB (in background).
        """
        prestiti = ottieni_prestiti_famiglia(id_famiglia, master_key_b64, id_utente)
        membri = ottieni_membri_famiglia(id_famiglia)
        return prestiti, membri

    def _on_data_loaded(self, result):
        """
        Callback chiamata quando i dati sono pronti via AsyncTask.
        Ricostruisce la UI.
        """
        prestiti, membri = result
        
        try:
            self.lv_prestiti.controls.clear()
            
            # Re-inserisci header
            self.lv_prestiti.controls.append(self._build_header())
            self.lv_prestiti.controls.append(AppStyles.page_divider())

            if not prestiti:
                self.lv_prestiti.controls.append(AppStyles.body_text(self.controller.loc.get("no_loans")))
            else:
                theme = self.controller.page.theme.color_scheme if self.controller.page and self.controller.page.theme else ft.ColorScheme()
                family_ids = [m['id_utente'] for m in membri]

                for prestito in prestiti:
                    # Calcola quota famiglia
                    q_list = prestito.get('lista_quote', [])
                    perc_fam = 100.0
                    if q_list:
                        perc_fam = sum([q['percentuale'] for q in q_list if q['id_utente'] in family_ids])
                    
                    prestito['perc_famiglia'] = perc_fam
                    
                    self.lv_prestiti.controls.append(self._crea_widget_prestito(prestito, theme))

            if self.controller.page:
                self.controller.page.update()

        except Exception as e:
            self._on_error(e)

    def _on_error(self, e):
        print(f"Errore in PrestitiTab._on_error: {e}")
        try:
            self.lv_prestiti.controls.clear()
            self.lv_prestiti.controls.append(AppStyles.body_text(f"Errore durante il caricamento: {e}", color=AppColors.ERROR))
            if self.controller.page:
                self.controller.page.update()
        except:
            pass

    def _build_header(self):
        loc = self.controller.loc
        return AppStyles.section_header(
                loc.get("loans_management"),
                ft.IconButton(
                    icon=ft.Icons.ADD,
                    tooltip=loc.get("add_loan"),
                    icon_color=AppColors.PRIMARY,
                    on_click=lambda e: self.controller.prestito_dialogs.apri_dialog_prestito()
                )
            )

    def build_controls(self):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        # Non più usata direttamente come prima, logica spostata in update_view_data/_on_data_loaded
        return [self.lv_prestiti]

    def _crea_widget_prestito(self, prestito, theme):
        loc = self.controller.loc
        
        # Calcolo progresso
        mesi_totali = prestito['numero_mesi_totali']
        rate_pagate = prestito.get('rate_pagate', 0)
        progresso = rate_pagate / mesi_totali if mesi_totali > 0 else 0
        # Clamp progresso between 0 and 1 to avoid errors
        progresso = max(0.0, min(1.0, progresso))
        mesi_rimanenti = mesi_totali - rate_pagate

        progress_bar = ft.ProgressBar(value=progresso, width=200, color=AppColors.PRIMARY, bgcolor=AppColors.SURFACE_VARIANT)
        
        content = ft.Column([
            ft.Row([
                AppStyles.subheader_text(prestito['nome']),
                ft.Text(prestito['tipo'], size=12, italic=True, color=AppColors.TEXT_SECONDARY)
            ]),
            ft.Text(prestito['descrizione'] if prestito['descrizione'] else "", size=14),
            ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
            ft.Row([
                AppStyles.caption_text(f"Quota Famiglia: {prestito['perc_famiglia']:.0f}%"),
            ]) if prestito['perc_famiglia'] < 100 else ft.Container(),

            ft.Divider(height=5, color=ft.Colors.TRANSPARENT),

            ft.Row([
                self._crea_info_prestito(loc.get("financed_amount"),
                                         loc.format_currency(prestito['importo_finanziato']), theme),
                self._crea_info_prestito(loc.get("remaining_amount"),
                                         loc.format_currency(float(prestito['importo_residuo']) * (prestito['perc_famiglia'] / 100.0)),
                                         theme, colore_valore=AppColors.ERROR),
            ]),
            # Dettaglio Residuo (Capitale/Interessi) se disponibile da piano
            ft.Row([
                 self._crea_info_prestito("Residuo Capitale", 
                                          loc.format_currency(float(prestito.get('capitale_residuo', 0)) * (prestito['perc_famiglia'] / 100.0)), 
                                          theme, size_pk=12),
                 self._crea_info_prestito("Residuo Interessi", 
                                          loc.format_currency(float(prestito.get('interessi_residui', 0)) * (prestito['perc_famiglia'] / 100.0)), 
                                          theme, size_pk=12)
            ]) if prestito.get('capitale_residuo', 0) > 0 else ft.Container(),
            ft.Row([
                self._crea_info_prestito(loc.get("monthly_installment"),
                                         loc.format_currency(float(prestito['importo_rata']) * (prestito['perc_famiglia'] / 100.0)), theme),
                self._crea_info_prestito(loc.get("total_installments"), mesi_totali, theme),
            ]),
            ft.Column([
                ft.Row([
                    ft.Text(f"{loc.get('paid_installments')}: {rate_pagate}/{mesi_totali}", size=12),
                    ft.Text(f"{loc.get('remaining_installments')}: {mesi_rimanenti}", size=12)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                progress_bar
            ], spacing=5),
            ft.Row([
                ft.ElevatedButton(loc.get("pay_installment"), icon=ft.Icons.PAYMENT,
                                  on_click=lambda e, p=prestito: self.controller.prestito_dialogs.apri_dialog_paga_rata(
                                      p),
                                  disabled=prestito['importo_residuo'] <= 0),
                ft.IconButton(icon=ft.Icons.EDIT, tooltip=loc.get("edit"), data=prestito,
                              icon_color=AppColors.PRIMARY,
                              on_click=lambda e: self.controller.prestito_dialogs.apri_dialog_prestito(
                                  e.control.data)),
                ft.IconButton(icon=ft.Icons.DELETE, tooltip=loc.get("delete"), icon_color=AppColors.ERROR,
                              data=prestito['id_prestito'],
                              on_click=lambda e: self.controller.open_confirm_delete_dialog(
                                  partial(self.elimina_cliccato, e))),
            ], alignment=ft.MainAxisAlignment.END)
        ])
        
        return AppStyles.card_container(content, padding=15)

    def _crea_info_prestito(self, etichetta, valore, theme, colore_valore=None, size_pk=16):
        return ft.Column([
            AppStyles.caption_text(etichetta),
            ft.Text(str(valore), size=size_pk, weight=ft.FontWeight.BOLD, color=colore_valore)
        ], horizontal_alignment=ft.CrossAxisAlignment.START)

    def elimina_cliccato(self, e):
        id_prestito = e.control.data
        if not id_prestito: return
        
        success = elimina_prestito(id_prestito)
        if success:
            self.controller.show_snack_bar("Prestito eliminato con successo.", success=True)
            self.update_view_data()
            self.controller.db_write_operation()
        else:
            self.controller.show_snack_bar("Errore durante l'eliminazione del prestito.", success=False)