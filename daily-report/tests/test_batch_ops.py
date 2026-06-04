"""batch_processor 나머지 연산 커버리지(batch_modify_labels / batch_trash / mark_all_as_read)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from core.batch_processor import BatchProcessor  # noqa: E402
from core.quota_manager import QuotaManager  # noqa: E402


class _Exec:
    def __init__(self, result=None, raise_exc=None):
        self._result, self._raise = result, raise_exc

    def execute(self):
        if self._raise:
            raise self._raise
        return self._result


class _Req:
    def __init__(self, mid):
        self.mid = mid


class _FakeBatch:
    def __init__(self, outcomes):
        self._outcomes, self._items = outcomes, []

    def add(self, request, callback):
        self._items.append((request.mid, callback))

    def execute(self):
        for mid, cb in self._items:
            o = self._outcomes.get(mid, {"id": mid})
            cb(mid, None, o) if isinstance(o, Exception) else cb(mid, o, None)


class _Messages:
    def __init__(self, svc):
        self.svc = svc

    def batchModify(self, userId, body):
        self.svc.batch_modify_calls.append(body)
        if self.svc.modify_raise:
            return _Exec(raise_exc=self.svc.modify_raise)
        return _Exec(result={})

    def trash(self, userId, id):
        return _Req(id)

    def list(self, **kwargs):
        i = self.svc.list_state["i"]; self.svc.list_state["i"] += 1
        return _Exec(result=self.svc.list_pages[i])


class _FakeService:
    def __init__(self, outcomes=None, list_pages=None, modify_raise=None):
        self.outcomes = outcomes or {}
        self.list_pages = list_pages or []
        self.list_state = {"i": 0}
        self.modify_raise = modify_raise
        self.batch_modify_calls = []

    def users(self):
        svc = self

        class _U:
            def messages(self):
                return _Messages(svc)
        return _U()

    def new_batch_http_request(self):
        return _FakeBatch(self.outcomes)


def _proc(svc, batch_size=50):
    return BatchProcessor(svc, quota_manager=QuotaManager(), user="t",
                          batch_size=batch_size, delay_between_batches=0)


def test_batch_modify_labels_success():
    svc = _FakeService()
    res = _proc(svc).batch_modify_labels(["1", "2", "3"], add_labels=["STARRED"])
    assert res.succeeded == 3 and res.failed == 0
    assert svc.batch_modify_calls[0]["addLabelIds"] == ["STARRED"]
    assert svc.batch_modify_calls[0]["ids"] == ["1", "2", "3"]


def test_batch_modify_labels_failure_recorded():
    svc = _FakeService(modify_raise=RuntimeError("boom"))
    res = _proc(svc).batch_modify_labels(["1", "2"], remove_labels=["UNREAD"])
    assert res.succeeded == 0 and res.failed == 2
    assert "boom" in res.errors[0]["error"]


def test_batch_trash_aggregates():
    svc = _FakeService(outcomes={"2": RuntimeError("nope")})
    res = _proc(svc).batch_trash_messages(["1", "2", "3"])
    assert res.succeeded == 2 and res.failed == 1


def test_mark_all_as_read_paginates_then_modifies():
    # list 2페이지 → 3개 id 수집 → batch_modify_labels(remove UNREAD)
    svc = _FakeService(list_pages=[
        {"messages": [{"id": "1"}, {"id": "2"}], "nextPageToken": "t"},
        {"messages": [{"id": "3"}]},
    ])
    res = _proc(svc).mark_all_as_read(max_messages=500)
    assert res.succeeded == 3
    assert svc.batch_modify_calls[0]["removeLabelIds"] == ["UNREAD"]
    assert svc.batch_modify_calls[0]["ids"] == ["1", "2", "3"]


def test_mark_all_as_read_empty_returns_empty():
    svc = _FakeService(list_pages=[{"messages": []}])
    res = _proc(svc).mark_all_as_read()
    assert res.total == 0 and res.succeeded == 0
