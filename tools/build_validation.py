"""
Builds the strict ECL Model *Validation* Document templates (brief + advanced).

    python tools/build_validation.py

The structure mirrors the Development Document (same cell conventions) and is aligned to
Chapter III (ECL-based provisioning) of the RBI (Commercial Banks - Asset Classification,
Provisioning and Income Recognition) Directions, 2026 (issued 27 April 2026, effective 1 April 2027).
Section numbers are generated automatically, so brief and advanced documents number cleanly.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from docx_to_template import mkcell, stats  # noqa: E402

RATING = "Satisfactory / Satisfactory with recommendations / Needs improvement / Unsatisfactory"

# ---------------------------------------------------------------- DSL helpers
def TBL(cols, rows, hints=None, brief_rows=None, check=None, adv=False):
    return dict(t="table", cols=cols, rows=rows, hints=hints or [""] * len(cols),
                brief_rows=brief_rows, check=check, adv=adv)


def PARA(label, hint, adv=False):
    return dict(t="para", label=label, text=hint, adv=adv)


def LIST(items, adv=False):
    return dict(t="list", items=items, adv=adv)


def NOTE(text, adv=False):
    return dict(t="note", text=text, adv=adv)


def G(title, blocks, brief=True, num=True):
    return dict(title=title, blocks=blocks, brief=brief, num=num)


def S(title, goal, groups, brief=True, appendix=False):
    return dict(title=title, goal=goal, groups=groups, brief=brief, appendix=appendix)


def build_table(b, depth):
    cols, hints = b["cols"], b["hints"]
    rows = b["rows"]
    if depth == "brief" and b["brief_rows"]:
        rows = rows[: b["brief_rows"]]
    out = []
    for r in rows:
        cells = []
        for ci in range(len(cols)):
            v = r[ci] if ci < len(r) else None
            if b["check"] and cols[ci] == b["check"]:
                cells.append({"k": "chk", "v": "", "f": 1, "lbl": ""})
            elif v is None:
                cells.append({"v": "", "h": hints[ci], "f": 1})
            else:
                cells.append(mkcell(v, static=bool(b["check"])))
        out.append(cells)
    proto = [h if (cols[i] != b["check"]) else "" for i, h in enumerate(hints)]
    return {"t": "table", "cols": cols, "rows": out, "proto": proto}


def build_block(b, depth):
    t = b["t"]
    if t == "table":
        return build_table(b, depth)
    if t == "para":
        return {"t": "para", "label": b["label"], "c": {"v": "", "h": b["text"], "f": 1}}
    if t == "note":
        return {"t": "note", "text": b["text"]}
    if t == "list":
        return {"t": "list", "items": [{"label": l, "c": {"v": "", "h": h, "f": 1}} for l, h in b["items"]]}
    raise ValueError(t)


# ---------------------------------------------------------------- content
ASSESS = ["", "", "Evidence reviewed and analysis performed", "Validator assessment and challenge", RATING]
TEST_COLS = ["Test", "Expectation", "Evidence and analysis", "Assessment", "Rating"]

SECTIONS = [
    S("Validation Control and Sign-Off",
      "Identify the model, the validation, the validators and the approval status in one place so MRM, audit and the supervisor can trace the work. Complete once per report.",
      [
          G("Validation metadata", [TBL(
              ["Metadata field", "Entry"],
              [
                  ("Validation ID and title", "[e.g., VAL-ECL-RET-MTG-2027-01 – Independent validation of Retail Residential Mortgage ECL Model]"),
                  ("Model ID and name (as in the development document)", "[e.g., ECL-RET-MTG-001 – Retail Residential Mortgage ECL Model]"),
                  ("Accounting and regulatory regime", "[RBI ECL Directions 2026 (Ind AS 109-aligned) / other, if group-consolidated]"),
                  ("Validation type", "[Initial / Periodic annual / Ad hoc after material change / Pre-transition (before 1 April 2027)]"),
                  ("Validation scope", "[Governance / conceptual soundness / data / implementation / outcomes analysis / forward-looking]"),
                  ("Model tier / materiality", "[Tier 1 (high) / Tier 2 (medium) / Tier 3 (low)] – rationale: [text]"),
                  ("Model owner (business)", "[Name, title, department]"),
                  ("Lead developer(s)", "[Name(s), team]"),
                  ("Independent validator(s) and team", "[Name(s), team, reporting line]"),
                  ("Independence confirmation", "[Confirm that validators did not develop, own or use the model and report outside the model owner's line]"),
                  ("Development document version and date reviewed", "[v1.0 – DD-MMM-YYYY]"),
                  ("Reference (data) date and validation window", "[DD-MMM-YYYY]; [Mon-YYYY to Mon-YYYY]"),
                  ("Validation report version and date", "[v1.0 – DD-MMM-YYYY]"),
                  ("Overall validation opinion", "[" + RATING + "]"),
              ])], num=False),
          G("Version history and approvals", [TBL(
              ["Version", "Date", "Author / approver", "Role", "Change summary and sign-off status"],
              [
                  ("v0.1", "[DD/MM/YYYY]", "[Validator]", "Lead validator", "Initial draft for validation-team review"),
                  ("v0.9", "[DD/MM/YYYY]", "[Head of validation]", "Head of validation", "Reviewed; shared with model owner for factual accuracy"),
                  ("v1.0", "[DD/MM/YYYY]", "[Head of validation]", "Head of validation", "Issued to model owner and ECL steering committee"),
                  ("[v1.x]", "[DD/MM/YYYY]", "[Approving body]", "[ECL steering committee / Board-approved committee]", "[Noting reference, minutes ID]"),
              ], brief_rows=3)], num=False),
      ]),

    S("Executive Summary and Overall Opinion",
      "Give senior management, the ECL steering committee and the supervisor a one-page view of the validation scope, the rating by area, the key findings and the opinion on fitness for use.",
      [
          G("Purpose, scope and materials reviewed", [
              {"t": "para_static", "label": "", "text": "This Model Validation Document (MVD) records the independent validation of [Model name] ([Model ID]), used to estimate Expected Credit Loss (ECL) under the Reserve Bank of India (Commercial Banks – Asset Classification, Provisioning and Income Recognition) Directions, 2026 (issued 27 April 2026; effective 1 April 2027). The validation covers [scope] and was performed by [validation team] between [start date] and [end date]."},
              TBL(["Item reviewed", "Version / reference", "Provided by", "Date", "Limitations or gaps"],
                  [("Model development document",), ("Model code and repository snapshot",), ("Data extracts and lineage evidence",),
                   ("Scenario and macro forecast files",), ("Approvals, minutes and policies",)],
                  hints=["", "Version, ID or link", "Name / team", "DD-MMM-YYYY", "Gaps in material or access"], brief_rows=3)]),
          G("Validation approach and rating by area", [
              TBL(["Validation area", "Procedures performed", "Rating", "Key observation"],
                  [("Governance and regulatory alignment",), ("Conceptual soundness and methodology",), ("Data and inputs",),
                   ("Implementation and code",), ("Outcomes analysis",), ("Forward-looking and scenarios",),
                   ("Floors, transition and overlays",), ("Monitoring, model risk and use",)],
                  hints=["", "Procedures performed (tests, re-performance, review of evidence)", RATING, "Most important observation for this area"])]),
          G("Overall opinion and conditions on use", [
              PARA("Overall opinion:", "State the opinion and its basis in 3–5 sentences: is the model fit for ECL provisioning under the Directions?"),
              PARA("Conditions on model use:", "List any restriction, compensating control or overlay that must apply until findings are closed"),
              PARA("Material changes since the last validation:", "Changes to scope, methodology, data, scenarios or the Directions that affect the opinion", adv=True)]),
          G("Findings summary", [
              TBL(["Severity", "Findings raised", "Open", "Closed", "Overdue"],
                  [("High",), ("Medium",), ("Low",), ("Total",)], hints=["", "Count", "Count", "Count", "Count"])]),
          G("Limitations of the validation", [
              LIST([("Scope limitations:", "Areas not covered and why"),
                    ("Data or access limitations:", "Data, code or people the validators could not access"),
                    ("Reliance on developer work:", "Developer results accepted without independent re-performance")], adv=True)], brief=False),
      ]),

    S("Regulatory Alignment and Governance Assessment",
      "Test that every requirement of the Directions maps to documented and evidenced treatment, and that governance and independence meet the bank's model risk policy. Fill paragraph numbers from the final Directions (27 April 2026) and the bank's compliance matrix.",
      [
          G("Review of the compliance matrix", [
              TBL(["Requirement area", "Directions para", "Treatment in development document", "Validator assessment", "Rating", "Comment / evidence"],
                  [("Staging framework (Stage 1 / 2 / 3)",), ("SICR determination at each reporting date",), ("NPA classification (extant norms retained)",),
                   ("Lifetime ECL and expected life",), ("Probability-weighted scenarios",), ("EIR and discounting",),
                   ("Prudential floors, Stage 1 and Stage 2 (product-based)",), ("Transition arrangements",),
                   ("Board oversight and governance",), ("Model validation and review",), ("Disclosures and reporting",),
                   ("Applicability and effective date (1 April 2027)",), ("Definitions: ECL, SICR, default, EIR, POCI, FVTPL",),
                   ("Initial recognition",), ("Measurement by instrument type",), ("Collateral",), ("POCI assets",),
                   ("Restructured accounts (Resolution of Stressed Assets Directions)",)],
                  hints=["", "para", "MDD section and summary of the treatment", "Is the treatment adequate and complete?", "Compliant / Partially compliant / Gap", "Evidence or reasoning"],
                  brief_rows=8),
              NOTE("Where the Directions are principles-based, record the bank's interpretation and the approval that supports it, and state whether the validator agrees.", adv=True)]),
          G("Governance and independence", [
              TBL(["Governance element", "Expectation", "Evidence reviewed", "Assessment", "Rating"],
                  [("Board and committee oversight", "Policy, methodology and results approved at the designated forum"),
                   ("ECL policy and model risk policy", "Approved, current and consistent with the Directions"),
                   ("Model inventory and tiering", "Model recorded with owner, tier and validation due date"),
                   ("Independence of validation", "Validators independent of development and of model use"),
                   ("Change management", "Material changes approved and re-validated before use"),
                   ("Use test", "Output is the basis for provisioning and for management reporting")],
                  hints=["", "", "Documents, minutes or approvals reviewed", "Validator assessment", RATING], brief_rows=4)]),
          G("Third-party and vendor components", [
              NOTE("Applies only where a vendor model, scenario provider or external data is used; otherwise write “Not applicable”."),
              TBL(["Component", "Vendor", "Access to documentation and code", "Supervisory access", "Validator assessment", "Rating"],
                  [(None,)], hints=["Component", "Vendor", "Y/N", "Y/N", "Dependency and concentration risk assessment", RATING])], brief=False),
      ]),

    S("Conceptual Soundness and Methodology Review",
      "Judge whether each methodological choice is theoretically sound, consistent with the Directions and supported by evidence. Challenge the developer; do not merely restate the development document.",
      [
          G("Scope, default, staging and SICR", [TBL(TEST_COLS, [
              ("Default definition and NPA alignment", "Default equals NPA classification under Chapter II of the Directions and is used consistently for PD, LGD and EAD"),
              ("Cure and probation rules", "Probation documented; no re-ageing without a basis"),
              ("SICR relative and absolute triggers", "Thresholds calibrated on the bank's data with evidence of discriminatory power"),
              ("Days-past-due backstop", "30 DPD rebuttable presumption applied and rebuttals documented"),
              ("Qualitative triggers", "Watchlist, early-warning and restructuring signals are captured"),
              ("Stage movement and symmetry", "Cure and migration rules are symmetric and tested"),
              ("Low credit risk exemption", "Applied only where the Directions permit and documented"),
              ("Restructured and modified assets", "Treatment aligned with the Resolution of Stressed Assets Directions"),
              ("Initial recognition, EIR and POCI", "Origination baseline, EIR method and POCI rules documented and applied"),
              ("Instruments in scope", "Funded, undrawn, guarantees and debt investments scoped correctly; FVTPL excluded"),
          ], hints=ASSESS, brief_rows=6)]),
          G("Probability of default (PD)", [TBL(TEST_COLS, [
              ("Segmentation and homogeneity", "Segments differ materially in default rate; no gaps or overlaps"),
              ("Model form and estimation", "Method suits the data; fit, significance and stability are evidenced"),
              ("Variable selection and signs", "Information value, VIF and sign checks passed; economic intuition holds"),
              ("Point-in-time conversion", "TTC-to-PiT method is reasonable and linked to the macro satellite model"),
              ("Lifetime PD extrapolation", "Term structure is consistent; marginal PD derived correctly"),
              ("Sample, window and representativeness", "Window covers a full cycle; enough defaults per segment"),
              ("Floors, caps and alternatives", "Floors are sourced; challenger approaches were considered"),
          ], hints=ASSESS, brief_rows=4)]),
          G("Loss given default (LGD)", [TBL(TEST_COLS, [
              ("Workout LGD construction", "Recoveries discounted at EIR; costs included; cash flows complete"),
              ("Cure and incomplete workouts", "Censoring handled with recovery curves or tested exclusions"),
              ("Downturn add-on removal", "ECL LGD is point-in-time and unbiased"),
              ("Collateral valuation and haircuts", "Valuation, haircut and time to realise supported by data"),
              ("Forward-looking link", "LGD varies with scenarios, for example collateral indexed to house prices"),
              ("Floors", "Any floor is sourced and its effect quantified"),
          ], hints=ASSESS, brief_rows=3)]),
          G("Exposure at default (EAD), prepayment and expected life", [TBL(TEST_COLS, [
              ("Amortising loans and prepayment", "Schedule, accrued interest and CPR are reasonable"),
              ("Revolving and undrawn exposures (CCF)", "CCF by utilisation and delinquency, tested on history"),
              ("Expected life and behavioural cap", "Life reflects the period of credit risk exposure; cap supported by survival data"),
              ("Lifetime projection and discounting", "Step size adequate; discounting at EIR applied"),
          ], hints=ASSESS, brief_rows=2)]),
          G("Individually assessed exposures", [TBL(TEST_COLS, [
              ("Assessment threshold", "Threshold documented and reasonable"),
              ("Discounted cash-flow method", "Scenario-weighted, approved and periodically reviewed"),
              ("Double counting", "Individually assessed exposures are excluded from the collective run"),
          ], hints=ASSESS)], brief=False),
          G("Challenge of assumptions and limitations", [TBL(
              ["Assumption ID", "Assumption", "Validator challenge", "Materiality", "Agreed?"],
              [("LIM-01",), ("LIM-02",), ("LIM-03",)],
              hints=["", "Assumption as stated in the development document", "Challenge and supporting analysis", "Low / Medium / High", "Y / N – reason"])], brief=False),
      ]),

    S("Data and Input Validation",
      "Confirm that the data behind the model is complete, accurate, representative and reconciled. Re-perform the sample waterfall and test the lineage from source tables to the modelling dataset.",
      [
          G("Data lineage and reconciliation", [TBL(
              ["Dataset", "Source and owner", "Test performed", "Result", "Exceptions and treatment", "Rating"],
              [("Loan and balance tape",), ("Default and recovery history",), ("Origination and bureau data",), ("Macroeconomic series",)],
              hints=["", "Source system, table and owner", "Test performed by the validator", "Result", "Exceptions and how they were treated", RATING], brief_rows=3)]),
          G("Data-quality tests", [TBL(
              ["Test", "Result", "Treatment of exceptions", "Residual impact", "Rating"],
              [("Completeness (missing values)",), ("Accuracy and reconciliation to GL",), ("Consistency across periods and systems",),
               ("Uniqueness and keys",), ("Timeliness",), ("History sufficiency (cycles and defaults)",)],
              hints=["", "Result and metric", "Treatment of exceptions", "Residual impact on ECL", RATING], brief_rows=4),
              TBL(["Waterfall step", "Developer accounts", "Validator re-performed accounts", "Developer balance (INR crore)", "Validator balance (INR crore)", "Variance"],
                  [("1. Raw extraction",), ("2. Scope filter",), ("3. Data-quality filter",), ("4. Final modelling dataset",)],
                  hints=["", "Count", "Count", "INR crore", "INR crore", "%"], adv=True)]),
          G("Representativeness, proxies and limitations", [TBL(
              ["Limitation or proxy", "Validator view on justification", "Effect on conservatism", "Rating"],
              [(None,)], hints=["Limitation or proxy used", "Is the proxy reasonable and supported?", "Conservative / neutral / aggressive", RATING])], brief=False),
      ]),

    S("Implementation and Code Review",
      "Prove that the production engine does what the development document says. Replicate the key outputs independently and review the code and its controls.",
      [
          G("Independent replication", [TBL(
              ["Component", "Replication method", "Developer value", "Validator value", "Variance", "Tolerance", "Status"],
              [("Staging and SICR",), ("12-month PD",), ("LGD",), ("Total probability-weighted ECL",),
               ("Lifetime PD term structure",), ("EAD and expected life",), ("ECL by stage",)],
              hints=["", "Independent code or tool used", "Value", "Value", "Absolute or %", "e.g., 0.01%", "Within tolerance / Outside tolerance"], brief_rows=4)]),
          G("Code review", [TBL(
              ["Check", "Result", "Comment"],
              [("Version control, release tag and access control",), ("Unit tests and coverage",), ("Hard-coded parameters",),
               ("Reproducibility (seeds, input snapshots)",), ("Error handling and logging",),
               ("Consistency of code with the development document",), ("Separation of development and production environments",)],
              hints=["", "Pass / Partial / Fail", "Evidence and comment"], brief_rows=4)]),
          G("Production controls", [TBL(
              ["Control", "Evidence reviewed", "Assessment", "Rating"],
              [("UAT and sign-off",), ("Parallel-run reconciliation",), ("ECL reconciliation to general ledger",), ("Run schedule and audit trail",)],
              hints=["", "Evidence reviewed", "Validator assessment", RATING])], brief=False),
      ]),

    S("Outcomes Analysis (Quantitative Testing)",
      "Re-perform or independently test discrimination, calibration, stability and back-testing. Thresholds below are illustrative bank-style defaults: replace them with the thresholds in the approved model risk policy.",
      [
          G("Discrimination and calibration", [TBL(
              ["Component and metric", "Developer result", "Validator result", "Threshold", "Status", "Comment"],
              [("PD: Gini / AUROC", None, None, "Green: Gini ≥ 0.45; Amber: 0.35–0.45; Red: < 0.35"),
               ("PD: KS statistic", None, None, "Green: KS ≥ 35%"),
               ("PD: calibration (binomial / Jeffreys)", None, None, "Observed within 95% interval of predicted"),
               ("PD: stability (PSI)", None, None, "Green: PSI < 0.10; Amber: 0.10–0.25; Red: ≥ 0.25"),
               ("LGD: R² / RMSE", None, None, "Beats historical-average benchmark"),
               ("LGD: predicted vs realised mean", None, None, "Absolute error < [3] points"),
               ("EAD / CCF: mean absolute error", None, None, "Green: MAE ≤ 10%")],
              hints=["", "Development / out-of-time result", "Validator's re-performed result", "", "Green / Amber / Red", "Comment"], brief_rows=5)]),
          G("Back-testing ECL against realised outcomes", [TBL(
              ["Period", "Segment", "Predicted ECL or loss (INR crore)", "Realised loss (INR crore)", "Variance (%)", "Comment"],
              [(None,), (None,)], hints=["Period", "Segment", "INR crore", "INR crore", "%", "Explanation of variance"])]),
          G("Stability and benchmarking", [TBL(
              ["Analysis", "Method", "Result", "Conclusion"],
              [("Population stability (PSI / CSI)",), ("Challenger or benchmark model",), ("Peer or industry comparison",)],
              hints=["", "Method and data", "Result", "Conclusion"])], brief=False),
          G("Staging and SICR effectiveness", [TBL(
              ["Test", "Result", "Threshold", "Status", "Comment"],
              [("Share of defaults preceded by Stage 2",), ("Stage 2 migration volatility (QoQ)",), ("Re-default rate after cure",)],
              hints=["", "Result", "Threshold from policy", "Green / Amber / Red", "Comment"])], brief=False),
      ]),

    S("Forward-Looking and Scenario Validation",
      "Challenge the statistical rigour and economic intuition behind each macro variable and show that scenario weighting captures the non-linearity of losses.",
      [
          G("Macro variables and satellite model", [TBL(
              ["Macro variable", "Tests performed (stationarity, sign, lag, VIF, residuals, stability)", "Result", "Validator assessment", "Rating"],
              [(None,), (None,), (None,)], hints=["Macro variable", "Tests performed", "Result", "Validator assessment", RATING], brief_rows=2)]),
          G("Scenarios and probability weights", [TBL(
              ["Scenario", "Weight", "Reasonableness of narrative and path", "Consistency with ICAAP and stress tests", "Rating"],
              [("Upside",), ("Baseline",), ("Downside",), ("Severe downside",)],
              hints=["", "%", "Is the narrative plausible and the path coherent?", "Consistent / not consistent – comment", RATING])]),
          G("Non-linearity and sensitivity re-performance", [
              TBL(["Sensitivity test", "Developer % change", "Validator re-performed % change", "Variance", "Status"],
                  [("100% severe downside",), ("100% upside",), ("SICR tightening",), ("LGD shock",), ("Macro shock",), ("Stage 2 backstop",)],
                  hints=["", "%", "%", "Percentage points", "Within tolerance / Outside tolerance"], brief_rows=3),
              PARA("Weighted ECL versus baseline-only ECL:", "Size of the non-linearity effect and the validator's view on its reasonableness", adv=True)]),
      ]),

    S("Prudential Floors, Transition and Overlays",
      "Confirm that model output becomes the booked provision correctly: floors applied, transition quantified and every post-model adjustment documented, approved and temporary.",
      [
          G("Prudential floors (Stage 1 and Stage 2)", [
              NOTE("Fill from the final Directions of 27 April 2026, not from the October 2025 draft."),
              TBL(["Product", "Stage", "Prescribed floor", "Model ECL", "Floor-adjusted provision", "Validator re-performance", "Floor binding?"],
                  [(None,), (None,)], hints=["Product", "1 / 2", "%", "INR crore", "INR crore", "Re-performed provision and variance", "Y / N"], brief_rows=1)]),
          G("Transition arrangements", [TBL(
              ["Item", "Expectation", "Evidence and assessment", "Rating"],
              [("Fair valuation of the loan book on 1 April 2027", "Basis documented, data complete and valuation reproducible"),
               ("Treatment of the transition impact", "Accounting and capital treatment follow the final Directions"),
               ("Quantified transition impact", "Amount and capital-adequacy effect are reasonable and reconciled")],
              hints=["", "", "Evidence reviewed and assessment", RATING])], brief=False),
          G("Overlays and post-model adjustments (PMAs)", [TBL(
              ["Overlay ID", "Reason", "Amount (INR crore)", "Validator assessment", "Approved and documented?", "Expiry / exit condition", "Rating"],
              [("OV-1",), ("OV-2",)], hints=["", "Model limitation, data gap or emerging risk", "INR crore", "Is the overlay justified and sized reasonably?", "Y / N – reference", "Expiry date and exit plan", RATING], brief_rows=1)]),
      ]),

    S("Monitoring, Model Risk and Use",
      "Check that the ongoing monitoring plan can detect deterioration in time and that limitations, compensating controls and conditions on use are explicit.",
      [
          G("Adequacy of the monitoring plan", [TBL(
              ["Metric", "Frequency in development document", "Threshold adequacy", "Validator assessment", "Rating"],
              [("Population stability index (PSI)",), ("PD discrimination (Gini)",), ("PD calibration drift",), ("LGD realised vs predicted error",),
               ("Stage 2 migration volatility",), ("Scenario weight and macro path review",), ("Overlay usage",)],
              hints=["", "Frequency", "Are the Green / Amber / Red thresholds adequate?", "Validator assessment", RATING], brief_rows=4)]),
          G("Limitations, compensating controls and conditions on use", [LIST([
              ("Key model limitations:", "Limitations that matter for the ECL estimate"),
              ("Compensating controls required:", "Overlays, floors, manual reviews or monitoring that must apply"),
              ("Restrictions on model use:", "Portfolios, products or purposes where the model must not be used"),
              ("Redevelopment and recalibration triggers agreed:", "Triggers agreed with the model owner")])]),
          G("Disclosure review", [TBL(
              ["Disclosure item", "Data source and owner", "Validator assessment", "Rating"],
              [("ECL methodology and key assumptions",), ("Reconciliation of opening to closing loss allowance by stage",),
               ("Exposure and ECL by stage and segment",), ("Transition and accounting changes",), ("Sensitivity disclosures",)],
              hints=["", "Data source and owner", "Validator assessment", RATING])], brief=False),
      ]),

    S("Findings, Remediation and Sign-Off",
      "Record every finding with a severity, owner and due date, state the conditions on use, and obtain the required sign-offs.",
      [
          G("Findings register", [TBL(
              ["ID", "Area and development-document reference", "Finding", "Severity", "Root cause", "Recommendation", "Owner", "Due date", "Status"],
              [("F-01",), ("F-02",), ("F-03",)],
              hints=["", "Area and MDD section", "Finding", "High / Medium / Low", "Root cause", "Recommendation", "Name", "DD-MMM-YYYY", "Open / In progress / Closed"], brief_rows=3)]),
          G("Validator's conclusion", [PARA("Conclusion:", "Conclusion on fitness for use, conditions that apply and the next validation date")]),
          G("Sign-off", [TBL(
              ["Role", "Name", "Date", "Signature / reference"],
              [("Lead validator",), ("Head of model validation",), ("Model owner (acknowledgement)",), ("ECL steering committee (noted)",)],
              hints=["", "Name", "DD-MMM-YYYY", "Signature or approval reference"], brief_rows=3)]),
      ]),

    S("Validation Checklist",
      "Confirm each item before the report is issued.",
      [G("", [TBL(
          ["#", "Item", "Required artifact or verification", "Done"],
          [("1", "Placeholders and guidance", "All [brackets] replaced; all Section goal boxes and italic guidance lines deleted; illustrative thresholds replaced by policy values"),
           ("2", "Independence", "Independence confirmation signed and recorded in the control table"),
           ("3", "Regulatory mapping", "Compliance matrix completed with Directions paragraph numbers"),
           ("4", "Methodology", "Every component and segment challenged; ratings recorded"),
           ("5", "Data", "Lineage, reconciliation and waterfall re-performed"),
           ("6", "Replication", "Independent replication within tolerance, or variance explained"),
           ("7", "Outcomes", "Discrimination, calibration, stability and back-tests completed on development and out-of-time samples"),
           ("8", "Scenarios", "Macro paths and weights challenged; sensitivities re-performed"),
           ("9", "Floors, transition and overlays", "Floors re-performed; transition and overlays reviewed"),
           ("10", "Monitoring", "Monitoring thresholds and escalation owners reviewed"),
           ("11", "Findings", "Register complete with severity, owner and due date"),
           ("12", "Reporting", "Report issued to model owner and ECL steering committee; approvals recorded")],
          check="Done", brief_rows=8)], num=False)],
      appendix=True),

    S("Test Inventory and Replication Log",
      "List every test run, with the code reference, so another validator can repeat the work.",
      [G("", [TBL(
          ["Test ID", "Description", "Data and period", "Tool and code reference", "Result", "Status"],
          [("T-01",), ("T-02",), ("T-03",)],
          hints=["", "Description of the test", "Dataset and period", "Notebook, script or tool and version", "Result", "Pass / Fail / Open"])], num=False)],
      brief=False, appendix=True),

    S("Rating Scales and Glossary",
      "Definitions used for ratings, severities and terms in this document.",
      [G("Rating scale", [TBL(["Rating", "Meaning"], [
          ("Satisfactory", "Meets requirements; no material weakness"),
          ("Satisfactory with recommendations", "Meets requirements; improvements recommended with no effect on ECL reliability"),
          ("Needs improvement", "Weakness that may affect ECL reliability; remediation required within the agreed date"),
          ("Unsatisfactory", "Weakness that materially affects ECL reliability; model use restricted until remediated")])], num=False),
       G("Finding severity", [TBL(["Severity", "Meaning"], [
          ("High", "Material misstatement risk or regulatory non-compliance; remediate before next reporting date"),
          ("Medium", "Could affect the ECL estimate under plausible conditions; remediate within two quarters"),
          ("Low", "Good-practice or documentation point; remediate at next model update")])], num=False),
       G("Glossary", [TBL(["Term", "Meaning in this document"], [
          ("ECL", "Probability-weighted average of credit losses across scenarios"),
          ("SICR", "Significant increase in credit risk since initial recognition"),
          ("POCI", "Purchased or originated credit-impaired asset"),
          ("EIR", "Effective interest rate"),
          ("PD / LGD / EAD", "Probability of default / loss given default / exposure at default"),
          ("PSI / CSI", "Population stability index / characteristic stability index"),
          ("PMA", "Post-model adjustment (overlay)"),
          ("MRM", "Model risk management")])], num=False)],
      appendix=True),
]

HOWTO = {
    "advanced": "Pre-filled text is written so you can keep and adapt it rather than rewrite it. Replace everything in [square brackets]; pick one option where the bracket lists several separated by “/”. Thresholds marked illustrative must be replaced by the values in the approved model risk policy. Rate every test with the scale in the Rating Scales appendix. Delete each Section goal box and italic note before issuing the report. Where a section does not apply, write “Not applicable” with a one-line reason instead of deleting it.",
    "brief": "Replace everything in [square brackets]; pick one option where the bracket lists several separated by “/”. Rate each test with the scale in the Rating Scales appendix and record every finding in the findings register. Delete each Section goal box before issuing the report.",
}
SUBTITLE = {
    "advanced": "Independent validation aligned to the RBI (Commercial Banks – Asset Classification, Provisioning and Income Recognition) Directions, 2026 – Chapter III (ECL-based Provisioning); effective 1 April 2027",
    "brief": "Concise independent validation record for ECL models under the RBI ECL Directions, 2026 (IFRS 9 / Ind AS 109-aligned)",
}


def build(depth):
    doc = {"kind": "validation", "depth": depth, "title": "ECL Model Validation Document (MVD)",
           "subtitle": SUBTITLE[depth], "howto": HOWTO[depth],
           "footer": "ECL Model Validation Document – Template  |  Confidential – internal use only", "sections": []}
    n, app = 0, 0
    for s in SECTIONS:
        if depth == "brief" and not s["brief"]:
            continue
        if s["appendix"]:
            title = f"Appendix {chr(65 + app)} – {s['title']}"
            app += 1
            num = None
        else:
            title = f"{n}. {s['title']}"
            num = n
            n += 1
        sec = {"title": title, "goal": s["goal"], "rep": False, "blocks": []}
        j = 0
        for g in s["groups"]:
            if depth == "brief" and not g["brief"]:
                continue
            blocks = [b for b in g["blocks"] if not (depth == "brief" and b.get("adv"))]
            if g["title"]:
                if g["num"] and num is not None:
                    j += 1
                    sec["blocks"].append({"t": "h", "text": f"{num}.{j} {g['title']}"})
                else:
                    sec["blocks"].append({"t": "h", "text": g["title"]})
            for b in blocks:
                if b["t"] == "para_static":
                    from docx_to_template import mkcell as mk
                    sec["blocks"].append({"t": "para", "label": b["label"], "c": mk(b["text"])})
                else:
                    sec["blocks"].append(build_block(b, depth))
        doc["sections"].append(sec)
    return doc


if __name__ == "__main__":
    out_dir = os.path.join(os.path.dirname(__file__), "..", "templates")
    for depth in ("brief", "advanced"):
        d = build(depth)
        path = os.path.join(out_dir, f"val_{depth}.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(d, fh, ensure_ascii=False, indent=1)
        nc, nf = stats(d)
        print(f"val_{depth}.json: {len(d['sections'])} sections, {nc} cells, {nf} to-fill")
