
import flet as ft
import datetime
from db.gestione_db import ottieni_carte_utente, elimina_carta, calcola_totale_speso_carta
from dialogs.card_dialog import CardDialog
from dialogs.card_transactions_dialog import CardTransactionsDialog

class TabCarte(ft.Container):
    def __init__(self, page_ctrl):
        super().__init__(padding=20, expand=True)
        self.page_ctrl = page_ctrl
        self.page = page_ctrl.page
        self.cards_view = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        
        self.content = ft.Column([
            ft.Row([
                ft.Text("Gestione Carte", size=24, weight=ft.FontWeight.BOLD),
                ft.IconButton(
                    icon=ft.Icons.ADD_CARD,
                    icon_color="primary", # Uses theme primary color
                    tooltip="Aggiungi Carta",
                    on_click=self._open_add_dialog
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=10),
            self.cards_view
        ], expand=True)
        
        # Initial load
        self.load_cards()

    # Removed build() method since Container doesn't support it in this way

    def load_cards(self):
        self.cards_view.controls.clear()
        
        # Fetch cards safely
        page = self.page or self.page_ctrl.page
        if not page: return

        user = page.session.get("utente_loggato")
        mk = page.session.get("master_key")
        
        if not user: return
        
        # Reload cards from DB
        carte = ottieni_carte_utente(user['id'], mk)
        
        if not carte:
            self.cards_view.controls.append(ft.Text("Nessuna carta trovata. Aggiungine una!"))
        else:
            grid = ft.GridView(
                expand=1,
                runs_count=5,
                max_extent=400, # Increased for better fit
                child_aspect_ratio=1.4,
                spacing=10,
                run_spacing=10,
            )
            
            for c in carte:
                grid.controls.append(self._build_card_tile(c))
            
            self.cards_view.controls.append(grid)
            
        # self.update() # Causes error if called during init (not attached to page yet)
        if self.page:
            try:
                self.update()
            except Exception as e:
                print(f"Error updating TabCarte: {e}")

    def _get_card_color(self, type_str, circuit_str):
        circuit = circuit_str.lower()
        is_credit = type_str == 'credito'
        
        if 'visa' in circuit:
            return ft.Colors.INDIGO_900 if is_credit else ft.Colors.BLUE_600
        elif 'master' in circuit:
             return ft.Colors.DEEP_ORANGE_900 if is_credit else ft.Colors.ORANGE_800
        elif 'amex' in circuit:
            return ft.Colors.TEAL_900
        elif 'paypal' in circuit:
            return ft.Colors.BLUE_ACCENT_700
        else:
            return ft.Colors.BLUE_GREY_800 if is_credit else ft.Colors.TEAL_700

    def _build_card_tile(self, card_data):
        # Create a nice visual card
        is_credit = card_data['tipo_carta'] == 'credito'
        bg_color = self._get_card_color(card_data['tipo_carta'], card_data['circuito'])
        icon = ft.Icons.CREDIT_CARD if is_credit else ft.Icons.CREDIT_CARD_OFF_OUTLINED
        
        content_col = [
            ft.ListTile(
                leading=ft.Icon(icon, color=ft.Colors.WHITE, size=30),
                title=ft.Text(card_data['nome_carta'], weight="bold", color=ft.Colors.WHITE),
                subtitle=ft.Text(f"{card_data['circuito'].upper()} - {card_data['tipo_carta'].capitalize()}", color=ft.Colors.WHITE70),
            )
        ]
        
        # Shared logic for spending calculation
        today = datetime.date.today()
        speso = calcola_totale_speso_carta(card_data['id_carta'], today.month, today.year)
        massimale = float(card_data.get('massimale', 0))

        if massimale > 0:
            # Show Progress Bar for both Credit and Debit if limit is set
            percent = min(speso / massimale, 1.0)
            
            # Subtitle/Extra Info differs by type
            if is_credit:
                extra_info = f"Addebito il giorno: {card_data.get('giorno_addebito', '-')}"
            else:
                extra_info = "Addebito immediato"

            content_col.append(ft.Container(padding=10, content=ft.Column([
                ft.Text(f"Speso questo mese: € {speso:.2f} / € {massimale:.2f}", color=ft.Colors.WHITE, size=12),
                ft.ProgressBar(value=percent, color=ft.Colors.ORANGE if percent > 0.8 else ft.Colors.GREEN, bgcolor=ft.Colors.WHITE24),
                ft.Text(extra_info, color=ft.Colors.WHITE70, size=12)
            ])))
        else:
            # No limit set
            if is_credit:
                 content_col.append(ft.Container(padding=10, content=ft.Text("Nessun massimale impostato", color=ft.Colors.WHITE70)))
            else:
                 # Debit without limit - just show spending
                 content_col.append(ft.Container(padding=10, content=ft.Column([
                    ft.Text(f"Speso questo mese: € {speso:.2f}", color=ft.Colors.WHITE, size=12),
                    ft.Text("Addebito immediato", color=ft.Colors.WHITE70, size=12)
                 ])))

        # Azioni Modifica/Elimina
        actions_row = ft.Row([
            ft.Container(), # Spacer
            ft.Row([
                ft.IconButton(icon=ft.Icons.LIST_ALT, icon_color=ft.Colors.WHITE, tooltip="Lista Movimenti", on_click=lambda e: self._open_transactions_dialog(card_data)),
                ft.IconButton(icon=ft.Icons.EDIT, icon_color=ft.Colors.WHITE, tooltip="Modifica", on_click=lambda e: self._open_edit_dialog(card_data)),
                ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.WHITE, tooltip="Elimina", on_click=lambda e: self._delete_card(card_data['id_carta']))
            ])
        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        
        content_col.append(ft.Container(padding=10, content=actions_row))

        return ft.Card(
            content=ft.Container(
                content=ft.Column(content_col),
                padding=10,
                bgcolor=bg_color,
                border_radius=10,
            )
        )

    def _open_add_dialog(self, e):
        try:
            page = self.page_ctrl.page
            if not page:
                print("Error: Page is None in _open_add_dialog")
                return
            dlg = CardDialog(page, self.load_cards, card=None)
            dlg.open()
        except Exception as ex:
            print(f"Error opening add card dialog: {ex}")
            import traceback
            traceback.print_exc()

    def _open_edit_dialog(self, card_data):
        try:
            page = self.page_ctrl.page
            if not page:
                print("Error: Page is None in _open_edit_dialog")
                return
            dlg = CardDialog(page, self.load_cards, card=card_data)
            dlg.open()
        except Exception as ex:
            print(f"Error opening edit card dialog: {ex}")
            traceback.print_exc()

    def _delete_card(self, id_carta):
        def confirm_delete(e):
            if elimina_carta(id_carta):
                self.load_cards()
            self.page_ctrl.close_dialog() # Assuming page_ctrl has this helper or using local dlg
        
        # Simple confirm dialog
        # Assuming page_ctrl.show_confirm_dialog exists? Or verify dashboard_view.
        # DashboardView usually handles dialogs.
        # Let's verify dashboard_view capability or create specific dialog.
        # I'll use page.dialog for now manually or reuse a generic one if I recalled it.
        # app_controller has show_confirm_dialog? Check headers.
        
        dlg = ft.AlertDialog(
            title=ft.Text("Conferma Eliminazione"),
            content=ft.Text("Vuoi davvero eliminare questa carta?"),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: self._close_dlg(dlg)),
                ft.TextButton("Elimina", on_click=lambda e: [self._close_dlg(dlg), confirm_delete(e)], style=ft.ButtonStyle(color=ft.Colors.RED))
            ]
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _close_dlg(self, dlg):
        dlg.open = False
        self.page.update()

    def _open_transactions_dialog(self, card_data):
        try:
            page = self.page or self.page_ctrl.page
            if not page: return
            
            mk = page.session.get("master_key")
            
            dlg = CardTransactionsDialog(
                page=page, 
                id_carta=card_data['id_carta'], 
                nome_carta=card_data['nome_carta'],
                master_key_b64=mk,
                controller=self.page_ctrl
            )
            # Use page.open() which is the modern Flet way and handles overlay automatically
            page.open(dlg)
        except Exception as ex:
            print(f"Error opening transactions dialog: {ex}")
            import traceback
            traceback.print_exc()
