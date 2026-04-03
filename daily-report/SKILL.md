---
name: daily-report
description: 주중 아침 데일리 리포트 생성. Gmail(khyang@wefun.io)에서 어제~오늘 수신 메일과 Notion 알림(notify@mail.notion.so)을 수집하여, 중요도 분류 및 이슈 그룹핑 후 리포트 파일을 생성한다. "데일리 리포트", "daily report", "아침 보고", "오늘 알림", "미확인 알림", "읽지 않은거 확인", "morning briefing", "morning report" 요청에 반드시 이 스킬을 사용하세요. /daily-report로 수동 실행 가능하며 cron으로 주중 10시 자동 실행 설정 가능. 단순 Gmail만 확인하거나 Notion만 확인하는 요청에도 데일리 리포트 맥락이면 이 스킬을 사용하세요.
---

# Daily Report

Gmail에서 어제~오늘 수신 메일과 Notion 알림을 수집하고, 중요도를 분류하여 데일리 리포트 파일을 생성한다.

## Prerequisites

- Gmail 스킬 계정 설정 완료 (`gmail:gmail` 스킬의 `setup_auth.py`로 work 계정 등록)
- Notion MCP 서버 연결 완료

## Execution Flow

아래 단계를 순서대로 실행한다. Step 1의 두 쿼리는 독립적이므로 병렬로 수행한다.

### Step 1: Gmail 수집 (2개 쿼리 병렬)

Gmail 스크립트로 khyang@wefun.io 계정의 메일을 조회한다. 기준은 **어제~오늘 수신** 메일이다.

**1a. 일반 메일 (Notion 알림 제외):**

```bash
GMAIL_DIR="/Users/ykh/.claude/skills/daily-report/gmail/scripts"
cd "$GMAIL_DIR" && uv run python list_messages.py --account work --query "newer_than:2d -from:notify@mail.notion.so" --max 50 --json
```

**1b. Notion 알림 (별도 수집):**

```bash
cd "$GMAIL_DIR" && uv run python list_messages.py --account work --query "from:notify@mail.notion.so newer_than:2d" --max 30 --json
```

snippet만으로 내용 파악이 어려운 중요 메일(Step 3 기준)은 `read_message.py`로 본문을 추가 조회한다:

```bash
cd "$GMAIL_DIR" && uv run python read_message.py --account work --id <message_id> --json
```

### Step 2: Notion 알림 분류 (subject 패턴 기반)

Step 1b에서 수집한 Notion 알림 메일을 subject 패턴으로 분류한다.

| subject 패턴 | 유형 | 기본 중요도 |
|---|---|---|
| `"나를 멘션했습니다"` | 직접 @멘션 | **중요** |
| `"블록을 업데이트함"` | 관찰 중 페이지 변경 | 일반 |
| `"메시지를 보냈습니다"` | 자동화/상태 변경 알림 | 일반 |

snippet에서 추가 정보를 파싱한다:
- `"상태 X Y"` → 상태 변경 (예: "진행 중 → 완료")
- `"담당자 양경희"` → 본인에게 담당자 지정됨 → **중요로 승격**

### Step 3: 멘션 상세 조회 (선택적)

Step 2에서 **중요**로 분류된 멘션 알림에 대해서만, Notion MCP `get-comments`로 해당 페이지의 댓글을 상세 조회하여 맥락을 파악한다. 일반 알림은 추가 조회하지 않는다.

### Step 4: 중요도 분류

수집된 일반 메일(Step 1a)과 Notion 알림(Step 2 결과)을 아래 규칙으로 분류한다.

**분류 순서** (위에서 아래로 체크, 먼저 매칭되면 해당 등급 부여):

#### 중요 (Action Required)

| 조건 | 설명 |
|------|------|
| Notion 직접 멘션 | subject에 "나를 멘션했습니다" 포함 |
| Notion 담당자 지정 | snippet에 "담당자 양경희" 포함 |
| 내부 도메인 + 액션 요구 | @wefun.io 또는 @snack24h.com에서 온 메일 중 답장/확인/승인 요구 |
| 긴급 키워드 | "긴급", "urgent", "장애", "incident", "blocker", "deadline", "ASAP" |
| 답장 요구 표현 | "확인 부탁", "검토해주세요", "승인 요청", "리뷰", "피드백", "reply needed" |

#### 일반 (Informational)

| 조건 | 설명 |
|------|------|
| Notion 페이지 업데이트 | subject에 "블록을 업데이트함" 포함 (멘션 아닌 단순 변경) |
| Notion 자동화 | subject에 "메시지를 보냈습니다" 포함 |
| 자동 발신 | noreply@, no-reply@, notifications@, alert@, automated@ |
| 모니터링/CI | GitHub, Sentry, Jenkins, Datadog, Slack, Jira 자동 알림 |
| 뉴스레터/마케팅 | 구독 메일, 프로모션, 뉴스레터 |
| 단순 공지 | 일방적 안내, 공지사항 (답장 불필요) |

**예외**: 일반으로 분류될 자동 알림이라도 "장애", "incident", "failure", "error" 등 긴급 키워드가 포함되면 중요로 승격한다.

### Step 5: 이슈 그룹핑

소스별(Gmail/Notion)이 아닌 **이슈별로 그룹핑**한다.
동일 주제에 대해 여러 소스에서 알림이 온 경우 하나의 이슈로 묶고, 하단에 출처를 나열한다.

그룹핑 기준:
- 같은 키워드/프로젝트명이 등장하는 항목끼리 묶기
- Gmail + Notion 알림이 동일 사안을 가리키면 하나로 합치기
- 묶을 수 없는 독립 항목은 단독 이슈로 표시

### Step 6: 리포트 파일 생성

수집/분류/그룹핑 결과를 아래 템플릿으로 작성하여 파일로 저장한다.

**저장 경로**: `~/daily-reports/YYYY-MM-DD.md`

디렉토리가 없으면 생성한다.

## Report Template

```
# Daily Report - {YYYY-MM-DD} ({요일})

> 중요 {n}건 / 일반 {n}건

## 지금 할 일

1. {이슈 제목} — {구체적 액션}
2. {이슈 제목} — {구체적 액션}
...

---

## 중요

### {이슈 제목}
{상황 요약 1-2문장}
- `{출처}` {발신자/페이지} — {핵심 내용}
- `{출처}` {발신자/페이지} — {핵심 내용}

### {이슈 제목}
{상황 요약 1-2문장}
- `{출처}` {발신자/페이지} — {핵심 내용}

---

## 일반 ({n}건)

- **{카테고리}** ({n}) — {한 줄 요약}
- **{카테고리}** ({n}) — {한 줄 요약}

---

## 리스크
{아래 패턴이 발견되면 명시}
- 여러 채널에서 동시에 알림이 온 이슈 (인시던트 가능성)
- 3일 이상 방치된 미확인 메일
- 마감 임박 언급
```

### 작성 규칙

- 이슈 제목: 10자 이내로 핵심만
- 상황 요약: 최대 2문장
- 출처 태그: `Gmail`, `Notion`, `Datadog`, `Sentry` 등 백틱으로 표시
- 일반 알림: 카테고리별 건수 + 한 줄 요약으로만 (상세 내역 불필요)
- "지금 할 일"은 최대 5개, 우선순위 순으로 정렬

## Output Rules

- 리포트 파일 저장 후, 터미널에도 요약 테이블 + 중요 항목 목록을 출력한다
- 중요 항목이 0건이면 "중요 알림 없음 - 좋은 아침입니다!" 메시지를 출력한다
- 일반 알림은 터미널 출력에서는 건수만 표시하고 상세는 파일에만 기록한다
