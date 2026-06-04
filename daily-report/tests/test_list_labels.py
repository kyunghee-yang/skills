"""list_labels 캐싱+정형 로직 커버리지(read-path)."""
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


class _Svc:
    def __init__(self, labels, counter):
        self._labels, self._counter = labels, counter

    def users(self):
        svc = self

        class _U:
            def labels(self):
                class _L:
                    def list(self, userId):
                        svc._counter["n"] += 1
                        return _Exec({"labels": svc._labels})
                return _L()
        return _U()


def _client(tmp_path, labels, counter):
    c = GmailClient.__new__(GmailClient)
    c._service = _Svc(labels, counter)
    c._quota_manager = None
    c._cache = EmailCache(cache_dir=str(tmp_path))
    c.account_name = "acc"
    return c


def test_list_labels_fetches_shapes_and_caches(tmp_path):
    counter = {"n": 0}
    raw = [{"id": "INBOX", "name": "INBOX", "type": "system",
            "messageListVisibility": "show", "labelListVisibility": "labelShow"}]
    c = _client(tmp_path, raw, counter)
    out = c.list_labels()
    assert out[0]["id"] == "INBOX" and out[0]["name"] == "INBOX"
    assert out[0]["message_list_visibility"] == "show"
    assert counter["n"] == 1
    # 캐시에 저장됐는지
    assert c._cache.get_labels("acc") is not None


def test_list_labels_cache_hit_skips_api(tmp_path):
    counter = {"n": 0}
    c = _client(tmp_path, [{"id": "X", "name": "X"}], counter)
    c.list_labels()                 # 1차: API 호출 + 캐시
    assert counter["n"] == 1
    c.list_labels()                 # 2차: 캐시 히트 → API 미호출
    assert counter["n"] == 1


def test_list_labels_no_cache_when_disabled(tmp_path):
    counter = {"n": 0}
    c = _client(tmp_path, [{"id": "X", "name": "X"}], counter)
    c.list_labels(use_cache=False)
    c.list_labels(use_cache=False)
    assert counter["n"] == 2        # 캐시 미사용 → 매번 API
