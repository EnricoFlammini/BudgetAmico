import flet as ft
import datetime
from db.gestione_db import (
    get_impostazioni_budget_famiglia,
    set_impostazioni_budget_famiglia,
    calcola_entrate_mensili_famiglia,
    ottieni_totale_budget_allocato,
    ottieni_totale_budget_storico,
    ottieni_periodi_budget_disponibili,
    salva_impostazioni_budget_storico,
    ottieni_budget_famiglia,
    ottieni_categorie_e_sottocategorie,
    imposta_budget,
    salva_budget_mese_corrente
)
from utils.styles import AppStyles, AppColors


class AdminSubTabBudgetManager(ft.Column):
    """
    Pagina Gestione Budget nel pannello Admin.
    Permette di impostare:
    - Entrate mensili (manuale o calcolate da transazioni categoria "Entrate")
    - Risparmio (percentuale o importo fisso)
    - Visualizzazione e modifica budget per sottocategoria
    - Warning per sforamenti budget
    """
    
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.controller.page = controller.page
        
        # --- Sezione 1: Entrate Mensili Stimate ---
        self.txt_entrate_mensili = ft.TextField(
            label="Entrate mensili stimate (€)",
            prefix_text="€ ",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=250,
            on_change=self._on_entrate_change,
            on_blur=self._auto_save_impostazioni
        )
        self.txt_entrate_display = ft.Text("", size=24, weight=ft.FontWeight.BOLD, color=AppColors.SUCCESS)
        
        # --- Sezione 2: Risparmio ---
        self.dd_risparmio_tipo = ft.Dropdown(
            label="Tipo Risparmio",
            options=[
                ft.dropdown.Option("percentuale", "Percentuale (%)"),
                ft.dropdown.Option("importo", "Importo Fisso (€)")
            ],
            value="percentuale",
            width=200
        )
        self.dd_risparmio_tipo.on_change = self._on_risparmio_tipo_change
        self.txt_risparmio_valore = ft.TextField(
            label="Valore Risparmio",
            keyboard_type=ft.KeyboardType.NUMBER,
            width=150,
            on_change=self._on_risparmio_change,
            on_blur=self._auto_save_impostazioni
        )
        self.txt_budget_disponibile = ft.Text("", size=18, weight=ft.FontWeight.BOLD)
        
        # --- Sezione 3: Riepilogo Allocazione ---
        self.txt_totale_allocato = ft.Text("", size=16)
        self.txt_rimanente_allocare = ft.Text("", size=16)
        self.progress_allocazione = ft.ProgressBar(value=0, color=AppColors.SUCCESS, bgcolor=AppColors.SURFACE_VARIANT)
        self.container_status = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.CHECK_CIRCLE, color=AppColors.SUCCESS),
                ft.Text("Budget OK", color=AppColors.SUCCESS, weight=ft.FontWeight.BOLD)
            ]),
            padding=10,
            border_radius=5,
            bgcolor=ft.Colors.with_opacity(0.1, AppColors.SUCCESS)
        )
        
        # --- Sezione 4: Lista Budget per Sottocategoria ---
        self.lv_budget_sottocategorie = ft.Column(spacing=10)
        
        # --- Controlli Periodo (Data) ---
        now = datetime.datetime.now()
        anno_attuale = now.year
        opzioni_mesi = [ft.dropdown.Option(str(i), f"{i:02d}") for i in range(1, 13)]
        opzioni_anni = [ft.dropdown.Option(str(a)) for a in range(anno_attuale - 2, anno_attuale + 3)]
        
        self.dd_periodo_mese = ft.Dropdown(
            label="Mese",
            options=opzioni_mesi,
            value=str(now.month),
            width=100,
            on_change=self._on_periodo_change
        )
        self.dd_periodo_anno = ft.Dropdown(
            label="Anno",
            options=opzioni_anni,
            value=str(anno_attuale),
            width=120,
            on_change=self._on_periodo_change
        )
        self.dd_clona_sorgente = ft.Dropdown(
            label="Copia configurazione da...",
            width=300,
            on_change=self._on_clona_sorgente_change,
            options=[] # Popolato in update_view_data
        )
        
        # --- Layout della Scheda ---
        self.controls = [
            # Header
            ft.Row([
                ft.Column([
                    ft.Text("Gestione Budget", size=24, weight=ft.FontWeight.BOLD),
                    ft.Text("Configura entrate, risparmio e limiti per il periodo selezionato.", size=12, color=AppColors.TEXT_SECONDARY),
                ], expand=True),
                ft.Row([
                    self.dd_periodo_mese,
                    self.dd_periodo_anno,
                ], spacing=10)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            
            ft.Row([
                ft.Icon(ft.Icons.COPY_ALL, size=20, color=AppColors.TEXT_SECONDARY),
                self.dd_clona_sorgente
            ], alignment=ft.MainAxisAlignment.END, spacing=10),
            
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            
            # Sezione Entrate Mensili
            AppStyles.card_container(
                ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.ATTACH_MONEY, color=AppColors.PRIMARY),
                        ft.Text("Entrate Mensili", size=18, weight=ft.FontWeight.BOLD)
                    ]),
                    ft.Row([
                        self.txt_entrate_mensili,
                    ], spacing=10),
                    self.txt_entrate_display
                ]),
                padding=15
            ),
            
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            
            # Sezione Risparmio
            AppStyles.card_container(
                ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.SAVINGS, color=AppColors.PRIMARY),
                        ft.Text("Risparmio", size=18, weight=ft.FontWeight.BOLD)
                    ]),
                    ft.Row([
                        self.dd_risparmio_tipo,
                        self.txt_risparmio_valore,
                    ], spacing=10),
                    ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
                    self.txt_budget_disponibile
                ]),
                padding=15
            ),
            
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            
            # Sezione Riepilogo
            AppStyles.card_container(
                ft.Column([
                    ft.Row([
                        ft.Icon(ft.Icons.PIE_CHART, color=AppColors.PRIMARY),
                        ft.Text("Riepilogo Allocazione", size=18, weight=ft.FontWeight.BOLD)
                    ]),
                    self.progress_allocazione,
                    ft.Row([
                        self.txt_totale_allocato,
                        self.txt_rimanente_allocare
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    self.container_status
                ]),
                padding=15
            ),
            
            ft.Divider(height=10, color=ft.Colors.TRANSPARENT),
            
            # Sezione Budget per Sottocategoria
            ft.Text("Limiti Budget per Sottocategoria", size=18, weight=ft.FontWeight.BOLD),
            self.lv_budget_sottocategorie,
            
            ft.Divider(height=20),
            
            # Sezione Salvataggio rimossa (auto-save attivo)
            
            ft.Container(height=80)
        ]
        
        self.expand = True
        self.spacing = 10
        self.scroll = ft.ScrollMode.ADAPTIVE
    
    def update_view_data(self, is_initial_load=False, prefetched_data=None):
        """Aggiorna i dati della vista using optional prefetched data."""
        famiglia_id = self.controller.get_family_id()
        if not famiglia_id:
            return
        
        anno = int(self.dd_periodo_anno.value)
        mese = int(self.dd_periodo_mese.value)
        today = datetime.date.today()
        is_current = (anno == today.year and mese == today.month)
        
        # Popola menu clona
        periodi = ottieni_periodi_budget_disponibili(famiglia_id)
        self.dd_clona_sorgente.options = [
            ft.dropdown.Option(f"{p['anno']}_{p['mese']}", f"{p['anno']}-{p['mese']:02d}")
            for p in periodi
            if not (p['anno'] == anno and p['mese'] == mese)
        ]
        self.dd_clona_sorgente.value = None

        # Usa dati pre-fetchati se disponibili (e se è il mese corrente, dato che il prefetch di solito è per il corrente)
        if prefetched_data and is_current:
            impostazioni = prefetched_data.get('impostazioni_budget')
            dati_categorie = prefetched_data.get('categorie')
            budget_impostati = prefetched_data.get('budget_impostati')
        else:
            # Caricamento dinamico basato su anno/mese
            master_key_b64 = self.controller.page.session.get("master_key")
            id_utente = self.controller.get_user_id()
            
            impostazioni = get_impostazioni_budget_famiglia(famiglia_id, anno, mese)
            dati_categorie = ottieni_categorie_e_sottocategorie(famiglia_id)
            budget_impostati = ottieni_budget_famiglia(famiglia_id, master_key_b64, id_utente, anno, mese)

        if impostazioni:
            self.txt_entrate_mensili.value = f"{impostazioni['entrate_mensili']:.2f}"
            self.dd_risparmio_tipo.value = impostazioni['risparmio_tipo']
            self.txt_risparmio_valore.value = f"{impostazioni['risparmio_valore']:.2f}"
        else:
            self.txt_entrate_mensili.value = "0.00"
            self.txt_risparmio_valore.value = "0.00"
        
        self._aggiorna_display()
        self._popola_lista_budget(dati_categorie, budget_impostati)

    
    def _aggiorna_display(self):
        """Aggiorna tutti i display calcolati."""
        try:
            entrate = float(self.txt_entrate_mensili.value.replace(",", ".") or 0)
            risparmio_tipo = self.dd_risparmio_tipo.value
            risparmio_valore = float(self.txt_risparmio_valore.value.replace(",", ".") or 0)
            
            # Calcola risparmio effettivo
            if risparmio_tipo == "percentuale":
                risparmio_importo = entrate * (risparmio_valore / 100)
                risparmio_display = f"{risparmio_valore:.1f}%"
            else:
                risparmio_importo = risparmio_valore
                risparmio_display = f"€{risparmio_valore:.2f}"
            
            # Budget disponibile
            budget_disponibile = entrate - risparmio_importo
            
            # Display entrate
            self.txt_entrate_display.value = f"Entrate: €{entrate:,.2f} (100%)"
            
            # Display budget disponibile
            if entrate > 0:
                perc_disp = ((entrate - risparmio_importo) / entrate) * 100
                self.txt_budget_disponibile.value = f"Budget Disponibile: €{budget_disponibile:,.2f} ({perc_disp:.1f}% delle entrate)"
            else:
                self.txt_budget_disponibile.value = f"Budget Disponibile: €{budget_disponibile:,.2f}"
            
            # Calcola totale allocato
            famiglia_id = self.controller.get_family_id()
            master_key_b64 = self.controller.page.session.get("master_key")
            id_utente = self.controller.get_user_id()
            
            anno = int(self.dd_periodo_anno.value)
            mese = int(self.dd_periodo_mese.value)
            today = datetime.date.today()
            
            if anno == today.year and mese == today.month:
                totale_allocato = ottieni_totale_budget_allocato(famiglia_id, master_key_b64, id_utente)
            else:
                totale_allocato = ottieni_totale_budget_storico(famiglia_id, anno, mese, master_key_b64, id_utente)
            
            rimanente = budget_disponibile - totale_allocato
            
            self.txt_totale_allocato.value = f"Totale Allocato: €{totale_allocato:,.2f}"
            self.txt_rimanente_allocare.value = f"Rimanente: €{rimanente:,.2f}"
            
            # Progress bar e status
            if budget_disponibile > 0:
                percentuale = totale_allocato / budget_disponibile
                self.progress_allocazione.value = min(percentuale, 1.0)
            else:
                percentuale = 0
                self.progress_allocazione.value = 0
            
            # Determina colore e status
            if totale_allocato <= budget_disponibile:
                # Verde: tutto ok
                self.progress_allocazione.color = AppColors.SUCCESS
                self.container_status.bgcolor = ft.Colors.with_opacity(0.1, AppColors.SUCCESS)
                self.container_status.content = ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE, color=AppColors.SUCCESS),
                    ft.Text("Budget OK", color=AppColors.SUCCESS, weight=ft.FontWeight.BOLD)
                ])
            elif totale_allocato <= entrate:
                # Giallo: superato budget disponibile ma non 100%
                self.progress_allocazione.color = AppColors.WARNING
                self.container_status.bgcolor = ft.Colors.with_opacity(0.1, AppColors.WARNING)
                perc_sforamento = (totale_allocato / budget_disponibile * 100) if budget_disponibile > 0 else 0
                self.container_status.content = ft.Row([
                    ft.Icon(ft.Icons.WARNING, color=AppColors.WARNING),
                    ft.Text(f"Attenzione: {perc_sforamento:.1f}% del budget disponibile", color=AppColors.WARNING, weight=ft.FontWeight.BOLD)
                ])
            else:
                # Rosso: superato 100% delle entrate
                self.progress_allocazione.color = AppColors.ERROR
                self.container_status.bgcolor = ft.Colors.with_opacity(0.1, AppColors.ERROR)
                perc_sforamento = (totale_allocato / entrate * 100) if entrate > 0 else 0
                self.container_status.content = ft.Row([
                    ft.Icon(ft.Icons.ERROR, color=AppColors.ERROR),
                    ft.Text(f"Sforamento: {perc_sforamento:.1f}% del budget totale!", color=AppColors.ERROR, weight=ft.FontWeight.BOLD)
                ])
            
            if self.page:
                self.page.update()
                
        except Exception as e:
            print(f"Errore aggiornamento display: {e}")
    
    def _popola_lista_budget(self, dati_categorie=None, budget_impostati=None):
        """Popola la lista dei budget per sottocategoria."""
        self.lv_budget_sottocategorie.controls.clear()
        
        famiglia_id = self.controller.get_family_id()
        if not famiglia_id:
            return
        
        try:
            master_key_b64 = self.controller.page.session.get("master_key")
            id_utente = self.controller.get_user_id()
            
            anno = int(self.dd_periodo_anno.value)
            mese = int(self.dd_periodo_mese.value)
            
            # Recupera dati se non passati
            if not dati_categorie:
                dati_categorie = ottieni_categorie_e_sottocategorie(famiglia_id)
            if not budget_impostati:
                budget_impostati = ottieni_budget_famiglia(famiglia_id, master_key_b64, id_utente, anno, mese)

            
            # Mappa budget per sottocategoria
            mappa_budget = {b['id_sottocategoria']: b['importo_limite'] for b in budget_impostati}
            
            for cat_data in dati_categorie:
                nome_cat = cat_data['nome_categoria']
                sottocategorie = cat_data['sottocategorie']
                
                # Requisito: Escludere la categoria 'ENTRATE' dalla modifica budget
                if "ENTRAT" in nome_cat.upper():
                    continue

                if not sottocategorie:
                    continue
                
                # Header categoria
                header = ft.Text(nome_cat, size=16, weight=ft.FontWeight.BOLD, color=AppColors.PRIMARY)
                
                # Lista sottocategorie
                rows = []
                for sub in sottocategorie:
                    id_sub = sub['id_sottocategoria']
                    nome_sub = sub['nome_sottocategoria']
                    limite = mappa_budget.get(id_sub, 0.0)
                    
                    # Usiamo un TextField per ogni sottocategoria per modifica diretta
                    txt_limite_sub = ft.TextField(
                        value=f"{limite:.2f}",
                        width=120,
                        text_size=14,
                        content_padding=5,
                        keyboard_type=ft.KeyboardType.NUMBER,
                        prefix_text="€ ",
                        on_change=self._on_sub_budget_change,
                        on_blur=self._auto_save_budget,
                        data={'id_sottocategoria': id_sub, 'nome': nome_sub}
                    )

                    rows.append(
                        ft.Row([
                            ft.Text(nome_sub, expand=True),
                            txt_limite_sub
                        ], spacing=5)
                    )
                
                self.lv_budget_sottocategorie.controls.append(
                    ft.Container(
                        content=ft.Column([header] + rows),
                        padding=10,
                        border=ft.border.all(1, ft.Colors.OUTLINE_VARIANT),
                        border_radius=8
                    )
                )
                
        except Exception as e:
            print(f"Errore popolamento lista budget: {e}")
            self.lv_budget_sottocategorie.controls.append(
                ft.Text(f"Errore: {e}", color=AppColors.ERROR)
            )

    def _on_sub_budget_change(self, e):
        """Handler cambio valore budget sottocategoria (solo UI)."""
        # Re-calcoliamo i totali globali leggendo tutti i campi della lista
        self._aggiorna_display_realtime()

    def _aggiorna_display_realtime(self):
        """Aggiorna i totali leggendo i valori correnti dai TextField della lista."""
        try:
            totale_allocato = 0.0
            for container in self.lv_budget_sottocategorie.controls:
                # Struttura: Container -> Column -> [Header, Row1, Row2, ...]
                column = container.content
                for row in column.controls[1:]: # Salta l'header
                    # Struttura: Row -> [Text, TextField]
                    txt_field = row.controls[1]
                    try:
                        val = float(txt_field.value.replace(",", ".") or 0)
                        totale_allocato += val
                    except: pass
            
            entrate = float(self.txt_entrate_mensili.value.replace(",", ".") or 0)
            risparmio_tipo = self.dd_risparmio_tipo.value
            risparmio_valore = float(self.txt_risparmio_valore.value.replace(",", ".") or 0)
            
            if risparmio_tipo == "percentuale":
                risparmio_importo = entrate * (risparmio_valore / 100)
            else:
                risparmio_importo = risparmio_valore
            
            budget_disponibile = entrate - risparmio_importo
            rimanente = budget_disponibile - totale_allocato
            
            self.txt_totale_allocato.value = f"Totale Allocato: €{totale_allocato:,.2f}"
            self.txt_rimanente_allocare.value = f"Rimanente: €{rimanente:,.2f}"
            
            if budget_disponibile > 0:
                self.progress_allocazione.value = min(totale_allocato / budget_disponibile, 1.0)
            else:
                self.progress_allocazione.value = 0
            
            # Aggiornamento colori status
            if totale_allocato <= budget_disponibile:
                self.progress_allocazione.color = AppColors.SUCCESS
            elif totale_allocato <= entrate:
                self.progress_allocazione.color = AppColors.WARNING
            else:
                self.progress_allocazione.color = AppColors.ERROR
                
            self.page.update()
        except: pass

    def _auto_save_budget(self, e):
        """Salva automaticamente il budget di una sottocategoria al termine della modifica."""
        try:
            id_sub = e.control.data['id_sottocategoria']
            nome = e.control.data['nome']
            valore = float(e.control.value.replace(",", ".") or 0)
            
            famiglia_id = self.controller.get_family_id()
            master_key_b64 = self.controller.page.session.get("master_key")
            id_utente = self.controller.get_user_id()
            
            anno = int(self.dd_periodo_anno.value)
            mese = int(self.dd_periodo_mese.value)
            
            imposta_budget(
                famiglia_id, id_sub, valore, 
                master_key_b64, id_utente, anno=anno, mese=mese
            )
            # Silenzioso
        except: pass
    
    def _on_entrate_change(self, e):
        """Handler cambio entrate."""
        self._aggiorna_display()
    
    def _on_risparmio_tipo_change(self, e):
        """Handler cambio tipo risparmio."""
        if self.dd_risparmio_tipo.value == "percentuale":
            self.txt_risparmio_valore.label = "Percentuale (%)"
            self.txt_risparmio_valore.suffix_text = "%"
            self.txt_risparmio_valore.prefix_text = None
        else:
            self.txt_risparmio_valore.label = "Importo (€)"
            self.txt_risparmio_valore.prefix_text = "€ "
            self.txt_risparmio_valore.suffix_text = None
        self._aggiorna_display()
    
    def _on_risparmio_change(self, e):
        """Handler cambio valore risparmio."""
        self._aggiorna_display()
    
    def _auto_save_impostazioni(self, e):
        """Salva automaticamente entrate e risparmio."""
        try:
            entrate = float(self.txt_entrate_mensili.value.replace(",", ".") or 0)
            risparmio_tipo = self.dd_risparmio_tipo.value
            risparmio_valore = float(self.txt_risparmio_valore.value.replace(",", ".") or 0)
            
            famiglia_id = self.controller.get_family_id()
            anno = int(self.dd_periodo_anno.value)
            mese = int(self.dd_periodo_mese.value)
            
            set_impostazioni_budget_famiglia(
                famiglia_id, entrate, risparmio_tipo, risparmio_valore, 
                anno=anno, mese=mese
            )
            # Silenzioso, nessuna notifica per auto-save UI
        except:
            pass

    def _on_clona_sorgente_change(self, e):
        """Handler per clonazione da periodo selezionato."""
        if not self.dd_clona_sorgente.value:
            return
            
        try:
            famiglia_id = self.controller.get_family_id()
            master_key_b64 = self.controller.page.session.get("master_key")
            id_utente = self.controller.get_user_id()
            
            anno_src, mese_src = map(int, self.dd_clona_sorgente.value.split("_"))
            anno_target = int(self.dd_periodo_anno.value)
            mese_target = int(self.dd_periodo_mese.value)
            
            self.controller.show_loading(f"Copia configurazione da {anno_src}-{mese_src:02d}...")
            
            # 1. Recupera impostazioni sorgente
            imps = get_impostazioni_budget_famiglia(famiglia_id, anno=anno_src, mese=mese_src) 
            
            # 2. Salva su target
            set_impostazioni_budget_famiglia(
                famiglia_id, imps['entrate_mensili'], imps['risparmio_tipo'], 
                imps['risparmio_valore'], anno=anno_target, mese=mese_target
            )
            
            # 3. Salva budget sorgente su target
            # Recuperiamo i budget della sorgente
            budget_src = ottieni_budget_famiglia(famiglia_id, master_key_b64, id_utente, anno_src, mese_src)
            for b in budget_src:
                imposta_budget(
                    famiglia_id, b['id_sottocategoria'], b['importo_limite'], 
                    master_key_b64, id_utente, anno=anno_target, mese=mese_target
                )
            
            self.controller.show_snack_bar(f"Configurazione copiata da {anno_src}-{mese_src:02d}!", success=True)
            self.update_view_data()
            
        except Exception as ex:
            self.controller.show_snack_bar(f"Errore copia: {ex}", success=False)
        finally:
            self.controller.hide_loading()
            self.dd_clona_sorgente.value = None
            self.page.update()
    
    def _modifica_budget_click(self, e):
        """Apre dialog per modificare budget sottocategoria."""
        data = e.control.data
        id_sottocategoria = data['id_sottocategoria']
        nome = data['nome']
        limite_attuale = data['limite']
        
        txt_limite = ft.TextField(
            label="Nuovo Limite",
            prefix_text="€ ",
            value=f"{limite_attuale:.2f}",
            keyboard_type=ft.KeyboardType.NUMBER,
            autofocus=True
        )
        
        def salva(e_dialog):
            try:
                nuovo_limite = float(txt_limite.value.replace(",", "."))
                anno = int(self.dd_periodo_anno.value)
                mese = int(self.dd_periodo_mese.value)
                
                famiglia_id = self.controller.get_family_id()
                master_key_b64 = self.controller.page.session.get("master_key")
                id_utente = self.controller.get_user_id()
                
                success = imposta_budget(
                    famiglia_id, id_sottocategoria, nuovo_limite, 
                    master_key_b64, id_utente, anno=anno, mese=mese
                )
                
                if success:
                    self.controller.show_snack_bar(f"Budget per '{nome}' salvato per {anno}-{mese:02d}!", success=True)
                    self.controller.page.close(dialog)
                    self._popola_lista_budget()
                    self._aggiorna_display()
                else:
                    raise Exception("Errore salvataggio")
            except Exception as ex:
                self.controller.show_snack_bar(f"Errore: {ex}", success=False)
        
        def chiudi(e_dialog):
            self.controller.page.close(dialog)
        
        dialog = ft.AlertDialog(
            title=ft.Text(f"Modifica Budget: {nome}"),
            content=txt_limite,
            actions=[
                ft.TextButton("Annulla", on_click=chiudi),
                ft.ElevatedButton("Salva", on_click=salva)
            ]
        )
        
        self.controller.page.open(dialog)
    
    def _on_periodo_change(self, e):
        """Handler cambio mese/anno di riferimento."""
        self.update_view_data()
