
import flet as ft
import os
import asyncio

async def main(page: ft.Page):
    print("[DEBUG TEST] Inizio main test_upload")
    page.title = "Test Upload"
    
    async def on_result(e: ft.FilePickerResultEvent):
        print(f"[DEBUG TEST] on_result triggered! Files: {e.files}")
        page.snack_bar = ft.SnackBar(ft.Text(f"File selezionato: {e.files}"))
        page.snack_bar.open = True
        page.update()
        
        if e.files:
            file = e.files[0]
            try:
                print(f"[DEBUG TEST] Generazione upload URL per {file.name}")
                upload_url = page.get_upload_url(file.name, 600)
                print(f"[DEBUG TEST] URL generato: {upload_url}")
                page.snack_bar = ft.SnackBar(ft.Text(f"URL: {upload_url}"))
                page.snack_bar.open = True
                page.update()
                
                print(f"[DEBUG TEST] Avvio upload...")
                await fp.upload_async([ft.FilePickerUploadFile(file.name, upload_url=upload_url)])
                print(f"[DEBUG TEST] Chiamata upload_async inviata.")
            except Exception as ex:
                print(f"[DEBUG TEST] ERRORE in on_result: {ex}")
                page.snack_bar = ft.SnackBar(ft.Text(f"Errore: {ex}"))
                page.snack_bar.open = True
                page.update()

    async def on_upload(e: ft.FilePickerUploadEvent):
        print(f"[DEBUG TEST] on_upload triggered! File: {e.file_name}, Progress: {e.progress}, Error: {e.error}")
        if e.progress == 1.0:
            page.snack_bar = ft.SnackBar(ft.Text(f"Upload completato: {e.file_name}"))
            page.snack_bar.open = True
            page.update()

    fp = ft.FilePicker(on_result=on_result, on_upload=on_upload)
    page.overlay.append(fp)
    
    async def pick_click(e):
        print("[DEBUG TEST] Click su Carica File")
        await fp.pick_files_async()

    page.add(
        ft.ElevatedButton("Carica File (Async)", on_click=pick_click)
    )
    page.update()
    print("[DEBUG TEST] UI Renderizzata")

# ft.app(target=main, upload_dir="uploads")
