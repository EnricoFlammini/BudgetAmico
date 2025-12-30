import flet as ft
from utils.localization import loc
from db.gestione_db import aggiungi_conto, modifica_conto

class InvestimentoDialog(ft.AlertDialog):
    def __init__(self, page, on_save, conto_da_modificare=None):
        super().__init__()
        self.page_ref = page # Renamed to avoid read-only property conflict
        self.on_save = on_save
        self.conto_da_modificare = conto_da_modificare
        self.modal = True
        self.title = ft.Text(loc.get("edit_investment_account") if conto_da_modificare else loc.get("new_investment_account"))
        
        # Campi del form
        self.nome_broker = ft.TextField(
            label=loc.get("broker_name"), 
            autofocus=True,
            value=conto_da_modificare['nome_conto'] if conto_da_modificare else ""
        )
        


        self.borsa_default = ft.Dropdown(
            label=loc.get("default_exchange"),
            options=[
                ft.dropdown.Option(".MI", loc.get("exchange_milano")),
                ft.dropdown.Option(".L", loc.get("exchange_londra")),
                ft.dropdown.Option(".DE", loc.get("exchange_xetra")),
                ft.dropdown.Option(".PA", loc.get("exchange_parigi")),
                ft.dropdown.Option(".SW", loc.get("exchange_svizzera")),
                ft.dropdown.Option(".AS", loc.get("exchange_amsterdam")),
            ],
            value=conto_da_modificare['borsa_default'] if conto_da_modificare and 'borsa_default' in conto_da_modificare else None
        )

        self.content = ft.Column(
            [
                self.nome_broker,
                self.borsa_default
            ],
            tight=True,
            width=400
        )

        self.actions = [
            ft.TextButton(loc.get("cancel"), on_click=self.chiudi),
            ft.ElevatedButton(loc.get("save"), on_click=self.salva)
        ]
        self.actions_alignment = ft.MainAxisAlignment.END

    def chiudi(self, e=None):
        try:
            self.page_ref.close(self)
            self.page_ref.update()
        except Exception as ex:
            print(f"Errore chiusura dialog investimento: {ex}")
            import traceback
            traceback.print_exc()

    def salva(self, e):
        try:
            nome = self.nome_broker.value.strip()
            borsa = self.borsa_default.value

            if not nome:
                self.nome_broker.error_text = loc.get("required_field")
                self.nome_broker.update()
                return

            master_key_b64 = self.page_ref.session.get("master_key")
            user_id = self.page_ref.session.get("utente_loggato")['id']

            if self.conto_da_modificare:
                successo, msg = modifica_conto(
                    self.conto_da_modificare['id_conto'], 
                    user_id, 
                    nome, 
                    "Investimento", 
                    valore_manuale=0.0, 
                    borsa_default=borsa,
                    master_key_b64=master_key_b64
                )
            else:
                res = aggiungi_conto(user_id, nome, "Investimento", valore_manuale=0.0, borsa_default=borsa, master_key_b64=master_key_b64)
                if isinstance(res, tuple):
                    successo, msg = True, res[1]
                else:
                    successo, msg = False, "Errore generico"

            if successo:
                self.chiudi()
                if self.on_save:
                    self.on_save()
            else:
                snack = ft.SnackBar(content=ft.Text(f"Errore: {msg}"))
                if hasattr(self.page_ref, "open"):
                    self.page_ref.open(snack)
                else:
                    self.page_ref.snack_bar = snack
                    snack.open = True
                    self.page_ref.update()
        except Exception as ex:
            print(f"Errore salvataggio investimento: {ex}")
            import traceback
            traceback.print_exc()
            self.chiudi() # Chiudi comunque per evitare blocco
            snack = ft.SnackBar(content=ft.Text(f"Errore inaspettato: {ex}"))
            if hasattr(self.page_ref, "open"):
                self.page_ref.open(snack)
            else:
                self.page_ref.snack_bar = snack
                snack.open = True
                self.page_ref.update()
