import flet as ft
from functools import partial
import urllib.parse
from db.gestione_db import ottieni_contatti_utente, elimina_contatto
from dialogs.contact_dialog import ContactDialog
from utils.async_task import AsyncTask
from utils.styles import AppStyles, AppColors, PageConstants
from utils.color_utils import get_color_from_string

class ContattiTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        
        self.grid_contatti = ft.GridView(
            expand=1,
            runs_count=5, # Will adjust based on max_extent
            max_extent=350,
            child_aspect_ratio=0.8, # Taller for content
            spacing=10,
            run_spacing=10,
        )

        self.fab_add = ft.FloatingActionButton(
            icon=ft.Icons.ADD, 
            on_click=self._apri_dialog_aggiungi,
            bgcolor=AppColors.PRIMARY
        )

        self.main_view = ft.Column([
            ft.Row([
                AppStyles.title_text("Rubrica Contatti"),
                # self.fab_add # RIMOSSO pulsante ridondante
            ], alignment=ft.MainAxisAlignment.START),
            AppStyles.page_divider(),
            self.grid_contatti
        ], expand=True)
        
        self.loading_view = ft.Container(
            content=ft.ProgressRing(),
            alignment=ft.alignment.center,
            visible=False
        )
        
        self.content = ft.Stack([
            self.main_view,
            self.loading_view
        ], expand=True)

    def update_view_data(self, is_initial_load=False):
        self.loading_view.visible = True
        self.main_view.visible = False
        if self.page: self.page.update()
        
        uid = self.controller.get_user_id()
        mk = self.controller.page.session.get("master_key")
        
        if not uid: return

        task = AsyncTask(
            target=ottieni_contatti_utente,
            args=(uid, mk),
            callback=self._on_data_loaded,
            error_callback=self._on_error
        )
        task.start()

    def _on_data_loaded(self, contatti):
        self.grid_contatti.controls.clear()
        
        if not contatti:
             self.grid_contatti.controls.append(
                 ft.Column([
                     ft.Icon(ft.Icons.CONTACT_PAGE, size=64, color=AppColors.TEXT_SECONDARY),
                     ft.Text("Nessun contatto presente.", color=AppColors.TEXT_SECONDARY)
                 ], alignment=ft.MainAxisAlignment.CENTER)
             )
        else:
            for c in contatti:
                self.grid_contatti.controls.append(self._crea_card_contatto(c))

        self.loading_view.visible = False
        self.main_view.visible = True
        if self.page: self.page.update()

    def _on_error(self, e):
        print(f"Errore ContattiTab: {e}")
        self.loading_view.visible = False
        self.main_view.visible = True
        if self.page: self.page.update()

    def _apri_dialog_aggiungi(self, e):
        # Pass callback to refresh on dismiss
        dlg = ContactDialog(self.page, self.controller, on_dismiss=lambda: self.update_view_data())
        self.page.open(dlg)

    def _crea_card_contatto(self, c):
        nome_completo = f"{c['nome']} {c.get('cognome','')}".strip()
        societa = c.get('societa', '')
        iban = c.get('iban', '')
        email = c.get('email', '')
        telefono = c.get('telefono', '')
        
        
        # Use stored color if available, otherwise fallback (though default should be set)
        bg_color = c.get('colore')
        if not bg_color:
             bg_color = get_color_from_string(str(c['id_contatto']) + nome_completo)
        
        def copy_to_clipboard(val, label):
            if val:
                self.page.set_clipboard(val)
                self.controller.show_snack_bar(f"{label} copiato!", success=True)
        
        def share_info(mode):
            text_lines = [f"Contatto: {nome_completo}"]
            if societa: text_lines.append(f"Società: {societa}")
            if iban: text_lines.append(f"IBAN: {iban}")
            if email: text_lines.append(f"Email: {email}")
            if telefono: text_lines.append(f"Tel: {telefono}")
            
            full_text = "\n".join(text_lines)
            
            if mode == "email":
                subject = urllib.parse.quote(f"Contatto: {nome_completo}")
                body = urllib.parse.quote(full_text)
                self.page.launch_url(f"mailto:?subject={subject}&body={body}")
            elif mode == "whatsapp":
                text_enc = urllib.parse.quote(full_text)
                self.page.launch_url(f"https://wa.me/?text={text_enc}")

        # Info Rows
        rows = []
        
        if societa:
            rows.append(ft.Row([ft.Icon(ft.Icons.BUSINESS, size=16, color=ft.Colors.WHITE70), ft.Text(societa, size=12, color=ft.Colors.WHITE, weight="bold")], spacing=5))
        
        if iban:
             rows.append(
                 ft.Row([
                     ft.Icon(ft.Icons.CREDIT_CARD, size=16, color=ft.Colors.WHITE70), 
                     ft.Text(iban, size=12, expand=True, overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.WHITE),
                     ft.IconButton(ft.Icons.COPY, icon_size=14, icon_color=ft.Colors.WHITE70, on_click=lambda e: copy_to_clipboard(iban, "IBAN"))
                 ], spacing=5)
             )
        
        if email:
             rows.append(
                 ft.Row([
                     ft.Icon(ft.Icons.EMAIL, size=16, color=ft.Colors.WHITE70), 
                     ft.Text(email, size=12, expand=True, overflow=ft.TextOverflow.ELLIPSIS, color=ft.Colors.WHITE),
                     ft.IconButton(ft.Icons.COPY, icon_size=14, icon_color=ft.Colors.WHITE70, on_click=lambda e: copy_to_clipboard(email, "Email"))
                 ], spacing=5)
             )
        
        if telefono:
             rows.append(
                 ft.Row([
                     ft.Icon(ft.Icons.PHONE, size=16, color=ft.Colors.WHITE70), 
                     ft.Text(telefono, size=12, expand=True, color=ft.Colors.WHITE),
                     ft.IconButton(ft.Icons.COPY, icon_size=14, icon_color=ft.Colors.WHITE70, on_click=lambda e: copy_to_clipboard(telefono, "Telefono"))
                 ], spacing=5)
             )

        # Action Buttons specific to Card
        actions_row = ft.Row([
            ft.IconButton(ft.Icons.SHARE, tooltip="Condividi via Email", icon_color=ft.Colors.WHITE, on_click=lambda e: share_info("email")),
            ft.IconButton(ft.Icons.MESSAGE, tooltip="Condividi via Whatsapp", icon_color=ft.Colors.WHITE, on_click=lambda e: share_info("whatsapp")),
            ft.Container(expand=True),
            ft.IconButton(ft.Icons.EDIT, tooltip="Modifica", icon_color=ft.Colors.WHITE, 
                          on_click=lambda e: self.page.open(ContactDialog(self.page, self.controller, contato_to_edit=c, on_dismiss=lambda: self.update_view_data()))),
            ft.IconButton(ft.Icons.DELETE, tooltip="Elimina", icon_color=ft.Colors.WHITE, 
                          on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(self._elimina_contatto_cliccato, c['id_contatto']))),
        ])

        return ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.PERSON, size=30, color=ft.Colors.WHITE),
                        ft.Text(nome_completo, size=16, weight="bold", color=ft.Colors.WHITE, expand=True),
                        # Badge for sharing type
                        ft.Container(
                             content=ft.Icon(
                                 ft.Icons.LOCK if c['tipo_condivisione'] == 'privato' else (ft.Icons.FAMILY_RESTROOM if c['tipo_condivisione'] == 'famiglia' else ft.Icons.GROUP),
                                 size=14, color=ft.Colors.BLACK
                             ),
                             padding=3, bgcolor=ft.Colors.WHITE54, border_radius=4, 
                             tooltip=f"Condivisione: {c['tipo_condivisione']}"
                        )
                    ]),
                    ft.Divider(color=ft.Colors.WHITE24),
                    ft.Column(rows, spacing=5, expand=True),
                    ft.Container(height=10),
                    actions_row
                ]),
                padding=15,
                bgcolor=bg_color,
                border_radius=10,
                height=250 # Fixed height to align grid
            ),
            elevation=5
        )

    def _elimina_contatto_cliccato(self, id_contatto, e):
        uid = self.controller.get_user_id()
        if elimina_contatto(id_contatto, uid):
            self.controller.show_snack_bar("Contatto eliminato.", success=True)
            self.update_view_data()
        else:
            self.controller.show_error_dialog("Impossibile eliminare il contatto (potrebbe non essere tuo).")
