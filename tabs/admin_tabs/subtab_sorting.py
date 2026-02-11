
import flet as ft
from db.gestione_db import (
    ottieni_tutti_i_conti_famiglia,
    ottieni_carte_utente,
    ottieni_ordinamento_conti_carte,
    salva_ordinamento_conti_carte,
    ottieni_membri_famiglia
)
from utils.styles import AppStyles, AppColors

class AdminSubTabSorting(ft.Container):
    def __init__(self, controller):
        super().__init__(expand=True)
        self.controller = controller
        self.items_list = [] # List of dict {id, name, type, icon, color, category}
        
        self.lv_sorting = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True, spacing=5)
        
        self.content = ft.Column([
            AppStyles.subheader_text("Trascina gli elementi per cambiare l'ordine di visualizzazione nei menu"),
            ft.Row([
                ft.ElevatedButton("Salva Ordinamento", icon=ft.Icons.SAVE, on_click=self._salva_cliccato, bgcolor=AppColors.PRIMARY, color=ft.Colors.WHITE),
                ft.TextButton("Reset", icon=ft.Icons.REFRESH, on_click=self._reset_cliccato)
            ]),
            AppStyles.page_divider(),
            self.lv_sorting
        ], expand=True)

    def update_view(self):
        self.items_list = []
        self.lv_sorting.controls.clear()
        
        id_famiglia = self.controller.get_family_id()
        id_utente = self.controller.get_user_id()
        master_key_b64 = self.controller.page.session.get("master_key")
        
        if not id_famiglia: return

        # 1. Recupera Conti
        conti = ottieni_tutti_i_conti_famiglia(id_famiglia, id_utente, master_key_b64=master_key_b64)
        
        # 2. Recupera Carte per ogni membro
        membri = ottieni_membri_famiglia(id_famiglia, master_key_b64, id_utente)
        tutte_le_carte = []
        for m in membri:
             carte = ottieni_carte_utente(m['id_utente'], master_key_b64)
             tutte_le_carte.extend(carte)

        # Build items
        for c in conti:
            prefix = "C" if c['is_condiviso'] else "P"
            key = f"{prefix}{c['id_conto']}"
            owner_suffix = f" ({c.get('nome_owner', 'Shared')})" if not c['is_condiviso'] else " (Condiviso)"
            self.items_list.append({
                'key': key,
                'name': f"{c['nome_conto']}{owner_suffix}",
                'tipo': c['tipo'],
                'icona': c.get('icona'),
                'colore': c.get('colore'),
                'is_conto': True
            })
            
        for c in tutte_le_carte:
            key = str(c['id_carta'])
            owner_name = next((m['nome_visualizzato'] for m in membri if m['id_utente'] == c.get('id_utente')), "Ignoto")
            self.items_list.append({
                'key': key,
                'name': f"{c['nome_carta']} ({owner_name})",
                'tipo': c['tipo_carta'],
                'icona': c.get('icona'),
                'colore': c.get('colore'),
                'is_conto': False
            })

        # 3. Applica ordinamento esistente
        saved_order = ottieni_ordinamento_conti_carte(id_famiglia)
        if saved_order:
             order_keys = saved_order.get('order', [])
             # Sort self.items_list based on order_keys
             def get_index(k):
                 try: return order_keys.index(k)
                 except: return 999
             self.items_list.sort(key=lambda x: get_index(x['key']))

        # Create draggable-like list (using simple move buttons for robustness if reorderable is tricky)
        # However, Flet ReorderableListView is better.
        self._refresh_list_ui()
        self.update()

    def _refresh_list_ui(self):
        self.lv_sorting.controls.clear()
        for idx, item in enumerate(self.items_list):
            row = ft.Container(
                content=ft.Row([
                    ft.Row([
                        AppStyles.get_logo_control(
                            tipo=item['tipo'],
                            size=20,
                            icona=item['icona'],
                            colore=item['colore']
                        ),
                        ft.Text(item['name'], weight="bold" if item['is_conto'] else "normal"),
                        ft.Text(f"[{item['tipo']}]", size=10, color=ft.Colors.GREY_500)
                    ], expand=True),
                    ft.Row([
                        ft.IconButton(ft.Icons.ARROW_UPWARD, on_click=lambda e, i=idx: self._move_item(i, -1), visible=(idx > 0)),
                        ft.IconButton(ft.Icons.ARROW_DOWNWARD, on_click=lambda e, i=idx: self._move_item(i, 1), visible=(idx < len(self.items_list)-1)),
                    ], spacing=0)
                ]),
                padding=10,
                border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                border_radius=8,
                bgcolor=ft.Colors.SURFACE_VARIANT if item['is_conto'] else ft.Colors.SURFACE
            )
            self.lv_sorting.controls.append(row)

    def _move_item(self, index, direction):
        new_index = index + direction
        if 0 <= new_index < len(self.items_list):
            self.items_list[index], self.items_list[new_index] = self.items_list[new_index], self.items_list[index]
            self._refresh_list_ui()
            self.update()

    def _salva_cliccato(self, e):
        id_famiglia = self.controller.get_family_id()
        if not id_famiglia: return
        
        order_keys = [item['key'] for item in self.items_list]
        if salva_ordinamento_conti_carte(id_famiglia, {'order': order_keys}):
            self.controller.show_snack_bar("Ordinamento salvato con successo!", success=True)
        else:
            self.controller.show_snack_bar("Errore nel salvataggio dell'ordinamento.", success=False)

    def _reset_cliccato(self, e):
        self.update_view()
