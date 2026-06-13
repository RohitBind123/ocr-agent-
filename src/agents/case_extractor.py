"""
Multi-document RGHS case extractor (model-parameterized).

For each case it feeds the prescription (all pages), the printed bill, and the
diagnosis report into one multimodal Gemini call and extracts the 5 target fields.
The same function runs for every model in the bake-off.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass

import google.genai as genai
from google.genai import types

from src.prompts.case_extraction import EXTRACTION_PROMPT, SYSTEM_PROMPT
from src.utils.case_discovery import DOC_LABELS, Case, render_doc_pages, render_region
from src.utils.llm import generate_with_retry
from src.utils.parsing import parse_json

# High-DPI crop of the prescription's bottom band, where the faint "Review Date /
# After Day(s)" follow-up interval lives. Disabled by default: measured to NOT improve the
# duration field (the value is often blank on the form — see accuracy_analysis.md §5.5).
INCLUDE_DURATION_CROP = False
DURATION_CROP_DPI = 300
DURATION_CROP_BOX = (0.0, 0.55, 1.0, 1.0)

# Per-document render plan: which docs to send, in priority order, and how many pages.
# P=prescription (primary), B=bill (printed cross-check), D=diagnosis report (confirm dx).
# Investigation (I) is intentionally excluded — its lab tables don't feed the 5 fields.
DOC_PLAN: tuple[tuple[str, int, int], ...] = (
    # (letter, max_pages, dpi)
    ("P", 4, 200),
    ("B", 3, 170),
    ("D", 2, 160),
)

FIELDS = ("patient_name", "tid", "consultant_name", "complaint", "diagnosis", "duration")


@dataclass(frozen=True)
class ExtractConfig:
    temperature: float = 0.0
    concurrency: int = 3


def _build_contents(case: Case) -> tuple[list, list[str]]:
    """Assemble the interleaved (label, image) content list for one case."""
    contents: list = []
    used: list[str] = []
    for letter, max_pages, dpi in DOC_PLAN:
        path = case.docs.get(letter)
        if path is None:
            continue
        images = render_doc_pages(path, dpi=dpi, max_pages=max_pages)
        if not images:
            continue
        used.append(letter)
        for i, img in enumerate(images, 1):
            contents.append(f"=== {DOC_LABELS[letter]} ({letter}) page {i}/{len(images)} ===")
            contents.append(types.Part.from_bytes(data=img, mime_type="image/jpeg"))

    # Extra high-res zoom of the prescription's bottom band so the faint "Review Date /
    # After Day(s)" line is readable. Only attach it when configured (it adds tokens/latency
    # and, when the line is blank, does not help — see accuracy_analysis.md §5.5).
    if INCLUDE_DURATION_CROP and (p_path := case.docs.get("P")) is not None:
        crop = render_region(p_path, page_index=0, dpi=DURATION_CROP_DPI, box=DURATION_CROP_BOX)
        if crop:
            contents.append(
                "=== PRESCRIPTION (P) BOTTOM-BAND ZOOM — read the 'Review Date / After Day(s)' "
                "follow-up interval here (do NOT use a medication course or symptom duration) ==="
            )
            contents.append(types.Part.from_bytes(data=crop, mime_type="image/jpeg"))

    contents.append(EXTRACTION_PROMPT)
    return contents, used


def _empty_record(case: Case, model: str, error: str) -> dict:
    rec = {f: "" for f in FIELDS}
    rec.update(
        case_id=case.case_id,
        folder_tid=case.tid,
        folder_name=case.name,
        model=model,
        docs_used="",
        latency_s=0.0,
        error=error,
    )
    return rec


async def extract_case(
    client: genai.Client,
    model: str,
    case: Case,
    sem: asyncio.Semaphore,
    cfg: ExtractConfig,
) -> dict:
    """Extract the 5 fields for one case with one model. Never raises."""
    async with sem:
        loop = asyncio.get_event_loop()
        try:
            contents, used = await loop.run_in_executor(None, _build_contents, case)
        except Exception as exc:  # rasterization failure
            return _empty_record(case, model, f"render: {exc}")

        t0 = time.time()
        try:
            response = await generate_with_retry(
                client,
                model,
                contents,
                types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    temperature=cfg.temperature,
                    response_mime_type="application/json",
                ),
            )
            data = parse_json(response.text or "")
            rec = {f: str(data.get(f, "") or "").strip() for f in FIELDS}
            rec.update(
                case_id=case.case_id,
                folder_tid=case.tid,
                folder_name=case.name,
                model=model,
                docs_used=",".join(used),
                latency_s=round(time.time() - t0, 2),
                error=None,
            )
            print(f"    [{model}] ✓ {case.case_id[:34]:34s} ({rec['latency_s']}s)")
            return rec
        except Exception as exc:  # noqa: BLE001
            detail = f"{type(exc).__name__}: {exc}".strip().rstrip(":").strip()
            print(f"    [{model}] ✗ {case.case_id[:34]:34s} ERROR: {detail}")
            return _empty_record(case, model, detail)


async def extract_all(
    client: genai.Client,
    model: str,
    cases: list[Case],
    cfg: ExtractConfig,
) -> list[dict]:
    """Run extraction for every case under one model, capped by a semaphore."""
    sem = asyncio.Semaphore(cfg.concurrency)
    tasks = [extract_case(client, model, c, sem, cfg) for c in cases]
    return await asyncio.gather(*tasks)
