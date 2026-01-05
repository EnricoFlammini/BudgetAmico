import os
import markdown
import glob

def convert_docs():
    docs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'docs')
    md_files = glob.glob(os.path.join(docs_dir, "*.md"))
    
    if not md_files:
        print(f"No markdown files found in {docs_dir}")
        return

    css = """
<style>
    body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; line-height: 1.6; padding: 20px; max-width: 800px; margin: 0 auto; color: #333; }
    h1, h2, h3 { color: #2c3e50; margin-top: 24px; margin-bottom: 16px; }
    h1 { border-bottom: 1px solid #eee; padding-bottom: 10px; }
    h2 { border-bottom: 1px solid #eee; padding-bottom: 8px; }
    code { background-color: #f6f8fa; padding: 2px 4px; border-radius: 3px; font-family: monospace; }
    pre { background-color: #f6f8fa; padding: 16px; border-radius: 6px; overflow: auto; }
    blockquote { border-left: 4px solid #dfe2e5; padding-left: 16px; color: #6a737d; margin: 0; }
    table { border-collapse: collapse; width: 100%; margin: 16px 0; }
    th, td { border: 1px solid #dfe2e5; padding: 8px 12px; }
    th { background-color: #f6f8fa; text-align: left; }
    img { max-width: 100%; }
    a { color: #0366d6; text-decoration: none; }
    a:hover { text-decoration: underline; }
</style>
"""

    for md_file in md_files:
        print(f"Converting {os.path.basename(md_file)}...")
        with open(md_file, 'r', encoding='utf-8') as f:
            text = f.read()
            html = markdown.markdown(text, extensions=['tables', 'fenced_code'])
            
            output_file = md_file.replace('.md', '.html')
            
            full_html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{os.path.basename(md_file).replace('.md', '')}</title>
    {css}
</head>
<body>
{html}
</body>
</html>
"""
            with open(output_file, 'w', encoding='utf-8') as out:
                out.write(full_html)
                print(f"Created {os.path.basename(output_file)}")

if __name__ == "__main__":
    try:
        convert_docs()
    except ImportError:
        print("Markdown library not found. Please run 'pip install markdown'")
    except Exception as e:
        print(f"Error: {e}")
