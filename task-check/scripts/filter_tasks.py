#!/usr/bin/env python3
"""Filter active tasks from Notion Board view query results.

Outputs formatted task list + JSON data block for status updates.

Default: 담당자=양경희 + 활성 상태 + 일정에 오늘 포함
--all-dates: 일정 필터 해제 (전체 활성 일감)
--include-backlog: 백로그도 포함
"""

import argparse
import json
from datetime import date

ACTIVE_STATUSES = ["진행 중", "검토 중", "해야할 일"]
MY_USER_ID = "user://0f90d063-d2bb-4e09-9b39-f7bdc4883d2b"

PRIORITY_ORDER = {"Must have": 0, "Should have": 1, "Could have": 2, "Won't have": 3}
STATUS_EMOJI = {"진행 중": "🔴", "검토 중": "🔵", "해야할 일": "🟡", "백로그": "⚪", "완료": "✅", "닫힘": "⬛"}


def parse_tags(raw):
    if not raw:
        return []
    try:
        tags = json.loads(raw) if isinstance(raw, str) else raw
        return tags if isinstance(tags, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _page_id_from_url(url):
    """Notion 페이지 URL에서 page_id(마지막 경로 세그먼트)를 견고하게 추출한다.

    이 값은 상태 변경(notion-update-page)의 타겟이므로 ?query·#fragment·trailing slash를
    먼저 제거해 엉뚱한 페이지를 가리키지 않게 한다.
    """
    if not url:
        return ""
    cleaned = str(url).split("?", 1)[0].split("#", 1)[0].rstrip("/")
    return cleaned.split("/")[-1] if cleaned else ""


def _date_part(value):
    """Notion 날짜에서 날짜(YYYY-MM-DD) 부분만 취한다. 일시('..T09:00..')면 시간 제거."""
    if not value or value == "None":
        return value
    return str(value).split("T", 1)[0]


def schedule_includes_today(task, today_str):
    """일정에 오늘이 포함되는지 확인한다.

    Notion 일정은 날짜('2026-06-04') 또는 일시('2026-06-04T09:00..+09:00')로 올 수 있으므로
    날짜 부분만으로 비교한다(시간이 설정된 오늘 일감이 누락되지 않게).

    - 범위(start~end): start <= today <= end
    - 단일 날짜(start만): start == today
    - 일정 없음: False
    """
    start = _date_part(task.get("date:일정:start"))
    if not start:
        return False
    end = task.get("date:일정:end")
    if end and end != "None":
        return start <= today_str <= _date_part(end)
    return start == today_str


def resolve_statuses(include_backlog=False, include_done=False):
    """활성 상태 목록을 옵션에 따라 구성한다. 정렬 우선순위(인덱스) 기준이 된다."""
    statuses = ACTIVE_STATUSES[:]
    if include_backlog:
        statuses.append("백로그")
    if include_done:
        statuses.extend(["완료", "닫힘"])
    return statuses


def extract_results(data):
    """MCP 응답(리스트+text 래핑) 또는 평문 dict 모두에서 results 배열을 꺼낸다."""
    if isinstance(data, list) and data and "text" in data[0]:
        inner = json.loads(data[0]["text"])
    else:
        inner = data
    return inner.get("results", [])


def filter_active_tasks(results, today_str, include_backlog=False,
                        include_done=False, all_dates=False):
    """내 활성 일감만 추려 상태→우선순위 순으로 정렬해 반환한다.

    순수 함수로 분리하여 단위 테스트가 가능하게 한다. main()의 출력 동작은 불변.
    """
    statuses = resolve_statuses(include_backlog, include_done)
    active = []
    for r in results:
        if r.get("상태") not in statuses:
            continue
        assignees = r.get("담당자")
        if not assignees:
            continue
        try:
            assignee_list = json.loads(assignees) if isinstance(assignees, str) else assignees
            if MY_USER_ID not in assignee_list:
                continue
        except (json.JSONDecodeError, TypeError):
            continue
        if not all_dates and not schedule_includes_today(r, today_str):
            continue
        active.append(r)

    active.sort(key=lambda r: (
        statuses.index(r.get("상태", "")),
        PRIORITY_ORDER.get(r.get("우선 순위"), 99),
    ))
    return active


def main():
    parser = argparse.ArgumentParser(description="Filter active tasks from Notion Board view query results.")
    parser.add_argument("file_path", help="Path to the Notion query result JSON file")
    parser.add_argument("--all-dates", action="store_true", help="Disable date filter (show all active tasks)")
    parser.add_argument("--include-backlog", action="store_true", help="Include backlog tasks")
    parser.add_argument("--include-done", action="store_true", help="Include completed/closed tasks")
    args = parser.parse_args()

    today_str = date.today().isoformat()

    with open(args.file_path) as f:
        data = json.load(f)

    results = extract_results(data)
    active = filter_active_tasks(
        results, today_str,
        include_backlog=args.include_backlog,
        include_done=args.include_done,
        all_dates=args.all_dates,
    )

    today = today_str
    print(f"📋 일감 현황 ({today})")
    print("━" * 40)

    if not active:
        print("\n활성 일감이 없습니다 🎉")
        return

    task_data = {}
    num = 1
    counts = {}
    current_status = None

    for task in active:
        status = task.get("상태")
        if status != current_status:
            if current_status is not None:
                print()
            emoji = STATUS_EMOJI.get(status, "❓")
            group_count = sum(1 for t in active if t.get("상태") == status)
            counts[status] = group_count
            print(f"\n{emoji} {status} ({group_count}건)")
            current_status = status

        task_id_num = task.get("userDefined:ID")
        task_id = f"RND-{task_id_num}" if task_id_num else "RND-?????"
        name = task.get("이름", "(제목 없음)")
        priority = task.get("우선 순위") or "-"
        tags = ", ".join(parse_tags(task.get("태그")))

        page_id = _page_id_from_url(task.get("url", ""))
        notion_link = f"https://www.notion.so/{page_id}" if page_id else ""

        line = f"  {num}. [{task_id}]({notion_link}) | {name} | {priority}"
        if tags:
            line += f" | {tags}"
        print(line)
        task_data[str(num)] = {
            "page_id": page_id,
            "name": name,
            "status": status,
            "rnd_id": task_id,
        }
        num += 1

    print()
    print("━" * 40)
    total = len(active)
    parts = " + ".join(f"{s} {c}" for s, c in counts.items())
    print(f"활성 {total}건 ({parts})")

    print("\n---TASK_DATA---")
    print(json.dumps(task_data, ensure_ascii=False))


if __name__ == "__main__":
    main()
