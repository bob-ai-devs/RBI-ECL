# ECL Model Lab: Standard Operating Procedures and Learning Guide

For people new to ECL. Read `ECL_Prototype_Documentation.md` for how it works and `ECL_App_Glossary.md` for plain-language meanings. This is an educational prototype: use it to learn and to rehearse, not to book provisions.

## A. How to use this document

| Role | Does |
|---|---|
| Model developer | Sets assumptions, calibrates PD, LGD, scenarios; documents choices |
| Risk analyst | Loads data, runs the cycle, investigates customers |
| Reviewer | Challenges staging, thresholds, overlays, differences; signs the checklist |
| Approver | Accepts assumptions and the provision (in a real bank: the Board-approved governance route) |

Rule for every SOP: **write down what you changed, why, who approved, and the date.** RBI expects thresholds and judgements to be documented and applied consistently (paras 29–30).

## B. Procedures

### SOP-01 Start the app
1. Install Python 3.10+. In the project folder run `pip install -r requirements.txt`.
2. Run `streamlit run app.py`; the browser opens.
3. Check the sidebar title shows "ECL Model Lab" and the tabs load without a red error box.
*If it fails:* see SOP-12.

### SOP-02 Load and check data
1. Sidebar → **Random data generator** to practise, or **upload your own CSV**. Use **CSV template (15 core columns)** for the layout.
2. Leave **Use optional columns** off unless you have those fields. Missing optional columns take safe defaults.
3. Read the message under the uploader: it lists missing core columns or ignored optional ones.
4. Open **Data** → expand **Data consistency rules**. Target: all pass. If violations show, inspect the examples, correct the source data, or click **Apply rule fixes** (conservative) and note it.
5. Reconcile: loan count and total outstanding against the source system (download via **Download data**).
*Do not continue with unexplained violations.*

### SOP-03 Set assumptions
Work top to bottom in the sidebar and record each value.
1. **Parameters come from:** IRB-based (long-run PD converted to today's conditions) or Simple.
2. **1 Staging rules:** NPA line (> 90 DPD), 30-DPD backstop, PD-change test (basis, rule, β, α), watchlist, upgrade rules.
3. **2 PD, LGD, EAD:** PD floor (0.03%), ① 12-month PD by grade, ② lifetime curve (derive, or type your own), LGD, CCF.
4. **2b IRB conversion** (IRB mode): ρ source, mean reversion φ, long-run and downturn LGD.
5. **3 Scenarios, discounting, overlay:** weights sum to 100%; z-values and downturn weights (IRB) or multipliers (Simple); discounting on; overlay with written reason.
Check the **Audit checks** tab afterwards: every ⚠️ needs an explanation.

### SOP-04 Run and review a reporting-date ECL
1. Load the reporting-date book (quarter-end at minimum, para 26). Confirm assumptions (SOP-03).
2. **Dashboard → Overview:** headline numbers and the plain-language summary. Compare with last period.
3. **Dashboard → Staging & PD:** which triggers feed Stage 2; check DPD buckets and the PD scatter.
4. **Dashboard → Floors & scenarios:** where RBI floors bind. Large top-ups mean the model is below the regulator: investigate.
5. **Account-level ECL:** filter Stage 3 and Floor-binding loans; open the biggest ones.
6. **Annex-4 style tables:** copy tables A–E for the pack.
7. **Audit checks:** resolve or explain every item.
8. Download results (CSV) and the loan book; store with the assumptions record.

### SOP-05 Review staging and thresholds
1. **Sensitivity & calibration → section 2**, click **Run calibration grid**. Read the share of exposure in Stage 2 for each β and α.
2. Choose a cell that catches real deterioration without flooding Stage 2; compare with your orange-outlined current setting.
3. **Dashboard → Staging & PD → What pushes loans into Stage 2?** A trigger whose "only trigger" bar is near zero adds little.
4. **Audit checks → 30-DPD rebuttals** (needs the optional column): lists how many accounts over 30 DPD were kept out of Stage 2; each needs documented evidence (paras 34–36).
5. Record the final β, α, basis and rationale.

### SOP-06 Calibrate the credit cycle (IRB mode)
1. **IRB & TTC/PiT → section 2:** replace the sample table with your portfolio's yearly default rates (at least 5 years; longer is better).
2. Keep **Estimate ρ from the data** on. Check "Std dev of Z" is near 1.
3. Read the suggested Base / Upside / Downside z-values and the scenario-approximation note.
4. Click **Use these scenarios and φ in the model** (optionally also ρ).
5. Check **section 1**: weighted PiT ÷ TTC near 1.0 (the Audit tab flags values outside 0.7–1.5×).
6. Read **section 3** (bridge): each step should have an explanation you can say aloud.
7. Run **section 5** (cycle sweep) to see how the provision moves in a downturn.

EOF
### SOP-07 Transition against IRACP (31 March 2027 book)
1. Load the **31 March 2027** closing book. Use optional columns and fill `iracp_provision` with provisions actually held; otherwise edit the proxy rates and record that they are estimates.
2. **Transition vs IRACP:** read the five headline numbers: IRACP provisions, ECL, difference, transitional adjustment, coverage.
3. Read the waterfall (which stage drives the difference) and the class × stage table.
4. Review the largest increases and decreases; download the loan- and customer-level files.
5. **Capital block:** enter tax rate, CET1 and RWA (crore); decide whether the arrangement is used; read the FY schedule.
6. Confirm accounts that were NPA at 31 March 2027 stay NPA (para 103).
7. Prepare para 112 disclosure points: whether the arrangement is applied, and capital and leverage ratios against fully loaded ratios.
8. Keep two data snapshots: 31 March 2027 (transition) and 30 June 2027 (first reporting).

### SOP-08 Investigate a customer or loan
1. **Customer explorer:** filter by stage, pick the customer. Read "Why this stage?" and the monitoring line.
2. **Explainability → Loan or Customer scope:** read the provision walk, the "in words" text, and the trigger table (🔴 active, 🟢 clear, headroom).
3. Click **Run SHAP explanation** for a loan. Read bars as "this input adds or removes N percentage points of coverage". Remember it is an approximation shown beside the actual engine figure.
4. **What-if** (Customer explorer): change DPD, grade, flags and compare customer and portfolio provision. Data is not changed.
5. Write the conclusion: stage, main driver, what would change it.

### SOP-09 Monthly early-warning and sensitivity
1. **Early warning:** set "near" (default 20%). Review Stage 1 loans near Stage 2 and Stage 2 near NPA; note the extra provision if they all cross.
2. Move near-trigger Stage 1 loans to monthly review.
3. **Sensitivity → section 1:** run; the longest bars are the assumptions to defend first.
4. **Explainability → Which inputs does the model depend on?** Run; inputs near zero are candidates to drop.

### SOP-10 Evidence pack
Store together: assumptions record (SOP-03), data reconciliation, Audit checks result, Annex-4 style tables A–E, floors summary, transition files (if applicable), early-warning list, sensitivity and calibration outputs, reviewer sign-off. Record the app version and the library versions (`requirements-lock.txt`).

### SOP-11 Change control
Any change to thresholds, PD or LGD tables, scenarios, overlay, or parameter source needs: reason, before and after provision (use **Sensitivity**), reviewer and approver names, date. Overlays must be documented and governed (para 131). Re-run SOP-04 after every approved change.

### SOP-12 Troubleshooting
| Symptom | Likely cause | Action |
|---|---|---|
| Red error on start | Library versions too old | `pip install -r requirements.txt`; Streamlit ≥ 1.52 |
| Upload message says core columns missing | Headers differ | Use the template headers exactly |
| Many rule violations | Source data contradictions | Inspect examples; fix source; or Apply rule fixes |
| Stage 2 share looks very high | β, α too low, watchlist or notches on, ΔPD basis | SOP-05 grid |
| Provision far above model | Floors binding | Floors tab: which category and stage |
| IRB audit flag: PiT ÷ TTC off | Scenario z-values and weights do not average to long-run | SOP-06 |
| SHAP slow or odd | Very large background | Lower the slider; remember approximation |
| Edits vanish after toggling optional columns | Editor resets per mode | Save the CSV first |
| Numbers differ from before | Seed, mode, or assumptions changed | Compare assumptions record |

## C. Cadence

| When | What |
|---|---|
| Daily | DPD and NPA tagging in the source system (day-end process) |
| Monthly | Early warning, staging review, management ECL run (good practice, not an RBI rule) |
| Quarter-end (at minimum) | Official staging, ECL, floors, Annex-4 tables, audit checks (paras 23, 26, 69) |
| Annually, or on trigger | PD and LGD validation and recalibration, scenario refresh, threshold review (paras 121, 131) |

## D. Learning path (about 7 sessions)

| # | Topic | Do in the app | Check yourself |
|---|---|---|---|
| 1 | Why ECL; the formula | Read glossary part 1. Explainability → worked example | Why is lifetime PD not the sum of yearly PDs? (A borrower who defaults in year 1 cannot default again; use survival.) |
| 2 | Stages | Customer explorer: one loan per stage; edit DPD in the what-if | Which gate decides Stage 3, and why per borrower? (Para 76.) |
| 3 | The two PDs | Sidebar tables ①②; Dashboard PD curves; Loan explorer | Which PD does Stage 1 use? Stage 2? |
| 4 | LGD, EAD, floors | Account-level ECL; Floors tab | When does the RBI floor decide the answer? (Model below the minimum; Stage 1/2 tested per category-stage group.) |
| 5 | Scenarios and the cycle | IRB tab sections 1, 2, 5 | Why does provision rise in a downturn even if loans do not change? |
| 6 | Transition | Transition tab with the generator's optional data | What is the transitional adjustment? (max(0, ECL − IRACP provisions), against opening earnings.) |
| 7 | Explaining results | Explainability: walk, triggers, SHAP, input importance | Why is SHAP an approximation here? |

**Exercises.** (a) Raise stress, regenerate, and note how Stage 2, Stage 3 and coverage change. (b) Set Downside weight to 0%; predict the total ECL direction, then check. (c) Make all PDs tiny; explain why floors take over. (d) Give a bad loan 4.5 years in Stage 3 and watch the floor jump. (e) Enter a harsher default history and watch z, φ and the bridge change.

## E. Review sign-off template

| Check | Done | By / date |
|---|---|---|
| Data reconciled to source; rules pass or explained | ☐ | |
| Assumptions recorded; thresholds documented (β, α, basis) | ☐ | |
| Overlay reason documented | ☐ | |
| Audit checks: all Pass or explained | ☐ | |
| Floors reviewed; large top-ups explained | ☐ | |
| Stage movements and rebuttals reviewed | ☐ | |
| Transition files produced (if applicable) | ☐ | |
| Evidence pack stored with versions | ☐ | |
| Reviewer and approver sign-off | ☐ | |

*Educational prototype: not a validated bank model, not regulatory advice. Confirm every requirement against the official RBI Directions and any amendments.*
