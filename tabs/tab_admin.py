import flet as ft
import json
from functools import partial
from utils.styles import AppColors, AppStyles, PageConstants
from db.gestione_db import (
    ottieni_categorie_e_sottocategorie, 
    ottieni_membri_famiglia, 
    rimuovi_utente_da_famiglia, 
    ottieni_budget_famiglia, 
    get_smtp_config, 
    esporta_dati_famiglia,
    get_impostazioni_budget_famiglia,
    get_server_family_key,
    enable_server_automation,
    disable_server_automation
)
from utils.email_sender import send_email
from tabs.admin_tabs.subtab_budget_manager import AdminSubTabBudgetManager
from utils.async_task import AsyncTask

class AdminTab(ft.Container):
    def __init__(self, controller):
        super().__init__(padding=PageConstants.PAGE_PADDING, expand=True)
        self.controller = controller
        self.controller.page = controller.page
        
        self.tabs_admin = ft.Tabs(
            tabs=[],
            expand=1,
            divider_color=ft.Colors.TRANSPARENT,
            indicator_color=AppColors.PRIMARY,
            label_color=AppColors.PRIMARY,
            unselected_label_color=AppColors.TEXT_SECONDARY
        )

        self.lv_categorie = ft.Column(scroll=ft.ScrollMode.AUTO, expand=True)
        self.lv_membri = ft.Column(scroll=ft.ScrollMode.AUTO)
        
        # Subtabs
        self.subtab_budget_manager = AdminSubTabBudgetManager(controller)
        
        # Stato Automazione
        self.server_automation_enabled = False
        self.switch_automation = ft.Switch(
            value=False,
            on_change=self._toggle_automation_click
        )
        self.container_force_check = ft.Container(
             visible=False,
             content=ft.OutlinedButton(
                "Esegui Check Ora (Forza Aggiornamento)",
                icon=ft.Icons.REFRESH,
                on_click=self._force_background_check_click,
                style=ft.ButtonStyle(color=AppColors.PRIMARY)
             ),
             padding=ft.padding.only(left=5)
        )

        self.content = ft.Column(
            [self.tabs_admin],
            expand=True
        )

    def build_tabs(self):
        loc = self.controller.loc
        tabs = []
        
        # 1. Categorie
        t_cat = ft.Tab(
            text=loc.get("categories_management"),
            icon=ft.Icons.CATEGORY,
            content=ft.Column(expand=True, controls=[
                ft.Row([
                    ft.Container(),  # Spacer
                    ft.IconButton(
                        icon=ft.Icons.ADD,
                        tooltip=loc.get("add_category"),
                        icon_color=AppColors.PRIMARY,
                        on_click=lambda e: self.controller.admin_dialogs.apri_dialog_categoria()
                    )
                ], alignment=ft.MainAxisAlignment.END),
                AppStyles.page_divider(),
                self.lv_categorie
            ])
        )
        tabs.append(t_cat)

        # 2. Gestione Budget
        t_bud = ft.Tab(
            text="Gestione Budget",
            icon=ft.Icons.ACCOUNT_BALANCE_WALLET,
            content=self.subtab_budget_manager
        )
        tabs.append(t_bud)

        # 3. Membri Famiglia
        t_mem = ft.Tab(
            text=loc.get("members_management"),
            icon=ft.Icons.PEOPLE,
            content=ft.Column([
                ft.Row([
                    ft.Container(),  # Spacer
                    ft.IconButton(
                        icon=ft.Icons.PERSON_ADD,
                        tooltip=loc.get("invite_member"),
                        icon_color=AppColors.PRIMARY,
                        on_click=lambda e: self.controller.admin_dialogs.apri_dialog_invito()
                    )
                ], alignment=ft.MainAxisAlignment.END),
                AppStyles.page_divider(),
                self.lv_membri
            ])
        )
        tabs.append(t_mem)
        
        # 4. Backup / Export (Sostituisce Email Tab)
        t_back = ft.Tab(
            text="Backup / Export",
            icon=ft.Icons.BACKUP,
            content=ft.Column([
                AppStyles.page_divider(),
                ft.Container(
                    content=ft.ElevatedButton(
                        "Invia Family key e configurazione via mail",
                        icon=ft.Icons.EMAIL,
                        on_click=self._invia_backup_email_cliccato,
                        bgcolor=AppColors.PRIMARY,
                        color=AppColors.ON_PRIMARY
                    ),
                    padding=20
                ),
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.WARNING_AMBER, color=AppColors.WARNING, size=32),
                        AppStyles.body_text(
                            "ATTENZIONE: Il file inviato contiene la chiave di crittografia della famiglia. "
                            "Assicurati che l'email di destinazione sia corretta e sicura.",
                            color=AppColors.WARNING
                        ),
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER),
                    padding=20,
                    border=ft.border.all(1, AppColors.WARNING),
                    border_radius=10
                ),
                ft.Divider(height=30),
                AppStyles.subheader_text("Impostazioni Sistema"),
                ft.Container(
                    content=ft.Row([
                        ft.Column([
                            ft.Row([
                                ft.Text("Automazione Cloud (Koyeb)", weight=ft.FontWeight.W_500),
                                ft.Icon(ft.Icons.CLOUD_QUEUE, color=AppColors.PRIMARY, size=16),
                            ], spacing=5),
                            ft.Text("Esegui spese fisse e aggiorna asset in background.", 
                                   size=12, color=AppColors.TEXT_SECONDARY)
                        ], expand=True),
                        self.switch_automation
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    padding=15,
                    border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                    border_radius=10
                ),
                ft.Container(height=5),
                self.container_force_check
            ], scroll=ft.ScrollMode.AUTO)
        )
        tabs.append(t_back)
        
        return tabs

    def update_all_admin_tabs_data(self, is_initial_load=False):
        """Avvia il caricamento asincrono di tutti i dati per le tab Admin."""
        self.tabs_admin.tabs = self.build_tabs()
        
        # Mostra loading nelle liste
        self.lv_categorie.controls = [ft.ProgressRing()]
        self.lv_membri.controls = [ft.ProgressRing()]
        if self.page:
            self.page.update()

        famiglia_id = self.controller.get_family_id()
        if not famiglia_id: return

        master_key_b64 = self.controller.page.session.get("master_key")
        id_utente = self.controller.get_user_id()

        task = AsyncTask(
            target=self._fetch_all_data,
            args=(famiglia_id, master_key_b64, id_utente),
            callback=self._on_data_loaded,
            error_callback=self._on_error
        )
        task.start()

    def _fetch_all_data(self, famiglia_id, master_key_b64, id_utente):
        """Recupera tutti i dati necessari per le sotto-schede."""
        return {
            'categorie': ottieni_categorie_e_sottocategorie(famiglia_id),
            'membri': ottieni_membri_famiglia(famiglia_id, master_key_b64, id_utente),
            'smtp_config': get_smtp_config(famiglia_id, master_key_b64, id_utente),
            'impostazioni_budget': get_impostazioni_budget_famiglia(famiglia_id),
            'budget_impostati': ottieni_budget_famiglia(famiglia_id, master_key_b64, id_utente),
            'server_key': get_server_family_key(famiglia_id)
        }

    def _on_data_loaded(self, result):
        try:
            # 1. Popola Categorie
            self._populate_tab_categorie(result['categorie'])
            
            # 2. Popola Membri
            self._populate_tab_membri(result['membri'])
            
            # 3. Popola Budget Manager
            self.subtab_budget_manager.update_view_data(prefetched_data=result)
            
            # Salva email utente corrente per invio backup
            current_user_id = self.controller.get_user_id()
            for membro in result.get('membri', []):
                if membro['id_utente'] == current_user_id:
                    self.current_user_email = membro.get('email')
                    break
            
            # 4. Stato Automazione
            self.server_automation_enabled = result.get('server_key') is not None
            self.switch_automation.value = self.server_automation_enabled
            self.container_force_check.visible = self.server_automation_enabled
            
            if self.page:
                self.page.update()
        except Exception as e:
            self._on_error(e)

    def _on_error(self, e):
        print(f"Errore AdminTab: {e}")
        try:
            err_msg = AppStyles.body_text(f"Errore caricamento: {e}", color=AppColors.ERROR)
            self.lv_categorie.controls = [err_msg]
            self.lv_membri.controls = [err_msg]
            if self.page:
                self.page.update()
        except:
            pass

    def _populate_tab_categorie(self, categorie_data):
        loc = self.controller.loc
        theme = self.controller._get_current_theme_scheme() or ft.ColorScheme()
        self.lv_categorie.controls.clear()

        if not categorie_data:
            self.lv_categorie.controls.append(AppStyles.body_text(loc.get("no_categories_found")))
        else:
            for cat_info in categorie_data:
                cat_id = cat_info['id_categoria']
                sottocategorie_list = ft.Column()
                for sub in cat_info['sottocategorie']:
                    sottocategorie_list.controls.append(
                        ft.Row([
                            ft.Icon(ft.Icons.SUBDIRECTORY_ARROW_RIGHT, size=16, color=AppColors.TEXT_SECONDARY),
                            ft.Text(sub['nome_sottocategoria'], expand=True),
                            ft.IconButton(icon=ft.Icons.EDIT, icon_size=16, tooltip=loc.get("edit"), data=sub, icon_color=AppColors.PRIMARY, on_click=lambda e: self.controller.admin_dialogs.apri_dialog_sottocategoria(sub_cat_data=e.control.data)),
                            ft.IconButton(icon=ft.Icons.DELETE, icon_size=16, tooltip=loc.get("delete"), icon_color=AppColors.ERROR, data=sub['id_sottocategoria'], on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(self.controller.admin_dialogs.elimina_sottocategoria_cliccato, e))),
                        ])
                    )
                
                self.lv_categorie.controls.append(
                    ft.ExpansionPanelList(
                        expand_icon_color=theme.primary,
                        elevation=0,
                        divider_color=ft.Colors.TRANSPARENT,
                        controls=[
                            ft.ExpansionPanel(
                                header=ft.Row([
                                    AppStyles.subheader_text(cat_info['nome_categoria']),
                                    ft.Row([
                                        ft.IconButton(icon=ft.Icons.ADD, tooltip=loc.get("add_subcategory"), data=cat_id, icon_color=AppColors.PRIMARY, on_click=lambda e: self.controller.admin_dialogs.apri_dialog_sottocategoria(id_categoria=e.control.data)),
                                        ft.IconButton(icon=ft.Icons.EDIT, tooltip=loc.get("edit"), data={'id_categoria': cat_id, 'nome_categoria': cat_info['nome_categoria']}, icon_color=AppColors.PRIMARY, on_click=lambda e: self.controller.admin_dialogs.apri_dialog_categoria(e.control.data)),
                                        ft.IconButton(icon=ft.Icons.DELETE, tooltip=loc.get("delete"), icon_color=AppColors.ERROR, data=cat_id, on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(self.controller.admin_dialogs.elimina_categoria_cliccato, e))),
                                    ])
                                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                                content=ft.Container(
                                    content=sottocategorie_list,
                                    padding=ft.padding.only(left=15, bottom=10)
                                ),
                                bgcolor=AppColors.SURFACE_VARIANT
                            )
                        ]
                    )
                )
            self.lv_categorie.controls.append(ft.Container(height=80))

    def _populate_tab_membri(self, membri):
        loc = self.controller.loc
        current_user_id = self.controller.get_user_id()
        self.lv_membri.controls.clear()

        if len(membri) <= 1:
            self.lv_membri.controls.append(AppStyles.body_text(loc.get("no_members_found")))
        else:
            for membro in membri:
                if membro['id_utente'] == current_user_id:
                    continue

                action_buttons = ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.SEND,
                        tooltip="Rimanda Credenziali",
                        data=membro,
                        icon_color=AppColors.PRIMARY,
                        on_click=lambda e: self._rimanda_credenziali_cliccato(e)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.EDIT,
                        tooltip=loc.get("edit") + " " + loc.get("role"),
                        data=membro,
                        icon_color=AppColors.PRIMARY,
                        on_click=lambda e: self.controller.admin_dialogs.apri_dialog_modifica_ruolo(e.control.data)
                    ),
                    ft.IconButton(
                        icon=ft.Icons.DELETE,
                        tooltip=loc.get("remove_from_family"),
                        icon_color=AppColors.ERROR,
                        data=membro,
                        on_click=lambda e: self.controller.open_confirm_delete_dialog(partial(self.rimuovi_membro_cliccato, e))
                    )
                ], spacing=0, wrap=True, alignment=ft.MainAxisAlignment.END)

                content = ft.ResponsiveRow([
                    ft.Column([
                        ft.Row([
                            ft.Icon(ft.Icons.PERSON, color=AppColors.PRIMARY),
                            ft.Column([
                                AppStyles.subheader_text(membro['nome_visualizzato']),
                                ft.Text(membro['ruolo'], color=AppColors.TEXT_SECONDARY)
                            ], spacing=2)
                        ])
                    ], col={"xs": 12, "sm": 8}),
                    ft.Column([action_buttons], col={"xs": 12, "sm": 4}, horizontal_alignment=ft.CrossAxisAlignment.END)
                ], vertical_alignment=ft.CrossAxisAlignment.CENTER)
                
                self.lv_membri.controls.append(AppStyles.card_container(content, padding=15))

        self.page.open(dlg)

    def _invia_backup_email_cliccato(self, e):
        print(f"[DEBUG] [ADMIN] Clicked 'Invia Family key e configurazione via mail'")
        btn = e.control
        orig_text = btn.text
        
        famiglia_id = self.controller.get_family_id()
        master_key = self.controller.page.session.get("master_key")
        user_id = self.controller.get_user_id()
        recipient_email = getattr(self, 'current_user_email', None)

        def _procedi_invio(email_scelta):
            btn.text = "Preparazione dati..."
            btn.disabled = True
            if self.page: self.page.update()

            def _run_workflow():
                try:
                    data_export, error_msg = esporta_dati_famiglia(famiglia_id, user_id, master_key)
                    if error_msg: return False, f"Errore generazione dati: {error_msg}"
                    if not data_export: return False, "Nessun dato da esportare."

                    import json
                    json_str = json.dumps(data_export, indent=2, default=str)
                    json_bytes = json_str.encode('utf-8')

                    import datetime
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"budget_amico_key_{timestamp}.json"
                    
                    subject = f"Family Key Budget Amico - {datetime.datetime.now().strftime('%d/%m/%Y %H:%M')}"
                    body = "<h3>La tua Family Key è pronta!</h3><p>In allegato trovi il file JSON con la chiave e le configurazioni della tua famiglia.</p>"
                    
                    success, email_error = send_email(to_email=email_scelta, subject=subject, body=body, attachment_bytes=json_bytes, attachment_name=filename)
                    
                    if not success: return False, f"Errore invio email: {email_error}"
                    return True, None
                except Exception as ex: return False, str(ex)

            def _on_complete(result):
                success, error = result
                btn.text = orig_text
                btn.disabled = False
                if success:
                    self.controller.show_snack_bar(f"Dati inviati a {email_scelta}!", AppColors.SUCCESS)
                else:
                    self.controller.show_error_dialog(f"Errore: {error}")
                if self.page: self.page.update()

            AsyncTask(target=_run_workflow, callback=_on_complete).start()

        # Mostra dialog di conferma prima di procedere
        self._mostra_confirm_email_dialog(
            title="Invia Family Key via Email",
            default_email=recipient_email or "",
            on_confirm=_procedi_invio
        )

    def rimuovi_membro_cliccato(self, e):
        if hasattr(e, 'control') and e.control and e.control.data:
            id_membro = e.control.data.get('id_utente')
            famiglia_id = self.controller.get_family_id()
            if rimuovi_utente_da_famiglia(id_membro, famiglia_id):
                self.update_all_admin_tabs_data()
                self.controller.show_snack_bar("Membro rimosso.", AppColors.SUCCESS)
            if self.page: self.page.update()

    def _rimanda_credenziali_cliccato(self, e):
        membro = e.control.data
        email_originale = membro.get('email')
        id_utente_membro = membro.get('id_utente')
        nome = membro.get('nome_visualizzato', 'Utente')

        if not email_originale or '@disabled.local' in str(email_originale):
            self.controller.show_snack_bar("Email non valida.", AppColors.ERROR)
            return

        def _procedi_invio_credenziali(email_scelta):
            e.control.disabled = True
            if self.page: self.page.update()

            def _invia():
                try:
                    from db.gestione_db import imposta_password_temporanea
                    import secrets
                    smtp_config = get_smtp_config() # Global
                    if not smtp_config.get('server'): return False, "SMTP non configurato globalmente."
                    temp_password = secrets.token_urlsafe(8)
                    if not imposta_password_temporanea(id_utente_membro, temp_password): return False, "Errore DB."
                    body = f"<h2>Ciao {nome}!</h2><p>Le tue nuove credenziali:</p><p><b>{temp_password}</b></p>"
                    return send_email(email_scelta, "Credenziali Budget Amico", body)
                except Exception as ex: return False, str(ex)

            def _complete(res):
                success, err = res
                e.control.disabled = False
                if success: self.controller.show_snack_bar(f"Email inviata a {email_scelta}!", AppColors.SUCCESS)
                else: self.controller.show_snack_bar(f"Errore: {err}", AppColors.ERROR)
                if self.page: self.page.update()

            AsyncTask(target=_invia, callback=_complete).start()

        # Mostra dialog di conferma
        self._mostra_confirm_email_dialog(
            title=f"Invia Credenziali a {nome}",
            default_email=email_originale,
            on_confirm=_procedi_invio_credenziali
        )

    def _toggle_automation_click(self, e):
        switch = e.control
        if switch.value:
            switch.value = False
            switch.update()
            def confirm(e):
                self.controller.page.close(dlg)
                self._execute_toggle_automation(True, switch)
            dlg = ft.AlertDialog(
                title=ft.Text("Attivare Automazione Cloud?"),
                content=ft.Text("Salva la chiave sul server per spese fisse automatiche."),
                actions=[ft.TextButton("Annulla", on_click=lambda e: self.controller.page.close(dlg)), ft.TextButton("Attiva", on_click=confirm)]
            )
            self.controller.page.open(dlg)
        else:
            self._execute_toggle_automation(False, switch)

    def _force_background_check_click(self, e):
        btn = e.control
        btn.disabled = True
        btn.update()
        def _run():
            try:
                from services.background_service import BackgroundService
                BackgroundService().run_all_jobs_now()
                return True, "Ok"
            except Exception as ex: return False, str(ex)
        def _done(res):
            btn.disabled = False
            self.controller.show_snack_bar(res[1], success=res[0])
            if self.page: self.page.update()
        AsyncTask(target=_run, callback=_done).start()

    def _execute_toggle_automation(self, enable, switch):
        fid = self.controller.get_family_id()
        uid = self.controller.get_user_id()
        mk = self.controller.page.session.get("master_key")
        if enable: success = enable_server_automation(fid, mk, uid)
        else: success = disable_server_automation(fid)
        if success:
            switch.value = enable
            self.server_automation_enabled = enable
            self.controller.show_snack_bar("Stato aggiornato!", success=True)
        switch.update()
