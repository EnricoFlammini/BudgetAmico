import markdown
import os

# HTML Template with some basic CSS for readability
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max_width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f4f4f9;
        }}
        h1, h2, h3 {{ color: #2c3e50; }}
        h1 {{ border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; margin-top: 30px; }}
        code {{ background-color: #e8e8e8; padding: 2px 4px; border-radius: 4px; font-family: monospace; }}
        pre {{ background-color: #f8f9fa; padding: 15px; border-radius: 5px; overflow-x: auto; border: 1px solid #ddd; }}
        blockquote {{ border-left: 4px solid #3498db; margin: 0; padding-left: 15px; color: #555; background-color: #eaf2f8; padding: 10px; border-radius: 4px; }}
        table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #3498db; color: white; }}
        tr:nth-child(even) {{ background-color: #f2f2f2; }}
        a {{ color: #3498db; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        .footer {{ margin-top: 50px; font-size: 0.9em; color: #777; text-align: center; border-top: 1px solid #ddd; padding-top: 20px; }}
    </style>
</head>
<body>
    {content}
</body>
</html>
"""

def convert_md_to_html(filename):
    if not os.path.exists(filename):
        print(f"File not found: {filename}")
        return

    with open(filename, 'r', encoding='utf-8') as f:
        text = f.read()

    # Convert Markdown to HTML
    try:
        html_content = markdown.markdown(text, extensions=['tables', 'fenced_code'])
    except Exception as e:
        print(f"Error converting markdown: {e}")
        return

    # Extract title from first h1
    title = "Budget Amico Docs"
    for line in text.split('\\n'):
        if line.startswith('# '):
            title = line[2:].strip()
            break

    # Fill template
    full_html = HTML_TEMPLATE.format(title=title, content=html_content)

    html_filename = filename.replace('.md', '.html')
    with open(html_filename, 'w', encoding='utf-8') as f:
        f.write(full_html)
    
    print(f"Converted {filename} -> {html_filename}")

if __name__ == "__main__":
    docs_dir = os.path.dirname(os.path.abspath(__file__))
    files = ["Guida_Rapida_Budget_Amico.md", "Manuale_Completo_Budget_Amico.md"]
    
    for f in files:
        convert_md_to_html(os.path.join(docs_dir, f))
