# RBI ECL Model Lab: Prototype Documentation

**Status:** educational prototype built from the RBI Commercial Banks (Asset Classification, Provisioning and Income Recognition) Directions, 2026. It is **not a validated bank model** and not regulatory advice. Terms are explained in `ECL_App_Glossary.md`; operating steps are in `ECL_SOP_and_Learning_Guide.md`.

## 1. Purpose and scope

The prototype lets a developer or analyst see, end to end, how an expected-credit-loss (ECL) provision is built under the RBI Directions: data → staging → PD, LGD, EAD → scenarios → RBI floors → reporting. It also adds: IRB-style conversion (TTC to PiT), transition against old IRACP provisions, explainability, and planning tools.

Key dates the design follows (all from the Directions): framework in force **1 April 2027** (para 2); transition ECL computed on the **31 March 2027** position (para 107); first ECL reporting **30 June 2027** (para 150); previous-year comparatives mandatory from **31 March 2028** (optional earlier); loans outstanding at 31 March 2027 move to EIR by **31 March 2030** (para 21).

## 2. Architecture

One Streamlit file (`app.py`, about 2,500 lines), no database. Data lives in the browser session; nothing is stored.

| Layer | What it holds |
|---|---|
| 1 Regulatory tables | RBI floor rates (para 82), Stage 3 floor schedules, product categories, IRB/IRACP defaults |
| 2 Data | Synthetic generator, input cleaner (`sanitize`), consistency rules R01–R15 |
| 3 Engine | Staging, two PDs, LGD, EAD, scenario ECL, floors, interest income |
| 4 Analysis helpers | Customer table, trigger table, provision walk, SHAP, transition, capital schedule |
| 5 Screens | 15 tabs rendered from the results |
| 6 Sidebar and state | Assumptions, mode switches, data editor |

**Data flow:** loan book (15 core columns, 10 optional) → rules check → staging → PD/LGD/EAD → ECL per scenario → probability-weighted ECL → overlay → RBI floors → final provision → tabs and downloads.

**Libraries:** streamlit, pandas, numpy, altair, shap, plus Python's built-in `statistics` and `datetime`. Python 3.10+ (tested on 3.12). Minimum tested versions: streamlit 1.52, pandas 2.2.3, altair 5.5; latest tested: streamlit 1.66.1, pandas 3.0.2, numpy 2.4.4, altair 6.3.0, shap 0.54.1.

## 3. Inputs

**15 core columns** are required: loan_id, borrower_id, category, outstanding, undrawn_limit, dpd, rating_orig, rating_curr, credit_impaired, watchlist, years_in_stage3, secured_pct, collateral_type, remaining_term_yrs, eir_pct. **10 optional columns** switch on extra rules; if absent they take safe defaults (not revolving, flat EAD, no flags, last stage = 1, 24 months regular payment, IRACP provision estimated from proxy rates). Ratings are grades 1 to 10; PDs come from two sidebar tables. All amounts are in ₹ lakh. Column meanings are in the glossary.

**Data rules (R01–R15).** Columns depend on each other, for example grade 6 or worse when DPD is 31–60, a Stage 3 borrower has no undrawn limit and is not on the watchlist, DPD above 90 cannot exceed 90 plus days in Stage 3, borrower-level flags agree across a customer's loans. The Data tab lists violations; "Apply rule fixes" repairs them conservatively (never adds collateral or good news). The synthetic generator builds data in dependency order (borrower state → grades and flags → DPD → limits and history) and produces zero violations.

## 4. Methodology

### 4.1 Staging (paras 25–38, 76–81)
Two gates, then upgrade rules.
- **Gate 1, Stage 3:** DPD **more than** 90 (para 8), or revolving out-of-order (over limit 90+ days), or the UTP / credit-impaired flag. Decided **per borrower**: one bad loan pulls the customer's other loans into Stage 3 (para 76).
- **Gate 2, Stage 2 (any one trigger):** DPD > 30 (para 33, rebuttable with documented evidence, paras 34–36); revolving over limit ≥ 60 days; PD now vs PD at origination; watchlist; covenant breach or collateral drop (Annex 1); optional rating notches; optional "another loan of the borrower is late".
- **PD-change test:** relative `PD now ÷ PD origination > β` **and** absolute `PD now − PD origination > α` (defaults β 2.5, α 0.5 percentage points; RBI sets none, the bank must document its own, paras 29–30). Basis: lifetime PD (para 26) or 12-month PD (para 27).
- **Upgrades:** a normal Stage 3 loan with arrears cleared may go straight to Stage 1, or Stage 2 if SICR evidence exists (para 77). Restructured loans first stay in Stage 3, then Stage 2, for set periods (paras 78–80; 12 + 12 months are placeholders). An optional bank probation (default 0) is the bank's own policy.

### 4.2 Two PDs
- **12-month PD** (Stage 1): table ① by grade, floored at **0.03%** (para 96).
- **Lifetime PD** (Stage 2): cumulative curve by grade and year (table ②). Default: `1 − (1 − PD)^t`. Beyond year 10 the year-10 yearly chance repeats.
- Year by year: `marginal PD_t = survive to start of t × default in t`; lifetime PD = sum of marginals. Stage 3: PD = 100%.
- Check example (12-month 2%, then 3%, 4%): lifetime PD = 1 − 0.98 × 0.97 × 0.96 = **8.74%**, not 9%.

### 4.3 IRB mode: TTC to PiT (paras 47, 69–70, 72, 124)
The RBI text has no IRB-specific rules; these conversions are industry practice built on those paragraphs. Tables ① and ② are read as **through-the-cycle (TTC)**.
- **PiT PD** = Φ( (Φ⁻¹(TTC PD) − √ρ · z) / √(1 − ρ) ), z negative = downturn so PD rises. The cycle path is `z_t = z₁ · φ^(t−1)`, reverting to 0.
- **ρ** (asset correlation) from Basel formulas: corporate 0.12–0.24 falling with PD, residential mortgage 0.15, other retail 0.03–0.16 (or one fixed value).
- **Scenarios** carry z and a downturn weight; LGD = long-run + weight × (downturn − long-run). ECL must be unbiased (para 47), so downturn LGD is blended, not used outright.
- **Calibration tool:** enter yearly default rates; the app inverts the model to get z per year, estimates ρ (so z has unit variance), fits φ by AR(1), and suggests Base/Upside/Downside z-values. A diagnostic shows how far three scenarios understate the exact average PD.
- The PD-change test for staging stays on TTC grade PDs, so stage moves show borrower deterioration, not the cycle.

### 4.4 LGD, EAD, discounting
- **LGD (simple mode):** RBI backstop, 65% on the secured part, 70% unsecured, 30% for cash, gold, government securities, LIC, KVP, NSC (paras 97–98), used only if own LGD cannot be estimated. **IRB mode:** editable long-run and downturn table by collateral class.
- **EAD (para 100):** outstanding + CCF × undrawn (CCF 40% is a placeholder; take real values from the Standardised Approach Directions). Stage 3: outstanding only. Collateral is not netted off. Optional straight-line amortisation.
- **Discounting:** at each loan's EIR, mid-year convention (switchable).

### 4.5 Scenarios, overlay, floors
- **ECL** = sum over years of `marginal PD × LGD × EAD_t × discount factor`, per scenario, then probability-weighted (default Base 60 / Upside 20 / Downside 20). A manual **overlay** (% of ECL) is added.
- **RBI floors (para 82):** minimum % of EAD by category and stage (examples: corporate 0.40% Stage 1 / 5% Stage 2; housing 0.25% / 1.5%; unsecured retail 1% / 5%). Stage 3 floors rise with years in Stage 3 and differ for secured and unsecured parts (up to 100%).
- **Application (para 90):** Stage 1 and 2 floors are tested **per category and stage as a group**; any shortfall is spread over its loans pro rata to EAD. Stage 3 floors are tested **loan by loan**. Final provision = higher of model and floor. The floor base used is EAD (check your bank's reading for off-balance items).

### 4.6 Interest income (paras 113–116)
Stage 1 and 2 accrue interest at EIR × gross amount. Stage 3 accrues none (cash basis). The dashboard shows both.

### 4.7 Transition against IRACP (paras 106–112)
Adjustment = `max(0, ECL at 1 Apr 2027 on the 31 Mar 2027 book − IRACP provisions held)`, taken against opening earnings, not the P&L. IRACP provisions come from an optional data column or from editable **placeholder** proxy rates. Optional CET1 add-back: at most 4/5, 3/5, 2/5, 1/5 for FY2027-28 to FY2030-31, then none, net of tax (default 25.17%, placeholder). If ECL is below IRACP, no adjustment arises (para 110). Accounts that were NPA at 31 March 2027 stay NPA until rectified (para 103).

### 4.8 Explainability
- **Provision walk:** from a neutral 12-month loss (or regulatory-style EL in IRB mode) to the final provision, one change at a time; adds up exactly.
- **Staging triggers table and "in words":** every trigger against its threshold with headroom.
- **Input importance:** scrambles each input across loans and re-runs the model.
- **SHAP:** real `shap` KernelExplainer on a fast stand-in that explains **coverage %** for one loan held in isolation. Shapley additivity is exact. It is an **approximation**: outstanding, undrawn limit, category and collateral type fixed; no amortisation, borrower-level Stage 3 or cure rules; floor checked for the loan alone. The app always shows the actual engine figure beside it.

EOF
## 5. The 15 tabs in one line each

Dashboard (4 sub-tabs, category filter) · Data (editable, rules check) · Customer explorer · Account-level ECL · Loan explorer · Early warning · Sensitivity & calibration · IRB & TTC/PiT · Transition vs IRACP · Explainability · Timeline & data plan · Prudential floors · Annex-4 style tables · Audit checks · Guide & limits. Details of every table and chart: glossary.

## 6. Verification performed

| Area | What was checked | Result |
|---|---|---|
| Staging | Hand-built cases at the boundaries: DPD 30 / 31 / 90 / 91, relative vs absolute vs combined PD rule, upgrade and probation cases, restructured 5 / 15 / 30 months | All as expected |
| PD maths | 8.74% lifetime example; Stage 1 and Stage 2 ECL against hand calculation (exact match) | Pass |
| IRB maths | Basel ρ at PD 1% (corporate 0.1928, other retail 0.1216); average of PiT PD over a standard-normal cycle equals the TTC PD; vector code equals the scalar formula; provision falls as the cycle improves | Pass |
| Regression | Simple mode gives identical results to the version before IRB was added (3 books) | Identical |
| Invariants | Provision never below model ECL; Stage 1/2 group floors met; no missing values; bridge steps add up to the final provision | Pass on random books up to 5,000 loans |
| Data rules | 8 generated books violate nothing; about 970 deliberately broken cells repaired to zero violations | Pass |
| App | Automated runs of every tab and control (buttons, radios, filters, mode switches) on the latest and the minimum library versions | No errors |
| Charts | Rendered to images and inspected; defects found and fixed (missing reference lines, label overlap) | Fixed |
| SHAP | Additivity exact; stand-in compared with the engine across stages, differs by tenths of a point to a few points (Stage 2 largest) | Documented approximation |

**Not done:** clicking through the app in a live browser after the latest additions; testing on real bank data; independent model validation; back-testing; performance testing beyond 5,000 loans.

## 7. Assumptions and placeholders to replace

PD grade table and lifetime curve · IRB long-run and downturn LGD (35/50/10% and 45/60/15%) · CCF 40% · β 2.5 and α 0.5 pp · scenario weights and z-values · sample default-rate history · restructured probation 12 + 12 months · IRACP proxy rates (pre-2027 style) · tax rate 25.17% · default PD floor and LGD backstop follow the Directions but should be re-confirmed against the final text and amendments.

## 8. Known limitations (not covered)

POCI assets · investments and other instruments (paras 83–86) · ADC and project-finance DCCO add-ons · small-MSME restructuring exemption (para 79) · loss-allowance roll-forward and write-offs · trade and lease receivables provision matrix (Annex 2) · a macroeconomic model (scenarios are typed or calibrated from default history only) · SME size adjustment to ρ · off-balance-sheet detail beyond a single CCF · deferred-tax modelling · model governance, validation and audit trail (Chapter V, Annex 3) beyond automated sanity checks · multi-user data storage.

## 9. Install and run

```
pip install -r requirements.txt        # or requirements-lock.txt for exact versions
streamlit run app.py
```
Files: `app.py`, `requirements.txt`, `requirements-lock.txt`, this document, the SOP, the glossary. For Streamlit Community Cloud, put the files in a GitHub repository and point the app at `app.py`. No secrets are used. Do not upload real customer data to a public deployment.

## 10. RBI paragraph map

| Topic | Paragraphs |
|---|---|
| Scope, effective date | 2, 17 |
| SICR, 12-month PD proxy, documentation | 26, 27, 29, 30 |
| 30-DPD presumption and rebuttal | 33–36 |
| NPA definition, Stage 3 per borrower | 8, 76 |
| Upgrades and cure | 77–81 |
| Unbiased scenarios, forward-looking, cycle, mean reversion | 47, 69–72, 124 |
| EIR discounting | 50–54 |
| Floors | 82, 90–95 |
| PD floor, LGD backstop, EAD | 96–100 |
| Interest income | 113–116 |
| Transition and capital | 103–112 |
| Reporting dates | 149–150 |
| Overlays / post-model adjustments | 131 |

## 11. Evolution of the prototype

Core engine and dashboard → two PDs (12-month, lifetime) → NPA corrected to "more than 90 days" → PD-change staging and upgrade rules → core/optional columns → coherent data generator and rules → customer explorer, early warning, sensitivity → IRB (TTC/PiT) → transition vs IRACP, explainability, timeline planner → SHAP → documentation.
