"""retry_handler.calculate_delay 단위 테스트.

core/__init__.py 는 batch_processor → googleapiclient.discovery 등 무거운 모듈을
즉시 import 하므로, 여기서는 retry_handler.py 만 파일 경로로 직접 로드해 순수 로직을
독립적으로 검증한다(googleapiclient.errors 만 필요).
"""
import importlib.util
import os

_MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "gmail", "scripts", "core", "retry_handler.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("retry_handler_under_test", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rh = _load()


def test_delay_never_exceeds_max_with_jitter():
    # 큰 attempt + jitter 에서도 max_delay 상한을 넘지 않아야 한다 (회귀: 과거 1.5배 초과).
    samples = [rh.calculate_delay(20, base_delay=1.0, max_delay=60.0, jitter=True)
               for _ in range(3000)]
    assert max(samples) <= 60.0


def test_no_jitter_is_deterministic_exponential():
    assert rh.calculate_delay(3, base_delay=1.0, exponential_base=2.0, jitter=False) == 8.0


def test_no_jitter_caps_at_max():
    assert rh.calculate_delay(10, base_delay=1.0, max_delay=60.0, jitter=False) == 60.0


def test_jitter_range_preserved_when_uncapped():
    # attempt0, base=1 → 지터 범위 [0.5, 1.5) (캡과 무관한 구간은 동작 불변).
    samples = [rh.calculate_delay(0, base_delay=1.0, max_delay=60.0, jitter=True)
               for _ in range(3000)]
    assert min(samples) >= 0.5
    assert max(samples) < 1.5


def test_delay_increases_with_attempt_no_jitter():
    d0 = rh.calculate_delay(0, jitter=False)
    d1 = rh.calculate_delay(1, jitter=False)
    d2 = rh.calculate_delay(2, jitter=False)
    assert d0 < d1 < d2


# Retry-After 헤더 존중 (외부 모범사례 반영)
class _FakeErr(Exception):
    def __init__(self, resp):
        self.resp = resp


def test_retry_after_parses_integer_seconds():
    assert rh.retry_after_seconds(_FakeErr({"retry-after": "5"})) == 5.0


def test_retry_after_none_when_absent():
    assert rh.retry_after_seconds(_FakeErr({})) is None
    assert rh.retry_after_seconds(Exception("no resp")) is None


def test_retry_after_ignores_http_date_and_negative():
    assert rh.retry_after_seconds(_FakeErr({"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"})) is None
    assert rh.retry_after_seconds(_FakeErr({"retry-after": "-3"})) is None
