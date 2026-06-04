from filter_tasks import (
    MY_USER_ID,
    extract_results,
    filter_active_tasks,
    parse_tags,
    resolve_statuses,
    schedule_includes_today,
)

TODAY = "2026-06-04"


def _task(status="진행 중", mine=True, start=TODAY, end=None,
          priority="Must have", tid="1", name="작업"):
    t = {
        "상태": status,
        "담당자": f'["{MY_USER_ID}"]' if mine else '["user://other"]',
        "userDefined:ID": tid,
        "이름": name,
        "우선 순위": priority,
        "url": "https://www.notion.so/abc",
    }
    if start:
        t["date:일정:start"] = start
    if end:
        t["date:일정:end"] = end
    return t


# --- parse_tags ---

def test_parse_tags_from_json_string():
    assert parse_tags('["a", "b"]') == ["a", "b"]


def test_parse_tags_from_list():
    assert parse_tags(["x"]) == ["x"]


def test_parse_tags_handles_empty_and_invalid():
    assert parse_tags(None) == []
    assert parse_tags("not-json") == []
    assert parse_tags('{"k": 1}') == []  # dict 는 list 아님


# --- schedule_includes_today ---

def test_schedule_single_date_match():
    assert schedule_includes_today({"date:일정:start": TODAY}, TODAY) is True


def test_schedule_single_date_no_match():
    assert schedule_includes_today({"date:일정:start": "2026-06-01"}, TODAY) is False


def test_schedule_range_inclusive():
    task = {"date:일정:start": "2026-06-01", "date:일정:end": "2026-06-30"}
    assert schedule_includes_today(task, TODAY) is True


def test_schedule_range_outside():
    task = {"date:일정:start": "2026-06-05", "date:일정:end": "2026-06-30"}
    assert schedule_includes_today(task, TODAY) is False


def test_schedule_no_start_is_false():
    assert schedule_includes_today({}, TODAY) is False


def test_schedule_end_none_string_treated_as_single():
    task = {"date:일정:start": TODAY, "date:일정:end": "None"}
    assert schedule_includes_today(task, TODAY) is True


# --- resolve_statuses ---

def test_resolve_statuses_default():
    assert resolve_statuses() == ["진행 중", "검토 중", "해야할 일"]


def test_resolve_statuses_with_flags():
    s = resolve_statuses(include_backlog=True, include_done=True)
    assert "백로그" in s and "완료" in s and "닫힘" in s


# --- extract_results ---

def test_extract_results_plain_dict():
    assert extract_results({"results": [1, 2]}) == [1, 2]


def test_extract_results_mcp_text_wrapper():
    import json
    wrapped = [{"text": json.dumps({"results": [{"이름": "x"}]})}]
    assert extract_results(wrapped) == [{"이름": "x"}]


# --- filter_active_tasks ---

def test_filter_excludes_other_assignee():
    tasks = [_task(mine=False)]
    assert filter_active_tasks(tasks, TODAY) == []


def test_filter_excludes_done_by_default():
    tasks = [_task(status="완료")]
    assert filter_active_tasks(tasks, TODAY) == []


def test_filter_includes_done_when_flagged():
    tasks = [_task(status="완료")]
    assert len(filter_active_tasks(tasks, TODAY, include_done=True)) == 1


def test_filter_date_filter_excludes_non_today():
    tasks = [_task(start="2026-06-01")]  # 단일 날짜, 오늘 아님
    assert filter_active_tasks(tasks, TODAY) == []
    # all_dates 면 날짜 무시하고 포함
    assert len(filter_active_tasks(tasks, TODAY, all_dates=True)) == 1


def test_filter_sorts_by_status_then_priority():
    tasks = [
        _task(status="해야할 일", priority="Must have", name="해야할"),
        _task(status="진행 중", priority="Should have", name="진행Should"),
        _task(status="진행 중", priority="Must have", name="진행Must"),
    ]
    active = filter_active_tasks(tasks, TODAY)
    names = [t["이름"] for t in active]
    # 진행 중이 해야할 일보다 먼저, 진행 중 안에서는 Must < Should
    assert names == ["진행Must", "진행Should", "해야할"]


def test_filter_skips_missing_assignee():
    t = _task()
    del t["담당자"]
    assert filter_active_tasks([t], TODAY) == []
