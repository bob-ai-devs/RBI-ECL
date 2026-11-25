"""
Exporters: one document JSON -> PDF, DOCX, XLSX and standalone HTML (all built in memory).

Unfilled placeholders are kept visible as blue [bracketed hints] in every format, so an exported file
is still a usable template. `include_guidance=False` drops the 'Section goal' boxes and italic notes,
as the source templates ask before submission.
"""
import hashlib
import html as _html
import io
import math
import re
from pathlib import Path

from . import model as M

ASSETS = Path(__file__).resolve().parent.parent / "assets"
NAVY, ORANGE, VERMILION, GOLD, CREAM, INK, BLUE = "0A2A66", "F26B21", "E4402A", "FDB515", "FFF8F0", "1F2937", "1F4E9E"

PH = M.PLACEHOLDER


# ------------------------------------------------------------------ shared helpers
def cell_text(c: dict):
    """-> (text, is_placeholder)"""
    if c.get("k") == "chk":
        mark = "☑" if c.get("v") == "Y" else "☐"
        return (f"{mark} {c.get('lbl') or 'Done'}", False)
    v = (c.get("v") or "").strip()
    if v:
        return v, bool(c.get("f") and PH.search(v))
    if c.get("f"):
        h = (c.get("h") or "").strip()
        return (f"[{h}]" if h else "[  ]"), True
    return "", False


def segments(text: str):
    """Split text into (segment, is_bracket) so placeholders can be coloured."""
    out, pos = [], 0
    for m in PH.finditer(text):
        if m.start() > pos:
            out.append((text[pos:m.start()], False))
        out.append((m.group(0), True))
        pos = m.end()
    if pos < len(text):
        out.append((text[pos:], False))
    return out


def col_weights(b: dict):
    n = len(b["cols"])
    w = []
    for ci in range(n):
        lens = sorted(len(cell_text(r[ci])[0]) for r in b["rows"]) or [0]
        med = lens[len(lens) // 2]
        w.append(max(10, min(70, 0.55 * max(len(b["cols"][ci]) * 0.9, med) + 0.45 * lens[-1] * 0.5)))
    s = sum(w)
    return [x / s for x in w]


def visible_blocks(sec, include_guidance):
    for b in sec["blocks"]:
        if b["t"] == "note" and not include_guidance:
            continue
        yield b


def all_sections(doc):
    return doc["sections"]


def header_line(doc, meta):
    return f"{M.KINDS[doc['kind']]} · {M.DEPTHS[doc['depth']]}"


def meta_line(doc, meta):
    f, t = M.completion(doc)
    bits = [f"Generated {meta.get('created', '')}", f"Completion {M.pct(doc)}% ({f}/{t} fields)"]
    if meta.get("ai"):
        bits.append(f"Draft prepared with AI assistance ({meta.get('model', 'Gemini')}) – human review required")
    return "  |  ".join(b for b in bits if b.strip())


# ================================================================== HTML
_CSS = f"""
:root{{--navy:#{NAVY};--orange:#{ORANGE};--ver:#{VERMILION};--gold:#{GOLD};--cream:#{CREAM};--ink:#{INK};--blue:#{BLUE}}}
*{{box-sizing:border-box}}body{{margin:0;font:14px/1.5 "Segoe UI",Roboto,Arial,sans-serif;color:var(--ink);background:#fff}}
.hero{{background:linear-gradient(115deg,var(--ver),var(--orange) 60%,var(--gold));color:#fff;padding:34px 48px}}
.hero small{{letter-spacing:.14em;font-weight:700;opacity:.92}}.hero h1{{margin:6px 0 4px;font-size:30px}}.hero p{{margin:0;opacity:.95;max-width:900px}}
.strip{{background:var(--navy);color:#fff;padding:8px 48px;font-size:12px}}
.wrap{{display:flex;max-width:1500px;margin:0 auto}}nav{{width:290px;flex:none;padding:22px 16px;position:sticky;top:0;align-self:flex-start;max-height:100vh;overflow:auto;border-right:1px solid #eee}}
nav a{{display:block;padding:6px 10px;color:var(--navy);text-decoration:none;border-radius:6px;font-size:13px}}nav a:hover{{background:var(--cream);color:var(--ver)}}
main{{flex:1;padding:10px 40px 60px;min-width:0}}h2.sec{{background:var(--navy);color:#fff;padding:9px 14px;border-left:8px solid var(--orange);border-radius:4px;margin:34px 0 12px;font-size:19px}}
h3{{color:var(--ver);border-bottom:2px solid var(--gold);padding-bottom:3px;margin:22px 0 8px;font-size:16px}}h4{{color:var(--navy);margin:14px 0 4px}}
.goal{{background:#fff4d6;border-left:5px solid var(--orange);padding:8px 12px;margin:8px 0;border-radius:3px;font-size:13px}}
.note{{color:#6b7280;font-style:italic;font-size:13px}}.howto{{background:#fff4d6;border:1px solid var(--gold);border-radius:6px;padding:10px 16px;margin:18px 0;font-size:13px}}
.tw{{overflow-x:auto;margin:8px 0 14px}}table{{border-collapse:collapse;width:100%;font-size:12.5px}}th{{background:var(--navy);color:#fff;text-align:left;padding:7px 8px;border:1px solid #1d3d80}}
td{{padding:6px 8px;border:1px solid #e5d9cc;vertical-align:top}}tbody tr:nth-child(even){{background:#fbf6f0}}td.first{{font-weight:600}}
.ph{{color:var(--blue)}}.need{{background:#fff6da}}pre.f{{background:#f3f4f6;border-left:4px solid var(--orange);padding:8px 12px;font:12.5px/1.5 Consolas,monospace;white-space:pre-wrap}}
.pl{{font-weight:700;color:var(--navy)}}footer{{text-align:center;color:#6b7280;font-size:12px;padding:26px;border-top:1px solid #eee}}
@media print{{nav{{display:none}}h2.sec{{break-after:avoid}}tr{{break-inside:avoid}}}}
@media(max-width:900px){{nav{{display:none}}main{{padding:10px 16px}}}}
"""


def _h(text):
    return _html.escape(text).replace("\n", "<br>")


def _hcell(c):
    text, is_ph = cell_text(c)
    inner = "".join(f'<span class="ph">{_h(s)}</span>' if br else _h(s) for s, br in segments(text)) if c.get("f") else _h(text)
    return inner, ("need" if (c.get("f") and M.needs_fill(c)) else "")


def export_html(doc, meta, include_guidance=False) -> bytes:
    p = []
    p.append(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>{_h(doc['title'])} – {_h(header_line(doc, meta))}</title><style>{_CSS}</style></head><body>")
    p.append(f"<div class='hero'><small>BANK OF BARODA · MODEL RISK MANAGEMENT · {_h(header_line(doc, meta).upper())}</small>"
             f"<h1>{_h(doc['title'])}</h1><p>{_h(doc['subtitle'])}</p></div><div class='strip'>{_h(meta_line(doc, meta))}</div><div class='wrap'><nav>")
    for i, s in enumerate(doc["sections"]):
        p.append(f"<a href='#s{i}'>{_h(s['title'])}</a>")
    p.append("</nav><main>")
    if include_guidance and doc.get("howto"):
        p.append(f"<div class='howto'><b>How to use this template.</b><br>{_h(doc['howto'])}</div>")
    for i, s in enumerate(doc["sections"]):
        p.append(f"<h2 class='sec' id='s{i}'>{_h(s['title'])}</h2>")
        if include_guidance and s.get("goal"):
            p.append(f"<div class='goal'><b>Section goal.</b> {_h(s['goal'])}</div>")
        for b in visible_blocks(s, include_guidance):
            t = b["t"]
            if t == "h":
                p.append(f"<h3>{_h(b['text'])}</h3>")
            elif t == "h3":
                p.append(f"<h4>{_h(b['text'])}</h4>")
            elif t == "note":
                p.append(f"<p class='note'>{_h(b['text'])}</p>")
            elif t == "formula":
                p.append(f"<pre class='f'>{_h(b['c']['v'])}</pre>")
            elif t == "para":
                inner, cls = _hcell(b["c"])
                lab = f"<span class='pl'>{_h(b['label'])}</span> " if b.get("label") else ""
                p.append(f"<p class='{cls}'>{lab}{inner}</p>")
            elif t == "list":
                p.append("<ul>")
                for it in b["items"]:
                    inner, cls = _hcell(it["c"])
                    lab = f"<span class='pl'>{_h(it['label'])}</span> " if it.get("label") else ""
                    p.append(f"<li class='{cls}'>{lab}{inner}</li>")
                p.append("</ul>")
            elif t == "table":
                p.append("<div class='tw'><table><thead><tr>" + "".join(f"<th>{_h(c)}</th>" for c in b["cols"]) + "</tr></thead><tbody>")
                for r in b["rows"]:
                    p.append("<tr>")
                    for ci, c in enumerate(r):
                        inner, cls = _hcell(c)
                        first = " first" if ci == 0 and not c.get("f") else ""
                        p.append(f"<td class='{cls}{first}'>{inner}</td>")
                    p.append("</tr>")
                p.append("</tbody></table></div>")
    p.append(f"</main></div><footer>{_h(doc.get('footer', ''))}</footer></body></html>")
    return "".join(p).encode("utf-8")


# ================================================================== DOCX
def export_docx(doc, meta, include_guidance=False) -> bytes:
    from docx import Document
    from docx.enum.section import WD_ORIENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Cm, Pt, RGBColor

    def rgb(h):
        return RGBColor.from_string(h)

    d = Document()
    sec0 = d.sections[0]
    sec0.orientation = WD_ORIENT.LANDSCAPE
    sec0.page_width, sec0.page_height = Cm(29.7), Cm(21.0)
    for side in ("left_margin", "right_margin"):
        setattr(sec0, side, Cm(1.5))
    sec0.top_margin, sec0.bottom_margin = Cm(1.6), Cm(1.6)
    usable = 26.7

    st = d.styles["Normal"]
    st.font.name, st.font.size = "Calibri", Pt(10)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")
    for name, size, color in (("Heading 1", 16, NAVY), ("Heading 2", 13, VERMILION), ("Heading 3", 11, NAVY)):
        h = d.styles[name]
        h.font.name, h.font.size, h.font.bold = "Calibri", Pt(size), True
        h.font.color.rgb = rgb(color)
        h.element.rPr.rFonts.set(qn("w:eastAsia"), "Calibri")

    def shade(cell, hex_):
        tcPr = cell._tc.get_or_add_tcPr()
        sh = OxmlElement("w:shd")
        sh.set(qn("w:val"), "clear"), sh.set(qn("w:color"), "auto"), sh.set(qn("w:fill"), hex_)
        tcPr.append(sh)

    def borders(cell, color="E5D9CC", sz=4, left=None):
        tcPr = cell._tc.get_or_add_tcPr()
        b = OxmlElement("w:tcBorders")
        for edge in ("top", "left", "bottom", "right"):
            e = OxmlElement(f"w:{edge}")
            e.set(qn("w:val"), "single")
            col, size = (left[0], left[1]) if (edge == "left" and left) else (color, sz)
            e.set(qn("w:sz"), str(size)), e.set(qn("w:space"), "0"), e.set(qn("w:color"), col)
            b.append(e)
        tcPr.append(b)

    def runs(par, text, size=9, bold=False, italic=False, color=None, mark_ph=True):
        for seg, br in (segments(text) if mark_ph else [(text, False)]):
            lines = seg.split("\n")
            for i, ln in enumerate(lines):
                r = par.add_run(ln)
                r.font.size, r.bold, r.italic = Pt(size), bold, italic
                if br:
                    r.font.color.rgb = rgb(BLUE)
                elif color:
                    r.font.color.rgb = rgb(color)
                if i < len(lines) - 1:
                    r.add_break()

    def fix_par(par, after=2, before=0):
        par.paragraph_format.space_after, par.paragraph_format.space_before = Pt(after), Pt(before)

    def add_field(par, instr, size=8):
        r = par.add_run()
        r.font.size = Pt(size)
        for t, txt in (("begin", None), (None, instr), ("end", None)):
            if t:
                e = OxmlElement("w:fldChar")
                e.set(qn("w:fldCharType"), t)
            else:
                e = OxmlElement("w:instrText")
                e.set(qn("xml:space"), "preserve")
                e.text = txt
            r._r.append(e)

    # header / footer
    hp = sec0.header.paragraphs[0]
    runs(hp, f"Bank of Baroda · {doc['title']} · {header_line(doc, meta)}", 8, color="6B7280", mark_ph=False)
    fp = sec0.footer.paragraphs[0]
    runs(fp, (doc.get("footer") or "") + "   |   Page ", 8, color="6B7280", mark_ph=False)
    add_field(fp, "PAGE")
    runs(fp, " of ", 8, color="6B7280", mark_ph=False)
    add_field(fp, "NUMPAGES")

    # cover banner
    t = d.add_table(rows=1, cols=1)
    t.autofit = False
    c = t.cell(0, 0)
    c.width = Cm(usable)
    shade(c, VERMILION)
    borders(c, VERMILION, 4)
    p0 = c.paragraphs[0]
    runs(p0, "BANK OF BARODA  •  MODEL RISK MANAGEMENT  •  " + header_line(doc, meta).upper(), 9, True, color="FFFFFF", mark_ph=False)
    p1 = c.add_paragraph()
    runs(p1, doc["title"], 24, True, color="FFFFFF", mark_ph=False)
    p2 = c.add_paragraph()
    runs(p2, doc["subtitle"], 10.5, color="FFFFFF", mark_ph=False)
    p3 = c.add_paragraph()
    runs(p3, meta_line(doc, meta), 8.5, italic=True, color="FFF4D6", mark_ph=False)
    d.add_paragraph()

    if include_guidance and doc.get("howto"):
        t = d.add_table(rows=1, cols=1)
        c = t.cell(0, 0)
        shade(c, "FFF4D6")
        borders(c, "FDB515", 6)
        runs(c.paragraphs[0], "HOW TO USE THIS TEMPLATE  ", 9, True, color=NAVY, mark_ph=False)
        runs(c.add_paragraph(), doc["howto"], 9)
        d.add_paragraph()

    d.add_heading("Contents", level=2)
    for s in doc["sections"]:
        p = d.add_paragraph()
        runs(p, s["title"], 10, color=NAVY, mark_ph=False)
        fix_par(p, 1)

    for si, s in enumerate(doc["sections"]):
        d.add_page_break() if si == 0 else None
        d.add_heading(s["title"], level=1)
        if include_guidance and s.get("goal"):
            t = d.add_table(rows=1, cols=1)
            c = t.cell(0, 0)
            shade(c, "FFF4D6")
            borders(c, "E5D9CC", 4, left=(ORANGE, 24))
            runs(c.paragraphs[0], "SECTION GOAL  ", 8.5, True, color=VERMILION, mark_ph=False)
            runs(c.add_paragraph(), s["goal"], 9)
            d.add_paragraph().paragraph_format.space_after = Pt(2)
        for b in visible_blocks(s, include_guidance):
            tt = b["t"]
            if tt == "h":
                d.add_heading(b["text"], level=2)
            elif tt == "h3":
                d.add_heading(b["text"], level=3)
            elif tt == "note":
                p = d.add_paragraph()
                runs(p, b["text"], 9, italic=True, color="6B7280")
            elif tt == "formula":
                p = d.add_paragraph()
                runs(p, b["c"]["v"], 9.5, mark_ph=False)
                for r in p.runs:
                    r.font.name = "Consolas"
                pPr = p._p.get_or_add_pPr()
                sh = OxmlElement("w:shd")
                sh.set(qn("w:val"), "clear"), sh.set(qn("w:fill"), "F3F4F6")
                pPr.append(sh)
            elif tt == "para":
                p = d.add_paragraph()
                if b.get("label"):
                    runs(p, b["label"] + " ", 10, True, color=NAVY, mark_ph=False)
                runs(p, cell_text(b["c"])[0], 10)
                fix_par(p, 4)
            elif tt == "list":
                for it in b["items"]:
                    p = d.add_paragraph(style="List Bullet")
                    if it.get("label"):
                        runs(p, it["label"] + " ", 10, True, color=NAVY, mark_ph=False)
                    runs(p, cell_text(it["c"])[0], 10)
                    fix_par(p, 2)
            elif tt == "table":
                ncols = len(b["cols"])
                tbl = d.add_table(rows=1, cols=ncols)
                tbl.autofit = False
                w = col_weights(b)
                for ci, name in enumerate(b["cols"]):
                    c = tbl.rows[0].cells[ci]
                    c.width = Cm(usable * w[ci])
                    shade(c, NAVY)
                    borders(c, "1D3D80", 4)
                    runs(c.paragraphs[0], name, 9, True, color="FFFFFF", mark_ph=False)
                trPr = tbl.rows[0]._tr.get_or_add_trPr()
                th = OxmlElement("w:tblHeader")
                th.set(qn("w:val"), "true")
                trPr.append(th)
                for ri, row in enumerate(b["rows"]):
                    cells = tbl.add_row().cells
                    cs = OxmlElement("w:cantSplit")
                    tbl.rows[-1]._tr.get_or_add_trPr().append(cs)
                    for ci, c in enumerate(row):
                        cc = cells[ci]
                        cc.width = Cm(usable * w[ci])
                        borders(cc)
                        if M.needs_fill(c):
                            shade(cc, "FFF6DA")
                        elif ri % 2:
                            shade(cc, "FBF6F0")
                        text, _ = cell_text(c)
                        bold = ci == 0 and not c.get("f") and ncols <= 3
                        runs(cc.paragraphs[0], text, 9, bold, mark_ph=bool(c.get("f")))
                d.add_paragraph().paragraph_format.space_after = Pt(4)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


# ================================================================== XLSX
def export_xlsx(doc, meta, include_guidance=False) -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    wb = Workbook()
    ws = wb.active
    ws.title = "Cover"
    thin = Side(style="thin", color="E5D9CC")
    box = Border(left=thin, right=thin, top=thin, bottom=thin)
    wrap = Alignment(wrap_text=True, vertical="top")
    f_head = Font(bold=True, color="FFFFFF", name="Calibri", size=10)
    fill_navy, fill_ver = PatternFill("solid", fgColor=NAVY), PatternFill("solid", fgColor=VERMILION)
    fill_need, fill_zebra = PatternFill("solid", fgColor="FFF6DA"), PatternFill("solid", fgColor="FBF6F0")
    fill_goal = PatternFill("solid", fgColor="FFF4D6")

    ws.sheet_view.showGridLines = False
    ws.column_dimensions["A"].width = 3
    ws.column_dimensions["B"].width = 34
    ws.column_dimensions["C"].width = 90
    ws.merge_cells("B2:C2")
    ws["B2"] = doc["title"]
    ws["B2"].font, ws["B2"].fill = Font(bold=True, size=20, color="FFFFFF"), fill_ver
    ws["B2"].alignment = Alignment(vertical="center", indent=1)
    ws.row_dimensions[2].height = 44
    ws.merge_cells("B3:C3")
    ws["B3"] = doc["subtitle"]
    ws["B3"].font, ws["B3"].fill, ws["B3"].alignment = Font(color="FFFFFF", size=10), fill_navy, Alignment(wrap_text=True, indent=1, vertical="center")
    ws.row_dimensions[3].height = 34
    f, t = M.completion(doc)
    info = [("Report", header_line(doc, meta)), ("Generated", meta.get("created", "")), ("Completion", f"{M.pct(doc)}%  ({f} of {t} fields filled)"),
            ("AI assistance", f"Draft prepared with {meta.get('model', 'Gemini')} – human review required" if meta.get("ai") else "None (manual / blank template)")]
    if include_guidance and doc.get("howto"):
        info.append(("How to use", doc["howto"]))
    for i, (k, v) in enumerate(info):
        r = 5 + i
        ws.cell(r, 2, k).font = Font(bold=True, color=NAVY)
        c = ws.cell(r, 3, v)
        c.alignment = wrap
        ws.row_dimensions[r].height = max(18, 15 * math.ceil(len(v) / 95))
    r = 6 + len(info)
    ws.cell(r, 2, "Contents").font = Font(bold=True, size=12, color=VERMILION)
    sheet_names = []
    for i, s in enumerate(doc["sections"]):
        mt = re.match(r"^(\d+)\.\s*(.*)$", s["title"])
        ma = re.match(r"^Appendix\s+([A-Z])\s*[–-]\s*(.*)$", s["title"])
        label = f"{mt.group(1)} {mt.group(2)}" if mt else (f"App {ma.group(1)} {ma.group(2)}" if ma else s["title"])
        short = re.sub(r"[\[\]:*?/\\]", "", label)
        name = short[:31]
        base, k = name, 2
        while name in sheet_names:
            name = f"{base[:28]}~{k}"
            k += 1
        sheet_names.append(name)
        ws.cell(r + 1 + i, 2, f"Sheet {i}").font = Font(color="6B7280")
        c = ws.cell(r + 1 + i, 3, s["title"])
        c.hyperlink = f"#'{name}'!A1"
        c.font = Font(color=NAVY, underline="single")

    open_rows = []
    for si, s in enumerate(doc["sections"]):
        sh = wb.create_sheet(sheet_names[si])
        sh.sheet_view.showGridLines = False
        tabs = [b for b in s["blocks"] if b["t"] == "table"]
        ncols = max([len(b["cols"]) for b in tabs] + [4])
        widths = [14] * ncols
        for b in tabs:
            wts = col_weights(b)
            for ci in range(len(b["cols"])):
                widths[ci] = max(widths[ci], min(55, 10 + wts[ci] * 140))
        widths[0] = max(widths[0], 28)
        for ci, w in enumerate(widths):
            sh.column_dimensions[get_column_letter(ci + 1)].width = w
        row = 1
        sh.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
        sh.cell(row, 1, s["title"]).font = Font(bold=True, size=14, color="FFFFFF")
        sh.cell(row, 1).fill = fill_navy
        sh.cell(row, 1).alignment = Alignment(vertical="center", indent=1)
        sh.row_dimensions[row].height = 28
        row += 2
        if include_guidance and s.get("goal"):
            sh.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
            sh.cell(row, 1, "Section goal: " + s["goal"]).alignment = wrap
            sh.cell(row, 1).fill = fill_goal
            sh.row_dimensions[row].height = max(18, 14 * math.ceil(len(s["goal"]) / (sum(widths) * 1.1)))
            row += 2
        heading = ""
        for b in visible_blocks(s, include_guidance):
            tt = b["t"]
            if tt in ("h", "h3"):
                heading = b["text"]
                sh.cell(row, 1, b["text"]).font = Font(bold=True, size=12, color=VERMILION)
                row += 1
            elif tt == "note":
                sh.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
                sh.cell(row, 1, b["text"]).font = Font(italic=True, color="6B7280")
                sh.cell(row, 1).alignment = wrap
                sh.row_dimensions[row].height = max(16, 14 * math.ceil(len(b["text"]) / (sum(widths) * 1.1)))
                row += 1
            elif tt in ("para", "formula", "list"):
                items = ([(b.get("label", ""), b["c"])] if tt != "list" else [(i.get("label", ""), i["c"]) for i in b["items"]])
                for lab, c in items:
                    text, _ = cell_text(c)
                    sh.cell(row, 1, lab).font = Font(bold=True, color=NAVY)
                    sh.cell(row, 1).alignment = wrap
                    sh.merge_cells(start_row=row, start_column=2, end_row=row, end_column=ncols)
                    cc = sh.cell(row, 2, text)
                    cc.alignment = wrap
                    if tt == "formula":
                        cc.font = Font(name="Consolas")
                    if M.needs_fill(c):
                        cc.fill, cc.font = fill_need, Font(color=BLUE, italic=True)
                        open_rows.append((s["title"], heading, lab or "paragraph", lab or "text", (c.get("h") or "")))
                    sh.row_dimensions[row].height = max(16, 14 * math.ceil(max(len(text), 1) / (sum(widths[1:]) * 1.05)))
                    row += 1
                row += 0
            elif tt == "table":
                for ci, name in enumerate(b["cols"]):
                    c = sh.cell(row, ci + 1, name)
                    c.font, c.fill, c.alignment, c.border = f_head, fill_navy, Alignment(wrap_text=True, vertical="center"), box
                sh.row_dimensions[row].height = 30
                row += 1
                for ri, r_ in enumerate(b["rows"]):
                    lines = 1
                    rowctx = next((c["v"] for c in r_ if not c.get("f") and c.get("v")), "")
                    for ci, c in enumerate(r_):
                        text, _ = cell_text(c)
                        cc = sh.cell(row, ci + 1, text)
                        cc.alignment, cc.border = wrap, box
                        if M.needs_fill(c):
                            cc.fill, cc.font = fill_need, Font(color=BLUE, italic=True)
                            open_rows.append((s["title"], heading, rowctx, b["cols"][ci], (c.get("h") or "")))
                        elif ri % 2:
                            cc.fill = fill_zebra
                        if ci == 0 and not c.get("f") and len(b["cols"]) <= 3:
                            cc.font = Font(bold=True)
                        lines = max(lines, math.ceil(max(len(text), 1) / (widths[ci] * 1.05)) + text.count("\n"))
                    sh.row_dimensions[row].height = min(400, max(16, 13.5 * lines))
                    row += 1
            row += 1 if tt in ("table", "list", "para") else 0
        sh.freeze_panes = "A2"

    ow = wb.create_sheet("Open items")
    ow.sheet_view.showGridLines = False
    heads = ["Section", "Heading", "Row", "Field", "Expected content (hint)"]
    for ci, h in enumerate(heads):
        c = ow.cell(1, ci + 1, h)
        c.font, c.fill = f_head, fill_ver
    for ri, rr in enumerate(open_rows):
        for ci, v in enumerate(rr):
            c = ow.cell(ri + 2, ci + 1, v)
            c.alignment = wrap
    for ci, w in enumerate([38, 38, 34, 28, 60]):
        ow.column_dimensions[get_column_letter(ci + 1)].width = w
    ow.freeze_panes = "A2"
    ow.auto_filter.ref = f"A1:E{max(2, len(open_rows) + 1)}"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ================================================================== PDF
def _register_fonts():
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    fd = ASSETS / "fonts"
    files = {"DV": "DejaVuSans.ttf", "DV-B": "DejaVuSans-Bold.ttf", "DV-I": "DejaVuSans-Oblique.ttf",
             "DV-BI": "DejaVuSans-BoldOblique.ttf", "DV-M": "DejaVuSansMono.ttf"}
    ok = all((fd / f).exists() for f in files.values())
    if ok:
        if "DV" not in pdfmetrics.getRegisteredFontNames():
            for name, f in files.items():
                pdfmetrics.registerFont(TTFont(name, str(fd / f)))
            pdfmetrics.registerFontFamily("DV", normal="DV", bold="DV-B", italic="DV-I", boldItalic="DV-BI")
        return "DV", "DV-B", "DV-I", "DV-M"
    return "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Courier"


def export_pdf(doc, meta, include_guidance=False) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.platypus import BaseDocTemplate, Frame, PageBreak, PageTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.platypus.tableofcontents import TableOfContents

    F, FB, FI, FM = _register_fonts()
    hx = lambda h: colors.HexColor("#" + h)
    PW, PH_ = landscape(A4)
    LM = RM = 14 * mm
    avail = PW - LM - RM

    S = {
        "body": ParagraphStyle("body", fontName=F, fontSize=9, leading=12.4, textColor=hx(INK), alignment=TA_LEFT, spaceAfter=4),
        "cell": ParagraphStyle("cell", fontName=F, fontSize=7.6, leading=9.8, textColor=hx(INK)),
        "cellh": ParagraphStyle("cellh", fontName=FB, fontSize=7.8, leading=9.8, textColor=colors.white),
        "cellb": ParagraphStyle("cellb", fontName=FB, fontSize=7.6, leading=9.8, textColor=hx(INK)),
        "h1": ParagraphStyle("H1", fontName=FB, fontSize=14, leading=18, textColor=colors.white, backColor=hx(NAVY), borderPadding=(5, 8, 5, 8),
                             spaceBefore=14, spaceAfter=10, keepWithNext=1),
        "h2": ParagraphStyle("H2", fontName=FB, fontSize=11.5, leading=14, textColor=hx(VERMILION), spaceBefore=10, spaceAfter=5, keepWithNext=1),
        "h3": ParagraphStyle("H3", fontName=FB, fontSize=9.5, leading=12, textColor=hx(NAVY), spaceBefore=6, spaceAfter=3, keepWithNext=1),
        "note": ParagraphStyle("note", fontName=FI, fontSize=8, leading=10.5, textColor=hx("6B7280"), spaceAfter=4),
        "formula": ParagraphStyle("formula", fontName=FM, fontSize=8, leading=11, textColor=hx(INK), backColor=hx("F3F4F6"), borderPadding=5, spaceAfter=8, spaceBefore=3),
        "bullet": ParagraphStyle("bullet", fontName=F, fontSize=9, leading=12.2, leftIndent=14, bulletIndent=3, spaceAfter=2),
        "toc": ParagraphStyle("toc", fontName=F, fontSize=9.5, leading=14, textColor=hx(NAVY)),
        "title": ParagraphStyle("title", fontName=FB, fontSize=24, leading=29, textColor=colors.white),
        "sub": ParagraphStyle("sub", fontName=F, fontSize=10.5, leading=14, textColor=colors.white),
        "kick": ParagraphStyle("kick", fontName=FB, fontSize=8.5, leading=11, textColor=hx("FFE9B8")),
        "meta": ParagraphStyle("meta", fontName=FI, fontSize=8, leading=10.5, textColor=hx("FFF4D6")),
    }

    def esc(t, limit=2500):
        if len(t) > limit:
            t = t[:limit] + " … (truncated in PDF – see DOCX/HTML for the full text)"
        return _html.escape(t).replace("\n", "<br/>")

    def rich(text, is_field=True):
        if not is_field:
            return esc(text)
        out = []
        for seg, br in segments(text):
            out.append(f'<font color="#{BLUE}">{esc(seg)}</font>' if br else esc(seg))
        return "".join(out)

    class NumberedCanvas(rl_canvas.Canvas):
        def __init__(self, *a, **k):
            super().__init__(*a, **k)
            self._saved = []

        def showPage(self):
            self._saved.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            n = len(self._saved)
            for st in self._saved:
                self.__dict__.update(st)
                self._decorate(n)
                super().showPage()
            super().save()

        def _decorate(self, total):
            self.saveState()
            self.setFillColor(hx(ORANGE))
            self.rect(0, PH_ - 5 * mm, PW, 5 * mm, stroke=0, fill=1)
            self.setFillColor(hx(NAVY))
            self.rect(0, PH_ - 6.2 * mm, PW, 1.2 * mm, stroke=0, fill=1)
            self.setFont(F, 7.5)
            self.setFillColor(hx("6B7280"))
            self.drawString(LM, 8 * mm, (doc.get("footer") or "")[:140])
            self.drawRightString(PW - RM, 8 * mm, f"Page {self._pageNumber} of {total}")
            self.setStrokeColor(hx("E5D9CC"))
            self.line(LM, 11.5 * mm, PW - RM, 11.5 * mm)
            if self._pageNumber > 1:
                self.drawString(LM, PH_ - 11 * mm, f"Bank of Baroda · {doc['title']} · {header_line(doc, meta)}")
            self.restoreState()

    class DocT(BaseDocTemplate):
        def afterFlowable(self, fl):
            if isinstance(fl, Paragraph) and fl.style.name == "H1":
                key = "sec" + hashlib.md5(fl.getPlainText().encode()).hexdigest()[:10]
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(fl.getPlainText(), key, 0, 0)
                self.notify("TOCEntry", (0, fl.getPlainText(), self.page, key))

    buf = io.BytesIO()
    dt = DocT(buf, pagesize=landscape(A4), leftMargin=LM, rightMargin=RM, topMargin=16 * mm, bottomMargin=16 * mm,
              title=f"{doc['title']} – {header_line(doc, meta)}", author="Bank of Baroda – Model Risk Management")
    dt.addPageTemplates([PageTemplate(id="p", frames=[Frame(LM, 16 * mm, avail, PH_ - 32 * mm, id="f", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)])])

    story = []
    # cover
    cover = Table([[Paragraph("BANK OF BARODA  •  MODEL RISK MANAGEMENT  •  " + esc(header_line(doc, meta).upper()), S["kick"])],
                   [Paragraph(esc(doc["title"]), S["title"])], [Paragraph(esc(doc["subtitle"]), S["sub"])],
                   [Paragraph(esc(meta_line(doc, meta)), S["meta"])]], colWidths=[avail])
    cover.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), hx(VERMILION)), ("LEFTPADDING", (0, 0), (-1, -1), 16), ("RIGHTPADDING", (0, 0), (-1, -1), 16),
                               ("TOPPADDING", (0, 0), (-1, 0), 14), ("BOTTOMPADDING", (0, -1), (-1, -1), 14), ("LINEBELOW", (0, -1), (-1, -1), 6, hx(GOLD))]))
    story += [cover, Spacer(1, 12)]
    if include_guidance and doc.get("howto"):
        hw = Table([[Paragraph("<b>HOW TO USE THIS TEMPLATE</b><br/>" + esc(doc["howto"]), S["body"])]], colWidths=[avail])
        hw.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), hx("FFF4D6")), ("BOX", (0, 0), (-1, -1), 0.8, hx(GOLD)), ("LEFTPADDING", (0, 0), (-1, -1), 10), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        story += [hw, Spacer(1, 10)]
    story.append(Paragraph("Contents", S["h2"]))
    toc = TableOfContents()
    toc.levelStyles = [ParagraphStyle("t0", parent=S["toc"], leftIndent=6, rightIndent=14)]
    toc.dotsMinLevel = 0
    story += [toc, PageBreak()]

    for s in doc["sections"]:
        story.append(Paragraph(esc(s["title"]), S["h1"]))
        if include_guidance and s.get("goal"):
            g = Table([[Paragraph("<b>SECTION GOAL</b> &nbsp;" + esc(s["goal"]), S["cell"])]], colWidths=[avail])
            g.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), hx("FFF4D6")), ("LINEBEFORE", (0, 0), (0, -1), 3, hx(ORANGE)),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
            story += [g, Spacer(1, 5)]
        for b in visible_blocks(s, include_guidance):
            tt = b["t"]
            if tt == "h":
                story.append(Paragraph(esc(b["text"]), S["h2"]))
            elif tt == "h3":
                story.append(Paragraph(esc(b["text"]), S["h3"]))
            elif tt == "note":
                story.append(Paragraph(esc(b["text"]), S["note"]))
            elif tt == "formula":
                story.append(Paragraph(esc(b["c"]["v"]), S["formula"]))
            elif tt == "para":
                text = cell_text(b["c"])[0]
                lab = f"<b><font color='#{NAVY}'>{esc(b['label'])}</font></b> " if b.get("label") else ""
                story.append(Paragraph(lab + rich(text, bool(b["c"].get("f"))), S["body"]))
            elif tt == "list":
                for it in b["items"]:
                    text = cell_text(it["c"])[0]
                    lab = f"<b><font color='#{NAVY}'>{esc(it['label'])}</font></b> " if it.get("label") else ""
                    story.append(Paragraph(lab + rich(text, bool(it["c"].get("f"))), S["bullet"], bulletText="•"))
            elif tt == "table":
                w = col_weights(b)
                data = [[Paragraph(esc(c), S["cellh"]) for c in b["cols"]]]
                cmds = [("BACKGROUND", (0, 0), (-1, 0), hx(NAVY)), ("GRID", (0, 0), (-1, -1), 0.4, hx("E5D9CC")), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4), ("TOPPADDING", (0, 0), (-1, -1), 3), ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, hx("FBF6F0")])]
                for ri, row in enumerate(b["rows"], start=1):
                    line = []
                    for ci, c in enumerate(row):
                        text, _ = cell_text(c)
                        style = S["cellb"] if (ci == 0 and not c.get("f") and len(b["cols"]) <= 3) else S["cell"]
                        line.append(Paragraph(rich(text, bool(c.get("f"))), style))
                        if M.needs_fill(c):
                            cmds.append(("BACKGROUND", (ci, ri), (ci, ri), hx("FFF6DA")))
                    data.append(line)
                tb = Table(data, colWidths=[avail * x for x in w], repeatRows=1)
                tb.setStyle(TableStyle(cmds))
                story += [tb, Spacer(1, 8)]
    dt.multiBuild(story, canvasmaker=NumberedCanvas)
    return buf.getvalue()


# ================================================================== bundle
EXPORTERS = {"pdf": export_pdf, "docx": export_docx, "xlsx": export_xlsx, "html": export_html}
MIMES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "html": "text/html",
}


def export_all(doc, meta, include_guidance=False):
    return {ext: fn(doc, meta, include_guidance) for ext, fn in EXPORTERS.items()}
