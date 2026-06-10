# RGHS OPD OCR Agent

An async AI pipeline that extracts structured clinical data (patient name, TID, complaint, diagnosis) from handwritten Rajasthan Government Health Scheme (RGHS) OPD prescription PDFs using Gemini 2.5 Flash.

## What it does

| Script | What it produces |
|---|---|
| `extract.py` | Batch-extracts all prescriptions → `RGHS_OPD_june_v3.xlsx` |
| `react_retry.py` | Re-reads "not legible" fields using a ReAct loop → `v4_react.xlsx` |
| `judge.py` | AI clinical judge: compares AI output vs human reference → `judge_report.xlsx` |
| `compare.py` | TID-matched diff of extracted vs reference → `comparison_report.xlsx` |
| `compare3.py` | Side-by-side 3-way diff (Reference / V2 / V3) → `comparison_3way.xlsx` |
| `merge_final.py` | Merges V3 with human reference as fallback → `RGHS_OPD_june_FINAL.xlsx` |

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

`poppler` is also required for `pdf2image`. On macOS:

```bash
brew install poppler
```

### 2. Configure credentials and paths

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```env
GEMINI_API_KEY=your_gemini_api_key_here
PDF_DIR=/path/to/folder/containing/prescription/pdfs
OUTPUT_DIR=output
REF_FILE=/path/to/human-verified-reference.xlsx
```

- **GEMINI_API_KEY** — get one at https://aistudio.google.com/app/apikey
- **PDF_DIR** — folder where the `* - P.pdf` prescription files live
- **OUTPUT_DIR** — where generated Excel files are written (default: `./output`)
- **REF_FILE** — the doctor-verified reference Excel (columns: Name, TID, Complaint, Diagnosis)

### 3. Run the pipeline

Run scripts in order for a full pipeline run:

```bash
# Step 1 — extract all prescriptions (parallel, ~5 concurrent Gemini calls)
python extract.py

# Step 2 (optional) — retry "not legible" fields with a ReAct image-investigation loop
python react_retry.py

# Step 3 — merge AI output with human reference as fallback for still-illegible rows
python merge_final.py

# Evaluation scripts (run any time after extract.py)
python judge.py          # AI-vs-human clinical equivalence scoring
python compare.py        # TID-matched diff report
python compare3.py       # 3-way comparison (REF / V2 / V3)
```

All output files are written to `OUTPUT_DIR` (default `./output/`).

## Pipeline overview

```
PDFs  ──►  extract.py  ──►  v3.xlsx
                               │
                    react_retry.py (optional)
                               │
                            v4.xlsx
                               │
                    merge_final.py  ◄──  reference.xlsx
                               │
                          FINAL.xlsx
```

## Key design decisions

- **Low thinking budget (3000 tokens)** on extraction — research shows higher budgets increase hallucination on faithful transcription tasks.
- **Strict section fidelity** — the model is constrained to pull complaint only from "Chief Complaints" and diagnosis only from the top free-space / provisional diagnosis box. It cannot infer from speciality or medications.
- **ReAct image loop** — illegible fields trigger up to 4 rounds of zoom/enhance/ink-isolation before a final answer is committed.
- **Concurrency capped at 5** to stay within Gemini rate limits.
- **Patient data stays local** — `output/` is gitignored. Never commit extracted data.
