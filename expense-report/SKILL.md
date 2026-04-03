---
name: expense
description: 기명카드 승인내역으로 지출결의서 엑셀 자동 생성. 폴더 경로를 지정하면 xls 파싱, Notion 팀활동비 매칭, 규칙 분류, 엑셀 생성, 영수증 첨부까지 수행. "/expense 폴더경로" 형태로 호출하거나 "지출결의서", "경비", "법인카드", "이번달 경비", "카드값 정리" 언급 시에도 이 스킬을 사용하세요. 매월 반복하는 법인카드 지출결의서 작성을 자동화합니다.
---

# 지출결의서 생성 스킬

## 사용법
```
/expense 202603              ← YYYYMM만 입력 (config의 base_path 사용)
/expense {전체 폴더경로}      ← 전체 경로 직접 지정
/expense-capture 202603
지출결의서 작성               ← 대상 월을 질문
```

**경로 해석**: 6자리 숫자(YYYYMM)만 입력하면 config의 `base_path`에서 `{base_path}/{YYYY}/{YYYYMM}` 경로를 자동 구성합니다.

## 분류 규칙 요약

> 상세 기준은 `references/classification-rules.md` 참조

| 규칙 | 이름 | 핵심 조건 | 계정과목 |
|------|------|-----------|----------|
| R1 | 팀 커피 (Notion 매칭) | Notion 팀활동비 DB에서 날짜+금액 매칭 | 복리후생비[회식비] |
| R2 | 택시 가승인 취소 | 가맹점 "카카오T택시_가승인" | 여비교통비[택시] |
| R3 | 법인택시 (야근) | 가맹점 "카카오T일반택시(법인)..." | 여비교통비[택시] |
| R4 | 일반 택시 | 가맹점에 "택시" 포함 | 여비교통비[택시] |
| R5 | 카페 (확인필요) | 카페 키워드 + Notion 미매칭 | 복리후생비[회식비] |
| R6 | 점심 식대 | 11:00~13:59, 비카페/비PG | 복리후생비[식비] |
| R7 | 저녁 식대 | 17:00~20:29, 비카페/비PG | 복리후생비[식비] |
| R8 | 수기 필요 | 위 규칙 해당 없음 | (수기 입력) |

**"(확인필요)" 태그**: 자동 분류되었지만 사용자 검토가 필요한 항목에 붙습니다.

## `/expense` 실행 절차

당신은 지출결의서 생성을 오케스트레이션하는 역할입니다. 아래 단계를 순서대로 수행하세요.

### Step 0: 사용자 설정 확인

사용자 설정 파일을 확인합니다:
```bash
cat ~/.config/expense-report/config.json 2>/dev/null || echo "NOT_FOUND"
```

**파일이 없으면 (첫 실행)** 사용자에게 아래 정보를 질문합니다:

| 항목 | 설명 | 예시 |
|------|------|------|
| 이름 | 기안자명 | 양경희 |
| 부서 | 소속 부서 | R&D본부 |
| 팀 리더 여부 | Notion 팀활동비 DB 접근 가능 여부 | true/false |
| 택시 도착지 | 집 동네 | 김포, 부천, 신림, 성남 등 |
| 지출결의서 폴더 | 기본 경로 (Google Drive 등) | /Users/홍길동/Documents/drive/개인경비 지출결의서 |

팀 리더인 경우 추가로 `mcp__notion__notion-get-users` 도구로 사용자 목록을 조회하여, 입력받은 이름과 일치하는 Notion user ID를 찾습니다.

수집한 정보로 설정 파일을 생성합니다:
```bash
mkdir -p ~/.config/expense-report
```

Write 도구로 `~/.config/expense-report/config.json` 파일을 생성합니다:
```json
{
  "drafter_name": "홍길동",
  "department": "R&D본부",
  "is_team_leader": false,
  "notion_user_id": null,
  "taxi_destination": "부천",
  "base_path": "/Users/홍길동/Documents/drive/개인경비 지출결의서"
}
```

팀 리더인 경우 `notion_user_id`에 조회된 ID를 넣습니다:
```json
{
  "drafter_name": "양경희",
  "department": "R&D본부",
  "is_team_leader": true,
  "notion_user_id": "0f90d063-d2bb-4e09-9b39-f7bdc4883d2b",
  "taxi_destination": "김포",
  "base_path": "/Users/ykh/Documents/drive/개인경비 지출결의서"
}
```

**파일이 이미 있으면** 설정 내용을 읽고 다음 단계로 진행합니다.

### Step 1: 폴더 검증 및 파일 준비 안내

Bash 도구로 폴더 내 파일을 확인합니다:
```bash
ls -la "{폴더경로}"
```

**폴더가 없으면** 생성 후 안내합니다:
```bash
mkdir -p "{폴더경로}"
```
> "폴더를 생성했습니다. 아래 파일을 준비한 후 다시 실행해주세요."

**필수 파일 체크 및 안내:**

1. **`간편서비스_승인내역.xls`** — 없으면 아래 안내 후 종료:
   > "승인내역 파일이 없습니다. 아래 절차로 다운로드하세요:
   > 1. 하나카드 간편서비스 접속 (https://card.hanacard.co.kr)
   > 2. 로그인 → [카드이용] → [이용내역조회]
   > 3. 기간: 해당월 1일~말일, 카드: 법인카드 선택
   > 4. [엑셀 다운로드] 클릭
   > 5. 다운로드된 `간편서비스_승인내역.xls` 파일을 `{폴더경로}`에 저장
   > 6. 다시 `/expense {YYYYMM}` 실행"

2. **영수증 이미지 (JPG/PNG)** — 택시비 사용 시 필수:
   > "택시비 항목이 있으면 영수증 이미지가 필요합니다:
   > - 카카오T 앱 → [이용내역] → 해당 건 → [영수증] → 스크린샷 저장
   > - 파일을 `{폴더경로}`에 저장 (파일명 자유)
   > - 지원 형식: .jpg, .jpeg, .png"

**모든 파일이 준비된 경우** 다음 단계로 진행합니다.
- 폴더명 마지막 6자리가 YYYYMM 형식이어야 합니다 (예: 202603)
- JPG/PNG 파일 목록을 기록해둡니다 (영수증 첨부용)

### Step 2: Notion 팀활동비 조회 및 JSON 저장

**`is_team_leader`가 false이면** 이 단계를 건너뜁니다. 빈 JSON을 생성하고 Step 3으로 진행:
```bash
echo '{"entries": []}' > /tmp/expense_notion_data.json
```
(팀 리더가 아닌 경우 Notion 접근이 불필요하며, 카페 결제는 모두 R5(확인필요)로 분류됩니다)

**`is_team_leader`가 true이면** Notion DB를 조회하고, 사용자 이름을 매핑하여, Python 스크립트용 JSON 파일을 생성합니다.

**2-1. 팀활동비 DB 조회**

`mcp__notion__notion-query-database-view` 도구로 조회:
- DB URL: `https://www.notion.so/wefun-platform/263270b243d0800faadbffde6ba5c9b0?v=263270b243d08023b856000c03fa97a0`

**⚠️ 페이지네이션**: 결과가 정확히 100건이면 전체를 못 가져온 것입니다.
- "월별 사용내역" 뷰(`v=2a0270b243d0805a9be0000cfdb680c5`)로 재조회하세요
- 그래도 부족하면 사용자에게 누락 가능성을 알리세요

조회 결과에서 아래 3가지 조건을 **모두** 만족하는 항목만 추출:
1. `사용내역` == "커피"
2. `사용자`에 양경희 user ID(`user://0f90d063-d2bb-4e09-9b39-f7bdc4883d2b`) 포함
3. `date:사용일:start`가 해당월(YYYYMM) 범위

**2-2. 동반자 이름 변환**

`mcp__notion__notion-get-users` 도구로 워크스페이스 사용자 목록을 조회하여 `동반자` 필드의 user ID를 실제 이름으로 변환합니다.

**2-3. JSON 파일 생성**

Write 도구로 `/tmp/expense_notion_data.json` 파일을 생성합니다. **반드시 아래 형식을 정확히 지켜야** Python 스크립트가 파싱할 수 있습니다:

```json
{
  "entries": [
    {
      "date": "2026-03-27",
      "amount": 27200,
      "companions": ["양경희", "김보민", "박경태"]
    }
  ]
}
```

필드 규칙:
- `date`: "YYYY-MM-DD" 형식 (Notion의 `date:사용일:start` 값)
- `amount`: 정수 (쉼표/원 제거, 예: 27200)
- `companions`: 이름 문자열 배열 (user ID가 아닌 **실제 이름**)

해당월에 매칭되는 커피 항목이 없으면 `{"entries": []}` 으로 저장합니다.

### Step 3: Python 스크립트 실행

```bash
PYTHONPATH=~/.claude/skills/expense-report/src python3 -m expense_report.main --folder "{폴더경로}" --notion-data /tmp/expense_notion_data.json
```

스크립트가 JSON을 stdout으로 출력합니다.

**에러 발생 시:**
- `ModuleNotFoundError` → PYTHONPATH 확인
- `FileNotFoundError` → 폴더경로 또는 xls 파일 경로 확인
- `KeyError` → `/tmp/expense_notion_data.json`의 JSON 형식이 잘못됨 (Step 2-3 재확인)

### Step 4: 결과 제시

출력된 JSON을 파싱하여 사용자에게 보여줍니다:

**자동 분류 요약:**

| 규칙 | 건수 |
|------|------|
| R1: 팀 커피 (Notion 매칭) | N건 |
| R2: 택시 가승인 취소 | N건 |
| R3: 법인택시 (야근) | N건 |
| R4: 일반 택시 | N건 |
| R5: 카페 (확인필요) | N건 |
| R6: 점심 식대 | N건 |
| R7: 저녁 식대 | N건 |
| R8: 수기 필요 | N건 |

**수기 필요 항목** (있는 경우):

| # | 이용일 | 시간 | 가맹점명 | 금액 |
|---|--------|------|----------|------|
| 1 | ... | ... | ... | ... |

**경고** (있는 경우):
- 택시 영수증 경고 메시지 표시

**생성 파일**: `{output 경로}`

### Step 5: 요약 캡처 (조건부)

수기 필요 항목이 **0건**이면:
```bash
PYTHONPATH=~/.claude/skills/expense-report/src python3 -c "
from expense_report.screenshot import capture_summary_sheet
capture_summary_sheet('{생성된_xlsx_경로}', '{폴더경로}/요약.png')
"
```

수기 필요 항목이 **1건 이상**이면:
> "수기 입력이 필요한 항목이 N건 있습니다. 엑셀에서 빈 셀을 채운 후 `/expense-capture {경로}`로 요약 캡처를 실행하세요."

## `/expense-capture` 실행 절차

수기 입력 완료 후 요약 시트를 캡처하는 명령입니다.

### Step 1: xlsx 파일 찾기

```bash
PYTHONPATH=~/.claude/skills/expense-report/src python3 -c "
from expense_report.screenshot import find_xlsx_in_folder
print(find_xlsx_in_folder('{폴더경로}'))
"
```

파일이 없으면 에러 메시지 출력 후 종료합니다.

### Step 2: 요약 시트 캡처

```bash
PYTHONPATH=~/.claude/skills/expense-report/src python3 -c "
from expense_report.screenshot import capture_summary_sheet
result = capture_summary_sheet('{xlsx_경로}', '{폴더경로}/요약.png')
print('캡처 성공' if result else '캡처 실패')
"
```

캡처가 성공하면 `{폴더경로}/요약.png` 파일이 생성됩니다.

**⚠️ 캡처 전 확인**: Excel이 실행 중이면 충돌할 수 있으므로, 사용자에게 Excel을 닫았는지 확인하세요.

## 재실행 동작

동일 폴더에서 `/expense`를 다시 실행하면:
- 이전에 수기 입력한 R8 항목의 값(계정과목, 사용내역, 경비금액, 동반자)이 보존됩니다
- R1~R7 항목은 최신 Notion 데이터와 규칙으로 다시 분류됩니다
- 따라서 Notion에 새 팀활동비를 등록한 후 재실행하면 R5→R1으로 승격됩니다
