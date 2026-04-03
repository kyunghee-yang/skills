---
name: task-check
description: Notion 이슈 DB에서 내 일감 현황을 조회하고 상태를 대화형으로 관리하는 스킬. "일감 확인", "오늘 할 일", "내 할일", "남은 일", "진행중인 일", "완료 처리", "task check", "할일 뭐 남았어", "뭐 해야돼", "일감 정리", "업무 현황", "할일 정리", "오늘 뭐 남았지", "일감 어때" 등 업무 현황 조회나 일감 상태 변경 요청에 반드시 이 스킬을 사용하세요. 하루에 여러 번 실행하여 일감 진행 상황을 추적하고 완료 처리하는 데 최적화되어 있습니다. 일감, 할 일, 업무, 태스크, task 등의 단어가 조회나 상태 확인/변경 맥락에서 사용되면 이 스킬을 적용하세요.
---

# Notion 일감 확인 & 관리

사용자의 활성 일감을 조회하고, 대화형으로 상태를 변경한다.

## 고정값

| 항목 | 값 |
|------|-----|
| Board View URL | `https://www.notion.so/cf012e4cf9fe4f95839f09ea53fec2a4?v=d921e7c01d7d41858b74cd959d5b49d6` |
| 담당자 | 양경희 (`user://0f90d063-d2bb-4e09-9b39-f7bdc4883d2b`) |
| 스크립트 | `<skill-dir>/scripts/filter_tasks.py` |

### 상태 전이

```
백로그 → 해야할 일 → 진행 중 → 검토 중 → 완료
                                         → 닫힘
```

## 실행 흐름

### Step 1: Board 뷰 조회

`mcp__notion__notion-query-database-view`를 호출한다.

```
view_url: https://www.notion.so/cf012e4cf9fe4f95839f09ea53fec2a4?v=d921e7c01d7d41858b74cd959d5b49d6
```

### Step 2: 활성 일감 추출

결과가 파일로 저장되면 (`tool-results/` 경로), 번들 스크립트로 필터링한다:

```bash
python3 <skill-dir>/scripts/filter_tasks.py <result-file-path>
```

기본 필터: 담당자=양경희 + 활성 상태 + **일정에 오늘 포함**
- 범위 일정(start~end): start <= 오늘 <= end
- 단일 날짜(start만): start == 오늘
- 일정 없음: 제외

옵션:
- `--all-dates`: 일정 필터 해제 (전체 활성 일감 조회)
- `--include-backlog`: 백로그도 포함

사용자가 "전체 일감", "날짜 상관없이" 등으로 요청하면 `--all-dates`를 추가한다.

### Step 3: 현황 출력

스크립트 출력에서 `---TASK_DATA---` 위쪽만 사용자에게 보여준다.
`---TASK_DATA---` 아래의 JSON은 상태 변경 시 page_id를 조회하는 데 사용한다.

### Step 4: 대화형 처리

`AskUserQuestion`으로 다음 액션을 물어본다:

| 선택지 | 설명 |
|--------|------|
| 완료 처리 | 번호를 입력받아 해당 일감을 `완료`로 변경 |
| 상태 변경 | 번호와 목표 상태를 입력받아 변경 |
| 완료 포함 보기 | `--include-done` 옵션으로 완료/닫힘 상태도 포함하여 조회 |
| 전체 일감 보기 | `--all-dates` 옵션으로 일정 필터 해제하여 다시 조회 |
| 백로그 보기 | `--include-backlog` 옵션으로 스크립트를 다시 실행 |
| 끝 | 종료 |

"완료 처리" 선택 시, 어떤 번호를 완료할지 추가로 물어본다.
여러 번호를 한번에 처리할 수 있다 (예: "1, 3, 5").

### Step 5: 상태 변경

TASK_DATA JSON에서 해당 번호의 `page_id`를 찾아 `mcp__notion__notion-update-page`로 변경한다.

```
page_id: <TASK_DATA에서 추출한 page_id>
command: update_properties
properties: {"상태": "완료"}
content_updates: []
```

변경 가능한 상태값: `백로그`, `해야할 일`, `진행 중`, `검토 중`, `완료`, `닫힘`

변경 후 결과를 출력한다:
```
✅ RND-12345 | 일감이름 → 완료
```

여러 건이면 각각 출력한다.

### Step 6: 반복 또는 종료

상태 변경 후 "더 처리할 일감이 있나요?"로 다시 Step 4로 돌아간다.
사용자가 "끝", "없어", "됐어"라고 하면 종료한다.

## 주의사항

- Notion datetime에 `+09:00`을 붙이지 않는다 (UTC 변환 방지).
- 상태 변경 시 `상태` 속성만 변경한다. 다른 속성은 건드리지 않는다.
- `content_updates`는 빈 배열 `[]`로 전달한다.
- 스크립트 경로의 `<skill-dir>`은 이 SKILL.md가 위치한 디렉토리이다.
