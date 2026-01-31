import flet as ft
import base64

def download_file_web(page: ft.Page, filename: str, content_bytes: bytes, mime_type: str = "application/octet-stream"):
    """
    Triggers a client-side download on Flet Web using JavaScript injection.
    This avoids server-side storage and is more robust against popup blockers than launch_url.
    """
    try:
        b64_data = base64.b64encode(content_bytes).decode('utf-8')
        
        # JavaScript to create a temporary link and click it
        js_code = f"""
        (function() {{
            var element = document.createElement('a');
            element.setAttribute('href', 'data:{mime_type};base64,{b64_data}');
            element.setAttribute('download', '{filename}');
            element.style.display = 'none';
            document.body.appendChild(element);
            element.click();
            document.body.removeChild(element);
        }})();
        """
        
        page.run_js(js_code)
        print(f"[DEBUG] [WEB] Download triggered via JS for {filename}")
        return True
    except Exception as e:
        print(f"[ERROR] [WEB] JS Download failed: {e}")
        return False
