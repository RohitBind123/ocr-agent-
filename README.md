# RGHS OPD OCR Agent

An async AI pipeline that extracts structured clinical data (patient name, TID, complaint, diagnosis) from handwritten Rajasthan Government Health Scheme (RGHS) OPD prescription PDFs using Gemini 2.5 Flash.

## What it does

Each root script is a thin entry point that delegates to a module under `src/`.

| Entry point | Module | What it produces |
|---|---|---|
| `extract.py` | `src/agents/extractor.py` | Batch-extracts all prescriptions → `RGHS_OPD_june_v3.xlsx` |
| `react_retry.py` | `src/agents/react_agent.py` | Re-reads "not legible" fields using a ReAct loop → `v4_react.xlsx` |
| `judge.py` | `src/analysis/judge.py` | AI clinical judge: AI output vs human reference → `judge_report.xlsx` |
| `compare.py` | `src/analysis/compare.py` | TID-matched diff of extracted vs reference → `comparison_report.xlsx` |
| `compare3.py` | `src/analysis/compare3.py` | Side-by-side 3-way diff (Reference / V2 / V3) → `comparison_3way.xlsx` |
| `merge_final.py` | `src/analysis/merger.py` | Merges V3 with human reference fallback → `RGHS_OPD_june_FINAL.xlsx` |

## Project structure

```
rghs_extractor/
├── extract.py            # thin entry points (run these)
├── react_retry.py
├── judge.py
├── compare.py
├── compare3.py
├── merge_final.py
├── src/
│   ├── config.py         # all credentials + paths, loaded from .env
│   ├── agents/           # the AI extraction agents
│   │   ├── extractor.py        # parallel one-shot extraction
│   │   └── react_agent.py      # ReAct image-investigation retry
│   ├── analysis/         # evaluation / reporting (no AI, except judge)
│   │   ├── judge.py
│   │   ├── compare.py
│   │   ├── compare3.py
│   │   └── merger.py
│   ├── prompts/          # all LLM prompts, one file per agent
│   │   ├── extraction.py
│   │   ├── react.py
│   │   └── judge.py
│   └── utils/            # shared helpers
│       ├── parsing.py          # JSON-from-LLM-response parser
│       ├── excel.py            # OPD workbook writer + style constants
│       └── image_tools.py      # crop / enhance / blue-ink isolation
├── requirements.txt
├── .env.example          # copy to .env and fill in
└── output/               # generated Excel files (gitignored — contains PHI)
```

All modules use absolute imports rooted at `src` (e.g. `from src.config import GEMINI_API_KEY`),
so always run the entry points from the project root.

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
