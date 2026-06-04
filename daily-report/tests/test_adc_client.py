"""ADCGmailClient.list_messages 커버리지(--adc 경로, 페이지네이션+max 트림).

google 스택 import 필요 시 skip. __init__(google.auth.default)는 우회한다.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from gmail_client import ADCGmailClient  # noqa: E402


class _ListExec:
    def __init__(self, pages, state):
        self.pages, self.state = pages, state

    def execute(self):
        i = self.state["i"]
        self.state["i"] += 1
        return self.pages[i]


class _Svc:
    def __init__(self, pages):
        self.pages, self.state = pages, {"i": 0}

    def users(self):
        svc = self

        class _U:
            def messages(self):
                class _M:
                    def list(self, **kwargs):
                        return _ListExec(svc.pages, svc.state)
                return _M()
        return _U()


def _client(pages):
    c = ADCGmailClient.__new__(ADCGmailClient)
    c._service = _Svc(pages)
    return c


def test_adc_follows_pagination():
    pages = [
        {"messages": [{"id": "1"}, {"id": "2"}], "nextPageToken": "t"},
        {"messages": [{"id": "3"}]},
    ]
    msgs = _client(pages).list_messages(max_results=20)
    assert [m["id"] for m in msgs] == ["1", "2", "3"]


def test_adc_trims_to_max_results():
    # 서버 초과 반환 → max_results 상한 강제(iter38 트림이 ADC 경로에도 적용)
    pages = [{"messages": [{"id": str(i)} for i in range(100)], "nextPageToken": "t"}]
    msgs = _client(pages).list_messages(max_results=5)
    assert len(msgs) == 5
