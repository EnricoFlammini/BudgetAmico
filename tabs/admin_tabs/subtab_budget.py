import flet as ft
import datetime
# Importa solo le funzioni DB necessarie per QUESTA scheda
from db.gestione_db import (
    ottieni_categorie,
    ottieni_budget_famiglia,
    imposta_budget,
    salva_budget_mese_corrente
)


class AdminSubTabBudget(ft.Column):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.page = controller.page

        # --- Controlli della Scheda ---

        # 1. Elenco Budget
        self.lv_admin_budget = ft.Column(spacing=10)
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
            ft.Text("Imposta un limite di spesa mensile per categoria (0 per nessun limite).", size=12,
                    color=ft.Colors.GREY_500),
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
            )
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
            categorie = ottieni_categorie(famiglia_id)
            budget_impostati = ottieni_budget_famiglia(famiglia_id)

            # Mappa i budget per un accesso rapido
            mappa_budget = {b['id_categoria']: b['importo_limite'] for b in budget_impostati}

            if not categorie:
                self.lv_admin_budget.controls.append(ft.Text("Nessuna categoria trovata. Creane una prima."))

            totale_budget_impostato = 0.0

            for cat in categorie:
                id_cat = cat['id_categoria']
                nome_cat = cat['nome_categoria']
                limite_attuale = mappa_budget.get(id_cat, 0.0)
                totale_budget_impostato += limite_attuale

                txt_limite = ft.TextField(
                    label=nome_cat,
                    prefix="€",
                    value=f"{limite_attuale:.2f}",
                    keyboard_type=ft.KeyboardType.NUMBER,
                    width=200
                )

                btn_salva = ft.IconButton(
                    icon=ft.Icons.SAVE,
                    tooltip="Salva Limite",
                    data={'id_categoria': id_cat, 'textfield': txt_limite},
                    on_click=self._salva_budget_categoria
                )

                self.lv_admin_budget.controls.append(
                    ft.Row([txt_limite, btn_salva], vertical_alignment=ft.CrossAxisAlignment.START)
                )

            self.txt_admin_totale_budget.value = f"Budget Mensile Totale: {totale_budget_impostato:.2f} €"

        except Exception as e:
            self.lv_admin_budget.controls.append(ft.Text(f"Errore caricamento budget: {e}"))

        # L'aggiornamento UI è gestito dal controller globale

    def _salva_budget_categoria(self, e):
        id_categoria = e.control.data['id_categoria']
        txt_field = e.control.data['textfield']

        try:
            importo_str = txt_field.value.replace(",", ".")
            importo_limite = float(importo_str)
            if importo_limite < 0:
                raise ValueError("Limite negativo")

            famiglia_id = self.controller.get_family_id()
            success = imposta_budget(famiglia_id, id_categoria, importo_limite)

            if success:
                self.controller.show_snack_bar(f"Budget per {txt_field.label} salvato!", success=True)
                txt_field.error_text = None
                self.controller.update_all_views()
            else:
                raise Exception("Errore salvataggio DB")

        except Exception as ex:
            print(f"Errore salvataggio budget: {ex}")
            self.controller.show_snack_bar(f"Errore: Inserire un importo valido (es. 250.50)", success=False)
            txt_field.error_text = "Non valido"
            if self.page:
                txt_field.update()

    def _clicca_salva_storico_selezionato(self, e):
        famiglia_id = self.controller.get_family_id()
        if not famiglia_id:
            return

        try:
            anno_selezionato = int(self.dd_admin_budget_anno.value)
            mese_selezionato = int(self.dd_admin_budget_mese.value)

            success = salva_budget_mese_corrente(famiglia_id, anno_selezionato, mese_selezionato)

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