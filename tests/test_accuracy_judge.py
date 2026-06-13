"""Unit tests for the deterministic parts of the accuracy judge (no API)."""
from src.analysis.accuracy_judge import (
    SCORED_FIELDS,
    _coerce_verdict,
    aggregate,
    string_similarity,
)


def test_string_similarity_bounds():
    assert string_similarity("", "") == 1.0
    assert string_similarity("x", "") == 0.0
    assert string_similarity("Hypertension", "hypertension") == 1.0
    assert 0.0 < string_similarity("low back ache", "back ache low") <= 1.0


def test_coerce_verdict_maps_score():
    assert _coerce_verdict({"verdict": "correct"}) == ("correct", 1.0)
    assert _coerce_verdict({"verdict": "partial"}) == ("partial", 0.5)
    assert _coerce_verdict({"verdict": "wrong"}) == ("wrong", 0.0)
    # unknown / malformed -> wrong
    assert _coerce_verdict({"verdict": "??"}) == ("wrong", 0.0)
    assert _coerce_verdict(None) == ("wrong", 0.0)


def _judgement(scores: dict[str, float]) -> dict:
    fields = {f: {"verdict": "x", "score": scores[f], "reason": "", "similarity": 0.0}
              for f in SCORED_FIELDS}
    return {"case_id": "c", "fields": fields,
            "case_score": sum(scores.values()) / len(scores)}


def test_aggregate_per_field_and_overall():
    j1 = _judgement({f: 1.0 for f in SCORED_FIELDS})
    j2 = _judgement({f: 0.0 for f in SCORED_FIELDS})
    agg = aggregate([j1, j2])
    assert agg["n"] == 2
    assert agg["overall"] == 0.5
    for f in SCORED_FIELDS:
        assert agg["fields"][f] == 0.5


def test_aggregate_empty():
    agg = aggregate([])
    assert agg["overall"] == 0.0
    assert agg["n"] == 0
