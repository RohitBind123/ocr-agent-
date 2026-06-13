"""
Central config — every credential and path loaded once from .env.
All src modules import from here; nothing is hardcoded elsewhere.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]

PDF_DIR    = Path(os.environ.get("PDF_DIR",    "pdfs"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "output"))
REF_FILE   = Path(os.environ.get("REF_FILE",   "reference.xlsx"))

# ── Case-folder pipeline (P/B/I/D per patient folder) ───────────────────────────
# Each case is a folder named "<TID> <NAME>" holding P.pdf (prescription, always),
# B.pdf (bill, always), and optionally I.pdf (investigation) and D.pdf (diagnosis).
CASES_DIR     = Path(os.environ.get("CASES_DIR",     "RGHS test"))
GROUND_TRUTH  = Path(os.environ.get("GROUND_TRUTH",  "RGHS test/Diagnosis.xlsx"))

# Winner of the 2026-06 bake-off (12 cases, contextual judge): most accurate AND fastest.
# Pro models over-reason and over-include detail, hurting the match against the terse
# ground truth. Use this as the default extraction model.
DEFAULT_MODEL = os.environ.get("EXTRACT_MODEL", "gemini-3-flash-preview")

# Bake-off candidate models. Order = run / display order in the report.
# NOTE: gemini-3-pro-preview was retired by Google (404 "no longer available") — excluded.
BAKEOFF_MODELS: tuple[str, ...] = (
    "gemini-3-flash-preview",   # winner, 75.8%
    "gemini-3.1-pro-preview",   # 71.7%
    "gemini-2.5-pro",           # 67.5%
    "gemini-2.5-flash",         # 62.5%
)

# Fixed judge model — fast, stable (GA), neutral enough to grade every candidate consistently.
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "gemini-2.5-flash")

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
