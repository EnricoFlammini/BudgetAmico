import flet as ft
import base64

def download_file_web(page: ft.Page, filename: str, content_bytes: bytes, mime_type: str = "application/octet-stream"):
    """
    Triggers a client-side download on Flet Web using JavaScript injection.
    Handles different Flet version method names for JS execution.
    """
    try:
        print(f"[DEBUG] [WEB] Preparing download for {filename} ({len(content_bytes)} bytes)")
        # Debugging degli attributi disponibili sulla pagina a runtime
        avail_methods = [m for m in dir(page) if not m.startswith("_")]
        print(f"[DEBUG] [WEB] Page object attributes: {avail_methods}")
        
        b64_data = base64.b64encode(content_bytes).decode('utf-8')
        data_uri = f"data:{mime_type};base64,{b64_data}"
        
        # JavaScript to create a temporary link and click it
        js_code = f"""
        (function() {{
            var element = document.createElement('a');
            element.setAttribute('href', '{data_uri}');
            element.setAttribute('download', '{filename}');
            element.style.display = 'none';
            document.body.appendChild(element);
            element.click();
            document.body.removeChild(element);
        }})();
        """
        
        # Try Strategy A: Standard JS execution method names in Flet
        js_methods = ["run_javascript", "run_js", "execute_javascript", "execute_js"]
        for method_name in js_methods:
            if hasattr(page, method_name):
                method = getattr(page, method_name)
                print(f"[DEBUG] [WEB] Found method page.{method_name}. Invoking...")
                method(js_code)
                return True
            
        # Try Strategy B: invoke_method (Low-level Flet call)
        # Some versions use "runJavaScript" or "runJs" via invoke_method
        print(f"[DEBUG] [WEB] Standard methods not found. Trying page.invoke_method...")
        invoke_variants = ["run_javascript", "runJavaScript", "executeJavaScript"]
        for variant in invoke_variants:
            try:
                print(f"[DEBUG] [WEB] Attempting page.invoke_method('{variant}')...")
                page.invoke_method(variant, arguments={"value": js_code})
                # We return True because if this fails, it usually raises an Exception 
                return True
            except Exception as e_invoke:
                print(f"[DEBUG] [WEB] page.invoke_method('{variant}') failed: {e_invoke}")

        # Try Strategy C: fallback via launch_url(javascript:...)
        print(f"[DEBUG] [WEB] invoke_method attempts failed. Trying javascript: url fallback...")
        try:
            # Note: launch_url with javascript: might be blocked or have length limits
            js_launch = f"javascript:{js_code.replace(chr(10), ' ').replace(chr(13), ' ')}"
            page.launch_url(js_launch)
            # No return here, might not have worked
        except Exception as e_js:
            print(f"[DEBUG] [WEB] javascript: fallback failed: {e_js}")
            
        # Strategy D: Direct Data URI Launch (Ultimate Fallback)
        # Note: This often loses the filename in some browsers
        print(f"[DEBUG] [WEB] Falling back to direct Data URI launch (filename might be lost)...")
        
        forced_mime = "application/octet-stream"
        data_uri_forced = f"data:{forced_mime};base64,{b64_data}"
        
        try:
             page.launch_url(data_uri_forced)
             return True
        except Exception as e_launch:
             print(f"[WARNING] [WEB] Data URI launch failed: {e_launch}")
             return False

    except Exception as e:
        print(f"[ERROR] [WEB] Download failed: {e}")
        return False

def download_file_desktop(page: ft.Page, filename: str, content_bytes: bytes):
    """
    Saves a file to the Downloads folder on Desktop and opens the folder.
    Supports Windows, macOS, and Linux.
    """
    import os
    import platform
    import subprocess
    from pathlib import Path

    try:
        # 1. Identifica la cartella Downloads in modo robusto
        # Path.home() / "Downloads" funziona nella maggior parte dei sistemi.
        # Se non esiste (es. lingua diversa), proviamo a creare o usare la home.
        downloads_dir = Path.home() / "Downloads"
        
        # Fallback per sistemi con nomi cartelle localizzati se Downloads non esiste
        if not downloads_dir.exists():
            # Su Linux/macOS a volte è gestito da XDG_DOWNLOAD_DIR
            # In assenza di standard, usiamo la Home come fallback sicuro
            if not os.path.exists(downloads_dir):
                 downloads_dir = Path.home()

        # Assicuriamoci che la directory esista (se Downloads è sparito o troncato)
        os.makedirs(downloads_dir, exist_ok=True)
        
        full_path = downloads_dir / filename
        
        # 2. Scrittura del file
        with open(full_path, "wb") as f:
            f.write(content_bytes)
        
        print(f"[DEBUG] [DESKTOP] File salvato in: {full_path}")
        
        # 3. Apertura della cartella in base al sistema operativo
        current_os = platform.system()
        try:
            if current_os == "Windows":
                os.startfile(downloads_dir)
            elif current_os == "Darwin":  # macOS
                subprocess.run(["open", str(downloads_dir)])
            else:  # Linux e altri POSIX
                # xdg-open è lo standard su Linux (freedesktop)
                subprocess.run(["xdg-open", str(downloads_dir)], check=False)
        except Exception as e_open:
            print(f"[WARNING] [DESKTOP] Impossibile aprire la cartella: {e_open}")
            
        return True, str(full_path)

    except Exception as e:
        print(f"[ERROR] [DESKTOP] Download fallito: {e}")
        return False, str(e)
