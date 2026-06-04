"""send_message 의 MIME 구성 테스트(네트워크 없이 raw 캡처·디코드).

google 스택 import 필요 시 skip. 페이크 서비스가 send body 의 raw 를 캡처하면, 이를
디코드해 헤더/본문/구조를 검증한다(분기: html/plain, cc/bcc, reply-to, threadId).
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


class _Capture:
    def __init__(self, store):
        self.store = store

    def execute(self):
        return {"id": "m1", "threadId": "t1", "labelIds": ["SENT"]}


class _Svc:
    def __init__(self, store):
        self.store = store

    def users(self):
        store = self.store

        class _U:
            def messages(self):
                class _M:
                    def send(self, userId, body):
                        store["body"] = body
                        return _Capture(store)
                return _M()
        return _U()


def _send(**kwargs):
    store = {}
    c = GmailClient.__new__(GmailClient)
    c._service = _Svc(store)
    c._quota_manager = None
    c._cache = None
    c.account_name = "acc"
    result = c.send_message(**kwargs)
    raw = store["body"]["raw"]
    msg = email.message_from_bytes(base64.urlsafe_b64decode(raw))
    return result, store["body"], msg


def _hdr(msg, name):
    """RFC2047 인코딩된 헤더를 디코드해 반환."""
    return str(make_header(decode_header(msg[name])))


def test_plain_message_headers():
    _, body, msg = _send(to="a@b.com", subject="제목", body="본문")
    assert msg["to"] == "a@b.com"
    assert _hdr(msg, "subject") == "제목"  # 비ASCII는 RFC2047 인코딩 → 디코드 비교
    assert "threadId" not in body  # thread_id 미지정


def test_cc_bcc_and_reply_headers():
    _, _, msg = _send(to="a@b.com", subject="s", body="b",
                      cc="c@b.com", bcc="d@b.com", reply_to_message_id="<m99>")
    assert msg["cc"] == "c@b.com"
    assert msg["bcc"] == "d@b.com"
    assert msg["In-Reply-To"] == "<m99>"
    assert msg["References"] == "<m99>"


def test_html_subtype():
    _, _, msg = _send(to="a@b.com", subject="s", body="<b>hi</b>", html=True)
    assert msg.get_content_subtype() == "html"


def test_thread_id_passed_in_body():
    _, body, _ = _send(to="a@b.com", subject="s", body="b", thread_id="t1")
    assert body["threadId"] == "t1"


def test_attachments_make_multipart(tmp_path):
    f = tmp_path / "a.txt"
    f.write_text("file content", encoding="utf-8")
    _, _, msg = _send(to="a@b.com", subject="s", body="b", attachments=[str(f)])
    assert msg.is_multipart()
    names = [p.get_filename() for p in msg.get_payload() if p.get_filename()]
    assert "a.txt" in names
