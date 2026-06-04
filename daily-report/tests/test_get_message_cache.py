"""get_message 의 캐시 상호작용 테스트(metadata/full 오염 회귀).

google 스택 import 필요 시 skip. 실제 EmailCache + 페이크 서비스로 네트워크 없이 검증.
"""
import base64
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from gmail_client import GmailClient  # noqa: E402
from core.cache_manager import EmailCache  # noqa: E402


def _b64(s: str) -> str:
    return base64.urlsafe_b64encode(s.encode()).decode()


class _Get:
    def __init__(self, fmt):
        self.fmt = fmt

    def execute(self):
        body = {} if self.fmt == "metadata" else {"data": _b64("FULL BODY")}
        return {
            "id": "m1", "threadId": "t1", "labelIds": ["INBOX"], "snippet": "s",
            "payload": {"mimeType": "text/plain",
                        "headers": [{"name": "Subject", "value": "S"}], "body": body},
        }


class _Svc:
    def users(self):
        class _U:
            def messages(self):
                class _M:
                    def get(self, userId, id, format):
                        return _Get(format)
                return _M()
        return _U()


def _client(tmp_path):
    c = GmailClient.__new__(GmailClient)
    c._cache = EmailCache(cache_dir=str(tmp_path))
    c._quota_manager = None
    c._service = _Svc()
    c.account_name = "acc"
    return c


def test_metadata_then_full_returns_full_body(tmp_path):
    # 회귀: metadata 조회가 full 캐시를 오염시키면 안 된다.
    c = _client(tmp_path)
    assert c.get_message("m1", format="metadata")["body"] == ""   # metadata엔 본문 없음
    assert c.get_message("m1", format="full")["body"] == "FULL BODY"


def test_full_then_metadata_served_from_full_cache(tmp_path):
    c = _client(tmp_path)
    assert c.get_message("m1", format="full")["body"] == "FULL BODY"
    # metadata 요청은 full 캐시(상위집합)로 충족 — 본문 포함되어도 무방
    assert c.get_message("m1", format="metadata")["body"] == "FULL BODY"


def test_full_body_is_cached(tmp_path):
    c = _client(tmp_path)
    c.get_message("m1", format="full")
    cached = c._cache.get_message("acc", "m1")
    assert cached is not None and cached["body"] == "FULL BODY"


def test_metadata_request_hits_full_cache_within_24h(tmp_path):
    # 회귀: full 캐시를 1~24h 사이에 metadata 로 조회해도 캐시 히트(재요청 안 함)
    import json
    from datetime import datetime, timedelta
    c = _client(tmp_path)
    c.get_message("m1", format="full")  # full 캐시 저장
    # cached_at 을 2시간 전으로 (메타 TTL 1h 초과, 메시지 TTL 24h 이내)
    p = c._cache._message_path("acc", "m1")
    data = json.load(open(p)); data["cached_at"] = (datetime.now() - timedelta(hours=2)).isoformat()
    json.dump(data, open(p, "w"))
    # metadata 조회 → 캐시된 full(본문 포함) 반환(빈 본문 메타 재요청 아님)
    out = c.get_message("m1", format="metadata")
    assert out["body"] == "FULL BODY"
