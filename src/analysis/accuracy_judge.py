"""
Clinical accuracy judge: score extracted records vs ground truth, per field and overall.

Primary metric: an LLM judge that scores each field by contextual/clinical equivalence
(correct=1.0 / partial=0.5 / wrong=0.0). Secondary metric: a deterministic normalized
string similarity, reported alongside for transparency (not the headline number).
"""
from __future__ import annotations

import asyncio
import re
from difflib import SequenceMatcher

import google.genai as genai
from google.genai import types

from src.analysis.ground_truth import GroundTruthRow
from src.prompts.accuracy_judge import JUDGE_SYSTEM_PROMPT, build_judge_prompt
from src.utils.llm import generate_with_retry
from src.utils.parsing import parse_json

SCORED_FIELDS = ("patient_name", "consultant_name", "complaint", "diagnosis", "duration")
_VERDICT_SCORE = {"correct": 1.0, "partial": 0.5, "wrong": 0.0}
_WS = re.compile(r"\s+")


def _norm(s: str) -> str:
    return _WS.sub(" ", (s or "").strip().lower())


def string_similarity(a: str, b: str) -> float:
    """Deterministic 0-1 normalized similarity (secondary, transparency metric)."""
    na, nb = _norm(a), _norm(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    seq = SequenceMatcher(None, na, nb).ratio()
    ta, tb = set(na.split()), set(nb.split())
    jacc = len(ta & tb) / max(len(ta | tb), 1)
    return round(max(seq, jacc), 3)


def _coerce_verdict(field_obj: object) -> tuple[str, float]:
    if not isinstance(field_obj, dict):
        return "wrong", 0.0
    verdict = str(field_obj.get("verdict", "wrong")).lower().strip()
    if verdict not in _VERDICT_SCORE:
        verdict = "wrong"
    # Trust the verdict label for the score (keeps scoring consistent).
    return verdict, _VERDICT_SCORE[verdict]


async def judge_case(
    client: genai.Client,
    judge_model: str,
    extracted: dict,
    gt: GroundTruthRow,
    sem: asyncio.Semaphore,
) -> dict:
    """Score one extracted record vs its ground-truth row. Never raises."""
    async with sem:
        # Secondary deterministic metric (always available even if the judge fails).
        sims = {
            f: string_similarity(extracted.get(f, ""), getattr(gt, f))
            for f in SCORED_FIELDS
        }
        try:
            response = await generate_with_retry(
                client,
                judge_model,
                [build_judge_prompt(extracted, gt)],
                types.GenerateContentConfig(
                    system_instruction=JUDGE_SYSTEM_PROMPT,
                    temperature=0.0,
                    response_mime_type="application/json",
                ),
            )
            verdicts = parse_json(response.text or "")
        except Exception as exc:  # noqa: BLE001
            verdicts = {}
            print(f"      judge ✗ {extracted.get('case_id','?')[:30]}: {exc}")

        per_field: dict[str, dict] = {}
        scores: list[float] = []
        for f in SCORED_FIELDS:
            verdict, score = _coerce_verdict(verdicts.get(f))
            reason = ""
            if isinstance(verdicts.get(f), dict):
                reason = str(verdicts[f].get("reason", ""))[:200]
            per_field[f] = {
                "verdict": verdict,
                "score": score,
                "reason": reason,
                "similarity": sims[f],
            }
            scores.append(score)

        return {
            "case_id": extracted.get("case_id", ""),
            "model": extracted.get("model", ""),
            "fields": per_field,
            "case_score": round(sum(scores) / len(scores), 4),
            "error": extracted.get("error"),
        }


async def judge_all(
    client: genai.Client,
    judge_model: str,
    pairs: list[tuple[dict, GroundTruthRow]],
    *,
    concurrency: int = 2,
) -> list[dict]:
    sem = asyncio.Semaphore(concurrency)
    tasks = [judge_case(client, judge_model, ext, gt, sem) for ext, gt in pairs]
    return await asyncio.gather(*tasks)


def aggregate(judgements: list[dict]) -> dict:
    """Per-field and overall accuracy across all judged cases for one model."""
    if not judgements:
        return {"overall": 0.0, "fields": {f: 0.0 for f in SCORED_FIELDS}, "n": 0}
    field_means: dict[str, float] = {}
    for f in SCORED_FIELDS:
        vals = [j["fields"][f]["score"] for j in judgements]
        field_means[f] = round(sum(vals) / len(vals), 4)
    overall = round(sum(j["case_score"] for j in judgements) / len(judgements), 4)
    return {"overall": overall, "fields": field_means, "n": len(judgements)}
