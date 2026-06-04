"""main.py 진입점 헬퍼(_extract_year_month, _find_xls)의 엣지케이스.

기존 test_main 은 run_pipeline 정상 경로만 검증하므로, 폴더명/파일 탐색의 에러 경로를
직접 고정한다(동작 변경 없는 회귀 방지 커버리지).
"""
import os

import pytest

from expense_report.main import _extract_year_month, _find_xls


# --- _extract_year_month ---

def test_extract_year_month_basic():
    assert _extract_year_month("/some/path/202603") == ("26", "03")


def test_extract_year_month_trailing_slash():
    assert _extract_year_month("/some/path/202512/") == ("25", "12")


def test_extract_year_month_rejects_non_six_digits():
    for bad in ["/p/2026", "/p/20260301", "/p/abcdef", "/p/march"]:
        with pytest.raises(ValueError):
            _extract_year_month(bad)


# --- _find_xls ---

def test_find_xls_returns_xls(tmp_path):
    (tmp_path / "간편서비스_승인내역.xls").write_text("x")
    found = _find_xls(str(tmp_path))
    assert found.endswith(".xls")


def test_find_xls_ignores_xlsx_and_dotfiles(tmp_path):
    (tmp_path / "결의서.xlsx").write_text("x")     # .xlsx 는 대상 아님
    (tmp_path / ".hidden.xls").write_text("x")      # dotfile 제외
    with pytest.raises(FileNotFoundError):
        _find_xls(str(tmp_path))


def test_find_xls_raises_when_absent(tmp_path):
    with pytest.raises(FileNotFoundError):
        _find_xls(str(tmp_path))


def test_find_xls_picks_real_xls_among_xlsx(tmp_path):
    (tmp_path / "결의서.xlsx").write_text("x")
    (tmp_path / "승인내역.xls").write_text("x")
    assert _find_xls(str(tmp_path)).endswith("승인내역.xls")
