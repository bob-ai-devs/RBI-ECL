"""
Google GenAI layer.

Design for low API load:
  1. ONE call reads the uploaded code and produces an "evidence digest" (cached for the whole session,
     so creating the other three reports never re-sends the code).
  2. Each report is filled from that digest in a few batched calls (only the still-blank cells are sent).
  3. Only one report is ever generated per click.

Model : gemini-flash-lite-latest      API version : v1beta
"""
import hashlib
import io
import json
import re
import time
import zipfile

from . import model as M

MODEL = "gemini-flash-lite-latest"
API_VERSION = "v1beta"

CODE_EXT = {".py", ".ipynb", ".sql", ".r", ".sas", ".txt", ".md", ".json", ".yaml", ".yml", ".cfg", ".toml", ".ini", ".sh", ".scala", ".java", ".js", ".csv"}
MAX_CODE_CHARS = 300_000          # ~75k tokens, well inside the model's context window
MAX_FILE_CHARS = 120_000
BATCH_CELLS = 180

SYSTEM = (
    "You are a senior credit-risk model documentation specialist at an Indian bank implementing the "
    "Reserve Bank of India (Commercial Banks – Asset Classification, Provisioning and Income Recognition) "
    "Directions, 2026 (issued 27 April 2026, effective 1 April 2027; Chapter III = ECL-based provisioning; "
    "Ind AS 109-aligned, three-stage model, probability-weighted scenarios, EIR discounting, prudential floors "
    "on Stage 1 and Stage 2). You write precise, evidence-based documentation and never invent facts."
)


# ------------------------------------------------------------------ code ingestion
def _ipynb_to_text(raw: bytes) -> str:
    nb = json.loads(raw.decode("utf-8", errors="ignore"))
    parts = []
    for i, cell in enumerate(nb.get("cells", [])):
        src = "".join(cell.get("source", []))
        if cell.get("cell_type") == "markdown":
            parts.append(f"# [markdown cell {i}]\n" + "\n".join("# " + l for l in src.splitlines()))
        elif cell.get("cell_type") == "code":
            parts.append(f"# [code cell {i}]\n{src}")
            for o in cell.get("outputs", []):
                txt = "".join(o.get("text", [])) or "".join(o.get("data", {}).get("text/plain", []))
                if txt:
                    parts.append("# [output]\n" + "\n".join("# " + l for l in txt[:800].splitlines()))
    return "\n\n".join(parts)


def _decode(name: str, raw: bytes) -> str:
    if name.lower().endswith(".ipynb"):
        try:
            return _ipynb_to_text(raw)
        except Exception:
            pass
    return raw.decode("utf-8", errors="ignore")


def read_uploads(files):
    """files: iterable of (name, bytes). Zips are expanded in memory. Returns list of (name, text)."""
    out = []
    for name, raw in files:
        low = name.lower()
        if low.endswith(".zip"):
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as zf:
                    for info in zf.infolist():
                        ext = "." + info.filename.rsplit(".", 1)[-1].lower() if "." in info.filename else ""
                        if info.is_dir() or ext not in CODE_EXT or info.file_size > 2_000_000:
                            continue
                        if any(p in info.filename for p in ("__pycache__", "node_modules", ".git/")):
                            continue
                        out.append((info.filename, _decode(info.filename, zf.read(info))))
            except zipfile.BadZipFile:
                pass
        else:
            out.append((name, _decode(name, raw)))
    return out


def fingerprint(files) -> str:
    h = hashlib.sha256()
    for name, raw in sorted(files, key=lambda x: x[0]):
        h.update(name.encode())
        h.update(hashlib.sha256(raw).digest())
    return h.hexdigest()[:16]


def build_corpus(texts):
    """Concatenate files with markers; trim proportionally if above the budget. Returns (corpus, truncated)."""
    total = sum(len(t) for _, t in texts)
    scale = min(1.0, MAX_CODE_CHARS / total) if total else 1.0
    parts, truncated = [], scale < 1.0
    for name, t in texts:
        lim = max(2000, int(min(len(t), MAX_FILE_CHARS) * scale))
        if len(t) > lim:
            truncated = True
            t = t[:lim] + "\n# ... [truncated]"
        parts.append(f"\n### FILE: {name}\n{t}")
    return "".join(parts), truncated


# ------------------------------------------------------------------ Gemini plumbing
def make_client(api_key: str):
    from google import genai
    from google.genai import types
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version=API_VERSION))


def _generate(client, prompt: str, max_tokens: int = 16384, retries: int = 4) -> str:
    from google.genai import types
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM, temperature=0.2, response_mime_type="application/json",
        max_output_tokens=max_tokens,
    )
    for attempt in range(retries):
        try:
            r = client.models.generate_content(model=MODEL, contents=prompt, config=cfg)
            return r.text or ""
        except Exception as e:  # network / quota / overload
            msg = str(e)
            transient = any(k in msg for k in ("429", "500", "502", "503", "504", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "DEADLINE", "overloaded"))
            if attempt == retries - 1 or not transient:
                raise
            time.sleep(3 * (attempt + 1) ** 2)
    return ""


_PAIR = re.compile(r'"(\d+\.\d+\.\d+\.\d+)"\s*:\s*"((?:[^"\\]|\\.)*)"')


def parse_json(text: str):
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        return json.loads(t)
    except Exception:
        return None


def parse_pairs(text: str) -> dict:
    """Salvage id -> value pairs from a truncated / slightly broken JSON answer."""
    obj = parse_json(text)
    if isinstance(obj, dict):
        return {str(k): v for k, v in obj.items() if isinstance(v, (str, int, float))}
    out = {}
    for k, v in _PAIR.findall(text or ""):
        try:
            out[k] = json.loads(f'"{v}"')
        except Exception:
            out[k] = v
    return out


# ------------------------------------------------------------------ step 1: evidence digest
DIGEST_KEYS = (
    "overview (model name, purpose, portfolio, instruments, language/libraries), "
    "segments_and_data (segments, data sources, windows, cleaning, sample split, waterfall counts), "
    "default_staging_sicr (default definition, DPD backstops, cure/probation, SICR triggers and thresholds, stage logic), "
    "pd (approach, variables, transformations, coefficients/parameters, TTC/PiT, lifetime extrapolation, floors), "
    "lgd (approach, drivers, collateral, haircuts, discounting, floors), "
    "ead_expected_life (amortisation, CCF, prepayment, behavioural life), "
    "macro_scenarios (macro variables, lags, satellite model, scenarios, weights, horizon), "
    "floors_overlays_transition (prudential floors, overlays/PMAs, transition), "
    "performance_testing (metrics computed: Gini, AUROC, KS, calibration, PSI, backtests, sensitivities - with the values the code produces), "
    "monitoring_production (monitoring thresholds, schedule, controls, logging, reproducibility, tests), "
    "code_quality (structure, version control hints, hard-coded values, randomness/seeds, error handling, unit tests), "
    "key_parameters (a flat object of parameter name -> exact value found in the code), "
    "gaps_not_evidenced (list of ECL documentation topics the code does not evidence)"
)


def build_digest(client, corpus: str, context: str = "") -> dict:
    prompt = f"""Read the code below. It implements (part of) an Expected Credit Loss (ECL) model.
Produce an EVIDENCE DIGEST as one JSON object with exactly these keys: {DIGEST_KEYS}.
Each value is a dense string or list of strings (key_parameters is an object). Rules:
- Only report what the code actually shows. Quote exact numbers, thresholds, variable names, function names and file names.
- If something is not in the code, do not guess; list it under gaps_not_evidenced.
- Keep the whole digest under 4,500 words. No markdown.
{('User-provided context: ' + context) if context.strip() else ''}

CODE:
{corpus}"""
    obj = parse_json(_generate(client, prompt, max_tokens=16384))
    if not isinstance(obj, dict):
        raise RuntimeError("Gemini returned an unreadable digest. Please try again.")
    return obj


# ------------------------------------------------------------------ step 2: fill cells
def _fmt_cell(c: dict) -> str:
    parts = [c["id"], c["heading"] or c["section"], c["row"] or "-", c["field"]]
    line = " | ".join(p.replace("|", "/") for p in parts)
    if c["current"]:
        line += f" | CURRENT: {c['current']}"
    if c["hint"]:
        line += f" | HINT: {c['hint']}"
    return line


RULES_DEV = (
    "You are drafting the DEVELOPER's Model Development Document from evidence in the digest. "
    "Write in the voice of the model developer (present tense, factual)."
)
RULES_VAL = (
    "You are drafting the INDEPENDENT VALIDATOR's Model Validation Document from a code review. "
    "Write in the voice of the validator. Report only what the code evidences (for example 'Code review: the 90 DPD default flag is "
    "applied in function X'). Never state that a test was performed, a result obtained or an approval given unless the code or the "
    "digest shows it; where a validator test is still to be run, leave the cell out. Ratings: only assign one when the digest gives a "
    "clear basis, otherwise leave it out."
)


def fill_batch(client, kind: str, depth: str, digest: dict, cells: list, context: str = "") -> dict:
    rules = RULES_DEV if kind == "development" else RULES_VAL
    prompt = f"""{rules}
Document: ECL Model {'Development' if kind == 'development' else 'Validation'} Document ({depth}).
{('User-provided context (treat as authoritative): ' + context) if context.strip() else ''}

EVIDENCE DIGEST (from the uploaded code):
{json.dumps(digest, ensure_ascii=False)}

CELLS TO FILL, one per line: id | heading | row | column or label | CURRENT text (if any) | HINT
{chr(10).join(_fmt_cell(c) for c in cells)}

Return ONE JSON object mapping each id to the text for that cell. Rules:
- Use only facts present in the digest or the user context. NEVER invent numbers, names, dates, approvals or results.
- If a cell cannot be supported by evidence, OMIT its id (do not return empty strings, "N/A" or "TBD").
- If CURRENT contains [square-bracket placeholders]: rewrite the whole text, keeping the fixed wording and replacing each placeholder you can support; leave a placeholder in brackets if you cannot.
- The HINT shows what the cell should contain; it is an example format, not data. Do not copy hint values as facts.
- Table cells: at most 25 words. Paragraph / bullet cells: at most 90 words. Plain text only, no markdown, no square brackets unless leaving a placeholder.
- Amounts in INR crore; dates DD-MMM-YYYY. Use the exact terminology of the template."""
    return parse_pairs(_generate(client, prompt, max_tokens=16384))


def fill_document(client, doc: dict, digest: dict, context: str = "", progress=None) -> int:
    """Fill every still-blank cell of `doc` (in place). Returns number of cells written."""
    cells = M.open_cells(doc)
    if not cells:
        return 0
    batches = [cells[i:i + BATCH_CELLS] for i in range(0, len(cells), BATCH_CELLS)]
    written = 0
    for n, batch in enumerate(batches, 1):
        if progress:
            progress((n - 1) / len(batches), f"Drafting cells {n}/{len(batches)} with Gemini ({MODEL})…")
        mapping = fill_one(client, doc, digest, batch, context)
        written += M.apply_fill(doc, mapping)
    if progress:
        progress(1.0, "Draft complete")
    return written


def fill_one(client, doc, digest, batch, context):
    valid = {c["id"] for c in batch}
    mapping = {k: v for k, v in fill_batch(client, doc["kind"], doc["depth"], digest, batch, context).items() if k in valid}
    # one retry for cells that came back missing because of truncation (not because the model chose to omit them)
    if len(mapping) < 0.5 * len(batch) and len(batch) > 20:
        rest = [c for c in batch if c["id"] not in mapping]
        retry = fill_batch(client, doc["kind"], doc["depth"], digest, rest[: len(rest) // 2 + 1], context)
        mapping.update({k: v for k, v in retry.items() if k in valid})
    return mapping
