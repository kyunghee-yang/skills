"""filter_tasks.py CLI 출력 회귀 테스트.

순수 함수(filter_active_tasks 등)는 test_filter_tasks 에서 다루므로, 여기서는 사용자 대면
출력(상태 그룹 헤더 / 일감 라인 / 카운트 요약 / ---TASK_DATA--- JSON)을 서브프로세스로 고정한다.
날짜 의존을 피하려 --all-dates 로 실행한다.
"""
import json
import os
import subprocess
import sys

SCRIPT = os.path.join(os.path.dirname(__file__), "..", "scripts", "filter_tasks.py")
MY = "user://0f90d063-d2bb-4e09-9b39-f7bdc4883d2b"


def _run(tmp_path, results, *args):
    data = {"results": results}
    p = tmp_path / "q.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    out = subprocess.run(
        [sys.executable, os.path.abspath(SCRIPT), str(p), "--all-dates", *args],
        capture_output=True, text=True, check=True,
    ).stdout
    return out


def _task(status, name, tid, mine=True, priority="Must have"):
    return {
        "상태": status, "이름": name, "userDefined:ID": tid,
        "우선 순위": priority,
        "담당자": f'["{MY}"]' if mine else '["user://other"]',
        "date:일정:start": "2026-06-01",
        "url": f"https://www.notion.so/{tid}",
    }


def test_cli_groups_and_task_data(tmp_path):
    results = [
        _task("진행 중", "A작업", "101"),
        _task("해야할 일", "B작업", "102", priority="Should have"),
        _task("완료", "끝난거", "103"),          # 기본 제외
        _task("진행 중", "남의일", "104", mine=False),  # 담당자 아님 제외
    ]
    out = _run(tmp_path, results)
    # 상태 그룹 헤더
    assert "🔴 진행 중 (1건)" in out
    assert "🟡 해야할 일 (1건)" in out
    # 일감 라인(RND-ID + 이름 + 우선순위)
    assert "[RND-101]" in out and "A작업" in out
    assert "[RND-102]" in out and "B작업" in out
    # 제외 항목 미포함
    assert "끝난거" not in out
    assert "남의일" not in out
    # 카운트 요약
    assert "활성 2건" in out

    # TASK_DATA JSON 블록 파싱
    marker = "---TASK_DATA---"
    assert marker in out
    task_data = json.loads(out.split(marker, 1)[1].strip())
    assert task_data["1"]["rnd_id"] == "RND-101"
    assert task_data["2"]["name"] == "B작업"


def test_cli_empty_when_no_active(tmp_path):
    out = _run(tmp_path, [_task("완료", "끝", "200")])
    assert "활성 일감이 없습니다" in out


def test_cli_include_done_flag(tmp_path):
    out = _run(tmp_path, [_task("완료", "끝난거", "300")], "--include-done")
    assert "끝난거" in out
    assert "✅ 완료" in out
