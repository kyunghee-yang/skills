"""gmail_client._attach_file 의 첨부 처리 테스트(네트워크 불필요).

모듈 import 에 google 스택이 필요하므로 없으면 skip. GmailClient.__new__ 로 __init__ 우회.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from email.mime.multipart import MIMEMultipart  # noqa: E402

from gmail_client import GmailClient  # noqa: E402


def _attach(tmp_path, name, content_bytes):
    c = GmailClient.__new__(GmailClient)
    p = tmp_path / name
    p.write_bytes(content_bytes)
    msg = MIMEMultipart()
    c._attach_file(msg, str(p))
    return msg


def test_attach_utf8_text(tmp_path):
    msg = _attach(tmp_path, "note.txt", "안녕".encode("utf-8"))
    parts = msg.get_payload()
    assert len(parts) == 1
    assert parts[0].get_content_type() == "text/plain"
    assert parts[0].get_filename() == "note.txt"


def test_attach_non_utf8_text_does_not_crash(tmp_path):
    # 회귀: 비UTF-8 텍스트 파일도 크래시 없이 첨부된다(바이너리 폴백).
    msg = _attach(tmp_path, "latin.txt", bytes([0xff, 0xfe]) + b"hi")
    parts = msg.get_payload()
    assert len(parts) == 1
    assert parts[0].get_filename() == "latin.txt"


def test_attach_binary_file(tmp_path):
    msg = _attach(tmp_path, "blob.bin", bytes(range(256)))
    parts = msg.get_payload()
    assert len(parts) == 1
    # 알 수 없는 타입은 application/octet-stream 으로 처리
    assert parts[0].get_content_type() == "application/octet-stream"
