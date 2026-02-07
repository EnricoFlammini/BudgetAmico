import flet as ft
import datetime
import csv
import io
from db.gestione_db import (
    aggiungi_rata_piano_ammortamento,
    ottieni_piano_ammortamento,
    elimina_piano_ammortamento,
    aggiorna_stato_rata_piano
)

class PianoAmmortamentoDialog:
    def __init__(self, controller):
        self.controller = controller
        # self.controller.page = controller.page # Removed for Flet 0.80 compatibility
        self.loc = controller.loc
        self.id_prestito_corrente = None
        self.rate_correnti = []

        # --- Campi Aggiunta Rata Manuale ---
        self.txt_num_rata = ft.TextField(label="N°", width=50, keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_data_scadenza = ft.TextField(
            label="Scadenza", width=120, read_only=True,
            suffix=ft.IconButton(icon=ft.Icons.CALENDAR_MONTH, on_click=self._apri_date_picker)
        )
        self.txt_importo_rata = ft.TextField(label="Rata Tot.", width=100, keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_quota_capitale = ft.TextField(label="Q. Capitale", width=100, keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_quota_interessi = ft.TextField(label="Q. Interessi", width=100, keyboard_type=ft.KeyboardType.NUMBER)
        self.txt_spese = ft.TextField(label="Spese", width=80, keyboard_type=ft.KeyboardType.NUMBER, value="0")

        # --- Tabella Rate ---
        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("N°", weight="bold")),
                ft.DataColumn(ft.Text("Scadenza", weight="bold")),
                ft.DataColumn(ft.Text("Rata", weight="bold")),
                ft.DataColumn(ft.Text("Capitale", weight="bold")),
                ft.DataColumn(ft.Text("Interessi", weight="bold")),
                ft.DataColumn(ft.Text("Spese", weight="bold")),
                ft.DataColumn(ft.Text("Stato", weight="bold")),
                ft.DataColumn(ft.Text("Azioni", weight="bold")),
            ],
            rows=[]
        )

        self.dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Piano Ammortamento Personalizzato"),
            content=ft.Column([
                ft.Row([
                    ft.ElevatedButton("Scarica Template CSV", icon=ft.Icons.DOWNLOAD, on_click=self._scarica_template),
                    ft.ElevatedButton("Carica da CSV", icon=ft.Icons.UPLOAD, on_click=lambda e: self.controller.pick_files_dialog.pick_files(allow_multiple=False, allowed_extensions=["csv"])),
                ]),
                ft.Divider(),
                ft.Text("Aggiungi Rata Manuale:", weight="bold"),
                ft.Row([
                    self.txt_num_rata, self.txt_data_scadenza, self.txt_importo_rata,
                    self.txt_quota_capitale, self.txt_quota_interessi, self.txt_spese,
                    ft.IconButton(icon=ft.Icons.ADD_CIRCLE, icon_color="green", on_click=self._aggiungi_rata_manuale)
                ], scroll=ft.ScrollMode.ADAPTIVE),
                ft.Divider(),
                ft.Container(
                    content=ft.Column([self.data_table], scroll=ft.ScrollMode.AUTO),
                    height=300, border=ft.border.all(1, "grey"), border_radius=5
                )
            ], width=350, scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.ElevatedButton("Conferma e Torna", on_click=self._chiudi_dialog)
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )

        # Inizializza FilePicker per CSV se non esiste nel controller (lo aggiungeremo dinamicamente se serve, ma meglio usare quello globale se disponibile o crearne uno qui)
        # Nota: AppController ha file_picker generici, ma per semplicità ne uso uno specifico qui se possibile, o uso quello globale.
        # Userò un nuovo FilePicker e lo aggiungerò all'overlay.
        self.file_picker_csv = ft.FilePicker(on_result=self._on_csv_picked)
        # Il dialog deve gestire l'aggiunta del filepicker alla pagina quando si apre, o nel costruttore se la pagina è disponibile.
        if self.controller.page:
            self.controller.page.overlay.append(self.file_picker_csv)
            # Riassegno il pulsante upload per usare questo picker
            self.dialog.content.controls[0].controls[1].on_click = lambda e: self.file_picker_csv.pick_files(allow_multiple=False, allowed_extensions=["csv"])
        
        # DatePicker dedicato per questo dialog (per problemi di Z-order con doppi dialoghi modali)
        self.date_picker = ft.DatePicker(on_change=self._on_date_set, on_dismiss=self._on_date_dismiss)


    
    
    def apri(self, id_prestito=None, temp_list=None, on_save=None):
        self.id_prestito_corrente = id_prestito
        self.on_save_callback = on_save
        
        if id_prestito:
            self.is_memory_mode = False
            self.rate_correnti = ottieni_piano_ammortamento(id_prestito)
        else:
            self.is_memory_mode = True
            # Use the passed list reference so updates are seen by caller
            self.rate_correnti = temp_list if temp_list is not None else []
            
        self._aggiorna_tabella()
        
        # Stima prossimo numero rata
        next_num = len(self.rate_correnti) + 1
        self.txt_num_rata.value = str(next_num)
        self.txt_data_scadenza.value = ""
        self.txt_importo_rata.value = ""
        self.txt_quota_capitale.value = ""
        self.txt_quota_interessi.value = ""
        self.txt_spese.value = "0"

        if self.dialog not in self.controller.page.overlay:
            self.controller.page.overlay.append(self.dialog)
        
        # Assicura che il date picker sia in overlay e DOPO il dialog
        if self.date_picker not in self.controller.page.overlay:
            self.controller.page.overlay.append(self.date_picker)
        else:
            # Se c'è già, muovilo alla fine per sicurezza
            self.controller.page.overlay.remove(self.date_picker)
            self.controller.page.overlay.append(self.date_picker)

        self.dialog.open = True
        self.controller.page.update()

    def _chiudi_dialog(self, e):
        # Chiudiamo esplicitamente il dialog e aggiorniamo per rimuoverlo visivamente
        # PRIMA di chiamare la callback che apre quello nuovo
        self.dialog.open = False
        self.controller.page.update()
        
        if hasattr(self, 'on_save_callback') and self.on_save_callback:
            self.on_save_callback()
    
    def _aggiorna_tabella(self):
        self.data_table.rows.clear()
        # Sort by number for consistency
        self.rate_correnti.sort(key=lambda x: x['numero_rata'])
        
        for i, rata in enumerate(self.rate_correnti):
            # In memory mode, id_rata might be None or missing, use index for deletion
            row_id = rata.get('id_rata') if not self.is_memory_mode else i
            
            self.data_table.rows.append(
                ft.DataRow(cells=[
                    ft.DataCell(ft.Text(str(rata['numero_rata']))),
                    ft.DataCell(ft.Text(rata['data_scadenza'])),
                    ft.DataCell(ft.Text(f"{rata['importo_rata']:.2f} €")),
                    ft.DataCell(ft.Text(f"{rata['quota_capitale']:.2f} €")),
                    ft.DataCell(ft.Text(f"{rata['quota_interessi']:.2f} €")),
                    ft.DataCell(ft.Text(f"{rata['spese_fisse']:.2f} €")),
                    ft.DataCell(
                        ft.Row([
                            ft.Icon(
                                name=ft.Icons.CHECK_CIRCLE if rata['stato'] == 'pagata' else ft.Icons.CIRCLE_OUTLINED,
                                color="green" if rata['stato'] == 'pagata' else "grey",
                                size=20
                            ),
                            ft.Text("Pagata" if rata['stato'] == 'pagata' else "Da pagare"),
                        ], spacing=5)
                        if False else # Fallback if we want just text, but we want interactive
                        ft.TextButton(
                            content=ft.Row([
                                ft.Icon(
                                    name=ft.Icons.CHECK_CIRCLE if rata['stato'] == 'pagata' else ft.Icons.CIRCLE_OUTLINED,
                                    color="green" if rata['stato'] == 'pagata' else "orange"
                                ),
                                ft.Text("Pagata" if rata['stato'] == 'pagata' else "Da pagare")
                            ]),
                            data=row_id,
                            on_click=self._toggle_stato_rata,
                            style=ft.ButtonStyle(padding=5)
                        )
                    ),
                    ft.DataCell(ft.IconButton(
                        icon=ft.Icons.DELETE, 
                        icon_color="red", 
                        data=row_id,
                        on_click=self._elimina_rata_click
                    )) 
                ])
            )
        self.controller.page.update()

    def _aggiungi_rata_manuale(self, e):
        try:
            num = int(self.txt_num_rata.value)
            data = self.txt_data_scadenza.value
            imp = float(self.txt_importo_rata.value.replace(",", "."))
            cap = float(self.txt_quota_capitale.value.replace(",", "."))
            int_ = float(self.txt_quota_interessi.value.replace(",", "."))
            spese = float(self.txt_spese.value.replace(",", "."))

            if not data:
                self.controller.show_snack_bar("Data scadenza obbligatoria", success=False)
                return

            if self.is_memory_mode:
                # Add check for duplicates numbers? For now simple append/replace
                # Remove allow duplicate numbers? Better remove existing with same number if any
                # MODIFY IN PLACE to preserve reference for parent dialog
                ids_to_remove = [i for i, r in enumerate(self.rate_correnti) if r['numero_rata'] == num]
                for i in reversed(ids_to_remove):
                    self.rate_correnti.pop(i)
                
                new_rata = {
                    'numero_rata': num,
                    'data_scadenza': data,
                    'importo_rata': imp,
                    'quota_capitale': cap,
                    'quota_interessi': int_,
                    'spese_fisse': spese,
                    'stato': 'da_pagare'
                }
                self.rate_correnti.append(new_rata)
                self.controller.show_snack_bar("Rata aggiunta (in memoria)", success=True)
                self._aggiorna_tabella()
                self.txt_num_rata.value = str(num + 1)
                self.controller.page.update()
            else:
                success = aggiungi_rata_piano_ammortamento(
                    self.id_prestito_corrente, num, data, imp, cap, int_, spese
                )
                if success:
                    self.controller.show_snack_bar("Rata aggiunta!", success=True)
                    self.rate_correnti = ottieni_piano_ammortamento(self.id_prestito_corrente)
                    self._aggiorna_tabella()
                    self.txt_num_rata.value = str(num + 1)
                    self.controller.page.update()
                else:
                    self.controller.show_snack_bar("Errore aggiunta rata.", success=False)

        except ValueError:
            self.controller.show_snack_bar("Dati non validi (controlla i numeri)", success=False)

    def _scarica_template(self, e):
        filename = "template_piano_ammortamento.csv"
        
        # Percorso dell'asset relativo alla directory assets configurata in ft.app
        # In Flet Web, gli asset sono accessibili tramite URL relativo
        url_template = "/templates/template_piano_ammortamento.csv"

        try:
            if self.controller.page.web:
                # WEB: Lanciamo il download tramite URL dell'asset
                self.controller.page.launch_url(url_template)
                self.controller.show_snack_bar("Download template avviato!", success=True)
            else:
                # DESKTOP: Leggiamo il file locale e usiamo la logica esistente
                import os
                import sys
                
                # Determina il percorso base (stessa logica di main.py)
                if getattr(sys, 'frozen', False):
                    base_path = sys._MEIPASS
                else:
                    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                
                asset_path = os.path.join(base_path, "assets", "templates", filename)
                
                if not os.path.exists(asset_path):
                    self.controller.show_snack_bar("Template non trovato sul server.", success=False)
                    return

                with open(asset_path, "rb") as f:
                    csv_data = f.read()

                from utils.file_downloader import download_file_desktop
                success, result = download_file_desktop(self.controller.page, filename, csv_data)
                
                if success:
                    self.controller.show_snack_bar(f"Template salvato in: {result}", success=True)
                else:
                    self.controller.show_error_dialog(f"Errore download: {result}")

        except Exception as ex:
            print(f"Errore download template: {ex}")
            self.controller.show_error_dialog(f"Errore download: {ex}")

    def _on_csv_picked(self, e: ft.FilePickerResultEvent):
        if not e.files: return
        
        try:
            if self.controller.page.web:
                # In modalità Web, dobbiamo caricare il file sul server prima di leggerlo
                file = e.files[0]
                upload_url = self.controller.page.get_upload_url(file.name, 600)
                
                # Eseguiamo l'upload
                self.file_picker_csv.upload([
                    ft.FilePickerUploadFile(file.name, upload_url=upload_url)
                ])
                
                # Polling semplice finché il file non esiste (soluzione pragmatica per Flet)
                import time
                import os
                upload_path = os.path.join("temp_uploads", file.name)
                
                max_retries = 20
                while not os.path.exists(upload_path) and max_retries > 0:
                    time.sleep(0.5)
                    max_retries -= 1
                
                if not os.path.exists(upload_path):
                    self.controller.show_snack_bar("Errore: Caricamento file non riuscito sul server.", success=False)
                    return
                
                file_path = upload_path
            else:
                # Modalità Desktop
                file_path = e.files[0].path

            temp_rows = []
            count = 0
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f, delimiter=';')
                header = next(reader, None) # Salta header
                
                for row in reader:
                    if len(row) < 5: continue
                    try:
                        num = int(row[0])
                        data = row[1]
                        # Parsing safe per formati europei o US
                        imp = float(row[2].replace(',', '.'))
                        cap = float(row[3].replace(',', '.'))
                        int_ = float(row[4].replace(',', '.'))
                        spese = float(row[5].replace(',', '.')) if len(row) > 5 else 0.0
                        
                        # Parsing intelligente della data
                        stato_rata = 'da_pagare'
                        dt_scad = None
                        
                        formats_to_try = ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y']
                        for fmt in formats_to_try:
                            try:
                                dt_scad = datetime.datetime.strptime(data, fmt).date()
                                # Se parsing ha successo, normalizziamo la stringa data in formato ISO per il DB e sorting corretto
                                data = dt_scad.strftime('%Y-%m-%d')
                                break
                            except ValueError:
                                continue
                        
                        if dt_scad:
                            if dt_scad < datetime.date.today():
                                stato_rata = 'pagata'
                        
                        temp_rows.append({
                            'numero_rata': num,
                            'data_scadenza': data, # Ora è normalizzata (YYYY-MM-DD) se parsing ok, o originale se fallito
                            'importo_rata': imp,
                            'quota_capitale': cap,
                            'quota_interessi': int_,
                            'spese_fisse': spese,
                            'stato': stato_rata
                        })
                        count += 1
                    except Exception as ex:
                        print(f"Skipping row {row}: {ex}")

            if self.is_memory_mode:
                self.rate_correnti.clear()
                self.rate_correnti.extend(temp_rows)
                self.controller.show_snack_bar(f"Importate {count} rate (in memoria).", success=True)
                self._aggiorna_tabella()
            else:
                # DB Mode
                # Pulisci piano esistente? Chiedi conferma? Per ora aggiungiamo in coda o sovrascriviamo se UNIQUE clash
                # Meglio pulire prima se è un import massivo
                elimina_piano_ammortamento(self.id_prestito_corrente)
                for r in temp_rows:
                    aggiungi_rata_piano_ammortamento(
                        self.id_prestito_corrente, r['numero_rata'], r['data_scadenza'], 
                        r['importo_rata'], r['quota_capitale'], r['quota_interessi'], r['spese_fisse']
                    )
                self.controller.show_snack_bar(f"Importate {count} rate con successo.", success=True)
                self.rate_correnti = ottieni_piano_ammortamento(self.id_prestito_corrente)
                self._aggiorna_tabella()
            
        except Exception as ex:
            self.controller.show_error_dialog(f"Errore importazione CSV: {ex}")

    def _apri_date_picker(self, e):
        # Callback already set in __init__
        self.date_picker.open = True
        self.controller.page.update()

    def _on_date_set(self, e):
        if self.date_picker.value:
            self.txt_data_scadenza.value = self.date_picker.value.strftime('%Y-%m-%d')
            self.date_picker.open = False
            self.controller.page.update()

    def _on_date_dismiss(self, e):
        self.date_picker.open = False
        self.controller.page.update()

    def _elimina_rata_click(self, e):
        if self.is_memory_mode:
            try:
                index = int(e.control.data) # Is index in memory mode
                if 0 <= index < len(self.rate_correnti):
                    self.rate_correnti.pop(index)
                    self._aggiorna_tabella()
            except ValueError:
                pass
        else:
            # DB Mode - Not implemented yet in DB but UI supports it now
            # For now just show message as before, or implement easy logic.
            # actually better to just warn.
            self.controller.show_snack_bar("Funzione eliminazione singola non disponibile per prestiti salvati. Ricarica il CSV.", success=False)

    def _toggle_stato_rata(self, e):
        row_id = e.control.data
        
        target_rata = None
        target_index = -1
        
        if self.is_memory_mode:
            try:
                target_index = int(row_id)
                if 0 <= target_index < len(self.rate_correnti):
                    target_rata = self.rate_correnti[target_index]
            except ValueError:
                pass
        else:
            # DB Mode: row_id is id_rata
            for i, r in enumerate(self.rate_correnti):
                if r['id_rata'] == row_id:
                    target_rata = r
                    target_index = i
                    break
        
        if target_rata:
            new_stato = 'da_pagare' if target_rata['stato'] == 'pagata' else 'pagata'
            
            # Update local list
            self.rate_correnti[target_index]['stato'] = new_stato
            
            # Update DB if needed
            if not self.is_memory_mode:
                aggiorna_stato_rata_piano(target_rata['id_rata'], new_stato)
                self.controller.show_snack_bar(f"Stato rata aggiornato a: {new_stato}", success=True)
            
            self._aggiorna_tabella()
