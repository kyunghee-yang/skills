"""verify_app.py 순수 판정 코어 테스트(브라우저 불필요).

브라우저 래퍼(verify)는 Playwright+매칭 브라우저가 필요하므로 단위 테스트하지 않는다
(환경 의존). 여기서는 classify_console / build_report 의 판정 로직만 검증한다.
"""
import verify_app as va


def test_classify_console_splits_types():
    msgs = [
        {"type": "error", "text": "TypeError: x"},
        {"type": "warning", "text": "deprecated"},
        {"type": "log", "text": "hello"},
    ]
    out = va.classify_console(msgs)
    assert out["errors"] == ["TypeError: x"]
    assert out["warnings"] == ["deprecated"]


def test_classify_console_ignores_noise():
    msgs = [
        {"type": "error", "text": "GET /favicon.ico 404"},
        {"type": "error", "text": "Failed to load resource: net::ERR_FAILED"},
        {"type": "error", "text": "real app error"},
    ]
    out = va.classify_console(msgs)
    assert out["errors"] == ["real app error"]
    assert len(out["ignored"]) == 2


def test_build_report_passes_when_clean_and_completed():
    rep = va.build_report("u", {"errors": [], "warnings": ["w"]}, [], flow_completed=True)
    assert rep["passed"] is True


def test_build_report_fails_on_console_error():
    rep = va.build_report("u", {"errors": ["boom"]}, [], flow_completed=True)
    assert rep["passed"] is False


def test_build_report_fails_on_page_error():
    rep = va.build_report("u", {"errors": []}, ["Uncaught X"], flow_completed=True)
    assert rep["passed"] is False


def test_build_report_fails_when_flow_incomplete():
    # 클릭 흐름을 끝까지 못 가면(예외로 중단) 콘솔이 깨끗해도 실패
    rep = va.build_report("u", {"errors": []}, [], flow_completed=False)
    assert rep["passed"] is False


def test_main_exit_code_flow_fail_is_1(monkeypatch, capsys):
    # 흐름 실패(passed=False)는 게이트 실패 exit 1 (환경오류 2 아님)
    monkeypatch.setattr(va, "verify", lambda *a, **k: va.build_report(
        "u", {"errors": []}, ["흐름 단계 실패: TimeoutError"], flow_completed=False))
    import sys as _s
    monkeypatch.setattr(_s, "argv", ["verify_app.py", "http://x"])
    assert va.main() == 1


def test_main_exit_code_env_error_is_2(monkeypatch):
    def _raise(*a, **k):
        raise ImportError("playwright 미설치")
    monkeypatch.setattr(va, "verify", _raise)
    import sys as _s
    monkeypatch.setattr(_s, "argv", ["verify_app.py", "http://x"])
    assert va.main() == 2


def test_main_exit_code_pass_is_0(monkeypatch):
    monkeypatch.setattr(va, "verify", lambda *a, **k: va.build_report(
        "u", {"errors": []}, [], flow_completed=True))
    import sys as _s
    monkeypatch.setattr(_s, "argv", ["verify_app.py", "http://x"])
    assert va.main() == 0
