"""
Load the human ground-truth (Diagnosis.xlsx) and match each case folder to its row.

Ground-truth columns: Patient name | Consultant Name | Complain | Diagnosis | Duration
The "Patient name" cell is messy — it may embed the TID and even the doctor
("100000000000010 RAVI KUMAR DR TEST DOCTOR") or be just a name ("alpha"). So matching a
case folder to its GT row is done by TID first, then by fuzzy name overlap.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import openpyxl

from src.utils.case_discovery import Case

_DIGITS = re.compile(r"\d{6,}")
_DOCTOR_TAIL = re.compile(r"\bdr\b.*$", re.IGNORECASE)
_NON_ALNUM = re.compile(r"[^a-z0-9 ]+")


@dataclass(frozen=True)
class GroundTruthRow:
    raw_name: str          # the original "Patient name" cell
    tid: str               # leading digits parsed from raw_name ("" if none)
    name_only: str         # name with TID + trailing "DR ..." stripped
    patient_name: str      # cleaned display name (== name_only, kept for clarity)
    consultant_name: str
    complaint: str
    diagnosis: str
    duration: str


def _norm(s: str) -> str:
    return _NON_ALNUM.sub("", (s or "").strip().lower()).strip()


def _name_only(raw: str) -> str:
    s = _DIGITS.sub("", raw or "").strip()
    s = _DOCTOR_TAIL.sub("", s).strip()
    return s


def load_ground_truth(path: Path) -> list[GroundTruthRow]:
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.worksheets[0]
    rows: list[GroundTruthRow] = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r or all(c is None or str(c).strip() == "" for c in r):
            continue
        cells = [("" if c is None else str(c)).strip() for c in r]
        cells += [""] * (5 - len(cells))
        raw_name, consultant, complaint, diagnosis, duration = cells[:5]
        tid_m = _DIGITS.search(raw_name)
        rows.append(
            GroundTruthRow(
                raw_name=raw_name,
                tid=tid_m.group(0) if tid_m else "",
                name_only=_name_only(raw_name),
                patient_name=_name_only(raw_name),
                consultant_name=consultant,
                complaint=complaint,
                diagnosis=diagnosis,
                duration=duration,
            )
        )
    return rows


def _name_similarity(a: str, b: str) -> float:
    na, nb = _norm(a), _norm(b)
    if not na or not nb:
        return 0.0
    set_a, set_b = set(na.split()), set(nb.split())
    token = len(set_a & set_b) / max(len(set_a | set_b), 1)
    seq = SequenceMatcher(None, na, nb).ratio()
    return max(token, seq)


def match_case_to_gt(
    case: Case, gt_rows: list[GroundTruthRow], *, min_name_score: float = 0.55
) -> GroundTruthRow | None:
    """Match a case folder to its ground-truth row by TID, then by fuzzy name."""
    # 1. TID equality / containment (handles minor truncation between folder and sheet)
    if case.tid:
        for g in gt_rows:
            if g.tid and (case.tid == g.tid or case.tid in g.raw_name or g.tid in case.tid):
                return g
    # 2. Fuzzy name overlap against the cleaned GT name
    best: GroundTruthRow | None = None
    best_score = 0.0
    for g in gt_rows:
        score = _name_similarity(case.name, g.name_only)
        if score > best_score:
            best, best_score = g, score
    return best if best_score >= min_name_score else None
