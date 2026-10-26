"""
RBI ECL Model Lab  -  a deliberately simple, transparent ECL engine + dashboard
Built around the RBI (Commercial Banks - Asset Classification, Provisioning and
Income Recognition) Directions, 2026.

Pipeline:  data -> category map -> staging -> PD / LGD / EAD -> scenario ECL
           -> prudential floors -> overlay -> reporting tables

All amounts are in Rs lakh.  Educational prototype, NOT a validated bank model.
"""
import numpy as np
import pandas as pd
import altair as alt
import streamlit as st

st.set_page_config(page_title="RBI ECL Model Lab", page_icon="🏦", layout="wide")

# ----------------------------------------------------------------------------
# 1. REGULATORY TABLES (RBI Directions 2026, para 82 / 96 / 97 / 98)
# ----------------------------------------------------------------------------
# Stage-3 floors by years in Stage 3: (secured portion %, unsecured portion %)
S3_TABLES = {
    "A": [(25, 40), (40, 100), (55, 100), (75, 100), (100, 100)],    # para 82(1), (5)
    "B": [(10, 25), (20, 100), (30, 100), (40, 100), (100, 100)],    # para 82(2), 82(5)
    "C": [(15, 25), (25, 100), (40, 100), (55, 100), (100, 100)],    # para 82(5) xi.c / xi.d
    "UR": [(25, 25), (100, 100), (100, 100), (100, 100), (100, 100)],  # para 82(3)
}
S3_BUCKETS = ["0-1 yr", "1-2 yrs", "2-3 yrs", "3-4 yrs", ">4 yrs"]

SPECIAL_COLL = "Cash / Gold / Govt sec / LIC / KVP / NSC"
COLL_TYPES = ["None", "Property", "Vehicle / Other tangible", "Receivables / Stock", SPECIAL_COLL]

# name: s1 floor %, s2 floor %, stage-3 table, + generator settings
CATS = {
    "Secured retail loans (100% collateral)": dict(s1=0.40, s2=5.0, tbl="A", w=6, scale=8, rmean=3.5, term=(2, 7), sec=(100, 100), coll="Vehicle / Other tangible", rev=0.0, amort=0.95, eir=9.5),
    "Corporate loan": dict(s1=0.40, s2=5.0, tbl="A", w=8, scale=1500, rmean=4.5, term=(1, 8), sec=(0, 70), coll="Receivables / Stock", rev=0.45, amort=0.3, eir=9.5),
    "Loan to small & micro enterprises": dict(s1=0.25, s2=5.0, tbl="A", w=12, scale=60, rmean=5.0, term=(1, 6), sec=(30, 100), coll="Receivables / Stock", rev=0.5, amort=0.4, eir=10.5),
    "Loan to medium enterprises": dict(s1=0.40, s2=5.0, tbl="A", w=7, scale=400, rmean=4.8, term=(1, 7), sec=(20, 90), coll="Receivables / Stock", rev=0.5, amort=0.35, eir=10.0),
    "Farm credit (agriculture)": dict(s1=0.25, s2=5.0, tbl="A", w=7, scale=6, rmean=5.0, term=(0.5, 4), sec=(0, 80), coll="Property", rev=0.3, amort=0.3, eir=8.5),
    "Loan to banks / NBFCs / regulated FIs": dict(s1=0.40, s2=5.0, tbl="A", w=2, scale=3000, rmean=3.5, term=(1, 5), sec=(0, 40), coll="Receivables / Stock", rev=0.2, amort=0.0, eir=8.5),
    "Loan against TD / LIC / KVP": dict(s1=0.40, s2=0.40, tbl="B", w=2, scale=5, rmean=1.5, term=(0.5, 3), sec=(100, 100), coll=SPECIAL_COLL, rev=0.2, amort=0.0, eir=7.5),
    "Gold loan": dict(s1=0.40, s2=1.50, tbl="B", w=6, scale=2, rmean=3.0, term=(0.5, 1.5), sec=(70, 100), coll=SPECIAL_COLL, rev=0.0, amort=0.0, eir=9.0),
    "State government exposures": dict(s1=0.40, s2=2.50, tbl="B", w=1, scale=5000, rmean=3.0, term=(2, 10), sec=(0, 0), coll="None", rev=0.0, amort=0.2, eir=7.5),
    "Unsecured retail loans": dict(s1=1.00, s2=5.0, tbl="UR", w=14, scale=3, rmean=6.0, term=(1, 5), sec=(0, 0), coll="None", rev=0.25, amort=0.8, eir=14.0),
    "Housing loan to individuals": dict(s1=0.25, s2=1.50, tbl="B", w=18, scale=40, rmean=3.0, term=(5, 25), sec=(90, 100), coll="Property", rev=0.0, amort=0.98, eir=8.5),
    "Other claims secured by residential RE": dict(s1=0.40, s2=1.50, tbl="C", w=3, scale=45, rmean=4.0, term=(3, 15), sec=(70, 100), coll="Property", rev=0.0, amort=0.8, eir=9.5),
    "Other claims secured by commercial RE": dict(s1=0.40, s2=2.50, tbl="C", w=4, scale=200, rmean=4.5, term=(2, 12), sec=(60, 100), coll="Property", rev=0.0, amort=0.5, eir=10.0),
    "Central-govt guaranteed (CGTMSE etc.)": dict(s1=0.25, s2=0.25, tbl="B", w=3, scale=50, rmean=5.0, term=(1, 6), sec=(60, 100), coll="Property", rev=0.3, amort=0.5, eir=10.0),
    "Restructured standard advances": dict(s1=5.0, s2=10.0, tbl="A", w=2, scale=150, rmean=6.5, term=(1, 6), sec=(0, 80), coll="Property", rev=0.3, amort=0.4, eir=11.0),
    "Other / residual": dict(s1=0.40, s2=5.0, tbl="A", w=3, scale=100, rmean=5.0, term=(1, 5), sec=(0, 60), coll="Property", rev=0.3, amort=0.4, eir=10.0),
}
CAT_NAMES = list(CATS)
DEFAULT_CAT = "Other / residual"

COLS = ["loan_id", "borrower_id", "category", "outstanding", "undrawn_limit", "is_revolving",
        "amortising", "dpd", "days_over_limit", "rating_orig", "rating_curr", "watchlist",
        "credit_impaired", "years_in_stage3", "secured_pct", "collateral_type",
        "remaining_term_yrs", "eir_pct"]
BOOL_COLS = ["is_revolving", "amortising", "watchlist", "credit_impaired"]
NUM_DEFAULT = {"outstanding": 0.0, "undrawn_limit": 0.0, "dpd": 0.0, "days_over_limit": 0.0,
               "rating_orig": 5.0, "rating_curr": 5.0, "years_in_stage3": 0.0, "secured_pct": 0.0,
               "remaining_term_yrs": 3.0, "eir_pct": 10.0}

DEFAULT_PD = [0.05, 0.10, 0.25, 0.50, 1.00, 2.00, 4.00, 8.00, 15.00, 30.00]   # 12m PD %, grade 1..10
STAGE_COLORS = alt.Scale(domain=["Stage 1", "Stage 2", "Stage 3"], range=["#2e9e6b", "#f0a500", "#d64545"])


# ----------------------------------------------------------------------------
# 2. DATA: generator + sanitiser
# ----------------------------------------------------------------------------
def generate_loans(n: int, seed: int, stress: float) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    names = CAT_NAMES
    w = np.array([CATS[k]["w"] for k in names], float)
    cat_idx = rng.choice(len(names), size=n, p=w / w.sum())
    cat = np.array([names[i] for i in cat_idx])

    # borrower ids (several loans can share a borrower -> shows borrower-level Stage 3)
    borrower = np.empty(n, dtype=object)
    for ci in range(len(names)):
        m = cat_idx == ci
        k = int(m.sum())
        if k:
            borrower[m] = [f"B{ci:02d}-{x}" for x in rng.integers(1, max(2, int(k * 1.6)) + 1, size=k)]

    def per_cat(key):
        return np.array([CATS[c][key] for c in cat])

    outstanding = np.round(per_cat("scale") * np.exp(rng.normal(0, 0.7, n)), 2)
    is_rev = rng.random(n) < per_cat("rev")
    undrawn = np.where(is_rev, np.round(outstanding * rng.uniform(0, 0.5, n), 2), 0.0)
    amort = (rng.random(n) < per_cat("amort")) & ~is_rev

    r_orig = np.clip(np.round(rng.normal(per_cat("rmean"), 1.3)), 1, 10).astype(int)
    p = np.array([0.78 - 0.2 * stress, 0.12, 0.06 + 0.07 * stress, 0.03 + 0.07 * stress, 0.01 + 0.06 * stress])
    p = p / p.sum()
    r_curr = np.clip(r_orig + rng.choice([0, 1, 2, 3, 4], size=n, p=p), 1, 10).astype(int)

    # delinquency
    pb = np.array([1 - (0.078 + 0.16 * stress), 0.04 + 0.05 * stress, 0.02 + 0.04 * stress,
                   0.010 + 0.03 * stress, 0.008 + 0.04 * stress])
    pb = pb / pb.sum()
    b = rng.choice(5, size=n, p=pb)
    dpd = np.select([b == 0, b == 1, b == 2, b == 3],
                    [np.zeros(n), rng.integers(1, 31, n), rng.integers(31, 61, n), rng.integers(61, 90, n)],
                    default=rng.integers(90, 700, n)).astype(int)

    over = np.where(is_rev & (rng.random(n) < 0.10 + 0.08 * stress), rng.integers(1, 90, n), 0)
    over = np.where(is_rev & (rng.random(n) < 0.01 + 0.01 * stress), rng.integers(90, 200, n), over)

    sovereign = cat == "State government exposures"          # keep the sovereign-like bucket clean
    dpd = np.where(sovereign, 0, dpd)
    over = np.where(sovereign, 0, over)
    watch = (r_curr >= 7) & (rng.random(n) < 0.25)
    impaired = (rng.random(n) < 0.003) & ~sovereign
    is_npa = (dpd >= 90) | impaired | (over >= 90)
    yrs = np.where(is_npa, rng.choice([0.4, 1.5, 2.5, 3.5, 5.0], size=n, p=[0.45, 0.22, 0.14, 0.10, 0.09]), 0.0)

    lo = np.array([CATS[c]["term"][0] for c in cat]); hi = np.array([CATS[c]["term"][1] for c in cat])
    term = np.round(rng.uniform(lo, hi), 1)
    slo = np.array([CATS[c]["sec"][0] for c in cat]); shi = np.array([CATS[c]["sec"][1] for c in cat])
    sec = np.round(rng.uniform(slo, shi))
    eir = np.round(per_cat("eir") + rng.normal(0, 0.7, n), 2)

    df = pd.DataFrame({
        "loan_id": [f"LN{i + 1:05d}" for i in range(n)], "borrower_id": borrower, "category": cat,
        "outstanding": outstanding, "undrawn_limit": undrawn, "is_revolving": is_rev, "amortising": amort,
        "dpd": dpd, "days_over_limit": over, "rating_orig": r_orig, "rating_curr": r_curr,
        "watchlist": watch, "credit_impaired": impaired, "years_in_stage3": yrs, "secured_pct": sec,
        "collateral_type": per_cat("coll"), "remaining_term_yrs": term, "eir_pct": eir,
    })
    return sanitize(df)


def sanitize(df: pd.DataFrame) -> pd.DataFrame:
    """Make any (edited / uploaded) table safe for the engine."""
    d = df.copy()
    for c in COLS:
        if c not in d.columns:
            d[c] = False if c in BOOL_COLS else (NUM_DEFAULT.get(c, ""))
    d = d[COLS].reset_index(drop=True)

    for c in ["loan_id", "borrower_id", "category", "collateral_type"]:
        d[c] = d[c].astype(object).where(d[c].notna(), "")
        d[c] = d[c].astype(str).str.strip()
    blank = d["loan_id"].isin(["", "nan", "None"])
    d.loc[blank, "loan_id"] = [f"NEW-{i + 1:04d}" for i in range(int(blank.sum()))]
    bb = d["borrower_id"].isin(["", "nan", "None"])
    d.loc[bb, "borrower_id"] = d.loc[bb, "loan_id"]
    d.loc[~d["category"].isin(CAT_NAMES), "category"] = DEFAULT_CAT
    d.loc[~d["collateral_type"].isin(COLL_TYPES), "collateral_type"] = "None"

    for c, dv in NUM_DEFAULT.items():
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(dv).astype(float)
    for c in BOOL_COLS:
        d[c] = d[c].fillna(False).astype(bool)

    d["outstanding"] = d["outstanding"].clip(lower=0)
    d["undrawn_limit"] = d["undrawn_limit"].clip(lower=0)
    d["dpd"] = d["dpd"].clip(lower=0).round().astype(int)
    d["days_over_limit"] = d["days_over_limit"].clip(lower=0).round().astype(int)
    d["rating_orig"] = d["rating_orig"].round().clip(1, 10).astype(int)
    d["rating_curr"] = d["rating_curr"].round().clip(1, 10).astype(int)
    d["secured_pct"] = d["secured_pct"].clip(0, 100)
    d["years_in_stage3"] = d["years_in_stage3"].clip(lower=0)
    d["remaining_term_yrs"] = d["remaining_term_yrs"].clip(0.1, 40)
    d["eir_pct"] = d["eir_pct"].clip(0, 60)
    return d


# ----------------------------------------------------------------------------
# 3. ENGINE
# ----------------------------------------------------------------------------
def stage_loans(d: pd.DataFrame, A: dict) -> pd.DataFrame:
    """Para 25-38 / 76-81: Stage 3 (borrower level), Stage 2 (SICR), else Stage 1."""
    npa_dpd = (d["dpd"] >= A["npa_dpd"])
    out_of_order = d["is_revolving"] & (d["days_over_limit"] >= A["npa_dpd"])
    s3_acct = npa_dpd | out_of_order | d["credit_impaired"]
    s3_borrower = s3_acct.groupby(d["borrower_id"]).transform("any")
    is3 = s3_acct | s3_borrower

    t_dpd = d["dpd"] > A["sicr_dpd"]
    t_rev = d["is_revolving"] & (d["days_over_limit"] >= A["rev_days"])
    t_down = (d["rating_curr"] - d["rating_orig"] >= A["notches"]) if A["use_notches"] else pd.Series(False, index=d.index)
    t_watch = d["watchlist"] if A["use_watch"] else pd.Series(False, index=d.index)
    is2 = ~is3 & (t_dpd | t_rev | t_down | t_watch)

    stage = np.where(is3, 3, np.where(is2, 2, 1))

    reason = pd.Series("", index=d.index, dtype=object)
    for flag, txt in [(t_dpd, f"DPD>{A['sicr_dpd']}; "), (t_rev, "Over limit/DP; "),
                      (t_down, f"Downgrade>={A['notches']} notches; "), (t_watch, "Watchlist; ")]:
        reason = reason + np.where(flag, txt, "")
    r3 = np.select([npa_dpd, out_of_order, d["credit_impaired"]],
                   [f"NPA (DPD>={A['npa_dpd']})", "NPA (out of order)", "Credit-impaired flag"],
                   default="Borrower-level Stage 3")
    reason = pd.Series(np.where(stage == 3, r3, np.where(stage == 2, reason, "Performing")), index=d.index)
    out = d.copy()
    out["stage"] = stage
    out["stage_reason"] = reason.str.rstrip("; ").to_numpy()
    return out


def scenario_ecl(r: pd.DataFrame, A: dict, pd_mult: float, lgd_mult: float, grade_pd: np.ndarray) -> np.ndarray:
    n = len(r)
    stage = r["stage"].to_numpy()
    T = r["remaining_term_yrs"].to_numpy()
    ead = r["ead"].to_numpy()

    pd12 = grade_pd[r["rating_curr"].to_numpy() - 1]
    pd12 = np.clip(np.maximum(pd12 * pd_mult, A["pd_floor"]), 0, 1)
    lgd = np.clip(r["lgd"].to_numpy() * lgd_mult, 0, 1)

    K = int(np.ceil(min(T.max(), 40)))
    t = np.arange(1, K + 1)[None, :]
    Tc = T[:, None]
    frac = np.clip(Tc - (t - 1), 0, 1)                                  # share of year t that is inside the term
    surv_start = (1 - pd12[:, None]) ** (t - 1)
    marginal = surv_start * (1 - (1 - pd12[:, None]) ** frac)         # PD of defaulting inside year t
    mask = np.where(stage[:, None] == 1, (t == 1), True)                # Stage 1 -> 12m only, Stage 2 -> lifetime
    ead_t = ead[:, None] * np.where(r["amortising"].to_numpy()[:, None], np.clip(1 - (t - 1) / Tc, 0, 1), 1.0)
    if A["discount"]:
        eir = r["eir_pct"].to_numpy()[:, None] / 100
        dft = (1 + eir) ** (-((t - 1) + frac / 2))
    else:
        dft = 1.0
    ecl12 = (marginal * mask * lgd[:, None] * ead_t * dft).sum(axis=1)
    ecl3 = ead * lgd                                                       # Stage 3: PD = 100%
    return np.where(stage == 3, ecl3, ecl12)


def run_engine(d: pd.DataFrame, A: dict, scen: pd.DataFrame, grade_pd: np.ndarray):
    r = stage_loans(d, A)
    stage = r["stage"].to_numpy()

    # EAD (para 100): balance + CCF x undrawn; no collateral netting. Stage 3 -> drawn balance only.
    r["ead"] = np.where(stage == 3, r["outstanding"], r["outstanding"] + A["ccf"] * r["undrawn_limit"])

    # LGD (para 97/98 backstop): secured x 65% (30% for cash/gold/govt sec/LIC/KVP/NSC) + unsecured x 70%
    sp = r["secured_pct"].to_numpy() / 100
    sec_l = np.where(r["collateral_type"].to_numpy() == SPECIAL_COLL, A["lgd_special"], A["lgd_sec"])
    r["lgd"] = sp * sec_l + (1 - sp) * A["lgd_unsec"]

    w = scen["weight_pct"].to_numpy(float)
    w = w / w.sum() if w.sum() > 0 else np.ones(len(w)) / len(w)
    names = scen["scenario"].tolist()
    for nm, pm, lm in zip(names, scen["pd_mult"], scen["lgd_mult"]):
        r[f"ecl_{nm}"] = scenario_ecl(r, A, float(pm), float(lm), grade_pd)
    r["ecl_model"] = sum(wi * r[f"ecl_{nm}"] for wi, nm in zip(w, names))
    r["ecl_adj"] = r["ecl_model"] * (1 + A["overlay"] / 100)

    # PD shown for information (base scenario, 12m, floored)
    r["pd12_pct"] = np.where(stage == 3, 100.0, np.maximum(grade_pd[r["rating_curr"].to_numpy() - 1], A["pd_floor"]) * 100)

    # ---- Prudential floors (para 82, applied per para 90) -----------------
    s1 = r["category"].map(lambda c: CATS[c]["s1"]).to_numpy(float)
    s2 = r["category"].map(lambda c: CATS[c]["s2"]).to_numpy(float)
    key = r["category"].map(lambda c: CATS[c]["tbl"]).to_numpy()
    yrs = r["years_in_stage3"].to_numpy()
    idx = np.select([yrs < 1, yrs < 2, yrs < 3, yrs < 4], [0, 1, 2, 3], default=4)
    sec_rate = np.zeros(len(r)); uns_rate = np.zeros(len(r))
    for k, tbl in S3_TABLES.items():
        m = key == k
        sec_rate[m] = np.array([x[0] for x in tbl])[idx[m]]
        uns_rate[m] = np.array([x[1] for x in tbl])[idx[m]]
    pct3 = sp * sec_rate + (1 - sp) * uns_rate
    r["floor_pct"] = np.where(stage == 3, pct3, np.where(stage == 2, s2, s1))
    r["s3_bucket"] = np.where(stage == 3, np.array(S3_BUCKETS)[idx], "")
    r["floor_amt"] = r["ead"] * r["floor_pct"] / 100

    r["topup"] = 0.0
    # Stage 3: account level
    m3 = r["stage"] == 3
    r.loc[m3, "topup"] = (r.loc[m3, "floor_amt"] - r.loc[m3, "ecl_adj"]).clip(lower=0)
    # Stage 1/2: portfolio level per category x stage, top-up spread pro-rata to EAD
    m12 = ~m3
    if m12.any():
        g = r.loc[m12].groupby(["category", "stage"])
        gm = g["ecl_adj"].transform("sum"); gf = g["floor_amt"].transform("sum"); ge = g["ead"].transform("sum")
        r.loc[m12, "topup"] = ((gf - gm).clip(lower=0) * r.loc[m12, "ead"] / ge.where(ge > 0, 1)).fillna(0)
    r["provision"] = r["ecl_adj"] + r["topup"]
    r["binding"] = np.where(r["topup"] > 1e-9, "Floor", "Model")
    r["stage_label"] = "Stage " + r["stage"].astype(str)
    return r


def floor_summary(r: pd.DataFrame) -> pd.DataFrame:
    g = r.groupby(["category", "stage_label"]).agg(
        loans=("loan_id", "count"), exposure=("ead", "sum"), model_ecl=("ecl_adj", "sum"),
        floor_required=("floor_amt", "sum"), topup=("topup", "sum"), provision=("provision", "sum")).reset_index()
    # for Stage 3 the floor is account-level: "floor required" should be the sum of account floors (already is)
    g["binding"] = np.where(g["topup"] > 1e-9, "Floor binds", "Model ≥ floor")
    g["coverage_%"] = np.where(g["exposure"] > 0, g["provision"] / g["exposure"] * 100, 0)
    return g


def fmt_amt(x: float) -> str:
    return f"₹{x / 100:,.2f} Cr" if abs(x) >= 100 else f"₹{x:,.1f} L"


# ----------------------------------------------------------------------------
# 4. STATE + SIDEBAR
# ----------------------------------------------------------------------------
if "loans" not in st.session_state:
    st.session_state.loans = generate_loans(400, 42, 0.3)
    st.session_state.ver = 0

st.sidebar.title("🏦 ECL Model Lab")
st.sidebar.caption("RBI ECL Directions 2026 · amounts in ₹ lakh")

with st.sidebar.expander("🎲 Random data generator", expanded=True):
    g_n = st.slider("Number of loans", 50, 5000, 400, step=50)
    g_seed = st.number_input("Random seed", 0, 99999, 42)
    g_stress = st.slider("Portfolio stress", 0.0, 1.0, 0.3, 0.05,
                         help="Higher = more delinquency, downgrades and NPAs")
    if st.button("Generate new data", type="primary", width="stretch"):
        st.session_state.loans = generate_loans(int(g_n), int(g_seed), float(g_stress))
        st.session_state.ver += 1
        st.rerun()
    up = st.file_uploader("…or upload your own CSV", type="csv")
    if up is not None and st.button("Load uploaded CSV", width="stretch"):
        st.session_state.loans = sanitize(pd.read_csv(up))
        st.session_state.ver += 1
        st.rerun()

A = {}
with st.sidebar.expander("1 · Staging rules (para 25-38)"):
    A["npa_dpd"] = st.number_input("Stage 3 / NPA at DPD ≥", 30, 365, 90)
    A["sicr_dpd"] = st.number_input("SICR backstop: DPD >", 0, 90, 30, help="Para 33: rebuttable 30-DPD presumption")
    A["rev_days"] = st.number_input("Revolving: days over limit/DP ≥", 1, 89, 60, help="Para 33, revolving facilities")
    A["use_notches"] = st.checkbox("SICR on rating downgrade", True)
    A["notches"] = st.number_input("…notches (must be defined in policy, para 30)", 1, 9, 3)
    A["use_watch"] = st.checkbox("SICR on watchlist", True)

with st.sidebar.expander("2 · PD, LGD, EAD (para 96-100)"):
    A["pd_floor"] = st.number_input("12m PD floor (%)", 0.0, 5.0, 0.03, 0.01, format="%.2f") / 100
    A["lgd_sec"] = st.number_input("LGD - secured portion (%)", 0.0, 100.0, 65.0) / 100
    A["lgd_unsec"] = st.number_input("LGD - unsecured portion (%)", 0.0, 100.0, 70.0) / 100
    A["lgd_special"] = st.number_input("LGD - cash/gold/govt sec/LIC/KVP/NSC (%)", 0.0, 100.0, 30.0) / 100
    A["ccf"] = st.number_input("CCF on undrawn limits (%)", 0.0, 100.0, 40.0,
                               help="Placeholder: take the value from the Standardised Approach Directions") / 100
    st.caption("12-month PD by internal rating grade (%) — editable")
    pd_tbl = st.data_editor(pd.DataFrame({"grade": range(1, 11), "pd_pct": DEFAULT_PD}),
                            hide_index=True, disabled=["grade"], key="pd_tbl", width="stretch")

with st.sidebar.expander("3 · Scenarios, discounting, overlay (para 47-54)"):
    st.caption("Probability-weighted scenarios")
    scen = st.data_editor(pd.DataFrame({"scenario": ["Base", "Upside", "Downside"],
                                        "weight_pct": [60.0, 20.0, 20.0],
                                        "pd_mult": [1.0, 0.8, 1.5], "lgd_mult": [1.0, 0.95, 1.1]}),
                          hide_index=True, disabled=["scenario"], key="scen", width="stretch")
    if abs(scen["weight_pct"].sum() - 100) > 0.01:
        st.warning(f"Weights sum to {scen['weight_pct'].sum():.1f}% — they will be normalised.")
    A["discount"] = st.checkbox("Discount at loan EIR", True)
    A["overlay"] = st.number_input("Post-model adjustment / overlay (% of ECL)", -50.0, 200.0, 0.0,
                                   help="Must be documented and governed (para 131 / Annex 4 Table 6)")

grade_pd = np.array(pd_tbl.sort_values("grade")["pd_pct"].clip(0, 100), float) / 100

# ----------------------------------------------------------------------------
# 5. LAYOUT
# ----------------------------------------------------------------------------
st.title("RBI ECL Model Lab")
st.caption("Edit the data or the assumptions — staging, ECL, floors and the dashboard recompute instantly.")
tab_dash, tab_data, tab_calc, tab_floor, tab_rep, tab_guide = st.tabs(
    ["📊 Dashboard", "🗂️ Data (editable)", "🧮 Account-level ECL", "🧱 Prudential floors",
     "📑 Annex-4 style tables", "📖 Guide & limits"])

# ---- Data tab (rendered first: its output feeds everything) ------------------
with tab_data:
    st.markdown("**Loan book** — edit cells, add rows (＋ at the bottom) or delete rows. Everything else updates.")
    edited = st.data_editor(
        st.session_state.loans, num_rows="dynamic", height=480, width="stretch",
        key=f"editor_{st.session_state.ver}",
        column_config={
            "category": st.column_config.SelectboxColumn("RBI product category", options=CAT_NAMES, required=True, width="large"),
            "collateral_type": st.column_config.SelectboxColumn("Collateral", options=COLL_TYPES, width="medium"),
            "outstanding": st.column_config.NumberColumn("Outstanding (₹ L)", min_value=0, format="%.2f"),
            "undrawn_limit": st.column_config.NumberColumn("Undrawn (₹ L)", min_value=0, format="%.2f"),
            "dpd": st.column_config.NumberColumn("DPD", min_value=0, step=1),
            "days_over_limit": st.column_config.NumberColumn("Days over limit/DP", min_value=0, step=1),
            "rating_orig": st.column_config.NumberColumn("Rating @origination (1-10)", min_value=1, max_value=10, step=1),
            "rating_curr": st.column_config.NumberColumn("Rating now (1-10)", min_value=1, max_value=10, step=1),
            "years_in_stage3": st.column_config.NumberColumn("Years in Stage 3", min_value=0, format="%.1f"),
            "secured_pct": st.column_config.NumberColumn("Secured %", min_value=0, max_value=100),
            "remaining_term_yrs": st.column_config.NumberColumn("Remaining term (yrs)", min_value=0.1, format="%.1f"),
            "eir_pct": st.column_config.NumberColumn("EIR %", min_value=0, format="%.2f"),
        })
    loans = sanitize(edited)
    c1, c2 = st.columns([1, 3])
    c1.download_button("⬇️ Download data (CSV)", loans.to_csv(index=False), "loan_book.csv", "text/csv")
    c2.caption(f"{len(loans):,} loans · rating 1 = best, 10 = worst · 'Secured %' = share of exposure covered by eligible collateral · "
               "Years in Stage 3 only matters for Stage 3 loans.")
    if loans["loan_id"].duplicated().any():
        st.warning("Duplicate loan_id values found.")

if loans.empty:
    st.info("The loan book is empty — generate or add some loans.")
    st.stop()

R = run_engine(loans, A, scen, grade_pd)
FS = floor_summary(R)

tot_out = R["outstanding"].sum(); tot_ead = R["ead"].sum()
tot_model = R["ecl_adj"].sum(); tot_prov = R["provision"].sum(); tot_top = R["topup"].sum()

# ---- Dashboard ---------------------------------------------------------------
with tab_dash:
    k = st.columns(6)
    k[0].metric("Gross exposure", fmt_amt(tot_out))
    k[1].metric("Model ECL", fmt_amt(tot_model))
    k[2].metric("Final provision", fmt_amt(tot_prov), f"+{fmt_amt(tot_top)} from floors" if tot_top > 0 else "no floor top-up")
    k[3].metric("Coverage ratio", f"{tot_prov / tot_out * 100:.2f}%" if tot_out else "–")
    k[4].metric("Stage 2 share", f"{R.loc[R.stage == 2, 'outstanding'].sum() / tot_out * 100:.1f}%" if tot_out else "–")
    k[5].metric("Stage 3 share", f"{R.loc[R.stage == 3, 'outstanding'].sum() / tot_out * 100:.1f}%" if tot_out else "–")

    by_stage = R.groupby("stage_label").agg(loans=("loan_id", "count"), exposure=("outstanding", "sum"),
                                            provision=("provision", "sum"), model=("ecl_adj", "sum")).reset_index()
    by_stage["coverage_%"] = by_stage["provision"] / by_stage["exposure"].where(by_stage["exposure"] > 0, 1) * 100

    a, b = st.columns(2)
    with a:
        st.subheader("Exposure by stage")
        st.altair_chart(alt.Chart(by_stage).mark_arc(innerRadius=70).encode(
            theta="exposure:Q", color=alt.Color("stage_label:N", scale=STAGE_COLORS, title="Stage"),
            tooltip=["stage_label", "loans", alt.Tooltip("exposure:Q", format=",.0f")]).properties(height=300),
            width="stretch")
    with b:
        st.subheader("Provision and coverage by stage")
        bars = alt.Chart(by_stage).mark_bar().encode(
            x=alt.X("stage_label:N", title=None), y=alt.Y("provision:Q", title="Provision (₹ L)"),
            color=alt.Color("stage_label:N", scale=STAGE_COLORS, legend=None),
            tooltip=["stage_label", alt.Tooltip("provision:Q", format=",.0f"), alt.Tooltip("coverage_%:Q", format=".2f")])
        txt = bars.mark_text(dy=-8).encode(text=alt.Text("coverage_%:Q", format=".2f"))
        st.altair_chart((bars + txt).properties(height=300), width="stretch")
        st.caption("Number above each bar = coverage % (provision ÷ exposure)")

    c, d_ = st.columns(2)
    with c:
        st.subheader("Provision by product category")
        st.altair_chart(alt.Chart(FS).mark_bar().encode(
            y=alt.Y("category:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260)),
            x=alt.X("sum(provision):Q", title="Provision (₹ L)"),
            color=alt.Color("stage_label:N", scale=STAGE_COLORS, title="Stage"),
            tooltip=["category", "stage_label", alt.Tooltip("provision:Q", format=",.0f")]).properties(height=420),
            width="stretch")
    with d_:
        st.subheader("Model ECL vs final provision (after floors)")
        cat_cmp = R.groupby("category").agg(model_ecl=("ecl_adj", "sum"), provision=("provision", "sum")).reset_index()
        cat_long = cat_cmp.melt("category", var_name="measure", value_name="amount")
        cat_long["measure"] = cat_long["measure"].map({"model_ecl": "Model ECL", "provision": "Final (with floors)"})
        st.altair_chart(alt.Chart(cat_long).mark_bar().encode(
            y=alt.Y("category:N", sort="-x", title=None, axis=alt.Axis(labelLimit=260)),
            x=alt.X("amount:Q", title="₹ lakh"), yOffset="measure:N",
            color=alt.Color("measure:N", scale=alt.Scale(range=["#8aa4c8", "#e8793a"]), title=None),
            tooltip=["category", "measure", alt.Tooltip("amount:Q", format=",.0f")]).properties(height=420),
            width="stretch")

    e, f = st.columns(2)
    with e:
        st.subheader("Scenario view (total ECL before floors)")
        names = scen["scenario"].tolist()
        sc = pd.DataFrame({"scenario": names + ["Weighted"],
                           "ecl": [R[f"ecl_{n}"].sum() * (1 + A["overlay"] / 100) for n in names] + [tot_model]})
        st.altair_chart(alt.Chart(sc).mark_bar().encode(
            x=alt.X("scenario:N", sort=None, title=None), y=alt.Y("ecl:Q", title="ECL (₹ L)"),
            color=alt.condition(alt.datum.scenario == "Weighted", alt.value("#e8793a"), alt.value("#8aa4c8")),
            tooltip=["scenario", alt.Tooltip("ecl:Q", format=",.0f")]).properties(height=300), width="stretch")
    with f:
        st.subheader("Exposure by DPD bucket and stage")
        R["dpd_bucket"] = pd.cut(R["dpd"], [-1, 0, 30, 60, 89, 10**6],
                                 labels=["Current", "1-30", "31-60", "61-89", "90+"]).astype(str)
        dd = R.groupby(["dpd_bucket", "stage_label"])["outstanding"].sum().reset_index()
        st.altair_chart(alt.Chart(dd).mark_bar().encode(
            x=alt.X("dpd_bucket:N", sort=["Current", "1-30", "31-60", "61-89", "90+"], title="Days past due"),
            y=alt.Y("outstanding:Q", title="Exposure (₹ L)"),
            color=alt.Color("stage_label:N", scale=STAGE_COLORS, title="Stage"),
            tooltip=["dpd_bucket", "stage_label", alt.Tooltip("outstanding:Q", format=",.0f")]).properties(height=300),
            width="stretch")

    binding = FS[FS["topup"] > 1e-9].sort_values("topup", ascending=False)
    if len(binding):
        top = binding.iloc[0]
        st.info(f"🧱 **Prudential floors bind in {len(binding)} category-stage buckets** and add {fmt_amt(tot_top)} "
                f"({tot_top / tot_prov * 100:.1f}% of the final provision). Largest top-up: **{top['category']} – {top['stage_label']}** "
                f"({fmt_amt(top['topup'])}). Your model numbers are below RBI's backstop there — expect questions.")
    else:
        st.success("Model ECL is above the RBI prudential floor in every bucket.")

# ---- Account-level tab -------------------------------------------------------
with tab_calc:
    st.markdown("**Every loan, step by step:** stage → PD/LGD/EAD → ECL → floor → final provision.")
    f1, f2, f3 = st.columns(3)
    sel_stage = f1.multiselect("Stage", ["Stage 1", "Stage 2", "Stage 3"], ["Stage 1", "Stage 2", "Stage 3"])
    sel_cat = f2.multiselect("Category", CAT_NAMES)
    sel_bind = f3.selectbox("Binding", ["All", "Floor", "Model"])
    v = R[R["stage_label"].isin(sel_stage)]
    if sel_cat: v = v[v["category"].isin(sel_cat)]
    if sel_bind != "All": v = v[v["binding"] == sel_bind]
    show = ["loan_id", "borrower_id", "category", "stage_label", "stage_reason", "outstanding", "ead", "pd12_pct", "lgd",
            "ecl_adj", "floor_pct", "s3_bucket", "floor_amt", "topup", "provision", "binding"]
    st.dataframe(v[show], hide_index=True, width="stretch", height=520, column_config={
        "stage_label": "Stage", "stage_reason": "Why", "outstanding": st.column_config.NumberColumn("Outstanding", format="%.1f"),
        "ead": st.column_config.NumberColumn("EAD", format="%.1f"), "pd12_pct": st.column_config.NumberColumn("12m PD %", format="%.2f"),
        "lgd": st.column_config.NumberColumn("LGD", format="%.2f"), "ecl_adj": st.column_config.NumberColumn("Model ECL", format="%.2f"),
        "floor_pct": st.column_config.NumberColumn("Floor %", format="%.2f"), "s3_bucket": "Yrs in S3",
        "floor_amt": st.column_config.NumberColumn("Floor ₹", format="%.2f"), "topup": st.column_config.NumberColumn("Floor top-up", format="%.2f"),
        "provision": st.column_config.NumberColumn("Final provision", format="%.2f")})
    st.download_button("⬇️ Download results (CSV)", R[show].to_csv(index=False), "ecl_results.csv", "text/csv")

# ---- Floors tab --------------------------------------------------------------
with tab_floor:
    st.markdown("**Para 90:** Stage 1/2 floors apply per product category per stage on a *portfolio* basis; "
                "Stage 3 floors apply *account by account*. Final provision = the higher of model and floor.")
    st.dataframe(FS.sort_values(["category", "stage_label"]), hide_index=True, width="stretch", height=520, column_config={
        "category": "Category", "stage_label": "Stage", "exposure": st.column_config.NumberColumn("Exposure (EAD)", format="%.1f"),
        "model_ecl": st.column_config.NumberColumn("Model ECL", format="%.1f"),
        "floor_required": st.column_config.NumberColumn("Floor required", format="%.1f"),
        "topup": st.column_config.NumberColumn("Top-up", format="%.1f"),
        "provision": st.column_config.NumberColumn("Final provision", format="%.1f"),
        "coverage_%": st.column_config.NumberColumn("Coverage %", format="%.2f")})
    st.markdown("**Floor rates used (Stage 1 / Stage 2)**")
    st.dataframe(pd.DataFrame([{"category": k, "Stage 1 %": v["s1"], "Stage 2 %": v["s2"], "Stage 3 table": v["tbl"]}
                               for k, v in CATS.items()]), hide_index=True, width="stretch")
    st.markdown("**Stage 3 floor tables (secured % / unsecured %) by time spent in Stage 3**")
    st.dataframe(pd.DataFrame({t: [f"{a}/{b}" for a, b in tbl] for t, tbl in S3_TABLES.items()}, index=S3_BUCKETS),
                 width="stretch")
    st.caption("A = corporate, MSME, farm, FI, secured retail, restructured, other · B = TD/LIC/KVP, gold, state govt, housing, "
               "CG-guaranteed · C = other residential / commercial RE · UR = unsecured retail.")

# ---- Reporting tab -----------------------------------------------------------
with tab_rep:
    st.markdown("Simplified versions of the **Annex 4** disclosure tables (credit quality and allowance by stage).")
    st.subheader("A. Gross carrying amount and loss allowance by DPD bucket and stage")
    order = ["Current", "1-30", "31-60", "61-89", "90+"]
    gca = R.pivot_table(index="dpd_bucket", columns="stage_label", values="outstanding", aggfunc="sum", fill_value=0)
    alw = R.pivot_table(index="dpd_bucket", columns="stage_label", values="provision", aggfunc="sum", fill_value=0)
    for s in ["Stage 1", "Stage 2", "Stage 3"]:
        for t_ in (gca, alw):
            if s not in t_.columns: t_[s] = 0.0
    gca = gca[["Stage 1", "Stage 2", "Stage 3"]].reindex(order).fillna(0)
    alw = alw[["Stage 1", "Stage 2", "Stage 3"]].reindex(order).fillna(0)
    gca["Total"] = gca.sum(axis=1); alw["Total"] = alw.sum(axis=1)
    gca.loc["Gross carrying amount"] = gca.sum(); alw.loc["Impairment loss allowance"] = alw.sum()
    tA = pd.concat([gca, alw.loc[["Impairment loss allowance"]]])
    tA.loc["Net carrying amount"] = tA.loc["Gross carrying amount"] - tA.loc["Impairment loss allowance"]
    st.dataframe(tA.style.format("{:,.1f}"), width="stretch")

    st.subheader("B. By product category and stage")
    tB = R.pivot_table(index="category", columns="stage_label", values=["outstanding", "provision"], aggfunc="sum", fill_value=0)
    tB.columns = [f"{'Gross' if a == 'outstanding' else 'Allowance'} · {b}" for a, b in tB.columns]
    tB["Gross · Total"] = tB[[c for c in tB.columns if c.startswith("Gross")]].sum(axis=1)
    tB["Allowance · Total"] = tB[[c for c in tB.columns if c.startswith("Allowance")]].sum(axis=1)
    tB["Coverage %"] = tB["Allowance · Total"] / tB["Gross · Total"].where(tB["Gross · Total"] > 0, 1) * 100
    st.dataframe(tB.style.format("{:,.1f}"), width="stretch")

    st.subheader("C. Assumptions snapshot (Annex 4 Tables 4-6 style)")
    st.dataframe(pd.DataFrame({
        "Item": ["Stage 3 trigger", "SICR - DPD backstop", "SICR - revolving", "SICR - rating downgrade", "SICR - watchlist",
                 "12m PD floor", "LGD secured / unsecured / special", "CCF", "Discounting", "Overlay"],
        "Value": [f"DPD ≥ {A['npa_dpd']} / out of order / flag / borrower-level", f"DPD > {A['sicr_dpd']}",
                  f"days over limit ≥ {A['rev_days']}", f"≥ {A['notches']} notches" if A["use_notches"] else "off",
                  "on" if A["use_watch"] else "off", f"{A['pd_floor'] * 100:.2f}%",
                  f"{A['lgd_sec'] * 100:.0f}% / {A['lgd_unsec'] * 100:.0f}% / {A['lgd_special'] * 100:.0f}%",
                  f"{A['ccf'] * 100:.0f}%", "EIR" if A["discount"] else "none", f"{A['overlay']:+.1f}% of ECL"]}),
        hide_index=True, width="stretch")

# ---- Guide ----------------------------------------------------------------------
with tab_guide:
    st.markdown("""
### How the engine works (one loan, five steps)
1. **Category** – every loan sits in one RBI product category (para 82, 91-92). That decides which floor applies.
2. **Stage** – *Stage 3* if NPA (DPD ≥ 90, out-of-order, credit-impaired flag) **and the same borrower's other loans follow** (para 76);
   *Stage 2* if SICR (DPD > 30, revolving over limit, rating downgrade, watchlist); otherwise *Stage 1*.
3. **PD · LGD · EAD**
   - PD: 12-month PD from the rating-grade table, floored at 0.03% (para 96). Stage 2 uses a **lifetime** curve: `1 − (1 − PD)^years`, built year by year. Stage 3 PD = 100%.
   - LGD: backstop (para 97-98): `secured% × 65% (30% for cash/gold/govt sec/LIC/KVP/NSC) + unsecured% × 70%`.
   - EAD: `outstanding + CCF × undrawn` (para 100). Collateral is *not* netted off.
4. **ECL** = Σ over years of `marginal PD × LGD × EAD × discount factor`, run in each scenario, then probability-weighted (para 47-49).
5. **Floors** – `provision = max(model ECL, RBI floor)`: Stage 1/2 per category-stage bucket, Stage 3 per account (para 82, 90).

### Simplifications you should know about
- **PD** is a grade lookup table with a constant-hazard term structure. A real model needs default history, TTC→PIT calibration and macro links.
- **Para 45 caution:** lifetime PD is *not* just a scaled Stage 1 PD in a proper model; here Stage 2 loans get a higher PD only through their worse current rating.
- **LGD** uses the regulatory backstop, allowed only if you cannot estimate LGD reliably (para 97). Document why.
- **CCF** is a single placeholder (40%) – take real values from the Standardised Approach Directions.
- **Floor base** = EAD (Stage 3: drawn balance). Check how your bank reads the base for off-balance items.
- **Scenarios** are PD/LGD multipliers, not a macro model.
- Revolving SICR uses days-over-limit *and* the DPD test (conservative reading of para 33).

### Not covered here
POCI assets · investments and other financial instruments (para 83-86) · ADC / project-finance DCCO add-ons · cure / upgrade probation rules ·
Stage-2 rebuttal documentation (para 34-35) · transition arrangements and CET1 add-back · loss-allowance roll-forward (needs a prior-period snapshot) ·
trade/lease receivables provision matrix (Annex 2) · governance, validation, back-testing and audit trail (Chapter V, Annex 3).

*Educational prototype built from the guideline text; not a validated model and not regulatory advice.*
""")
