"""
Simple ECL app (RBI expected-credit-loss framework, FY2027-28 onwards)
Run:  streamlit run app.py
Only 'see-through' models are used: decision trees + plain averages. Every number can be traced.
"""
import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from scipy.stats import binomtest
from sklearn.metrics import roc_auc_score, roc_curve
from sklearn.tree import DecisionTreeClassifier, DecisionTreeRegressor, export_text, plot_tree

st.set_page_config(page_title="Simple ECL – RBI FY2027-28", page_icon="🏦", layout="wide")
st.markdown(
    """<style>[data-testid="stMetric"]{background:rgba(128,128,128,.08);border:1px solid rgba(128,128,128,.25);
    border-radius:10px;padding:10px 14px}</style>""",
    unsafe_allow_html=True,
)

H = 30  # max horizon in years
FEATS = ["rating", "dpd", "utilisation", "secured_pct", "remaining_term_yrs"]
DEV_COLS = ["acct_id", "category", "snapshot_year", "rating", "dpd", "utilisation", "secured_pct",
            "remaining_term_yrs", "outstanding", "default_year", "lgd_obs"]
PROD_COLS = ["acct_id", "category", "outstanding", "undrawn_limit", "dpd", "rating", "orig_rating",
             "utp_flag", "watchlist", "secured_pct", "remaining_term_yrs", "eir"]
DEV_NUM = [c for c in DEV_COLS if c not in ("acct_id", "category")]
PROD_NUM = [c for c in PROD_COLS if c not in ("acct_id", "category")]
STAGE_COL = {"Stage 1": "#2e7d32", "Stage 2": "#f9a825", "Stage 3": "#c62828"}


# ───────────────────────────── demo data ─────────────────────────────
@st.cache_data(show_spinner=False)
def make_demo(n_dev, n_prod, seed):
    rng = np.random.default_rng(seed)
    cats = ["Home", "Personal", "MSME", "Corporate"]
    share, r_mu = [.35, .30, .20, .15], [2.8, 3.8, 4.0, 3.2]
    s_lo, s_hi, t_lo, t_hi = [.7, 0, 0, 0], [1, 0, .8, .7], [5, 1, 1, 1], [25, 5, 7, 8]
    size, eir_c, pdm = [40, 5, 80, 600], [.09, .13, .11, .10], [.6, 1.3, 1.2, .9]
    base = np.array([.003, .007, .015, .03, .06, .12, .25])
    macro = {2015: 1.0, 2016: .9, 2017: .9, 2018: 1.1, 2019: 1.2, 2020: 1.8, 2021: 1.5, 2022: .9, 2023: .8, 2024: .8}

    def book(n, max_dpd):
        cat = rng.choice(cats, n, p=share)
        idx = pd.Categorical(cat, categories=cats).codes
        A = lambda a: np.array(a)[idx]
        rating = np.clip(np.round(rng.normal(A(r_mu), 1.3)), 1, 7).astype(int)
        dpd = np.where(rng.random(n) < 0.03 * rating, rng.integers(1, max_dpd, n), 0)
        util = np.clip(rng.beta(2, 2, n), .05, 1).round(3)
        sec = rng.uniform(A(s_lo), A(s_hi)).round(3)
        term = rng.uniform(A(t_lo), A(t_hi)).round(2)
        out = (rng.lognormal(0, .6, n) * A(size)).round(2)
        eir = (A(eir_c) + rng.normal(0, .01, n)).round(4)
        pd12 = base[rating - 1] * A(pdm) * (1 + dpd / 60) * (1 + .3 * util) * (1 - .3 * sec)
        return cat, idx, rating, dpd, util, sec, term, out, eir, pd12

    # development (history) data – performing accounts at each snapshot year, with outcomes
    cat, idx, rating, dpd, util, sec, term, out, eir, pd12 = book(n_dev, 90)
    yr = rng.choice(list(macro), n_dev)
    h0 = np.clip(pd12 * np.array([macro[y] for y in yr]), 0, .9)
    dy, alive = np.zeros(n_dev, int), np.ones(n_dev, bool)
    for t in range(1, 6):
        hit = alive & (rng.random(n_dev) < np.clip(h0 * (1 + .15 * (t - 1)), 0, .9))
        dy[hit] = t
        alive &= ~hit
    lgd = np.clip(.65 * (1 - .75 * sec) + np.array([0, .1, .05, 0])[idx] + .02 * (rating - 4)
                  + rng.normal(0, .08, n_dev), .03, 1)
    dev = pd.DataFrame({"acct_id": [f"D{i:06d}" for i in range(n_dev)], "category": cat, "snapshot_year": yr,
                        "rating": rating, "dpd": dpd, "utilisation": util, "secured_pct": sec,
                        "remaining_term_yrs": term, "outstanding": out, "default_year": dy,
                        "lgd_obs": np.where(dy > 0, lgd.round(3), np.nan)})

    # production (current book)
    cat, idx, rating, dpd, util, sec, term, out, eir, _ = book(n_prod, 125)
    orig = np.clip(rating - rng.choice([-1, 0, 0, 0, 1, 1, 2, 3], n_prod), 1, 7)
    corp = np.isin(cat, ["MSME", "Corporate"])
    prod = pd.DataFrame({
        "acct_id": [f"P{i:06d}" for i in range(n_prod)], "category": cat, "outstanding": out,
        "undrawn_limit": np.where(corp, out * rng.uniform(0, .6, n_prod), 0).round(2), "dpd": dpd,
        "rating": rating, "orig_rating": orig,
        "utp_flag": (((rating == 7) & (rng.random(n_prod) < .3)) | (rng.random(n_prod) < .004)).astype(int),
        "watchlist": (rng.random(n_prod) < (.02 + .03 * (rating >= 5))).astype(int),
        "secured_pct": sec, "remaining_term_yrs": term, "eir": eir})

    # a few deliberate data-quality problems so Step 1 has something to find
    dev.loc[dev.sample(frac=.008, random_state=seed).index, "secured_pct"] = np.nan
    dev = pd.concat([dev, dev.sample(frac=.003, random_state=seed)], ignore_index=True)
    prod.loc[prod.sample(frac=.007, random_state=seed).index, "rating"] = np.nan
    prod.loc[prod.sample(frac=.005, random_state=seed + 1).index, "eir"] = np.nan
    prod.loc[prod.sample(3, random_state=seed).index, "dpd"] = -5
    prod = pd.concat([prod, prod.sample(5, random_state=seed)], ignore_index=True)
    return dev, prod


# ───────────────────────────── data quality ─────────────────────────────
def coerce(df, kind):
    d = df.copy()
    for c in (DEV_NUM if kind == "dev" else PROD_NUM):
        if c in ("utp_flag", "watchlist"):
            d[c] = d[c].replace({True: 1, False: 0, "Y": 1, "N": 0, "Yes": 1, "No": 0})
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["acct_id"] = d["acct_id"].astype(str)
    d["category"] = d["category"].astype(str).str.strip().replace({"nan": np.nan, "None": np.nan, "": np.nan})
    return d


def dq_checks(df, kind):
    d, n = coerce(df, kind), max(len(df), 1)
    req = DEV_COLS if kind == "dev" else PROD_COLS
    c = {"Missing / non-numeric values": d[[x for x in req if x != "lgd_obs"]].isna().any(axis=1),
         "Duplicate rows": d.duplicated(keep="first") if kind == "dev" else d.duplicated("acct_id", keep="first"),
         "Rating outside 1–7": (d.rating < 1) | (d.rating > 7),
         "Negative DPD": d.dpd < 0,
         "Outstanding ≤ 0": d.outstanding <= 0,
         "Secured % outside 0–1": (d.secured_pct < 0) | (d.secured_pct > 1),
         "Remaining term ≤ 0": d.remaining_term_yrs <= 0}
    if kind == "dev":
        c["Utilisation outside 0–1"] = (d.utilisation < 0) | (d.utilisation > 1)
        c["Default year not in 0–5"] = ~d.default_year.isin(range(0, 6)) & d.default_year.notna()
        c["Defaulted but LGD missing"] = (d.default_year > 0) & d.lgd_obs.isna()
        c["LGD outside 0–1"] = (d.lgd_obs < 0) | (d.lgd_obs > 1)
    else:
        c["Undrawn limit negative"] = d.undrawn_limit < 0
        c["EIR outside 0–50%"] = (d.eir < 0) | (d.eir > .5)
        c["Flags not 0/1"] = (~d.utp_flag.isin([0, 1]) & d.utp_flag.notna()) | (~d.watchlist.isin([0, 1]) & d.watchlist.notna())
    tbl = pd.DataFrame({"Check": list(c), "Rows flagged": [int(v.sum()) for v in c.values()]})
    tbl["% of rows"] = tbl["Rows flagged"] / n * 100
    tbl["Status"] = np.where(tbl["Rows flagged"] == 0, "✅ Clean", np.where(tbl["% of rows"] < 1, "⚠️ Minor", "❌ Fix"))
    score = 100 * (1 - pd.concat(list(c.values()), axis=1).any(axis=1).mean())
    return tbl, score


def prepare(df, kind):
    """Auto-fix: drop duplicates / unusable rows, fill gaps with median, clip to valid ranges."""
    d = coerce(df, kind)
    n0 = len(d)
    d = d[d.category.notna()]
    d = d.drop_duplicates() if kind == "dev" else d.drop_duplicates("acct_id")
    if kind == "dev":
        d = d[d.default_year.isin(range(0, 6)) & d.snapshot_year.notna()]
    d = d[d.outstanding > 0].copy()
    num = [c for c in (DEV_NUM if kind == "dev" else PROD_NUM) if c not in ("lgd_obs", "default_year", "snapshot_year")]
    filled = int(d[num].isna().sum().sum())
    if kind == "prod":
        d["orig_rating"] = d["orig_rating"].fillna(d["rating"])
    for c in num:
        d[c] = d[c].fillna(0 if c in ("utp_flag", "watchlist") else d[c].median())
    d["rating"] = d.rating.round().clip(1, 7).astype(int)
    d["dpd"] = d.dpd.clip(lower=0)
    d["secured_pct"] = d.secured_pct.clip(0, 1)
    d["remaining_term_yrs"] = d.remaining_term_yrs.clip(lower=.25)
    if kind == "dev":
        d["utilisation"] = d.utilisation.clip(0, 1)
        d["default_year"] = d.default_year.astype(int)
        d["snapshot_year"] = d.snapshot_year.astype(int)
        m = (d.default_year > 0) & d.lgd_obs.isna()
        filled += int(m.sum())
        d.loc[m, "lgd_obs"] = d.loc[d.default_year > 0, "lgd_obs"].median()
        d["lgd_obs"] = d.lgd_obs.clip(0, 1)
    else:
        d["orig_rating"] = d.orig_rating.round().clip(1, 7).astype(int)
        d["undrawn_limit"] = d.undrawn_limit.clip(lower=0)
        d["eir"] = d.eir.clip(0, .5)
        d["utp_flag"] = (d.utp_flag > 0).astype(int)
        d["watchlist"] = (d.watchlist > 0).astype(int)
        d["utilisation"] = d.outstanding / (d.outstanding + d.undrawn_limit)
    return d.reset_index(drop=True), {"dropped": n0 - len(d), "filled": filled}


# ───────────────────────────── model helpers ─────────────────────────────
def leaf_rules(t, feats):
    tr, out = t.tree_, {}

    def walk(node, conds):
        if tr.children_left[node] == -1:
            out[node] = " AND ".join(conds) if conds else "all accounts"
            return
        f, th = feats[tr.feature[node]], tr.threshold[node]
        walk(tr.children_left[node], conds + [f"{f} ≤ {th:.2f}"])
        walk(tr.children_right[node], conds + [f"{f} > {th:.2f}"])

    walk(0, [])
    return out


@st.cache_data(show_spinner=False)
def fit_pools(dev_tr, max_leaves, min_leaf):
    models = {}
    for c, d in dev_tr.groupby("category"):
        y = (d.default_year == 1).astype(int)
        t = DecisionTreeClassifier(max_leaf_nodes=int(max_leaves), min_samples_leaf=int(min_leaf),
                                   random_state=0).fit(d[FEATS], y)
        leaves = t.apply(d[FEATS])
        order = pd.Series(y.values).groupby(leaves).mean().sort_values().index  # P1 = lowest risk
        models[c] = (t, {leaf: i + 1 for i, leaf in enumerate(order)}, leaf_rules(t, FEATS))
    return models


def assign_pool(df, models):
    pool = pd.Series(np.nan, index=df.index, dtype=object)
    for c, (t, rank, _) in models.items():
        m = (df.category == c).values
        if m.any():
            pool[m] = [f"{c}-P{rank[l]}" for l in t.apply(df.loc[m, FEATS])]
    return pool


def build_curves(dev_tr, pool, floor):
    d = dev_tr.assign(pool=pool)
    d = d[d.pool.notna()]
    yearly = (d.assign(d12=(d.default_year == 1).astype(int)).groupby(["pool", "snapshot_year"]).d12.mean().unstack())
    lra = yearly.mean(axis=1).clip(lower=floor)  # long-run average = mean of yearly default rates
    hz = {}
    for p, g in d.groupby("pool"):
        h = np.array([(g.default_year == t).sum() / max(((g.default_year == 0) | (g.default_year >= t)).sum(), 1)
                      for t in range(1, 6)])
        h = h * (lra[p] / h[0]) if h[0] > 0 else np.full(5, floor)  # keep curve shape, anchor level to LRA
        h = np.clip(h, floor, .99)
        hz[p] = np.concatenate([h, np.full(H - 5, h[-1])])
    return lra, yearly, hz


def marg_from_h(h):
    surv = np.cumprod(1 - h)
    return h * np.concatenate([[1], surv[:-1]])


def pit_h(h, S, R):
    t = np.arange(1, H + 1)
    return np.clip(h * (1 + (S - 1) * np.clip(1 - (t - 1) / R, 0, 1)), 0, .99)


def stage_accounts(p, r, rating_pd):
    p = p.copy()
    p["pd_orig"], p["pd_curr"] = p.orig_rating.map(rating_pd), p.rating.map(rating_pd)
    p["notches"] = p.rating - p.orig_rating
    p["s3_dpd"], p["s3_utp"] = p.dpd > r["dpd3"], (p.utp_flag == 1) & r["use_utp"]
    p["s2_dpd"], p["s2_watch"] = p.dpd > r["dpd2"], (p.watchlist == 1) & r["use_watch"]
    p["s2_notch"] = p.notches >= p.category.map(r["notch"]).fillna(2)
    rel, ab = p.pd_curr / p.pd_orig >= r["rel"], (p.pd_curr - p.pd_orig) >= r["abs"]
    p["s2_pd"] = (rel & ab) if r["mode"].startswith("Both") else (rel | ab)
    s3 = p.s3_dpd | p.s3_utp
    s2 = p.s2_dpd | p.s2_watch | p.s2_notch | p.s2_pd
    p["stage"] = np.where(s3, 3, np.where(s2, 2, 1))
    return p


def compute_book(p, marg_w, lgd_map, ccf):
    p = p.copy()
    cc = ccf.set_index("category")
    p["ccf"], p["amortising"] = p.category.map(cc.ccf), p.category.map(cc.amortising).astype(bool)
    p["ead"] = p.outstanding + p.ccf * p.undrawn_limit
    p["lgd"] = p.pool.map(lgd_map)
    T = np.clip(p.remaining_term_yrs.values, .25, H)[:, None]
    t = np.arange(1, H + 1)[None, :]
    w = np.clip(T - (t - 1), 0, 1)                                   # share of year t inside remaining life
    prof = np.where(p.amortising.values[:, None], np.clip(1 - (t - 1) / T, 0, 1), 1.0)  # exposure profile
    dfac = (1 + p.eir.values[:, None]) ** (-t)                        # discount at EIR
    M = np.array([marg_w[x] for x in p.pool])
    base = (p.ead * p.lgd).values
    p["pd12"], p["pd_life"] = (M * w)[:, 0], (M * w).sum(1)
    p["ecl12"] = base * (M * w * prof * dfac)[:, 0]
    p["ecl_life"] = base * (M * w * prof * dfac).sum(1)
    s = p.stage.values
    p["pd_applied"] = np.select([s == 1, s == 2], [p.pd12, p.pd_life], default=1.0)
    p["ecl"] = np.select([s == 1, s == 2], [p.ecl12, p.ecl_life], default=base)
    p["stage_lbl"] = "Stage " + p.stage.astype(str)
    return p


def draw_tree(model, feats, classes=True, height=5):
    fig, ax = plt.subplots(figsize=(14, height))
    kw = {"class_names": ["No default", "Default"]} if classes else {}
    plot_tree(model, feature_names=feats, filled=True, rounded=True, impurity=False, fontsize=8,
              precision=3, ax=ax, **kw)
    st.pyplot(fig)
    plt.close(fig)


def read_any(f):
    return pd.read_excel(f) if f.name.lower().endswith(("xlsx", "xls")) else pd.read_csv(f)


def csv_bytes(df):
    return df.to_csv(index=False).encode()


def hint(text):
    st.info("💡 **In simple words:** " + text)


# ───────────────────────────── sidebar: data source ─────────────────────────────
if "dev" not in st.session_state:
    st.session_state.dev, st.session_state.prod = make_demo(12000, 1500, 42)

with st.sidebar:
    st.title("🏦 Simple ECL")
    st.caption("RBI expected-credit-loss framework · effective FY2027-28")
    rep_date = st.date_input("Reporting date", date(2027, 4, 1))
    mode = st.radio("Data source", ["Demo data", "Upload my files"], horizontal=True)
    if mode == "Demo data":
        n_dev = st.slider("History rows (development)", 3000, 30000, 12000, 1000)
        n_prod = st.slider("Current accounts (production)", 300, 5000, 1500, 100)
        seed = st.number_input("Random seed", 1, 9999, 42)
        if st.button("🔄 Generate demo data", width="stretch"):
            st.session_state.dev, st.session_state.prod = make_demo(n_dev, n_prod, int(seed))
            st.rerun()
    else:
        for kind, label, cols in (("dev", "Development data (history, CSV/XLSX)", DEV_COLS),
                                  ("prod", "Production portfolio (CSV/XLSX)", PROD_COLS)):
            f = st.file_uploader(label, type=["csv", "xlsx", "xls"], key=f"up_{kind}")
            if f is not None and st.session_state.get(f"sig_{kind}") != (f.name, f.size):
                st.session_state[kind], st.session_state[f"sig_{kind}"] = read_any(f), (f.name, f.size)
                st.rerun()
            st.download_button(f"⬇️ {kind} template", csv_bytes(make_demo(300, 60, 1)[0 if kind == 'dev' else 1][cols].head(5)),
                               f"{kind}_template.csv", key=f"tpl_{kind}")
        st.caption("Until you upload, the last loaded data stays active. You can also edit data in Step 1.")

for k, cols in (("dev", DEV_COLS), ("prod", PROD_COLS)):
    miss = [c for c in cols if c not in st.session_state[k].columns]
    if miss:
        st.error(f"The {k} data is missing columns: {miss}")
        st.stop()

# ───────────────────────────── prepare data ─────────────────────────────
dq_dev, score_dev = dq_checks(st.session_state.dev, "dev")
dq_prod, score_prod = dq_checks(st.session_state.prod, "prod")
dev, fix_dev = prepare(st.session_state.dev, "dev")
prod, fix_prod = prepare(st.session_state.prod, "prod")
if len(dev) < 500 or len(prod) < 1:
    st.error("Not enough usable rows after cleaning (need ≥500 development rows and ≥1 production account).")
    st.stop()
cats = sorted(dev.category.unique())
assump = [("Reporting date", rep_date)]

T = st.tabs(["📊 Dashboard", "1 Data", "2 SICR rules", "3 Pools", "4 LRA PD", "5 PiT PD", "6 PD validation",
             "7 LGD", "8 EAD", "9 Staging", "10 ECL", "11 Report", "📖 Guide"])

# ───────────────────────────── 1 data completeness ─────────────────────────────
with T[1]:
    st.subheader("Step 1 – Check data completeness")
    hint("Before any maths we ask: is every field filled, sensible and unique? Bad data in = bad ECL out. "
         "The checks run on your raw data; the model then uses an auto-fixed copy (duplicates removed, gaps filled with the median, values clipped to valid ranges).")
    for kind, sub, tbl, score, fx in zip(["dev", "prod"], st.tabs(["Development (history)", "Production (current book)"]),
                                         [dq_dev, dq_prod], [score_dev, score_prod], [fix_dev, fix_prod]):
        with sub:
            c1, c2, c3, c4 = st.columns(4)
            raw = st.session_state[kind]
            c1.metric("Rows", f"{len(raw):,}")
            c2.metric("Completeness score", f"{score:.1f}%", help="Share of rows with no issue at all")
            c3.metric("Rows dropped by auto-fix", fx["dropped"])
            c4.metric("Cells filled by auto-fix", fx["filled"])
            l, r = st.columns([1.2, 1])
            l.dataframe(tbl.style.format({"% of rows": "{:.2f}%"}), hide_index=True, width="stretch")
            r.plotly_chart(px.bar(tbl, x="Rows flagged", y="Check", orientation="h", height=340,
                                  color="Status", color_discrete_map={"✅ Clean": "#2e7d32", "⚠️ Minor": "#f9a825", "❌ Fix": "#c62828"}),
                           width="stretch")
            if st.toggle("✏️ View / edit raw data", key=f"tog_{kind}"):
                ed = st.data_editor(raw, num_rows="dynamic", width="stretch", key=f"ed_{kind}")
                if st.button("💾 Save edits (re-runs everything)", key=f"save_{kind}"):
                    st.session_state[kind] = ed
                    st.rerun()
            st.download_button("⬇️ Download current raw data", csv_bytes(raw), f"{kind}_data.csv", key=f"dl_{kind}")
    assump.append(("Data completeness score dev / prod", f"{score_dev:.1f}% / {score_prod:.1f}%"))

# ───────────────────────────── 2 SICR rules ─────────────────────────────
with T[2]:
    st.subheader("Step 2 – Finalise SICR (stage-allocation) rules for this portfolio")
    hint("Stage 1 = healthy, Stage 2 = risk has risen a lot since the loan was given, Stage 3 = already bad. "
         "Stage 3 is checked first, then Stage 2, otherwise Stage 1. Change the limits below and watch the counts move.")
    d12 = (dev.default_year == 1).groupby(dev.rating).mean().reindex(range(1, 8))
    rating_pd = d12.ffill().bfill().cummax().clip(lower=.0003)
    a, b = st.columns(2)
    with a:
        st.markdown("**Stage 3 (credit-impaired) – any one is true**")
        dpd3 = st.number_input("DPD more than", 0, 365, 90, key="dpd3")
        use_utp = st.checkbox("Unlikeliness-to-pay flag = 1", True)
        st.markdown("**Rating notches downgraded since origination (Stage 2), by portfolio**")
        notch_df = st.data_editor(pd.DataFrame({"category": cats, "notches": [2] * len(cats)}), hide_index=True,
                                  disabled=["category"], key="notch_ed", width="stretch")
    with b:
        st.markdown("**Stage 2 (SICR) – any one is true**")
        dpd2 = st.number_input("DPD more than ", 0, 365, 30, key="dpd2")
        use_watch = st.checkbox("On watchlist", True)
        rel = st.slider("PD today ÷ PD at origination at least", 1.0, 10.0, 2.0, .5)
        ab = st.slider("PD today − PD at origination at least (percentage points)", 0.0, 5.0, 0.5, .1) / 100
        pd_mode = st.radio("PD-change test fires when", ["Both limits crossed", "Either limit crossed"], horizontal=True)
    rules = dict(dpd3=dpd3, use_utp=use_utp, dpd2=dpd2, use_watch=use_watch, rel=rel, abs=ab, mode=pd_mode,
                 notch=dict(zip(notch_df.category, notch_df.notches)))
    prod_s = stage_accounts(prod, rules, rating_pd)
    assump += [("Stage 3: DPD >", dpd3), ("Stage 3: UTP flag used", use_utp), ("Stage 2: DPD >", dpd2),
               ("Stage 2: watchlist used", use_watch), ("Stage 2: PD ratio ≥", rel), ("Stage 2: PD increase ≥", ab),
               ("Stage 2: PD test mode", pd_mode), ("Stage 2: notch limits", str(rules["notch"]))]
    st.markdown("**Rating → PD map** (from development data; used to compare PD today vs PD at origination)")
    c1, c2 = st.columns([1, 1.4])
    c1.dataframe(pd.DataFrame({"Rating": rating_pd.index, "12-month PD": (rating_pd.values * 100).round(2)})
                 .style.format({"12-month PD": "{:.2f}%"}), hide_index=True, width="stretch")
    hits = pd.DataFrame({"Rule": ["S3: DPD", "S3: UTP flag", "S2: DPD", "S2: Watchlist", "S2: Rating downgrade", "S2: PD change"],
                         "Accounts hit": [int(prod_s[c].sum()) for c in ["s3_dpd", "s3_utp", "s2_dpd", "s2_watch", "s2_notch", "s2_pd"]]})
    c2.plotly_chart(px.bar(hits, x="Rule", y="Accounts hit", text="Accounts hit", title="How many accounts each rule catches (overlaps possible)"),
                    width="stretch")
    sc = prod_s.stage.value_counts().reindex([1, 2, 3], fill_value=0)
    st.success(f"Result on current book → Stage 1: {sc[1]:,} · Stage 2: {sc[2]:,} · Stage 3: {sc[3]:,} accounts")

# ───────────────────────────── 3 pools ─────────────────────────────
with T[3]:
    st.subheader("Step 3 – Homogeneous pools (decision tree) and staging view")
    hint("Pools group accounts that behave alike. A small decision tree per portfolio asks simple yes/no questions "
         "(e.g. 'rating ≤ 3?') and every answer-path ends in a pool. P1 = safest pool, higher numbers = riskier. Read the tree top to bottom.")
    years = sorted(dev.snapshot_year.unique())
    max_n = max(1, min(4, len(years) - 1))
    a, b, c = st.columns(3)
    oot_n = a.number_input("Latest years kept for out-of-time test (Step 6)", 1, max_n, min(2, max_n))
    max_leaves = b.number_input("Max pools per portfolio", 2, 8, 4)
    min_leaf = c.number_input("Min accounts per pool", 50, 2000, 250, 50)
    cut = years[-int(oot_n)]
    dev_tr, dev_te = dev[dev.snapshot_year < cut].copy(), dev[dev.snapshot_year >= cut].copy()
    st.caption(f"Development window: {years[0]}–{cut - 1} ({len(dev_tr):,} rows) · Out-of-time test: {cut}–{years[-1]} ({len(dev_te):,} rows)")
    models = fit_pools(dev_tr, max_leaves, min_leaf)
    pool_tr, pool_te = assign_pool(dev_tr, models), assign_pool(dev_te, models)
    prod_s["pool"] = assign_pool(prod_s, models)
    if prod_s.pool.isna().any():
        st.warning(f"{int(prod_s.pool.isna().sum())} production accounts are in a portfolio with no development data and are excluded.")
        prod_s = prod_s[prod_s.pool.notna()].copy()
    rows = [{"pool": f"{c}-P{k}", "category": c, "rule": rules_[leaf]}
            for c, (_, rank, rules_) in models.items() for leaf, k in rank.items()]
    pool_info = pd.DataFrame(rows).set_index("pool").sort_index()
    ps = dev_tr.assign(pool=pool_tr).groupby("pool").agg(accounts=("acct_id", "size"), defaults=("default_year", lambda s: int((s == 1).sum())))
    pool_info = pool_info.join(ps)
    pool_info["12m default rate"] = pool_info.defaults / pool_info.accounts
    st.dataframe(pool_info.style.format({"12m default rate": "{:.2%}"}), width="stretch")
    sel = st.selectbox("See the tree for portfolio", list(models))
    draw_tree(models[sel][0], FEATS)
    with st.expander("Same tree as plain text"):
        st.code(export_text(models[sel][0], feature_names=FEATS))
    ct = pd.crosstab(prod_s.pool, prod_s.stage).reindex(columns=[1, 2, 3], fill_value=0)
    ct.columns = ["Stage 1", "Stage 2", "Stage 3"]
    st.plotly_chart(px.imshow(ct, text_auto=True, aspect="auto", color_continuous_scale="Blues",
                              title="Current accounts: pool × stage (pool = how alike, stage = how much risk has risen)"),
                    width="stretch")
    assump += [("Out-of-time years", int(oot_n)), ("Max pools / portfolio", int(max_leaves)), ("Min accounts / pool", int(min_leaf))]

# ───────────────────────────── 4 LRA PD ─────────────────────────────
with T[4]:
    st.subheader("Step 4 – Long-run-average (LRA) PD and lifetime PD per pool")
    hint("LRA PD = the average yearly default rate over good and bad years. Lifetime PD = chance of defaulting any time before the loan ends. "
         "We watch how many accounts default in year 1, 2, 3… among those still alive (the 'hazard') and stack that into a curve.")
    floor = st.number_input("PD floor (%)", 0.0, 1.0, 0.03, 0.01) / 100
    lra, yearly, hz = build_curves(dev_tr, pool_tr, floor)
    assump.append(("PD floor", floor))
    sel = st.selectbox("Portfolio to chart", cats, key="c4")
    pl = [p for p in hz if p.startswith(sel + "-")]
    l, r = st.columns(2)
    y = yearly.loc[pl].T.reset_index().melt("snapshot_year", var_name="pool", value_name="rate")
    l.plotly_chart(px.line(y, x="snapshot_year", y="rate", color="pool", markers=True, title="Default rate by year (LRA = their average)")
                   .update_yaxes(tickformat=".1%"), width="stretch")
    cur = pd.DataFrame([{"pool": p, "year": t, "cum PD": 1 - np.prod(1 - hz[p][:t])} for p in pl for t in range(1, 11)])
    r.plotly_chart(px.line(cur, x="year", y="cum PD", color="pool", title="Lifetime (cumulative) LRA PD curve").update_yaxes(tickformat=".1%"),
                   width="stretch")
    tab4 = pd.DataFrame({"12m LRA PD": lra, "3-yr cum. PD": {p: 1 - np.prod(1 - hz[p][:3]) for p in hz},
                         "5-yr cum. PD": {p: 1 - np.prod(1 - hz[p][:5]) for p in hz}})
    st.dataframe(tab4.style.format("{:.2%}"), width="stretch")

# ───────────────────────────── 5 PiT PD ─────────────────────────────
with T[5]:
    st.subheader("Step 5 – Convert LRA PD into Point-in-Time (PiT) PD")
    hint("LRA PD is the 'average weather'. PiT PD is 'today's forecast'. We multiply the average by a scenario factor "
         "(economy better / as expected / worse), weight the scenarios by probability, and let the effect fade back to normal over a few years.")
    last = (dev.assign(d=(dev.default_year == 1)).groupby("snapshot_year").d.mean())
    st.caption(f"Reference: latest observed default rate {last.iloc[-1]:.2%} vs long-run average {last.mean():.2%} → ratio {last.iloc[-1] / last.mean():.2f}")
    scen = st.data_editor(pd.DataFrame({"scenario": ["Upside", "Base", "Downside"], "probability": [.2, .5, .3],
                                        "PD multiplier": [.85, 1.05, 1.5]}), hide_index=True, disabled=["scenario"],
                          key="scen", width="stretch")
    R = st.slider("Years until PD fades back to long-run level", 1, 5, 3)
    wsum = scen.probability.sum()
    if abs(wsum - 1) > 1e-6:
        st.warning(f"Probabilities add to {wsum:.2f}; normalised to 100%.")
    wts = (scen.probability / wsum).values
    S_eff = float((wts * scen["PD multiplier"].values).sum())
    st.metric("Probability-weighted PD multiplier", f"{S_eff:.3f}")
    marg_lra = {p: marg_from_h(h) for p, h in hz.items()}
    marg_w = {p: sum(w * marg_from_h(pit_h(h, S, R)) for w, S in zip(wts, scen["PD multiplier"].values)) for p, h in hz.items()}
    assump += [("Scenarios", scen.to_dict("records")), ("PD fade years", R)]
    sel = st.selectbox("Pool to chart", sorted(hz), key="c5")
    yrs = np.arange(1, 11)
    fig = go.Figure()
    fig.add_scatter(x=yrs, y=np.cumsum(marg_lra[sel])[:10], name="LRA (through-the-cycle)", mode="lines+markers")
    fig.add_scatter(x=yrs, y=np.cumsum(marg_w[sel])[:10], name="PiT (weighted scenarios)", mode="lines+markers")
    fig.update_layout(title=f"{sel}: cumulative PD", yaxis_tickformat=".1%", xaxis_title="Year")
    st.plotly_chart(fig, width="stretch")
    pit_tab = pd.DataFrame({"LRA 12m": {p: marg_lra[p][0] for p in hz}, "PiT 12m": {p: marg_w[p][0] for p in hz},
                            "LRA 5-yr": {p: marg_lra[p][:5].sum() for p in hz}, "PiT 5-yr": {p: marg_w[p][:5].sum() for p in hz}})
    st.dataframe(pit_tab.style.format("{:.2%}"), width="stretch")

# ───────────────────────────── 6 validation ─────────────────────────────
auc_oot, n_review, n_tested, min_auc = np.nan, 0, 0, 0.65
with T[6]:
    st.subheader("Step 6 – Validate the PD model on unseen (out-of-time) years")
    hint("We hide the latest years while building the model, then test it on them. Two questions: "
         "(1) Does it rank risky accounts above safe ones? (AUC/Gini)  (2) Does predicted default rate match what actually happened?")
    min_auc = st.number_input("Minimum acceptable AUC", .5, .95, .65, .01)
    te = dev_te.assign(pool=pool_te)
    te = te[te.pool.notna()]
    te["y"] = (te.default_year == 1).astype(int)
    te["pred"] = te.pool.map(lra)
    trn = dev_tr.assign(pool=pool_tr, y=(dev_tr.default_year == 1).astype(int))
    trn = trn[trn.pool.notna()]
    trn["pred"] = trn.pool.map(lra)
    if te.y.nunique() < 2:
        st.warning("Out-of-time data has no defaults (or only defaults) – cannot compute AUC.")
    else:
        auc_oot, auc_tr = roc_auc_score(te.y, te.pred), roc_auc_score(trn.y, trn.pred)
        fpr, tpr, _ = roc_curve(te.y, te.pred)
        c = st.columns(4)
        c[0].metric("AUC – out-of-time", f"{auc_oot:.3f}")
        c[1].metric("Gini – out-of-time", f"{2 * auc_oot - 1:.3f}")
        c[2].metric("KS", f"{(tpr - fpr).max():.3f}")
        c[3].metric("AUC – development", f"{auc_tr:.3f}", help="A big gap vs out-of-time AUC means over-fitting")
        st.success("Ranking power acceptable ✅") if auc_oot >= min_auc else st.error("Ranking power below threshold ❌")
        l, r = st.columns(2)
        f = go.Figure()
        f.add_scatter(x=fpr, y=tpr, name="Model")
        f.add_scatter(x=[0, 1], y=[0, 1], name="Random", line=dict(dash="dash"))
        l.plotly_chart(f.update_layout(title="ROC curve (out-of-time)", xaxis_title="False positive rate", yaxis_title="True positive rate"),
                       width="stretch")
        cal = te.groupby("pool").agg(accounts=("y", "size"), defaults=("y", "sum"), predicted=("pred", "mean"))
        cal["observed"] = cal.defaults / cal.accounts
        cal["p-value"] = [binomtest(int(k), int(n), float(min(max(p, 1e-6), 1))).pvalue for k, n, p in zip(cal.defaults, cal.accounts, cal.predicted)]
        cal["Status"] = np.where(cal["p-value"] >= .05, "✅ OK", "⚠️ Review")
        n_review, n_tested = int((cal.Status != "✅ OK").sum()), len(cal)
        cm = cal.reset_index().melt("pool", ["predicted", "observed"], var_name="type", value_name="rate")
        r.plotly_chart(px.bar(cm, x="pool", y="rate", color="type", barmode="group", title="Predicted vs actual default rate by pool")
                       .update_yaxes(tickformat=".1%"), width="stretch")
        st.dataframe(cal.style.format({"predicted": "{:.2%}", "observed": "{:.2%}", "p-value": "{:.3f}"}), width="stretch")
        st.caption("p-value test: if the actual defaults are very unlikely (p<0.05) under the predicted PD, the pool is flagged for review.")
        mono = []
        for c_ in cats:
            o = te[te.pool.str.startswith(c_ + "-")].groupby("pool").y.mean().sort_index()
            mono.append({"Portfolio": c_, "Safer pools really have lower defaults?": "✅ Yes" if o.is_monotonic_increasing else "⚠️ No"})
        sh = pd.DataFrame({"train": pool_tr.value_counts(normalize=True), "test": pool_te.value_counts(normalize=True)}).fillna(.0001)
        psi = float(((sh.test - sh.train) * np.log(sh.test / sh.train)).sum())
        a, b = st.columns(2)
        a.dataframe(pd.DataFrame(mono), hide_index=True, width="stretch")
        b.metric("Population stability (PSI)", f"{psi:.3f}", help="<0.10 stable, 0.10–0.25 watch, >0.25 shifted")

# ───────────────────────────── 7 LGD ─────────────────────────────
with T[7]:
    st.subheader("Step 7 – Loss Given Default (LGD) per pool")
    hint("LGD = of every ₹100 that defaults, how much is finally lost after recoveries. We take the average loss (weighted by loan size) "
         "of past defaulted accounts in each pool. Pools with too few defaults borrow their portfolio's average.")
    a, b = st.columns(2)
    min_def = a.number_input("Min defaults for pool's own LGD", 1, 200, 15)
    lgd_floor = b.number_input("LGD floor (%)", 0, 50, 10) / 100
    dd = dev.assign(pool=assign_pool(dev, models))
    dd = dd[(dd.default_year > 0) & dd.pool.notna()].copy()
    dd["lw"] = dd.lgd_obs * dd.outstanding
    g = dd.groupby("pool").agg(n_def=("acct_id", "size"), lw=("lw", "sum"), w=("outstanding", "sum"))
    g["lgd_pool"] = g.lw / g.w
    gc = dd.groupby("category").agg(lw=("lw", "sum"), w=("outstanding", "sum"))
    cat_lgd = gc.lw / gc.w
    lg = pool_info[["category"]].join(g[["n_def", "lgd_pool"]])
    lg["n_def"] = lg.n_def.fillna(0).astype(int)
    lg["lgd_category"] = lg.category.map(cat_lgd).fillna(dd.lw.sum() / dd.outstanding.sum())
    lg["LGD used"] = np.where(lg.n_def >= min_def, lg.lgd_pool, lg.lgd_category)
    lg["LGD used"] = lg["LGD used"].astype(float).clip(lgd_floor, 1)
    lgd_map = lg["LGD used"]
    assump += [("Min defaults for pool LGD", int(min_def)), ("LGD floor", lgd_floor)]
    l, r = st.columns([1.3, 1])
    l.dataframe(lg.style.format({"lgd_pool": "{:.1%}", "lgd_category": "{:.1%}", "LGD used": "{:.1%}"}, na_rep="–"), width="stretch")
    r.plotly_chart(px.bar(lg.reset_index(), x="pool", y="LGD used", color="category", title="LGD used by pool").update_yaxes(tickformat=".0%"),
                   width="stretch")
    if len(dd) >= 60:
        st.markdown("**What drives loss? (see-through tree on defaulted accounts)**")
        reg = DecisionTreeRegressor(max_depth=3, min_samples_leaf=max(10, len(dd) // 30), random_state=0)
        reg.fit(dd[["secured_pct", "rating", "utilisation"]], dd.lgd_obs)
        draw_tree(reg, ["secured_pct", "rating", "utilisation"], classes=False, height=4)
        st.caption("Each box shows the average loss (value) for accounts reaching it. Usually more collateral → lower loss.")

# ───────────────────────────── 8 EAD ─────────────────────────────
with T[8]:
    st.subheader("Step 8 – Exposure at Default (EAD)")
    hint("EAD = what we expect to be owed if the customer defaults = money already lent + the part of the unused limit they are likely to draw "
         "(CCF = credit conversion factor). Amortising loans shrink every year, so their exposure falls over time.")
    ccf = st.data_editor(pd.DataFrame({"category": cats, "ccf": [1.0 if c in ("Home", "Personal") else .5 for c in cats],
                                       "amortising": [c != "Corporate" for c in cats]}),
                         hide_index=True, disabled=["category"], key="ccf", width="stretch",
                         column_config={"ccf": st.column_config.NumberColumn("CCF on undrawn (0–1)", min_value=0.0, max_value=1.0)})
    assump.append(("CCF / amortising", ccf.to_dict("records")))
    e = prod_s.merge(ccf, on="category", how="left")
    e["drawn"], e["from_undrawn"] = e.outstanding, e.ccf * e.undrawn_limit
    es = e.groupby("category")[["drawn", "from_undrawn"]].sum().reset_index().melt("category", var_name="part", value_name="₹ lakh")
    st.plotly_chart(px.bar(es, x="category", y="₹ lakh", color="part", title="EAD = drawn + CCF × undrawn, by portfolio"), width="stretch")
    st.latex(r"EAD = Outstanding + CCF \times Undrawn\ limit")

# ───────────────────────────── 9 staging + apply ─────────────────────────────
book = compute_book(prod_s, marg_w, lgd_map, ccf)
with T[9]:
    st.subheader("Step 9 – Stage the production accounts and attach PD, LGD and EAD")
    hint("Each current account gets: a stage (from Step 2), a pool (Step 3), a PD (Steps 4–5), an LGD (Step 7) and an EAD (Step 8). "
         "Stage 1 uses the next-12-months PD; Stage 2 uses the PD over the whole remaining life; Stage 3 is treated as already defaulted (PD = 100%).")
    ss = book.groupby("stage_lbl").agg(accounts=("acct_id", "size"), ead=("ead", "sum")).reset_index()
    ss["share of EAD"] = ss.ead / ss.ead.sum()
    c1, c2 = st.columns(2)
    c1.dataframe(ss.style.format({"ead": "{:,.0f}", "share of EAD": "{:.1%}"}), hide_index=True, width="stretch")
    c2.plotly_chart(px.pie(ss, names="stage_lbl", values="ead", hole=.5, color="stage_lbl", color_discrete_map=STAGE_COL), width="stretch")
    cols = ["acct_id", "category", "pool", "stage", "dpd", "rating", "orig_rating", "pd12", "pd_life", "pd_applied", "lgd", "ead"]
    st.dataframe(book[cols].style.format({"pd12": "{:.2%}", "pd_life": "{:.2%}", "pd_applied": "{:.2%}", "lgd": "{:.1%}", "ead": "{:,.1f}"}),
                 hide_index=True, width="stretch")

# ───────────────────────────── 10 ECL ─────────────────────────────
with T[10]:
    st.subheader("Step 10 – Final ECL")
    hint("ECL is the average loss we expect. Stage 1: PD(12m) × LGD × EAD. Stage 2: same but added up for every year of the remaining life. "
         "Stage 3: LGD × EAD. Future losses are discounted back to today at the loan's own interest rate (EIR).")
    st.latex(r"ECL_{S1}=EAD\times LGD\times PD_{12m}\times DF \qquad ECL_{S2}=\sum_{t=1}^{T}EAD_t\times LGD\times PD_t\times DF_t \qquad ECL_{S3}=EAD\times LGD")
    sm = book.groupby("stage_lbl").agg(accounts=("acct_id", "size"), ead=("ead", "sum"), ecl=("ecl", "sum")).reset_index()
    sm["coverage"] = sm.ecl / sm.ead
    st.dataframe(sm.style.format({"ead": "{:,.0f}", "ecl": "{:,.1f}", "coverage": "{:.2%}"}), hide_index=True, width="stretch")
    pool_sum = book.groupby("pool").agg(accounts=("acct_id", "size"), ead=("ead", "sum"), ecl=("ecl", "sum"), pd12=("pd12", "mean"),
                                        lgd=("lgd", "mean")).reset_index()
    pool_sum["coverage"] = pool_sum.ecl / pool_sum.ead
    pool_sum["category"] = pool_sum.pool.str.rsplit("-", n=1).str[0]
    st.markdown("**ECL by pool**")
    st.dataframe(pool_sum.style.format({"ead": "{:,.0f}", "ecl": "{:,.1f}", "pd12": "{:.2%}", "lgd": "{:.1%}", "coverage": "{:.2%}"}),
                 hide_index=True, width="stretch")
    st.markdown("### 🔍 Explain one account – follow the number from start to end")
    pick = book.sort_values("ecl", ascending=False).acct_id.head(300).tolist()
    aid = st.selectbox("Account (top 300 by ECL; type to search)", pick)
    r = book[book.acct_id == aid].iloc[0]
    why = [txt for col, txt in [("s3_dpd", "DPD above Stage 3 limit"), ("s3_utp", "Unlikeliness-to-pay flag"), ("s2_dpd", "DPD above Stage 2 limit"),
                                ("s2_watch", "On watchlist"), ("s2_notch", f"Rating fell {int(r.notches)} notch(es)"),
                                ("s2_pd", f"PD rose {r.pd_orig:.2%} → {r.pd_curr:.2%}")] if r[col]]
    st.markdown(f"**1. Stage {r.stage}** – " + ("; ".join(why) if why else "no trigger fired → healthy (Stage 1)"))
    st.markdown(f"**2. Pool `{r.pool}`** – tree path: _{pool_info.loc[r.pool, 'rule']}_")
    Tt = float(np.clip(r.remaining_term_yrs, .25, H))
    t_ = np.arange(1, int(np.ceil(Tt)) + 1)
    w_ = np.clip(Tt - (t_ - 1), 0, 1)
    prof_ = np.clip(1 - (t_ - 1) / Tt, 0, 1) if r.amortising else np.ones(len(t_))
    df_ = (1 + r.eir) ** (-t_)
    m_ = marg_w[r.pool][:len(t_)]
    ead_t = r.ead * prof_
    yr = pd.DataFrame({"Year": t_, "Share of year in life": w_, "Marginal PD": m_, "EAD that year": ead_t, "Discount factor": df_,
                       "ECL that year": ead_t * r.lgd * m_ * w_ * df_})
    st.markdown(f"**3. PD** – 12-month PiT PD = {r.pd12:.2%}; lifetime PD over remaining {Tt:.1f} years = {r.pd_life:.2%}")
    st.markdown(f"**4. LGD** – pool LGD = {r.lgd:.1%}")
    st.markdown(f"**5. EAD** – {r.outstanding:,.1f} + {r.ccf:.0%} × {r.undrawn_limit:,.1f} = **{r.ead:,.1f}**")
    if r.stage == 1:
        st.markdown(f"**6. ECL** = {r.ead:,.1f} × {r.lgd:.1%} × {r.pd12:.2%} × {df_[0]:.3f} = **{r.ecl:,.2f}**")
    elif r.stage == 2:
        st.markdown(f"**6. ECL** = sum of the yearly amounts below = **{r.ecl:,.2f}**")
    else:
        st.markdown(f"**6. ECL** = {r.ead:,.1f} × {r.lgd:.1%} = **{r.ecl:,.2f}**")
    l, rr = st.columns([1.3, 1])
    l.dataframe(yr.style.format({"Share of year in life": "{:.2f}", "Marginal PD": "{:.3%}", "EAD that year": "{:,.1f}",
                                 "Discount factor": "{:.3f}", "ECL that year": "{:,.3f}"}), hide_index=True, width="stretch")
    rr.plotly_chart(px.bar(yr, x="Year", y="Marginal PD", title="Chance of defaulting in each year").update_yaxes(tickformat=".1%"), width="stretch")

# ───────────────────────────── 11 reconcile & report ─────────────────────────────
with T[11]:
    st.subheader("Step 11 – Validation, reconciliation and reporting")
    hint("A last set of tick-box checks: does everything add up, are numbers sensible, did earlier steps pass? "
         "Then compare with the previous period and download the report pack.")
    gl = st.number_input("Balance-sheet (GL) outstanding for this portfolio (₹ lakh)", value=float(round(prod.outstanding.sum(), 2)))
    min_dq = st.number_input("Minimum data completeness score (%)", 50.0, 100.0, 95.0)
    chk = []

    def add(name, ok, detail):
        chk.append({"Check": name, "Result": "✅ Pass" if ok else "❌ Fail", "Detail": detail})

    tot = book.ecl.sum()
    add("Account count: input = output", len(book) == len(prod), f"{len(prod):,} in / {len(book):,} out")
    add("Outstanding ties to GL (±0.01%)", abs(book.outstanding.sum() - gl) <= 1e-4 * max(gl, 1), f"{book.outstanding.sum():,.1f} vs {gl:,.1f}")
    add("ECL adds up by stage = pool = category = total",
        np.isclose(book.groupby("stage").ecl.sum().sum(), tot) and np.isclose(pool_sum.ecl.sum(), tot) and np.isclose(book.groupby("category").ecl.sum().sum(), tot),
        f"Total {tot:,.1f}")
    add("ECL never exceeds EAD", int((book.ecl > book.ead + 1e-9).sum()) == 0, f"{int((book.ecl > book.ead + 1e-9).sum())} breaches")
    cov = book.groupby("stage").ecl.sum() / book.groupby("stage").ead.sum()
    add("Coverage rises Stage 1 < 2 < 3", cov.is_monotonic_increasing, ", ".join(f"S{i}: {v:.2%}" for i, v in cov.items()))
    add("PD and LGD within 0–100%, no blanks", book[["pd_applied", "lgd", "ecl"]].notna().all().all() and book.pd_applied.between(0, 1).all() and book.lgd.between(0, 1).all(), "")
    add("Every Stage 3 account has a Stage 3 trigger", bool(((book.stage != 3) | book.s3_dpd | book.s3_utp).all()), "")
    add("Data completeness above minimum", min(score_dev, score_prod) >= min_dq, f"dev {score_dev:.1f}% / prod {score_prod:.1f}%")
    add("PD ranking power (out-of-time AUC)", (not np.isnan(auc_oot)) and auc_oot >= min_auc, "n/a" if np.isnan(auc_oot) else f"{auc_oot:.3f} vs min {min_auc:.2f}")
    add("PD calibration: <30% of pools flagged", n_tested > 0 and n_review / n_tested < .3, f"{n_review} of {n_tested} pools flagged")
    ck = pd.DataFrame(chk)
    st.metric("Checks passed", f"{(ck.Result == '✅ Pass').sum()} / {len(ck)}")
    st.dataframe(ck, hide_index=True, width="stretch")

    st.markdown("**Movement versus previous period**")
    cur = book.groupby("stage").ecl.sum().reindex([1, 2, 3], fill_value=0)
    prev = st.data_editor(pd.DataFrame({"stage": ["Stage 1", "Stage 2", "Stage 3"], "previous ECL (₹ lakh)": (cur.values * [.93, .88, .95]).round(1)}),
                          hide_index=True, disabled=["stage"], key=f"prev_{int(tot)}", width="stretch")
    delta = cur.values - prev["previous ECL (₹ lakh)"].values
    wf = go.Figure(go.Waterfall(x=["Opening ECL", "Stage 1 change", "Stage 2 change", "Stage 3 change", "Closing ECL"],
                                measure=["absolute", "relative", "relative", "relative", "total"],
                                y=[prev["previous ECL (₹ lakh)"].sum(), *delta, 0]))
    st.plotly_chart(wf.update_layout(title="ECL movement (₹ lakh)"), width="stretch")

    s3 = book[book.stage == 3]
    st.markdown("**Management summary**")
    st.markdown(f"- Reporting date **{rep_date:%d %b %Y}**: total ECL **₹{tot:,.0f} lakh** on EAD ₹{book.ead.sum():,.0f} lakh (coverage {tot / book.ead.sum():.2%}).\n"
                f"- Stage mix by EAD: S1 {book[book.stage == 1].ead.sum() / book.ead.sum():.1%}, S2 {book[book.stage == 2].ead.sum() / book.ead.sum():.1%}, S3 {s3.ead.sum() / book.ead.sum():.1%}.\n"
                f"- Largest portfolio by ECL: **{book.groupby('category').ecl.sum().idxmax()}**; largest pool: **{pool_sum.sort_values('ecl').pool.iloc[-1]}**.\n"
                f"- Probability-weighted PD multiplier {S_eff:.2f}; checks passed {(ck.Result == '✅ Pass').sum()}/{len(ck)}.")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        sm.to_excel(xw, sheet_name="Summary by stage", index=False)
        pool_sum.to_excel(xw, sheet_name="Pools", index=False)
        book[["acct_id", "category", "pool", "stage", "pd12", "pd_life", "pd_applied", "lgd", "ead", "ecl"]].to_excel(xw, sheet_name="Accounts", index=False)
        ck.to_excel(xw, sheet_name="Checks", index=False)
        pd.DataFrame(assump, columns=["Parameter", "Value"]).astype(str).to_excel(xw, sheet_name="Assumptions", index=False)
    a, b = st.columns(2)
    a.download_button("⬇️ Excel report pack", buf.getvalue(), "ecl_report.xlsx", width="stretch")
    b.download_button("⬇️ Account-level ECL (CSV)", csv_bytes(book[["acct_id", "category", "pool", "stage", "pd_applied", "lgd", "ead", "ecl"]]),
                      "ecl_accounts.csv", width="stretch")

# ───────────────────────────── dashboard (filled last, shown first) ─────────────────────────────
with T[0]:
    st.subheader("ECL dashboard")
    tot_ead = book.ead.sum()
    k = st.columns(6)
    k[0].metric("Total ECL (₹ lakh)", f"{tot:,.0f}")
    k[1].metric("Total EAD (₹ lakh)", f"{tot_ead:,.0f}")
    k[2].metric("Coverage", f"{tot / tot_ead:.2%}")
    k[3].metric("Stage 2 share of EAD", f"{book[book.stage == 2].ead.sum() / tot_ead:.1%}")
    k[4].metric("Stage 3 share of EAD", f"{book[book.stage == 3].ead.sum() / tot_ead:.1%}")
    k[5].metric("Checks passed", f"{(ck.Result == '✅ Pass').sum()}/{len(ck)}")
    q = st.columns(4)
    q[0].metric("Data quality (dev / prod)", f"{score_dev:.0f}% / {score_prod:.0f}%")
    q[1].metric("PD model AUC (out-of-time)", "n/a" if np.isnan(auc_oot) else f"{auc_oot:.3f}")
    q[2].metric("Pools", len(pool_sum))
    q[3].metric("PD multiplier (PiT/LRA)", f"{S_eff:.2f}")
    l, r = st.columns(2)
    l.plotly_chart(px.bar(sm, x="stage_lbl", y="ecl", color="stage_lbl", color_discrete_map=STAGE_COL, text=sm.coverage.map("{:.2%}".format),
                          title="ECL by stage (label = coverage)").update_layout(showlegend=False), width="stretch")
    r.plotly_chart(px.pie(book.groupby("stage_lbl").ead.sum().reset_index(), names="stage_lbl", values="ead", hole=.55, color="stage_lbl",
                          color_discrete_map=STAGE_COL, title="EAD by stage"), width="stretch")
    l, r = st.columns(2)
    l.plotly_chart(px.bar(book.groupby(["category", "stage_lbl"]).ecl.sum().reset_index(), x="category", y="ecl", color="stage_lbl",
                          color_discrete_map=STAGE_COL, title="ECL by portfolio and stage"), width="stretch")
    hm = book.groupby(["rating", "category"]).agg(e=("ecl", "sum"), d=("ead", "sum")).reset_index()
    hm["coverage"] = hm.e / hm.d
    r.plotly_chart(px.imshow(hm.pivot(index="rating", columns="category", values="coverage"), text_auto=".1%", aspect="auto",
                             color_continuous_scale="Reds", title="Coverage by rating × portfolio"), width="stretch")
    l, r = st.columns(2)
    l.plotly_chart(px.bar(pool_sum.sort_values("ecl").tail(10), x="ecl", y="pool", orientation="h", color="category", title="Top 10 pools by ECL"),
                   width="stretch")
    r.plotly_chart(px.scatter(pool_sum, x="pd12", y="lgd", size="ecl", color="category", hover_name="pool", title="Pool risk map: PD vs LGD (bubble = ECL)")
                   .update_xaxes(tickformat=".1%").update_yaxes(tickformat=".0%"), width="stretch")
    st.markdown("**Top 10 accounts by ECL**")
    st.dataframe(book.sort_values("ecl", ascending=False).head(10)[["acct_id", "category", "pool", "stage", "pd_applied", "lgd", "ead", "ecl"]]
                 .style.format({"pd_applied": "{:.2%}", "lgd": "{:.1%}", "ead": "{:,.1f}", "ecl": "{:,.2f}"}), hide_index=True, width="stretch")

# ───────────────────────────── guide ─────────────────────────────
with T[12]:
    st.subheader("How to read this app")
    st.markdown("""
**Flow:** Data → Rules → Pools → PD (long-run) → PD (today) → Validate → LGD → EAD → Stage the book → ECL → Report.

**Models used:** only decision trees (pool building, LGD drivers) and plain averages. No black boxes.

**Input files (CSV/XLSX; amounts in ₹ lakh)**
- *Development:* acct_id, category, snapshot_year, rating (1 best – 7 worst), dpd, utilisation (0–1), secured_pct (0–1), remaining_term_yrs,
  outstanding, **default_year** (0 = no default within 5 years, 1–5 = year of first default), lgd_obs (final loss rate, only for defaulted accounts).
  Use performing accounts at each snapshot, with a completed 5-year outcome window.
- *Production:* acct_id, category, outstanding, undrawn_limit, dpd, rating, orig_rating, utp_flag (0/1), watchlist (0/1), secured_pct, remaining_term_yrs, eir (e.g. 0.10).

**Suggested corrections to the draft steps**
1. Add *Step 0*: define "default" once (e.g. 90 DPD or unlikely-to-pay) and use it for Stage 3, the PD target and the LGD sample.
2. Step 2 needs a rating → PD map to test "PD today vs PD at origination", so a quick one is built from development data and can be refined after Step 4.
3. Step 5: use probability-weighted scenarios and let the effect fade to long-run level (done here).
4. Step 6 should use years the model has never seen (out-of-time) – done here. LGD/EAD back-testing is a natural next addition.
5. Step 10: discount at the loan's EIR (done); Step 11: tie-out to the general ledger and to the previous period (done).
6. Not included to stay simple: cure/upgrade probation rules, collective-vs-individual assessment, management overlays – add once the base works.

Always confirm thresholds, definitions and treatment against the final RBI Directions and your Board-approved policy.
""")
