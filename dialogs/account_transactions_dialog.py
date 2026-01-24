
import flet as ft
import datetime
from db.gestione_db import (
    ottieni_transazioni_conto_mese, 
    ottieni_mesi_disponibili_conto,
    ottieni_transazioni_conto_condiviso_mese,
    ottieni_mesi_disponibili_conto_condiviso,
    modifica_transazione,
    modifica_transazione_condivisa,
    elimina_transazione # Might need this too if I add delete button, but let's stick to edit for now. Actually user didn't ask for delete, but it's good practice. existing file didn't import it.
)
from utils.styles import AppStyles

class AccountTransactionsDialog(ft.AlertDialog):
    def __init__(self, page, id_conto, nome_conto, master_key_b64, controller, is_shared=False):
        self.page_ref = page
        self.id_conto = id_conto
        self.nome_conto = nome_conto
        self.master_key_b64 = master_key_b64
        self.controller = controller
        self.is_shared = is_shared
        
        self.dd_mesi = ft.Dropdown(
            label="Seleziona Mese",
            width=200,
            on_change=self._on_month_change
        )
        
        self.lv_transazioni = ft.ListView(
            expand=True,
            spacing=10,
            padding=10,
            height=400
        )
        
        self.txt_totale = ft.Text("Totale Movimenti: € 0.00", size=16, weight=ft.FontWeight.BOLD)
        
        # DatePicker per modifica
        self.date_picker = ft.DatePicker(
            on_change=self._on_date_change,
            first_date=datetime.datetime(2000, 1, 1),
            last_date=datetime.datetime(2099, 12, 31)
        )
        # Aggiungilo all'overlay subito se possibile, o gestiscilo dopo.
        # Poiché passiamo 'page' nel costruttore, possiamo provare ad aggiungerlo qui se page ha overlay.
        try:
            if self.date_picker not in self.page_ref.overlay:
                self.page_ref.overlay.append(self.date_picker)
        except:
             pass 

        super().__init__(
            title=ft.Text(f"Movimenti: {self.nome_conto}"),
            content=ft.Column(
                controls=[
                    self.dd_mesi,
                    ft.Divider(),
                    self.lv_transazioni,
                    ft.Divider(),
                    self.txt_totale,
                    AppStyles.small_text("Include solo transazioni registrate, non i giroconti interni.")
                ],
                width=500,
                height=500,
                scroll=ft.ScrollMode.AUTO
            ),
            actions=[
                ft.TextButton("Chiudi", on_click=self._chiudi)
            ],
            on_dismiss=lambda e: print("Dialog dismissed")
        )
        
        self._carica_mesi()

    def _chiudi(self, e):
        self.page_ref.close(self)

    def _on_date_change(self, e):
        if self.date_picker.value and hasattr(self, 'txt_mod_data'):
            self.txt_mod_data.value = self.date_picker.value.strftime('%Y-%m-%d')
            self.dialog_modifica.update()

    def _carica_mesi(self):
        if self.is_shared:
            mesi_disponibili = ottieni_mesi_disponibili_conto_condiviso(self.id_conto)
        else:
            mesi_disponibili = ottieni_mesi_disponibili_conto(self.id_conto)
        
        if not mesi_disponibili:
            # Se non ci sono transazioni, disabilita tutto
            self.dd_mesi.options.append(ft.dropdown.Option("Nessuna transazione"))
            self.dd_mesi.value = "Nessuna transazione"
            self.dd_mesi.disabled = True
            self.lv_transazioni.controls.append(ft.Text("Nessun movimento registrato."))
            return

        options = []
        for anno, mese in mesi_disponibili:
            nome_mese = datetime.date(anno, mese, 1).strftime('%B %Y')
            val = f"{mese}-{anno}" # formato value: "M-YYYY"
            options.append(ft.dropdown.Option(key=val, text=nome_mese))
        
        self.dd_mesi.options = options
        
        # Seleziona il primo (più recente)
        if options:
            self.dd_mesi.value = options[0].key
            self._carica_transazioni(options[0].key)

    def _on_month_change(self, e):
        if self.dd_mesi.value and self.dd_mesi.value != "Nessuna transazione":
            self._carica_transazioni(self.dd_mesi.value)

    def _carica_transazioni(self, mese_anno_str):
        self.lv_transazioni.controls.clear()
        
        try:
            mese, anno = map(int, mese_anno_str.split('-'))
            id_utente = self.controller.get_user_id()
            id_famiglia = self.controller.get_family_id()
            
            if self.is_shared:
                transazioni = ottieni_transazioni_conto_condiviso_mese(
                    self.id_conto, mese, anno, 
                    master_key_b64=self.master_key_b64,
                    id_utente=id_utente,
                    id_famiglia=id_famiglia
                )
            else:
                transazioni = ottieni_transazioni_conto_mese(
                    self.id_conto, mese, anno, 
                    master_key_b64=self.master_key_b64,
                    id_utente=id_utente,
                    id_famiglia=id_famiglia
                )
            
            totale_periodo = 0.0
            
            if not transazioni:
                 self.lv_transazioni.controls.append(ft.Text("Nessuna transazione in questo mese."))
            
            for t in transazioni:
                amount = float(t['importo'])
                totale_periodo += amount
                
                date_str = datetime.datetime.strptime(str(t['data']), '%Y-%m-%d').strftime('%d/%m/%Y')
                desc = t.get('descrizione') or "Senza descrizione"
                cat = t.get('nome_sottocategoria') or t.get('nome_categoria') or "Nessuna Categoria"
                
                # Handling shared transactions label
                is_shared_tx = t.get('is_shared', False)
                autore = t.get('autore', '')
                user_label = f" ({autore})" if is_shared_tx and autore else ""
                
                color_amount = ft.Colors.RED if amount < 0 else ft.Colors.GREEN
                
                # Item UI
                item = ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(f"{date_str}", size=12, color=ft.Colors.GREY),
                            ft.Text(f"{desc}{user_label}", size=14, weight=ft.FontWeight.W_500, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(f"{cat}", size=12, italic=True)
                        ], expand=True),
                        ft.Row([
                            ft.Text(f"€ {amount:,.2f}", color=color_amount, weight=ft.FontWeight.BOLD),
                            ft.IconButton(
                                icon=ft.Icons.EDIT, 
                                icon_size=20, 
                                tooltip="Modifica Data/Dettagli",
                                data=t,
                                on_click=self._apri_dialog_modifica
                            )
                        ], alignment=ft.MainAxisAlignment.END, spacing=5)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=10,
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.GREY_300))
                )
                self.lv_transazioni.controls.append(item)
            
            self.txt_totale.value = f"Totale Periodo: € {totale_periodo:,.2f}"
            self.page_ref.update()
            
            self.page_ref.update()
            
        except Exception as e:
            print(f"Errore caricamento transazioni conto: {e}")
            self.lv_transazioni.controls.append(ft.Text(f"Errore: {e}"))
            self.page_ref.update()

    def _apri_dialog_modifica(self, e):
        self.transazione_in_modifica = e.control.data
        t = self.transazione_in_modifica
        
        # Campi modifica
        self.txt_mod_data = ft.TextField(label="Data", value=str(t['data']), width=200, read_only=True)
        btn_date = ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, on_click=lambda _: self.date_picker.pick_date())
        row_data = ft.Row([self.txt_mod_data, btn_date], spacing=5)

        self.txt_mod_desc = ft.TextField(label="Descrizione", value=t.get('descrizione', ''), width=300)
        self.txt_mod_importo = ft.TextField(label="Importo", value=str(t['importo']), width=150, keyboard_type=ft.KeyboardType.NUMBER)
        
        self.dialog_modifica = ft.AlertDialog(
            title=ft.Text("Modifica Transazione"),
            content=ft.Column([
                row_data,
                self.txt_mod_desc,
                self.txt_mod_importo,
                AppStyles.small_text("Attenzione: Modificare l'importo non aggiorna automaticamente i saldi degli asset, solo il saldo del conto.")
            ], tight=True, height=250),
            actions=[
                ft.TextButton("Annulla", on_click=self._chiudi_dialog_modifica),
                ft.TextButton("Salva", on_click=self._salva_modifica)
            ]
        )
        self.page_ref.open(self.dialog_modifica)
        self.page_ref.update()

    def _chiudi_dialog_modifica(self, e):
        self.page_ref.close(self.dialog_modifica)
        self.page_ref.update()

    def _salva_modifica(self, e):
        try:
            nuova_data = self.txt_mod_data.value
            nuova_desc = self.txt_mod_desc.value
            nuovo_importo = float(self.txt_mod_importo.value)
            
            # Validazione Data
            datetime.datetime.strptime(nuova_data, '%Y-%m-%d')
            
            t = self.transazione_in_modifica
            success = False
            
            if self.is_shared:
                success = modifica_transazione_condivisa(
                    t['id_transazione_condivisa'],
                    nuova_data,
                    nuova_desc,
                    nuovo_importo,
                    id_sottocategoria=t.get('id_sottocategoria'), # Mantieni categoria
                    master_key_b64=self.master_key_b64,
                    id_utente=self.controller.get_user_id()
                )
            else:
                success = modifica_transazione(
                    t['id_transazione'],
                    nuova_data,
                    nuova_desc,
                    nuovo_importo,
                    id_sottocategoria=t.get('id_sottocategoria'),
                    id_conto=self.id_conto, # Importante per ricalcoli
                    master_key_b64=self.master_key_b64
                )
            
            if success:
                self.controller.show_snack_bar("Transazione modificata.", success=True)
                self._chiudi_dialog_modifica(None)
                # Ricarica lista
                if self.dd_mesi.value:
                    self._carica_transazioni(self.dd_mesi.value)
                # Notifica aggiornamento dashboard
                self.controller.db_write_operation()
            else:
                self.controller.show_snack_bar("Errore durante la modifica.", success=False)
                
        except ValueError:
             self.controller.show_snack_bar("Dati non validi (controlla data e importo).", success=False)
