"""
Document model shared by the editor component, the AI layer and the exporters.

A document is plain JSON:
    {kind, depth, title, subtitle, howto, footer, sections:[{title, goal, rep, copy?, blocks:[...]}]}

Blocks:  h | h3 | note | formula | para | list | table
Cells :  {v: value, h: hint, f: 1 if it has to be filled, a: 1 if drafted by AI, k: 'chk' for tick boxes}
"""
import copy
import json
import re
from functools import lru_cache
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
PLACEHOLDER = re.compile(r"\[[^\]]*\]")

KINDS = {"development": "Development Document", "validation": "Validation Document"}
DEPTHS = {"brief": "Standard", "advanced": "Advanced"}   # "brief" is the internal key of the Standard templates
PREFIX = {"development": "dev", "validation": "val"}


# ------------------------------------------------------------------ templates
@lru_cache(maxsize=8)
def _load(kind: str, depth: str) -> str:
    path = TEMPLATE_DIR / f"{PREFIX[kind]}_{depth}.json"
    return path.read_text(encoding="utf-8")


def load_template(kind: str, depth: str) -> dict:
    """Fresh, blank copy of a template."""
    return json.loads(_load(kind, depth))


def rep_templates(doc: dict) -> dict:
    """Pristine copies of repeatable sections (e.g. 'copy section 5 once per PD / LGD / EAD model')."""
    base = load_template(doc["kind"], doc["depth"])
    return {s["title"]: s for s in base["sections"] if s.get("rep")}


# ------------------------------------------------------------------ cells
def needs_fill(c: dict) -> bool:
    if not c.get("f"):
        return False
    if c.get("k") == "chk":
        return c.get("v") != "Y"
    v = (c.get("v") or "").strip()
    return v == "" or bool(PLACEHOLDER.search(v))


def _block_cells(b: dict):
    """Yield (ri, ci, cell) for every cell in a block."""
    t = b["t"]
    if t == "table":
        for ri, row in enumerate(b["rows"]):
            for ci, c in enumerate(row):
                yield ri, ci, c
    elif t == "list":
        for ri, it in enumerate(b["items"]):
            yield ri, 0, it["c"]
    elif t in ("para", "formula"):
        yield 0, 0, b["c"]


def iter_cells(doc: dict):
    for si, s in enumerate(doc["sections"]):
        for bi, b in enumerate(s["blocks"]):
            for ri, ci, c in _block_cells(b):
                yield si, bi, ri, ci, c


def completion(doc: dict):
    """(filled, total) over cells that were meant to be filled."""
    total = filled = 0
    for *_, c in iter_cells(doc):
        if c.get("f"):
            total += 1
            if not needs_fill(c):
                filled += 1
    return filled, total


def pct(doc: dict) -> int:
    f, t = completion(doc)
    return round(100 * f / t) if t else 100


def ai_cell_count(doc: dict) -> int:
    return sum(1 for *_, c in iter_cells(doc) if c.get("a"))


# ------------------------------------------------------------------ AI hand-off
def _short(s, n=150):
    s = re.sub(r"\s+", " ", s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def open_cells(doc: dict):
    """Cells the AI may fill, with enough context to write a precise answer."""
    out = []
    for si, s in enumerate(doc["sections"]):
        heading = ""
        for bi, b in enumerate(s["blocks"]):
            if b["t"] in ("h", "h3"):
                heading = b["text"]
                continue
            if b["t"] == "table":
                cols = b["cols"]
                for ri, row in enumerate(b["rows"]):
                    static = [c["v"] for c in row if not c.get("f") and c.get("v")]
                    rowctx = " / ".join(_short(x, 70) for x in static[:3])
                    for ci, c in enumerate(row):
                        if c.get("k") == "chk" or not needs_fill(c):
                            continue
                        out.append({
                            "id": f"{si}.{bi}.{ri}.{ci}", "section": s["title"], "heading": heading,
                            "row": rowctx, "field": cols[ci], "current": _short(c.get("v"), 300),
                            "hint": _short(c.get("h"), 160),
                        })
            elif b["t"] == "para":
                c = b["c"]
                if needs_fill(c):
                    out.append({"id": f"{si}.{bi}.0.0", "section": s["title"], "heading": heading, "row": "",
                                "field": b.get("label") or "paragraph", "current": _short(c.get("v"), 600),
                                "hint": _short(c.get("h"), 200)})
            elif b["t"] == "list":
                for ri, it in enumerate(b["items"]):
                    c = it["c"]
                    if needs_fill(c):
                        out.append({"id": f"{si}.{bi}.{ri}.0", "section": s["title"], "heading": heading, "row": "",
                                    "field": it.get("label") or "bullet", "current": _short(c.get("v"), 400),
                                    "hint": _short(c.get("h"), 200)})
    return out


def apply_fill(doc: dict, mapping: dict) -> int:
    """Write AI text into the document. Returns number of cells updated."""
    n = 0
    for si, bi, ri, ci, c in iter_cells(doc):
        key = f"{si}.{bi}.{ri}.{ci}"
        if key in mapping and c.get("k") != "chk":
            val = str(mapping[key]).strip()
            if val:
                c["v"] = val
                c["a"] = 1
                n += 1
    return n


def clone(doc: dict) -> dict:
    return copy.deepcopy(doc)


def file_stem(kind: str, depth: str) -> str:
    return f"ECL_{KINDS[kind].split()[0]}_{DEPTHS[depth]}"
