import flet as ft
from db.gestione_db import crea_contatto, modifica_contatto, ottieni_membri_famiglia, ottieni_prima_famiglia_utente
from utils.styles import AppStyles, AppColors
from functools import partial

class ContactDialog(ft.AlertDialog):
    def __init__(self, page, controller, contato_to_edit=None, on_dismiss=None):
        self.controller = controller
        self.page_ref = page
        self.contatto = contato_to_edit
        self.on_dismiss_callback = on_dismiss
        
        self.tf_nome = ft.TextField(label="Nome", width=300, autofocus=True)
        self.tf_cognome = ft.TextField(label="Cognome", width=300)
        self.tf_societa = ft.TextField(label="Società", width=300)
        self.tf_iban = ft.TextField(label="IBAN", width=300)
        self.tf_email = ft.TextField(label="Email", width=300)
        self.tf_email = ft.TextField(label="Email", width=300)
        self.tf_telefono = ft.TextField(label="Telefono", width=300)
        
        # Color Picker
        self.colors = [
            '#424242', # Grey 800 (Default)
            '#c62828', # Red 800
            '#ad1457', # Pink 800
            '#6a1b9a', # Purple 800
            '#4527a0', # Deep Purple 800
            '#283593', # Indigo 800
            '#1565c0', # Blue 800
            '#00695c', # Teal 800
            '#2e7d32', # Green 800
            '#ff8f00', # Amber 800
            '#ef6c00', # Orange 800
            '#4e342e', # Brown 800
            '#37474f', # Blue Grey 800
        ]
        self.selected_color = '#424242'
        self.color_circles = ft.Row(wrap=True, spacing=5, run_spacing=5, width=300)
        
        self.dd_condivisione = ft.Dropdown(
            label="Condivisione",
            width=300,
            options=[
                ft.dropdown.Option("privato", "Solo Io (Privato)"),
                ft.dropdown.Option("famiglia", "Tutta la Famiglia"),
                ft.dropdown.Option("selezione", "Selezione Utenti"),
            ],
            value="privato",
            on_change=self._on_condivisione_change
        )
        
        self.col_selezione_utenti = ft.Column(visible=False)
        self.selected_users_switches = {} # user_id -> checkbox/switch
        
        # Populate if editing
        if self.contatto:
            self.tf_nome.value = self.contatto.get('nome', '')
            self.tf_cognome.value = self.contatto.get('cognome', '')
            self.tf_societa.value = self.contatto.get('societa', '')
            self.tf_iban.value = self.contatto.get('iban', '')
            self.tf_email.value = self.contatto.get('email', '')
            self.tf_telefono.value = self.contatto.get('telefono', '')
            self.dd_condivisione.value = self.contatto.get('tipo_condivisione', 'privato')
            self.selected_color = self.contatto.get('colore', '#424242')
        
        # Build Color Circles
        self._build_color_picker()
        
        super().__init__(
            modal=True,
            title=ft.Text("Nuovo Contatto" if not self.contatto else "Modifica Contatto"),
            content=ft.Column([
                self.tf_nome, 
                self.tf_cognome,
                self.tf_societa,
                self.tf_iban,
                self.tf_email,
                self.tf_telefono,
                ft.Text("Colore Scheda", size=12, color=AppColors.TEXT_SECONDARY),
                self.color_circles,
                ft.Divider(),
                self.dd_condivisione,
                self.col_selezione_utenti
            ], tight=True, scroll=ft.ScrollMode.AUTO, height=500),
            actions=[
                ft.TextButton("Annulla", on_click=self._close),
                ft.TextButton("Salva", on_click=self._save),
            ]
        )
        
        # Initial population of users if needed
        self._load_users()
        self._on_condivisione_change(None) # Set visibility

    def _load_users(self):
        uid = self.controller.get_user_id()
        fid = self.controller.get_family_id() or ottieni_prima_famiglia_utente(uid)
        
        if fid:
            # Check arguments for ottieni_membri_famiglia. AdminTab calls it with (famiglia_id, master_key_b64, id_utente)
            master_key = self.page_ref.session.get("master_key")
            membri = ottieni_membri_famiglia(fid, master_key, uid)
            # Filter out self
            membri = [m for m in membri if str(m['id_utente']) != str(uid)]
            
            for m in membri:
                sw = ft.Switch(label=f"{m.get('nome', m.get('username', 'Utente'))} {m.get('cognome','')}", value=False)
                self.selected_users_switches[str(m['id_utente'])] = sw
                self.col_selezione_utenti.controls.append(sw)
            
            # If editing and mode is selection, activate switches
            if self.contatto and self.contatto.get('tipo_condivisione') == 'selezione':
                shared_ids = self.contatto.get('condiviso_con', [])
                for uid_shared in shared_ids:
                    if str(uid_shared) in self.selected_users_switches:
                        self.selected_users_switches[str(uid_shared)].value = True
    
    def _build_color_picker(self):
        self.color_circles.controls.clear()
        for color in self.colors:
            is_selected = (color == self.selected_color)
            self.color_circles.controls.append(
                ft.Container(
                    width=30, height=30,
                    bgcolor=color,
                    border_radius=15,
                    border=ft.border.all(2, ft.Colors.WHITE) if is_selected else None,
                    on_click=partial(self._select_color, color),
                    padding=2
                )
            )

    def _select_color(self, color, e):
        self.selected_color = color
        self._build_color_picker()
        self.color_circles.update()

    def _on_condivisione_change(self, e):
        self.col_selezione_utenti.visible = (self.dd_condivisione.value == 'selezione')
        self.page_ref.update()

    def _close(self, e):
        self.page_ref.close(self)

    def _save(self, e):
        nome = self.tf_nome.value
        if not nome:
            self.tf_nome.error_text = "Il nome è obbligatorio"
            self.tf_nome.update()
            return

        master_key = self.page_ref.session.get("master_key")
        user_id = self.controller.get_user_id()
        fam_id = self.controller.get_family_id() or ottieni_prima_famiglia_utente(user_id)
        
        condivisi = []
        if self.dd_condivisione.value == 'selezione':
            for uid, sw in self.selected_users_switches.items():
                if sw.value:
                    condivisi.append(uid)
        
        data = {
            'nome': nome,
            'cognome': self.tf_cognome.value,
            'societa': self.tf_societa.value,
            'email': self.tf_email.value,
            'telefono': self.tf_telefono.value,
            'iban': self.tf_iban.value,
            'tipo_condivisione': self.dd_condivisione.value,
            'condivisi_ids': condivisi,
            'id_famiglia': fam_id,
            'colore': self.selected_color
        }
        
        self.controller.show_loading("Salvataggio...")
        
        try:
            if self.contatto:
                # Update
                success = modifica_contatto(self.contatto['id_contatto'], user_id, data, master_key_b64=master_key)
            else:
                # Create
                success = crea_contatto(
                    user_id, 
                    data['nome'], data['cognome'], data['societa'], 
                    data['iban'], data['email'], data['telefono'], 
                    data['tipo_condivisione'], 
                    contatti_condivisi_ids=condivisi, 
                    id_famiglia=fam_id, 
                    master_key_b64=master_key,
                    colore=data['colore']
                )
            
            self.controller.hide_loading()
            
            if success:
                self.controller.show_snack_bar("Salvataggio completato!", success=True)
                self._close(None)
                if self.on_dismiss_callback:
                    self.on_dismiss_callback()
            else:
                self.controller.show_snack_bar("Errore durante il salvataggio.", success=False)
                
        except Exception as ex:
             self.controller.hide_loading()
             print(ex)
             self.controller.show_snack_bar(f"Errore: {ex}", success=False)
