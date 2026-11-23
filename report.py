"""BoB ECL Reporting Studio: Development + Validation documents per RBI ECL Directions, 2026 (27 Apr 2026)."""
import io, json, datetime as dt, html as H
from pathlib import Path
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="BoB ECL Reporting Studio", page_icon="🟧", layout="wide")
V, O, G, B = "#E8461F", "#F7941D", "#FDB913", "#1B3F8F"
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
td{vertical-align:top;padding:8px 10px;border-bottom:1px solid #f0ede8}td.r{width:9%;color:var(--v);font-weight:600}td.q{width:25%}td.a{width:29%}td.u{width:22%}
.c{min-height:44px;padding:4px 6px;border-bottom:2px dashed var(--g);background:#fffdf5}
select{font:inherit;padding:3px;border:1px solid var(--ln);background:#fff}
button{cursor:pointer;font:inherit;border:0;padding:6px 12px;border-radius:3px}
.add{background:var(--o);color:#fff;margin:8px 10px}.del{background:none;color:var(--v);font-size:20px;padding:0 6px}
.ex,.ss{background:#fff6dc;border-left:6px solid var(--g);padding:8px 12px;margin-top:16px}.ss{margin:0;border-left-color:var(--o);background:#fff9ee}.ex b,.ss b{color:var(--b);font:700 13px Georgia,serif}.sb{min-height:38px;padding:3px 5px;margin-top:3px}.u .c2{min-height:44px;padding:4px 6px;background:#eef2fb;border-bottom:2px solid var(--b)}
.addsec{background:var(--b);color:#fff;margin:18px 0 26px}
</style></head><body><div id="app"></div><script>
const S=(t,o)=>parent.postMessage(Object.assign({isStreamlitMessage:true,type:t},o),"*");
let doc=null,cur="";
const uid=()=>Math.random().toString(36).slice(2,8);
const esc=s=>String(s==null?"":s).replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const ST=["Open","In progress","Done","N/A"];
const fit=()=>S("streamlit:setFrameHeight",{height:document.body.scrollHeight+10});
const push=()=>{cur=JSON.stringify(doc);S("streamlit:setComponentValue",{value:doc,dataType:"json"});fit()};
const blank=()=>({id:uid(),ref:"",req:"",resp:"",sum:"",status:"Open"});
function prog(){let n=0,d=0;doc.sections.forEach(s=>s.rows.forEach(r=>{n++;if((r.resp||"").trim())d++}));
 const p=n?Math.round(100*d/n):0;document.getElementById("pg").style.width=p+"%";
 document.getElementById("pt").textContent=d+" of "+n+" rows filled ("+p+"%)"}
function draw(){
 const m=doc.meta||{};
 let h='<div class="hd"><div class="k">Bank of Baroda, RBI ECL Directions 2026 (issued 27 April 2026)</div><h1 contenteditable data-t="title">'+esc(doc.title)+'</h1><div class="meta">'
  +Object.keys(m).map(k=>'<label>'+esc(k)+' <span contenteditable data-m="'+esc(k)+'">'+esc(m[k])+'</span></label>').join("")
  +'</div><div class="bar"><i id="pg"></i></div><div class="k" id="pt" style="margin-top:6px"></div></div><div class="wrap">'
  +'<div class="ex"><b>Executive summary</b><div class="sb" contenteditable data-e="1">'+esc(doc.exec)+'</div></div>';
 doc.sections.forEach((s,i)=>{
  h+='<div class="sec"><div class="st"><b>'+(i+1)+'</b><span class="t" contenteditable data-s="'+i+'" data-f="title">'+esc(s.title)+'</span><button class="del" title="Delete section" data-act="ds" data-s="'+i+'">&times;</button></div>'
   +'<div class="ss"><b>Section summary</b><div class="sb" contenteditable data-s="'+i+'" data-f="sum">'+esc(s.sum)+'</div></div>'
   +'<table><tr><th>Reference</th><th>Requirement</th><th>Response (fill in)</th><th>Summary</th><th>Status</th><th></th></tr>';
  s.rows.forEach((r,j)=>{const a=' data-s="'+i+'" data-r="'+j+'"';
   h+='<tr><td class="r"><div contenteditable'+a+' data-f="ref">'+esc(r.ref)+'</div></td>'
    +'<td class="q"><div contenteditable'+a+' data-f="req">'+esc(r.req)+'</div></td>'
    +'<td class="a"><div class="c" contenteditable'+a+' data-f="resp">'+esc(r.resp)+'</div></td>'
    +'<td class="u"><div class="c2" contenteditable'+a+' data-f="sum">'+esc(r.sum)+'</div></td>'
    +'<td><select'+a+' data-f="status">'+ST.map(x=>'<option'+(x==r.status?' selected':'')+'>'+x+'</option>').join("")+'</select></td>'
    +'<td><button class="del" title="Delete row" data-act="dr"'+a+'>&times;</button></td></tr>'});
  h+='</table><button class="add" data-act="ar" data-s="'+i+'">+ Add row</button></div>'});
 h+='<button class="addsec" data-act="as">+ Add section</button></div>';
 document.getElementById("app").innerHTML=h;prog();fit()}
document.addEventListener("input",e=>{const t=e.target,d=t.dataset;if(!doc||!d)return;
 if(d.t)doc.title=t.innerText;else if(d.m)doc.meta[d.m]=t.innerText;else if(d.e!==undefined)doc.exec=t.innerText;
 else if(d.f){const s=doc.sections[+d.s];if(d.r!==undefined)s.rows[+d.r][d.f]=t.innerText;else s[d.f]=t.innerText}
 prog()});
document.addEventListener("focusout",e=>{if(doc&&e.target.isContentEditable)push()});
document.addEventListener("change",e=>{const t=e.target;if(doc&&t.tagName=="SELECT"){doc.sections[+t.dataset.s].rows[+t.dataset.r].status=t.value;push()}});
document.addEventListener("click",e=>{const b=e.target.closest("[data-act]");if(!b||!doc)return;
 const i=+b.dataset.s,j=+b.dataset.r,a=b.dataset.act;
 if(a=="ds")doc.sections.splice(i,1);
 if(a=="dr")doc.sections[i].rows.splice(j,1);
 if(a=="ar")doc.sections[i].rows.push(blank());
 if(a=="as")doc.sections.push({id:uid(),title:"New section",sum:"",rows:[blank()]});
 draw();push()});
addEventListener("message",e=>{if(e.data.type!=="streamlit:render")return;
 const js=JSON.stringify(e.data.args.doc);if(js!==cur){doc=JSON.parse(js);cur=js;draw()}});
new ResizeObserver(fit).observe(document.body);addEventListener("resize",fit);
S("streamlit:componentReady",{apiVersion:1});
</script></body></html>
'''
_TMP = Path(tempfile.gettempdir()) / "ecl_doc_component"
_TMP.mkdir(exist_ok=True)
(_TMP / "index.html").write_text(HTML, encoding="utf-8")
_C = components.declare_component("ecl_doc", path=str(_TMP))

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
    meta = {"Version": "0.1", "Owner": "", "Date": dt.date.today().isoformat(), "Model": "", "Risk tier": ""}
    return {"tab": tab, "title": title, "meta": meta, "exec": "", "sections": [
        {"id": f"{k}{i}", "title": t, "sum": "", "rows": [
            {"id": f"{k}{i}.{j}", "ref": r, "req": q, "resp": "", "sum": "", "status": "Open"} for j, (r, q) in enumerate(rows)]}
        for i, (t, rows) in enumerate(secs)]}

FLOORS = [("Secured retail loans (100% primary security)", "0.40%", "5%"), ("Corporate loans", "0.40%", "5%"), ("Small and micro enterprises", "0.25%", "5%"),
 ("Medium enterprises", "0.40%", "5%"), ("Farm credit", "0.25%", "5%"), ("Loans to banks, NBFCs, regulated FIs", "0.40%", "5%"),
 ("Loans against term deposits, LIC policy, KVP", "0.40%", "0.40%"), ("Gold loans", "0.40%", "1.50%"), ("State government direct or guaranteed", "0.40%", "2.50%"),
 ("Unsecured retail loans", "1%", "5%"), ("Housing loans to individuals", "0.25%", "1.50%"), ("Other residential real estate", "0.40%", "1.50%"),
 ("Other commercial real estate", "0.40%", "2.50%"), ("CRE-ADC (non-qualifying)", "1.25%", "DCCO-event based"), ("CRE-RH (ADC)", "1%", "DCCO-event based"),
 ("Project finance, pre-operational", "1%", "DCCO-event based"), ("Project finance, operational", "0.40%", "5%"),
 ("Central govt guarantee schemes (CGTMSE, NCGTC, CRGFTLIH)", "0.25%", "0.25%"), ("Restructured standard (natural calamity)", "5%", "10% if SICR"), ("Residual category", "0.40%", "5%")]
SICR_P = ["Internal rating downgrade vs origination (notches)", "External rating downgrade", "Change in PD vs origination (absolute and relative)", "Loan pricing / credit spread change",
 "Macroeconomic or sector outlook", "Borrower financials (revenue, margins, leverage, DSCR)", "Behavioural score", "Collateral value / LTV", "Watch-list status", "Covenant breach, actual or expected"]
NPA_T = ["Term loan or bills interest / principal overdue more than 90 days", "OD/CC out of order (over limit or drawing power, no credits, or credits below interest for 90 days)",
 "Drawing power based on stock statements older than 3 months, drawings for 90 days", "Crop loans overdue for the prescribed seasons", "Securitisation liquidity facility or partial credit enhancement outstanding 90 days",
 "Credit card minimum due unpaid for 90 days", "Bond or debenture interest / instalment unpaid more than 90 days"]
DATA_S = ["Account / exposure master", "Repayment and DPD history", "Ratings and scores", "Collateral and recoveries", "Macroeconomic series"]
INSTR = [("Loans", "In scope"), ("Debt securities (not at FVTPL)", "In scope"), ("Trade receivables", "In scope, simplified approach allowed"), ("Lease receivables", "In scope, simplified approach allowed"),
 ("Loan commitments / undrawn limits", "In scope"), ("Off-balance-sheet exposures (guarantees)", "In scope"), ("Investments in subsidiaries, associates, JVs", "Excluded"), ("Assets measured at FVTPL", "Excluded from ECL staging")]
FILL = "Developer entry: "

DEV = [
 ("1. Purpose, scope and applicability", [("S1", "Model purpose, run frequency (first quarterly ECL report due 30 June 2027) and business use of outputs (provisioning, capital, disclosure, pricing)")]
  + [("S1.1", f"{n} ({d}). Covered by this model? If not, give the reason") for n, d in INSTR]
  + [("S1.1", "Carve-outs kept in Stage 1 without SICR testing: SLR-eligible investments, direct central-government claims, central-government guaranteed exposures, zero risk-weight foreign sovereigns / central banks / MDBs / BIS / IMF. Describe implementation"),
     ("S1.2", "Segmentation table: for each segment give product category for floors, exposure (Rs crore), approach (PD-LGD-EAD or provision matrix) and data source")]),
 ("2. Governance and model inventory", [
  ("Ch. V", "Board-approved ECL policy: name, version, approval date"), ("Ch. V", "Oversight committee including CFO and CRO: members and meeting frequency"),
  ("Ch. V", "Model inventory entry: owner, developer, risk tier, interdependencies"), ("Ch. V", "Three lines: first-line owner duties, second-line risk and compliance monitoring, third-line internal audit assurance"),
  ("Ch. V", "Third-party or vendor model: vendor, documentation access, RBI supervisory evaluation clause (or N/A)"),
  ("Ch. V", "Model lifecycle stage: development, pre-implementation validation, implemented, monitoring or recalibration")]),
 ("3. Data", [("S3", f"{d}: source system, period, fields used, owner, quality checks, known gaps and proxies") for d in DATA_S]
  + [("S3", "Data lineage diagram reference"), ("S3", "Reconciliation of model input to general ledger"), ("S3", "Treatment of missing values, outliers and data breaks")]),
 ("4. Default definition and Stage 3", [("Ch. II", "Default = NPA, so NPA = Stage 3 = lifetime ECL, applied at borrower level (all exposures of a borrower move together). Confirm implementation")]
  + [("Ch. II", f"NPA trigger: {t}. Implemented? Source field and notes") for t in NPA_T]
  + [("Transition", "Accounts NPA on 31 March 2027 are not upgraded merely because of the framework change. Handling"),
     ("S4", "Stage 3 time-in-stage tracking (needed for floors)"), ("S4", "Identification of POCI assets at origination or purchase")]),
 ("5. Staging and SICR", [("Para 30", "SICR definition: change in default risk over remaining life versus the same period at origination, using reasonable and supportable information. Describe the approach; note Stage 3 is borrower level and Stage 2 facility level")]
  + [("Para 30, Annex 1", f"SICR parameter: {p}. Used? Threshold or trigger, rationale and calibration evidence") for p in SICR_P]
  + [("Para 33", "Presumption: more than 30 days past due indicates SICR. Implemented? Rebuttal procedure, evidence required, approver"),
     ("Para 33", "Presumption: revolving facility over limit / drawing power continuously up to 60 days indicates SICR. Implemented? Rebuttal procedure"),
     ("Para 33", "Rebuttal log location (rebuttal must be documented, reasonable, not routine)"),
     ("Ch. III", "Collective SICR assessment segments (instrument type, collateral, maturity, geography, industry)"),
     ("Ch. III", "Consistent application to similar exposures; board approval of SICR parameters"), ("Ch. III", "Low credit risk exemption used? If yes, where"),
     ("Upgrade", "Stage 3 to Stage 1 (non-restructured, no SICR evidence) or to Stage 2 (SICR evidence)"),
     ("Upgrade", "Restructured non-MSME above Rs 25 crore: Stage 3 to 2 to 1 per Resolution of Stressed Assets Directions, 2025"),
     ("Upgrade", "Restructured MSME below Rs 25 crore: Stage 3 directly to Stage 1 on meeting conditions"), ("S5", "Stage decision flow chart reference")]),
 ("6. ECL measurement", [
  ("S6", "ECL = PD x LGD x EAD x discount factor, probability-weighted across scenarios. Stage 1 uses 12-month PD; Stages 2 and 3 lifetime. Confirm formula as coded"),
  ("S6.1", "12-month PD: methodology, model form, segmentation"), ("S6.1", "Lifetime PD term structure: method (transition matrix, survival, vintage)"),
  ("S6.1", "PD development sample, observation window, default rate"), ("S6.1", "Through-the-cycle to point-in-time conversion"), ("S6.1", "Calibration technique and results"),
  ("S6.1", "0.03% floor on 12-month PD applied? If not, why"), ("S6.1", "Origination PD retained for SICR comparison"), ("S6.1", "PD performance statistics (Gini, KS, calibration)"),
  ("S6.2", "LGD approach: internal estimate, workout or collateral-based"), ("S6.2", "Recovery cash flows, timing, cure rates, costs"), ("S6.2", "Discount rate for recoveries"),
  ("S6.2", "Collateral haircuts and valuation refresh"), ("S6.2", "Backstop where data are insufficient: 65% secured portion, 70% unsecured portion. Applied?"),
  ("S6.2", "30% LGD portions (cash, gold, government securities, LIC policies, KVP, NSC). Applied?"), ("S6.2", "Downturn adjustment"),
  ("S6.3", "EAD for amortising, revolving and bullet products"), ("S6.3", "CCF source for undrawn limits and off-balance-sheet items"),
  ("S6.3", "Credit risk mitigants are not netted from EAD. Confirm"), ("S6.3", "Discount rate: EIR (contractual rate allowed for opening ECL at 1 April 2027)"),
  ("Annex 2", "Trade and lease receivables: provision matrix, lifetime ECL at all times. Used or N/A")]),
 ("7. Forward-looking information and scenarios", [
  ("S7", "Macro variables: source, used for PD or LGD, link method and lag, horizon (one line per variable)"),
  ("S7", "Base scenario: probability weight, narrative, key assumptions, ECL impact"), ("S7", "Upside scenario: probability weight, narrative, key assumptions, ECL impact"),
  ("S7", "Downside scenario: probability weight, narrative, key assumptions, ECL impact"), ("S7", "Basis of probability weights and review frequency"),
  ("S7", "Forecast horizon versus lifetime horizon, and reversion method"), ("Ch. V", "Country risk in PD and LGD for cross-border exposures"),
  ("Ch. V", "Unhedged foreign-currency exposure of borrowers"), ("Ch. V", "Overseas subsidiary jurisdiction, legal and enforcement risks")]),
 ("8. Prudential floors", [("S8", "Allowance = max(model ECL, floor). Stage 1/2 floors by product category (portfolio or account level per policy); Stage 3 floors at account level; off-balance-sheet floors after CCF. Confirm implementation")]
  + [("S8.1", f"{n}: Stage 1 floor {a}, Stage 2 floor {b}. Enter bank portfolio mapped") for n, a, b in FLOORS]
  + [("S8.1", "Product category assigned at origination, reclassified only on material change; gold loans kept as gold loans. Assignment rules"),
     ("S8.2", "Stage 3 floors by time in Stage 3 (secured / unsecured): 0-1y 25% / 40%; 1-2y 40% / 100%; 2-3y 55% / 100%; 3-4y 75% / 100%; over 4y 100% / 100%. Implementation"),
     ("S8.2", "Lower-risk Stage 3 ladder (term-deposit loans, gold loans, state government): 10% / 25%, 20% / 100%, 30% / 100%, 40% / 100%, 100% / 100%. Implementation"),
     ("S8.2", "Unsecured retail loans Stage 3: 25% in year 1, 100% after. Implementation"), ("S8.2", "Additional 5% provision for wilful defaulters over computed ECL"),
     ("S8.2", "Stage 3 collateral above Rs 7.5 crore valued at classification and at least every 2 years; stock annually")]),
 ("9. Overlays and other provisions", [
  ("Ch. III", "Management overlay: trigger, quantification, approval, expiry (general provision)"), ("Ch. III", "Default loss guarantee cover considered in ECL? N/A or describe"),
  ("Ch. III", "Utilisation of floating provisions / countercyclical buffer"), ("Ch. III", "Reserve for exchange rate fluctuation on forex-linked NPAs"),
  ("Capital", "Capital treatment: Stage 3 specific provision, Stage 1 and 2 general provision")]),
 ("10. EIR, POCI and income recognition", [
  ("Ch. IV", "EIR inputs: integral fees, transaction costs, premiums and discounts; excluding expected credit losses"), ("Ch. IV", "Floating-rate loans: EIR re-estimation on benchmark change"),
  ("Ch. IV", "New loans from 1 April 2027 at EIR"), ("Ch. IV", "Migration plan for loans outstanding at 31 March 2027 (complete by 31 March 2030)"),
  ("Ch. IV", "POCI: credit-adjusted EIR, lifetime ECL, only cumulative changes recognised"), ("Ch. IV", "Stage 3 and POCI income on cash basis, no accrual"),
  ("Ch. IV", "Resumption of accrual after upgrade")]),
 ("11. Transition arrangements", [
  ("Transition", "Day 1 fair valuation of the loan portfolio at 1 April 2027 (difference to opening retained earnings)"),
  ("Transition", "Transitional adjustment = max(0, ECL at 1 April 2027 minus IRAC provisions at 31 March 2027). Amount"),
  ("Transition", "CET1 add-back, net of tax: 4/5 in FY2027-28, 3/5, 2/5, 1/5, nil from FY2031-32. Elected schedule"),
  ("Transition", "Shorter transition period chosen? If yes, details"), ("Transition", "Parallel IRACP reporting until 31 December 2027")]),
 ("12. Implementation and automation", [
  ("Annex 3", "System architecture and platform"), ("Annex 3", "Straight-through processing of staging, upgrades and downgrades"),
  ("Annex 3", "Automation of SICR, ECL computation, income recognition and reversals"), ("Annex 3", "Manual override: two-level authorisation, delegation, audit trail"),
  ("Annex 3", "Exception logs retained at least 3 years"), ("Annex 3", "Version control, change management and release testing"), ("Annex 3", "Code repository and run book reference")]),
 ("13. Monitoring, limitations and change control", [
  ("Ch. V", "Monitoring metric: stage migration rates (frequency, threshold, action)"), ("Ch. V", "Monitoring metric: PD back-test and stability"),
  ("Ch. V", "Monitoring metric: LGD and EAD realised versus estimate"), ("Ch. V", "Monitoring metric: coverage ratio by stage"),
  ("Ch. V", "Limitations and assumptions: impact and mitigant (one line each)"), ("Ch. V", "Triggers for recalibration, redevelopment or retirement")]),
 ("14. Reporting and disclosure", [
  ("Ch. VI", "First quarterly ECL report due 30 June 2027: owner and status"), ("Ch. VI", "Parallel IRACP quarterly reports until 31 December 2027"),
  ("Ch. VI", "First annual ECL report with comparatives, 31 March 2028"), ("Annex 4", "Roll-forward of allowance by stage and instrument type"),
  ("Annex 4", "Credit-quality tables: gross, ECL, net by stage and product"), ("Annex 4", "SICR criteria and segmentation submitted to RBI quarterly"),
  ("Annex 4", "Macroeconomic scenario assumptions submitted to RBI"), ("Annex 4", "Transitional arrangement impact on capital and leverage ratios")]),
 ("15. Open issues, deviations and sign-off", [
  ("S15", "Issue or deviation from the Directions: impact, owner, due date (one line each)"),
  ("S15", "Sign-off: model developer, model owner, Head of Credit Risk, Chief Risk Officer (names and dates)")]),
]

TESTS = [("V1", "Governance", "Inventory, tiering, policy approval review", "Document review"), ("V2", "Data", "Completeness, accuracy, reconciliation to ledger", "Re-performance"),
 ("V3", "Staging", "Stage 3 to NPA register reconciliation", "Full population match"), ("V4", "SICR", "Back-test of SICR triggers", "Default rates by stage"),
 ("V5", "SICR", "Review of presumption rebuttals", "Sample testing"), ("V6", "PD", "Discriminatory power", "Gini, KS, AUC"),
 ("V7", "PD", "Calibration and 12-month back-test", "Binomial or Hosmer-Lemeshow"), ("V8", "PD", "Stability", "PSI, rating migration"),
 ("V9", "LGD", "Realised versus estimated LGD", "Back-test by segment"), ("V10", "EAD", "CCF and utilisation back-test", "Realised versus estimated"),
 ("V11", "Scenarios", "Reasonableness and weights", "Challenge and sensitivity"), ("V12", "Floors", "Floor application", "Independent recomputation"),
 ("V13", "Output", "ECL recomputation", "Sample re-performance"), ("V14", "Controls", "IT, STP and audit trail", "Walkthrough and testing"),
 ("V15", "Reporting", "Roll-forward and disclosure tie-out", "Reconciliation")]
MATERIALS = ["Development document", "Source code and run book", "Input data extracts and data dictionary", "Previous validation report and open findings",
 "Board-approved ECL policy and SICR parameter approval", "Macroeconomic scenario pack"]
T = "Result, evidence and rating: "

VAL = [
 ("1. Independence, scope and materials", [
  ("Ch. V", "Validators are independent of developers and model owners. Confirm and state reporting line"),
  ("Ch. V", "Validation covers staging, SICR, PD, LGD, EAD, scenarios, floors, overlays, EIR / POCI, disclosures. Confirm coverage"),
  ("Ch. V", "Third-party model: documentation, code and data access obtained (or N/A)"), ("S1", "Items out of scope and reason")]
  + [("S1", f"Material received: {m}. Version, date, complete?") for m in MATERIALS]),
 ("2. Validation plan and test inventory", [(i, f"{a}: {t} (method: {m}). Acceptance threshold, result, rating") for i, a, t, m in TESTS]),
 ("3. Governance and inventory review", [
  ("Ch. V", "Model in central inventory with owner, developer, tier, interdependencies, validation status"), ("Ch. V", "Board-approved ECL policy and oversight committee with CFO and CRO"),
  ("Ch. V", "Three-line responsibilities defined and operating"),
  ("Ch. V", "Lifecycle documented: development, pre-implementation validation, implementation, monitoring, independent validation, recalibration or retirement"),
  ("Ch. V", "Reporting to Board or Audit Committee on ECL model risk")]),
 ("4. Data validation", [
  ("V2", "Source-to-model reconciliation to general ledger"), ("V2", "Completeness of accounts, including temporary overdrafts"),
  ("V2", "Accuracy of DPD, limits, ratings, collateral fields"), ("V2", "History length and representativeness for PD, LGD, EAD"),
  ("V2", "Treatment of missing data, outliers and proxies"), ("V2", "Data lineage documented end to end")]),
 ("5. Conceptual soundness", [
  ("Ch. II", "Default definition: default equals NPA, applied at borrower level"), ("Ch. III", "Staging logic: Stage 3 first, then SICR for Stage 2, else Stage 1; Stage 2 at facility level"),
  ("Ch. III", "PD methodology: model form, 12-month and lifetime PD, TTC to PIT conversion, 0.03% floor on 12-month PD"),
  ("Ch. III", "LGD methodology: recovery and cure logic, discounting, 65% / 70% backstop, 30% for eligible cash-like collateral"),
  ("Ch. III", "EAD and CCF: undrawn limits, no netting of mitigants from EAD"), ("Ch. III", "ECL formula: PD x LGD x EAD x discount factor, probability-weighted"),
  ("Annex 2", "Simplified approach: provision matrix for trade and lease receivables, lifetime ECL"), ("Ch. V", "Assumptions and limitations documented, reasonable, with compensating controls")]),
 ("6. Staging and SICR validation", [
  ("V3", "Stage 3 reconciliation to NPA register at borrower level, including contagion across a borrower's facilities"), ("V3", "Re-perform 90-day, out-of-order and drawing-power triggers on a sample"),
  ("Para 30", "SICR parameters and thresholds are board approved and applied consistently to similar exposures"),
  ("Para 33", "30-day and 60-day presumptions: confirm automated flagging; test rebuttal sample for documented evidence"),
  ("V4", "SICR back-test: default rates of Stage 1 versus Stage 2; does SICR lead default?"), ("V4", "Stage migration matrix, volatility, cure and re-default behaviour"),
  ("Ch. III", "Collective assessment: segment homogeneity and common risk characteristics"),
  ("Ch. III", "Upgrade rules: Stage 3 to 1 or 2; restructured above Rs 25 crore; MSME below Rs 25 crore"),
  ("Ch. III", "Carve-outs: SLR, central government and zero risk-weight exposures held in Stage 1 correctly"),
  ("Transition", "Accounts NPA at 31 March 2027 not upgraded solely because of the framework change")]),
 ("7. PD validation", [
  ("V6", "Rank ordering: Gini / AUC / KS and thresholds"), ("V7", "12-month calibration: predicted versus observed default rate by grade and segment"),
  ("V7", "Lifetime PD term structure: back-test of cumulative default curves"), ("V8", "Population and characteristic stability (PSI)"),
  ("Ch. III", "TTC to PIT conversion: reasonableness against the macro cycle"), ("Ch. V", "Benchmarking against external ratings or an alternative model"),
  ("Ch. III", "Floor application: 12-month PD not below 0.03%"), ("Ch. III", "Origination PD stored and used consistently for SICR")]),
 ("8. LGD validation", [
  ("V9", "Realised versus estimated LGD by segment and collateral type"), ("V9", "Recovery cash flows and cure rates re-derived from workout data"),
  ("V9", "Discount rate and timing consistent with EIR / policy"),
  ("Ch. III", "Collateral valuation and haircuts: sample valuations; Stage 3 above Rs 7.5 crore valued at classification and at least every 2 years; stock annually"),
  ("Ch. III", "Backstop usage: 65% secured / 70% unsecured only where data are insufficient"),
  ("Ch. III", "30% LGD category only for eligible collateral (cash, gold, government securities, LIC policies, KVP, NSC)"), ("Ch. V", "Downturn conditions reflected where relevant")]),
 ("9. EAD and CCF validation", [
  ("V10", "EAD for amortising, revolving and bullet products: re-perform on a sample"), ("V10", "CCF for undrawn and off-balance-sheet items: back-test realised drawdown at default"),
  ("Ch. III", "No netting of credit risk mitigants: confirm in code and output"), ("Ch. III", "Guarantees devolved and turned NPA: Stage 3 floor applied without CCF")]),
 ("10. Forward-looking information and scenarios", [
  ("V11", "Scenario set: at least base, upside, downside with consistent narratives"), ("V11", "Probability weights: basis, documentation, governance approval"),
  ("V11", "Macro-to-PD / LGD linkage: significance, sign and lag reasonableness"), ("V11", "Lifetime horizon beyond forecasts: reversion method documented and reasonable"),
  ("V11", "Sensitivity: ECL change under shifted weights and shocks"), ("Ch. V", "Country risk, unhedged foreign-currency exposure and overseas subsidiary risks reflected in PD and LGD")]),
 ("11. Floors and output reasonableness", [
  ("V12", "Product category assignment correct at origination; gold loans kept as gold loans"), ("V12", "Stage 1 and 2 floors: allowance not below product floor at the applied level"),
  ("V12", "Stage 3 floors: time-in-stage bands at account level, secured and unsecured split"), ("V12", "Floors on off-balance-sheet items applied after CCF"),
  ("V12", "Wilful defaulters: additional 5% over ECL"), ("V13", "Independent ECL recomputation: sample size and tolerance"),
  ("V13", "Coverage by stage: trend and peer reasonableness"), ("V13", "Period movement: drivers of change in allowance")]),
 ("12. Overlays and other provisions", [
  ("Ch. III", "Management overlays: trigger, quantification, approval, expiry documented; general provision"), ("Ch. III", "DLG: integral to contract, not recognised separately, reduced on invocation"),
  ("Ch. III", "Floating provisions / countercyclical buffer: utilisation approved and disclosed"), ("Ch. III", "Forex-linked NPA reserve: revaluation gain provided in full"),
  ("Capital", "Capital classification: Stage 3 specific, Stage 1 and 2 general provision")]),
 ("13. EIR, POCI and income recognition", [
  ("Ch. IV", "EIR calculation re-performed on a sample; integral fees and costs included, expected credit losses excluded"), ("Ch. IV", "Floating-rate EIR re-estimation on benchmark change"),
  ("Ch. IV", "Migration plan: loans outstanding at 31 March 2027 on track for EIR by 31 March 2030"), ("Ch. IV", "POCI: credit-adjusted EIR; only cumulative lifetime ECL changes recognised"),
  ("Ch. IV", "Stage 3 and POCI income on cash basis; accrual resumes after upgrade")]),
 ("14. Implementation and IT controls", [
  ("V14", "Code review: code matches Development document; no undocumented logic"), ("V14", "User acceptance and parallel run against independent replication"),
  ("Annex 3", "Straight-through processing of staging, upgrades and downgrades"), ("Annex 3", "Manual override control: two-level authorisation, delegation, audit trail"),
  ("Annex 3", "Exception logs kept at least 3 years"), ("Annex 3", "Access, change and release management: segregation of duties, version control")]),
 ("15. Reporting, disclosure and transition", [
  ("V15", "Allowance roll-forward by stage and instrument type: opening to closing"), ("V15", "Credit-quality tables tie to ledger"),
  ("Annex 4", "Regulatory submissions: SICR criteria and segmentation (quarterly); macro scenarios to RBI"),
  ("Ch. VI", "Reporting calendar: first quarterly report 30 June 2027; parallel IRACP until 31 December 2027; first annual 31 March 2028"),
  ("Transition", "Transitional adjustment recomputed: max(0, ECL at 1 April 2027 minus IRAC provisions at 31 March 2027)"),
  ("Transition", "CET1 add-back schedule 4/5, 3/5, 2/5, 1/5 for FY2027-28 to FY2030-31, net of tax"),
  ("Transition", "Day 1 fair valuation adjusted to opening retained earnings, not profit and loss")]),
 ("16. Findings log", [("F1", "Finding: area, description, severity (High / Medium / Low), impact on ECL, management response, owner, due date, status"),
  ("F2", "Finding (as above)"), ("F3", "Finding (as above)")]),
 ("17. Conclusion and sign-off", [
  ("S17", "Overall conclusion: fit for use / fit for use with conditions / not fit for use"), ("S17", "Conditions or restrictions on use"), ("S17", "Next validation due"),
  ("S17", "Summary of key strengths and weaknesses"), ("S17", "Sign-off: lead validator, Head of Model Validation, model owner acknowledgement, Chief Risk Officer")]),
]

_dv = {t.split(". ", 1)[1]: r for t, r in DEV}
_vl = {t.split(". ", 1)[1]: r for t, r in VAL}
DEV = [
 ("1. Executive summary and model overview", _dv["Purpose, scope and applicability"] + [
  ("S1.2", "Accounting and regulatory regime (Ind AS 109, RBI ECL Directions 2026) and model materiality tier"),
  ("S1.1", "EAD balances reconcile to the general ledger at the development reference date"),
  ("S1.3", "Core formulation as coded: marginal PD, LGD, EAD and discount factor by horizon and scenario, summed with probability weights"),
  ("S1.3", "Key assumptions, limitations and post-model adjustments (PMAs) in brief")]),
 ("2. Regulatory and accounting alignment", _dv["Governance and model inventory"] + _dv["Default definition and Stage 3"]
  + [("Ch. II", "Curing rules and probation period before upgrade from default; cliff-effect check on SICR thresholds")] + _dv["Staging and SICR"]),
 ("3. Data architecture, quality and segmentation", _dv["Data"] + [
  ("S3.1", "Observation window covering at least one full credit cycle, including a downturn"),
  ("S3.2", "Data cleaning rules, exclusions and waterfall reconciliation from raw data to modelling dataset to general ledger"),
  ("S3.3", "Homogeneous risk segmentation: basis (product, collateral, rating, geography) and evidence of homogeneity")]),
 ("4. Component modelling methodologies", _dv["ECL measurement"] + [
  ("S4.1", "Marginal PD term structure by scenario and the move from TTC ratings to PiT term structures"),
  ("S4.2", "LGD: workout recovery cash flows, cure rates, collateral haircuts, discounting at EIR"),
  ("S4.3", "EAD: amortisation schedules, prepayment, CCF or behavioural lifetime for revolving facilities")]),
 ("5. Forward-looking macroeconomic integration", [
  ("S5.1", "Macro variable selection (GDP, unemployment, inflation, interest rates) and econometric satellite model; stationarity, multicollinearity, sign intuition"),
  ("S5.2", "Scenario generation method and probability weighting")] + _dv["Forward-looking information and scenarios"]),
 ("6. Prudential floors, overlays and other provisions", _dv["Prudential floors"] + _dv["Overlays and other provisions"]),
 ("7. Model performance, back-testing and sensitivity", [
  ("S7.1", "Discrimination: Gini, AUROC, KS by segment"),
  ("S7.1", "Calibration: predicted PiT PD, LGD, EAD against realised outcomes (binomial, Hosmer-Lemeshow, traffic light)"),
  ("S7.1", "Benchmarking against a challenger or vendor model"), ("S7.2", "Sensitivity of ECL to macro variable shifts"),
  ("S7.2", "Stress analysis: ECL volatility under severe scenarios")] + _dv["Monitoring, limitations and change control"]),
 ("8. EIR, POCI, income recognition and transition", _dv["EIR, POCI and income recognition"] + _dv["Transition arrangements"]),
 ("9. Production implementation, governance and controls", _dv["Implementation and automation"] + [
  ("S9", "IT system integration and automated calculation engine"), ("S9", "Maker-checker controls on inputs, parameters and outputs"),
  ("S9", "Independent validation sign-off process before production use")]),
 ("10. Reporting and disclosure", _dv["Reporting and disclosure"]),
 ("11. Open issues, deviations and sign-off", _dv["Open issues, deviations and sign-off"]),
]
VAL = [
 ("1. Executive summary and validation opinion", [
  ("S1", "Validation scope: initial validation, annual review or material change; materiality tier"),
  ("S1", "Overall model rating (Satisfactory, Needs Improvement, Unsatisfactory) and conditions for approval")] + _vl["Independence, scope and materials"]),
 ("2. Validation plan and test inventory", _vl["Validation plan and test inventory"]),
 ("3. Governance and regulatory compliance check", _vl["Governance and inventory review"] + [
  ("Ch. V", "Compliance with internal MRM policy, Ind AS 109 / RBI ECL Directions and regulatory floors (30-DPD and 90-DPD backstops, PD and LGD floors)"),
  ("Ch. V", "Independent sign-off path including the Risk Management Committee of the Board (RMCB)")]),
 ("4. Data integrity and representativeness review", _vl["Data validation"] + [
  ("V2", "ETL pipeline audit: transformations, controls, rerun consistency"), ("V2", "Historical window captures a full economic downturn")]),
 ("5. Conceptual soundness and methodology challenge", _vl["Conceptual soundness"] + _vl["Staging and SICR validation"] + [
  ("V4", "Segmentation: homogeneity of risk pools; premature or delayed Stage 2 migration (cliff effect)"),
  ("V11", "Macro variables: stationarity, multicollinearity, sign intuition"), ("V11", "Non-linearity and probability weighting of base, upside, downside scenarios")]
  + _vl["Forward-looking information and scenarios"]),
 ("6. Independent code replication and implementation testing", _vl["Implementation and IT controls"] + [
  ("V14", "Line-by-line code review (Python, SAS or R)"),
  ("V14", "Independent replication of parameters: production outputs match development prototype within tolerance")]),
 ("7. Outcomes analysis: back-testing and benchmarking", [
  ("V6", "Discrimination power: Gini, AUROC, KS"), ("V7", "Calibration accuracy: binomial, Hosmer-Lemeshow, traffic-light approach"),
  ("V11", "Benchmarking against challenger models (simpler regressions or vendor benchmarks)")]
  + _vl["PD validation"] + _vl["LGD validation"] + _vl["EAD and CCF validation"]),
 ("8. Sensitivity, stress testing, floors and overlay assessment", [("V11", "ECL volatility under stressed macro variable shocks")]
  + _vl["Floors and output reasonableness"] + _vl["Overlays and other provisions"]),
 ("9. EIR, POCI and income recognition", _vl["EIR, POCI and income recognition"]),
 ("10. Reporting, disclosure and transition", _vl["Reporting, disclosure and transition"]),
 ("11. Findings log and remediation plan", _vl["Findings log"] + [("F", "Remediation plan: owner, severity, target closure date before deployment")]),
 ("12. Conclusion and sign-off", _vl["Conclusion and sign-off"]),
]

SKEL = {"dev": ("d", "Development", "ECL Model Development Document", DEV),
        "val": ("v", "Validation", "ECL Model Validation Document", VAL)}
LABEL = {"dev": "Development", "val": "Validation"}
for _k, _v in (("docs", {"dev": None, "val": None}), ("ver", {"dev": 0, "val": 0}), ("up_key", 0), ("sig", None)):
    st.session_state.setdefault(_k, _v)

def clear_all():
    st.session_state.docs = {"dev": None, "val": None}
    st.session_state.ver = {k: v + 1 for k, v in st.session_state.ver.items()}

# ---------------------------------------------------------------- Gemini
PROMPT = """You are a senior model-risk documentation specialist at an Indian bank, completing part of the %s DOCUMENT for an ECL model under the RBI (Commercial Banks - Asset Classification, Provisioning and Income Recognition) Directions, 2026 (27 April 2026) and Ind AS 109 / IFRS 9 practice.
Each row has an id and a requirement. Using ONLY the source code, write for each row id: "detail" (max 60 words: name the function or constant used and its values or formula; for the validation document, say what a validator can test and any gap or deviation from the Directions) and "summary" (max 20 words, plain and decisive). If the code gives no evidence, detail must be exactly "Not evidenced in the code provided." and summary exactly "No evidence in code."
Also write for each section id a "summary" of at most 40 words giving that section's overall position.
Return ONLY JSON: {"rows": {"<row id>": {"detail": "...", "summary": "..."}}, "sections": {"<section id>": "<summary>"}}
SECTIONS AND ROWS:
%s
CODE:
%s"""
EXEC_PROMPT = """Write the executive summary (max 150 words) of the %s DOCUMENT for an ECL model under the RBI ECL Directions 2026, from the section summaries below. State scope, key design choices, main gaps and the overall position in plain language.
Return ONLY JSON: {"executive_summary": "..."}
%s"""

def code_text(up):
    raw = up.getvalue().decode("utf-8", "ignore")
    if up.name.endswith(".ipynb"):
        nb = json.loads(raw)
        raw = "\n\n".join("".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code")
    return raw[:60000]

def blank_doc(kind):
    k, tab, title, secs = SKEL[kind]
    return mk(k, tab, title, secs)

def build_doc(kind, code):
    from google import genai
    from google.genai import types
    d = blank_doc(kind)
    client = genai.Client(api_key=st.secrets["GEMINI_API_KEY"], http_options=types.HttpOptions(api_version="v1beta"))
    def ask(prompt):
        out = client.models.generate_content(model=MODEL, contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.2))
        return json.loads(out.text)
    chunks, cur, n = [], [], 0
    for sec in d["sections"]:
        cur.append(sec); n += len(sec["rows"])
        if n >= 35: chunks.append(cur); cur, n = [], 0
    if cur: chunks.append(cur)
    for ch in chunks:
        payload = [{"section_id": s["id"], "title": s["title"], "rows": {r["id"]: r["req"] for r in s["rows"]}} for s in ch]
        res = ask(PROMPT % (LABEL[kind].upper(), json.dumps(payload, indent=0), code))
        rows, secs = res.get("rows", {}), res.get("sections", {})
        for s in ch:
            s["sum"] = str(secs.get(s["id"], ""))
            for r in s["rows"]:
                x = rows.get(r["id"], {})
                r["resp"], r["sum"] = str(x.get("detail", "")), str(x.get("summary", ""))
    digest = "\n".join(f"{s['title']}: {s['sum']}" for s in d["sections"])
    d["exec"] = str(ask(EXEC_PROMPT % (LABEL[kind].upper(), digest)).get("executive_summary", ""))
    return d

with st.sidebar:
    st.header("Gemini assistant")
    up = st.file_uploader("Upload model code", type=["py", "ipynb", "txt", "sql", "r", "sas"], key=f"up{st.session_state.up_key}")
    if up is not None and (up.name, up.size) != st.session_state.sig:
        clear_all(); st.session_state.sig = (up.name, up.size)   # a new file resets both documents
    for k in ("dev", "val"):
        if st.button(f"Create {LABEL[k]} document", key=f"mk_{k}", disabled=up is None, use_container_width=True):
            try:
                with st.spinner(f"Gemini is writing the {LABEL[k].lower()} document..."):
                    st.session_state.docs[k] = build_doc(k, code_text(up))   # touches only this document
                    st.session_state.ver[k] += 1
                st.toast(f"{LABEL[k]} document created. Review and edit every row.")
            except KeyError:
                st.error("Add GEMINI_API_KEY to Streamlit secrets.")
            except Exception as e:
                st.error(f"Gemini call failed: {e}")
    st.caption("Creating a document again replaces only that document.")
    st.divider()
    if st.button("Clear both documents", use_container_width=True):
        clear_all(); st.session_state.up_key += 1; st.session_state.sig = None; st.rerun()
    st.caption("Generated text is a draft. Verify against the RBI Directions before use.")

# ---------------------------------------------------------------- exports
COLS = ["Ref", "Requirement", "Response", "Summary", "Status"]
KEYS = ("ref", "req", "resp", "sum", "status")
def meta_line(d): return ", ".join(f"{k}: {v}" for k, v in d["meta"].items() if v)

def to_html(docs):
    e = H.escape
    css = (f"body{{font:14px/1.5 'Segoe UI',sans-serif;margin:0}}header{{background:{V};color:#fff;padding:18px 28px;border-bottom:6px solid {G}}}"
           f"h1{{font:700 24px Georgia,serif;margin:0}}main{{padding:0 28px 30px}}h2{{color:{B};font:700 17px Georgia,serif;border-left:6px solid {B};padding-left:10px;margin-top:26px}}"
           f".ex,.ss{{background:#fff6dc;border-left:6px solid {G};padding:8px 12px;margin:14px 0;white-space:pre-wrap}}.ss{{background:#fff9ee;border-left-color:{O};margin:6px 0}}"
           f"table{{width:100%;border-collapse:collapse}}th{{background:{B};color:#fff;text-align:left;padding:6px}}td{{border-bottom:1px solid #e6e2da;padding:6px;vertical-align:top;white-space:pre-wrap}}td:nth-child(4){{background:#eef2fb}}")
    body = ""
    for d in docs:
        body += f"<header><h1>{e(d['title'])}</h1><div>{e(meta_line(d))}</div></header><main>"
        if d.get("exec"): body += f"<div class='ex'><b>Executive summary</b><br>{e(d['exec'])}</div>"
        for i, s in enumerate(d["sections"], 1):
            body += f"<h2>{i}. {e(s['title'])}</h2>"
            if s.get("sum"): body += f"<div class='ss'><b>Section summary</b><br>{e(s['sum'])}</div>"
            body += "<table><tr>" + "".join(f"<th>{c}</th>" for c in COLS) + "</tr>"
            body += "".join("<tr>" + "".join(f"<td>{e(r.get(k, ''))}</td>" for k in KEYS) + "</tr>" for r in s["rows"]) + "</table>"
        body += "</main>"
    return f"<!doctype html><meta charset='utf-8'><title>ECL report</title><style>{css}</style>{body}".encode()

def to_docx(docs):
    from docx import Document
    doc = Document()
    for n, d in enumerate(docs):
        if n: doc.add_page_break()
        doc.add_heading(d["title"], 0)
        doc.add_paragraph(meta_line(d))
        if d.get("exec"):
            doc.add_heading("Executive summary", 1); doc.add_paragraph(d["exec"])
        for i, s in enumerate(d["sections"], 1):
            doc.add_heading(f"{i}. {s['title']}", 1)
            if s.get("sum"): doc.add_paragraph().add_run("Section summary: " + s["sum"]).italic = True
            t = doc.add_table(rows=1, cols=5); t.style = "Light Grid Accent 1"
            for c, x in zip(t.rows[0].cells, COLS): c.text = x
            for r in s["rows"]:
                for c, k in zip(t.add_row().cells, KEYS): c.text = r.get(k, "")
    b = io.BytesIO(); doc.save(b); return b.getvalue()

def to_pdf(docs):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, PageBreak
    ss = getSampleStyleSheet(); body = ss["BodyText"]; body.fontSize = 7.5; body.leading = 9.5
    P = lambda x: Paragraph(H.escape(x or "-").replace("\n", "<br/>"), body)
    out, flow = io.BytesIO(), []
    for n, d in enumerate(docs):
        if n: flow.append(PageBreak())
        flow += [Paragraph(H.escape(d["title"]), ss["Title"]), Paragraph(H.escape(meta_line(d)), body)]
        if d.get("exec"): flow += [Paragraph("Executive summary", ss["Heading2"]), P(d["exec"])]
        for i, s in enumerate(d["sections"], 1):
            flow.append(Paragraph(f"{i}. {H.escape(s['title'])}", ss["Heading2"]))
            if s.get("sum"): flow.append(P("Section summary: " + s["sum"]))
            data = [COLS] + [[P(r.get(k, "")) for k in KEYS] for r in s["rows"]]
            t = Table(data, colWidths=[48, 125, 165, 115, 50], repeatRows=1)
            t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(B)), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                   ("BACKGROUND", (3, 1), (3, -1), colors.HexColor("#EEF2FB")),
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
        for w, c in zip((12, 50, 60, 40, 12), "ABCDE"): ws.column_dimensions[c].width = w
        if d.get("exec"): ws.append(["Executive summary", d["exec"]]); ws[ws.max_row][0].font = Font(bold=True)
        for s in d["sections"]:
            ws.append([]); ws.append([s["title"]])
            for c in ws[ws.max_row]: c.fill = PatternFill("solid", fgColor=G[1:]); c.font = Font(bold=True)
            if s.get("sum"): ws.append(["Summary", s["sum"]])
            ws.append(COLS)
            for c in ws[ws.max_row]: c.fill = PatternFill("solid", fgColor=B[1:]); c.font = Font(bold=True, color="FFFFFF")
            for r in s["rows"]: ws.append([r.get(k, "") for k in KEYS])
        for row in ws.iter_rows():
            for c in row: c.alignment = Alignment(wrap_text=True, vertical="top")
    b = io.BytesIO(); wb.save(b); return b.getvalue()

# ---------------------------------------------------------------- UI
st.markdown("<div class='hero'><h1>ECL Reporting Studio</h1><p>Development and Validation documents for the RBI ECL Directions, 2026 (27 April 2026, effective 1 April 2027)</p></div>", unsafe_allow_html=True)
tabs = st.tabs(["Development document", "Validation document", "Export reports"])
for tab, k in zip(tabs[:2], ("dev", "val")):
    with tab:
        d = st.session_state.docs[k]
        if d is None:
            st.info(f"No {LABEL[k].lower()} document yet. Upload model code in the sidebar and click 'Create {LABEL[k]} document', or start from the blank template.")
            if st.button(f"Open blank {LABEL[k].lower()} template", key=f"bl_{k}"):
                st.session_state.docs[k] = blank_doc(k); st.session_state.ver[k] += 1; st.rerun()
        else:
            v = _C(doc=d, key=f"c_{k}_{st.session_state.ver[k]}", default=None)
            if v: st.session_state.docs[k] = v
with tabs[2]:
    have = {k: st.session_state.docs[k] for k in ("dev", "val") if st.session_state.docs[k]}
    if not have:
        st.info("Create at least one document first.")
    else:
        pick = st.radio("Document", [LABEL[k] for k in have] + (["Both"] if len(have) == 2 else []), horizontal=True)
        docs = [have[k] for k in have if pick in (LABEL[k], "Both")]
        base = f"BoB_ECL_{pick}_{dt.date.today():%Y%m%d}"
        c = st.columns(4)
        c[0].download_button("PDF", to_pdf(docs), base + ".pdf", "application/pdf")
        c[1].download_button("Word (.docx)", to_docx(docs), base + ".docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
        c[2].download_button("Excel (.xlsx)", to_xlsx(docs), base + ".xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        c[3].download_button("Standalone HTML", to_html(docs), base + ".html", "text/html")
