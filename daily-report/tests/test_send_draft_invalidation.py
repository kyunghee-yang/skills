"""send_draft 의 목록 캐시 무효화 테스트.

google 스택 import 필요 시 skip. 실제 EmailCache + 페이크 서비스로 검증.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from gmail_client import GmailClient  # noqa: E402
from core.cache_manager import EmailCache  # noqa: E402


class _Send:
    def execute(self):
        return {"id": "m1", "threadId": "t1", "labelIds": ["SENT"]}


class _Svc:
    def users(self):
        class _U:
            def drafts(self):
                class _D:
                    def send(self, userId, body):
                        return _Send()
                return _D()
        return _U()


def test_send_draft_invalidates_list_cache(tmp_path):
    c = GmailClient.__new__(GmailClient)
    c._cache = EmailCache(cache_dir=str(tmp_path))
    c._quota_manager = None
    c._service = _Svc()
    c.account_name = "acc"

    c._cache.set_list("acc", "in:sent", [{"id": "old"}])
    assert c._cache.get_list("acc", "in:sent") is not None

    c.send_draft("d1")

    assert c._cache.get_list("acc", "in:sent") is None
