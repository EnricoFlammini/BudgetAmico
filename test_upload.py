
import flet as ft
import os

def main(page: ft.Page):
    page.title = "Test Upload"
    
    def on_result(e: ft.FilePickerResultEvent):
        page.snack_bar = ft.SnackBar(ft.Text(f"File selezionato: {e.files}"))
        page.snack_bar.open = True
        page.update()
        
        if e.files:
            file = e.files[0]
            try:
                upload_url = page.get_upload_url(file.name, 600)
                page.snack_bar = ft.SnackBar(ft.Text(f"URL: {upload_url}"))
                page.snack_bar.open = True
                page.update()
                
                fp.upload([ft.FilePickerUploadFile(file.name, upload_url=upload_url)])
            except Exception as ex:
                page.snack_bar = ft.SnackBar(ft.Text(f"Errore: {ex}"))
                page.snack_bar.open = True
                page.update()

    def on_upload(e: ft.FilePickerUploadEvent):
        page.snack_bar = ft.SnackBar(ft.Text(f"Upload completato: {e.file_name} error={e.error}"))
        page.snack_bar.open = True
        page.update()

    fp = ft.FilePicker(on_result=on_result, on_upload=on_upload)
    page.overlay.append(fp)
    page.add(
        ft.ElevatedButton("Carica File", on_click=lambda _: fp.pick_files())
    )

# ft.app(target=main, upload_dir="uploads")
