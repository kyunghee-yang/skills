"""라벨 CRUD 의 라벨 캐시 무효화 테스트(stale 회귀).

google 스택 import 필요 시 skip. 실제 EmailCache + 페이크 서비스로 검증.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from gmail_client import GmailClient  # noqa: E402
from core.cache_manager import EmailCache  # noqa: E402


class _Exec:
    def __init__(self, val):
        self._val = val

    def execute(self):
        return self._val


class _Labels:
    def create(self, userId, body):
        return _Exec({"id": "L1", "name": body["name"]})

    def get(self, userId, id):
        return _Exec({"id": id, "name": "old"})

    def update(self, userId, id, body):
        return _Exec({"id": id, "name": body.get("name", "old")})

    def delete(self, userId, id):
        return _Exec(None)


class _Svc:
    def users(self):
        class _U:
            def labels(self):
                return _Labels()
        return _U()


def _client(tmp_path):
    c = GmailClient.__new__(GmailClient)
    c._cache = EmailCache(cache_dir=str(tmp_path))
    c._quota_manager = None
    c._service = _Svc()
    c.account_name = "acc"
    return c


def _seed_labels(c):
    c._cache.set_labels("acc", [{"id": "INBOX", "name": "INBOX"}])
    assert c._cache.get_labels("acc") is not None


def test_create_label_invalidates_cache(tmp_path):
    c = _client(tmp_path)
    _seed_labels(c)
    c.create_label("새라벨")
    assert c._cache.get_labels("acc") is None


def test_update_label_invalidates_cache(tmp_path):
    c = _client(tmp_path)
    _seed_labels(c)
    c.update_label("L1", name="변경")
    assert c._cache.get_labels("acc") is None


def test_delete_label_invalidates_cache(tmp_path):
    c = _client(tmp_path)
    _seed_labels(c)
    c.delete_label("L1")
    assert c._cache.get_labels("acc") is None
