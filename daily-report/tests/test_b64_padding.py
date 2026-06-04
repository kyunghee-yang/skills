"""base64url 패딩 보정 테스트(Gmail 본문/첨부 패딩 누락 회귀).

google 스택 import 필요 시 skip. GmailClient.__new__ 로 __init__ 우회.
"""
import base64
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from gmail_client import GmailClient, _b64url_decode  # noqa: E402


def test_b64url_decode_handles_missing_padding():
    # 'Hello' = 'SGVsbG8=' → 패딩 제거해도 동일하게 디코딩
    assert _b64url_decode("SGVsbG8") == b"Hello"
    assert _b64url_decode("SGVsbG8=") == b"Hello"


def test_b64url_decode_various_lengths():
    for s in ["A", "AB", "ABC", "ABCD", "안녕하세요 세계"]:
        enc = base64.urlsafe_b64encode(s.encode()).decode().rstrip("=")  # 패딩 제거
        assert _b64url_decode(enc).decode() == s


def test_extract_body_unpadded_does_not_crash():
    c = GmailClient.__new__(GmailClient)
    # 패딩 없는 본문 data
    payload = {"mimeType": "text/plain", "body": {"data": "SGVsbG8"}}
    body, att = c._extract_body_and_attachments(payload, "mid")
    assert body == "Hello"
