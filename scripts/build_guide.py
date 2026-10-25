"""Render this project's small, trusted Markdown guide without extra dependencies."""
from __future__ import annotations
import html
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def inline(text):
    text = html.escape(text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    return re.sub(r'\[([^]]+)\]\((https://[^\s)]+|[^\s)]+\.md)\)', r'<a href="\2">\1</a>', text)


def render(markdown):
    out, para, listing, quote, code = [], [], [], [], None
    code_language = ''

    def flush():
        if para:
            out.append('<p>' + inline(' '.join(para)) + '</p>')
            para.clear()
        if listing:
            out.append('<ol>' + ''.join('<li>' + inline(item) + '</li>' for item in listing) + '</ol>')
            listing.clear()
        if quote:
            out.append('<blockquote>' + inline(' '.join(quote)) + '</blockquote>')
            quote.clear()

    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if code is not None:
            if line.startswith('```'):
                if code_language == 'setup-prompt':
                    out.append('<div class="prompt"><label for="codex-setup-prompt"><strong>Copy this whole message into your new Codex chat</strong></label>'
                               '<textarea id="codex-setup-prompt" readonly spellcheck="false" rows="17">' + html.escape('\n'.join(code)) + '</textarea>'
                               '<button type="button" id="copy-setup-prompt">Copy setup prompt</button>'
                               '<p id="copy-status" role="status" aria-live="polite">Or click inside the box, press Command+A, then Command+C.</p></div>')
                else:
                    out.append('<pre><code>' + html.escape('\n'.join(code)) + '</code></pre>')
                code = None
            else:
                code.append(line)
        elif line.startswith('```'):
            flush()
            code = []
            code_language = line[3:].strip()
        elif line.startswith('|'):
            flush()
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                cells = [cell.strip() for cell in lines[i].strip('|').split('|')]
                if not all(re.fullmatch(r'[:\- ]+', cell) for cell in cells):
                    rows.append(cells)
                i += 1
            out.append('<div class="table-wrap"><table><thead><tr>' + ''.join('<th>' + inline(c) + '</th>' for c in rows[0]) + '</tr></thead><tbody>')
            out.extend('<tr>' + ''.join('<td>' + inline(c) + '</td>' for c in row) + '</tr>' for row in rows[1:])
            out.append('</tbody></table></div>')
            continue
        elif line.startswith('#'):
            flush()
            level = len(line) - len(line.lstrip('#'))
            title = line[level:].strip()
            anchor = re.sub('[^a-z0-9]+', '-', title.lower()).strip('-')
            out.append(f'<h{level} id="{anchor}">{inline(title)}</h{level}>')
        elif re.match(r'^\d+\. ', line):
            if para or quote:
                flush()
            listing.append(re.sub(r'^\d+\. ', '', line))
        elif line.startswith('>'):
            if para or listing:
                flush()
            quote.append(line[1:].strip())
        elif not line.strip():
            flush()
        elif listing and line.startswith(' '):
            listing[-1] += ' ' + line.strip()
        else:
            if listing or quote:
                flush()
            para.append(line.strip())
        i += 1
    flush()
    return '\n'.join(out)


def build(root=ROOT):
    markdown = (root / 'docs/USER-GUIDE.md').read_text()
    prompts = re.findall(r'```setup-prompt\n(.*?)\n```', markdown, re.S)
    if len(prompts) != 1:
        raise ValueError('The guide must contain exactly one Codex setup prompt')
    body = render(markdown).replace('href="docs/', 'href="../docs/')
    document = '''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>NextRole · Start here</title>
<style>
:root{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#242236;background:#f7f7fb;line-height:1.65}
*{box-sizing:border-box}body{margin:0}main{max-width:980px;margin:auto;padding:46px 28px 70px}header{background:#fff;border:1px solid #e4ddef;border-radius:20px;padding:32px;margin-bottom:28px}
.eyebrow{color:#6539c7;font-size:12px;font-weight:750;letter-spacing:2px}header h1{font-size:42px;line-height:1.15;margin:14px 0}header p{color:#625d72;font-size:18px}.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:25px 0}.step{background:#f2ecff;border-radius:12px;padding:18px}.step b{display:block;margin-bottom:7px}.step p{font-size:14px;margin:0;color:#4d455f}
nav{display:flex;flex-wrap:wrap;gap:10px}a{color:#6330cc;text-decoration-thickness:1px;text-underline-offset:3px}nav a{background:#fff;border:1px solid #dcd1ef;padding:7px 12px;border-radius:8px;text-decoration:none;font-size:13px}h2{border-top:1px solid #ded9e8;padding-top:28px;margin-top:40px;font-size:25px;scroll-margin-top:20px}article>h1{font-size:15px;color:#625d72;text-transform:uppercase;letter-spacing:1px}p,li{max-width:85ch}li{padding-left:4px;margin:10px 0}code{font-size:.9em;background:#eeeaf4;padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}pre{overflow:auto;background:#242236;color:#fff;padding:18px;border-radius:10px}pre code{background:transparent;padding:0;color:inherit;overflow-wrap:normal}blockquote{border-left:4px solid #7950d3;background:#f0eafb;margin:20px 0;padding:18px 22px}.table-wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;background:#fff;font-size:14px}th,td{text-align:left;vertical-align:top;border:1px solid #e4dfeb;padding:12px}th{background:#f1ecf9}footer{margin-top:45px;color:#625d72;font-size:13px}.local{font-size:14px;background:#eaf5ef;border-radius:10px;padding:14px 18px}
.prompt{border:2px solid #d5c5f3;border-radius:12px;background:#fff;padding:20px}.prompt label{display:block;margin-bottom:12px}.prompt textarea{display:block;width:100%;resize:vertical;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;color:#242236;background:#faf8ff;border:1px solid #d6cbe8;border-radius:8px;padding:16px;margin-bottom:14px}.prompt button{font:600 15px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#6539c7;color:#fff;border:0;border-radius:8px;padding:12px 18px;cursor:pointer}.prompt p{font-size:14px;color:#625d72;margin-bottom:0}button:focus-visible,a:focus-visible,textarea:focus-visible{outline:3px solid #9776dc;outline-offset:3px}
@media(max-width:650px){main{padding:20px 16px}header{padding:22px}header h1{font-size:32px}.steps{grid-template-columns:1fr}h2{font-size:23px}}@media print{nav{display:none}main{padding:0}header{break-inside:avoid}h2{break-after:avoid}}
</style></head><body><main><header><div class="eyebrow">NEXTROLE · MAC EDITION</div>
<h1>Give Codex the ZIP and your resume.</h1><p>The recommended Mac setup. Attach your files, paste one message, then let Codex guide you.</p>
<div class="steps"><div class="step"><b>1 · Open a local Codex chat</b><p>Use Codex on your Mac, signed into your own account. No coding knowledge needed.</p></div>
<div class="step"><b>2 · Attach the ZIP + your resume</b><p>Drag both files into the message, or name your resume in Drive. Codex can unpack the project for you.</p></div>
<div class="step"><b>3 · Paste the setup message</b><p>Use the copy button below. Codex checks your connections, launches the site and helps you review your profile.</p></div></div>
<p>Already set up? Just double-click <strong>Start NextRole.command</strong>. You can keep using the same Codex chat for help.</p>
<p class="local">After launch, open <a href="http://127.0.0.1:8877/">your local NextRole</a>. This link works only while the launcher is running.</p>
<nav aria-label="Guide sections"><a href="#step-1-open-a-local-codex-chat">Open Codex</a><a href="#step-3-attach-your-current-resume-or-choose-drive">Add your resume</a><a href="#step-4-copy-this-message-paste-and-send">Copy setup prompt</a><a href="#step-6-open-the-site-and-try-one-job">First job</a><a href="#step-7-tomorrow-just-double-click">Tomorrow</a><a href="#manual-folder-fallback-only-if-attachments-do-not-work">Manual fallback</a><a href="#troubleshooting">I am stuck</a></nav>
</header><article>''' + body + '''</article><footer>Mac source release 0.8.4 · Keep your used workspace private. Share the original clean ZIP.</footer></main>
<script>
document.getElementById('copy-setup-prompt').addEventListener('click', async function () {
  const text = document.getElementById('codex-setup-prompt');
  const status = document.getElementById('copy-status');
  try {
    if (!navigator.clipboard || !navigator.clipboard.writeText) throw new Error('Manual copy needed');
    await navigator.clipboard.writeText(text.value);
    status.textContent = 'Copied. Open your new Codex chat, click the message box, press Command+V, then send.';
  } catch (_) {
    text.focus();
    text.select();
    status.textContent = 'Message selected. Press Command+C to copy, then click the Codex message box and press Command+V.';
  }
});
</script></body></html>'''
    target = root / 'setup/START HERE.html'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(document, encoding='utf-8')
    (root / 'setup/CODEX SETUP PROMPT.txt').write_text(prompts[0] + '\n', encoding='utf-8')
    return target


if __name__ == '__main__':
    print(build())
