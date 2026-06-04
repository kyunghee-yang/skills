"""list_messages 페이지네이션/캐시 테스트.

외부 조사(Google list-messages: maxResults 는 페이지 크기일 뿐, nextPageToken 을 따라야 함)
반영: 짧은 페이지/빈 페이지+토큰/캐시 히트를 페이크 서비스로 검증한다. google 스택 import 필요 시 skip.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from gmail_client import GmailClient  # noqa: E402
from core.cache_manager import EmailCache  # noqa: E402


class _ListExec:
    def __init__(self, pages, state):
        self.pages = pages
        self.state = state

    def execute(self):
        i = self.state["i"]
        self.state["i"] += 1
        return self.pages[i]


class _Svc:
    def __init__(self, pages):
        self.pages = pages
        self.state = {"i": 0}

    def users(self):
        svc = self

        class _U:
            def messages(self):
                class _M:
                    def list(self, **kwargs):
                        return _ListExec(svc.pages, svc.state)
                return _M()
        return _U()


def _client(pages, tmp_path, cache=False):
    c = GmailClient.__new__(GmailClient)
    c._service = _Svc(pages)
    c._quota_manager = None
    c._cache = EmailCache(cache_dir=str(tmp_path)) if cache else None
    c.account_name = "acc"
    return c


def test_follows_next_page_token_across_short_pages(tmp_path):
    # page1: 2건 + 토큰, page2: 1건(짧음) + 토큰 없음 → 총 3건
    pages = [
        {"messages": [{"id": "1"}, {"id": "2"}], "nextPageToken": "t1"},
        {"messages": [{"id": "3"}]},
    ]
    msgs = _client(pages, tmp_path).list_messages(max_results=20)
    assert [m["id"] for m in msgs] == ["1", "2", "3"]


def test_empty_page_with_token_then_more(tmp_path):
    # 빈 페이지 + 토큰 → 계속 진행해야 함(maxResults 는 보장 개수가 아님)
    pages = [
        {"messages": [], "nextPageToken": "t1"},
        {"messages": [{"id": "9"}]},
    ]
    msgs = _client(pages, tmp_path).list_messages(max_results=20)
    assert [m["id"] for m in msgs] == ["9"]


def test_stops_at_max_results(tmp_path):
    pages = [{"messages": [{"id": str(i)} for i in range(100)], "nextPageToken": "t1"}]
    msgs = _client(pages, tmp_path).list_messages(max_results=5)
    assert len(msgs) == 5


def test_cache_hit_returns_without_api(tmp_path):
    c = _client([], tmp_path, cache=True)
    c._cache.set_list("acc", "q", [{"id": "c1"}, {"id": "c2"}])
    # 캐시 히트 → 서비스 호출 없이 반환(빈 pages라 API 호출 시 IndexError 날 것)
    msgs = c.list_messages(query="q", max_results=20)
    assert [m["id"] for m in msgs] == ["c1", "c2"]
