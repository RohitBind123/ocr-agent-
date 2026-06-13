# RGHS OPD OCR Agent

An async AI pipeline that extracts structured clinical data from handwritten Rajasthan Government Health Scheme (RGHS) OPD records using Google Gemini. It supports two modes:

1. **Case bake-off pipeline** (current focus) — folder-per-patient cases (Prescription + Bill + Diagnosis/Investigation reports) extracted into the 5-column ground-truth format, with a multi-model accuracy bake-off scored by an LLM clinical judge. See [Case bake-off pipeline](#case-bake-off-pipeline).
2. **Flat-file pipeline** (original) — a single folder of `* - P.pdf` prescriptions extracted into a 4-column sheet.

## What it does

Each root script is a thin entry point that delegates to a module under `src/`.

| Entry point | Module | What it produces |
|---|---|---|
| `bakeoff.py` | `src/analysis/bakeoff.py` | **Runs every candidate model on every case, judges each vs ground truth, ranks them → `extracted_<model>.xlsx` + `bakeoff_report.xlsx`** |
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

## Case bake-off pipeline

The case pipeline works on **one folder per patient**. Each folder is named `<TID> <NAME>`
and contains some subset of:

| File | Meaning | Presence | Role in extraction |
|---|---|---|---|
| `P.pdf` | Prescription (handwritten RGHS OPD form) | always | **Primary** source for all 5 fields |
| `B.pdf` | Bill of supply (printed) | always | Cross-checks patient name, consultant, TID (in "Remarks") |
| `D.pdf` | Diagnosis report (imaging / lab) | optional | Confirms the spelling of the diagnosis only |
| `I.pdf` | Investigation report (lab values) | optional | Not fed to the model (no target field comes from it) |

It extracts the **5 ground-truth columns**: `Patient name`, `Consultant Name`, `Complain`,
`Diagnosis`, `Duration`.

### Field sources (where each column comes from on the form)

- **Patient name / TID** — prescription header + the printed bill (bill spelling wins).
- **Consultant Name** — prescription "Treating Doctor Name" + doctor's stamp, confirmed by the bill's "Consultant".
- **Complain** — the prescription "Chief Complaints:" section only (concise primary complaint + duration).
- **Diagnosis** — the prescription provisional-diagnosis box / top free space + major chronic comorbidities. The D-report only confirms spelling; it never replaces the OPD diagnosis with radiology findings.
- **Duration** — the prescription "Review Date / After Day(s):" follow-up interval (e.g. `1 month`, `15 Days`, `30 Days`).

### How accuracy is measured

The output is intentionally a **concise one-line case-sheet summary** that mirrors the human
ground truth — not a verbatim transcription. Accuracy is scored **contextually** (not
word-by-word) by an LLM clinical judge (`src/analysis/accuracy_judge.py`): each field is graded
`correct` (1.0) / `partial` (0.5) / `wrong` (0.0) by clinical equivalence — paraphrase, expanded
abbreviations, and equivalent units (`1 month` == `30 days`) all count as correct. A deterministic
string-similarity is reported alongside as a secondary signal.

### Running the bake-off

```bash
python3 bakeoff.py
```

This extracts every case with each model in `BAKEOFF_MODELS` (config), judges each against the
ground truth with `JUDGE_MODEL`, then writes:

- `output/extracted_<model>.xlsx` — one model's output in the 5-column ground-truth format
- `output/bakeoff_report.xlsx` — a `Summary` sheet ranking models by overall + per-field accuracy, plus one detail sheet per model (ground truth vs extracted, verdict, score, reason)

The console prints a ranked table and names the winning model.

### New modules

```
src/utils/case_discovery.py      # find <TID> <NAME> folders, identify P/B/I/D, rasterize pages
src/utils/llm.py                 # async Gemini call with retry + exponential backoff
src/prompts/case_extraction.py   # XML-structured 5-field extraction prompt
src/agents/case_extractor.py     # model-parameterized multi-document extractor
src/analysis/ground_truth.py     # load Diagnosis.xlsx + match each case folder to its row
src/prompts/accuracy_judge.py    # XML-structured clinical accuracy judge prompt
src/analysis/accuracy_judge.py   # LLM judge + deterministic similarity + aggregation
src/utils/excel_report.py        # 5-column output + multi-sheet bake-off report
src/analysis/bakeoff.py          # orchestrator: extract -> judge -> rank
```

Unit tests for the deterministic core (folder parsing, GT matching, scoring) live in `tests/`:

```bash
python3 -m pytest tests/ -q
```

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
