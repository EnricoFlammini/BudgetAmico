import flet as ft
from functools import partial
from db.gestione_db import ottieni_immobili_famiglia, elimina_immobile, ottieni_membri_famiglia
from utils.styles import AppStyles, AppColors, PageConstants
from utils.async_task import AsyncTask
import time

class ImmobiliTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.page = controller.page

        self.lv_immobili = ft.Column(
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
        self.lv_immobili.controls.clear()
        self.lv_immobili.controls.append(
            ft.Container(
                content=ft.Column([
                    ft.ProgressRing(color=AppColors.PRIMARY),
                    ft.Text("Caricamento immobili...", color=AppColors.TEXT_SECONDARY)
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                alignment=ft.alignment.center,
                padding=50
            )
        )
        self.content.controls = [self.lv_immobili]
        if self.page:
            self.page.update()

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
        # Simula un ritardo per verificare che la UI non si blocchi (rimuovere in produzione se necessario)
        # time.sleep(0.5) 
        
        immobili = ottieni_immobili_famiglia(id_famiglia, master_key_b64, id_utente)
        membri = ottieni_membri_famiglia(id_famiglia)
        return immobili, membri

    def _on_data_loaded(self, result):
        """
        Callback chiamata quando i dati sono pronti via AsyncTask.
        Ricostruisce la UI.
        """
        immobili, membri = result
        
        # Poiché siamo in un thread separato, dobbiamo assicurarci di gestire eventuali errori di UI
        # Ma Flet gestisce page.update() thread-safe.
        try:
            theme = self.page.theme.color_scheme if self.page and self.page.theme else ft.ColorScheme()
            family_ids = [m['id_utente'] for m in membri]

            # Calcolo Totali
            tot_acquisto = 0.0
            tot_attuale = 0.0
            tot_mutui = 0.0

            for imm in immobili:
                val_acq = imm.get('valore_acquisto') or 0.0
                val_att = imm.get('valore_attuale') or 0.0
                val_mut = imm.get('valore_mutuo_residuo') or 0.0
                
                # Calcolo Quote
                q_imm = imm.get('lista_quote', [])
                perc_imm_fam = 100.0
                if q_imm:
                    perc_imm_fam = sum([q['percentuale'] for q in q_imm if q['id_utente'] in family_ids])
                
                q_mut = imm.get('lista_quote_prestito', [])
                perc_mut_fam = 100.0
                if q_mut:
                    perc_mut_fam = sum([q['percentuale'] for q in q_mut if q['id_utente'] in family_ids])
                
                # Salvo le percentuali calcolate nell'oggetto per il widget
                imm['perc_famiglia_immobile'] = perc_imm_fam
                imm['perc_famiglia_mutuo'] = perc_mut_fam

                # Valori pesati
                val_acq_weighted = val_acq * (perc_imm_fam / 100.0)
                val_att_weighted = val_att * (perc_imm_fam / 100.0)
                val_mut_weighted = val_mut * (perc_mut_fam / 100.0)

                tot_acquisto += val_acq_weighted
                tot_mutui += val_mut_weighted
                if not imm.get('nuda_proprieta'):
                    tot_attuale += val_att_weighted
            
            tot_netto = tot_attuale - tot_mutui

            # Ricostruisce la lista controlli
            new_controls = []

            # Costruisco header con riepilogo
            header_controls = [
                AppStyles.section_header(
                    self.controller.loc.get("properties_management"),
                    ft.IconButton(
                        icon=ft.Icons.ADD_HOME,
                        tooltip=self.controller.loc.get("add_property"),
                        icon_color=AppColors.PRIMARY,
                        on_click=lambda e: self.controller.immobile_dialog.apri_dialog_immobile()
                    )
                ),
                AppStyles.page_divider(),
            ]
            new_controls.extend(header_controls)

            # Card Riepilogo (se ci sono immobili)
            if immobili:
                loc = self.controller.loc
                summary_content = ft.Column([
                    AppStyles.subheader_text("Riepilogo Patrimonio Immobiliare"),
                    ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                    ft.Row([
                        self._crea_info_immobile(loc.get("current_value"), loc.format_currency(tot_attuale), theme, colore_valore=AppColors.SUCCESS),
                        self._crea_info_immobile(loc.get("residual_mortgage"), loc.format_currency(tot_mutui), theme, colore_valore=AppColors.ERROR),
                        self._crea_info_immobile("Patrimonio Netto (Famiglia)", loc.format_currency(tot_netto), theme, colore_valore=AppColors.PRIMARY),
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
                ])
                new_controls.append(AppStyles.card_container(summary_content, padding=15))
                new_controls.append(ft.Container(height=10)) # Spaziatura
            
            if not immobili:
                new_controls.append(AppStyles.body_text(self.controller.loc.get("no_properties")))
            else:
                for immobile in immobili:
                    new_controls.append(self._crea_widget_immobile(immobile, theme))

            # Aggiorna la UI
            self.lv_immobili.controls = new_controls
            if self.page:
                self.page.update()
            
        except Exception as e:
            self._on_error(e)

    def _on_error(self, e):
        print(f"Errore in ImmobiliTab._on_error: {e}")
        try:
            self.lv_immobili.controls.clear()
            self.lv_immobili.controls.append(AppStyles.body_text(f"Errore durante il caricamento: {e}", color=AppColors.ERROR))
            if self.page:
                self.page.update()
        except:
            pass

    def build_controls(self):
        """Costruisce e restituisce la lista di controlli per la scheda."""
        return [self.lv_immobili]

    def _crea_widget_immobile(self, immobile, theme):
        loc = self.controller.loc
        is_nuda = immobile.get('nuda_proprieta')
        
        val_acq = immobile.get('valore_acquisto') or 0.0
        val_att = immobile.get('valore_attuale') or 0.0
        val_mut = immobile.get('valore_mutuo_residuo') or 0.0
        
        perc_imm = immobile.get('perc_famiglia_immobile', 100.0)
        perc_mut = immobile.get('perc_famiglia_mutuo', 100.0)
        
        val_att_fam = val_att * (perc_imm / 100.0)
        val_mut_fam = val_mut * (perc_mut / 100.0)
        
        valore_netto = val_att_fam - val_mut_fam
        
        colore_valore_attuale = AppColors.SUCCESS
        tooltip_valore = None
        
        header_row_controls = [AppStyles.subheader_text(immobile.get('nome', 'Senza Nome'))]
        if is_nuda:
            header_row_controls.append(
                ft.Container(
                    content=ft.Text("NUDA PROPRIETÀ", size=10, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                    bgcolor=ft.Colors.ORANGE_700,
                    padding=ft.padding.symmetric(horizontal=8, vertical=4),
                    border_radius=4,
                    tooltip="Valore non conteggiato nei totali"
                )
            )
            colore_valore_attuale = AppColors.TEXT_SECONDARY
            tooltip_valore = "Escluso dai totali"
            
        content = ft.Column([
            ft.Row([
                ft.Row(header_row_controls, alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                ft.Text(f"{immobile.get('via', '')}, {immobile.get('citta', '')}", size=12, italic=True,
                        color=AppColors.TEXT_SECONDARY)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            # Info Quote
            ft.Row([
                AppStyles.caption_text(f"Quota Famiglia: {perc_imm:.0f}%" + (f" (Mutuo: {perc_mut:.0f}%)" if val_mut > 0 else "")),
            ]) if perc_imm < 100 or perc_mut < 100 else ft.Container(),

            ft.Divider(height=5, color=ft.Colors.TRANSPARENT),
            ft.Row([
                self._crea_info_immobile(loc.get("purchase_value"),
                                         loc.format_currency(val_acq), theme),
                self._crea_info_immobile(loc.get("current_value"),
                                         loc.format_currency(val_att_fam) + (f" (su {loc.format_currency(val_att)})" if perc_imm < 100 else ""),
                                         theme, colore_valore=colore_valore_attuale),
            ]),
            ft.Row([
                self._crea_info_immobile(loc.get("residual_mortgage"),
                                         loc.format_currency(val_mut_fam) + (f" (su {loc.format_currency(val_mut)})" if perc_mut < 100 else ""), theme),
                self._crea_info_immobile("Valore Netto (Quota)", loc.format_currency(valore_netto), theme, colore_valore=AppColors.PRIMARY),
            ]),
            ft.Row([
                ft.IconButton(icon=ft.Icons.EDIT, tooltip=loc.get("edit"), data=immobile,
                              icon_color=AppColors.PRIMARY,
                              on_click=lambda e: self.controller.immobile_dialog.apri_dialog_immobile(
                                  e.control.data)),
                ft.IconButton(icon=ft.Icons.DELETE, tooltip=loc.get("delete"), icon_color=AppColors.ERROR,
                              data=immobile['id_immobile'],
                              on_click=lambda e: self.controller.open_confirm_delete_dialog(
                                  partial(self.elimina_cliccato, e))),
            ], alignment=ft.MainAxisAlignment.END)
        ])
        
        return AppStyles.card_container(content, padding=15)

    def _crea_info_immobile(self, etichetta, valore, theme, colore_valore=None):
        return ft.Column([
            AppStyles.caption_text(etichetta),
            ft.Text(str(valore), size=16, weight=ft.FontWeight.BOLD, color=colore_valore)
        ], horizontal_alignment=ft.CrossAxisAlignment.START)

    def elimina_cliccato(self, e):
        id_immobile = e.control.data
        if not id_immobile: return
        
        # Elimina usando la logica sincrona (va bene per azioni utente singole)
        # O si può rendere async anche questo se serve
        success = elimina_immobile(id_immobile)
        if success:
            self.controller.show_snack_bar("Immobile eliminato con successo.", success=True)
            # Ricarica i dati (userà la nuova logica async)
            self.update_view_data()
            self.controller.db_write_operation() # Questo ricarica tutto, forse ridondante se chiamiamo update_view_data
        else:
            self.controller.show_snack_bar("Errore durante l'eliminazione dell'immobile.", success=False)