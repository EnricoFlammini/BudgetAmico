
import flet as ft
from db.gestione_db import (
    aggiungi_carta, modifica_carta
)
import datetime

class CardDialog:
    def __init__(self, page, callback, card=None):
        self.page = page
        self.callback = callback
        self.card = card  # If provided, internal edit mode
        self.is_edit = card is not None
        
        self.dlg = None
        self.file_picker_icona = ft.FilePicker(on_result=self._on_file_picker_result)
        self._build_dialog()

        # Personalizzazione
        self.selected_icon_value = self.card.get('icona') if self.card else None
        self.selected_color_value = self.card.get('colore') if self.card else None

    def _build_dialog(self):
        # Fields
        self.txt_nome = ft.TextField(label="Nome Carta", value=self.card['nome_carta'] if self.card else "")
        
        self.dd_tipo = ft.Dropdown(
            label="Tipo",
            options=[
                ft.dropdown.Option("credito", "Carta di Credito"),
                ft.dropdown.Option("debito", "Carta di Debito"),
            ],
            value=self.card['tipo_carta'] if self.card else "credito",
            on_change=self._on_type_change
        )
        
        self.dd_circuito = ft.Dropdown(
            label="Circuito",
            options=[
                ft.dropdown.Option("visa", "Visa"),
                ft.dropdown.Option("mastercard", "Mastercard"),
                ft.dropdown.Option("amex", "American Express"),
                ft.dropdown.Option("maestro", "Maestro"),
                ft.dropdown.Option("altro", "Altro"),
            ],
            value=self.card['circuito'] if self.card else "visa"
        )
        
        self.accounts = self._fetch_accounts()
        ref_opts = []
        for a in self.accounts:
            # type_code: 'P' = Personal, 'S' = Shared
            val = f"{a['type_code']}:{a['id']}"
            ref_opts.append(ft.dropdown.Option(val, a['nome_display']))

        curr_val = None
        if self.card:
            if self.card.get('id_conto_riferimento'):
                curr_val = f"P:{self.card['id_conto_riferimento']}"
            elif self.card.get('id_conto_riferimento_condiviso'):
                curr_val = f"S:{self.card['id_conto_riferimento_condiviso']}"

        self.dd_conto_rif = ft.Dropdown(
            label="Conto di Addebito (Banca)",
            options=ref_opts,
            value=curr_val
        )

        # New Fields
        self.txt_massimale = ft.TextField(
            label="Massimale Mensile (€)", 
            value=str(self.card['massimale']) if self.card and self.card.get('massimale') else "",
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.txt_costo_tenuta = ft.TextField(
            label="Costo Tenuta (€)",
            value=str(self.card['spesa_tenuta']) if self.card and self.card.get('spesa_tenuta') else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=180
        )
        
        self.txt_giorno_tenuta = ft.TextField(
            label="Giorno Addebito Costo (1-31)",
            value=str(self.card['giorno_addebito_tenuta']) if self.card and self.card.get('giorno_addebito_tenuta') else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200,
            helper_text="Giorno del mese in cui viene addebitato il canone"
        )

        self.txt_soglia_azzeramento = ft.TextField(
            label="Soglia Azzeramento (€)",
            value=str(self.card['soglia_azzeramento']) if self.card and self.card.get('soglia_azzeramento') else "",
            keyboard_type=ft.KeyboardType.NUMBER,
            helper_text="Importo minimo per azzerare il canone"
        )
        
        row_costi = ft.Row([self.txt_costo_tenuta, self.txt_giorno_tenuta], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)

        # Credit specific
        self.txt_giorno = ft.TextField(
            label="Giorno Addebito Saldo (1-31)",
            value=str(self.card['giorno_addebito']) if self.card and self.card.get('giorno_addebito') else "",
            keyboard_type=ft.KeyboardType.NUMBER
        )
        
        self.credit_fields = ft.Column([
            self.txt_giorno
        ], visible=(self.dd_tipo.value == "credito"))

        # Personalizzazione UI
        from utils.styles import AppStyles
        self.icon_preview = ft.Icon(ft.Icons.CREDIT_CARD, size=30)
        self.btn_icon_selector = ft.IconButton(
            icon=ft.Icons.AUTO_AWESOME_OUTLINED,
            on_click=self._apri_selettore_icona
        )
        
        self.color_preview = ft.Container(width=30, height=30, border_radius=15, bgcolor=ft.Colors.BLUE_GREY_700)
        self.btn_color_selector = ft.IconButton(
            icon=ft.Icons.COLOR_LENS_OUTLINED,
            on_click=self._apri_selettore_colore
        )
        
        self.container_personalizzazione = ft.Container(
            content=ft.Row([
                ft.Row([ft.Text("Icona:", size=12, weight="bold"), self.icon_preview, self.btn_icon_selector], spacing=5),
                ft.Row([ft.Text("Colore:", size=12, weight="bold"), self.color_preview, self.btn_color_selector], spacing=5),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=5,
            border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
            border_radius=8
        )

        self.dlg = ft.AlertDialog(
            title=ft.Text("Modifica Carta" if self.is_edit else "Nuova Carta"),
            content=ft.Column([
                self.txt_nome,
                self.dd_tipo,
                self.dd_circuito,
                self.dd_conto_rif,
                ft.Divider(),
                ft.Divider(),
                self.container_personalizzazione,
                self.txt_massimale,
                row_costi,
                self.txt_soglia_azzeramento,
                ft.Divider(),
                self.credit_fields
            ], width=350, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.TextButton("Annulla", on_click=self._close),
                ft.ElevatedButton("Salva", on_click=self._save)
            ],
            on_dismiss=lambda e: print("Dialog dismissed")
        )

    def _on_type_change(self, e):
        is_credit = self.dd_tipo.value == "credito"
        self.credit_fields.visible = is_credit
        self.page.update()

    def _fetch_accounts(self):
        user = self.page.session.get("utente_loggato")
        fam_id = self.page.session.get("id_famiglia")
        mk = self.page.session.get("master_key")
        
        if not user or not fam_id: return []
        return self._manual_fetch_accounts(fam_id, user['id'], mk)

    def _manual_fetch_accounts(self, id_famiglia, id_utente, master_key):
        from db.gestione_db import ottieni_tutti_i_conti_utente
        
        accs = []
        try:
            # Centralized fetch (decryption handled inside)
            conti = ottieni_tutti_i_conti_utente(id_utente, master_key_b64=master_key)
            
            for c in conti:
                # Filtra conti: Solo Conto Corrente (o Corrente) o Conto Risparmio possono essere collegati ad una carta
                # Tipi supportati: 'Corrente', 'Conto Corrente', 'Risparmio', 'Conto Risparmio'
                if c['tipo'] not in ['Conto Corrente', 'Conto Risparmio', 'Corrente', 'Risparmio']: continue
                
                # Format name based on type
                prefix = "[Personale]" if not c['is_condiviso'] else "[Condiviso]"
                type_code = 'P' if not c['is_condiviso'] else 'S'
                
                # Use decrypted name if available, else fallback
                display_name = c['nome_conto']
                
                accs.append({
                    'id': c['id_conto'], 
                    'nome_display': f"{prefix} {display_name}", 
                    'type_code': type_code
                })
                    
        except Exception as e:
            print(f"Error fetching accounts: {e}")
        return accs

    def open(self):
        if hasattr(self.page, "open"):
            self.page.open(self.dlg)
        else:
            self.page.dialog = self.dlg
            self.dlg.open = True
            
        if self.file_picker_icona not in self.page.overlay:
            self.page.overlay.append(self.file_picker_icona)
            
        self._aggiorna_preview_personalizzazione()
        self.page.update()

    def _close(self, e):
        if hasattr(self.page, "close"):
            self.page.close(self.dlg)
        else:
            self.dlg.open = False
            self.page.update()

    def _save(self, e):
        # Validation
        if not self.txt_nome.value:
            self.txt_nome.error_text = "Nome obbligatorio"
            self.page.update()
            return
            
        user = self.page.session.get("utente_loggato")
        mk = self.page.session.get("master_key")
        
        # Parse Account Selection
        id_conto_rif = None
        id_conto_rif_condiviso = None
        
        if self.dd_conto_rif.value:
            parts = self.dd_conto_rif.value.split(":")
            if len(parts) == 2:
                type_code, acc_id = parts
                if type_code == 'P':
                    id_conto_rif = int(acc_id)
                elif type_code == 'S':
                    id_conto_rif_condiviso = int(acc_id)

        # Collect data
        data = {
            'nome_carta': self.txt_nome.value,
            'tipo_carta': self.dd_tipo.value,
            'circuito': self.dd_circuito.value,
            'id_conto_riferimento': id_conto_rif,
            'id_conto_riferimento_condiviso': id_conto_rif_condiviso,
            'addebito_automatico': True, # Implied for Credit, meaningless/instant for Debit
            'master_key_b64': mk,
            'icona': self.selected_icon_value,
            'colore': self.selected_color_value
        }
        if self.dd_tipo.value == "debito":
            # For Debit Cards, Accounting Account must match Reference Account (Checking)
            data['id_conto_contabile'] = id_conto_rif
            data['id_conto_contabile_condiviso'] = id_conto_rif_condiviso
        
        # Parse numeric fields
        try:
            if self.txt_massimale.value:
                data['massimale'] = float(self.txt_massimale.value)
            if self.txt_costo_tenuta.value:
                data['spesa_tenuta'] = float(self.txt_costo_tenuta.value)
            if self.txt_soglia_azzeramento.value:
                data['soglia_azzeramento'] = float(self.txt_soglia_azzeramento.value)
            if self.txt_giorno_tenuta.value:
                data['giorno_addebito_tenuta'] = int(self.txt_giorno_tenuta.value)
        except ValueError:
            self.txt_massimale.error_text = "Valori numerici non validi"
            self.page.update()
            return

        if self.dd_tipo.value == "credito":
            if not self.txt_giorno.value:
                self.txt_giorno.error_text = "Giorno obbligatorio"
                self.page.update()
                return
            try:
                giorno = int(self.txt_giorno.value)
                if not (1 <= giorno <= 31):
                    raise ValueError
                data['giorno_addebito'] = giorno
            except ValueError:
                self.txt_giorno.error_text = "Inserire giorno 1-31"
                self.page.update()
                return

        success = False
        if self.is_edit:
            success = modifica_carta(self.card['id_carta'], **data)
        else:
            # Add has different signature slightly (id_utente first)
            data.pop('master_key_b64') 
            success = aggiungi_carta(user['id'], 
                                     data['nome_carta'], data['tipo_carta'], data['circuito'],
                                     id_conto_riferimento=data.get('id_conto_riferimento'),
                                     id_conto_riferimento_condiviso=data.get('id_conto_riferimento_condiviso'),
                                     massimale=data.get('massimale'),
                                     giorno_addebito=data.get('giorno_addebito'),
                                     spesa_tenuta=data.get('spesa_tenuta'),
                                     soglia_azzeramento=data.get('soglia_azzeramento'),
                                     giorno_addebito_tenuta=data.get('giorno_addebito_tenuta'),
                                     addebito_automatico=data['addebito_automatico'],
                                     master_key=mk,
                                     icona=self.selected_icon_value,
                                     colore=self.selected_color_value)

        if success:
            self.callback()
            self._close(None)
        else:
            print("Error saving card") 
            self._close(None)

    def _aggiorna_preview_personalizzazione(self):
        from utils.styles import AppStyles
        self.icon_preview.content = AppStyles.get_logo_control(
            tipo=self.dd_tipo.value or "debito",
            circuito=self.dd_circuito.value,
            size=30,
            icona=self.selected_icon_value,
            colore=self.selected_color_value
        )
        self.color_preview.bgcolor = self.selected_color_value if self.selected_color_value else ft.Colors.BLUE_GREY_700
        if self.dlg.open:
            self.container_personalizzazione.update()

    def _apri_selettore_icona(self, e):
        icone_comuni = [
            ("Default", None),
            ("Carta 1", "CREDIT_CARD"),
            ("Carta 2", "PAYMENT"),
            ("Shopping", "SHOPPING_CART"),
            ("Contanti", "MONEY"),
        ]
        items = []
        for nome, val in icone_comuni:
            items.append(
                ft.ListTile(
                    leading=ft.Icon(getattr(ft.Icons, val) if val else ft.Icons.CREDIT_CARD),
                    title=ft.Text(nome),
                    on_click=lambda ev, v=val: self._seleziona_icona(v)
                )
            )
        # --- Icone Custom ---
        try:
            from db.gestione_db import lista_icone_personalizzate
            custom_icons = lista_icone_personalizzate()
            
            if custom_icons:
                items.append(ft.Divider())
                items.append(ft.Text("Icone Personalizzate", size=12, color=ft.Colors.GREY, weight=ft.FontWeight.BOLD))
                
                for icon_file in custom_icons:
                    items.append(
                        ft.ListTile(
                            leading=ft.Image(src=f"/icons/custom/{icon_file}", width=32, height=32, fit=ft.ImageFit.CONTAIN),
                            title=ft.Text(icon_file, size=12),
                            on_click=lambda ev, v=f"custom/{icon_file}": self._seleziona_icona(v)
                        )
                    )
        except Exception as ex:
            print(f"Errore caricamento icone custom: {ex}")

        items.append(ft.Divider())
        items.append(
             ft.ListTile(
                leading=ft.Icon(ft.Icons.UPLOAD),
                title=ft.Text("Carica Icona PNG..."),
                on_click=self._avvia_upload_icona
            )
        )
        self._picker_dlg = ft.AlertDialog(
            title=ft.Text("Seleziona Icona"),
            content=ft.Container(content=ft.Column(items, scroll=ft.ScrollMode.AUTO, height=300), width=300)
        )
        self.page.open(self._picker_dlg)

    def _seleziona_icona(self, icon_name):
        self.selected_icon_value = icon_name
        self._aggiorna_preview_personalizzazione()
        self.page.close(self._picker_dlg)

    def _avvia_upload_icona(self, e):
        self.file_picker_icona.pick_files(allowed_extensions=["png", "jpg", "jpeg"])

    def _on_file_picker_result(self, e: ft.FilePickerResultEvent):
        if not e.files: return
        file = e.files[0]
        from db.gestione_db import salva_icona_personalizzata
        with open(file.path, "rb") as f:
            file_bytes = f.read()
        import datetime
        ext = file.name.split('.')[-1]
        safe_name = f"card_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}.{ext}"
        if salva_icona_personalizzata(safe_name, file_bytes):
            self.selected_icon_value = f"custom/{safe_name}"
            self._aggiorna_preview_personalizzazione()
            if hasattr(self, '_picker_dlg') and self._picker_dlg: self.page.close(self._picker_dlg)

    def _apri_selettore_colore(self, e):
        from utils.color_utils import MATERIAL_COLORS
        grid = ft.GridView(expand=True, runs_count=6, max_extent=50, spacing=5, run_spacing=5)
        for color in MATERIAL_COLORS:
            grid.controls.append(
                ft.Container(bgcolor=color, width=40, height=40, border_radius=20, on_click=lambda ev, c=color: self._seleziona_colore(c))
            )
        self._picker_dlg = ft.AlertDialog(title=ft.Text("Seleziona Colore"), content=ft.Container(content=grid, width=300, height=300))
        self.page.open(self._picker_dlg)

    def _seleziona_colore(self, color):
        self.selected_color_value = color
        self._aggiorna_preview_personalizzazione()
        self.page.close(self._picker_dlg)

