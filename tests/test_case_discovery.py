"""Unit tests for case folder-name parsing and discovery (no API, no rendering)."""
import pytest

from src.utils.case_discovery import Case, _parse_folder_name, discover_cases


# Synthetic fixtures (no real PHI): exercise leading-TID parsing, multi-word names,
# and the no-TID (name-only) folder shape.
@pytest.mark.parametrize(
    "folder, tid, name",
    [
        ("100000000000001 RAVI KUMAR", "100000000000001", "RAVI KUMAR"),
        ("1000000000000022 MOHAN LAL VERMA", "1000000000000022", "MOHAN LAL VERMA"),
        ("100000000000003 ANITA DEVI SHARMA", "100000000000003", "ANITA DEVI SHARMA"),
        ("Meena devi", "", "Meena devi"),
        ("alpha", "", "alpha"),
    ],
)
def test_parse_folder_name(folder, tid, name):
    assert _parse_folder_name(folder) == (tid, name)


def test_discover_cases_requires_prescription(tmp_path):
    # case A: has P + B -> discovered
    a = tmp_path / "111111 ALPHA"
    a.mkdir()
    (a / "P.pdf").write_bytes(b"%PDF-1.4")
    (a / "B.pdf").write_bytes(b"%PDF-1.4")
    # case B: only a bill, no prescription -> skipped
    b = tmp_path / "222222 BETA"
    b.mkdir()
    (b / "B.pdf").write_bytes(b"%PDF-1.4")

    cases = discover_cases(tmp_path)
    ids = {c.case_id for c in cases}
    assert ids == {"111111 ALPHA"}
    case = cases[0]
    assert case.tid == "111111"
    assert sorted(case.docs) == ["B", "P"]


def test_case_is_frozen():
    c = Case(folder=None, tid="1", name="X")  # type: ignore[arg-type]
    with pytest.raises(Exception):
        c.tid = "2"  # type: ignore[misc]
