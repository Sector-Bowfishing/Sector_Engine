"""Small Markdown → print HTML converter for the audit hand-offs (headings, lists, tables, emphasis)."""
import html, re, sys

src, out, title = sys.argv[1], sys.argv[2], sys.argv[3]
lines = open(src, encoding="utf-8").read().split("\n")

def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<em>\1</em>", s)
    return s

LIST = re.compile(r"^(\s*)([-*]|\d+\.)\s+(.*)$")
body, i, n = [], 0, len(lines)
while i < n:
    ln = lines[i]
    if not ln.strip():
        i += 1; continue
    if ln.strip() == "---":
        body.append("<hr>"); i += 1; continue
    mi = re.match(r"^!\[(.*?)\]\((.*?)\)\s*$", ln)
    if mi:
        body.append(f'<figure><img src="{html.escape(mi.group(2))}" alt="{html.escape(mi.group(1))}"><figcaption>{inline(mi.group(1))}</figcaption></figure>'); i += 1; continue
    m = re.match(r"^(#{1,3})\s+(.*)$", ln)
    if m:
        lvl = len(m.group(1)); body.append(f"<h{lvl}>{inline(m.group(2))}</h{lvl}>"); i += 1; continue
    if ln.startswith("|"):
        rows = []
        while i < n and lines[i].startswith("|"):
            rows.append([c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", lines[i].strip().strip("|"))]); i += 1
        head, align, rest = rows[0], rows[1], rows[2:]
        al = ["right" if a.endswith(":") and not a.startswith(":") else "left" for a in align]
        t = ["<div class=\"tw\"><table><thead><tr>" + "".join(f'<th style="text-align:{al[k]}">{inline(c)}</th>' for k, c in enumerate(head)) + "</tr></thead><tbody>"]
        for r in rest:
            t.append("<tr>" + "".join(f'<td style="text-align:{al[k] if k < len(al) else "left"}">{inline(c)}</td>' for k, c in enumerate(r)) + "</tr>")
        t.append("</tbody></table></div>"); body.append("".join(t)); continue
    if LIST.match(ln):
        stack, parts = [], []          # stack of (indent, tag)
        while i < n and (LIST.match(lines[i]) or (lines[i].startswith("  ") and lines[i].strip() and stack)):
            mm = LIST.match(lines[i])
            if not mm:                  # continuation line of the previous item
                parts[-1] = parts[-1] + " " + inline(lines[i].strip()); i += 1; continue
            ind, mark, text = len(mm.group(1)), mm.group(2), mm.group(3)
            tag = "ol" if mark[0].isdigit() else "ul"
            while stack and ind < stack[-1][0]:
                parts.append(f"</li></{stack.pop()[1]}>")
            if not stack or ind > stack[-1][0]:
                stack.append((ind, tag)); parts.append(f"<{tag}><li>{inline(text)}")
            else:
                parts.append(f"</li><li>{inline(text)}")
            i += 1
        while stack:
            parts.append(f"</li></{stack.pop()[1]}>")
        body.append("".join(parts)); continue
    para = []
    while i < n and lines[i].strip() and not lines[i].startswith(("|", "#")) and not LIST.match(lines[i]) and lines[i].strip() != "---":
        para.append(lines[i].strip()); i += 1
    body.append(f"<p>{inline(' '.join(para))}</p>")

# keep each heading with the block that follows it
merged, k = [], 0
while k < len(body):
    b = body[k]
    if re.match(r"<h[23]>", b) and k + 1 < len(body):
        grp = [b]; k += 1
        while k < len(body) and re.match(r"<h3>", body[k]) and len(grp) < 2:
            grp.append(body[k]); k += 1
        if k < len(body) and not re.match(r"<h[123]>|<hr>", body[k]):
            grp.append(body[k]); k += 1
        merged.append('<div class="keep">' + "".join(grp) + "</div>")
    else:
        merged.append(b); k += 1

CSS = """@page{size:Letter;margin:15mm 14mm}
body{font-family:-apple-system,"Helvetica Neue",Helvetica,Arial,sans-serif;color:#1d2530;font-size:10pt;line-height:1.42;margin:0}
h1{font-size:18pt;margin:0 0 6pt;letter-spacing:-.2pt;color:#0f2a3d;text-wrap:balance}
h2{font-size:12.5pt;margin:14pt 0 5pt;padding-bottom:3pt;border-bottom:1.5px solid #cfdbe4;color:#0f2a3d}
h3{font-size:10.5pt;margin:10pt 0 4pt;color:#23455e}
p{margin:4pt 0}ul,ol{margin:3pt 0 4pt 15pt;padding:0}li{margin:1.5pt 0}
hr{border:0;border-top:1px solid #dbe4ea;margin:10pt 0}
code{font-family:"SF Mono",Menlo,monospace;font-size:8.5pt;background:#eef3f7;padding:0 3px;border-radius:3px}
.tw{overflow-x:auto}
table{border-collapse:collapse;width:100%;margin:5pt 0 7pt;font-size:8.6pt;font-variant-numeric:tabular-nums;page-break-inside:avoid;break-inside:avoid}
th{background:#e8eff5;color:#23455e;font-weight:600;padding:4px 6px;border-bottom:1.5px solid #b9cad7;vertical-align:bottom}
td{padding:3px 6px;border-bottom:1px solid #e3eaf0;vertical-align:top}
figure{margin:6pt 0;break-inside:avoid}figure img{max-width:100%;max-height:230mm;display:block;margin:0 auto}figcaption{font-size:8.5pt;color:#4a5a68;margin-top:3pt}
h2,h3{break-after:avoid-page;page-break-after:avoid}.keep{break-inside:avoid;page-break-inside:avoid}"""
open(out, "w", encoding="utf-8").write(
    f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(title)}</title><style>{CSS}</style></head><body>'
    + "".join(merged) + "</body></html>")
