"""batch_processor 의 청킹/집계 로직 테스트.

실제 Gmail 서비스 대신 콜백을 즉시 구동하는 페이크 서비스를 주입해, API/네트워크 없이
배치 분할·성공/실패 집계·진행 콜백·할당량 기록을 검증한다. 모듈 import 에는 google 스택이
필요하므로 없으면 skip 한다.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from core.batch_processor import BatchProcessor  # noqa: E402
from core.quota_manager import QuotaManager  # noqa: E402


class _Req:
    def __init__(self, msg_id):
        self.msg_id = msg_id


class _Messages:
    def get(self, userId, id, format):
        return _Req(id)

    def trash(self, userId, id):
        return _Req(id)

    def delete(self, userId, id):
        return _Req(id)


class _Users:
    def messages(self):
        return _Messages()


class _FakeBatch:
    """add() 로 등록된 콜백을, execute() 시 사전 정의된 결과로 구동."""

    def __init__(self, outcomes):
        self._outcomes = outcomes  # {msg_id: Exception | response}
        self._items = []

    def add(self, request, callback):
        self._items.append((request.msg_id, callback))

    def execute(self):
        for msg_id, cb in self._items:
            outcome = self._outcomes.get(msg_id, {"id": msg_id})
            if isinstance(outcome, Exception):
                cb(msg_id, None, outcome)
            else:
                cb(msg_id, outcome, None)


class _FakeService:
    def __init__(self, outcomes=None):
        self._outcomes = outcomes or {}

    def users(self):
        return _Users()

    def new_batch_http_request(self):
        return _FakeBatch(self._outcomes)


def _proc(outcomes=None, batch_size=50):
    return BatchProcessor(
        _FakeService(outcomes), quota_manager=QuotaManager(),
        user="t", batch_size=batch_size, delay_between_batches=0,
    )


def test_batch_size_floor_prevents_zero_step():
    # 회귀: batch_size<=0 이어도 ValueError 없이 1로 보정되어 동작한다.
    p = _proc(batch_size=0)
    assert p.batch_size == 1
    res = p.batch_get_messages(["m1", "m2"])
    assert res.total == 2 and res.succeeded == 2


def test_batch_size_capped_at_max():
    assert _proc(batch_size=1000).batch_size == 50


def test_batch_get_all_success():
    p = _proc()
    res = p.batch_get_messages(["m1", "m2", "m3"])
    assert res.total == 3
    assert res.succeeded == 3
    assert res.failed == 0
    assert len(res.results) == 3


def test_batch_get_mixed_success_and_failure():
    outcomes = {"m2": RuntimeError("not found")}
    p = _proc(outcomes)
    res = p.batch_get_messages(["m1", "m2", "m3"])
    assert res.succeeded == 2
    assert res.failed == 1
    assert res.errors[0]["message_id"] == "m2"
    assert "not found" in res.errors[0]["error"]


def test_chunking_across_multiple_batches_and_progress():
    p = _proc(batch_size=2)
    progress = []
    res = p.batch_get_messages(
        ["m1", "m2", "m3", "m4", "m5"],
        on_progress=lambda cur, total: progress.append((cur, total)),
    )
    assert res.total == 5 and res.succeeded == 5
    # 2,2,1 로 3개 배치 → 진행 콜백 3회, 마지막은 (5,5)
    assert progress == [(2, 5), (4, 5), (5, 5)]


def test_quota_is_recorded():
    p = _proc(batch_size=50)
    p.batch_get_messages(["m1", "m2"])
    usage = p.quota_manager.get_usage("t")
    assert usage["daily_units"] == 2 * 5  # MESSAGES_GET=5
