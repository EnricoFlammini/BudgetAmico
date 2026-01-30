
import flet as ft
import datetime
import traceback
from db.gestione_db import ottieni_carte_utente, elimina_carta, calcola_totale_speso_carta
from dialogs.card_dialog import CardDialog
from dialogs.card_transactions_dialog import CardTransactionsDialog
from utils.styles import AppStyles
from utils.color_utils import get_color_from_string, get_type_color, MATERIAL_COLORS

class TabCarte(ft.Container):
    def __init__(self, page_ctrl):
        super().__init__(padding=20, expand=True)
        self.page_ctrl = page_ctrl
        self.page = page_ctrl.page
        self.cards_view = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        
        self.content = ft.Column([
            ft.Row([
                AppStyles.title_text("Gestione Carte"),
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Container(height=10),
            self.cards_view
        ], expand=True)
        
        # Initial load
        self.load_cards()

    def update_view_data(self, is_initial_load=False):
        """Metodo chiamato dal dashboard controller per aggiornare i dati della vista."""
        self.load_cards()

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
            self.cards_view.controls.append(AppStyles.body_text("Nessuna carta trovata. Aggiungine una!"))
        else:
            grid = ft.GridView(
                expand=1,
                runs_count=5,
                max_extent=400, # Increased for better fit
                child_aspect_ratio=1.4,
                spacing=10,
                run_spacing=10,
            )
            
            for idx, c in enumerate(carte):
                # Unique color assignment
                color = MATERIAL_COLORS[idx % len(MATERIAL_COLORS)]
                grid.controls.append(self._build_card_tile(c, assigned_color=color))
            
            self.cards_view.controls.append(grid)
            
        if self.page:
            try:
                # Only update if attached to page
                if self.page.controls and self in self.page.controls: # Crude check, better to relay on mounted
                     self.update()
                else:
                     # If the control is not in the page's tree, update() fails. 
                     # However, TabCarte is usually inside a Tabs or Dashboard view.
                     # If it's the initial load, we don't need to update self, just populating children is enough
                     # because the parent will update.
                     # But if it's a refresh (e.g. after add), we need to update.
                     
                     # Safe fallback: update the cards_view directly if possible?
                     # Or check properties
                     if self.uid:
                        self.update()
            except Exception as e:
                print(f"Error updating TabCarte: {e}")
                # traceback.print_exc() # detailed logging if needed

    def _build_card_tile(self, card_data, assigned_color: str = None):
        # Create a nice visual card
        is_credit = card_data['tipo_carta'] == 'credito'
        
        # Use new utility for unique background color
        if assigned_color:
            bg_color = assigned_color
        else:
            seed = f"{card_data.get('id_carta')}{card_data.get('nome_carta')}"
            bg_color = get_color_from_string(seed)
        
        # Type indicator color
        type_color = get_type_color(card_data['tipo_carta'])
        
        icon = ft.Icons.CREDIT_CARD if is_credit else ft.Icons.CREDIT_CARD_OFF_OUTLINED
        
        # Custom Header (Replacing ListTile to fix styling issues)
        header_row = ft.Row([
            ft.Icon(icon, color=ft.Colors.WHITE, size=30),
            ft.Column([
                AppStyles.subheader_text(card_data['nome_carta'], color=ft.Colors.WHITE),
                ft.Row([
                    AppStyles.small_text(f"{card_data['circuito'].upper()} - {card_data['tipo_carta'].capitalize()}", color=ft.Colors.WHITE70),
                     ft.Container(
                        content=ft.Text(card_data['tipo_carta'][:1].upper(), color=ft.Colors.BLACK, size=10, weight="bold"),
                        bgcolor=type_color,
                        width=20, height=20, border_radius=10,
                        alignment=ft.alignment.center,
                        tooltip=f"Tipo: {card_data['tipo_carta']}"
                    )
                ], spacing=5)
            ], expand=True, spacing=2)
        ], alignment=ft.MainAxisAlignment.START, vertical_alignment=ft.CrossAxisAlignment.CENTER)
        
        content_col = [
            ft.Container(content=header_row, padding=5),
            ft.Divider(color=ft.Colors.WHITE24, height=1)
        ]
        
        # Shared logic for spending calculation
        today = datetime.date.today()
        speso = calcola_totale_speso_carta(card_data['id_carta'], today.month, today.year)
        massimale = float(card_data.get('massimale', 0))

        spending_info = []

        if massimale > 0:
            # Show Progress Bar for both Credit and Debit if limit is set
            percent = min(speso / massimale, 1.0)
            
            # Subtitle/Extra Info differs by type
            if is_credit:
                extra_info = f"Addebito il giorno: {card_data.get('giorno_addebito', '-')}"
            else:
                extra_info = "Addebito immediato"

            spending_info.extend([
                AppStyles.small_text(f"Speso questo mese: € {speso:.2f} / € {massimale:.2f}", color=ft.Colors.WHITE),
                ft.ProgressBar(value=percent, color=ft.Colors.ORANGE if percent > 0.8 else ft.Colors.GREEN, bgcolor=ft.Colors.WHITE24),
                AppStyles.small_text(extra_info, color=ft.Colors.WHITE70)
            ])
        else:
            # No limit set
            if is_credit:
                 spending_info.append(AppStyles.small_text("Nessun massimale impostato", color=ft.Colors.WHITE70))
            else:
                  # Debit without limit - just show spending
                  spending_info.extend([
                     AppStyles.small_text(f"Speso questo mese: € {speso:.2f}", color=ft.Colors.WHITE),
                     AppStyles.small_text("Addebito immediato", color=ft.Colors.WHITE70)
                  ])
        
        content_col.append(ft.Container(padding=10, content=ft.Column(spending_info)))

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
                content=ft.Column(content_col, spacing=5),
                padding=10,
                bgcolor=bg_color,
                border_radius=10, # Card radius
            ),
            elevation=5
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
                self.page.snack_bar = ft.SnackBar(ft.Text("Carta eliminata correttamente"), bgcolor=ft.Colors.GREEN)
                self.page.snack_bar.open = True
            else:
                self.page.snack_bar = ft.SnackBar(ft.Text("Errore durante l'eliminazione"), bgcolor=ft.Colors.RED)
                self.page.snack_bar.open = True
            
            self.page.close(self.dlg_delete)
            self.page.update()
        
        self.dlg_delete = ft.AlertDialog(
            title=AppStyles.section_header_text("Conferma Eliminazione"),
            content=AppStyles.body_text("Vuoi davvero eliminare questa carta? Le transazioni rimarranno visibili nello storico."),
            actions=[
                ft.TextButton("Annulla", on_click=lambda e: self.page.close(self.dlg_delete)),
                ft.TextButton("Elimina", on_click=confirm_delete, style=ft.ButtonStyle(color=ft.Colors.RED))
            ]
        )
        self.page.open(self.dlg_delete)

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
            page.open(dlg)
        except Exception as ex:
            print(f"Error opening transactions dialog: {ex}")
            traceback.print_exc()
