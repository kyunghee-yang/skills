"""modify_message 의 캐시 무효화 테스트(목록 캐시 stale 회귀).

google 스택 import 필요 시 skip. 실제 EmailCache + 페이크 서비스로 검증.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from gmail_client import GmailClient  # noqa: E402
from core.cache_manager import EmailCache  # noqa: E402


class _Modify:
    def __init__(self, mid):
        self.mid = mid

    def execute(self):
        return {"id": self.mid, "threadId": "t1", "labelIds": ["INBOX"]}


class _Svc:
    def users(self):
        class _U:
            def messages(self):
                class _M:
                    def modify(self, userId, id, body):
                        return _Modify(id)
                return _M()
        return _U()


def _client(tmp_path):
    c = GmailClient.__new__(GmailClient)
    c._cache = EmailCache(cache_dir=str(tmp_path))
    c._quota_manager = None
    c._service = _Svc()
    c.account_name = "acc"
    return c


def test_modify_invalidates_message_and_list_cache(tmp_path):
    c = _client(tmp_path)
    # 메시지 캐시와 목록 캐시를 미리 채운다
    c._cache.set_message("acc", "m1", {"id": "m1", "body": "x"})
    c._cache.set_list("acc", "is:unread", [{"id": "m1"}])
    assert c._cache.get_message("acc", "m1") is not None
    assert c._cache.get_list("acc", "is:unread") is not None

    c.modify_message("m1", remove_label_ids=["UNREAD"])

    # 회귀: 라벨 변경 후 메시지·목록 캐시 모두 무효화돼야 한다
    assert c._cache.get_message("acc", "m1") is None
    assert c._cache.get_list("acc", "is:unread") is None
