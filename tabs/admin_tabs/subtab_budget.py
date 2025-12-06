import flet as ft
import datetime
# Importa solo le funzioni DB necessarie per QUESTA scheda
from db.gestione_db import (
    ottieni_categorie_e_sottocategorie,
    ottieni_budget_famiglia,
    imposta_budget,
    salva_budget_mese_corrente
)
from utils.styles import AppStyles, AppColors


class AdminSubTabBudget(ft.Column):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.page = controller.page

        # --- Controlli della Scheda ---

        # 1. Elenco Budget
        self.lv_admin_budget = ft.Column(spacing=20) # Aumentato spacing per separare meglio le categorie
        self.txt_admin_totale_budget = ft.Text(size=16, weight=ft.FontWeight.BOLD)

        # 2. Controlli Storicizzazione
        now = datetime.datetime.now()
        anno_attuale = now.year
        opzioni_mesi = [ft.dropdown.Option(str(i), f"{i:02d}") for i in range(1, 13)]
        opzioni_anni = [ft.dropdown.Option(str(a)) for a in range(anno_attuale - 2, anno_attuale + 2)]

        self.dd_admin_budget_mese = ft.Dropdown(
            label="Mese",
            options=opzioni_mesi,
            value=str(now.month),
            width=100
        )
        self.dd_admin_budget_anno = ft.Dropdown(
            label="Anno",
            options=opzioni_anni,
            value=str(anno_attuale),
            width=120
        )

        # --- Layout della Scheda ---
        self.controls = [
            ft.Text("Gestione Budget Mensile", size=24, weight=ft.FontWeight.BOLD),
            ft.Text("Imposta un limite di spesa mensile per SOTTOCATEGORIA (0 per nessun limite).", size=12,
                    color=ft.Colors.GREY_500),
            ft.Divider(height=20, color=ft.Colors.TRANSPARENT),
            self.lv_admin_budget,  # Contenitore per i campi di testo
            ft.Divider(height=10),
            self.txt_admin_totale_budget,
            ft.Divider(height=20),

            ft.Text("Storicizzazione Manuale", size=18, weight=ft.FontWeight.BOLD),
            ft.Text("Salva uno snapshot del budget di un mese specifico.", size=12, color=ft.Colors.GREY_500),
            ft.Row(
                [
                    self.dd_admin_budget_mese,
                    self.dd_admin_budget_anno,
                    ft.ElevatedButton(
                        "Salva Snapshot",
                        icon=ft.Icons.SAVE_AS,
                        on_click=self._clicca_salva_storico_selezionato,
                        tooltip="Salva lo snapshot del mese e anno selezionati."
                    )
                ],
                alignment=ft.MainAxisAlignment.START
            ),
            # Spazio in basso per evitare interferenze con il pulsante +
            ft.Container(height=80)
        ]

        self.expand = True
        self.spacing = 10
        self.scroll = ft.ScrollMode.ADAPTIVE  # Scroll sull'intera colonna

    def update_view_data(self, is_initial_load=False):
        """ Questa funzione viene chiamata da AdminTab """
        famiglia_id = self.controller.get_family_id()
        if not famiglia_id:
            return

        self.lv_admin_budget.controls.clear()

        try:
            # Recupera struttura completa categorie/sottocategorie
            dati_categorie = ottieni_categorie_e_sottocategorie(famiglia_id)
            
            # Pass master_key_b64
            master_key_b64 = self.controller.page.session.get("master_key")
            budget_impostati = ottieni_budget_famiglia(famiglia_id, master_key_b64)

            # Mappa i budget per un accesso rapido usando id_sottocategoria
            mappa_budget = {b['id_sottocategoria']: b['importo_limite'] for b in budget_impostati}

            if not dati_categorie:
                self.lv_admin_budget.controls.append(ft.Text("Nessuna categoria trovata. Creane una prima."))

            totale_budget_impostato = 0.0

            # Itera sulle categorie
            for cat_data in dati_categorie:
                nome_cat = cat_data['nome_categoria']
                sottocategorie = cat_data['sottocategorie']
                
                if not sottocategorie:
                    continue

                # Crea header categoria
                header_cat = ft.Text(nome_cat, size=18, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY)
                
                # Container per le sottocategorie di questa categoria
                container_sottocategorie = ft.Column(spacing=10)

                for sub in sottocategorie:
                    id_sub = sub['id_sottocategoria']
                    nome_sub = sub['nome_sottocategoria']
                    
                    limite_attuale = mappa_budget.get(id_sub, 0.0)
                    totale_budget_impostato += limite_attuale

                    # Testo con nome sottocategoria e valore budget
                    txt_nome_budget = ft.Text(
                        f"{nome_sub}: €{limite_attuale:.2f}",
                        size=14,
                        weight=ft.FontWeight.W_500,
                        width=250
                    )

                    btn_modifica = ft.IconButton(
                        icon=ft.Icons.EDIT,
                        tooltip="Modifica Limite",
                        data={'id_sottocategoria': id_sub, 'nome_sottocategoria': nome_sub, 'limite_attuale': limite_attuale},
                        on_click=self._modifica_budget_sottocategoria,
                        icon_size=20
                    )

                    container_sottocategorie.controls.append(
                        ft.Row(
                            [txt_nome_budget, btn_modifica], 
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                            spacing=10
                        )
                    )
                
                # Aggiungi il blocco categoria alla lista principale
                self.lv_admin_budget.controls.append(
                    ft.Container(
                        content=ft.Column([header_cat, container_sottocategorie]),
                        padding=10,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=10
                    )
                )

            self.txt_admin_totale_budget.value = f"Budget Mensile Totale: {totale_budget_impostato:.2f} €"

        except Exception as e:
            self.lv_admin_budget.controls.append(ft.Text(f"Errore caricamento budget: {e}"))
            print(f"Errore caricamento budget: {e}")

        # L'aggiornamento UI è gestito dal controller globale

    def _modifica_budget_sottocategoria(self, e):
        """Apre un dialog per modificare il budget di una sottocategoria"""
        id_sottocategoria = e.control.data['id_sottocategoria']
        nome_sottocategoria = e.control.data['nome_sottocategoria']
        limite_attuale = e.control.data['limite_attuale']

        # Campo di testo per il nuovo valore
        txt_nuovo_limite = ft.TextField(
            label="Nuovo Limite",
            prefix="€",
            value=f"{limite_attuale:.2f}",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=200,
            autofocus=True
        )

        def salva_modifica(e_dialog):
            try:
                importo_str = txt_nuovo_limite.value.replace(",", ".")
                importo_limite = float(importo_str)
                if importo_limite < 0:
                    raise ValueError("Limite negativo")

                famiglia_id = self.controller.get_family_id()
                
                # Pass master_key_b64
                master_key_b64 = self.controller.page.session.get("master_key")
                print(f"[DEBUG] subtab_budget - master_key in session: {bool(master_key_b64)}")
                if master_key_b64:
                    print(f"[DEBUG] subtab_budget - master_key content (partial): {master_key_b64[:10]}...")
                success = imposta_budget(famiglia_id, id_sottocategoria, importo_limite, master_key_b64)

                if success:
                    self.controller.show_snack_bar(f"Budget per {nome_sottocategoria} salvato!", success=True)
                    self.page.close(dialog)
                    self.page.update()
                    self.controller.update_all_views()
                else:
                    raise Exception("Errore salvataggio DB")

            except Exception as ex:
                print(f"Errore salvataggio budget: {ex}")
                self.controller.show_snack_bar(f"Errore: Inserire un importo valido (es. 250.50)", success=False)
                txt_nuovo_limite.error_text = "Non valido"
                txt_nuovo_limite.update()

        def chiudi_dialog(e_dialog):
            self.page.close(dialog)
            self.page.update()

        dialog = ft.AlertDialog(
            title=ft.Text(f"Modifica Budget: {nome_sottocategoria}"),
            content=txt_nuovo_limite,
            actions=[
                ft.TextButton("Annulla", on_click=chiudi_dialog),
                ft.ElevatedButton("Salva", on_click=salva_modifica)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

        self.page.open(dialog)
        self.page.update()

    def _clicca_salva_storico_selezionato(self, e):
        famiglia_id = self.controller.get_family_id()
        if not famiglia_id:
            return

        try:
            anno_selezionato = int(self.dd_admin_budget_anno.value)
            mese_selezionato = int(self.dd_admin_budget_mese.value)

            # Pass master_key_b64
            master_key_b64 = self.controller.page.session.get("master_key")
            success = salva_budget_mese_corrente(famiglia_id, anno_selezionato, mese_selezionato, master_key_b64)

            if success:
                self.controller.show_snack_bar(
                    f"Snapshot del budget {anno_selezionato}-{mese_selezionato:02d} salvato nello storico!",
                    success=True
                )
                self.controller.update_all_views()
            else:
                self.controller.show_snack_bar("❌ Errore durante il salvataggio dello storico.", success=False)

        except Exception as ex:
            print(f"Errore parsing data per storicizzazione: {ex}")
            self.controller.show_snack_bar("❌ Errore: Seleziona un mese e un anno validi.", success=False)