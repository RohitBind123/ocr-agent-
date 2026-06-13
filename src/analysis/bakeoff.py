"""
Model bake-off: extract every case with every candidate model, judge each against the
ground truth, and rank the models by contextual accuracy.

Outputs (to OUTPUT_DIR):
  - extracted_<model>.xlsx   one per model, ground-truth 5-column format
  - bakeoff_report.xlsx      summary + per-model field-level detail
"""
from __future__ import annotations

import asyncio

import google.genai as genai

from src.agents.case_extractor import ExtractConfig, extract_all
from src.analysis.accuracy_judge import aggregate, judge_all
from src.analysis.ground_truth import load_ground_truth, match_case_to_gt
from src.config import (
    BAKEOFF_MODELS,
    CASES_DIR,
    GEMINI_API_KEY,
    GROUND_TRUTH,
    JUDGE_MODEL,
    OUTPUT_DIR,
)
from src.utils.case_discovery import discover_cases
from src.utils.excel_report import write_bakeoff_report, write_extraction_excel


def _avg_latency(extractions: list[dict]) -> float:
    lats = [e["latency_s"] for e in extractions if not e.get("error")]
    return round(sum(lats) / len(lats), 2) if lats else 0.0


async def run_bakeoff(
    models: tuple[str, ...] = BAKEOFF_MODELS,
    *,
    extract_concurrency: int = 3,
    judge_concurrency: int = 2,
) -> list[dict]:
    client = genai.Client(api_key=GEMINI_API_KEY)

    cases = discover_cases(CASES_DIR)
    gt_rows = load_ground_truth(GROUND_TRUTH)
    print(f"Cases: {len(cases)} | Ground-truth rows: {len(gt_rows)} | Models: {len(models)}\n")

    # Match every case to its ground-truth row up front.
    gt_by_case: dict = {}
    matched_cases = []
    for case in cases:
        gt = match_case_to_gt(case, gt_rows)
        if gt is None:
            print(f"  ⚠ no ground-truth match for {case.case_id} — skipping in scoring")
            continue
        gt_by_case[case.case_id] = gt
        matched_cases.append(case)
    print(f"Matched {len(matched_cases)}/{len(cases)} cases to ground truth\n")

    cfg = ExtractConfig(temperature=0.0, concurrency=extract_concurrency)
    bundles: list[dict] = []

    for model in models:
        print(f"── Extracting with {model} " + "─" * (40 - len(model)))
        extractions = await extract_all(client, model, matched_cases, cfg)

        pairs = [(e, gt_by_case[e["case_id"]]) for e in extractions if e["case_id"] in gt_by_case]
        print(f"   judging {len(pairs)} cases with {JUDGE_MODEL} …")
        judgements = await judge_all(client, JUDGE_MODEL, pairs, concurrency=judge_concurrency)
        judged = {j["case_id"]: j for j in judgements}
        agg = aggregate(judgements)

        bundle = {
            "model": model,
            "extractions": extractions,
            "judged": judged,
            "agg": agg,
            "avg_latency": _avg_latency(extractions),
            "errors": sum(1 for e in extractions if e.get("error")),
        }
        bundles.append(bundle)

        write_extraction_excel(
            extractions, OUTPUT_DIR / f"extracted_{model.replace('/', '_')}.xlsx"
        )
        print(f"   {model}: overall {agg['overall']*100:.1f}%  "
              f"(errors={bundle['errors']}, avg {bundle['avg_latency']}s)\n")

        # Write the report incrementally so a partial sweep always has usable output.
        write_bakeoff_report(bundles, gt_by_case, OUTPUT_DIR / "bakeoff_report.xlsx")
        _print_ranking(bundles, final=False)

    _print_ranking(bundles, final=True)
    return bundles


def _print_ranking(bundles: list[dict], *, final: bool = True) -> None:
    from src.analysis.accuracy_judge import SCORED_FIELDS

    ranked = sorted(bundles, key=lambda b: b["agg"]["overall"], reverse=True)
    print("=" * 78)
    label = "FINAL RANKING" if final else f"RANKING SO FAR ({len(bundles)} model(s) done)"
    print(f"{label} (contextual accuracy vs ground truth)")
    print("=" * 78)
    header = f"{'Model':<26}{'Overall':>9}  " + "".join(f"{f[:5]:>7}" for f in SCORED_FIELDS)
    print(header)
    print("-" * 78)
    for b in ranked:
        a = b["agg"]
        line = f"{b['model']:<26}{a['overall']*100:>8.1f}%  " + "".join(
            f"{a['fields'][f]*100:>6.0f}%" for f in SCORED_FIELDS
        )
        print(line)
    print("-" * 78)
    best = ranked[0]
    if final:
        print(f"WINNER: {best['model']}  →  {best['agg']['overall']*100:.1f}% overall")
        print(f"Report → {OUTPUT_DIR / 'bakeoff_report.xlsx'}")
    else:
        print(f"leading: {best['model']}  ({best['agg']['overall']*100:.1f}%)  "
              f"— report updated → {OUTPUT_DIR / 'bakeoff_report.xlsx'}")


def main() -> None:
    asyncio.run(run_bakeoff())


if __name__ == "__main__":
    main()
