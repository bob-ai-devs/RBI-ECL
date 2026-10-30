# ECL Model Lab: plain-language glossary

Written for readers who do not know banking or modelling terms. Four parts: **1** words and units, **2** tabs and headings, **3** tables and their columns, **4** charts and their labels, **5** functions.

## 1. Words and units

| Term | Simple meaning |
|---|---|
| ₹ lakh / ₹ crore | 1 lakh = 1,00,000 rupees. 1 crore = 100 lakh. The app shows money in lakh unless it says crore. |
| Provision | Money the bank sets aside today because some loans will probably not be repaid in full. |
| ECL (expected credit loss) | The bank's best estimate of the loss it will suffer on a loan: chance of default × share lost × amount owed. |
| PD | Probability of Default: how likely the borrower is to stop paying. |
| LGD | Loss Given Default: if they do stop, the share of the money the bank loses after selling any security. |
| EAD | Exposure at Default: how much the borrower will owe at that moment (balance plus part of any unused limit). |
| 12-month PD / lifetime PD | Chance of default within the next year / at any time before the loan ends. |
| Stage 1, 2, 3 | Stage 1 = healthy. Stage 2 = risk has clearly risen. Stage 3 = bad loan (NPA). Higher stage = bigger provision. |
| DPD | Days past due: how many days a payment is late. |
| NPA | Non-performing asset: a loan more than 90 days overdue (or otherwise impaired). |
| SICR | Significant increase in credit risk: the reason a loan moves to Stage 2. |
| Coverage | Provision ÷ amount outstanding, as a percentage. How much of the loan is "covered". |
| Floor | RBI's minimum provision. The bank cannot go below it. |
| TTC / PiT | Through-the-cycle = average over good and bad years. Point-in-time = today's conditions. |
| z (credit-cycle index) | One number for how good or bad the economy is: 0 = average, negative = downturn. |
| IRACP | The old RBI rules for classifying loans and provisioning, which ECL replaces. |
| CET1 | The bank's highest-quality capital. |
| SHAP | A fair way to split a result between its causes (see the Explainability tab). |
| Overlay | A manual top-up for risks the model cannot see. |
| Scenario | One possible future (Base, Upside, Downside), each with a weight. |
| EIR | Effective interest rate: the loan's true yearly rate, used to discount future losses. |

## 2. Tabs and what each heading means

| Tab | What it is for |
|---|---|
| 📊 Dashboard | The summary. Has four sub-tabs: **Overview** (headline numbers, stage mix, waterfall), **Concentration** (where provisions sit by category and customer), **Staging & PD** (why loans are in Stage 2, risk curves), **Floors & scenarios** (model vs RBI minimum, future scenarios). A category filter narrows everything. |
| 🗂️ Data (editable) | The loan list. You can edit it. A rules check below it flags contradictions (for example a loan 120 days late with a top rating). |
| 👤 Customer explorer | Everything about one customer: its loans, why it is in its stage, and a what-if. |
| 🧮 Account-level ECL | Every loan, step by step, to its final provision. |
| 🔍 Loan explorer | One loan year by year: PD, loss amount, discounting. |
| 🚨 Early warning | Loans close to moving to a worse stage, and what that would cost. |
| 🎛️ Sensitivity & calibration | **1** Which assumption moves the total provision most. **2** A grid for choosing the thresholds (β, α) that decide Stage 2. |
| 🏛️ IRB & TTC/PiT | **1** Long-run vs today's PD by grade. **2** Estimating the credit cycle from past default rates. **3** Walk from a regulatory-style loss to the final provision. **4** The loss-share (LGD) views. **5** Provision across good and bad economies. |
| 🔁 Transition vs IRACP | Compares the new ECL provision to what the old rules required, and the capital effect. |
| 🧭 Explainability | **Provision walk**, **In words**, **Staging triggers**, **SHAP**, **Which inputs the model depends on**, and a worked PD example. |
| 🗓️ Timeline & data plan | RBI dates, how to split history into build / validate / test periods, and the data to request. |
| 🧱 Prudential floors | Model result against RBI's minimum, by category and stage. |
| 📑 Annex-4 style tables | Simplified versions of the tables banks must publish (A to E). |
| 🕵️ Audit checks | Automatic sanity checks a reviewer would run. |
| 📖 Guide & limits | Built-in explanation and what is not covered. |

Sidebar sections: **Parameters come from** (simple tables vs IRB-based), **Random data generator**, **1 Staging rules**, **2 PD, LGD, EAD**, **2b IRB conversion**, **3 Scenarios, discounting, overlay**.

## 3. Tables and columns

### 3.1 The loan book (Data tab; this is what you load)
The first 15 are **core** (needed). The last 10 are **optional** (safe defaults are used if missing).

| Column | Meaning |
|---|---|
| loan_id | Unique loan number. |
| borrower_id | Customer number. Loans with the same number belong to one customer. |
| category | RBI product type (housing, gold, corporate…). Decides which RBI minimum applies. |
| outstanding | Amount owed now (₹ lakh). |
| undrawn_limit | Sanctioned but unused credit that could still be drawn (₹ lakh). |
| dpd | Days the payment is late. 0 = on time. |
| rating_orig | Credit grade when the loan was given (1 = best, 10 = worst). |
| rating_curr | Credit grade today. |
| credit_impaired | Yes if the borrower is in distress or got concessions, even if not 90 days late (called UTP). |
| watchlist | Yes if the bank is watching this customer closely. |
| years_in_stage3 | How long the customer has been a bad loan. Longer = higher RBI minimum. |
| secured_pct | Share of the loan backed by security (0–100). |
| collateral_type | What backs it: None, Property, Vehicle, Receivables/Stock, or Cash/gold/govt securities. |
| remaining_term_yrs | Years left until the loan ends. |
| eir_pct | The loan's true yearly interest rate (%). |
| *is_revolving* | Yes for overdraft/credit-card style limits that can be reused. |
| *amortising* | Yes if the balance shrinks steadily over time. |
| *days_over_limit* | Days the customer has been above the sanctioned limit. |
| *covenant_breach* | Yes if the customer broke a loan condition. |
| *collateral_decline* | Yes if the security has lost value. |
| *dpd_rebuttal* | Yes if the bank documented why a 30-day delay should not count as higher risk. |
| *prior_stage* | Stage at the last reporting date. |
| *restructured* | Yes if the loan terms were changed because of stress. |
| *months_regular* | Months of on-time payment since arrears ended. |
| *iracp_provision* | Provision held under the old rules at 31 March 2027 (₹ lakh). |

### 3.2 Result columns (Account-level ECL tab; one row per loan, created by the app)

| Column | Meaning |
|---|---|
| stage / stage_label | 1, 2 or 3 ("Stage 1"…). |
| stage_reason | Why: for example "DPD>30", "Watchlist", "NPA (DPD>90)", "Borrower-level Stage 3". |
| prior_stage, stage_move | Stage last time, and whether the loan Improved, Worsened or is Unchanged. |
| pd_orig_pct, pd_now_pct, pd_ratio | PD when the loan was given, PD today, and today ÷ then. A big ratio means it got much riskier. |
| ead | Amount at default: outstanding + part of undrawn limit (Stage 3: outstanding only). |
| lgd | Share lost if it defaults (probability-weighted). lgd_lr / lgd_dt = long-run / downturn versions. |
| pd12_ttc_pct | 12-month PD on a long-run-average basis. |
| pd12_pct, pd_life_pct | 12-month and lifetime PD actually used (today's conditions in IRB mode). |
| pd_used_pct, pd_type | The PD that drives this loan's provision, and whether it is "12-month", "Lifetime" or "Default (100%)". |
| ecl_Base, ecl_Upside, ecl_Downside | Expected loss if that future happens. |
| ecl_model | Probability-weighted average of the scenarios. |
| ecl_adj | ecl_model after any manual overlay. |
| floor_pct, floor_amt | RBI minimum as a % of EAD, and in rupees. |
| s3_bucket | How long in Stage 3 (0-1 yr, 1-2 yrs…) for the Stage 3 minimum. |
| topup | Extra provision added because the model came in below the RBI minimum. |
| provision | Final provision = ecl_adj + topup. |
| binding | "Floor" if RBI's minimum decided the number, "Model" if the model did. |
| interest_annual / accrued / suspended | Yearly interest; the part the bank may book (Stage 1–2); the part it may not (Stage 3, cash basis). |
| trg_dpd, trg_rev, trg_pd, trg_notch, trg_watch, trg_qual, trg_cross | True/false: which Stage 2 triggers fired (late, over limit, PD jump, grade drop, watchlist, covenant/collateral, another loan late). |
| dpd_bucket | Lateness band: Current, 1-30, 31-60, 61-90, >90. |

### 3.3 Other tables, by tab

**Sidebar inputs**
| Table | Columns |
|---|---|
| ① 12-month PD by grade | grade (1–10); pd_pct = yearly default chance for that grade. |
| ② Lifetime PD curve | grade; y1…y10 = cumulative chance of default by year 1…10. |
| Scenarios (simple) | scenario; weight_pct = probability; pd_mult, lgd_mult = how much PD and LGD are scaled in that future. |
| Scenarios (IRB) | scenario; weight_pct; z = state of the economy over the next year; lgd_dt_w = how far loss share moves toward its downturn value (0–1). |
| LGD table (IRB) | collateral class; long-run % = typical loss share; downturn % = loss share in a bad economy. |

**Customer explorer**: one row per loan: Stage, Why, Outstanding, Undrawn, EAD, DPD, Grade then/now, PD used, LGD, Model ECL, Floor top-up, Provision, Binding. *What-if table:* loan_id, stage before/after, provision before/after, change.

**Early warning**: loan_id, borrower_id, category, Stage now, Could move to, Why it is close, DPD, PD ratio, Outstanding, Provision now, **Extra if it moves** (the added provision).

**Sensitivity & calibration**: *Sensitivity* = parameter, setting, provision, Change (₹ lakh), Change %. *Grid* = beta (relative multiple), alpha (percentage-point rise), Stage 2 share of exposure (%), Loans flagged only by ΔPD.

**IRB & TTC/PiT**: *ρ table* (asset correlation: how strongly loans move together with the economy) by exposure class and grade. *Default history* = year, default_rate_pct. *Suggested scenarios* = scenario, weight_pct, z, lgd_dt_w. *Bridge* = Step, Amount (₹ lakh), % of final provision. *Cycle sweep* = z, provision, PiT ÷ TTC PD.

**Transition vs IRACP**: *Proxy rates* = category, standard-asset provision % (old-rule percentage for healthy loans); NPA age, secured %, unsecured % (old-rule percentages for bad loans). *Class × stage* = iracp_class (Standard/NPA under old rules), stage_label, loans, outstanding, IRACP, ECL, difference. *Largest increases/decreases* = loan_id, borrower_id, category, stage, outstanding, **iracp** (old-rule provision), **provision** (ECL), **delta** (ECL minus old). *Capital schedule* = financial year; max add-back fraction (share of the hit RBI lets the bank add back to capital); add-back to CET1; CET1 deduction (the part that does hit capital); CET1 ratio impact (bps; 100 bps = 1%); CET1 ratio after (%).

**Explainability**: *Provision walk* = Step, Amount, % of final provision. *Staging triggers* = Trigger, Current value, Threshold, Status (🔴 active / 🟢 clear), Headroom (distance to the threshold). *SHAP table* = Input, Value for this loan, SHAP value (percentage points of coverage it adds or removes). *Input importance* = input, provision shift % (average change in a loan's provision when that input is scrambled), loans changing stage %, total provision change. *Worked example* = year, conditional PD (chance of default that year if still alive), survive to year-end, marginal PD (chance of defaulting in that year), cumulative PD, ECL in year.

**Timeline & data plan**: *Milestones* = date, milestone, what happens, days from today. *Split plan* = segment (Development / Validation / Out-of-time test / Latest scoring), from, to, use, months. *Matured outcomes* = horizon (months), last date with a known outcome, usable share of the window. *Extracts* = extract, as-of / coverage, purpose.

**Prudential floors**: *Summary* = category, Stage, loans, Exposure (EAD), Model ECL, Floor required, Top-up, Final provision, Coverage %. *Rates* = category, Stage 1 %, Stage 2 %, Stage 3 table (A, B, C or UR). *Stage 3 table*: rows = years in Stage 3; cell "25/40" = % for the secured part / the unsecured part.

**Annex-4 style tables**: **A** gross amount and provision by lateness band (rows) and stage (columns), ending in net amount. **B** same by category, with Coverage %. **C** Item / Value: the settings used. **D** interest by stage: gross amount, interest accrued, not accrued, basis. **E** migration: rows = stage last time, columns = stage now (exposure and loan counts).

**Data rules / Audit**: *Data rules* = Rule (R01…R15), What it checks, Violations (count), Examples (loan ids). *Audit* = Area, Check, Status (✅ Pass / ⚠️ Review), Detail.

## 4. Charts and what their labels mean

**Colour rules used everywhere.** Stages: green = Stage 1, amber = Stage 2, red = Stage 3. Waterfalls: dark navy = a total, orange = a step that *adds* provision, green = a step that *removes* it. A waterfall always adds up exactly to its last bar.

| Chart (tab) | What you are looking at |
|---|---|
| Exposure by stage (Dashboard) | Donut. Each slice = share of money owed that sits in that stage. |
| Provision and coverage by stage | Bars = provision (₹ lakh). Number above a bar = coverage % (provision ÷ amount owed). |
| From model ECL to final provision | Waterfall: ECL of Stage 1, 2, 3 → manual Overlay → Floor top-up (RBI minimum) → Final provision. |
| Provision by product category | Bars = provision per category, split by stage colour. |
| Coverage ratio by category | Bars = provision ÷ exposure (%). Longer = more of that category is provided for. |
| Coverage heatmap: category × stage | Each cell = coverage % for that category and stage. Darker = higher. Blank = no loans. |
| Top N customers by provision | Bars = the customers with the largest provisions; colour = their worst stage. |
| What pushes loans into Stage 2? | For each trigger: blue = loans it flags; orange = loans for which it is the *only* trigger. A tiny orange bar means the trigger adds little. |
| Exposure by DPD bucket and stage | Bars = money owed, grouped by how late the loan is (Current, 1-30…>90 days), coloured by stage. A Stage 2 bar under "Current" means risk, not lateness, moved it. |
| PD now vs PD at origination | Each dot = a loan. Across = PD when given; up = PD today (both log scale). Solid line = no change; dashed line = "β times riskier". Dots above the dashed line got much riskier. |
| Two PDs: cumulative default curve by grade | Each line = a rating grade. Across = years from today; up = cumulative chance of default (%). Year 1 = the 12-month PD; the whole line = the lifetime PD. |
| Average PD by stage: 12-month vs lifetime | Green = 12-month PD, amber = lifetime PD, averaged by loan size (EAD-weighted). |
| Model ECL vs final provision | Blue = what the model says; orange = after the RBI minimum. Orange longer = the model was below the regulator. |
| Scenario view | Expected loss in each future (Base, Upside, Downside) and the Weighted average (orange). |
| Exposure by loan / How each loan's provision is built (Customer) | Money owed per loan; provision per loan split into Model ECL and Floor top-up. |
| PV of ECL by year (Loan explorer) | Bars = loss expected in each future year, in today's money (PV = present value). Dark = counted at the loan's current stage; pale = counted only if it were Stage 2. |
| Extra provision if they migrate (Early warning) | Bars = extra provision if near-trigger loans cross the line, by category; amber = to Stage 2, red = to Stage 3. |
| Change in total provision (Sensitivity) | Tornado. Each assumption has a green (Low) and red (High) bar: how far the total moves. Longest bar = biggest driver. |
| β × α heatmap (Calibration) | Share of money in Stage 2 for each pair of thresholds: β = how many times riskier, α = how many percentage points riskier. Orange outline = your current setting. |
| 12-month PD (%, log scale) by rating grade (IRB) | Grey dashed = long-run (TTC) PD. Blue/green/red = today's-conditions (PiT) PD in the Base/Upside/Downside; dark = probability-weighted. Log scale: equal steps are equal *ratios*. |
| Observed default rate / Implied credit-cycle index | Bars = the yearly default rate you entered (dashed orange = average). Line = the economy index z derived from it; 0 = average year, below 0 = downturn. |
| Regulatory EL → ECL bridge | Starts from a regulatory-style loss and adds each conversion (cycle, loss share, lifetime, discounting, scenarios, overlay, floor) up to the final provision. |
| LGD: backstop, long-run, downturn, expected | Grouped bars of loss share (%) per collateral class: RBI's default, typical, bad-economy, and the one the ECL uses. |
| Provision vs cycle / PiT ÷ TTC 12-month PD | Across = economy index z (left = downturn). Up = total provision, or how many times today's PD exceeds the long-run PD. Both rise steeply in a downturn. |
| IRACP vs ECL by category / Loan-level difference | Blue = old-rule provision, orange = ECL. The histogram = how many loans see a given change (as % of their balance). |
| Add-back to CET1 vs CET1 deduction | Green = part of the transition hit the bank may add back to capital; red = part that reduces capital, for each financial year. |
| Provision walk (Explainability) | Waterfall from a neutral 12-month expected loss to the final provision, one change at a time. |
| SHAP waterfall | Starts at the portfolio's average coverage %. Each bar is one input: orange raises this loan's coverage, green lowers it. Ends at this loan's coverage. |
| Input importance | Bars = how much loan provisions move when that input is scrambled. Near zero = the model barely uses it. |
| Milestone timeline / Split Gantt (Timeline) | Dots = RBI dates. Bars = periods: blue development, amber validation, red out-of-time test, pale blue latest loans (outcomes not yet known). |

Axis words: **₹ L** = lakh; **bps** = basis points (1/100 of 1%); **pp** = percentage points; **log scale** = each gridline is a multiple of the previous one.

## 5. Functions (what each piece of code does)

**Data**: `generate_loans` builds a realistic fake loan book. `sanitize` cleans any table so the engine can use it. `core_template` makes a blank CSV with the 15 core columns. `rule_masks`, `check_rules`, `apply_rules` find and fix contradictory data (R01–R15). `_s3_like` flags customers who are Stage 3.

**Risk engine**: `stage_loans` decides Stage 1, 2 or 3 and applies upgrade/probation rules. `cum_pd` gives cumulative default chance over a period. `derived_curve` and `hazards_from_curve` turn a 12-month PD into a lifetime PD curve and back into yearly chances. `_phi`, `_phi_inv`, `rho_table`, `pit_tables`, `irb_lgd` convert long-run PD and LGD into today's-conditions versions. `ensure_scen` fills missing scenario columns. `ecl_terms`, `ecl_from_terms`, `scenario_ecl` compute expected loss year by year per scenario. `run_engine` runs everything for the whole book, including floors. `floor_summary` totals model vs RBI minimum. `ecl_if_stage` asks "what if this loan were in Stage X?". `fmt_amt` prints money as ₹ L or ₹ Cr.

**Customers and explanations**: `borrower_table` groups loans by customer. `explain_borrower`, `explain_loan`, `monitoring_text` write plain-language reasons and review advice. `trigger_table` lists every staging trigger against its threshold. `provision_walk` (and `irb_bridge`) walk from a neutral loss to the final provision. `perm_importance` ranks inputs by scrambling them. `shap_feature_list`, `_predict_coverage`, `_shap_instance_vec` prepare the SHAP explanation.

**Transition and planning**: `iracp_proxy` estimates old-rule provisions. `transition_frame` compares them with ECL loan by loan. `capital_schedule` phases the capital add-back. `pd_worked_example` shows 12-month vs lifetime PD arithmetic. `split_plan` makes the development/validation/test dates.

**Screens (render_…)**: `render_dashboard`, `render_customer`, `render_early_warning`, `render_sensitivity`, `render_irb`, `render_transition`, `render_explain`, `render_timeline`, `render_shap` draw the tabs of the same names. `_walk_chart` draws any waterfall. `_apply_cal` copies calibrated scenarios into the model. `build_checks` makes the Audit table.

*This is an educational prototype, not a validated bank model.*
