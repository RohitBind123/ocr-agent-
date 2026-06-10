"""
Central configuration — all credentials and paths loaded from .env.
Scripts import from here instead of hardcoding values.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY: str = os.environ["GEMINI_API_KEY"]

PDF_DIR    = Path(os.environ.get("PDF_DIR",    "pdfs"))
OUTPUT_DIR = Path(os.environ.get("OUTPUT_DIR", "output"))
REF_FILE   = Path(os.environ.get("REF_FILE",   "reference.xlsx"))

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
