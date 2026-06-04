"""quota_manager 단위 테스트.

core/__init__.py 의 무거운 import 를 피하기 위해 모듈을 파일 경로로 직접 로드한다.
quota_manager 는 순수 stdlib 라 외부 의존성이 없다.
"""
import importlib.util
import os
from datetime import datetime, timedelta

_MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "gmail", "scripts", "core", "quota_manager.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("quota_manager_under_test", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


qm = _load()
USER = "user@example.com"


def _mgr(**kw):
    return qm.QuotaManager(**kw)


def test_can_execute_within_limit():
    m = _mgr(rate_limit=250)
    assert m.can_execute(USER, 100) is True


def test_can_execute_rejects_over_limit():
    m = _mgr(rate_limit=250)
    m.record_usage(USER, 200)
    assert m.can_execute(USER, 100) is False  # 200+100 > 250
    assert m.can_execute(USER, 50) is True     # 200+50 == 250


def test_record_usage_accumulates_rate_and_daily():
    m = _mgr()
    m.record_usage(USER, 5)
    m.record_usage(USER, 10)
    u = m.get_usage(USER)
    assert u["units_used"] == 15
    assert u["daily_units"] == 15


def test_get_remaining_rate():
    m = _mgr(rate_limit=250)
    m.record_usage(USER, 60)
    assert m.get_remaining_rate(USER) == 190


def test_get_remaining_rate_never_negative():
    m = _mgr(rate_limit=10)
    m.record_usage(USER, 25)  # 초과 기록
    assert m.get_remaining_rate(USER) == 0


def test_reset_user_clears_state():
    m = _mgr()
    m.record_usage(USER, 50)
    m.reset_user(USER)
    assert m.get_usage(USER)["units_used"] == 0


def test_per_second_reset():
    m = _mgr()
    m.record_usage(USER, 100)
    # 1초 이전으로 last_reset 을 당겨 초당 리셋을 유도
    m._usage[USER].last_reset = datetime.now() - timedelta(seconds=2)
    assert m.get_remaining_rate(USER) == m.rate_limit  # 리셋되어 가득 참


def test_daily_limit_reached_true_within_day():
    m = _mgr(daily_limit=10)
    m.record_usage(USER, 10)
    assert m.is_daily_limit_reached(USER) is True


def test_daily_limit_resets_after_midnight():
    # 회귀: 자정 경과 후에는 어제 daily_units 가 아니라 리셋된 값으로 판정해야 한다.
    m = _mgr(daily_limit=10)
    m.record_usage(USER, 10)
    m._usage[USER].daily_reset = datetime.now() - timedelta(days=1)
    assert m.is_daily_limit_reached(USER) is False
