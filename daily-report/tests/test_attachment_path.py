"""read_message._safe_attachment_path 경로 탈출 방지 테스트.

read_message 는 google 스택을 import 하므로 없으면 skip.
"""
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from read_message import _safe_attachment_path  # noqa: E402


def _contained(save_dir: Path, filename: str) -> bool:
    p = _safe_attachment_path(save_dir, filename).resolve()
    return str(p).startswith(str(save_dir.resolve()) + os.sep)


def test_normal_filename(tmp_path):
    p = _safe_attachment_path(tmp_path, "report.pdf")
    assert p == tmp_path / "report.pdf"


def test_parent_traversal_is_contained(tmp_path):
    assert _contained(tmp_path, "../../../tmp/evil.txt")
    assert _safe_attachment_path(tmp_path, "../../etc/passwd").name == "passwd"


def test_absolute_path_is_contained(tmp_path):
    assert _contained(tmp_path, "/etc/passwd")
    assert _safe_attachment_path(tmp_path, "/etc/passwd") == tmp_path / "passwd"


def test_dotdot_and_empty_fallback(tmp_path):
    assert _safe_attachment_path(tmp_path, "..").name == "attachment"
    assert _safe_attachment_path(tmp_path, "").name == "attachment"


def test_nested_path_keeps_basename(tmp_path):
    assert _safe_attachment_path(tmp_path, "a/b/c/doc.txt") == tmp_path / "doc.txt"
