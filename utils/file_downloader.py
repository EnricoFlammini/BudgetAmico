import flet as ft
import base64

def download_file_web(page: ft.Page, filename: str, content_bytes: bytes, mime_type: str = "application/octet-stream"):
    """
    Triggers a client-side download on Flet Web using JavaScript injection.
    Handles 'run_js' attribute error for older Flet versions.
    """
    try:
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
        
        # Strategy 1: page.run_js (Newer Flet)
        if hasattr(page, "run_js"):
            print(f"[DEBUG] [WEB] Using page.run_js for {filename}")
            page.run_js(js_code)
            return True
            
        # Strategy 2: Direct Data URI Launch (Fallback for older Flet)
        # We force 'application/octet-stream' to ensure the browser treats it as a download
        # rather than trying to display it (which might be blocked or open in tab).
        print(f"[DEBUG] [WEB] page.run_js not found. Fallback to direct Data URI launch...")
        
        # Re-encode with forced download mime type
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
