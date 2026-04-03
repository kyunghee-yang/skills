# Claude Code Skills

Claude Code에서 반복 업무를 자동화하는 커스텀 스킬 모음.

## 스킬 목록

| 스킬 | 설명 | 의존성 |
|------|------|--------|
| [notion-issue](#notion-issue) | Notion 이슈 DB에 일감 등록 | Notion MCP |
| [task-check](#task-check) | 내 일감 현황 조회 및 상태 관리 | Notion MCP |
| [daily-report](#daily-report) | Gmail + Notion 알림 데일리 리포트 | Gmail API, Notion MCP |
| [review-resume](#review-resume) | 이력서 PDF 평가 및 면접 질문지 생성 | - |
| [review-codingtest](#review-codingtest) | 코딩테스트 PDF 코드 품질 평가 | - |
| [expense-report](#expense-report) | 법인카드 지출결의서 엑셀 자동 생성 | Notion MCP, Python 3.9+ |

---

## notion-issue

Notion 이슈 DB에 새 일감을 빠르게 등록합니다.

```
/notion-issue API 응답 시간 개선
"로그인 버그 이슈 등록해줘"
```

## task-check

Notion 이슈 DB에서 내 일감을 조회하고 상태를 관리합니다.

```
/task-check
"오늘 할 일 뭐 있어?"
"진행중인 일감 확인"
"OOO 건 완료 처리해줘"
```

## daily-report

Gmail 수신 메일과 Notion 알림을 수집하여 아침 데일리 리포트를 생성합니다.

```
/daily-report
"데일리 리포트"
"아침 보고"
```

### 초기 설정

Gmail API OAuth 인증이 필요합니다. 최초 실행 시 브라우저 인증 절차를 안내합니다.

## review-resume

이력서 PDF를 JD와 비교하여 S/A/B/C 등급을 산정하고 면접 질문지를 생성합니다.

```
/review-resume /path/to/이력서폴더
/review-resume /path/to/이력서폴더 --mode=면접
/review-resume /path/to/이력서폴더 --applicant=홍길동
```

### 주의사항

- 분석 결과는 대화 내 출력만 허용 (파일 저장 금지)
- 연락처, 주소 등 개인정보는 출력에 포함하지 않음
- 이력서를 외부 AI 서비스로 전송하므로 PIPA 적법성 검토 필요

## review-codingtest

프로그래머스 코딩테스트 결과 PDF를 분석하여 코드 품질과 AI 사용 의심도를 평가합니다.

```
/review-codingtest /path/to/결과.pdf
/review-codingtest /path/to/결과폴더 --applicant=홍길동
```

## expense-report

법인카드 승인내역(xls)을 파싱하여 지출결의서 엑셀을 자동 생성합니다.

```
/expense 202603
/expense /full/path/to/202603
"지출결의서 작성"
"이번달 경비 정리해줘"
```

### 초기 설정

첫 실행 시 사용자 정보를 입력받아 `~/.config/expense-report/config.json`을 생성합니다.

| 항목 | 설명 |
|------|------|
| 이름 | 기안자명 |
| 부서 | 소속 부서 |
| 팀 리더 여부 | Notion 팀활동비 조회 필요 여부 |
| 택시 도착지 | 집 동네 (김포, 부천 등) |
| 기본 경로 | 지출결의서 폴더 위치 |

### 분류 규칙

| 규칙 | 이름 | 조건 |
|------|------|------|
| R1 | 팀 커피 | Notion 팀활동비 매칭 |
| R2 | 택시 가승인 취소 | 카카오T택시_가승인 |
| R3 | 법인택시 | 카카오T일반택시(법인) |
| R4 | 일반 택시 | 가맹점에 "택시" 포함 |
| R5 | 카페 (확인필요) | 카페 키워드 매칭 |
| R6 | 점심 식대 | 11:00~13:59 |
| R7 | 저녁 식대 | 17:00~20:29 |
| R8 | 수기 필요 | 위 규칙 해당 없음 |

### 수기 입력 후 캡처

```
/expense-capture 202603
```

---

## 설치

```bash
git clone git@github.com:kyunghee-yang/skills.git ~/.claude/skills
```

## 필수 환경

- Claude Code (CLI 또는 Desktop)
- Notion MCP 서버 (notion-issue, task-check, daily-report, expense-report)
- Python 3.9+ (expense-report)
  ```bash
  pip install xlrd openpyxl Pillow
  ```
