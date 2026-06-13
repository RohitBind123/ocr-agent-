# RGHS Case Bake-off — Build the most accurate OCR extraction agent

## Goal
Extract 5 fields (Patient name, Consultant Name, Complain, Diagnosis, Duration) from
folder-per-patient RGHS cases (P/B/I/D PDFs) into the ground-truth format, and find the
most accurate Gemini model by scoring against `RGHS test/Diagnosis.xlsx` **contextually**
(not word-by-word).

## Decisions (locked with user)
- Models: top-5 bake-off — 3.1-pro, 3-pro, 2.5-pro, 3-flash, 2.5-flash (3.5-flash excluded per user)
- Doc inputs per case: **P + B + D** (Investigation `I` excluded — no target field comes from it)
- Accuracy: LLM clinical judge (correct/partial/wrong) + deterministic similarity as secondary
- Judge model: gemini-3.1-pro-preview (fixed, for fairness)

## Plan / status
- [x] Research forms: map all 5 fields to form regions (P primary, B printed cross-check, D confirms dx)
- [x] Protect PHI: gitignore `RGHS test/`
- [x] `case_discovery.py` — folder parsing, P/B/I/D detection, multi-page rasterize (fixes old pages[0] bug)
- [x] `case_extraction.py` — XML prompt; concise summary style, duration targeting, dx sourcing
- [x] `case_extractor.py` — model-parameterized async multi-doc extractor + retry/backoff
- [x] `ground_truth.py` — load Diagnosis.xlsx, match case->GT by TID then fuzzy name (12/12 matched)
- [x] `accuracy_judge.py` + prompt — contextual per-field judge + aggregate
- [x] `excel_report.py` — 5-col output + multi-sheet bake-off report
- [x] `bakeoff.py` orchestrator + `bakeoff.py` entry point
- [x] Unit tests (16 passing) for deterministic core
- [x] Prompt iteration v1->v2 on flash: 67.5% -> 75.0% (complaint 62->79, duration 25->42, dx 50->54)
- [ ] Full 5-model sweep (RUNNING) — pick winner
- [ ] Review winner's per-field gaps; final prompt tune if worthwhile
- [ ] Update README (done) + commit on a feature branch + PR

## Known hard fields
- **Duration** (weakest): faint "Review Date / After Day(s)" handwriting; model grabs med-course
  durations/quantities instead. Pro models expected to read it better.
- **Diagnosis**: handwriting ambiguity (Presbyopia vs hypermetropia) + human summarization style.

## Review (fill after sweep)
- Winner:
- Overall accuracy:
- Per-field:
