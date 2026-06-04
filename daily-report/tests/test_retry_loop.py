"""retry_handler 재시도 루프 동작 테스트(exponential_backoff / RetryableOperation).

google 스택 import 필요 시 skip. base_delay=0 으로 실제 sleep 을 없앤다.
"""
import importlib.util
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "gmail", "scripts"))

pytest.importorskip("googleapiclient")
from googleapiclient.errors import HttpError  # noqa: E402

_MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "gmail", "scripts", "core", "retry_handler.py"
)
spec = importlib.util.spec_from_file_location("rh_loop", _MODULE_PATH)
rh = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rh)


class _Resp:
    def __init__(self, status):
        self.status = status
        self.reason = "x"


def _http_error(status):
    return HttpError(_Resp(status), b"{}")


def test_is_retryable_error():
    assert rh.is_retryable_error(_http_error(429)) is True
    assert rh.is_retryable_error(_http_error(503)) is True
    assert rh.is_retryable_error(_http_error(400)) is False
    assert rh.is_retryable_error(ValueError("x")) is False


def test_backoff_retries_then_succeeds():
    calls = {"n": 0}

    @rh.exponential_backoff(max_retries=5, base_delay=0, jitter=False)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 3:
            raise _http_error(429)
        return "ok"

    assert flaky() == "ok"
    assert calls["n"] == 3  # 2회 실패 후 3번째 성공


def test_backoff_non_retryable_raises_immediately():
    calls = {"n": 0}

    @rh.exponential_backoff(max_retries=5, base_delay=0)
    def bad():
        calls["n"] += 1
        raise _http_error(400)  # 재시도 불가

    with pytest.raises(HttpError):
        bad()
    assert calls["n"] == 1  # 재시도 없이 1회만


def test_backoff_exhausts_retries():
    calls = {"n": 0}

    @rh.exponential_backoff(max_retries=2, base_delay=0, jitter=False)
    def always_429():
        calls["n"] += 1
        raise _http_error(429)

    with pytest.raises(HttpError):
        always_429()
    assert calls["n"] == 3  # 최초 1 + 재시도 2


def test_retryable_operation_execute_succeeds_after_retry():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _http_error(503)
        return "done"

    op = rh.RetryableOperation(max_retries=3, base_delay=0, jitter=False)
    assert op.execute(flaky) == "done"
    assert calls["n"] == 2


def test_retry_after_header_used_in_backoff(monkeypatch):
    # Retry-After 가 있으면 calculate_delay 대신 그 값(여기선 0)을 쓴다 → 크래시 없이 재시도
    calls = {"n": 0}
    slept = []
    monkeypatch.setattr(rh.time, "sleep", lambda s: slept.append(s))

    class _RespRA(dict):
        status = 429
        reason = "x"

    def _err():
        e = HttpError(_RespRA({"retry-after": "0"}), b"{}")
        return e

    @rh.exponential_backoff(max_retries=2, base_delay=99, jitter=False)
    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise _err()
        return "ok"

    assert flaky() == "ok"
    # Retry-After=0 이 base_delay=99 대신 쓰여 0초 대기
    assert slept and slept[0] == 0
