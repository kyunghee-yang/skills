"""cache_manager(EmailCache) 단위 테스트.

core/__init__.py 의 무거운 import 를 피하려 모듈을 파일 경로로 직접 로드한다.
cache_manager 는 순수 stdlib 라 외부 의존성이 없다.
"""
import importlib.util
import json
import os
from datetime import datetime, timedelta

_MODULE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "gmail", "scripts", "core", "cache_manager.py"
)


def _load():
    spec = importlib.util.spec_from_file_location("cache_manager_under_test", _MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cm = _load()


def _cache(tmp_path):
    return cm.EmailCache(cache_dir=str(tmp_path))


def _age_message(cache, account, msg_id, hours):
    """캐시 파일의 cached_at 을 hours 시간 전으로 조작."""
    p = cache._message_path(account, msg_id)
    data = json.load(open(p))
    data["cached_at"] = (datetime.now() - timedelta(hours=hours)).isoformat()
    json.dump(data, open(p, "w"))


def test_set_get_message_roundtrip(tmp_path):
    c = _cache(tmp_path)
    c.set_message("acc", "m1", {"id": "m1", "body": "hello"})
    assert c.get_message("acc", "m1")["body"] == "hello"


def test_get_missing_returns_none(tmp_path):
    assert _cache(tmp_path).get_message("acc", "nope") is None


def test_list_roundtrip_and_key_includes_labels(tmp_path):
    c = _cache(tmp_path)
    c.set_list("acc", "is:unread", [{"id": "1"}], label_ids=["INBOX"])
    assert c.get_list("acc", "is:unread", label_ids=["INBOX"]) == [{"id": "1"}]
    # 다른 라벨 조합은 캐시 미스여야 한다
    assert c.get_list("acc", "is:unread", label_ids=["SENT"]) is None


def test_labels_roundtrip(tmp_path):
    c = _cache(tmp_path)
    c.set_labels("acc", [{"id": "INBOX"}])
    assert c.get_labels("acc") == [{"id": "INBOX"}]


def test_invalidate_message(tmp_path):
    c = _cache(tmp_path)
    c.set_message("acc", "m1", {"id": "m1"})
    c.invalidate_message("acc", "m1")
    assert c.get_message("acc", "m1") is None


def test_metadata_only_read_preserves_body_cache(tmp_path):
    """회귀: 본문 TTL(24h) 내라면 metadata_only(1h) 만료 조회가 본문 캐시를 지우면 안 된다."""
    c = _cache(tmp_path)
    c.set_message("acc", "m1", {"id": "m1", "body": "full"})
    _age_message(c, "acc", "m1", hours=2)  # 메타 TTL(1h) 초과, 본문 TTL(24h) 이내
    assert c.get_message("acc", "m1", metadata_only=True) is None  # 메타 기준 만료
    # 핵심: 본문 캐시는 살아 있어야 한다
    assert c.get_message("acc", "m1", metadata_only=False) == {"id": "m1", "body": "full"}


def test_expired_body_cache_is_deleted(tmp_path):
    c = _cache(tmp_path)
    c.set_message("acc", "m1", {"id": "m1", "body": "full"})
    _age_message(c, "acc", "m1", hours=25)  # 본문 TTL(24h)도 초과
    assert c.get_message("acc", "m1") is None
    assert not c._message_path("acc", "m1").exists()  # 만료 파일 삭제됨


def test_corrupted_cache_file_is_handled(tmp_path):
    c = _cache(tmp_path)
    c.set_message("acc", "m1", {"id": "m1"})
    c._message_path("acc", "m1").write_text("{not json")
    assert c.get_message("acc", "m1") is None
