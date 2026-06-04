"""get_all_accounts 진입 로직 테스트(계정 탐색 회귀).

google 스택 import 필요 시 skip.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from gmail_client import get_all_accounts  # noqa: E402


def _accounts(tmp_path, names):
    acc = tmp_path / "accounts"
    acc.mkdir()
    for n in names:
        (acc / n).write_text("{}")
    return tmp_path


def test_missing_accounts_dir_returns_empty(tmp_path):
    assert get_all_accounts(tmp_path) == []


def test_lists_account_stems(tmp_path):
    base = _accounts(tmp_path, ["work.json", "personal.json"])
    assert sorted(get_all_accounts(base)) == ["personal", "work"]


def test_excludes_credentials(tmp_path):
    base = _accounts(tmp_path, ["work.json", "credentials.json"])
    assert get_all_accounts(base) == ["work"]


def test_ignores_non_json(tmp_path):
    base = _accounts(tmp_path, ["work.json"])
    (base / "accounts" / "notes.txt").write_text("x")
    (base / "accounts" / "config.yaml").write_text("x")
    assert get_all_accounts(base) == ["work"]
