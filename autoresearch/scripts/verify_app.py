#!/usr/bin/env python3
"""앱 브라우저 검증 도구 — 핵심 사용자 흐름을 클릭하며 콘솔/페이지 오류를 잡는다.

오토리서치 VERIFY 단계에서 "앱을 직접 클릭하며 오류 잡기"를 자동화한다. cmux 환경이면
cmux 내장 브라우저+codex computer-use 가 1순위지만, 일반 환경에서는 Playwright(설치돼
있으면)로 헤드리스 검증한다.

구성:
  - 순수 판정 코어(classify_console / build_report): 브라우저 없이 단위 테스트 가능.
  - 브라우저 래퍼(verify): Playwright sync API 로 페이지를 열고 클릭 흐름을 완주하며
    콘솔/페이지 에러와 스크린샷을 수집한 뒤 코어로 판정.

사용법:
  python3 verify_app.py http://localhost:5173 --click "로그인" --click "계산" \
      --screenshot /tmp/verify.png
종료 코드: 통과 0, 실패(콘솔 에러/흐름 미완주) 1. → 스크립트 게이트로 사용 가능.
"""
from __future__ import annotations

import argparse
import sys

# 무시해도 되는 흔한 노이즈(분석/파비콘 등). 필요시 확장.
_IGNORABLE_SUBSTRINGS = (
    "favicon.ico",
    "Failed to load resource: net::ERR_",  # 외부 리소스 로드 실패(앱 버그 아님인 경우 많음)
)


def classify_console(messages: list[dict]) -> dict:
    """콘솔 메시지 목록을 error/warning 으로 분류하고 무시 가능 항목을 거른다.

    messages: [{"type": "error"|"warning"|..., "text": str}, ...]
    반환: {"errors": [...], "warnings": [...], "ignored": [...]}
    """
    errors, warnings, ignored = [], [], []
    for m in messages:
        text = (m.get("text") or "")
        mtype = m.get("type")
        if any(s in text for s in _IGNORABLE_SUBSTRINGS):
            ignored.append(text)
            continue
        if mtype == "error":
            errors.append(text)
        elif mtype == "warning":
            warnings.append(text)
    return {"errors": errors, "warnings": warnings, "ignored": ignored}


def build_report(url: str, console: dict, page_errors: list[str],
                 flow_completed: bool, screenshot: str | None = None) -> dict:
    """검증 결과 리포트를 만든다. passed = 콘솔/페이지 에러 0 AND 흐름 완주."""
    errors = list(console.get("errors", [])) + list(page_errors)
    passed = (len(errors) == 0) and flow_completed
    return {
        "url": url,
        "passed": passed,
        "console_errors": console.get("errors", []),
        "console_warnings": console.get("warnings", []),
        "page_errors": page_errors,
        "flow_completed": flow_completed,
        "screenshot": screenshot,
    }


def verify(url: str, click_texts: list[str] | None = None,
           screenshot: str | None = None, timeout_ms: int = 10000) -> dict:
    """Playwright 로 url 을 열고 click_texts 를 순서대로 클릭하며 오류를 수집한다.

    Playwright(및 매칭 브라우저)가 없으면 ImportError/RuntimeError 가 난다 — 호출부에서
    cmux/codex 경로나 수동 검증으로 폴백한다.
    """
    from playwright.sync_api import sync_playwright  # 지연 import (선택적 의존)

    messages: list[dict] = []
    page_errors: list[str] = []
    flow_completed = False

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.on("console", lambda m: messages.append({"type": m.type, "text": m.text}))
        page.on("pageerror", lambda e: page_errors.append(str(e)))
        page.goto(url, timeout=timeout_ms)
        for text in (click_texts or []):
            page.get_by_text(text, exact=False).first.click(timeout=timeout_ms)
            page.wait_for_timeout(200)
        flow_completed = True
        if screenshot:
            page.screenshot(path=screenshot, full_page=True)
        browser.close()

    return build_report(url, classify_console(messages), page_errors, flow_completed, screenshot)


def main() -> int:
    ap = argparse.ArgumentParser(description="Playwright 앱 클릭 검증")
    ap.add_argument("url")
    ap.add_argument("--click", action="append", default=[], help="클릭할 텍스트(반복 가능)")
    ap.add_argument("--screenshot", help="스크린샷 저장 경로")
    args = ap.parse_args()
    try:
        report = verify(args.url, args.click, args.screenshot)
    except Exception as e:  # 브라우저 미가용 등
        print(f"검증 실행 불가(브라우저 환경 확인 필요): {type(e).__name__}: {e}", file=sys.stderr)
        return 2
    import json
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
