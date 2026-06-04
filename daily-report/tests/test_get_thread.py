"""get_thread 파싱 테스트(다건 메시지 + 비UTF-8 안전성).

스레드는 메시지와 별개의 진입점이므로, _parse_message 경유로 UTF-8 안전 처리가 스레드
읽기에도 적용됨을 고정한다. google 스택 import 필요 시 skip.
"""
import base64
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from gmail_client import GmailClient  # noqa: E402


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode()


def _msg(mid, body_bytes):
    return {
        "id": mid, "threadId": "t1", "labelIds": ["INBOX"], "snippet": "s",
        "payload": {"mimeType": "text/plain",
                    "headers": [{"name": "Subject", "value": f"S{mid}"}],
                    "body": {"data": _b64(body_bytes)}},
    }


class _ThreadGet:
    def execute(self):
        return {
            "id": "t1",
            "messages": [
                _msg("m1", "정상 본문".encode("utf-8")),
                _msg("m2", bytes([0xff, 0xfe]) + b"partial"),  # 비UTF-8 섞임
            ],
        }


class _Svc:
    def users(self):
        class _U:
            def threads(self):
                class _T:
                    def get(self, userId, id, format):
                        return _ThreadGet()
                return _T()
        return _U()


def test_get_thread_parses_all_messages_without_crash():
    c = GmailClient.__new__(GmailClient)
    c._service = _Svc()
    out = c.get_thread("t1")
    assert out["message_count"] == 2
    assert out["messages"][0]["body"] == "정상 본문"
    # 비UTF-8 메시지도 크래시 없이 문자열 본문을 가진다
    assert isinstance(out["messages"][1]["body"], str)
    assert "partial" in out["messages"][1]["body"]
