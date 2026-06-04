"""gmail_client 의 순수 파싱 로직(_parse_message, _extract_body_and_attachments) 테스트.

API/네트워크 없이 합성 메시지 dict 로 검증한다. __init__(자격증명 로드)을 우회하기 위해
GmailClient.__new__ 로 인스턴스를 만든다. 모듈 import 에는 google 스택이 필요하다.
"""
import base64
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

google = pytest.importorskip("googleapiclient")  # google 스택 없으면 skip
from gmail_client import GmailClient  # noqa: E402


def _client():
    return GmailClient.__new__(GmailClient)  # __init__ 우회


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode()


def test_extract_plain_body_utf8():
    c = _client()
    payload = {"mimeType": "text/plain", "body": {"data": _b64("안녕하세요".encode("utf-8"))}}
    body, att = c._extract_body_and_attachments(payload, "mid")
    assert body == "안녕하세요"
    assert att == []


def test_extract_non_utf8_body_does_not_crash():
    # 회귀: 비UTF-8 바이트가 섞여도 UnicodeDecodeError 없이 본문을 돌려준다.
    c = _client()
    payload = {"mimeType": "text/plain", "body": {"data": _b64(bytes([0xff, 0xfe, 0x41]))}}
    body, att = c._extract_body_and_attachments(payload, "mid")
    assert isinstance(body, str)  # 크래시 없이 문자열 반환
    assert "A" in body            # 유효 바이트는 보존


def test_extract_attachment_metadata():
    c = _client()
    payload = {
        "mimeType": "image/png",
        "filename": "photo.png",
        "body": {"size": 1234, "attachmentId": "att1"},
    }
    body, att = c._extract_body_and_attachments(payload, "mid")
    assert body == ""
    assert att == [{"filename": "photo.png", "mime_type": "image/png",
                    "size": 1234, "attachment_id": "att1"}]


def test_extract_multipart_collects_body_and_attachments():
    c = _client()
    payload = {
        "mimeType": "multipart/mixed",
        "parts": [
            {"mimeType": "text/plain", "body": {"data": _b64("hello".encode())}},
            {"mimeType": "application/pdf", "filename": "doc.pdf",
             "body": {"size": 10, "attachmentId": "a2"}},
        ],
    }
    body, att = c._extract_body_and_attachments(payload, "mid")
    assert body == "hello"
    assert len(att) == 1 and att[0]["filename"] == "doc.pdf"


def test_parse_message_fills_defaults_and_headers():
    c = _client()
    msg = {
        "id": "m1", "threadId": "t1", "labelIds": ["INBOX"], "snippet": "snip",
        "payload": {
            "mimeType": "text/plain",
            "headers": [
                {"name": "From", "value": "a@b.com"},
                {"name": "Subject", "value": "제목"},
            ],
            "body": {"data": _b64("본문".encode())},
        },
    }
    out = c._parse_message(msg)
    assert out["from"] == "a@b.com"
    assert out["subject"] == "제목"
    assert out["body"] == "본문"
    assert out["cc"] == ""              # 누락 헤더 기본값
    assert out["label_ids"] == ["INBOX"]


def test_parse_message_default_subject_when_missing():
    c = _client()
    msg = {"id": "m1", "threadId": "t1",
           "payload": {"mimeType": "text/plain", "headers": [], "body": {}}}
    out = c._parse_message(msg)
    assert out["subject"] == "(제목 없음)"


def test_snippet_is_html_unescaped():
    c = _client()
    msg = {"id": "m1", "threadId": "t1",
           "payload": {"mimeType": "text/plain", "headers": [],
                       "body": {}},
           "snippet": "Tom&#39;s &quot;report&quot; &amp; notes"}
    out = c._parse_message(msg)
    assert out["snippet"] == 'Tom\'s "report" & notes'
