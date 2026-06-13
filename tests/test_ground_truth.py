"""Unit tests for ground-truth parsing and case->GT matching (no API)."""
from src.analysis.ground_truth import (
    GroundTruthRow,
    _name_only,
    _name_similarity,
    match_case_to_gt,
)
from src.utils.case_discovery import Case


def _gt(raw, tid, name):
    return GroundTruthRow(
        raw_name=raw, tid=tid, name_only=name, patient_name=name,
        consultant_name="Dr X", complaint="c", diagnosis="d", duration="1 month",
    )


# All fixtures below are synthetic (no real PHI) but preserve the exact GT quirks:
# a TID + name + trailing "DR <doctor>" in one cell, case-variant names, and two
# different people who share a name but differ by TID.
def test_name_only_strips_tid_and_doctor():
    assert _name_only("100000000000010 RAVI KUMAR DR TEST DOCTOR") == "RAVI KUMAR"
    assert _name_only("\t100000000000011 RAVI KUMAR DR OTHER DOCTOR") == "RAVI KUMAR"
    assert _name_only("Meena devi") == "Meena devi"


def test_name_similarity_case_insensitive():
    assert _name_similarity("ANITA DEVI SHARMA", "Anita devi sharma") > 0.6
    assert _name_similarity("ALPHA", "alpha") == 1.0
    assert _name_similarity("ALPHA", "BETA") < 0.5


def test_match_by_tid_disambiguates_same_name():
    # Two same-name people must map to their OWN gt row by TID, not collide.
    gt_rows = [
        _gt("100000000000010 RAVI KUMAR DR TEST DOCTOR", "100000000000010", "RAVI KUMAR"),
        _gt("100000000000011 RAVI KUMAR DR OTHER DOCTOR", "100000000000011", "RAVI KUMAR"),
    ]
    c1 = Case(folder=None, tid="100000000000010", name="RAVI KUMAR")  # type: ignore[arg-type]
    c2 = Case(folder=None, tid="100000000000011", name="RAVI KUMAR")  # type: ignore[arg-type]
    assert match_case_to_gt(c1, gt_rows).tid == "100000000000010"
    assert match_case_to_gt(c2, gt_rows).tid == "100000000000011"


def test_match_by_name_when_no_tid_in_gt():
    gt_rows = [_gt("alpha", "", "alpha")]
    c = Case(folder=None, tid="100000000000012", name="ALPHA")  # type: ignore[arg-type]
    assert match_case_to_gt(c, gt_rows) is gt_rows[0]


def test_no_match_returns_none():
    gt_rows = [_gt("alpha", "", "alpha")]
    c = Case(folder=None, tid="999", name="ZEBRA")  # type: ignore[arg-type]
    assert match_case_to_gt(c, gt_rows) is None
