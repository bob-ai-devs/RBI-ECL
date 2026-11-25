"""
Convert the reference ECL Model Development Document (.docx) templates into the
JSON template format used by the Streamlit app.

    python tools/docx_to_template.py brief_documentation.docx    templates/dev_brief.json    brief
    python tools/docx_to_template.py advanced_documentation.docx templates/dev_advanced.json advanced

Conventions (same as the source templates):
  * a table cell / paragraph that is entirely "[...]"        -> blank cell, text becomes the grey hint
  * a cell that contains "[...]" together with fixed wording -> pre-filled text, placeholders still to be replaced
  * everything else                                          -> static text
"""
import json
import re
import sys

import docx
from docx.oxml.ns import qn
from docx.table import Table
from docx.text.paragraph import Paragraph

BR = re.compile(r"\[[^\]]*\]")
FORMULA_START = re.compile(r"^(ECL_i|ECL\(i\)|DF\(|Z_t|Z\(t\)|EAD_t|EAD\(t\))\s*=?")


def clean(t: str) -> str:
    t = t.replace("\u00a0", " ").replace("\r", "")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\s*\n\s*", "\n", t)
    return t.strip()


def mkcell(text: str, static: bool = False) -> dict:
    """Turn template text into a cell dict.  v=value, h=hint, f=1 when it has to be filled."""
    t = clean(text)
    if not t:
        return {"v": "", "h": "", "f": 1}
    if static:
        return {"v": t, "f": 0}
    if t.startswith("[") and t.endswith("]") and t.count("[") == 1 and t.count("]") == 1:
        return {"v": "", "h": t[1:-1].strip(), "f": 1}
    if BR.search(t):
        return {"v": t, "f": 1}
    return {"v": t, "f": 0}


def is_check(header: str) -> bool:
    return header.strip().lower() in ("done", "developer check")


def table_block(tbl: Table) -> dict:
    rows = [[clean(c.text) for c in r.cells] for r in tbl.rows]
    cols = rows[0]
    has_check = any(is_check(c) for c in cols)
    out, proto = [], []
    for ri, r in enumerate(rows[1:]):
        cells = []
        for ci, txt in enumerate(r):
            if is_check(cols[ci]):
                cells.append({"k": "chk", "v": "", "f": 1, "lbl": "Completed" if "completed" in txt.lower() else ""})
            else:
                cells.append(mkcell(txt, static=has_check))
        out.append(cells)
        if ri == 0:
            proto = [c.get("h", "") for c in cells]
    return {"t": "table", "cols": cols, "rows": out, "proto": proto}


def lead_bold_label(p: Paragraph):
    """Return (label, rest) when the paragraph starts with a bold label."""
    label, i = "", 0
    runs = list(p.runs)
    while i < len(runs) and runs[i].bold:
        label += runs[i].text
        i += 1
    rest = "".join(r.text for r in runs[i:])
    lab = clean(label)
    if lab and "[" not in lab and len(lab) < 90 and not FORMULA_START.match(lab):
        return lab, clean(rest)
    return "", clean(p.text)


def convert(path: str, depth: str) -> dict:
    d = docx.Document(path)
    doc = {
        "kind": "development",
        "depth": depth,
        "title": "ECL Model Development Document (MDD)",
        "subtitle": "",
        "howto": "",
        "footer": "ECL Model Development Document – Template  |  Confidential – internal use only",
        "sections": [],
    }
    cur = None

    def new_section(title, rep=False):
        nonlocal cur
        cur = {"title": title, "goal": "", "rep": rep, "blocks": []}
        doc["sections"].append(cur)

    for el in d.element.body.iterchildren():
        tag = el.tag.split("}")[1]
        if tag == "tbl":
            tb = Table(el, d)
            if len(tb.rows) == 1 and len(tb.columns) == 1:
                txt = clean(tb.cell(0, 0).text)
                up = txt.upper()
                if up.startswith("ENTERPRISE MODEL RISK"):
                    doc["subtitle"] = txt.split("\n")[-1].strip()
                elif "HOW TO USE" in up:
                    lines = [l.lstrip("• ").strip() for l in txt.split("\n")[1:]]
                    doc["howto"] = "\n".join(l for l in lines if l)
                elif up.startswith("DEVELOPER INSTRUCTIONS") and cur is not None:
                    lines = [l.lstrip("• ").strip() for l in txt.split("\n")[1:]]
                    cur["goal"] = "\n".join(l for l in lines if l)
                continue
            if cur is None:
                new_section("0. Document Control")
            cur["blocks"].append(table_block(tb))
            continue
        if tag != "p":
            continue
        p = Paragraph(el, d)
        txt = clean(p.text)
        if not txt:
            continue
        st = p.style.name
        if st == "Title":
            continue
        if st == "Subtitle":
            doc["subtitle"] = txt
            continue
        if st == "Heading 1":
            new_section(txt, rep=txt.startswith("5.") and depth == "advanced")
            continue
        if st == "Heading 2":
            if cur is None:
                new_section("0. " + txt)
            elif txt.lower().startswith("appendix"):
                new_section(txt)
            else:
                cur["blocks"].append({"t": "h", "text": txt})
            continue
        if txt.upper().startswith("HOW TO USE THIS TEMPLATE"):
            doc["howto"] = re.sub(r"^how to use this template:\s*", "", txt, flags=re.I)
            continue
        if txt.startswith("Section goal:"):
            if cur is not None:
                cur["goal"] = txt[len("Section goal:"):].strip()
            continue
        if txt.upper().startswith("CONFIDENTIAL") or "Confidential – internal use only" in txt:
            doc["footer"] = txt
            continue
        if cur is None:
            continue
        numpr = el.find(".//" + qn("w:numPr")) is not None
        runs = [r for r in p.runs if r.text.strip()]
        all_italic = bool(runs) and all(r.italic for r in runs)
        if st == "Source Code" or FORMULA_START.match(txt):
            cur["blocks"].append({"t": "formula", "c": {"v": txt, "f": 0}})
        elif numpr or st in ("List Bullet", "Compact num"):
            lab, rest = lead_bold_label(p)
            cur["blocks"].append({"t": "list", "items": [{"label": lab, "c": mkcell(rest)}]})
        elif all_italic:
            cur["blocks"].append({"t": "note", "text": txt})
        else:
            lab, rest = lead_bold_label(p)
            if lab and not rest:
                cur["blocks"].append({"t": "h3", "text": lab.rstrip(":")})
            else:
                cur["blocks"].append({"t": "para", "label": lab, "c": mkcell(rest)})

    # merge consecutive single-item list blocks
    for s in doc["sections"]:
        merged = []
        for b in s["blocks"]:
            if b["t"] == "list" and merged and merged[-1]["t"] == "list":
                merged[-1]["items"].extend(b["items"])
            else:
                merged.append(b)
        s["blocks"] = merged
    return doc


def stats(doc):
    n_cells = n_fill = 0
    for s in doc["sections"]:
        for b in s["blocks"]:
            if b["t"] == "table":
                cells = [c for r in b["rows"] for c in r]
            elif b["t"] == "list":
                cells = [i["c"] for i in b["items"]]
            elif b["t"] in ("para", "formula"):
                cells = [b["c"]]
            else:
                cells = []
            n_cells += len(cells)
            n_fill += sum(1 for c in cells if c.get("f"))
    return n_cells, n_fill


if __name__ == "__main__":
    src, dst, depth = sys.argv[1:4]
    out = convert(src, depth)
    with open(dst, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    nc, nf = stats(out)
    print(f"{dst}: {len(out['sections'])} sections, {nc} cells, {nf} to-fill")
