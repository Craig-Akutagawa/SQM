import os
import re

def parse_inline(text):
    # Escape HTML characters first
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    # Restore KaTeX backslash characters after escaping
    # E.g. inline math $SV < 0$ after HTML escape is $SV &lt; 0$. KaTeX auto-render handles this.
    
    # Parse images: ![alt](url) (supporting up to one level of nested parentheses in URL)
    def img_replacer(match):
        alt = match.group(1)
        url = match.group(2)
        url = url.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        if url.startswith('../'):
            url = url[3:]
        return '<img src="{}" alt="{}" class="markdown-image">'.format(url, alt)
        
    text = re.sub(r'!\[([^\]]*)\]\(([^()]*(?:\([^()]*\)[^()]*)*)\)', img_replacer, text)

    # Parse bold: **text**
    text = re.sub(r'\*\*([^\*]+)\*\*', r'<strong>\1</strong>', text)
    
    # Parse code: `code`
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    
    # Parse links: [text](url) (supporting up to one level of nested parentheses in URL)
    text = re.sub(r'\[([^\]]+)\]\(([^()]*(?:\([^()]*\)[^()]*)*)\)', r'<a href="\2">\1</a>', text)
    
    return text

def md_to_html(md_text):
    lines = md_text.split('\n')
    html_lines = []
    
    in_code = False
    in_mermaid = False
    in_bq = False
    in_table = False
    
    bq_type = "alert-note"
    bq_lines = []
    
    # List tracking stack
    list_stack = [] # contains tuples of (indent, type)
    
    for line in lines:
        stripped = line.strip()
        
        # Handle code blocks
        if stripped.startswith("```"):
            # If we are in code block, first close any open lists!
            while list_stack:
                indent, ltype = list_stack.pop()
                html_lines.append("</{}>".format(ltype))
                
            if in_code or in_mermaid:
                if in_mermaid:
                    html_lines.append("</div>")
                    in_mermaid = False
                else:
                    html_lines.append("</code></pre>")
                    in_code = False
            else:
                lang = stripped[3:].strip()
                if lang == "mermaid":
                    html_lines.append('<div class="mermaid">')
                    in_mermaid = True
                else:
                    html_lines.append('<pre><code class="language-{}">'.format(lang if lang else 'text'))
                    in_code = True
            continue
            
        if in_code or in_mermaid:
            if in_code:
                escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
                html_lines.append(escaped)
            else:
                html_lines.append(line)
            continue
            
        # Detect list item
        ul_match = re.match(r'^(\s*)(?:\*|\-)\s+(.*)$', line)
        ol_match = re.match(r'^(\s*)(\d+)\.\s+(.*)$', line)
        
        is_list = False
        ltype = None
        lindent = 0
        lcontent = ""
        
        if ul_match:
            is_list = True
            ltype = "ul"
            lindent = len(ul_match.group(1))
            lcontent = ul_match.group(2)
        elif ol_match:
            is_list = True
            ltype = "ol"
            lindent = len(ol_match.group(1))
            lcontent = ol_match.group(3)
            
        # If not in list, close all open lists
        if not is_list:
            while list_stack:
                indent, stack_type = list_stack.pop()
                html_lines.append("</{}>".format(stack_type))
        else:
            # Handle list levels
            if not list_stack:
                list_stack.append((lindent, ltype))
                html_lines.append("<{}>".format(ltype))
            else:
                top_indent, top_type = list_stack[-1]
                if lindent > top_indent:
                    list_stack.append((lindent, ltype))
                    html_lines.append("<{}>".format(ltype))
                elif lindent < top_indent:
                    while list_stack and list_stack[-1][0] > lindent:
                        _, stack_type = list_stack.pop()
                        html_lines.append("</{}>".format(stack_type))
                    if not list_stack or list_stack[-1][0] < lindent:
                        list_stack.append((lindent, ltype))
                        html_lines.append("<{}>".format(ltype))
                    elif list_stack[-1][0] == lindent and list_stack[-1][1] != ltype:
                        _, stack_type = list_stack.pop()
                        html_lines.append("</{}>".format(stack_type))
                        list_stack.append((lindent, ltype))
                        html_lines.append("<{}>".format(ltype))
                else: # lindent == top_indent
                    if top_type != ltype:
                        _, stack_type = list_stack.pop()
                        html_lines.append("</{}>".format(stack_type))
                        list_stack.append((lindent, ltype))
                        html_lines.append("<{}>".format(ltype))
                        
        # Close blockquote if no longer in blockquote
        if not stripped.startswith(">"):
            if in_bq:
                bq_content = "\n".join(bq_lines)
                bq_html = md_to_html(bq_content)
                html_lines.append('<blockquote class="{}">{}</blockquote>'.format(bq_type, bq_html))
                in_bq = False
                bq_lines = []
                
        # Handle blockquotes
        if stripped.startswith(">"):
            first_line = stripped[1:].strip()
            if not in_bq:
                in_bq = True
                if first_line.startswith("[!NOTE]"):
                    bq_type = "alert-note"
                    bq_lines.append("💡 **Note:** " + first_line[7:].strip())
                elif first_line.startswith("[!TIP]"):
                    bq_type = "alert-tip"
                    bq_lines.append("✨ **Tip:** " + first_line[6:].strip())
                elif first_line.startswith("[!IMPORTANT]") or first_line.startswith("[!WARNING]"):
                    bq_type = "alert-warning"
                    bq_lines.append("⚠️ **Warning:** " + (first_line[12:].strip() if first_line.startswith("[!IMPORTANT]") else first_line[10:].strip()))
                elif first_line.startswith("[!CAUTION]"):
                    bq_type = "alert-caution"
                    bq_lines.append("🚨 **Caution:** " + first_line[10:].strip())
                else:
                    bq_type = "alert-note"
                    bq_lines.append(first_line)
            else:
                bq_lines.append(first_line)
            continue
            
        # Handle Table
        is_table_row = stripped.startswith("|") and stripped.endswith("|")
        if is_table_row:
            if "---" in stripped:
                continue
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            if not in_table:
                html_lines.append("<table>")
                in_table = True
                cell_tags = "".join(["<th>{}</th>".format(parse_inline(c)) for c in cells])
                html_lines.append("<tr>{}</tr>".format(cell_tags))
            else:
                cell_tags = "".join(["<td>{}</td>".format(parse_inline(c)) for c in cells])
                html_lines.append("<tr>{}</tr>".format(cell_tags))
            continue
        else:
            if in_table:
                html_lines.append("</table>")
                in_table = False
                
        # Handle Horizontal Rules
        if re.match(r'^(?:-{3,}|\*{3,}|_{3,})$', stripped):
            html_lines.append("<hr>")
            continue
            
        # Handle Headings
        if stripped.startswith("# "):
            html_lines.append("<h1>{}</h1>".format(parse_inline(stripped[2:])))
        elif stripped.startswith("## "):
            html_lines.append("<h2>{}</h2>".format(parse_inline(stripped[3:])))
        elif stripped.startswith("### "):
            html_lines.append("<h3>{}</h3>".format(parse_inline(stripped[4:])))
        elif stripped.startswith("#### "):
            html_lines.append("<h4>{}</h4>".format(parse_inline(stripped[5:])))
            
        # Handle Lists items
        elif is_list:
            if ltype == "ul":
                if lcontent.startswith("[ ]"):
                    html_lines.append('<li class="checklist-item"><label><input type="checkbox"> {}</label></li>'.format(parse_inline(lcontent[3:].strip())))
                elif lcontent.startswith("[x]") or lcontent.startswith("[X]"):
                    html_lines.append('<li class="checklist-item"><label><input type="checkbox" checked> {}</label></li>'.format(parse_inline(lcontent[3:].strip())))
                else:
                    html_lines.append("<li>{}</li>".format(parse_inline(lcontent)))
            else: # ol
                html_lines.append("<li>{}</li>".format(parse_inline(lcontent)))
                
        else:
            if stripped:
                html_lines.append("<p>{}</p>".format(parse_inline(stripped)))
            else:
                html_lines.append("")
                
    # Close any remaining open tags
    while list_stack:
        _, stack_type = list_stack.pop()
        html_lines.append("</{}>".format(stack_type))
    if in_table:
        html_lines.append("</table>")
    if in_bq:
        bq_content = "\n".join(bq_lines)
        bq_html = md_to_html(bq_content)
        html_lines.append('<blockquote class="{}">{}</blockquote>'.format(bq_type, bq_html))
        
    return "\n".join(html_lines)

file_mapping = {
    "00_课程导读与大纲.md": "index.html",
    "01_第一讲_软件质量与管理概述.md": "01_intro.html",
    "02_第二讲_软件过程的历史演变.md": "02_evolution.html",
    "03_第三讲_团队动力学(PSP,TSP,Scrum).md": "03_dynamics.html",
    "04_第四讲_软件估算、计划与跟踪(PROBE,EVM).md": "04_estimation.html",
    "05_第五讲_软件质量管理与设计验证.md": "05_quality.html",
    "06_第六讲_团队工程开发.md": "06_engineering.html",
    "07_第七讲_项目支持活动(配置管理,度量,决策与根因分析).md": "07_support.html",
    "08_练习题.md": "08_exercises.html",
    "09_2023年期末真题.md": "09_exam_2023.html",
    "10_历年期末真题整理.md": "10_exams_summary.html"
}

def process_all():
    src_dir = os.path.dirname(os.path.abspath(__file__))
    dest_dir = os.path.dirname(src_dir)
    
    files = list(file_mapping.keys())
    
    # Generate sidebar nav HTML
    nav_items_html = ""
    for f in files:
        html_filename = file_mapping[f]
        display_name = f.replace(".md", "").split("_", 1)[-1]
        display_name = display_name.replace("_", " ")
        # Strip parentheses and their content from the sidebar navigation
        display_name = re.sub(r'\(.*?\)|（.*?）', '', display_name).strip()
        nav_items_html += '<a href="{}" class="nav-item" data-filename="{}">{}</a>\n'.format(html_filename, html_filename, display_name)
        
    template = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{TITLE} - 软件质量与管理复习系统</title>
    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
    
    <!-- KaTeX CSS -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.css">
    
    <!-- PrismJS Light Theme (Prism Default) -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/themes/prism.min.css">
    
    <style>
        :root {
            --bg-color: #ffffff;
            --sidebar-bg: #f8fafc;
            --card-bg: #ffffff;
            --border-color: #e2e8f0;
            --text-color: #334155;
            --text-headings: #0f172a;
            --text-muted: #64748b;
            --primary: #4f46e5;
            --primary-light: #eef2ff;
            --primary-gradient: linear-gradient(135deg, #6366f1, #4f46e5);
            --accent: #a855f7;
            --accent-green-bg: #f0fdf4;
            --accent-green-border: #16a34a;
            --accent-green-text: #15803d;
            --accent-blue-bg: #f0f9ff;
            --accent-blue-border: #0284c7;
            --accent-blue-text: #0369a1;
            --accent-yellow-bg: #fefce8;
            --accent-yellow-border: #ca8a04;
            --accent-yellow-text: #a16207;
            --accent-red-bg: #fef2f2;
            --accent-red-border: #dc2626;
            --accent-red-text: #b91c1c;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }

        body {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.8;
            display: flex;
            min-height: 100vh;
            overflow-x: hidden;
        }

        /* Scrollbar customization */
        ::-webkit-scrollbar {
            width: 8px;
            height: 8px;
        }
        ::-webkit-scrollbar-track {
            background: #f1f5f9;
        }
        ::-webkit-scrollbar-thumb {
            background: #cbd5e1;
            border-radius: 4px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: #94a3b8;
        }

        /* Layout */
        .sidebar {
            width: 320px;
            height: 100vh;
            background-color: var(--sidebar-bg);
            border-right: 1px solid var(--border-color);
            padding: 2rem 1.5rem;
            position: fixed;
            left: 0;
            top: 0;
            overflow-y: auto;
            z-index: 100;
            display: flex;
            flex-direction: column;
            gap: 1.5rem;
            transition: transform 0.3s ease;
        }

        .logo-area {
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-headings);
            margin-bottom: 1rem;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .logo-area::before {
            content: "🛡️";
        }

        .nav-links {
            display: flex;
            flex-direction: column;
            gap: 0.4rem;
        }

        .nav-item {
            color: var(--text-muted);
            text-decoration: none;
            padding: 0.7rem 0.9rem;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 500;
            transition: all 0.2s ease;
            border: 1px solid transparent;
        }

        .nav-item:hover {
            background-color: rgba(79, 70, 229, 0.05);
            color: var(--primary);
        }

        .nav-item.active {
            background-color: var(--primary-light);
            color: var(--primary);
            font-weight: 600;
            border-color: rgba(79, 70, 229, 0.15);
        }

        .main-container {
            margin-left: 320px;
            width: calc(100% - 320px);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            background-color: #ffffff;
        }

        /* Top Progress & Header */
        header {
            position: sticky;
            top: 0;
            height: 65px;
            background: rgba(255, 255, 255, 0.85);
            backdrop-filter: blur(12px);
            border-bottom: 1px solid var(--border-color);
            z-index: 90;
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 2rem;
        }

        .scroll-progress-container {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 4px;
            background: transparent;
        }

        .scroll-progress-bar {
            height: 100%;
            width: 0%;
            background: var(--primary-gradient);
            transition: width 0.1s ease;
        }

        .header-title {
            font-weight: 500;
            font-size: 1rem;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .header-title .current-page {
            color: var(--text-headings);
            font-weight: 700;
        }

        .mobile-toggle {
            display: none;
            background: none;
            border: none;
            color: var(--text-headings);
            font-size: 1.5rem;
            cursor: pointer;
        }

        .content-area {
            flex-grow: 1;
            padding: 3rem 4rem;
            max-width: 960px;
            width: 100%;
            margin: 0 auto;
        }

        /* Markdown Rendering Styles (Github-style Light Theme) */
        .rendered-markdown {
            font-size: 1.075rem;
        }

        /* Markdown Image Styling */
        .rendered-markdown img {
            max-width: 100%;
            height: auto;
            border-radius: 8px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
            margin: 1.5rem 0;
            display: block;
            border: 1px solid var(--border-color);
        }

        .rendered-markdown h1 {
            font-size: 2.2rem;
            font-weight: 800;
            margin-bottom: 1.5rem;
            color: var(--text-headings);
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.6rem;
        }

        .rendered-markdown hr {
            border: none;
            border-top: 1.5px solid var(--border-color);
            margin: 2.2rem 0;
        }

        .rendered-markdown h2 {
            font-size: 1.5rem;
            font-weight: 700;
            margin-top: 2.5rem;
            margin-bottom: 1.1rem;
            color: var(--text-headings);
            border-left: 4px solid var(--primary);
            padding-left: 0.75rem;
        }

        .rendered-markdown h3 {
            font-size: 1.2rem;
            font-weight: 600;
            margin-top: 1.8rem;
            margin-bottom: 0.8rem;
            color: #1e1b4b;
        }

        .rendered-markdown p {
            margin-bottom: 1.25rem;
        }

        .rendered-markdown ul, .rendered-markdown ol {
            margin-bottom: 1.5rem;
            padding-left: 1.75rem;
        }

        .rendered-markdown li {
            margin-bottom: 0.5rem;
        }

        /* Code Block Styling - Light GitHub Style */
        .rendered-markdown pre {
            background-color: #f8fafc !important;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.1rem !important;
            margin-bottom: 1.5rem;
            overflow-x: auto;
        }

        .rendered-markdown code {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9em;
            background-color: #f1f5f9;
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            color: #dc2626; /* clear readable red code */
        }

        .rendered-markdown pre code {
            background-color: transparent;
            padding: 0;
            color: #1e293b;
        }

        /* Enhanced Alerts */
        .rendered-markdown blockquote {
            padding: 1rem 1.5rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
            border-left: 4px solid;
            background-color: var(--accent-blue-bg);
            border-color: var(--accent-blue-border);
            color: var(--accent-blue-text);
        }

        .rendered-markdown blockquote p {
            margin-bottom: 0;
            color: inherit;
        }

        /* Support github alerts explicitly */
        .rendered-markdown blockquote.alert-note {
            background-color: var(--accent-blue-bg);
            border-color: var(--accent-blue-border);
            color: var(--accent-blue-text);
        }
        .rendered-markdown blockquote.alert-tip {
            background-color: var(--accent-green-bg);
            border-color: var(--accent-green-border);
            color: var(--accent-green-text);
        }
        .rendered-markdown blockquote.alert-warning,
        .rendered-markdown blockquote.alert-caution {
            background-color: var(--accent-yellow-bg);
            border-color: var(--accent-yellow-border);
            color: var(--accent-yellow-text);
        }

        /* Tables styling */
        .rendered-markdown table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 2rem;
            background-color: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid var(--border-color);
        }

        .rendered-markdown th, .rendered-markdown td {
            padding: 0.85rem 1.1rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }

        .rendered-markdown th {
            background-color: #f1f5f9;
            font-weight: 600;
            color: var(--text-headings);
        }

        .rendered-markdown tr:last-child td {
            border-bottom: none;
        }

        /* Interactive Quiz Card Styles - High legibility light mode */
        .quiz-answer-container {
            margin-top: 0.5rem;
            margin-bottom: 1.5rem;
            border-radius: 8px;
            overflow: hidden;
            border: 1px solid #cbd5e1;
            background: #f8fafc;
        }

        .btn-toggle-answer {
            width: 100%;
            background: #eef2ff;
            border: none;
            color: var(--primary);
            padding: 0.75rem 1.25rem;
            font-size: 0.95rem;
            font-weight: 600;
            text-align: left;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: all 0.2s ease;
        }

        .btn-toggle-answer:hover {
            background: #e0e7ff;
            color: var(--primary);
        }

        .btn-toggle-answer.active {
            background: #eef2ff;
            color: var(--primary);
            border-bottom: 1px solid #cbd5e1;
        }

        .quiz-answer-content {
            padding: 1.25rem 1.5rem;
            background: #ffffff;
            animation: fadeIn 0.2s ease;
            border-left: 4px solid var(--accent-green-border);
        }

        .quiz-answer-content p {
            margin-bottom: 0.75rem;
            color: #334155;
        }
        
        .quiz-answer-content p:last-child {
            margin-bottom: 0;
        }

        .quiz-answer-content strong {
            color: var(--accent-green-text);
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(-3px); }
            to { opacity: 1; transform: translateY(0); }
        }

        /* Mermaid diagram styling */
        .mermaid {
            background: #f8fafc;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 1.5rem;
            margin-bottom: 1.8rem;
            display: flex;
            justify-content: center;
        }

        @media (max-width: 960px) {
            .sidebar {
                transform: translateX(-100%);
            }
            .sidebar.open {
                transform: translateX(0);
            }
            .main-container {
                margin-left: 0;
                width: 100%;
            }
            header {
                padding: 0 1.5rem;
            }
            .mobile-toggle {
                display: block;
            }
            .content-area {
                padding: 2rem 1.5rem;
            }
        }
        
        
        /* Checklist styling */
        .rendered-markdown ul:has(.checklist-item) {
            list-style-type: none;
            padding-left: 0;
        }
        .checklist-item {
            list-style: none;
            margin-bottom: 0.6rem;
            position: relative;
            padding-left: 1.8rem;
        }
        .checklist-item label {
            cursor: pointer;
            font-size: 1.025rem;
            color: var(--text-color);
            transition: color 0.2s ease;
            display: inline;
        }
        .checklist-item input[type="checkbox"] {
            position: absolute;
            left: 0;
            top: 0.25rem;
            appearance: none;
            -webkit-appearance: none;
            width: 1.2rem;
            height: 1.2rem;
            border: 2px solid #cbd5e1;
            border-radius: 4px;
            outline: none;
            cursor: pointer;
            display: grid;
            place-content: center;
            transition: all 0.2s ease;
            background-color: #fff;
        }
        .checklist-item input[type="checkbox"]::before {
            content: "";
            width: 0.65rem;
            height: 0.65rem;
            transform: scale(0);
            transition: 120ms transform ease-in-out;
            box-shadow: inset 1em 1em var(--primary);
            transform-origin: bottom left;
            clip-path: polygon(14% 44%, 0 65%, 50% 100%, 100% 16%, 80% 0%, 43% 62%);
        }
        .checklist-item input[type="checkbox"]:checked {
            border-color: var(--primary);
            background-color: var(--primary-light);
        }
        .checklist-item input[type="checkbox"]:checked::before {
            transform: scale(1);
        }
        .checklist-item label:has(input:checked) {
            color: var(--text-muted);
            text-decoration: line-through;
        }

        /* Dynamic Tab Layout */
        .tab-container {
            display: flex;
            gap: 1rem;
            margin-bottom: 2rem;
            border-bottom: 2px solid var(--border-color);
            padding-bottom: 0.5rem;
        }
        .tab-button {
            padding: 0.75rem 1.5rem;
            font-size: 1rem;
            font-weight: 600;
            color: var(--text-muted);
            background: none;
            border: none;
            cursor: pointer;
            transition: all 0.2s ease;
            position: relative;
        }
        .tab-button:hover {
            color: var(--primary);
        }
        .tab-button.active {
            color: var(--primary);
        }
        .tab-button.active::after {
            content: "";
            position: absolute;
            bottom: -0.6rem;
            left: 0;
            width: 100%;
            height: 3px;
            background: var(--primary-gradient);
            border-radius: 9999px;
        }

        /* Practice Dashboard Card */
        .progress-dashboard {
            background: linear-gradient(135deg, #f8fafc, #eff6ff);
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.5rem 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.05);
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1.5rem;
        }
        .dashboard-info {
            display: flex;
            gap: 2.5rem;
            flex-grow: 1;
        }
        .dashboard-stat-box {
            display: flex;
            flex-direction: column;
            gap: 0.25rem;
        }
        .dashboard-stat-label {
            font-size: 0.875rem;
            color: var(--text-muted);
            font-weight: 500;
        }
        .dashboard-stat-value {
            font-size: 1.5rem;
            font-weight: 700;
            color: var(--text-headings);
        }
        .dashboard-progress-container {
            width: 150px;
            height: 8px;
            background: #e2e8f0;
            border-radius: 9999px;
            overflow: hidden;
            margin-top: 0.5rem;
        }
        .dashboard-progress-bar {
            height: 100%;
            width: 0%;
            background: var(--primary-gradient);
            transition: width 0.3s ease;
        }
        .reset-all-btn {
            background: #ffffff;
            color: var(--accent-red-text);
            border: 1px solid var(--accent-red-border);
            padding: 0.6rem 1.2rem;
            border-radius: 8px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .reset-all-btn:hover {
            background: var(--accent-red-bg);
        }

        /* Interactive Quiz Card */
        .quiz-card {
            background: #ffffff;
            border: 1px solid var(--border-color);
            border-radius: 16px;
            padding: 1.75rem 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.05);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }
        .quiz-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.05);
        }
        .quiz-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.25rem;
        }
        .quiz-type-badge {
            font-size: 0.75rem;
            font-weight: 700;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            background: var(--primary-light);
            color: var(--primary);
            border: 1px solid rgba(79, 70, 229, 0.15);
        }
        .quiz-type-badge.badge-multi {
            background: #faf5ff;
            color: var(--accent);
            border-color: rgba(168, 85, 247, 0.15);
        }
        .quiz-number {
            font-size: 0.875rem;
            font-weight: 600;
            color: var(--text-muted);
        }
        .quiz-question-text {
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--text-headings);
            margin-bottom: 1.5rem;
            line-height: 1.6;
        }
        .quiz-options-list {
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
            margin-bottom: 1.5rem;
            list-style: none;
            padding-left: 0;
        }
        .quiz-option-item {
            background: #ffffff;
            border: 1.5px solid var(--border-color);
            border-radius: 12px;
            padding: 0.85rem 1.25rem;
            cursor: pointer;
            display: flex;
            align-items: center;
            gap: 1rem;
            transition: all 0.2s ease;
            user-select: none;
        }
        .quiz-option-item:hover {
            border-color: var(--primary);
            background-color: var(--primary-light);
        }
        .quiz-option-item.selected {
            border-color: var(--primary);
            background-color: var(--primary-light);
            font-weight: 600;
        }
        .option-letter-circle {
            width: 1.75rem;
            height: 1.75rem;
            border-radius: 9999px;
            background: #f1f5f9;
            color: var(--text-color);
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            font-size: 0.875rem;
            transition: all 0.2s ease;
        }
        .quiz-option-item:hover .option-letter-circle {
            background: var(--primary);
            color: #ffffff;
        }
        .quiz-option-item.selected .option-letter-circle {
            background: var(--primary);
            color: #ffffff;
        }
        
        /* Submission States styling */
        .quiz-option-item.correct-choice {
            border-color: var(--accent-green-border);
            background-color: var(--accent-green-bg);
        }
        .quiz-option-item.correct-choice .option-letter-circle {
            background: var(--accent-green-border);
            color: #ffffff;
        }
        .quiz-option-item.incorrect-choice {
            border-color: var(--accent-red-border);
            background-color: var(--accent-red-bg);
        }
        .quiz-option-item.incorrect-choice .option-letter-circle {
            background: var(--accent-red-border);
            color: #ffffff;
        }
        .quiz-option-item.missed-correct {
            border: 2px dashed var(--accent-green-border);
        }
        .quiz-option-item.disabled {
            pointer-events: none;
        }

        /* Quiz Action Buttons */
        .quiz-actions {
            display: flex;
            gap: 1rem;
            align-items: center;
        }
        .quiz-submit-btn {
            background: var(--primary-gradient);
            color: #ffffff;
            border: none;
            padding: 0.7rem 1.5rem;
            font-size: 0.95rem;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            box-shadow: 0 4px 6px -1px rgba(79, 70, 229, 0.2);
        }
        .quiz-submit-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 15px -3px rgba(79, 70, 229, 0.3);
        }
        .quiz-submit-btn:disabled {
            background: #cbd5e1;
            box-shadow: none;
            color: #94a3b8;
            cursor: not-allowed;
            transform: none;
        }
        .quiz-reset-btn {
            background: #ffffff;
            color: var(--text-color);
            border: 1px solid var(--border-color);
            padding: 0.7rem 1.5rem;
            font-size: 0.95rem;
            font-weight: 600;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .quiz-reset-btn:hover {
            background: #f1f5f9;
        }

        /* Result Panel */
        .quiz-result-panel {
            margin-top: 1.5rem;
            border-top: 1px solid var(--border-color);
            padding-top: 1.5rem;
            animation: slideDown 0.3s ease-out;
        }
        @keyframes slideDown {
            from { opacity: 0; transform: translateY(-5px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .result-alert-box {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            padding: 0.85rem 1.25rem;
            border-radius: 8px;
            font-weight: 700;
            font-size: 1rem;
            margin-bottom: 1.25rem;
        }
        .result-alert-box.alert-correct {
            background-color: var(--accent-green-bg);
            color: var(--accent-green-text);
            border: 1px solid var(--accent-green-border);
        }
        .result-alert-box.alert-incorrect {
            background-color: var(--accent-red-bg);
            color: var(--accent-red-text);
            border: 1px solid var(--accent-red-border);
        }
        .result-alert-box.alert-submitted {
            background-color: var(--primary-light);
            color: var(--primary);
            border: 1.5px solid var(--primary);
        }
        .quiz-correct-answer-text {
            font-size: 1rem;
            color: var(--text-headings);
            font-weight: 600;
            margin-bottom: 0.75rem;
        }
        .quiz-explanation-panel {
            background-color: #f8fafc;
            border-left: 4px solid var(--primary);
            border-radius: 0 8px 8px 0;
            padding: 1.1rem 1.5rem;
            color: var(--text-color);
            font-size: 0.95rem;
            line-height: 1.7;
        }
        .explanation-title-box {
            font-weight: 700;
            color: var(--text-headings);
            margin-bottom: 0.4rem;
        }

        /* Subjective Answer Hideable panel */
        .subjective-answer-wrapper {
            margin: 1.5rem 0;
            border: 1px solid var(--border-color);
            border-radius: 12px;
            overflow: hidden;
        }
        .subjective-toggle-btn {
            width: 100%;
            background: #f8fafc;
            border: none;
            color: var(--primary);
            padding: 0.75rem 1.25rem;
            font-size: 0.95rem;
            font-weight: 600;
            text-align: left;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: space-between;
            transition: all 0.2s ease;
        }
        .subjective-toggle-btn:hover {
            background: var(--primary-light);
        }
        .subjective-answer-content {
            padding: 1.25rem 1.5rem;
            background: #ffffff;
            border-top: 1px solid var(--border-color);
            animation: fadeIn 0.2s ease;
        }
    </style>
</head>
<body>

    <!-- Sidebar Navigation -->
    <div class="sidebar" id="sidebar">
        <div class="logo-area">质量与管理复习</div>
        <div class="nav-links">
            {NAV_ITEMS}
        </div>
    </div>

    <!-- Main Container -->
    <div class="main-container">
        <!-- Scroll Progress & Top Header -->
        <header>
            <button class="mobile-toggle" id="mobile-toggle">☰</button>
            <div class="header-title">
                软件质量与管理 / <span class="current-page" id="current-page-title">Loading...</span>
            </div>
            <div class="scroll-progress-container">
                <div class="scroll-progress-bar" id="progress-bar"></div>
            </div>
        </header>

        <!-- Content Area -->
        <div class="content-area">
            <div class="rendered-markdown" id="markdown-rendered">
                <!-- Rendered HTML goes here directly -->
                {HTML_CONTENT}
            </div>
        </div>
    </div>

    <!-- KaTeX JS & auto-render -->
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/katex.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/katex@0.16.8/dist/contrib/auto-render.min.js"></script>

    <!-- Mermaid JS -->
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>

    <!-- PrismJS -->
    <script src="https://cdn.jsdelivr.net/npm/prismjs@1.29.0/prism.min.js"></script>

    <script>
        // Set current page global variables
        const currentPath = window.location.pathname;
        let currentFile = 'index.html';
        try {
            currentFile = decodeURIComponent(currentPath.substring(currentPath.lastIndexOf('/') + 1)) || 'index.html';
        } catch(e) {
            currentFile = currentPath.substring(currentPath.lastIndexOf('/') + 1) || 'index.html';
        }
        const storageKey = 'quiz_answers_' + currentFile;

        document.addEventListener("DOMContentLoaded", function() {
            // Mobile toggle logic
            const sidebar = document.getElementById('sidebar');
            const toggle = document.getElementById('mobile-toggle');
            toggle.addEventListener('click', (e) => {
                sidebar.classList.toggle('open');
                e.stopPropagation();
            });
            document.addEventListener('click', (e) => {
                if (!sidebar.contains(e.target) && sidebar.classList.contains('open')) {
                    sidebar.classList.remove('open');
                }
            });

            // Set current page active in sidebar
            const navItems = document.querySelectorAll('.nav-item');
            
            let currentTitleText = "首页";
            navItems.forEach(item => {
                const targetFilename = item.getAttribute('data-filename');
                if (currentFile === targetFilename || (currentFile === '' && targetFilename === 'index.html')) {
                    item.classList.add('active');
                    currentTitleText = item.textContent;
                }
            });
            document.getElementById('current-page-title').textContent = currentTitleText;

            // Scroll Progress
            window.addEventListener('scroll', () => {
                const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
                const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
                const scrolled = (winScroll / height) * 100;
                document.getElementById('progress-bar').style.width = scrolled + '%';
            });

            // Initialize and run Mermaid
            mermaid.initialize({ startOnLoad: true, theme: 'neutral' });

            // Render Math with KaTeX
            renderMathInElement(document.getElementById('markdown-rendered'), {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '$', right: '$', display: false},
                    {left: '\\\\(', right: '\\\\)', display: false},
                    {left: '\\\\[', right: '\\\\]', display: true}
                ],
                throwOnError : false
            });

            // Highlight code blocks
            Prism.highlightAllUnder(document.getElementById('markdown-rendered'));

            // Format Interactive Quizzes
            formatInteractiveQuizzes();

            // Persist checkbox state
            const checkboxes = document.querySelectorAll('.checklist-item input[type="checkbox"]');
            const pageKey = 'checklist_' + currentFile;
            
            // Load saved states
            let savedStates = {};
            try {
                savedStates = JSON.parse(localStorage.getItem(pageKey)) || {};
            } catch(e) {
                console.error(e);
            }
            
            checkboxes.forEach((chk, idx) => {
                // Set initial state
                if (savedStates[idx] !== undefined) {
                    chk.checked = savedStates[idx];
                }
                
                // Add event listener to save state
                chk.addEventListener('change', () => {
                    savedStates[idx] = chk.checked;
                    localStorage.setItem(pageKey, JSON.stringify(savedStates));
                });
            });
        });
        
        function loadAllSavedAnswers() {
            try {
                return JSON.parse(localStorage.getItem(storageKey)) || {};
            } catch(e) {
                return {};
            }
        }
        
        function loadUserAnswer(idx) {
            const data = loadAllSavedAnswers();
            return data[idx] || null;
        }
        
        function saveUserAnswer(idx, selected, isCorrect) {
            const data = loadAllSavedAnswers();
            data[idx] = { selected, isCorrect };
            localStorage.setItem(storageKey, JSON.stringify(data));
        }
        
        function deleteUserAnswer(idx) {
            const data = loadAllSavedAnswers();
            delete data[idx];
            localStorage.setItem(storageKey, JSON.stringify(data));
        }
        
        function formatSubjectiveAnswers() {
            const uls = Array.from(document.querySelectorAll('.rendered-markdown ul'));
            uls.forEach(ul => {
                const lis = Array.from(ul.children);
                if (lis.length > 0 && lis[0].textContent.includes('参考答案')) {
                    const wrapper = document.createElement('div');
                    wrapper.className = 'subjective-answer-wrapper';
                    
                    const btn = document.createElement('button');
                    btn.className = 'subjective-toggle-btn';
                    btn.innerHTML = '<span>👁️ 显示参考答案</span> <span>▼</span>';
                    
                    const contentDiv = document.createElement('div');
                    contentDiv.className = 'subjective-answer-content';
                    contentDiv.style.display = 'none';
                    
                    ul.parentNode.insertBefore(wrapper, ul);
                    contentDiv.appendChild(ul);
                    
                    let nextEl = wrapper.nextSibling;
                    while (nextEl) {
                        if (nextEl.nodeType === 1) {
                            const tagName = nextEl.tagName;
                            if (tagName.startsWith('H') || tagName === 'HR' || nextEl.classList.contains('quiz-card') || nextEl.classList.contains('subjective-answer-wrapper')) {
                                break;
                            }
                        }
                        const toMove = nextEl;
                        nextEl = nextEl.nextSibling;
                        contentDiv.appendChild(toMove);
                    }
                    
                    wrapper.appendChild(btn);
                    wrapper.appendChild(contentDiv);
                    
                    btn.addEventListener('click', () => {
                        const isHidden = contentDiv.style.display === 'none';
                        if (isHidden) {
                            contentDiv.style.display = 'block';
                            btn.children[0].innerHTML = '🙈 隐藏参考答案';
                            btn.children[1].textContent = '▲';
                        } else {
                            contentDiv.style.display = 'none';
                            btn.children[0].innerHTML = '👁️ 显示参考答案';
                            btn.children[1].textContent = '▼';
                        }
                    });
                }
            });
        }
        
        function initDashboardAndTabs(totalQuizzes) {
            const isTargetPage = currentFile === '09_exam_2023.html' || currentFile === '08_exercises.html';
            const hasTabs = currentFile === '09_exam_2023.html';
            
            if (isTargetPage) {
                const container = document.getElementById('markdown-rendered');
                
                if (hasTabs) {
                    const children = Array.from(container.children);
                    
                    let part1Elements = [];
                    let part2Elements = [];
                    let currentPart = 0;
                    
                    children.forEach(el => {
                        if (el.tagName === 'H2' && el.textContent.includes('第一部分')) {
                            currentPart = 1;
                            part1Elements.push(el);
                        } else if (el.tagName === 'H2' && el.textContent.includes('第二部分')) {
                            currentPart = 2;
                            part2Elements.push(el);
                        } else if (el.tagName === 'H1') {
                            // Keep h1
                        } else if (el.tagName === 'UL' && el.querySelector('.checklist-item')) {
                            // Keep checklist
                        } else if (el.tagName === 'HR' && currentPart === 0) {
                            // Keep hr
                        } else {
                            if (currentPart === 1) {
                                part1Elements.push(el);
                            } else if (currentPart === 2) {
                                part2Elements.push(el);
                            }
                        }
                    });
                    
                    const panel1 = document.createElement('div');
                    panel1.id = 'tab-panel-realexam';
                    panel1.className = 'tab-content-panel';
                    
                    const panel2 = document.createElement('div');
                    panel2.id = 'tab-panel-inclass';
                    panel2.className = 'tab-content-panel';
                    panel2.style.display = 'none';
                    
                    part1Elements.forEach(el => panel1.appendChild(el));
                    part2Elements.forEach(el => panel2.appendChild(el));
                    
                    const tabContainer = document.createElement('div');
                    tabContainer.className = 'tab-container';
                    tabContainer.innerHTML = `
                        <button class="tab-button active" id="btn-tab-realexam">📝 第一部分：不定项选择题 (共15题)</button>
                        <button class="tab-button" id="btn-tab-inclass">✏️ 第二部分：主观简答题 (共7题)</button>
                    `;
                    
                    const dashboard = createDashboardHTML();
                    
                    const h1 = container.querySelector('h1');
                    if (h1) {
                        h1.parentNode.insertBefore(dashboard, h1.nextSibling);
                    } else {
                        container.insertBefore(dashboard, container.firstChild);
                    }
                    dashboard.parentNode.insertBefore(tabContainer, dashboard.nextSibling);
                    tabContainer.parentNode.insertBefore(panel1, tabContainer.nextSibling);
                    panel1.parentNode.insertBefore(panel2, panel1.nextSibling);
                    
                    const btn1 = document.getElementById('btn-tab-realexam');
                    const btn2 = document.getElementById('btn-tab-inclass');
                    
                    btn1.addEventListener('click', () => {
                        btn1.classList.add('active');
                        btn2.classList.remove('active');
                        panel1.style.display = 'block';
                        panel2.style.display = 'none';
                    });
                    
                    btn2.addEventListener('click', () => {
                        btn1.classList.remove('active');
                        btn2.classList.add('active');
                        panel1.style.display = 'none';
                        panel2.style.display = 'block';
                    });
                } else {
                    const dashboard = createDashboardHTML();
                    const listEl = container.querySelector('ul');
                    if (listEl) {
                        listEl.parentNode.insertBefore(dashboard, listEl.nextSibling);
                    } else {
                        container.insertBefore(dashboard, container.firstChild);
                    }
                }
                
                document.getElementById('dash-reset-all').addEventListener('click', () => {
                    if (confirm('确认要重置本页所有选择题练习记录吗？这会清除所有已保存的选择记录。')) {
                        localStorage.removeItem(storageKey);
                        window.location.reload();
                    }
                });
                
                window.totalQuizzesCount = totalQuizzes;
                updateDashboard();
            }
        }
        
        function createDashboardHTML() {
            const dashboard = document.createElement('div');
            dashboard.className = 'progress-dashboard';
            dashboard.innerHTML = `
                <div class="dashboard-info">
                    <div class="dashboard-stat-box" style="flex: 1;">
                        <span class="dashboard-stat-label">练习进度</span>
                        <span class="dashboard-stat-value" id="dash-progress-text">0 / 0</span>
                        <div class="dashboard-progress-container">
                            <div class="dashboard-progress-bar" id="dash-progress-bar"></div>
                        </div>
                    </div>
                </div>
                <button class="reset-all-btn" id="dash-reset-all">🧹 重置本页所有练习记录</button>
            `;
            return dashboard;
        }
        
        function updateDashboard() {
            const isTargetPage = currentFile === '09_exam_2023.html' || currentFile === '08_exercises.html';
            if (isTargetPage && window.totalQuizzesCount !== undefined) {
                const savedAnswers = loadAllSavedAnswers();
                const total = window.totalQuizzesCount;
                const completed = Object.keys(savedAnswers).length;
                const progressPercent = total > 0 ? (completed / total) * 100 : 0;
                
                const progressTextEl = document.getElementById('dash-progress-text');
                const progressBarEl = document.getElementById('dash-progress-bar');
                if (progressTextEl) progressTextEl.textContent = `${completed} / ${total} 题`;
                if (progressBarEl) progressBarEl.style.width = `${progressPercent}%`;
            }
        }

        function formatInteractiveQuizzes() {
            const uls = Array.from(document.querySelectorAll('.rendered-markdown ul'));
            let quizIndex = 0;
            
            uls.forEach(ul => {
                if (ul.querySelector('.checklist-item')) return;
                
                const lis = Array.from(ul.children);
                let optItems = [];
                
                lis.forEach(li => {
                    const text = li.textContent.trim();
                    if (/^[A-G][.．、\\s]/i.test(text)) {
                        optItems.push(li);
                    }
                });
                
                if (optItems.length >= 2) {
                    const currentQuizIdx = quizIndex++;
                    
                    let prevHeading = ul.previousElementSibling;
                    while (prevHeading && !/^H[1-6]$/i.test(prevHeading.tagName)) {
                        prevHeading = prevHeading.previousElementSibling;
                    }
                    
                    const questionText = prevHeading ? prevHeading.innerHTML : "练习题";
                    
                    const optionsData = optItems.map(opt => {
                        const text = opt.textContent.trim();
                        const letterMatch = text.match(/^([A-G])[.．、\\s]\\s*(.*)$/i);
                        const letter = letterMatch ? letterMatch[1].toUpperCase() : '';
                        const desc = letterMatch ? letterMatch[2] : text;
                        return { letter, desc, originalHTML: opt.innerHTML };
                    });
                    
                    const card = document.createElement('div');
                    card.className = 'quiz-card';
                    card.setAttribute('data-quiz-index', currentQuizIdx);
                    card.setAttribute('data-page', currentFile);
                    
                    const qHeader = document.createElement('div');
                    qHeader.className = 'quiz-header';
                    qHeader.innerHTML = `
                        <span class="quiz-number">第 ${currentQuizIdx + 1} 题</span>
                        <span class="quiz-type-badge">练习题</span>
                    `;
                    card.appendChild(qHeader);
                    
                    const qQuestion = document.createElement('div');
                    qQuestion.className = 'quiz-question-text';
                    qQuestion.innerHTML = questionText;
                    card.appendChild(qQuestion);
                    
                    const qOptsList = document.createElement('ul');
                    qOptsList.className = 'quiz-options-list';
                    
                    optionsData.forEach(opt => {
                        const optLi = document.createElement('li');
                        optLi.className = 'quiz-option-item';
                        optLi.setAttribute('data-letter', opt.letter);
                        optLi.innerHTML = `
                            <span class="option-letter-circle">${opt.letter}</span>
                            <span class="option-desc">${opt.desc}</span>
                        `;
                        
                        optLi.addEventListener('click', () => {
                            if (card.classList.contains('submitted')) return;
                            
                            // Allow toggling multiple options by default for flexibility
                            optLi.classList.toggle('selected');
                            
                            const hasSelection = qOptsList.querySelector('.quiz-option-item.selected') !== null;
                            submitBtn.disabled = !hasSelection;
                        });
                        
                        qOptsList.appendChild(optLi);
                    });
                    card.appendChild(qOptsList);
                    
                    const actionsDiv = document.createElement('div');
                    actionsDiv.className = 'quiz-actions';
                    
                    const submitBtn = document.createElement('button');
                    submitBtn.className = 'quiz-submit-btn';
                    submitBtn.textContent = '保存答案';
                    submitBtn.disabled = true;
                    actionsDiv.appendChild(submitBtn);
                    
                    const resetBtn = document.createElement('button');
                    resetBtn.className = 'quiz-reset-btn';
                    resetBtn.textContent = '修改答案';
                    resetBtn.style.display = 'none';
                    actionsDiv.appendChild(resetBtn);
                    
                    card.appendChild(actionsDiv);
                    
                    ul.parentNode.insertBefore(card, ul);
                    ul.style.display = 'none';
                    if (prevHeading) prevHeading.style.display = 'none';
                    
                    const revealResult = (selectedLetters) => {
                        if (!selectedLetters || !Array.isArray(selectedLetters)) selectedLetters = [];
                        card.classList.add('submitted');
                        submitBtn.style.display = 'none';
                        resetBtn.style.display = 'block';
                        
                        qOptsList.querySelectorAll('.quiz-option-item').forEach(item => {
                            item.classList.add('disabled');
                            const letter = item.getAttribute('data-letter');
                            const isSelected = selectedLetters.includes(letter);
                            if (isSelected) {
                                item.classList.add('selected');
                            }
                        });
                        
                        const resultDiv = document.createElement('div');
                        resultDiv.className = 'quiz-result-panel';
                        
                        resultDiv.innerHTML = `
                            <div class="result-alert-box alert-submitted">
                                <span>💾 已保存你的答案：${selectedLetters.join(', ')}</span>
                            </div>
                        `;
                        card.appendChild(resultDiv);
                        
                        saveUserAnswer(currentQuizIdx, selectedLetters, true);
                        updateDashboard();
                    };
                    
                    submitBtn.addEventListener('click', () => {
                        const selectedItems = Array.from(qOptsList.querySelectorAll('.quiz-option-item.selected'));
                        const selectedLetters = selectedItems.map(item => item.getAttribute('data-letter'));
                        revealResult(selectedLetters);
                    });
                    
                    resetBtn.addEventListener('click', () => {
                        qOptsList.querySelectorAll('.quiz-option-item').forEach(item => {
                            item.classList.remove('selected', 'disabled');
                        });
                        card.classList.remove('submitted');
                        submitBtn.style.display = 'block';
                        submitBtn.disabled = true;
                        resetBtn.style.display = 'none';
                        
                        const res = card.querySelector('.quiz-result-panel');
                        if (res) res.parentNode.removeChild(res);
                        
                        deleteUserAnswer(currentQuizIdx);
                        updateDashboard();
                    });
                    
                    const savedAns = loadUserAnswer(currentQuizIdx);
                    if (savedAns && savedAns.selected && Array.isArray(savedAns.selected)) {
                        savedAns.selected.forEach(letter => {
                            const optItem = qOptsList.querySelector(`.quiz-option-item[data-letter="${letter}"]`);
                            if (optItem) optItem.classList.add('selected');
                        });
                        revealResult(savedAns.selected);
                    } else if (savedAns) {
                        deleteUserAnswer(currentQuizIdx);
                    }
                }
            });
            
            formatSubjectiveAnswers();
            initDashboardAndTabs(quizIndex);
        }
    </script>
</body>
</html>
"""
    
    # Process each markdown file to replace relative links and output beautiful HTML files
    for f in files:
        md_path = os.path.join(src_dir, f)
        html_filename = file_mapping[f]
        dest_path = os.path.join(dest_dir, html_filename)
        
        with open(md_path, "r", encoding="utf-8") as file:
            md_text = file.read()
            
        # Replace markdown links to .md files with links to .html files in the html version (supporting nested parentheses)
        def link_replacer(match):
            anchor_text = match.group(1)
            url = match.group(2)
            basename = os.path.basename(url)
            if basename in file_mapping:
                mapped_html = file_mapping[basename]
                url = mapped_html
                if anchor_text.endswith('.md'):
                    anchor_text = mapped_html
            return "[{}]({})".format(anchor_text, url)
            
        content_replaced = re.sub(r'\[([^\]]+)\]\(([^()]*(?:\([^()]*\)[^()]*)*)\)', link_replacer, md_text)
        
        # Convert markdown text to static HTML content in Python
        html_content = md_to_html(content_replaced)
        
        # Render HTML template
        title_display = f.replace(".md", "").split("_", 1)[-1].replace("_", " ")
        rendered = template.replace("{TITLE}", title_display)
        rendered = rendered.replace("{NAV_ITEMS}", nav_items_html)
        rendered = rendered.replace("{HTML_CONTENT}", html_content)
        
        with open(dest_path, "w", encoding="utf-8") as out:
            out.write(rendered)
            
        print("Generated Static HTML: {}".format(dest_path))

if __name__ == '__main__':
    process_all()
