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

> Requires **Python 3.10+**. Run every command from the project root (`rghs_extractor/`).

### 1. Install the `poppler` system dependency

`pdf2image` shells out to poppler to rasterize PDFs.

**macOS** (Homebrew):
```bash
brew install poppler
```

**Windows**:
1. Download the latest build from https://github.com/oschwartz10612/poppler-windows/releases
2. Unzip it (e.g. to `C:\poppler`)
3. Add the `...\poppler\Library\bin` folder to your **PATH** environment variable
4. Open a new terminal so the PATH change takes effect

(Alternatively, on either OS with conda: `conda install -c conda-forge poppler`.)

### 2. Create a virtual environment and install Python deps

**macOS / Linux**:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

**Windows (PowerShell)**:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

**Windows (Command Prompt)**:
```cmd
python -m venv .venv
.venv\Scripts\activate.bat
pip install -r requirements.txt
```

### 3. Configure credentials and paths

Copy the template, then edit `.env`:

**macOS / Linux**:
```bash
cp .env.example .env
```

**Windows**:
```cmd
copy .env.example .env
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
  (Windows example: `PDF_DIR=C:\Users\you\Downloads\RGHS OPD june` — no quotes needed)
- **OUTPUT_DIR** — where generated Excel files are written (default: `./output`)
- **REF_FILE** — the doctor-verified reference Excel (columns: Name, TID, Complaint, Diagnosis)

### 4. Run the pipeline

The commands are identical on every OS — only the `python` executable name differs
(`python3` on macOS/Linux, `python` on Windows). Run them in order:

**macOS / Linux**:
```bash
python3 extract.py        # Step 1 — extract all prescriptions (~5 concurrent Gemini calls)
python3 react_retry.py    # Step 2 (optional) — ReAct retry on "not legible" fields
python3 merge_final.py    # Step 3 — merge AI output with human-reference fallback

# Evaluation (run any time after extract.py)
python3 judge.py          # AI-vs-human clinical equivalence scoring
python3 compare.py        # TID-matched diff report
python3 compare3.py       # 3-way comparison (REF / V2 / V3)
```

**Windows**:
```powershell
python extract.py
python react_retry.py
python merge_final.py

python judge.py
python compare.py
python compare3.py
```

All output files are written to `OUTPUT_DIR` (default `./output/`).

> **Alternative — run as modules.** Since the logic lives in `src/`, you can also run
> any stage with `python -m`, e.g. `python -m src.agents.extractor` or
> `python -m src.analysis.compare`. The thin root scripts above are just shortcuts.

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
