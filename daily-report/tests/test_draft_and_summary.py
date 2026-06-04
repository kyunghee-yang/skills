"""create_draft MIME 구성 + format_message_summary 잘림 로직 테스트.

google 스택 import 필요 시 skip. 네트워크 없이 페이크 서비스/스텁으로 검증.
"""
import base64
import email
import os
import sys
from email.header import decode_header, make_header

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from gmail_client import GmailClient  # noqa: E402
import list_messages  # noqa: E402


# ---------- create_draft ----------

class _DraftCreate:
    def __init__(self, store, body):
        store["body"] = body

    def execute(self):
        return {"id": "d1", "message": {"id": "m1"}}


class _DraftSvc:
    def __init__(self, store):
        self.store = store

    def users(self):
        store = self.store

        class _U:
            def drafts(self):
                class _D:
                    def create(self, userId, body):
                        return _DraftCreate(store, body)
                return _D()
        return _U()


def _hdr(msg, name):
    return str(make_header(decode_header(msg[name])))


def test_create_draft_builds_mime_with_headers():
    store = {}
    c = GmailClient.__new__(GmailClient)
    c._service = _DraftSvc(store)
    out = c.create_draft(to="a@b.com", subject="안녕", body="본문", cc="c@b.com")
    assert out["status"] == "created"
    raw = store["body"]["message"]["raw"]
    msg = email.message_from_bytes(base64.urlsafe_b64decode(raw))
    assert msg["to"] == "a@b.com"
    assert msg["cc"] == "c@b.com"
    assert _hdr(msg, "subject") == "안녕"


# ---------- format_message_summary ----------

class _StubClient:
    def __init__(self, msg):
        self._msg = msg

    def get_message(self, msg_id, format="metadata"):
        return self._msg


def _summary(snippet):
    msg = {"id": "m1", "from": "a@b.com", "subject": "S", "date": "D",
           "snippet": snippet, "label_ids": ["INBOX"]}
    return list_messages.format_message_summary(_StubClient(msg), "m1")


def test_summary_short_snippet_unchanged():
    out = _summary("짧은 스니펫")
    assert out["snippet"] == "짧은 스니펫"
    assert out["from"] == "a@b.com"
    assert out["labels"] == ["INBOX"]


def test_summary_long_snippet_truncated():
    long = "x" * 150
    out = _summary(long)
    assert out["snippet"] == "x" * 100 + "..."


def test_summary_exactly_100_not_truncated():
    s = "y" * 100
    out = _summary(s)
    assert out["snippet"] == s  # 100자는 그대로(>100 일 때만 잘림)
