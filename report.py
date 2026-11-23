"""BoB ECL Reporting Studio: Development + Validation documents per RBI ECL Directions, 2026 (27 Apr 2026)."""
import io, json, datetime as dt, html as H
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="BoB ECL Reporting Studio", page_icon="🟧", layout="wide")
V, O, G, B = "#E8461F", "#F7941D", "#FDB913", "#1B3F8F"
try:
    MODEL = st.secrets.get("GEMINI_MODEL", "gemini-2.5-flash")
except Exception:
    MODEL = "gemini-flash-lite-latest"
import tempfile
HTML = r'''<!doctype html><html><head><meta charset="utf-8"><style>
:root{--v:#E8461F;--o:#F7941D;--g:#FDB913;--b:#1B3F8F;--ink:#1c2233;--mut:#6b7385;--ln:#e3dfd8}
*{box-sizing:border-box}body{margin:0;font:14px/1.5 "Segoe UI",system-ui,sans-serif;color:var(--ink);background:#fff}
[contenteditable]{outline:none;white-space:pre-wrap;border-radius:2px}[contenteditable]:focus{box-shadow:0 0 0 2px var(--g)}
.hd{background:var(--v);color:#fff;padding:20px 26px 16px;border-bottom:6px solid var(--g)}
.hd h1{margin:2px 0 0;font:700 25px Georgia,serif}.k{font-size:12px;color:#ffe9d6}
.meta{display:flex;gap:16px;flex-wrap:wrap;margin-top:10px}.meta label{font-size:12px;color:#ffe9d6}
.meta span{display:inline-block;min-width:80px;padding:2px 8px;background:rgba(255,255,255,.18);color:#fff}
.bar{height:8px;background:rgba(255,255,255,.3);border-radius:4px;margin-top:14px}.bar i{display:block;height:100%;background:var(--g);border-radius:4px;width:0;transition:width .3s}
.wrap{padding:0 22px}.sec{margin-top:20px;border:1px solid var(--ln);border-left:6px solid var(--b)}
.st{display:flex;align-items:center;gap:10px;background:#eef2fb;padding:8px 12px}
.st b{background:var(--b);color:#fff;padding:1px 9px}.st .t{flex:1;font:700 16px Georgia,serif;color:var(--b)}
table{width:100%;border-collapse:collapse}th{text-align:left;font-size:12px;color:var(--mut);padding:6px 10px;border-bottom:1px solid var(--ln)}
td{vertical-align:top;padding:8px 10px;border-bottom:1px solid #f0ede8}td.r{width:11%;color:var(--v);font-weight:600}td.q{width:33%}td.a{width:38%}
.c{min-height:44px;padding:4px 6px;border-bottom:2px dashed var(--g);background:#fffdf5}
select{font:inherit;padding:3px;border:1px solid var(--ln);background:#fff}
button{cursor:pointer;font:inherit;border:0;padding:6px 12px;border-radius:3px}
.add{background:var(--o);color:#fff;margin:8px 10px}.del{background:none;color:var(--v);font-size:20px;padding:0 6px}
.addsec{background:var(--b);color:#fff;margin:18px 0 26px}
</style></head><body><div id="app"></div><script>
const S=(t,o)=>parent.postMessage(Object.assign({isStreamlitMessage:true,type:t},o),"*");
let doc=null,cur="";
const uid=()=>Math.random().toString(36).slice(2,8);
const esc=s=>String(s==null?"":s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const ST=["Open","In progress","Done","N/A"];
const fit=()=>S("streamlit:setFrameHeight",{height:document.body.scrollHeight+10});
const push=()=>{cur=JSON.stringify(doc);S("streamlit:setComponentValue",{value:doc,dataType:"json"});fit()};
const blank=()=>({id:uid(),ref:"",req:"",resp:"",status:"Open"});
function prog(){let n=0,d=0;doc.sections.forEach(s=>s.rows.forEach(r=>{n++;if((r.resp||"").trim())d++}));
 const p=n?Math.round(100*d/n):0;document.getElementById("pg").style.width=p+"%";
 document.getElementById("pt").textContent=d+" of "+n+" rows filled ("+p+"%)"}
function draw(){
 const m=doc.meta||{};
 let h='<div class="hd"><div class="k">Bank of Baroda, RBI ECL Directions 2026 (issued 27 April 2026)</div><h1 contenteditable data-t="title">'+esc(doc.title)+'</h1><div class="meta">'
  +Object.keys(m).map(k=>'<label>'+esc(k)+' <span contenteditable data-m="'+esc(k)+'">'+esc(m[k])+'</span></label>').join("")
  +'</div><div class="bar"><i id="pg"></i></div><div class="k" id="pt" style="margin-top:6px"></div></div><div class="wrap">';
 doc.sections.forEach((s,i)=>{
  h+='<div class="sec"><div class="st"><b>'+(i+1)+'</b><span class="t" contenteditable data-s="'+i+'" data-f="title">'+esc(s.title)+'</span><button class="del" title="Delete section" data-act="ds" data-s="'+i+'">&times;</button></div>'
   +'<table><tr><th>Reference</th><th>Requirement</th><th>Response (fill in)</th><th>Status</th><th></th></tr>';
  s.rows.forEach((r,j)=>{const a=' data-s="'+i+'" data-r="'+j+'"';
   h+='<tr><td class="r"><div contenteditable'+a+' data-f="ref">'+esc(r.ref)+'</div></td>'
    +'<td class="q"><div contenteditable'+a+' data-f="req">'+esc(r.req)+'</div></td>'
    +'<td class="a"><div class="c" contenteditable'+a+' data-f="resp">'+esc(r.resp)+'</div></td>'
    +'<td><select'+a+' data-f="status">'+ST.map(x=>'<option'+(x==r.status?' selected':'')+'>'+x+'</option>').join("")+'</select></td>'
    +'<td><button class="del" title="Delete row" data-act="dr"'+a+'>&times;</button></td></tr>'});
  h+='</table><button class="add" data-act="ar" data-s="'+i+'">+ Add row</button></div>'});
 h+='<button class="addsec" data-act="as">+ Add section</button></div>';
 document.getElementById("app").innerHTML=h;prog();fit()}
document.addEventListener("input",e=>{const t=e.target,d=t.dataset;if(!doc||!d)return;
 if(d.t)doc.title=t.innerText;else if(d.m)doc.meta[d.m]=t.innerText;
 else if(d.f){const s=doc.sections[+d.s];if(d.r!==undefined)s.rows[+d.r][d.f]=t.innerText;else s.title=t.innerText}
 prog()});
document.addEventListener("focusout",e=>{if(doc&&e.target.isContentEditable)push()});
document.addEventListener("change",e=>{const t=e.target;if(doc&&t.tagName=="SELECT"){doc.sections[+t.dataset.s].rows[+t.dataset.r].status=t.value;push()}});
document.addEventListener("click",e=>{const b=e.target.closest("[data-act]");if(!b||!doc)return;
 const i=+b.dataset.s,j=+b.dataset.r,a=b.dataset.act;
 if(a=="ds")doc.sections.splice(i,1);
 if(a=="dr")doc.sections[i].rows.splice(j,1);
 if(a=="ar")doc.sections[i].rows.push(blank());
 if(a=="as")doc.sections.push({id:uid(),title:"New section",rows:[blank()]});
 draw();push()});
addEventListener("message",e=>{if(e.data.type!=="streamlit:render")return;
 const js=JSON.stringify(e.data.args.doc);if(js!==cur){doc=JSON.parse(js);cur=js;draw()}});
S("streamlit:componentReady",{apiVersion:1});
</script></body></html>
'''
_D = Path(tempfile.gettempdir()) / "ecl_doc_component"
_D.mkdir(exist_ok=True)
(_D / "index.html").write_text(HTML, encoding="utf-8")
_C = components.declare_component("ecl_doc", path=str(_D))

st.markdown("""<style>
.hero{background:__V__;color:#fff;padding:20px 28px;border-bottom:6px solid __G__;margin:-1rem -1rem 1rem}
.hero h1{font:700 30px Georgia,serif;margin:0;color:#fff}.hero p{margin:4px 0 0;color:#ffe9d6}
.stTabs [aria-selected="true"]{color:__V__!important}.stTabs [data-baseweb="tab-highlight"]{background:__V__!important}
.stButton>button,.stDownloadButton>button{background:__B__;color:#fff;border:0;border-radius:3px}
.stButton>button:hover,.stDownloadButton>button:hover{background:__V__;color:#fff}
section[data-testid=stSidebar]{background:#eef2fb}
</style>""".replace("__V__", V).replace("__G__", G).replace("__B__", B), unsafe_allow_html=True)

# ---------------------------------------------------------------- templates
def mk(k, tab, title, secs):
    meta = {"Version": "0.1", "Owner": "", "Date": dt.date.today().isoformat(), "Model": ""}
    return {"tab": tab, "title": title, "meta": meta, "sections": [
        {"id": f"{k}{i}", "title": t, "rows": [
            {"id": f"{k}{i}.{j}", "ref": r, "req": q, "resp": "", "status": "Open"} for j, (r, q) in enumerate(rows)]}
        for i, (t, rows) in enumerate(secs)]}

DEV = [
 ("Scope, governance and policy", [
  ("Ch. I-III", "Instruments in scope (loans, debt securities, commitments, off-balance-sheet exposures) and exclusions / carve-outs (SLR investments, central-government claims)."),
  ("Ch. III", "Board-approved ECL policy; oversight by a committee including CFO and CRO; effective date 1 April 2027."),
  ("Ch. V", "Model inventory entry: owner, developer, risk tier, dependencies, validation status.")]),
 ("Staging and SICR", [
  ("Ch. II / III", "Stage 3 = NPA (borrower level); automated NPA flags; treatment of accounts that were NPA on 31 March 2027."),
  ("Para 26-27, Annex 1", "SICR definition versus origination and the parameters used (ratings, behavioural score, watch-list, collateral, covenants) with thresholds."),
  ("Para 33", "Rebuttable presumption: more than 30 days past due; revolving facility over limit / drawing power up to 60 days; rebuttal evidence standard."),
  ("Ch. III", "Collective SICR segmentation, Stage 2 at facility level, upgrade rules from Stage 3 and Stage 2.")]),
 ("PD, LGD and EAD", [
  ("Ch. III", "12-month PD (Stage 1) and lifetime PD (Stage 2): data, segmentation, model form, calibration, 0.03% floor on 12-month PD."),
  ("Ch. III", "LGD: recovery and cure estimation, discounting; backstops 65% secured / 70% unsecured; 30% for cash, gold, government securities, LIC policy, KVP, NSC."),
  ("Ch. III", "EAD and CCF for undrawn limits and off-balance-sheet items; credit risk mitigants not netted from EAD.")]),
 ("Forward-looking scenarios", [
  ("Ch. III", "Macroeconomic variables, at least three scenarios (base, upside, downside), probability weights and their basis."),
  ("Ch. V", "Link from macro variables to PD and LGD; horizon beyond forecasts for lifetime ECL; country risk and unhedged FX exposure.")]),
 ("Prudential floors and overlays", [
  ("Ch. III", "Product-wise Stage 1 and Stage 2 floors; final allowance = higher of model ECL and floor."),
  ("Ch. III", "Stage 3 time-based floors applied at account level; additional 5% for wilful defaulters; management overlay treatment.")]),
 ("EIR, POCI and income recognition", [
  ("Ch. IV", "EIR determination (fees, costs, premiums); floating-rate re-estimation; migration of pre-April 2027 loans by 31 March 2030."),
  ("Ch. III", "POCI assets: credit-adjusted EIR, lifetime ECL; cash-basis income for Stage 3 / POCI.")]),
 ("Data, automation and transition", [
  ("Annex 3", "Data sources, lineage and quality checks; straight-through processing of staging and ECL; manual-override approvals; exception logs kept 3 years."),
  ("Transition", "Day 1 fair valuation, transitional adjustment = max(0, ECL on 1 Apr 2027 minus IRAC provisions on 31 Mar 2027), CET1 add-back schedule.")]),
]
VAL = [
 ("Independence and governance", [
  ("Ch. V", "Validator independence from developers; three-line model risk structure; validation frequency by risk tier."),
  ("Ch. V", "Third-party / vendor models: documentation access and RBI supervisory evaluation rights.")]),
 ("Conceptual soundness and data", [
  ("Ch. V", "Review of methodology, assumptions and limitations against the Development document."),
  ("Ch. III / V", "Data completeness, accuracy, representativeness; treatment of missing data and proxies.")]),
 ("Staging and SICR validation", [
  ("Para 26-33", "Back-test SICR triggers; stability of stage migrations; sample review of rebuttals of the 30-day / 60-day presumption."),
  ("Ch. II", "Reconciliation of Stage 3 population to NPA register at borrower level.")]),
 ("PD, LGD and EAD performance", [
  ("Ch. V", "Back-testing and benchmarking of 12-month and lifetime PD, LGD and EAD / CCF; discriminatory power and calibration."),
  ("Ch. III", "Use of 0.03% PD floor and 65% / 70% LGD backstops; sensitivity analysis.")]),
 ("Scenarios and overlays", [
  ("Ch. III / V", "Reasonableness of scenarios, probability weights and macro linkage; overlay approvals and expiry."),
  ("Ch. III", "Management overlays and floating-provision utilisation.")]),
 ("Floors, reconciliation and outputs", [
  ("Ch. III", "Independent recomputation of ECL for a sample; correct application of Stage 1-3 floors."),
  ("Ch. VI, Annex 4", "Roll-forward of allowances by stage; credit-quality tables; disclosure completeness.")]),
 ("Controls, reporting and sign-off", [
  ("Annex 3", "System controls, audit trail, STP and exception logs."),
  ("Reporting", "Quarterly ECL reporting from 30 June 2027 and parallel IRACP reporting until 31 December 2027 are supported."),
  ("Ch. V", "Findings, severity, remediation owner and date; overall validation conclusion and sign-off.")]),
]

def fresh():
    return {"dev": mk("d", "Development", "ECL Model Development Document", DEV),
            "val": mk("v", "Validation", "ECL Model Validation Document", VAL)}

if "docs" not in st.session_state:
    st.session_state.docs, st.session_state.ver = fresh(), {"dev": 0, "val": 0}

# ---------------------------------------------------------------- Gemini
PROMPT = """You are a model-risk documentation analyst at an Indian bank. The RBI (Commercial Banks - Asset Classification, Provisioning and Income Recognition) Directions, 2026, dated 27 April 2026, require ECL models to be documented and independently validated.
Read the source code below and complete the DEVELOPMENT and VALIDATION document rows.
Rules: use only facts evidenced in the code (functions, constants, thresholds, formulas) and name the function or constant; if the code gives no evidence write exactly "NOT EVIDENCED IN CODE - owner to complete"; for validation rows say what a validator can test and flag gaps or deviations from the Directions; at most 90 words per row.
Return ONLY JSON: {"development": {"<row id>": "<text>"}, "validation": {"<row id>": "<text>"}}
ROWS:
%s
CODE:
%s"""

def code_text(up):
    raw = up.getvalue().decode("utf-8", "ignore")
    if up.name.endswith(".ipynb"):
        nb = json.loads(raw)
        raw = "\n\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
    return raw[:60000]

def gemini_fill(code, overwrite):
    from google import genai
    from google.genai import types
    D = st.session_state.docs
    rows = {n: {r["id"]: r["req"] for s in D[k]["sections"] for r in s["rows"] if overwrite or not r["resp"].strip()}
            for n, k in (("development", "dev"), ("validation", "val"))}
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"], http_options=types.HttpOptions(api_version="v1beta"))
    out = client.models.generate_content(model=MODEL, contents=PROMPT % (json.dumps(rows, indent=1), code),
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2))
    res = json.loads(out.text)
    for n, k in (("development", "dev"), ("validation", "val")):
        for s in D[k]["sections"]:
            for r in s["rows"]:
                if r["id"] in res.get(n, {}):
                    r["resp"] = str(res[n][r["id"]])
        st.session_state.ver[k] += 1

with st.sidebar:
    st.header("Gemini assistant")
    up = st.file_uploader("Upload model code", type=["py", "ipynb", "txt", "sql", "r", "sas"])
    over = st.checkbox("Overwrite rows that already have text", False)
    if st.button("Read code and fill both documents", disabled=up is None):
        try:
            with st.spinner("Gemini is reading the code..."):
                gemini_fill(code_text(up), over)
            st.toast("Both documents updated. Review and edit every row.")
        except KeyError:
            st.error("Add GEMINI_API_KEY to .streamlit/secrets.toml (or Streamlit Cloud secrets).")
        except Exception as e:
            st.error(f"Gemini call failed: {e}")
    st.divider()
    if st.button("Reset both documents"):
        st.session_state.docs = fresh()
        st.session_state.ver = {k: v + 1 for k, v in st.session_state.ver.items()}
        st.rerun()
    st.caption("Generated text is a draft. Verify against the RBI Directions before use.")

# ---------------------------------------------------------------- exports
COLS = ["Ref", "Requirement", "Response", "Status"]
def meta_line(d): return ", ".join(f"{k}: {v}" for k, v in d["meta"].items() if v)

def to_html(docs):
    e = H.escape
    css = (f"body{{font:14px/1.5 'Segoe UI',sans-serif;margin:0}}header{{background:{V};color:#fff;padding:18px 28px;border-bottom:6px solid {G}}}"
           f"h1{{font:700 24px Georgia,serif;margin:0}}main{{padding:0 28px 30px}}h2{{color:{B};font:700 17px Georgia,serif;border-left:6px solid {B};padding-left:10px;margin-top:26px}}"
           f"table{{width:100%;border-collapse:collapse}}th{{background:{B};color:#fff;text-align:left;padding:6px}}td{{border-bottom:1px solid #e6e2da;padding:6px;vertical-align:top;white-space:pre-wrap}}")
    body = ""
    for d in docs:
        body += f"<header><h1>{e(d['title'])}</h1><div>{e(meta_line(d))}</div></header><main>"
        for i, s in enumerate(d["sections"], 1):
            body += f"<h2>{i}. {e(s['title'])}</h2><table><tr>" + "".join(f"<th>{c}</th>" for c in COLS) + "</tr>"
            body += "".join("<tr>" + "".join(f"<td>{e(r[k])}</td>" for k in ("ref", "req", "resp", "status")) + "</tr>" for r in s["rows"]) + "</table>"
        body += "</main>"
    return f"<!doctype html><meta charset='utf-8'><title>ECL report</title><style>{css}</style>{body}".encode()

def to_docx(docs):
    from docx import Document
    doc = Document()
    for n, d in enumerate(docs):
        if n: doc.add_page_break()
        doc.add_heading(d["title"], 0)
        doc.add_paragraph(meta_line(d))
        for i, s in enumerate(d["sections"], 1):
            doc.add_heading(f"{i}. {s['title']}", 1)
            t = doc.add_table(rows=1, cols=4); t.style = "Light Grid Accent 1"
            for c, x in zip(t.rows[0].cells, COLS): c.text = x
            for r in s["rows"]:
                for c, k in zip(t.add_row().cells, ("ref", "req", "resp", "status")): c.text = r[k]
    b = io.BytesIO(); doc.save(b); return b.getvalue()

def to_pdf(docs):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, PageBreak
    ss = getSampleStyleSheet(); body = ss["BodyText"]; body.fontSize = 8; body.leading = 10
    P = lambda x: Paragraph(H.escape(x or "-").replace("\n", "<br/>"), body)
    out, flow = io.BytesIO(), []
    for n, d in enumerate(docs):
        if n: flow.append(PageBreak())
        flow += [Paragraph(H.escape(d["title"]), ss["Title"]), Paragraph(H.escape(meta_line(d)), body)]
        for i, s in enumerate(d["sections"], 1):
            flow.append(Paragraph(f"{i}. {H.escape(s['title'])}", ss["Heading2"]))
            data = [COLS] + [[P(r[k]) for k in ("ref", "req", "resp", "status")] for r in s["rows"]]
            t = Table(data, colWidths=[62, 170, 230, 55], repeatRows=1)
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(B)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                   ("GRID", (0, 0), (-1, -1), .3, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
            flow.append(t)
    SimpleDocTemplate(out, pagesize=A4, leftMargin=30, rightMargin=30, topMargin=30, bottomMargin=30).build(flow)
    return out.getvalue()

def to_xlsx(docs):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    wb = Workbook(); wb.remove(wb.active)
    for d in docs:
        ws = wb.create_sheet(d["tab"]); ws.append([d["title"]]); ws.append([meta_line(d)]); ws["A1"].font = Font(bold=True, size=14)
        for w, c in zip((14, 60, 70, 14), "ABCD"): ws.column_dimensions[c].width = w
        for s in d["sections"]:
            ws.append([]); ws.append([s["title"]])
            for c in ws[ws.max_row]: c.fill = PatternFill("solid", fgColor=G[1:]); c.font = Font(bold=True)
            ws.append(COLS)
            for c in ws[ws.max_row]: c.fill = PatternFill("solid", fgColor=B[1:]); c.font = Font(bold=True, color="FFFFFF")
            for r in s["rows"]: ws.append([r["ref"], r["req"], r["resp"], r["status"]])
        for row in ws.iter_rows():
            for c in row: c.alignment = Alignment(wrap_text=True, vertical="top")
    b = io.BytesIO(); wb.save(b); return b.getvalue()

# ---------------------------------------------------------------- UI
st.markdown("<div class='hero'><h1>ECL Reporting Studio</h1><p>Development and Validation documents for the RBI ECL Directions, 2026 (27 April 2026, effective 1 April 2027)</p></div>", unsafe_allow_html=True)
tabs = st.tabs(["Development document", "Validation document", "Export reports"])
for tab, k in zip(tabs[:2], ("dev", "val")):
    with tab:
        v = _C(doc=st.session_state.docs[k], key=f"c_{k}_{st.session_state.ver[k]}", default=None)
        if v: st.session_state.docs[k] = v
with tabs[2]:
    pick = st.radio("Document", ["Development", "Validation", "Both"], horizontal=True)
    D = st.session_state.docs
    docs = {"Development": [D["dev"]], "Validation": [D["val"]], "Both": [D["dev"], D["val"]]}[pick]
    stamp = dt.date.today().strftime("%Y%m%d"); base = f"BoB_ECL_{pick}_{stamp}"
    c = st.columns(4)
    c[0].download_button("PDF", to_pdf(docs), base + ".pdf", "application/pdf")
    c[1].download_button("Word (.docx)", to_docx(docs), base + ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    c[2].download_button("Excel (.xlsx)", to_xlsx(docs), base + ".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    c[3].download_button("Standalone HTML", to_html(docs), base + ".html", "text/html")
