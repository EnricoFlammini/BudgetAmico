import flet as ft
import datetime
import traceback
import pandas as pd
import io
from utils.logger import setup_logger

logger = setup_logger("ExportView")

# Importa le funzioni DB necessarie
from db.gestione_db import (
    ottieni_anni_mesi_storicizzati,
    ottieni_transazioni_famiglia_per_export,
    ottieni_storico_budget_per_export,
    ottieni_riepilogo_conti_famiglia,
    ottieni_dettaglio_portafogli_famiglia,
    ottieni_ruolo_utente
)


class ExportView:
    def __init__(self, controller):
        self.controller = controller
        self.page = controller.page

        # --- Controlli della Vista ---

        self.chk_export_transazioni = ft.Checkbox(label="Esporta Transazioni Familiari", value=True)
        self.txt_export_data_inizio = ft.TextField(label="Data Inizio (YYYY-MM-DD)", width=200)
        self.txt_export_data_fine = ft.TextField(label="Data Fine (YYYY-MM-DD)", width=200)

        self.chk_export_budget = ft.Checkbox(label="Esporta Storico Budget", value=True)
        self.chk_export_budget_tutti = ft.Checkbox(
            label="Seleziona tutti i periodi",
            value=True,
            on_change=self._toggle_selezione_periodi
        )
        self.lv_export_periodi = ft.ListView(expand=True, spacing=5)

        self.chk_export_conti = ft.Checkbox(label="Esporta Riepilogo Conti e Totali", value=True)
        self.chk_export_portafogli = ft.Checkbox(label="Esporta Dettaglio Portafogli (Asset)", value=True)
        
        # Nuove Opzioni
        self.chk_export_immobili = ft.Checkbox(label="Esporta Patrimonio Immobiliare", value=True)
        self.chk_export_prestiti = ft.Checkbox(label="Esporta Prestiti e Mutui", value=True)
        self.chk_export_spese_fisse = ft.Checkbox(label="Esporta Spese Fisse", value=True)

    def build_view(self) -> ft.View:
        """ Costruisce e restituisce la vista di Esportazione """
        return ft.View(
            "/export",
            scroll=ft.ScrollMode.ADAPTIVE,
            controls=[
                ft.Text("Esporta Dati", size=30, weight=ft.FontWeight.BOLD),

                # Sezione Transazioni
                ft.Container(
                    content=ft.Column([
                        self.chk_export_transazioni,
                        ft.Row([self.txt_export_data_inizio, self.txt_export_data_fine])
                    ]),
                    padding=10, border=ft.border.all(1, ft.Colors.GREY_800), border_radius=5
                ),
                ft.Divider(height=10),

                # Sezione Budget
                ft.Container(
                    content=ft.Column([
                        self.chk_export_budget,
                        self.chk_export_budget_tutti,
                        ft.Container(
                            content=self.lv_export_periodi,
                            height=150,
                            border=ft.border.all(1, ft.Colors.GREY_800)
                        )
                    ]),
                    padding=10, border=ft.border.all(1, ft.Colors.GREY_800), border_radius=5
                ),
                ft.Divider(height=10),

                # Sezione Conti e Portafogli
                ft.Container(
                    content=ft.Column([
                        self.chk_export_conti,
                        self.chk_export_portafogli,
                        self.chk_export_immobili,
                        self.chk_export_prestiti,
                        self.chk_export_spese_fisse,
                    ]),
                    padding=10, border=ft.border.all(1, ft.Colors.GREY_800), border_radius=5
                ),

                # Pulsante Esporta
                ft.ElevatedButton(
                    "Genera e Scarica Excel",
                    icon=ft.Icons.DOWNLOAD,
                    on_click=self._clicca_esporta_excel,
                    height=50,
                    style=ft.ButtonStyle(bgcolor=ft.Colors.GREEN_700, color=ft.Colors.WHITE)
                )
            ],
            appbar=ft.AppBar(
                title=ft.Text("Pagina di Esportazione"),
                leading=ft.IconButton(
                    icon=ft.Icons.ARROW_BACK,
                    tooltip="Torna alla Dashboard",
                    on_click=lambda _: self.page.go("/dashboard")
                )
            ),
            padding=20,
            spacing=10
        )

    def update_view_data(self):
        """
        Chiamata dal controller quando si naviga a /export.
        Popola i campi con dati aggiornati.
        NON chiama .update() per evitare l'AssertionError.
        """
        famiglia_id = self.controller.get_family_id()
        if not famiglia_id:
            return

        # Popola i periodi storici per l'export del budget
        self.lv_export_periodi.controls.clear()
        periodi_storici = ottieni_anni_mesi_storicizzati(famiglia_id)

        if not periodi_storici:
            self.lv_export_periodi.controls.append(ft.Text("Nessun periodo storicizzato trovato."))

        for p in periodi_storici:
            periodo_key = (p['anno'], p['mese'])
            periodo_label = f"{p['mese']:02d}/{p['anno']}"
            self.lv_export_periodi.controls.append(
                ft.Checkbox(label=periodo_label, value=True, data=periodo_key)
            )

        # Imposta le date di default per l'export transazioni (mese corrente)
        now = datetime.datetime.now()
        primo_giorno = now.replace(day=1).strftime('%Y-%m-%d')
        self.txt_export_data_inizio.value = primo_giorno
        self.txt_export_data_inizio.value = primo_giorno
        self.txt_export_data_fine.value = now.strftime('%Y-%m-%d')
        
        # --- Applica Restrizioni per Ruolo ---
        ruolo = self.controller.get_user_role()
        
        # Livello 3: Accesso Negato (Security Fallback)
        if ruolo == 'livello3':
            self.controller.show_snack_bar("Accesso negato: Funzione riservata.", success=False)
            self.page.go("/dashboard")
            return

        # Livello 2: Solo Transazioni Personali
        if ruolo == 'livello2':
            self.chk_export_transazioni.label = "Esporta Le Mie Transazioni"
            self.chk_export_transazioni.update()

    def _toggle_selezione_periodi(self, e):
        for chk in self.lv_export_periodi.controls:
            if isinstance(chk, ft.Checkbox):
                chk.value = e.control.value
        self.lv_export_periodi.update()

    def on_file_picker_result(self, e):
        """ Callback gestito dall'AppController """
        pass

    def _clicca_esporta_excel(self, _):
        famiglia_id = self.controller.get_family_id()
        if not famiglia_id:
            self.controller.show_snack_bar("❌ Errore: Famiglia non trovata.", success=False)
            return

        # Retrieve keys from session
        master_key_b64 = self.page.session.get("master_key")
        user_id = self.controller.get_user_id()

        try:
            dati_transazioni = []
            dati_budget = []
            dati_conti = []
            dati_portafogli = []
            dati_immobili = []
            dati_prestiti = []
            dati_spese_fisse = []

            # 1. Prepara Dati Transazioni
            if self.chk_export_transazioni.value:
                data_inizio = self.txt_export_data_inizio.value
                data_fine = self.txt_export_data_fine.value
                if not (data_inizio and data_fine):
                    self.txt_export_data_inizio.error_text = "Obbligatorio" if not data_inizio else None
                    self.txt_export_data_fine.error_text = "Obbligatorio" if not data_fine else None
                    self.txt_export_data_inizio.update()
                    self.txt_export_data_fine.update()
                    return
                self.txt_export_data_inizio.error_text = None
                self.txt_export_data_fine.error_text = None
                self.txt_export_data_inizio.update()
                self.txt_export_data_fine.update()
                
                # Setup filtro utente per Livello 2
                ruolo = self.controller.get_user_role()
                filtra_utente_id = user_id if ruolo == 'livello2' else None
                
                dati_transazioni = ottieni_transazioni_famiglia_per_export(
                    famiglia_id, data_inizio, data_fine, master_key_b64, user_id, 
                    filtra_utente_id=filtra_utente_id
                )

            # 2. Prepara Dati Budget
            if self.chk_export_budget.value:
                periodi_selezionati = []
                for chk in self.lv_export_periodi.controls:
                    if isinstance(chk, ft.Checkbox) and chk.value:
                        periodi_selezionati.append(chk.data)
                if periodi_selezionati:
                    dati_budget = ottieni_storico_budget_per_export(
                        famiglia_id, periodi_selezionati, master_key_b64, user_id
                    )

            # 3. Prepara Dati Conti
            if self.chk_export_conti.value:
                dati_conti = ottieni_riepilogo_conti_famiglia(famiglia_id, master_key_b64, user_id)

            # 4. Prepara Dati Portafogli
            if self.chk_export_portafogli.value:
                dati_portafogli = ottieni_dettaglio_portafogli_famiglia(famiglia_id, master_key_b64, user_id)

            # 5. Prepara Dati Immobili
            if self.chk_export_immobili.value:
                # Import here to avoid circular dependencies if not already imported
                from db.gestione_db import ottieni_dati_immobili_famiglia_per_export
                dati_immobili = ottieni_dati_immobili_famiglia_per_export(famiglia_id, master_key_b64, user_id)

            # 6. Prepara Dati Prestiti
            if self.chk_export_prestiti.value:
                from db.gestione_db import ottieni_dati_prestiti_famiglia_per_export
                dati_prestiti = ottieni_dati_prestiti_famiglia_per_export(famiglia_id, master_key_b64, user_id)
            
            # 7. Prepara Dati Spese Fisse
            if self.chk_export_spese_fisse.value:
                from db.gestione_db import ottieni_dati_spese_fisse_famiglia_per_export
                dati_spese_fisse = ottieni_dati_spese_fisse_famiglia_per_export(famiglia_id, master_key_b64, user_id)

            if not any([dati_transazioni, dati_budget, dati_conti, dati_portafogli, 
                        dati_immobili, dati_prestiti, dati_spese_fisse]):
                self.controller.show_snack_bar("Nessun dato selezionato o trovato.", success=False)
                return

            # 8. Crea l'Excel in memoria
            output_bytes = io.BytesIO()
            with pd.ExcelWriter(output_bytes, engine='openpyxl') as writer:
                if dati_transazioni:
                    pd.DataFrame(dati_transazioni).to_excel(writer, sheet_name='Transazioni_Famiglia', index=False)
                if dati_budget:
                    pd.DataFrame(dati_budget).to_excel(writer, sheet_name='Storico_Budget', index=False)

                if dati_conti:
                    df_conti_completo = pd.DataFrame(dati_conti)
                    df_liquidi = df_conti_completo[df_conti_completo['tipo'] != 'Investimento']
                    if not df_liquidi.empty:
                        df_totali_tipo = df_liquidi.groupby(['tipo', 'membro'])['saldo_calcolato'].sum().reset_index()
                        df_totali_tipo.columns = ['Tipo Conto', 'Intestatario', 'Saldo Totale']
                        df_totali_tipo = df_totali_tipo.sort_values(by=['Tipo Conto', 'Intestatario'])
                        df_totali_tipo.to_excel(writer, sheet_name='Totali_Conti_Liquidi', index=False)
                        df_liquidi.to_excel(writer, sheet_name='Dettaglio_Conti_Liquidi', index=False)

                    df_investimenti = df_conti_completo[df_conti_completo['tipo'] == 'Investimento']
                    if not df_investimenti.empty:
                        df_investimenti.to_excel(writer, sheet_name='Riepilogo_Investimenti', index=False)

                if dati_portafogli:
                    pd.DataFrame(dati_portafogli).to_excel(writer, sheet_name='Dettaglio_Portafogli', index=False)
                
                if dati_immobili:
                    pd.DataFrame(dati_immobili).to_excel(writer, sheet_name='Patrimonio_Immobiliare', index=False)
                    
                if dati_prestiti:
                    pd.DataFrame(dati_prestiti).to_excel(writer, sheet_name='Prestiti_Mutui', index=False)
                    
                if dati_spese_fisse:
                     pd.DataFrame(dati_spese_fisse).to_excel(writer, sheet_name='Spese_Fisse', index=False)

            output_bytes.seek(0)
            file_data_bytes = output_bytes.getvalue()

            # 9. Salva i byte nella sessione
            self.page.session.set("excel_export_data", file_data_bytes)

            # 10. Apri il dialogo "Salva con nome"
            self.controller.file_picker_salva_excel.save_file(
                file_name=f"Report_Budget_Famiglia_{datetime.date.today()}.xlsx"
            )

        except Exception as ex:
            logger.error(f"Errore durante l'esportazione Excel: {ex}", exc_info=True)
            self.controller.show_snack_bar(f"❌ Errore imprevisto durante l'esportazione: {ex}", success=False)