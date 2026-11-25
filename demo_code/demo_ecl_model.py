"""
ECL-RET-MTG-001 – Retail Residential Mortgage ECL Model (DEMO / SYNTHETIC DATA)

Purpose : exercise the ECL Documentation Studio. Everything here is synthetic.
Regime  : RBI (Commercial Banks – Asset Classification, Provisioning and Income Recognition) Directions, 2026
          (Ind AS 109-aligned three-stage ECL; effective 1 April 2027)
Run     : python demo_ecl_model.py
"""
import numpy as np
import pandas as pd

SEED = 42
REFERENCE_DATE = "2026-03-31"
DEVELOPMENT_WINDOW = ("2016-04", "2026-03")
OOT_SHARE = 0.30                      # out-of-time sample share
N_ACCOUNTS = 20_000

# ---------------------------------------------------------------- policy parameters
DPD_STAGE3 = 90                       # default / NPA backstop (days past due)
DPD_STAGE2 = 30                       # rebuttable SICR presumption
SICR_RELATIVE_PD = 2.0                # lifetime PD ratio (current / origination) >= 2.0x -> Stage 2
SICR_ABSOLUTE_BPS = 150               # lifetime PD increase >= 150 bps -> Stage 2
CURE_PROBATION_DAYS = 180             # consecutive days of full payment before cure
PD_FLOOR_12M = 0.0003                 # 0.03% minimum 12-month PD
LGD_FLOOR = {"SEG-01": 0.10, "SEG-02": 0.15, "SEG-03": 0.25}
EXPECTED_LIFE_CAP_MONTHS = 360        # contractual maturity cap for term loans
SCENARIO_WEIGHTS = {"Upside": 0.15, "Baseline": 0.55, "Downside": 0.20, "Severe downside": 0.10}
SCENARIO_GDP_Y1 = {"Upside": 7.5, "Baseline": 6.5, "Downside": 4.2, "Severe downside": 1.5}
SCENARIO_UNEMP_Y1 = {"Upside": 4.2, "Baseline": 4.8, "Downside": 6.1, "Severe downside": 7.8}
PD_COEF = {"intercept": -4.125, "behavioural_score": -0.014, "max_dpd_l6m_30plus": 1.380, "current_ltv": 0.021}
MACRO_BETA = {"gdp_growth_lag1": -0.185, "unemployment_diff_lag2": 0.310, "hpi_yoy_lag1": -0.140}
PSI_AMBER, PSI_RED = 0.10, 0.25
GINI_GREEN, GINI_AMBER = 0.45, 0.35


# ---------------------------------------------------------------- data
def make_portfolio(n=N_ACCOUNTS, seed=SEED):
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "account_id": np.arange(n),
        "segment": rng.choice(["SEG-01", "SEG-02", "SEG-03"], n, p=[0.45, 0.35, 0.20]),
        "balance_cr": rng.lognormal(-5.0, 0.6, n),               # INR crore
        "eir": rng.normal(0.0875, 0.007, n).clip(0.07, 0.11),
        "ltv": rng.normal(62, 14, n).clip(20, 150),               # LTV capped at 150%
        "behavioural_score": rng.normal(680, 60, n).clip(300, 900),
        "dpd": rng.choice([0, 5, 20, 35, 60, 95, 140], n, p=[0.80, 0.06, 0.05, 0.04, 0.02, 0.02, 0.01]),
        "max_dpd_l6m": rng.choice([0, 15, 35, 65], n, p=[0.78, 0.10, 0.08, 0.04]),
        "remaining_months": rng.integers(12, EXPECTED_LIFE_CAP_MONTHS, n),
        "orig_pd": rng.beta(2, 60, n),
    })
    return df


# ---------------------------------------------------------------- PD, LGD, EAD
def pd_12m(df, z=0.0):
    """12-month point-in-time PD from a logistic model with a systematic factor z (macro satellite output)."""
    logit = (PD_COEF["intercept"] + PD_COEF["behavioural_score"] * (df["behavioural_score"] - 680) / 10
             + PD_COEF["max_dpd_l6m_30plus"] * (df["max_dpd_l6m"] >= 30)
             + PD_COEF["current_ltv"] * (df["ltv"].clip(upper=150) - 60) + z)
    return np.clip(1 / (1 + np.exp(-logit)), PD_FLOOR_12M, 1.0)


def lifetime_pd(pd12, months):
    """Constant-hazard extrapolation: cumulative PD = 1 - (1 - PD12)^(months/12)."""
    return 1 - (1 - pd12) ** (np.minimum(months, EXPECTED_LIFE_CAP_MONTHS) / 12)


def lgd(df, hpi_shock=0.0):
    base = 0.18 + 0.004 * (df["ltv"] - 60).clip(lower=0) - hpi_shock * 0.5
    floor = df["segment"].map(LGD_FLOOR)
    return np.maximum(base, floor).clip(upper=1.0)


def ead(df, months_ahead=12, ccf=0.0):
    """Amortising term loan: straight-line principal run-off + 3 months accrued interest."""
    remaining = (1 - months_ahead / df["remaining_months"]).clip(lower=0)
    return df["balance_cr"] * remaining * (1 + df["eir"] * 3 / 12)


# ---------------------------------------------------------------- staging
def assign_stage(df, pd12):
    lt = lifetime_pd(pd12, df["remaining_months"])
    lt_orig = lifetime_pd(df["orig_pd"], df["remaining_months"])
    stage = np.where(df["dpd"] >= DPD_STAGE3, 3,
             np.where((df["dpd"] >= DPD_STAGE2) | (lt / lt_orig >= SICR_RELATIVE_PD)
                      | ((lt - lt_orig) * 1e4 >= SICR_ABSOLUTE_BPS), 2, 1))
    return stage


# ---------------------------------------------------------------- ECL
def ecl_for_scenario(df, stage, z, hpi_shock):
    p12 = pd_12m(df, z)
    horizon = np.where(stage == 1, 12, df["remaining_months"].clip(upper=EXPECTED_LIFE_CAP_MONTHS))
    cum = lifetime_pd(p12, horizon)
    cum = np.where(stage == 3, 1.0, cum)
    df_ = 1 / (1 + df["eir"]) ** (horizon / 24)               # mid-horizon discount factor at EIR
    return cum * lgd(df, hpi_shock) * ead(df, horizon / 2) * df_


def probability_weighted_ecl(df):
    stage = assign_stage(df, pd_12m(df))
    z_by = {"Upside": -0.30, "Baseline": 0.0, "Downside": 0.45, "Severe downside": 0.90}
    hpi_by = {"Upside": 0.03, "Baseline": 0.0, "Downside": -0.05, "Severe downside": -0.12}
    per = {s: ecl_for_scenario(df, stage, z_by[s], hpi_by[s]) for s in SCENARIO_WEIGHTS}
    total = sum(SCENARIO_WEIGHTS[s] * per[s] for s in per)
    return stage, per, total


# ---------------------------------------------------------------- testing
def gini(y, score):
    order = np.argsort(score)
    y = np.asarray(y)[order]
    cum = np.cumsum(y) / y.sum()
    return float(1 - 2 * np.trapezoid(cum, dx=1 / len(y))) if hasattr(np, 'trapezoid') else float(1 - 2 * np.trapz(cum, dx=1 / len(y)))


def ks_stat(y, score):
    d = pd.DataFrame({"y": y, "s": score}).sort_values("s")
    return float(np.max(np.abs(np.cumsum(d.y) / d.y.sum() - np.cumsum(1 - d.y) / (1 - d.y).sum())))


def psi(expected, actual, bins=10):
    edges = np.quantile(expected, np.linspace(0, 1, bins + 1))
    e = np.histogram(expected, edges)[0] / len(expected) + 1e-6
    a = np.histogram(np.clip(actual, edges[0], edges[-1]), edges)[0] / len(actual) + 1e-6
    return float(np.sum((a - e) * np.log(a / e)))


def run():
    rng = np.random.default_rng(SEED)
    df = make_portfolio()
    stage, per, total = probability_weighted_ecl(df)
    df["stage"], df["ecl_cr"] = stage, total
    summary = df.groupby("stage").agg(exposure_cr=("balance_cr", "sum"), ecl_cr=("ecl_cr", "sum"))
    summary["coverage_pct"] = 100 * summary.ecl_cr / summary.exposure_cr
    print("Exposure and ECL by stage (INR crore)\n", summary.round(3))

    p = pd_12m(df)
    default_flag = rng.binomial(1, p)
    dev = df.sample(frac=1 - OOT_SHARE, random_state=SEED).index
    oot = df.index.difference(dev)
    print("\nGini  dev/OOT:", round(gini(default_flag[dev], p[dev]), 3), round(gini(default_flag[oot], p[oot]), 3))
    print("KS    dev/OOT:", round(ks_stat(default_flag[dev], p[dev]), 3), round(ks_stat(default_flag[oot], p[oot]), 3))
    print("PSI score dev vs OOT:", round(psi(df.loc[dev, "behavioural_score"], df.loc[oot, "behavioural_score"]), 4))

    base = sum(SCENARIO_WEIGHTS[s] * per[s].sum() for s in per)
    sev = per["Severe downside"].sum()
    print(f"\nWeighted ECL {base:.3f} cr | baseline-only {per['Baseline'].sum():.3f} cr | 100% severe {sev:.3f} cr ({100*(sev/base-1):+.1f}%)")
    return df


if __name__ == "__main__":
    run()
