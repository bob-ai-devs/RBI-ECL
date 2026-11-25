"""
ECL Documentation Studio – Bank of Baroda theme
Strict Model Development + Model Validation documents for the RBI ECL Directions, 2026 (27 April 2026).

Hosting: GitHub -> Streamlit Community Cloud. Nothing is written to disk: reports live in st.session_state
until Clear is pressed or a new code file is uploaded; exports are built in memory.
"""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from core import ai, exporters, model as M
from core.theme import CSS, hero

ROOT = Path(__file__).resolve().parent
IST = timezone(timedelta(hours=5, minutes=30))
DEMO = ROOT / "demo_code" / "demo_ecl_model.py"

st.set_page_config(page_title="ECL Documentation Studio · Bank of Baroda", page_icon="🟠", layout="wide")
st.markdown(CSS, unsafe_allow_html=True)

_editor = components.declare_component("ecl_doc_editor", path=str(ROOT / "components" / "doc_editor"))

# Validation Document is switched off for now. To bring it back, uncomment "validation" below.
ENABLED_KINDS = [
    "development",
    # "validation",
]
LABEL = {f"{k}|{d}": f"{M.KINDS[k]} · {M.DEPTHS[d]}" for k in ENABLED_KINDS for d in M.DEPTHS}


# ------------------------------------------------------------------ state
def init():
    ss = st.session_state
    ss.setdefault("reports", {})      # "kind|depth" -> {doc, rev, seq, meta}
    ss.setdefault("code", None)       # {names, hash, corpus, truncated, chars}
    ss.setdefault("digest", None)     # evidence digest for ss.code
    ss.setdefault("exports", {})
    ss.setdefault("uploader_key", 0)
    ss.setdefault("confirm", None)
    ss.setdefault("view", None)
    ss.setdefault("context", "")
    ss.setdefault("manual_key", "")


def clear_all():
    ss = st.session_state
    ss.reports, ss.code, ss.digest, ss.exports, ss.confirm, ss.view = {}, None, None, {}, None, None
    ss.uploader_key += 1


def now_str():
    return datetime.now(IST).strftime("%d-%b-%Y %H:%M IST")


def api_key():
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        try:
            if st.secrets.get(name):
                return st.secrets[name]
        except Exception:
            pass
        if os.environ.get(name):
            return os.environ[name]
    return st.session_state.manual_key.strip()


def set_code(files):
    """files: list of (name, bytes). A different fingerprint = a new upload -> reports are cleared."""
    ss = st.session_state
    fp = ai.fingerprint(files)
    if ss.code and ss.code["hash"] == fp:
        return
    texts = ai.read_uploads(files)
    corpus, truncated = ai.build_corpus(texts)
    if ss.code is not None or ss.reports:
        ss.reports, ss.exports, ss.view = {}, {}, None
    ss.code = {"names": [n for n, _ in texts], "hash": fp, "corpus": corpus, "truncated": truncated, "chars": len(corpus)}
    ss.digest = None


# ------------------------------------------------------------------ AI actions
def ensure_digest(client, status):
    ss = st.session_state
    if ss.digest is None:
        status.update(label=f"Reading your code with Gemini ({ai.MODEL})… one call, cached for all reports")
        ss.digest = ai.build_digest(client, ss.code["corpus"], ss.context)
    return ss.digest


def create_report(kind, depth):
    ss = st.session_state
    key = f"{kind}|{depth}"
    doc = M.load_template(kind, depth)
    meta = {"created": now_str(), "ai": False, "model": ai.MODEL, "filled": 0}
    k = api_key()
    if ss.code and k:
        with st.status(f"Creating {LABEL[key]} report…", expanded=True) as status:
            bar = st.progress(0.0)
            try:
                client = ai.make_client(k)
                digest = ensure_digest(client, status)
                n = ai.fill_document(client, doc, digest, ss.context,
                                     progress=lambda f, t: (bar.progress(min(f, 1.0)), status.update(label=t)))
                meta.update(ai=True, filled=n)
                status.update(label=f"{LABEL[key]} ready – {n} fields drafted by Gemini", state="complete", expanded=False)
            except Exception as e:  # keep the blank template so no work is lost
                status.update(label="Gemini call failed – blank template created instead", state="error")
                st.error(f"AI drafting failed: {e}")
    else:
        why = "no code uploaded" if not ss.code else "no Gemini API key"
        st.info(f"Created a blank strict template ({why}).")
    prev = ss.reports.get(key)
    ss.reports[key] = {"doc": doc, "rev": (prev["rev"] + 1) if prev else 1, "seq": 0, "meta": meta}
    ss.exports.pop(key, None)
    ss.view = key


def ai_fill_remaining(key):
    ss = st.session_state
    rep = ss.reports[key]
    with st.status("Drafting remaining blanks with Gemini…", expanded=True) as status:
        bar = st.progress(0.0)
        try:
            client = ai.make_client(api_key())
            digest = ensure_digest(client, status)
            n = ai.fill_document(client, rep["doc"], digest, ss.context,
                                 progress=lambda f, t: (bar.progress(min(f, 1.0)), status.update(label=t)))
            rep["meta"].update(ai=True, filled=rep["meta"].get("filled", 0) + n)
            rep["rev"] += 1
            rep["seq"] = 0
            ss.exports.pop(key, None)
            status.update(label=f"{n} more fields drafted", state="complete", expanded=False)
        except Exception as e:
            status.update(label="Gemini call failed", state="error")
            st.error(f"AI drafting failed: {e}")
            return False
    return True


# ------------------------------------------------------------------ sidebar
def sidebar():
    ss = st.session_state
    with st.sidebar:
        st.markdown("### 🟠 ECL Documentation Studio")
        st.caption("RBI ECL Directions, 2026 · issued 27 Apr 2026 · effective 1 Apr 2027")
        st.markdown("#### 1 · Upload model code")
        files = st.file_uploader("Code (.py .ipynb .sql .r .sas .txt .zip …)", accept_multiple_files=True,
                                 key=f"up{ss.uploader_key}", label_visibility="collapsed")
        if files:
            set_code([(f.name, f.getvalue()) for f in files])
        c1, c2 = st.columns(2)
        if c1.button("Use demo code", use_container_width=True):
            set_code([(DEMO.name, DEMO.read_bytes())])
        c2.download_button("Get demo code", DEMO.read_bytes(), file_name=DEMO.name, mime="text/x-python", use_container_width=True)
        if ss.code:
            st.success(f"{len(ss.code['names'])} file(s) loaded · {ss.code['chars']:,} characters")
            if ss.code["truncated"]:
                st.warning("Code was trimmed to fit the context budget.")
            with st.expander("Files read"):
                for n in ss.code["names"]:
                    st.caption(n)
        else:
            st.caption("No code loaded – templates will be created blank.")
        st.markdown("#### 2 · Context for the AI (optional)")
        ss.context = st.text_area("Entity, model name, portfolio, reference date…", value=ss.context, height=90, label_visibility="collapsed",
                                  placeholder="e.g. Bank of Baroda, retail home loans, reference date 31-Mar-2026, amounts in INR crore")
        st.markdown("#### 3 · Gemini")
        if api_key() and not ss.manual_key:
            st.success("API key found in secrets")
        else:
            ss.manual_key = st.text_input("Gemini API key (this session only)", value=ss.manual_key, type="password")
            if not api_key():
                st.caption("Add GEMINI_API_KEY to Streamlit secrets, or paste a key here.")
        st.caption(f"Model `{ai.MODEL}` · API `{ai.API_VERSION}`")
        st.divider()
        if st.button("🗑 Clear everything", use_container_width=True, help="Removes all stored reports, the uploaded code and the AI digest"):
            clear_all()
            st.rerun()
        st.caption("Reports stay in this browser session until you press Clear or upload different code. Nothing is saved to disk.")


# ------------------------------------------------------------------ main sections
def tiles_html(container):
    ss = st.session_state
    with container:
        cols = st.columns(len(LABEL))
        for col, key in zip(cols, LABEL):
            rep = ss.reports.get(key)
            if rep:
                p = M.pct(rep["doc"])
                tag = "AI-drafted" if rep["meta"]["ai"] else "Blank template"
                body = f'<div class="pc">{p}%</div><div class="st">{tag} · {rep["meta"]["created"]}</div><div class="bar"><i style="width:{p}%"></i></div>'
            else:
                body = '<div class="st">Not created yet</div>'
            col.markdown(f'<div class="tile {"on" if rep else ""}"><b>{LABEL[key]}</b>{body}</div>', unsafe_allow_html=True)


def creation_panel():
    ss = st.session_state
    st.markdown('<h3 class="sub">Create a report</h3>', unsafe_allow_html=True)
    with st.container(border=True):
        depth_label = st.radio("Report depth", ["Standard", "Advanced"], horizontal=True,
                               help="Standard = condensed strict template. Advanced = full template aligned to the RBI Directions paragraph by paragraph.")
        depth = "brief" if depth_label == "Standard" else "advanced"   # "brief" is the internal template key
        st.caption("One report is generated per click (lower API load). Every generated report is stored in the session.")
        cols = st.columns(len(ENABLED_KINDS))
        for col, kind in zip(cols, ENABLED_KINDS):
            key = f"{kind}|{depth}"
            exists = key in ss.reports
            label = f"{'↻ Re-create' if exists else '＋ Create'} {M.KINDS[kind]} · {depth_label}"
            if col.button(label, key=f"mk-{key}", type="primary", use_container_width=True):
                if exists:
                    ss.confirm = key
                else:
                    create_report(kind, depth)
                    st.rerun()
        if ss.confirm:
            k, d = ss.confirm.split("|")
            st.warning(f"Re-creating **{LABEL[ss.confirm]}** replaces the stored report and any edits you made.")
            y, n, _ = st.columns([1, 1, 3])
            if y.button("Yes, replace", key="conf-y"):
                ss.confirm = None
                create_report(k, d)
                st.rerun()
            if n.button("Cancel", key="conf-n"):
                ss.confirm = None
                st.rerun()
        if ss.code and api_key():
            st.caption("✅ Code and API key ready – new reports are pre-filled from your code.")
        else:
            st.caption("ℹ️ Without code + API key, a blank strict template is created (still fully editable).")


def viewer():
    ss = st.session_state
    if not ss.reports:
        st.info("Create a Development or Validation report above to open the editable document here.")
        return
    keys = [k for k in LABEL if k in ss.reports]
    if ss.view not in keys:
        ss.view = keys[-1]
    st.markdown('<h3 class="sub">Open report</h3>', unsafe_allow_html=True)
    ss.view = st.radio("Stored reports", keys, index=keys.index(ss.view), format_func=lambda k: LABEL[k], horizontal=True, label_visibility="collapsed")
    key = ss.view
    rep = ss.reports[key]
    kind, depth = key.split("|")

    guidance = st.session_state.get("guidance_on", True)
    val = _editor(doc=rep["doc"], rev=rep["rev"], rep=M.rep_templates(rep["doc"]), guidance=guidance, height=860,
                  key=f"ed-{key}-{rep['rev']}", default=None)
    if val and val.get("rev") == rep["rev"] and val.get("seq", 0) > rep["seq"]:
        rep["doc"], rep["seq"] = val["doc"], val["seq"]

    st.caption("Click any cell to edit · ＋ ⧉ ✕ on each row add, duplicate or delete it (with undo) · edits sync automatically to the session.")
    a, b, c = st.columns(3)
    if a.button("✨ AI-fill remaining blanks", use_container_width=True, disabled=not (ss.code and api_key()),
                help="Sends only the still-blank cells to Gemini, using the cached code digest"):
        if ai_fill_remaining(key):
            st.rerun()
    if b.button("↺ Reset to blank template", use_container_width=True):
        rep["doc"], rep["rev"], rep["seq"] = M.load_template(kind, depth), rep["rev"] + 1, 0
        rep["meta"].update(ai=False, filled=0)
        ss.exports.pop(key, None)
        st.rerun()
    if c.button("🗑 Delete this report", use_container_width=True):
        ss.reports.pop(key, None)
        ss.exports.pop(key, None)
        ss.view = None
        st.rerun()

    export_panel(key, rep, kind, depth)


def export_panel(key, rep, kind, depth):
    ss = st.session_state
    st.markdown('<h3 class="sub">Export report</h3>', unsafe_allow_html=True)
    with st.container(border=True):
        incl = st.checkbox("Include developer guidance boxes and notes", value=False,
                           help="The source templates ask for these to be deleted before submission.")
        sig = (rep["rev"], rep["seq"], incl)
        if st.button("⚙ Build PDF · DOCX · XLSX · HTML", type="primary", key=f"build-{key}"):
            with st.spinner("Building the four formats…"):
                files = exporters.export_all(rep["doc"], rep["meta"], incl)
            ss.exports[key] = {"sig": sig, "files": files}
        ex = ss.exports.get(key)
        if ex and ex["sig"] != sig:
            st.warning("The report changed since these files were built. Rebuild to export the latest edits.")
        if ex:
            stamp = datetime.now(IST).strftime("%Y%m%d")
            cols = st.columns(4)
            for col, (ext, data) in zip(cols, ex["files"].items()):
                col.download_button(f"⬇ {ext.upper()}", data, file_name=f"{M.file_stem(kind, depth)}_{stamp}.{ext}",
                                    mime=exporters.MIMES[ext], use_container_width=True, key=f"dl-{key}-{ext}")
            st.caption(f"Unfilled placeholders stay visible as blue [bracketed hints] so exported files remain usable templates · {M.pct(rep['doc'])}% complete.")


# ------------------------------------------------------------------ page
init()
sidebar()
st.markdown(hero("ECL Documentation Studio",
                 "Strict Model Development documents (Standard and Advanced) for the RBI (Commercial Banks – Asset Classification, Provisioning and Income Recognition) "
                 "Directions, 2026. Upload model code, let Gemini draft, edit every row in the browser, export to PDF, Word, Excel and HTML."),
            unsafe_allow_html=True)
tile_box = st.container()
creation_panel()
viewer()
tiles_html(tile_box)
