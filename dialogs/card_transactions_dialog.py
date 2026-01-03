import flet as ft
import datetime
from db.gestione_db import ottieni_transazioni_carta, ottieni_mesi_disponibili_carta

class CardTransactionsDialog(ft.AlertDialog):
    def __init__(self, page, id_carta, nome_carta, master_key_b64, controller):
        self.page_ref = page
        self.id_carta = id_carta
        self.nome_carta = nome_carta
        self.master_key_b64 = master_key_b64
        self.controller = controller
        
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
        
        self.txt_totale = ft.Text("Totale: € 0.00", size=16, weight=ft.FontWeight.BOLD)
        
        super().__init__(
            title=ft.Text(f"Movimenti: {self.nome_carta}"),
            content=ft.Column(
                controls=[
                    self.dd_mesi,
                    ft.Divider(),
                    self.lv_transazioni,
                    ft.Divider(),
                    self.txt_totale
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

    def _carica_mesi(self):
        mesi_disponibili = ottieni_mesi_disponibili_carta(self.id_carta)
        
        if not mesi_disponibili:
            # Se non ci sono transazioni, disabilita tutto
            self.dd_mesi.options.append(ft.dropdown.Option("Nessuna transazione"))
            self.dd_mesi.value = "Nessuna transazione"
            self.dd_mesi.disabled = True
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
        if self.dd_mesi.value:
            self._carica_transazioni(self.dd_mesi.value)

    def _carica_transazioni(self, mese_anno_str):
        self.lv_transazioni.controls.clear()
        
        try:
            mese, anno = map(int, mese_anno_str.split('-'))
            id_utente = self.controller.get_user_id()
            
            transazioni = ottieni_transazioni_carta(
                self.id_carta, mese, anno, 
                master_key_b64=self.master_key_b64,
                id_utente=id_utente
            )
            
            totale = 0.0
            
            if not transazioni:
                 self.lv_transazioni.controls.append(ft.Text("Nessuna transazione in questo mese."))
            
            for t in transazioni:
                amount = float(t['importo'])
                totale += amount
                
                # Formattazione
                date_str = datetime.datetime.strptime(str(t['data']), '%Y-%m-%d').strftime('%d/%m/%Y')
                desc = t['descrizione'] or "Senza descrizione"
                cat = t['nome_sottocategoria'] or t['nome_categoria'] or "Nessuna Categoria"
                user_label = f" ({t.get('autore')})" if t.get('tipo') == 'Condivisa' and t.get('autore') else ""
                
                color_amount = ft.Colors.RED if amount < 0 else ft.Colors.GREEN
                
                # Item UI
                item = ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Text(f"{date_str}", size=12, color=ft.Colors.GREY),
                            ft.Text(f"{desc}{user_label}", size=14, weight=ft.FontWeight.W_500, overflow=ft.TextOverflow.ELLIPSIS),
                            ft.Text(f"{cat}", size=12, italic=True)
                        ], expand=True),
                        ft.Text(f"€ {amount:,.2f}", color=color_amount, weight=ft.FontWeight.BOLD)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=10,
                    border=ft.border.only(bottom=ft.border.BorderSide(1, ft.Colors.GREY_300))
                )
                self.lv_transazioni.controls.append(item)
            
            self.txt_totale.value = f"Totale: € {totale:,.2f}"
            self.page_ref.update()
            
        except Exception as e:
            print(f"Errore caricamento transazioni: {e}")
            self.lv_transazioni.controls.append(ft.Text("Errore durante il caricamento."))
