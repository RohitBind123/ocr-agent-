"""
Discover RGHS case folders and rasterize their PDFs.

Each case is a folder named "<TID> <NAME>" containing some subset of:
  - P.pdf  Prescription   (always present — primary source for all 5 fields)
  - B.pdf  Bill           (always present — clean printed name / consultant / TID)
  - I.pdf  Investigation  (optional — lab reports)
  - D.pdf  Diagnosis      (optional — imaging / diagnosis report)
"""
from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from pdf2image import convert_from_path

# doc-type letter → human label, ordered by importance for extraction
DOC_LABELS: dict[str, str] = {
    "P": "PRESCRIPTION",
    "B": "BILL",
    "D": "DIAGNOSIS REPORT",
    "I": "INVESTIGATION REPORT",
}

_TID_RE = re.compile(r"^\s*(\d{6,})\b")


@dataclass(frozen=True)
class Case:
    """One patient case = one folder."""

    folder: Path
    tid: str           # leading numeric token of the folder name ("" if none)
    name: str          # remainder of the folder name
    docs: dict[str, Path] = field(default_factory=dict)  # letter -> pdf path

    @property
    def case_id(self) -> str:
        return self.folder.name


def _parse_folder_name(folder_name: str) -> tuple[str, str]:
    """'100000000000001 RAVI KUMAR' -> ('100000000000001', 'RAVI KUMAR')."""
    m = _TID_RE.match(folder_name)
    if m:
        tid = m.group(1)
        name = folder_name[m.end():].strip()
        return tid, name
    return "", folder_name.strip()


def discover_cases(root: Path) -> list[Case]:
    """Return every case folder under ``root`` that contains at least a P.pdf."""
    cases: list[Case] = []
    for sub in sorted(p for p in root.iterdir() if p.is_dir()):
        docs: dict[str, Path] = {}
        for pdf in sub.glob("*.pdf"):
            letter = pdf.stem.strip().upper()[:1]
            if letter in DOC_LABELS:
                docs[letter] = pdf
        if "P" not in docs:
            # No prescription — skip; nothing reliable to extract from.
            continue
        tid, name = _parse_folder_name(sub.name)
        cases.append(Case(folder=sub, tid=tid, name=name, docs=docs))
    return cases


@lru_cache(maxsize=256)
def _render_cached(path_str: str, dpi: int, max_pages: int, quality: int) -> tuple[bytes, ...]:
    pages = convert_from_path(path_str, dpi=dpi)
    out: list[bytes] = []
    for page in pages[:max_pages]:
        buf = io.BytesIO()
        page.save(buf, format="JPEG", quality=quality)
        out.append(buf.getvalue())
    return tuple(out)


def render_doc_pages(
    path: Path,
    *,
    dpi: int = 200,
    max_pages: int = 4,
    quality: int = 90,
) -> list[bytes]:
    """Rasterize the first ``max_pages`` pages of a PDF to JPEG bytes (cached)."""
    return list(_render_cached(str(path), dpi, max_pages, quality))


@lru_cache(maxsize=128)
def _render_region_cached(
    path_str: str, page_index: int, dpi: int, box: tuple[float, float, float, float], quality: int
) -> bytes | None:
    pages = convert_from_path(
        path_str, dpi=dpi, first_page=page_index + 1, last_page=page_index + 1
    )
    if not pages:
        return None
    pg = pages[0]
    w, h = pg.size
    left, top, right, bottom = box
    crop = pg.crop((int(w * left), int(h * top), int(w * right), int(h * bottom)))
    buf = io.BytesIO()
    crop.save(buf, format="JPEG", quality=quality)
    return buf.getvalue()


def render_region(
    path: Path,
    *,
    page_index: int = 0,
    dpi: int = 300,
    box: tuple[float, float, float, float] = (0.0, 0.55, 1.0, 1.0),
    quality: int = 92,
) -> bytes | None:
    """Rasterize a fractional crop of one page at high DPI (for hard-to-read regions).

    ``box`` is (left, top, right, bottom) as fractions of the page. Default = bottom 45%
    full width, where the RGHS "Review Date / After Day(s)" line and medication course live.
    """
    return _render_region_cached(str(path), page_index, dpi, box, quality)
