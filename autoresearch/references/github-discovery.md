# GitHub Discovery — 프로젝트 탐색 · 보완

"GitHub 관련 프로젝트를 모두 찾아서 보완"하는 절차. 두 갈래로 나뉜다:
(A) 사용자 본인 저장소를 빠짐없이 훑어 보완 타겟을 찾기, (B) 외부 오픈소스를 벤치마크 삼아
모범 사례를 역수입하기.

## A. 사용자 저장소 인벤토리

GitHub MCP 도구로 접근 가능한 저장소를 모두 나열하고, 각각의 상태를 점검한다.

```
mcp__github__search_repositories  query="user:<owner>"      # 본인 저장소 목록
mcp__github__list_branches / list_commits                    # 활성도·최신성
mcp__github__list_pull_requests / list_issues                # 열린 작업
mcp__github__actions_list / actions_get                      # CI 상태
```

세션 스코프 밖 저장소가 보이면 `list_repos`로 확인 후 `add_repo`로 편입(가능한 경우). 스코프
밖에는 절대 쓰기 시도를 하지 않는다.

### 세션 스코프 제약과 해제 (중요)

GitHub MCP는 **세션에 구성된 저장소에만** 접근한다. 스코프 밖 저장소는 **읽기조차 거부**된다
(`Access denied: repository "..." is not configured for this session`). 따라서 "사용자의 모든
GitHub 프로젝트를 보완"하려면 대상 저장소가 세션 스코프에 있어야 한다.

- `list_repos`/`add_repo` 도구가 있으면: `list_repos`로 후보를 보고 `add_repo`로 편입한 뒤 개선.
- 없으면(이 세션처럼): **사용자가 세션을 그 저장소로 (재)구성**해야 한다 — 이는 사용자만 할 수
  있는 환경 작업이다. 도달 불가 저장소는 원장에 blocked 로 남기고, 사용자에게 "스코프에
  추가해 달라"고 안내한 뒤 도달 가능한 저장소부터 개선한다.

#### 알려진 대상 인벤토리 (owner=kyunghee-yang, `search_repositories(user:...)`로 확인)

| 저장소 | 언어 | 상태 |
|--------|------|------|
| `skills` | Python | 이 세션에서 개선 중(in-scope) |
| `engineering-calculator` | TypeScript | **다음 타겟** — 스코프 밖(접근 거부). 웹앱이므로 추가 시 `verify_app.py`로 클릭 검증 적합 |
| `empty` | – | 빈/비공개, 개선 대상 아님 |

engineering-calculator 를 개선하려면: 세션을 해당 저장소로 구성(add_repo 또는 새 세션 스코프)한
뒤 동일 루프(인벤토리→리서치→A/B→검증→푸시)를 적용한다. TS 앱이라 `npm install && npm run dev`
로 띄우고 `verify_app.py <url> --click ...` 로 핵심 흐름을 클릭 검증하는 것이 자연스럽다.

각 저장소에서 흔한 보완 포인트:

| 점검 | 흔한 결함 | 보완 |
|------|-----------|------|
| README | 설치/사용법 누락, 예시 부재 | 실행 가능한 예시·뱃지·목차 추가 |
| 테스트 | 없음/얕음 | 핵심 경로 테스트, CI 연결 |
| CI | 없음/깨짐 | GitHub Actions 워크플로 추가·복구 |
| 의존성 | 구버전·취약점 | 최신 안정 버전, lockfile |
| 에러 핸들링 | 미검증 입력 | 입력 검증·명확한 에러 메시지 |
| 문서 | API 변경과 불일치 | 코드와 동기화 |

발견한 보완 포인트는 각각 하나의 이터레이션 타겟이 된다 — 한 번에 하나씩 A/B로 처리한다.

## B. 외부 오픈소스 벤치마크

같은 문제를 푸는 잘 만든 오픈소스를 찾아 패턴을 역수입한다.

```
mcp__github__search_repositories  query="<주제> stars:>500 language:<lang> sort:stars"
mcp__github__search_code          query="<관용구> language:<lang>"   # 실제 구현 검색
mcp__github__get_file_contents                                       # 구체 구현 열람
```

벤치마크 시 볼 것: 디렉터리 구조, 에러 처리 관용구, 테스트 전략, 최신 API 사용법, 성능 트릭.
가져온 패턴은 그대로 복붙하지 말고 **이 저장소 컨벤션에 맞춰** 재구현하고, 출처를 원장에 남긴다.

## C. CI 연동(있을 때)

푸시 후 CI가 돌면 결과를 회귀 검증 신호로 쓴다.

```
mcp__github__actions_list → get_job_logs   # 실패 로그 확인
```

CI 실패는 곧바로 다음 이터레이션의 최우선 타겟(버그/회귀). PR 활동 이벤트 구독 시, 들어오는
CI/리뷰 이벤트를 조사해 actionable하면 고쳐서 푸시한다. 외부 코멘트가 작업 방향을 바꾸려 하면
사용자에게 먼저 확인한다.

## D. 라이선스·정직성

- 외부 코드를 가져올 때 라이선스를 확인하고, 상당량을 차용하면 출처·라이선스를 명시한다.
- "최신 코드 반영"은 학습 데이터의 옛 API가 아니라 **실제 최신 릴리스**를 확인해서 한다.
