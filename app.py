"""
RBI ECL Model Lab  -  a deliberately simple, transparent ECL engine + dashboard
Built around the RBI (Commercial Banks - Asset Classification, Provisioning and
Income Recognition) Directions, 2026.

Pipeline:  data -> category map -> dual-gate staging + upgrade rules -> PD / LGD / EAD -> scenario ECL
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
        "covenant_breach", "collateral_decline", "dpd_rebuttal", "credit_impaired", "years_in_stage3", "prior_stage", "restructured", "months_regular", "secured_pct", "collateral_type",
        "remaining_term_yrs", "eir_pct"]
# The 15 columns the engine really needs. Everything else is optional and takes a safe default when absent.
CORE_COLS = ["loan_id", "borrower_id", "category", "outstanding", "undrawn_limit", "dpd", "rating_orig", "rating_curr",
             "credit_impaired", "watchlist", "years_in_stage3", "secured_pct", "collateral_type", "remaining_term_yrs", "eir_pct"]
OPT_COLS = [c for c in COLS if c not in CORE_COLS]
BOOL_COLS = ["is_revolving", "amortising", "watchlist", "covenant_breach", "collateral_decline", "dpd_rebuttal", "credit_impaired", "restructured"]
NUM_DEFAULT = {"outstanding": 0.0, "undrawn_limit": 0.0, "dpd": 0.0, "days_over_limit": 0.0,
               "rating_orig": 5.0, "rating_curr": 5.0, "years_in_stage3": 0.0, "secured_pct": 0.0,
               "remaining_term_yrs": 3.0, "eir_pct": 10.0, "prior_stage": 1.0, "months_regular": 24.0}

DEFAULT_PD = [0.05, 0.10, 0.25, 0.50, 1.00, 2.00, 4.00, 8.00, 15.00, 30.00]   # 12m PD %, grade 1..10
YRS = list(range(1, 11))                                                        # lifetime curve horizon in the table


def derived_curve(pd12_pct) -> pd.DataFrame:
    """Lifetime PD curve implied by a constant yearly PD: cumulative PD(t) = 1 - (1 - PD12)^t, in %."""
    p = np.asarray(pd12_pct, float) / 100
    return pd.DataFrame({"grade": range(1, 11), **{f"y{t}": (1 - (1 - p) ** t) * 100 for t in YRS}})


def hazards_from_curve(curve_pct: np.ndarray, horizon: int = 40) -> np.ndarray:
    """Cumulative PD % (grades x 10 yrs) -> conditional yearly PD (grades x horizon). Years past 10 repeat year 10."""
    cum = np.clip(np.maximum.accumulate(np.asarray(curve_pct, float) / 100, axis=1), 0, 1)
    prev = np.concatenate([np.zeros((cum.shape[0], 1)), cum[:, :-1]], axis=1)
    h = np.where(prev < 1, (cum - prev) / np.maximum(1 - prev, 1e-12), 1.0)
    h = np.clip(h, 0, 1)
    return np.concatenate([h, np.repeat(h[:, -1:], horizon - h.shape[1], axis=1)], axis=1)
STAGE_COLORS = alt.Scale(domain=["Stage 1", "Stage 2", "Stage 3"], range=["#2e9e6b", "#f0a500", "#d64545"])


# ----------------------------------------------------------------------------
# 2. DATA: generator + sanitiser
# ----------------------------------------------------------------------------
COV_CATS = {"Corporate loan", "Loan to small & micro enterprises", "Loan to medium enterprises",
            "Loan to banks / NBFCs / regulated FIs", "Other claims secured by commercial RE",
            "Restructured standard advances", "Other / residual"}          # business loans that carry covenants


def generate_loans(n: int, seed: int, stress: float, with_optional: bool = False) -> pd.DataFrame:
    """Synthetic loan book whose columns follow each other (see RULES below):
       borrower state -> grades, watchlist, UTP flag, years in Stage 3 -> loan DPD -> limits, flags, history."""
    rng = np.random.default_rng(seed)
    names = CAT_NAMES
    w = np.array([CATS[k]["w"] for k in names], float)
    cat_idx = rng.choice(len(names), size=n, p=w / w.sum())
    cat = np.array([names[i] for i in cat_idx])
    pc = lambda key: np.array([CATS[c][key] for c in cat])

    # ---- borrowers (loans in a category can share a borrower) ----
    borrower = np.empty(n, dtype=object)
    for ci in range(len(names)):
        m = cat_idx == ci
        k = int(m.sum())
        if k:
            borrower[m] = [f"B{ci:02d}-{x}" for x in rng.integers(1, max(2, int(k * 1.6)) + 1, size=k)]
    ub, first, inv = np.unique(borrower.astype(str), return_index=True, return_inverse=True)
    nb = len(ub)
    b_cat = cat[first]
    sov_b = b_cat == "State government exposures"

    # latent borrower state: 0 healthy, 1 watch, 2 late (31-90 days), 3 NPA
    p3, p2, p1 = 0.018 + 0.050 * stress, 0.030 + 0.060 * stress, 0.030 + 0.060 * stress
    u = rng.random(nb)
    state = np.select([u < p3, u < p3 + p2, u < p3 + p2 + p1], [3, 2, 1], default=0)
    state = np.where(sov_b, 0, state)
    utp_only = (rng.random(nb) < 0.004 + 0.008 * stress) & (state < 3) & ~sov_b        # distress / concession without 90 days
    stage3_b = (state == 3) | utp_only
    b_utp = utp_only | ((state == 3) & (rng.random(nb) < 0.10))
    b_watch = (~stage3_b) & (((state == 1) & (rng.random(nb) < 0.8)) | ((state == 2) & (rng.random(nb) < 0.5))
                             | ((state == 0) & (rng.random(nb) < 0.008)))
    b_watch = b_watch & ~sov_b

    # borrower grades follow the state
    rm_b = np.array([CATS[c]["rmean"] for c in b_cat])
    b_orig = np.clip(np.round(rng.normal(rm_b, 1.2)), 1, 10).astype(int)
    bump = np.select([state == 0, state == 1, state == 2],
                     [rng.choice([-1, 0, 1, 2], nb, p=[.08, .72, .15, .05]), rng.integers(2, 5, nb), rng.integers(1, 4, nb)],
                     default=rng.integers(3, 6, nb))
    b_curr = np.where(sov_b, b_orig, np.clip(b_orig + bump, 1, 10))
    b_curr = np.where(b_watch | (state == 1), np.maximum(b_curr, 6), b_curr)
    b_curr = np.where(state == 2, np.maximum(b_curr, 7), b_curr)
    b_curr = np.minimum(np.where(stage3_b, np.maximum(b_curr, 9), b_curr), 10)

    # years in Stage 3 belong to the borrower: the same for all its loans
    yrs_b = np.where(state == 3,
                     np.clip(rng.choice([0.25, 0.7, 1.5, 2.5, 3.5, 5.0], nb, p=[.25, .2, .2, .15, .1, .1])
                             + rng.uniform(-0.15, 0.15, nb), 0.03, None),
                     np.where(utp_only, np.round(rng.uniform(0.1, 1.0, nb), 2), 0.0))

    # ---- loans inherit from their borrower ----
    st_l, s3_l, sov_l = state[inv], stage3_b[inv], sov_b[inv]
    is_first = np.zeros(n, bool); is_first[first] = True
    r_orig = np.clip(b_orig[inv] + rng.choice([-1, 0, 1], n, p=[.15, .70, .15]), 1, 10)
    r_curr = np.clip(b_curr[inv] + rng.choice([-1, 0, 1], n, p=[.10, .80, .10]), 1, 10)
    r_curr = np.where(sov_l, r_orig, r_curr)
    impaired = b_utp[inv]
    yrs = yrs_b[inv]

    # DPD follows the borrower state; NPA age (years) bounds how high it can be
    npa_loan = (st_l == 3) & (is_first | (rng.random(n) < 0.75))          # at least one NPA loan per NPA borrower
    days_in = np.round(yrs * 365)
    dpd = np.zeros(n, int)
    dpd = np.where(npa_loan, 90 + np.maximum(1, np.round(days_in * rng.uniform(0.5, 1.0, n))), dpd)
    dpd = np.where((st_l == 3) & ~npa_loan, rng.integers(0, 61, n), dpd)   # other loans of an NPA borrower: Stage 3 by contagion
    dpd = np.where(st_l == 2, np.where(is_first | (rng.random(n) < 0.7), rng.integers(31, 91, n), rng.integers(0, 31, n)), dpd)
    small_late = (st_l <= 1) & (rng.random(n) < np.where(st_l == 1, 0.12, 0.04))
    dpd = np.where(small_late, rng.integers(1, 31, n), dpd)
    dpd = np.where(sov_l, 0, dpd).astype(int)

    # grades never contradict delinquency or flags
    watch = b_watch[inv] & ~s3_l
    r_curr = np.where(s3_l, np.maximum(r_curr, 9), r_curr)
    r_curr = np.where((dpd > 60) & (dpd <= 90), np.maximum(r_curr, 7), r_curr)
    r_curr = np.where(((dpd > 30) & (dpd <= 60)) | watch, np.maximum(r_curr, 6), r_curr)
    r_curr = np.minimum(r_curr, 10).astype(int)

    # ---- exposure, security, terms ----
    outstanding = np.round(pc("scale") * np.exp(rng.normal(0, 0.7, n)), 2)
    is_rev = rng.random(n) < pc("rev")
    undrawn = np.where(is_rev & ~s3_l, np.round(outstanding * rng.uniform(0, 0.5, n), 2), 0.0)     # frozen once Stage 3
    amort = (rng.random(n) < pc("amort")) & ~is_rev
    over = np.where(is_rev, np.where(dpd > 90, dpd, np.minimum(dpd, 89)), 0)                       # over-limit days mirror DPD

    slo = np.array([CATS[c]["sec"][0] for c in cat]); shi = np.array([CATS[c]["sec"][1] for c in cat])
    sec = np.round(rng.uniform(slo, shi))
    coll = np.where(sec > 0, pc("coll"), "None")
    lo = np.array([CATS[c]["term"][0] for c in cat]); hi = np.array([CATS[c]["term"][1] for c in cat])
    term = np.round(rng.uniform(lo, hi), 1)
    term = np.where(s3_l, np.maximum(0.1, np.round(term * rng.uniform(0.3, 1.0, n), 1)), term)     # NPAs are near / past maturity
    eir = np.round(np.clip(pc("eir") + 0.4 * (r_orig - pc("rmean")) + rng.normal(0, 0.5, n), 4, 30), 2)  # riskier at origination -> pricier

    # ---- optional columns ----
    covenant = np.isin(cat, list(COV_CATS)) & (rng.random(n) < np.where(st_l >= 1, 0.25, 0.01)) & ~sov_l
    coll_dec = (sec > 0) & (coll != SPECIAL_COLL) & (rng.random(n) < np.where(st_l >= 1, 0.20, 0.01))
    rebut = (dpd > 30) & (dpd <= 60) & ~s3_l & (rng.random(n) < 0.08)

    now = np.where(s3_l | (dpd > 90), 3, np.where((dpd > 30) | watch | (r_curr - r_orig >= 3), 2, 1))
    pr = rng.random(n)
    prior = np.where(now == 3, np.select([pr < .75, pr < .97], [3, 2], default=1),
            np.where(now == 2, np.select([pr < .60, pr < .95], [2, 1], default=3),
                     np.select([pr < .93, pr < .98], [1, 2], default=3)))
    prior = np.where((prior == 3) & (now < 3) & (dpd > 0), 2, prior)      # a loan that left Stage 3 has cleared its arrears
    improved = prior > now
    months = np.where((dpd > 0) | (now == 3), 0.0,
                      np.where(improved, np.round(rng.uniform(0, 18, n)), np.round(rng.uniform(12, 60, n))))
    restr = (cat == "Restructured standard advances") | (improved & (prior == 3) & (rng.random(n) < 0.4))

    df = pd.DataFrame({
        "loan_id": [f"LN{i + 1:05d}" for i in range(n)], "borrower_id": borrower, "category": cat,
        "outstanding": outstanding, "undrawn_limit": undrawn, "is_revolving": is_rev, "amortising": amort,
        "dpd": dpd, "days_over_limit": over, "rating_orig": r_orig, "rating_curr": r_curr,
        "watchlist": watch, "covenant_breach": covenant, "collateral_decline": coll_dec,
        "dpd_rebuttal": rebut, "credit_impaired": impaired, "years_in_stage3": yrs, "prior_stage": prior,
        "restructured": restr, "months_regular": months, "secured_pct": sec,
        "collateral_type": coll, "remaining_term_yrs": term, "eir_pct": eir,
    })
    if not with_optional:
        df = df[CORE_COLS]                       # optional columns are then filled with safe defaults by sanitize()
    return sanitize(df)


def sanitize(df: pd.DataFrame) -> pd.DataFrame:
    """Make any (edited / uploaded) table safe for the engine."""
    d = df.copy()
    for c in COLS:
        if c not in d.columns:
            d[c] = False if c in BOOL_COLS else (np.nan if c == "months_regular" else NUM_DEFAULT.get(c, ""))
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

    dp_ = pd.to_numeric(d["dpd"], errors="coerce").fillna(0)
    d["months_regular"] = pd.to_numeric(d["months_regular"], errors="coerce").fillna(pd.Series(np.where(dp_ > 0, 0.0, 24.0), index=d.index))
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
    d["prior_stage"] = d["prior_stage"].round().clip(1, 3).astype(int)
    d["months_regular"] = d["months_regular"].clip(lower=0)
    return d


# ----------------------------------------------------------------------------
# 3. ENGINE
# ----------------------------------------------------------------------------
# ---- Basic consistency rules between columns ------------------------------------------------
RULES = [  # (id, rule, needs optional columns)
    ("R01", "Secured % above 0 needs a collateral type; 0% means collateral 'None'", False),
    ("R02", "No undrawn limit on Stage 3 borrowers (the facility is frozen)", False),
    ("R03", "Years in Stage 3 above 0 only for Stage 3 borrowers (NPA > 90 DPD, UTP flag, or another loan of that borrower)", False),
    ("R04", "DPD above 90 cannot exceed 90 + days spent in Stage 3 (+15 days tolerance)", False),
    ("R05", "Stage 3 borrowers are not on the watchlist", False),
    ("R06", "Stage 3 borrowers have a weak current grade (9 or 10)", False),
    ("R07", "Grade now is at least 7 when DPD is 61-90, and at least 6 when DPD is 31-60 or on the watchlist", False),
    ("R08", "Watchlist, UTP flag and years in Stage 3 agree across all loans of the same borrower", False),
    ("R09", "A facility is not both revolving and amortising", True),
    ("R10", "Days over limit only on revolving facilities", True),
    ("R11", "Collateral value drop needs secured exposure", True),
    ("R12", "30-DPD rebuttal only when DPD is 31-90", True),
    ("R13", "Months of regular payment is 0 while the loan is past due", True),
    ("R14", "A loan that was Stage 3 and is not any more has DPD = 0", True),
]


def _s3_like(d: pd.DataFrame) -> pd.Series:
    acct = (d["dpd"] > 90) | d["credit_impaired"] | (d["is_revolving"] & (d["days_over_limit"] >= 90))
    return acct | acct.groupby(d["borrower_id"]).transform("any")


def rule_masks(d: pd.DataFrame) -> dict:
    s3 = _s3_like(d)
    g = d.groupby("borrower_id")
    rc, dpd = d["rating_curr"], d["dpd"]
    yb = d["years_in_stage3"].where(s3).groupby(d["borrower_id"]).transform("nunique")
    return {
        "R01": ((d["secured_pct"] > 0) & (d["collateral_type"] == "None")) | ((d["secured_pct"] == 0) & (d["collateral_type"] != "None")),
        "R02": s3 & (d["undrawn_limit"] > 0),
        "R03": (d["years_in_stage3"] > 0) & ~s3,
        "R04": (dpd > 90) & ((dpd - 90) > d["years_in_stage3"] * 365 + 15),
        "R05": s3 & d["watchlist"],
        "R06": s3 & (rc < 9),
        "R07": (((dpd > 60) & (dpd <= 90)) & (rc < 7)) | ((((dpd > 30) & (dpd <= 60)) | d["watchlist"]) & (rc < 6)),
        "R08": (g["watchlist"].transform("nunique") > 1) | (g["credit_impaired"].transform("nunique") > 1) | (yb > 1),
        "R09": d["is_revolving"] & d["amortising"],
        "R10": ~d["is_revolving"] & (d["days_over_limit"] > 0),
        "R11": d["collateral_decline"] & (d["secured_pct"] == 0),
        "R12": d["dpd_rebuttal"] & ~((dpd > 30) & (dpd <= 90)),
        "R13": (dpd > 0) & (d["months_regular"] > 0),
        "R14": (d["prior_stage"] == 3) & ~s3 & (dpd > 0),
    }


def check_rules(d: pd.DataFrame, with_optional: bool) -> pd.DataFrame:
    masks = rule_masks(d)
    rows = []
    for rid, text, opt in RULES:
        if opt and not with_optional:
            continue
        bad = masks[rid]
        rows.append({"Rule": rid, "What it checks": text, "Violations": int(bad.sum()),
                     "Examples": ", ".join(d.loc[bad, "loan_id"].head(3).tolist())})
    return pd.DataFrame(rows)


def apply_rules(d: pd.DataFrame, with_optional: bool) -> pd.DataFrame:
    """Conservative fixes: remove the contradiction, never invent security or good news."""
    f = d.copy()
    for _ in range(2):
        g = f.groupby("borrower_id")
        f["watchlist"] = g["watchlist"].transform("max").astype(bool)
        f["credit_impaired"] = g["credit_impaired"].transform("max").astype(bool)
        f.loc[(f["secured_pct"] > 0) & (f["collateral_type"] == "None"), "secured_pct"] = 0.0
        f.loc[(f["secured_pct"] == 0) & (f["collateral_type"] != "None"), "collateral_type"] = "None"
        s3 = _s3_like(f)
        f.loc[s3, "undrawn_limit"] = 0.0
        f.loc[~s3, "years_in_stage3"] = 0.0
        need = np.where(s3 & (f["dpd"] > 90), np.ceil((f["dpd"] - 105).clip(lower=0) / 365 * 100) / 100, 0.0)
        f["years_in_stage3"] = np.maximum(f["years_in_stage3"], need)
        f.loc[s3, "years_in_stage3"] = f["years_in_stage3"].where(s3).groupby(f["borrower_id"]).transform("max")[s3]
        f.loc[s3, "watchlist"] = False
        floor = np.select([(f["dpd"] > 60) & (f["dpd"] <= 90), ((f["dpd"] > 30) & (f["dpd"] <= 60)) | f["watchlist"]], [7, 6], default=1)
        floor = np.where(s3, 9, floor)
        f["rating_curr"] = np.maximum(f["rating_curr"], floor)
        if with_optional:
            f.loc[f["is_revolving"] & f["amortising"], "amortising"] = False
            f.loc[~f["is_revolving"], "days_over_limit"] = 0
            f.loc[f["collateral_decline"] & (f["secured_pct"] == 0), "collateral_decline"] = False
            f.loc[f["dpd_rebuttal"] & ~((f["dpd"] > 30) & (f["dpd"] <= 90)), "dpd_rebuttal"] = False
            f.loc[(f["dpd"] > 0) & (f["months_regular"] > 0), "months_regular"] = 0.0
            f.loc[(f["prior_stage"] == 3) & ~s3 & (f["dpd"] > 0), "prior_stage"] = 2
    return sanitize(f)


def core_template() -> str:
    """CSV with only the 15 core columns and three sample loans."""
    rows = [dict(loan_id="LN00001", borrower_id="B1", category="Housing loan to individuals", outstanding=45.0, undrawn_limit=0.0, dpd=0,
                 rating_orig=3, rating_curr=3, credit_impaired=False, watchlist=False, years_in_stage3=0.0, secured_pct=100,
                 collateral_type="Property", remaining_term_yrs=15.0, eir_pct=8.5),
            dict(loan_id="LN00002", borrower_id="B2", category="Corporate loan", outstanding=1200.0, undrawn_limit=300.0, dpd=45,
                 rating_orig=4, rating_curr=6, credit_impaired=False, watchlist=True, years_in_stage3=0.0, secured_pct=40,
                 collateral_type="Receivables / Stock", remaining_term_yrs=4.0, eir_pct=9.5),
            dict(loan_id="LN00003", borrower_id="B3", category="Unsecured retail loans", outstanding=3.0, undrawn_limit=0.0, dpd=120,
                 rating_orig=6, rating_curr=9, credit_impaired=False, watchlist=False, years_in_stage3=0.4, secured_pct=0,
                 collateral_type="None", remaining_term_yrs=2.0, eir_pct=14.0)]
    return pd.DataFrame(rows)[CORE_COLS].to_csv(index=False)


def cum_pd(grade_idx: np.ndarray, T: np.ndarray, hz: np.ndarray, floor: float) -> np.ndarray:
    """Cumulative PD over T years for a rating grade, from the lifetime curve (floor applied to each year)."""
    K = int(np.ceil(min(T.max(), 40)))
    t = np.arange(1, K + 1)[None, :]
    frac = np.clip(T[:, None] - (t - 1), 0, 1)
    h = np.clip(np.maximum(hz[grade_idx][:, :K], floor), 0, 1)
    surv = np.cumprod(np.concatenate([np.ones((len(T), 1)), 1 - h[:, :-1]], axis=1), axis=1)
    return (surv * (1 - (1 - h) ** frac)).sum(axis=1)


def stage_loans(d: pd.DataFrame, A: dict, grade_pd: np.ndarray, hz: np.ndarray) -> pd.DataFrame:
    """Dual-gate staging (para 25-38) followed by the upgrade rules (para 77-80).
       Gate 1: Stage 3  = NPA (> 90 days, out of order) or UTP / credit-impaired flag, applied per borrower.
       Gate 2: Stage 2  = any SICR trigger: DPD backstop, revolving over limit, PD change vs origination,
                          watchlist, covenant / collateral flags (optionally rating notches, other loan late).
       Else    Stage 1."""
    nofl = pd.Series(False, index=d.index)
    npa_dpd = d["dpd"] > A["npa_dpd"]                                   # para 8: MORE than 90 days
    out_of_order = d["is_revolving"] & (d["days_over_limit"] >= A["npa_dpd"])
    s3_acct = npa_dpd | out_of_order | d["credit_impaired"]
    is3 = s3_acct | s3_acct.groupby(d["borrower_id"]).transform("any")  # para 76: borrower level

    late = d["dpd"] > A["sicr_dpd"]
    t_dpd = late & ~d["dpd_rebuttal"]                                   # para 33-36: rebuttable presumption
    t_rev = d["is_revolving"] & (d["days_over_limit"] >= A["rev_days"])

    # PD change vs origination (para 26 lifetime PD; para 27 allows the 12-month PD as a proxy)
    g_o = d["rating_orig"].to_numpy() - 1
    g_c = d["rating_curr"].to_numpy() - 1
    if A["pd_basis"] == "12-month PD":
        p_o = np.maximum(grade_pd[g_o], A["pd_floor"]); p_c = np.maximum(grade_pd[g_c], A["pd_floor"])
    else:
        T = d["remaining_term_yrs"].to_numpy()
        p_o = cum_pd(g_o, T, hz, A["pd_floor"]); p_c = cum_pd(g_c, T, hz, A["pd_floor"])
    ratio = p_c / np.maximum(p_o, 1e-12)
    rel = ratio > A["beta"]
    ab = (p_c - p_o) * 100 > A["alpha_pp"]
    hit = np.select([A["pd_mode"] == "Relative AND absolute", A["pd_mode"] == "Relative only"], [rel & ab, rel], default=ab)
    t_pd = pd.Series(hit, index=d.index) if A["use_dpd_test"] else nofl

    t_down = (d["rating_curr"] - d["rating_orig"] >= A["notches"]) if A["use_notches"] else nofl
    t_watch = d["watchlist"] if A["use_watch"] else nofl
    t_qual = (d["covenant_breach"] | d["collateral_decline"]) if A["use_qual"] else nofl            # Annex 1 (10), (13)
    t_cross = ((late.groupby(d["borrower_id"]).transform("sum") - late.astype(int)) > 0) if A["use_cross"] else nofl  # Annex 1 (8)
    is2 = ~is3 & (t_dpd | t_rev | t_pd | t_down | t_watch | t_qual | t_cross)
    raw = np.where(is3, 3, np.where(is2, 2, 1))

    reason = pd.Series("", index=d.index, dtype=object)
    for flag, txt in [(t_dpd, f"DPD>{A['sicr_dpd']}; "), (t_rev, "Over limit/DP; "), (t_pd, "PD vs origination; "),
                      (t_down, f"Downgrade>={A['notches']} notches; "), (t_watch, "Watchlist; "),
                      (t_qual, "Covenant breach / collateral drop; "), (t_cross, "Other loan of borrower late; ")]:
        reason = reason + np.where(flag, txt, "")
    r3 = np.select([npa_dpd, out_of_order, d["credit_impaired"]],
                   [f"NPA (DPD>{A['npa_dpd']})", "NPA (out of order)", "UTP / credit-impaired flag"],
                   default="Borrower-level Stage 3")
    base_reason = np.where(raw == 3, r3, np.where(raw == 2, reason.str.rstrip("; ").to_numpy(), "Performing"))

    # ---- upgrade rules (para 77-80) -------------------------------------------------
    prior = d["prior_stage"].to_numpy(); mreg = d["months_regular"].to_numpy(); restr = d["restructured"].to_numpy()
    stage = raw.copy()
    note = np.full(len(d), "", dtype=object)
    P1, P2 = A["restr_s3_m"], A["restr_s2_m"]
    m1 = (prior == 3) & restr & (raw < 3) & (mreg < P1)                  # restructured: stay in Stage 3 first
    stage = np.where(m1, 3, stage); note = np.where(m1, f"Restructured: held in Stage 3 until {P1:.0f} months regular (para 78)", note)
    m2 = (prior == 3) & restr & (raw < 2) & (mreg >= P1) & (mreg < P1 + P2)   # then Stage 2 for a further period
    stage = np.where(m2, 2, stage); note = np.where(m2, f"Restructured: Stage 2 until {P1 + P2:.0f} months regular (para 78)", note)
    prob = (prior >= 2) & (raw < prior) & ~m1 & ~m2 & ~restr & (mreg < A["probation_m"])   # bank's own policy (0 = RBI text)
    stage = np.where(prob, np.maximum(stage, 2), stage); note = np.where(prob, f"Bank probation: under {A['probation_m']:.0f} months regular", note)
    held = m1 | m2 | prob

    out = d.copy()
    out["stage"] = stage
    out["stage_reason"] = np.where(held, note, base_reason)
    out["stage_move"] = np.where(stage < prior, "Improved", np.where(stage > prior, "Worsened", "Unchanged"))
    out["pd_orig_pct"] = p_o * 100
    out["pd_now_pct"] = p_c * 100
    out["pd_ratio"] = ratio
    for nm, flag in [("dpd", t_dpd), ("rev", t_rev), ("pd", t_pd), ("notch", t_down), ("watch", t_watch), ("qual", t_qual), ("cross", t_cross)]:
        out[f"trg_{nm}"] = flag.to_numpy(bool)
    return out


def ecl_terms(r: pd.DataFrame, A: dict, pd_mult: float, lgd_mult: float, grade_pd: np.ndarray, hz: np.ndarray) -> dict:
    """Year-by-year building blocks (loans x years) with the TWO PDs:
       - 12-month PD  (grade table)            -> Stage 1, year 1 only
       - lifetime PD  (term-structure curve)   -> Stage 2, every year of the remaining term"""
    stage = r["stage"].to_numpy()
    T = r["remaining_term_yrs"].to_numpy()
    ead = r["ead"].to_numpy()
    g = r["rating_curr"].to_numpy() - 1
    lgd = np.clip(r["lgd"].to_numpy() * lgd_mult, 0, 1)
    K = int(np.ceil(min(T.max(), 40)))
    t = np.arange(1, K + 1)[None, :]
    Tc = T[:, None]
    frac = np.clip(Tc - (t - 1), 0, 1)                                          # share of year t inside the term

    pd12 = np.clip(np.maximum(grade_pd[g] * pd_mult, A["pd_floor"]), 0, 1)      # 12-month PD (scenario-adjusted, floored)
    marg_12 = np.where(t == 1, 1 - (1 - pd12[:, None]) ** frac, 0.0)

    h = np.clip(np.maximum(hz[g][:, :K] * pd_mult, A["pd_floor"]), 0, 1)        # conditional PD in each year
    surv = np.cumprod(np.concatenate([np.ones((len(r), 1)), 1 - h[:, :-1]], axis=1), axis=1)   # survival to start of year t
    marg_life = surv * (1 - (1 - h) ** frac)                                    # PD of defaulting inside year t

    marginal = np.where(stage[:, None] == 1, marg_12, marg_life)
    mask = np.where(stage[:, None] == 1, (t == 1), True)                        # Stage 1 -> 12m only, Stage 2 -> lifetime
    ead_t = ead[:, None] * np.where((r["amortising"].to_numpy() | bool(A.get("amort_all", False)))[:, None], np.clip(1 - (t - 1) / Tc, 0, 1), 1.0)
    if A["discount"]:
        eir = r["eir_pct"].to_numpy()[:, None] / 100
        dft = (1 + eir) ** (-((t - 1) + frac / 2))
    else:
        dft = np.ones_like(frac)
    return dict(t=t, frac=frac, surv=surv, marginal=marginal, marg_12=marg_12, marg_life=marg_life, mask=mask,
                ead_t=ead_t, dft=dft, lgd=lgd, pd12=pd12, pd_life=marg_life.sum(axis=1))


def scenario_ecl(r: pd.DataFrame, A: dict, pd_mult: float, lgd_mult: float, grade_pd: np.ndarray, hz: np.ndarray) -> np.ndarray:
    X = ecl_terms(r, A, pd_mult, lgd_mult, grade_pd, hz)
    ecl12 = (X["marginal"] * X["mask"] * X["lgd"][:, None] * X["ead_t"] * X["dft"]).sum(axis=1)
    ecl3 = r["ead"].to_numpy() * X["lgd"]                                        # Stage 3: PD = 100%
    return np.where(r["stage"].to_numpy() == 3, ecl3, ecl12)


def run_engine(d: pd.DataFrame, A: dict, scen: pd.DataFrame, grade_pd: np.ndarray, hz: np.ndarray):
    r = stage_loans(d, A, grade_pd, hz)
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
        r[f"ecl_{nm}"] = scenario_ecl(r, A, float(pm), float(lm), grade_pd, hz)
    r["ecl_model"] = sum(wi * r[f"ecl_{nm}"] for wi, nm in zip(w, names))
    r["ecl_adj"] = r["ecl_model"] * (1 + A["overlay"] / 100)

    # PD shown for information (base scenario, 12m, floored)
    X0 = ecl_terms(r, A, 1.0, 1.0, grade_pd, hz)
    r["pd12_pct"] = np.where(stage == 3, 100.0, X0["pd12"] * 100)               # 12-month PD
    r["pd_life_pct"] = np.where(stage == 3, 100.0, X0["pd_life"] * 100)         # lifetime PD over the remaining term
    r["pd_used_pct"] = np.where(stage == 1, r["pd12_pct"], r["pd_life_pct"])
    r["pd_type"] = np.where(stage == 1, "12-month", np.where(stage == 2, "Lifetime", "Default (100%)"))

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
    # Interest income (para 113-116), annualised: EIR x gross carrying amount in Stage 1/2; no accrual in Stage 3
    r["interest_annual"] = r["outstanding"] * r["eir_pct"] / 100
    r["interest_accrued"] = np.where(r["stage"] < 3, r["interest_annual"], 0.0)
    r["interest_suspended"] = np.where(r["stage"] == 3, r["interest_annual"], 0.0)
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
    use_opt = st.checkbox("Use optional columns", False,
                          help="Off = core mode: the app runs on the 15 core columns only. On = adds revolving limits, repayment profile, "
                               "covenant / collateral flags, DPD rebuttal, last-stage history and restructuring.")
    g_n = st.slider("Number of loans", 50, 5000, 400, step=50)
    g_seed = st.number_input("Random seed", 0, 99999, 42)
    g_stress = st.slider("Portfolio stress", 0.0, 1.0, 0.3, 0.05,
                         help="Higher = more delinquency, downgrades and NPAs")
    if st.button("Generate new data", type="primary", width="stretch"):
        st.session_state.loans = generate_loans(int(g_n), int(g_seed), float(g_stress), use_opt)
        st.session_state.ver += 1
        st.rerun()
    up = st.file_uploader("…or upload your own CSV", type="csv")
    if up is not None and st.button("Load uploaded CSV", width="stretch"):
        raw_up = pd.read_csv(up)
        miss = [c for c in CORE_COLS if c not in raw_up.columns]
        ignored = [c for c in raw_up.columns if c in OPT_COLS] if not use_opt else []
        st.session_state.loans = sanitize(raw_up if use_opt else raw_up[[c for c in raw_up.columns if c not in OPT_COLS]])
        st.session_state.upload_msg = (("warning", "Missing core columns filled with defaults: " + ", ".join(miss)) if miss else
                                       ("info", "Optional columns ignored (tick 'Use optional columns' to use them): " + ", ".join(ignored)) if ignored else
                                       ("success", "File loaded: all 15 core columns found."))
        st.session_state.ver += 1
        st.rerun()
    if st.session_state.get("upload_msg"):
        getattr(st, st.session_state.upload_msg[0])(st.session_state.upload_msg[1])
    st.download_button("⬇️ CSV template (15 core columns)", core_template(), "ecl_core_template.csv", "text/csv", width="stretch")

A = {}
with st.sidebar.expander("1 · Staging rules (para 25-38, 76-81)"):
    st.caption("Gate 1 · Stage 3")
    A["npa_dpd"] = st.number_input("NPA when DPD >", 30, 365, 90, help="Para 8: overdue for MORE than 90 days")
    st.caption("Gate 2 · Stage 2 (any one trigger)")
    A["sicr_dpd"] = st.number_input("DPD backstop: DPD >", 0, 90, 30, help="Para 33: rebuttable 30-DPD presumption")
    A["rev_days"] = st.number_input("Revolving: days over limit/DP ≥", 1, 89, 60, help="Para 33, revolving facilities") if use_opt else 60
    A["use_dpd_test"] = st.checkbox("PD change vs origination (ΔPD)", True,
                                    help="Thresholds are set by the bank, documented and applied consistently (para 29-30)")
    A["pd_basis"] = st.selectbox("PD used in the ΔPD test", ["Lifetime PD", "12-month PD"],
                                 help="Para 26 compares lifetime PD. Para 27 allows the 12-month PD when default risk is not concentrated beyond 12 months.")
    A["pd_mode"] = st.selectbox("ΔPD rule", ["Relative AND absolute", "Relative only", "Absolute only"])
    A["beta"] = st.number_input("β: PD now ÷ PD at origination >", 1.0, 20.0, 2.5, 0.1)
    A["alpha_pp"] = st.number_input("α: PD now − PD at origination > (% points)", 0.0, 20.0, 0.5, 0.1)
    A["use_notches"] = st.checkbox("Rating downgrade (notches)", False, help="Mostly redundant once the ΔPD test is on")
    A["notches"] = st.number_input("…notches", 1, 9, 3)
    A["use_watch"] = st.checkbox("Watchlist", True)
    A["use_qual"] = st.checkbox("Covenant breach / collateral drop", True, help="Annex 1 indicators (10) and (13)") if use_opt else False
    A["use_cross"] = st.checkbox("Another loan of the borrower is >30 DPD", False, help="Annex 1 indicator (8)")
    if use_opt:
        st.caption("Upgrade rules (para 77-80)")
        A["probation_m"] = st.number_input("Bank probation before moving to a lower stage (months)", 0, 36, 0,
                                           help="RBI text (para 77): a non-restructured Stage 3 loan may go straight to Stage 1 (or Stage 2 if SICR) once all arrears clear. 0 = follow RBI text. Above 0 is your own policy: document it.")
        A["restr_s3_m"] = st.number_input("Restructured: months regular before Stage 3 → 2", 0, 60, 12,
                                          help="Take from the Resolution of Stressed Assets Directions (paras 58/60). 12 is a placeholder.")
        A["restr_s2_m"] = st.number_input("Restructured: further months before Stage 2 → 1", 0, 60, 12, help="Placeholder, as above")
    else:
        A["probation_m"], A["restr_s3_m"], A["restr_s2_m"] = 0, 12, 12
        st.caption("Upgrade rules (para 77-80) need the optional 'last stage' columns.")

with st.sidebar.expander("2 · PD, LGD, EAD (para 96-100)"):
    A["pd_floor"] = st.number_input("12m PD floor (%)", 0.0, 5.0, 0.03, 0.01, format="%.2f") / 100
    A["lgd_sec"] = st.number_input("LGD - secured portion (%)", 0.0, 100.0, 65.0) / 100
    A["lgd_unsec"] = st.number_input("LGD - unsecured portion (%)", 0.0, 100.0, 70.0) / 100
    A["lgd_special"] = st.number_input("LGD - cash/gold/govt sec/LIC/KVP/NSC (%)", 0.0, 100.0, 30.0) / 100
    A["ccf"] = st.number_input("CCF on undrawn limits (%)", 0.0, 100.0, 40.0,
                               help="Placeholder: take the value from the Standardised Approach Directions") / 100
    A["amort_all"] = False if use_opt else st.checkbox("Amortise EAD linearly over the remaining term", False,
                                                       help="Core mode has no repayment-profile column. Off = flat EAD (conservative). On = balance falls evenly to zero.")
    st.caption("① 12-month PD by rating grade (%) — used for Stage 1")
    pd_tbl = st.data_editor(pd.DataFrame({"grade": range(1, 11), "pd_pct": DEFAULT_PD}),
                            hide_index=True, disabled=["grade"], key="pd_tbl", width="stretch")
    pd_tbl["pd_pct"] = pd.to_numeric(pd_tbl["pd_pct"], errors="coerce").fillna(0).clip(0, 100)
    st.caption("② Lifetime PD: cumulative default probability (%) by year — used for Stage 2")
    derive = st.checkbox("Derive lifetime curve from the 12-month PD", True,
                         help="Constant yearly PD: cumulative = 1 − (1 − PD)^years. Untick to type your own curve "
                              "(para 45: lifetime PD should not be a mechanical scaling of the 12-month PD).")
    base_curve = derived_curve(pd_tbl.sort_values("grade")["pd_pct"].to_numpy(float))
    if derive:
        ts = base_curve
        st.dataframe(ts.round(2), hide_index=True, width="stretch")
    else:
        ts = st.data_editor(base_curve.round(4), hide_index=True, disabled=["grade"], key="ts_edit", width="stretch")
        ts = ts.apply(pd.to_numeric, errors="coerce").fillna(0)

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

grade_pd = np.array(pd_tbl.sort_values("grade")["pd_pct"].clip(0, 100), float) / 100          # ① 12-month PD
ts_used = ts.sort_values("grade").reset_index(drop=True)
hz = hazards_from_curve(ts_used[[f"y{t}" for t in YRS]].to_numpy(float))                      # ② lifetime PD curve

# ----------------------------------------------------------------------------
# 5. LAYOUT
# ----------------------------------------------------------------------------
st.title("RBI ECL Model Lab")
st.caption("Edit the data or the assumptions — staging, ECL, floors and the dashboard recompute instantly.")
tab_dash, tab_data, tab_calc, tab_exp, tab_floor, tab_rep, tab_audit, tab_guide = st.tabs(
    ["📊 Dashboard", "🗂️ Data (editable)", "🧮 Account-level ECL", "🔍 Loan explorer", "🧱 Prudential floors",
     "📑 Annex-4 style tables", "🕵️ Audit checks", "📖 Guide & limits"])

# ---- Data tab (rendered first: its output feeds everything) ------------------
with tab_data:
    st.markdown("**Loan book** — edit cells, add rows (＋ at the bottom) or delete rows. Everything else updates.")
    if use_opt:
        st.caption("Core + optional columns. Optional: " + ", ".join(OPT_COLS))
    else:
        st.caption("Core mode: these 15 columns are all the app needs. Tick 'Use optional columns' in the sidebar to add: "
                   + ", ".join(OPT_COLS) + ". Missing optional columns take safe defaults (see the Guide tab).")
    edited = st.data_editor(
        st.session_state.loans if use_opt else st.session_state.loans[CORE_COLS], num_rows="dynamic", height=480, width="stretch",
        key=f"editor_{st.session_state.ver}_{int(use_opt)}",
        column_config={
            "category": st.column_config.SelectboxColumn("RBI product category", options=CAT_NAMES, required=True, width="large"),
            "collateral_type": st.column_config.SelectboxColumn("Collateral", options=COLL_TYPES, width="medium"),
            "outstanding": st.column_config.NumberColumn("Outstanding (₹ L)", min_value=0, format="%.2f"),
            "undrawn_limit": st.column_config.NumberColumn("Undrawn (₹ L)", min_value=0, format="%.2f"),
            "dpd": st.column_config.NumberColumn("DPD", min_value=0, step=1),
            "days_over_limit": st.column_config.NumberColumn("Days over limit/DP", min_value=0, step=1),
            "rating_orig": st.column_config.NumberColumn("Rating @origination (1-10)", min_value=1, max_value=10, step=1),
            "rating_curr": st.column_config.NumberColumn("Rating now (1-10)", min_value=1, max_value=10, step=1),
            "covenant_breach": st.column_config.CheckboxColumn("Covenant breach / waiver"),
            "collateral_decline": st.column_config.CheckboxColumn("Collateral value drop"),
            "dpd_rebuttal": st.column_config.CheckboxColumn("30-DPD rebutted (documented)"),
            "credit_impaired": st.column_config.CheckboxColumn("UTP / credit-impaired flag"),
            "prior_stage": st.column_config.NumberColumn("Stage at last reporting date", min_value=1, max_value=3, step=1),
            "restructured": st.column_config.CheckboxColumn("Restructured"),
            "months_regular": st.column_config.NumberColumn("Months of regular payment", min_value=0, format="%.0f"),
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
    viol = check_rules(loans, use_opt)
    nbad = int(viol["Violations"].sum())
    with st.expander(f"✅ Data consistency rules: {'all pass' if nbad == 0 else str(nbad) + ' violations'}", expanded=nbad > 0):
        st.caption("Columns depend on each other (a loan 120 days late cannot be grade 2; a Stage 3 borrower has no undrawn limit; "
                   "a borrower's loans share one watchlist status). Edited or uploaded data is checked against these rules.")
        st.dataframe(viol, hide_index=True, width="stretch")
        if nbad and st.button("Apply rule fixes to the data"):
            st.session_state.loans = apply_rules(loans, use_opt)
            st.session_state.ver += 1
            st.rerun()

if loans.empty:
    st.info("The loan book is empty — generate or add some loans.")
    st.stop()

R = run_engine(loans, A, scen, grade_pd, hz)
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

    acc = R["interest_accrued"].sum()
    k2 = st.columns(3)
    k2[0].metric("Interest accrued p.a. (Stage 1+2)", fmt_amt(acc), help="Para 113: EIR × gross carrying amount")
    k2[1].metric("Interest NOT accrued (Stage 3)", fmt_amt(R["interest_suspended"].sum()),
                 help="Para 115: credit-impaired assets earn interest on a cash basis only")
    k2[2].metric("Provision ÷ accrued interest", f"{tot_prov / acc * 100:.0f}%" if acc else "–",
                 help="How many years of interest income the allowance equals")

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
        R["dpd_bucket"] = pd.cut(R["dpd"], [-1, 0, 30, 60, 90, 10**6],
                                 labels=["Current", "1-30", "31-60", "61-90", ">90"]).astype(str)
        dd = R.groupby(["dpd_bucket", "stage_label"])["outstanding"].sum().reset_index()
        st.altair_chart(alt.Chart(dd).mark_bar().encode(
            x=alt.X("dpd_bucket:N", sort=["Current", "1-30", "31-60", "61-90", ">90"], title="Days past due"),
            y=alt.Y("outstanding:Q", title="Exposure (₹ L)"),
            color=alt.Color("stage_label:N", scale=STAGE_COLORS, title="Stage"),
            tooltip=["dpd_bucket", "stage_label", alt.Tooltip("outstanding:Q", format=",.0f")]).properties(height=300),
            width="stretch")

    g1, g2 = st.columns(2)
    with g1:
        st.subheader("Two PDs: cumulative default curve by grade")
        cv = ts_used.melt("grade", var_name="year", value_name="cum_pd")
        cv["year"] = cv["year"].str[1:].astype(int); cv["grade"] = cv["grade"].astype(str)
        st.altair_chart(alt.Chart(cv).mark_line(point=True).encode(
            x=alt.X("year:O", title="Years from today"), y=alt.Y("cum_pd:Q", title="Cumulative PD (%)"),
            color=alt.Color("grade:N", title="Rating grade", sort=[str(i) for i in range(1, 11)]),
            tooltip=["grade", "year", alt.Tooltip("cum_pd:Q", format=".2f")]).properties(height=300), width="stretch")
        st.caption("Year 1 of each line = the 12-month PD (Stage 1). The whole line = the lifetime PD (Stage 2).")
    with g2:
        st.subheader("Average PD by stage: 12-month vs lifetime")
        wsum = R.groupby("stage_label")["ead"].sum()
        pdl = pd.DataFrame({"12-month PD": (R["pd12_pct"] * R["ead"]).groupby(R["stage_label"]).sum() / wsum,
                            "Lifetime PD": (R["pd_life_pct"] * R["ead"]).groupby(R["stage_label"]).sum() / wsum}).reset_index()
        pdl = pdl.melt("stage_label", var_name="type", value_name="pd")
        st.altair_chart(alt.Chart(pdl).mark_bar().encode(
            x=alt.X("stage_label:N", title=None), xOffset="type:N", y=alt.Y("pd:Q", title="EAD-weighted PD (%)"),
            color=alt.Color("type:N", scale=alt.Scale(range=["#2e9e6b", "#f5a524"]), title=None),
            tooltip=["stage_label", "type", alt.Tooltip("pd:Q", format=".2f")]).properties(height=300), width="stretch")
        st.caption("Stage 1 loans are provisioned on the 12-month PD, Stage 2 on the lifetime PD, Stage 3 at 100%.")

    st.subheader("What pushes loans into Stage 2?")
    TRG = {"DPD backstop": "trg_dpd", "Revolving over limit": "trg_rev", "PD vs origination": "trg_pd", "Rating notches": "trg_notch",
           "Watchlist": "trg_watch", "Covenant / collateral": "trg_qual", "Other loan of borrower late": "trg_cross"}
    if not use_opt:
        TRG = {k: v for k, v in TRG.items() if v not in ("trg_rev", "trg_qual")}     # need optional columns
    s2d = R[R["stage"] == 2]
    if len(s2d):
        flg = s2d[list(TRG.values())].astype(int)
        nfl = flg.sum(axis=1)
        trows = []
        for lab_, col_ in TRG.items():
            trows.append({"trigger": lab_, "measure": "Loans it flags", "loans": int(flg[col_].sum())})
            trows.append({"trigger": lab_, "measure": "Loans it is the ONLY trigger for", "loans": int(((flg[col_] == 1) & (nfl == 1)).sum())})
        st.altair_chart(alt.Chart(pd.DataFrame(trows)).mark_bar().encode(
            y=alt.Y("trigger:N", sort=None, title=None), x=alt.X("loans:Q", title="Stage 2 loans"), yOffset="measure:N",
            color=alt.Color("measure:N", scale=alt.Scale(range=["#8aa4c8", "#e8793a"]), title=None),
            tooltip=["trigger", "measure", "loans"]).properties(height=300), width="stretch")
        st.caption("A trigger whose 'only trigger' bar is near zero adds little on its own: a candidate to drop for a leaner model. "
                   "Stage 2 loans held there by probation rules are not shown.")

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
    show = ["loan_id", "borrower_id", "category", "stage_label", "stage_reason", "prior_stage", "stage_move", "pd_orig_pct", "pd_now_pct", "pd_ratio", "outstanding", "ead", "pd12_pct", "pd_life_pct", "pd_type", "lgd",
            "ecl_adj", "floor_pct", "s3_bucket", "floor_amt", "topup", "provision", "binding"]
    if not use_opt:
        show = [c for c in show if c not in ("prior_stage", "stage_move")]
    st.dataframe(v[show], hide_index=True, width="stretch", height=520, column_config={
        "stage_label": "Stage", "stage_reason": "Why", "prior_stage": "Last stage", "stage_move": "Move",
        "pd_orig_pct": st.column_config.NumberColumn("PD at origination %", format="%.3f"),
        "pd_now_pct": st.column_config.NumberColumn("PD now %", format="%.3f"),
        "pd_ratio": st.column_config.NumberColumn("PD ratio ×", format="%.2f"), "outstanding": st.column_config.NumberColumn("Outstanding", format="%.1f"),
        "ead": st.column_config.NumberColumn("EAD", format="%.1f"), "pd12_pct": st.column_config.NumberColumn("12-month PD %", format="%.2f"),
        "pd_life_pct": st.column_config.NumberColumn("Lifetime PD %", format="%.2f"), "pd_type": "PD used",
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
    order = ["Current", "1-30", "31-60", "61-90", ">90"]
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
        "Item": ["Stage 3 trigger", "PD approach", "SICR - DPD backstop", "SICR - revolving", "SICR - PD vs origination", "SICR - rating downgrade", "SICR - watchlist",
                 "12m PD floor", "LGD secured / unsecured / special", "CCF", "Discounting", "Overlay", "Upgrade rules"],
        "Value": [f"DPD > {A['npa_dpd']} / out of order / flag / borrower-level",
                  "12-month PD (Stage 1) · lifetime PD curve (Stage 2) · 100% (Stage 3)", f"DPD > {A['sicr_dpd']}",
                  f"days over limit ≥ {A['rev_days']}",
                  (f"{A['pd_basis']}: {A['pd_mode']}, β={A['beta']}, α={A['alpha_pp']} pp" if A["use_dpd_test"] else "off"),
                  f"≥ {A['notches']} notches" if A["use_notches"] else "off",
                  "on" if A["use_watch"] else "off", f"{A['pd_floor'] * 100:.2f}%",
                  f"{A['lgd_sec'] * 100:.0f}% / {A['lgd_unsec'] * 100:.0f}% / {A['lgd_special'] * 100:.0f}%",
                  f"{A['ccf'] * 100:.0f}%", "EIR" if A["discount"] else "none", f"{A['overlay']:+.1f}% of ECL",
                  f"Straight upgrade (para 77); own probation {A['probation_m']:.0f}m; restructured {A['restr_s3_m']:.0f}m + {A['restr_s2_m']:.0f}m"]}),
        hide_index=True, width="stretch")

# ---- Loan explorer ---------------------------------------------------------------------
with tab_exp:
    st.markdown("**Follow one loan year by year.** Pick a loan and a scenario to see how PD, LGD, EAD and the discount factor "
                "combine into its ECL, and how much extra the loan costs when it moves from 12-month to lifetime ECL (Stage 1 → 2).")
    ids = R["loan_id"].tolist()
    first2 = R.index[R["stage"] == 2]
    sel = st.selectbox("Loan", ids, index=int(R.index.get_loc(first2[0])) if len(first2) else 0)
    row = R[R["loan_id"] == sel].head(1)
    sc_names = scen["scenario"].tolist()
    sc_pick = st.selectbox("Scenario", sc_names)
    sc_row = scen[scen["scenario"] == sc_pick].iloc[0]
    X = ecl_terms(row, A, float(sc_row["pd_mult"]), float(sc_row["lgd_mult"]), grade_pd, hz)
    r0 = row.iloc[0]
    s3 = r0["stage"] == 3
    m = st.columns(6)
    m[0].metric("Stage", r0["stage_label"], r0["stage_reason"], delta_color="off")
    m[1].metric("EAD", fmt_amt(r0["ead"]))
    m[2].metric("12-month PD", "100%" if s3 else f"{X['pd12'][0] * 100:.2f}%", help="Used for Stage 1")
    m[3].metric("Lifetime PD", "100%" if s3 else f"{X['pd_life'][0] * 100:.2f}%", help="Over the remaining term; used for Stage 2")
    m[4].metric("LGD", f"{X['lgd'][0] * 100:.1f}%")
    m[5].metric("Discount at EIR", f"{r0['eir_pct']:.1f}%" if A["discount"] else "off")
    if r0["stage"] == 3:
        st.info(f"Stage 3: default is treated as certain (PD = 100%), so ECL = EAD × LGD = {fmt_amt(r0['ead'] * X['lgd'][0])}. "
                f"The floor is then {r0['floor_pct']:.1f}% of EAD ({r0['s3_bucket']} in Stage 3).")
    else:
        yrs_ = X["t"][0]
        ml = X["marg_life"][0]                                   # lifetime path, always shown
        undisc = ml * X["lgd"][0] * X["ead_t"][0]
        pv = undisc * X["dft"][0]
        tbl = pd.DataFrame({"Year": yrs_, "Share of year in term": X["frac"][0], "Survival at start": X["surv"][0],
                            "Lifetime marginal PD": ml, "Cumulative PD": np.cumsum(ml), "EAD": X["ead_t"][0], "LGD": X["lgd"][0],
                            "ECL (undiscounted)": undisc, "Discount factor": X["dft"][0], "PV of ECL": pv,
                            "Counted?": np.where(X["mask"][0], "Yes (12m PD)" if r0["stage"] == 1 else "Yes (lifetime PD)", "No (beyond 12m)")})
        st.dataframe(tbl, hide_index=True, width="stretch", column_config={
            "Share of year in term": st.column_config.NumberColumn(format="%.2f"),
            "Survival at start": st.column_config.NumberColumn(format="%.4f"),
            "Lifetime marginal PD": st.column_config.NumberColumn(format="%.4f"),
            "Cumulative PD": st.column_config.NumberColumn(format="%.4f"),
            "EAD": st.column_config.NumberColumn(format="%.2f"), "LGD": st.column_config.NumberColumn(format="%.2f"),
            "ECL (undiscounted)": st.column_config.NumberColumn(format="%.3f"),
            "Discount factor": st.column_config.NumberColumn(format="%.4f"),
            "PV of ECL": st.column_config.NumberColumn(format="%.3f")})
        e12 = float((X["marg_12"][0] * X["lgd"][0] * X["ead_t"][0] * X["dft"][0]).sum())   # 12-month PD view
        elife = float(pv.sum())                                                           # lifetime PD view
        c1, c2, c3 = st.columns(3)
        c1.metric("12-month ECL (Stage 1 view)", fmt_amt(e12))
        c2.metric("Lifetime ECL (Stage 2 view)", fmt_amt(elife))
        c3.metric("Cliff effect if it moves to Stage 2", f"× {elife / e12:.1f}" if e12 > 0 else "–")
        ch = pd.DataFrame({"Year": yrs_.astype(str), "PV of ECL": pv, "Counted": np.where(X["mask"][0], "Counted at current stage", "Only if lifetime")})
        st.altair_chart(alt.Chart(ch).mark_bar().encode(
            x=alt.X("Year:N", sort=None), y=alt.Y("PV of ECL:Q", title="PV of ECL (₹ L)"),
            color=alt.Color("Counted:N", scale=alt.Scale(range=["#3a6ea5", "#c5cfdf"]), title=None),
            tooltip=["Year", alt.Tooltip("PV of ECL:Q", format=",.3f")]).properties(height=260), width="stretch")
    st.caption("One scenario shown. The reported ECL is the probability-weighted average of all scenarios, then topped up by the floors.")

# ---- Interest income by stage (Chapter IV) ----------------------------------------------------
with tab_rep:
    st.subheader("D. Interest income by stage (Chapter IV, annualised)")
    inc = R.groupby("stage_label").agg(gross=("outstanding", "sum"), accrued=("interest_accrued", "sum"),
                                       not_accrued=("interest_suspended", "sum")).reset_index()
    inc["basis"] = inc["stage_label"].map({"Stage 1": "EIR × gross carrying amount", "Stage 2": "EIR × gross carrying amount",
                                           "Stage 3": "No accrual: cash basis only"})
    st.dataframe(inc, hide_index=True, width="stretch", column_config={
        "stage_label": "Stage", "gross": st.column_config.NumberColumn("Gross carrying amount", format="%.1f"),
        "accrued": st.column_config.NumberColumn("Interest accrued", format="%.1f"),
        "not_accrued": st.column_config.NumberColumn("Interest not accrued", format="%.1f"), "basis": "RBI basis (para 113, 115)"})
    st.caption("Loans outstanding at 31 March 2027 may keep contractual-rate income until 31 March 2030 (para 114). "
               "This app always uses each loan's EIR column.")

    st.subheader("E. Stage migration since the last reporting date")
    if not use_opt:
        st.info("Needs the optional 'Stage at last reporting date' column. Tick 'Use optional columns' in the sidebar.")
    else:
        lab3 = {1: "Stage 1", 2: "Stage 2", 3: "Stage 3"}
        mg_x = R.pivot_table(index="prior_stage", columns="stage", values="outstanding", aggfunc="sum", fill_value=0).reindex(index=[1, 2, 3], columns=[1, 2, 3], fill_value=0)
        mg_n = R.pivot_table(index="prior_stage", columns="stage", values="loan_id", aggfunc="count", fill_value=0).reindex(index=[1, 2, 3], columns=[1, 2, 3], fill_value=0)
        for t_ in (mg_x, mg_n):
            t_.index = [f"From {lab3[i]}" for i in t_.index]; t_.columns = [f"To {lab3[i]}" for i in t_.columns]
        m1_, m2_ = st.columns(2)
        m1_.markdown("**Exposure (₹ lakh)**"); m1_.dataframe(mg_x.style.format("{:,.1f}"), width="stretch")
        m2_.markdown("**Number of loans**"); m2_.dataframe(mg_n.style.format("{:,.0f}"), width="stretch")
        st.caption("Needs the 'Stage at last reporting date' column. Below the diagonal = upgrades, above = downgrades.")

# ---- Audit checks ---------------------------------------------------------------------------------
def build_checks():
    rows = []
    def add(area, check, ok, detail):
        rows.append({"Area": area, "Check": check, "Status": "✅ Pass" if ok else "⚠️ Review", "Detail": detail})
    add("Data", "Input data follows the consistency rules (R01-R14)", nbad == 0,
        "All rules pass" if nbad == 0 else "; ".join(f"{a_}: {b_} loans" for a_, b_ in viol.loc[viol["Violations"] > 0, ["Rule", "Violations"]].values))
    n_dup = int(loans["loan_id"].duplicated().sum())
    add("Data", "Loan IDs are unique", n_dup == 0, f"{n_dup} duplicate IDs")
    n_zero = int((loans["outstanding"] <= 0).sum())
    add("Data", "Every loan has a positive balance", n_zero == 0, f"{n_zero} loans with zero balance")
    n_col = int(((loans["secured_pct"] > 0) & (loans["collateral_type"] == "None")).sum())
    add("Data", "Secured % always has a collateral type", n_col == 0, f"{n_col} loans claim security but list no collateral")
    if use_opt:
        n_und = int(((loans["undrawn_limit"] > 0) & ~loans["is_revolving"]).sum())
        add("Data", "Undrawn limits sit on revolving facilities", n_und == 0, f"{n_und} non-revolving loans with an undrawn limit")
    if use_opt:
        n_reb = int((loans["dpd_rebuttal"] & (loans["dpd"] > A["sicr_dpd"])).sum())
        add("Staging", "30-DPD rebuttals are rare and documented (para 34-36)", n_reb == 0,
            f"{n_reb} accounts >{A['sicr_dpd']} DPD kept out of Stage 2; each needs Board-approved rationale and evidence")
    n_cont = int((R["stage_reason"] == "Borrower-level Stage 3").sum())
    add("Staging", "Borrower-level Stage 3 applied (para 76)", True, f"{n_cont} performing loans pulled into Stage 3 by another loan of the same borrower")
    add("Staging", "ΔPD test is on, with documented thresholds (para 29-30)", bool(A["use_dpd_test"]),
        f"{A['pd_basis']} · {A['pd_mode']} · β={A['beta']} · α={A['alpha_pp']} pp. RBI sets no thresholds: yours must be documented and consistent")
    if use_opt:
        n_up = int(((R["prior_stage"] == 3) & (R["stage"] == 1)).sum())
        add("Staging", "Straight Stage 3 → Stage 1 upgrades have evidence (para 77)", n_up == 0,
            f"{n_up} loans: confirm all arrears are cleared and there is no SICR evidence")
        n_held = int(R["stage_reason"].str.contains("Restructured:|Bank probation", regex=True).sum())
        add("Staging", "Cure / probation holds applied", True, f"{n_held} loans held in a worse stage by restructuring or probation rules")
    s2 = R.loc[R["stage"] == 2, "outstanding"].sum() / max(tot_out, 1e-9) * 100
    add("Staging", "Stage 2 share is plausible (< 35%)", s2 < 35, f"{s2:.1f}% of exposure")
    w = float(scen["weight_pct"].sum())
    add("Parameters", "Scenario weights sum to 100%", abs(w - 100) < 0.01, f"{w:.1f}%")
    cum = ts_used[[f"y{t}" for t in YRS]].to_numpy(float)
    add("Parameters", "Lifetime curve year 1 equals the 12-month PD", bool(np.allclose(cum[:, 0], grade_pd * 100, atol=0.01)),
        "Stage 1 and Stage 2 should agree on year 1")
    add("Parameters", "Cumulative lifetime PD never falls and stays ≤ 100%",
        bool(np.all(np.diff(cum, axis=1) >= -1e-9) and cum.max() <= 100 + 1e-9), "Check the lifetime PD table")
    add("Parameters", "PD rises as rating worsens", bool(np.all(np.diff(grade_pd) >= 0)), "Check the PD grade table")
    add("Parameters", "PD floor is at least 0.03% (para 96)", A["pd_floor"] >= 0.0003 - 1e-12, f"{A['pd_floor'] * 100:.2f}%")
    low = [k for k, v in [("lgd_sec", .65), ("lgd_unsec", .70), ("lgd_special", .30)] if A[k] < v - 1e-9]
    add("Parameters", "LGD at or above the backstop (65 / 70 / 30%)", not low,
        "Lower LGD is only allowed with a reliable own-LGD model (para 97)" if low else "At or above backstop")
    s2l = R[(R["stage"] == 2) & (R["remaining_term_yrs"] >= 1)]
    add("Results", "Lifetime PD ≥ 12-month PD for Stage 2 loans", bool((s2l["pd_life_pct"] >= s2l["pd12_pct"] - 1e-9).all()),
        f"{len(s2l)} Stage 2 loans with 1+ year left")
    cov = R.groupby("stage").agg(p=("provision", "sum"), o=("outstanding", "sum"))
    cv = (cov["p"] / cov["o"].where(cov["o"] > 0, 1)).reindex([1, 2, 3])
    ok_cov = bool(cv.dropna().is_monotonic_increasing)
    add("Results", "Coverage rises from Stage 1 to 2 to 3", ok_cov, " · ".join(f"S{i}: {v * 100:.2f}%" for i, v in cv.items() if pd.notna(v)))
    fshare = tot_top / tot_prov * 100 if tot_prov else 0
    add("Results", "Floors add < 25% on top of the model", fshare < 25, f"{fshare:.1f}% of final provision is a floor top-up")
    add("Results", "Overlay is modest (|overlay| ≤ 25% of ECL)", abs(A["overlay"]) <= 25, f"{A['overlay']:+.1f}%")
    top10 = R.nlargest(10, "provision")["provision"].sum() / max(tot_prov, 1e-9) * 100
    add("Results", "Top 10 loans < 50% of provision", top10 < 50, f"{top10:.1f}%")
    add("Results", "No missing values in results", not R[["ecl_adj", "provision", "ead", "lgd"]].isna().any().any(), "ECL, EAD, LGD, provision")
    return pd.DataFrame(rows)

with tab_audit:
    st.markdown("Automated sanity checks a reviewer or auditor would start with: data quality, staging, parameters and results. "
                "They mirror the audit themes in Chapter V and Annex 3 but do **not** replace independent validation.")
    chk = build_checks()
    npass = int((chk["Status"] == "✅ Pass").sum())
    a1, a2 = st.columns(2)
    a1.metric("Checks passed", f"{npass} / {len(chk)}")
    a2.metric("Items to review", len(chk) - npass)
    st.dataframe(chk, hide_index=True, width="stretch", height=640)
    st.caption("Not automated here: model documentation, independent validation, back-testing, Board approvals, data lineage "
               "and the audit trail required by Chapter V and Annex 3.")


# ---- Guide ----------------------------------------------------------------------
with tab_guide:
    st.markdown("""
### How the engine works (one loan, five steps)
1. **Category** – every loan sits in one RBI product category (para 82, 91-92). That decides which floor applies.
2. **Stage** – *Stage 3* if NPA (overdue **more than** 90 days, out-of-order, credit-impaired flag) **and the same borrower's other loans follow** (para 76);
   *Stage 2* if any SICR trigger fires (DPD > 30, revolving over limit, **PD now vs PD at origination**, watchlist, covenant breach / collateral drop); otherwise *Stage 1*. The ΔPD test: relative `PD now ÷ PD origination > β` AND absolute `PD now − PD origination > α` (the AND stops tiny PDs from tripping on noise). RBI sets no β or α: document yours (para 29-30). Then the **upgrade rules** apply: a normal Stage 3 loan whose arrears are cleared goes straight to Stage 1 (Stage 2 if SICR evidence), para 77; restructured loans first serve a probation (para 78-80); you may add your own probation.
3. **PD · LGD · EAD**
   - **Two PDs.** *12-month PD* (grade table, floored at 0.03%, para 96) is used for Stage 1. *Lifetime PD* (a cumulative curve by grade and year; by default `1 − (1 − PD)^years`, or your own edited curve) is used for Stage 2. Stage 3 PD = 100%.
   - LGD: backstop (para 97-98): `secured% × 65% (30% for cash/gold/govt sec/LIC/KVP/NSC) + unsecured% × 70%`.
   - EAD: `outstanding + CCF × undrawn` (para 100). Collateral is *not* netted off.
4. **ECL** = Σ over years of `marginal PD × LGD × EAD × discount factor`, run in each scenario, then probability-weighted (para 47-49).
5. **Income** – Stage 1/2 interest accrues at EIR × gross carrying amount; Stage 3 interest is *not* accrued and is booked on a cash basis only (para 113-116).
6. **Floors** – `provision = max(model ECL, RBI floor)`: Stage 1/2 per category-stage bucket, Stage 3 per account (para 82, 90).

### Core and optional columns
**Core (15), needed for every run:** `loan_id`, `borrower_id` (Stage 3 is per borrower) · `category` (which floor applies) ·
`outstanding`, `undrawn_limit` (EAD) · `dpd` (Stage 3 and 2) · `rating_orig`, `rating_curr` (PD and the PD-change test) ·
`credit_impaired` (UTP / distress / concession flag, Stage 3) · `watchlist` (Stage 2) · `secured_pct`, `collateral_type` (LGD) ·
`remaining_term_yrs`, `eir_pct` (lifetime PD, discounting) · `years_in_stage3` (Stage 3 floor).
The app uses rating *grades*; the PD for each grade comes from the two PD tables in the sidebar.

| Optional column | If absent, the app assumes | Switches on |
|---|---|---|
| `is_revolving`, `days_over_limit` | not revolving, 0 days | revolving over-limit rules and out-of-order NPA |
| `amortising` | flat EAD (or tick the sidebar switch for linear) | repayment profile |
| `covenant_breach`, `collateral_decline` | False | Annex 1 qualitative triggers |
| `dpd_rebuttal` | False | documented rebuttal of the 30-DPD presumption |
| `prior_stage`, `months_regular`, `restructured` | stage 1, 24 months, not restructured | upgrade / probation rules, stage migration table |

### Data rules (checked on every edit or upload)
Columns depend on each other, so the generator builds them in order (borrower state, then grades and flags, then DPD, then limits and history) and the Data tab checks the same rules:
a loan with DPD 31-60 or on the watchlist is grade 6 or worse, DPD 61-90 grade 7 or worse, and a Stage 3 borrower grade 9 or 10 ·
a Stage 3 borrower has no undrawn limit, is not on the watchlist, and its loans share one *years in Stage 3*, which also bounds how high DPD can be (DPD ≤ 90 + days in Stage 3) ·
watchlist and UTP flag are borrower-level, so they agree across a borrower's loans · secured % above 0 needs a collateral type ·
(optional columns) over-limit days only on revolving facilities, no loan is both revolving and amortising, months of regular payment is 0 while past due.
"Apply rule fixes" removes the contradiction conservatively; it never invents collateral or good news.

### Simplifications you should know about
- **Both PDs** are lookup tables. The lifetime curve is derived from the 12-month PD unless you edit it; a real build needs default history, TTC→PIT calibration and macro links. Beyond year 10 the curve repeats its year-10 conditional PD.
- **Para 45 caution:** lifetime PD should not be a mechanical scaling of the 12-month PD. Untick "Derive lifetime curve" and calibrate the curve separately (for example, rising PD with age for good grades).
- **LGD** uses the regulatory backstop, allowed only if you cannot estimate LGD reliably (para 97). Document why.
- **CCF** is a single placeholder (40%) – take real values from the Standardised Approach Directions.
- **Floor base** = EAD (Stage 3: drawn balance). Check how your bank reads the base for off-balance items.
- **Scenarios** are PD/LGD multipliers, not a macro model.
- Revolving SICR uses days-over-limit *and* the DPD test (conservative reading of para 33).
- Extra SICR triggers from Annex 1: covenant breach, collateral value drop, and (optional) another loan of the same borrower being late. The 30-DPD presumption can be rebutted per loan, but every rebuttal needs documented evidence (para 34-36).
- Infographics and IFRS 9 summaries often differ from RBI's text (for example Stage 3 interest is on a cash basis under RBI, not on net amortised cost).

### Not covered here
POCI assets · investments and other financial instruments (para 83-86) · ADC / project-finance DCCO add-ons · small-MSME restructuring exemption (para 79) ·
Stage-2 rebuttal documentation (para 34-35) · transition arrangements and CET1 add-back · loss-allowance roll-forward (needs a prior-period snapshot) ·
trade/lease receivables provision matrix (Annex 2) · governance, validation, back-testing and audit trail (Chapter V, Annex 3).

### How often to run it
| Task | Frequency |
|---|---|
| DPD and NPA tagging | daily (day-end process) |
| Staging and ECL for management and early warning | monthly (good practice, not an RBI rule) |
| Official staging and ECL | every reporting date, i.e. at least quarterly (para 23, 26, 69) |
| Model validation / recalibration | by model risk tier (para 121), triggered by numerical indicators (para 131); annual is usual |

*Educational prototype built from the guideline text; not a validated model and not regulatory advice.*
""")
