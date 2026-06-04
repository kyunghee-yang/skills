# Browser Verification — cmux / codex computer-use / Playwright

앱·UI 변경은 "테스트 통과"만으로 부족하다. **사람처럼 직접 클릭하며** 동작과 콘솔 에러를
확인한다. 환경에 따라 세 가지 경로가 있고, 가용한 것을 우선순위대로 쓴다.

## 환경 감지

```bash
# cmux 환경인가?
env | grep -i cmux ; command -v cmux
# codex computer-use가 있나?
command -v codex ; env | grep -i codex
# Playwright 브라우저가 있나? (이 저장소 환경엔 보통 있음)
echo "$PLAYWRIGHT_BROWSERS_PATH"; ls "$PLAYWRIGHT_BROWSERS_PATH" 2>/dev/null
```

감지 결과에 따라:

1. **cmux 내장 브라우저 + codex computer-use 사용 가능** → 1순위.
   cmux의 내장 브라우저로 앱을 열고, codex의 computer-use(스크린샷+클릭/타이핑)로 화면을 보며
   메뉴·버튼을 하나씩 눌러 흐름을 완주한다. 각 화면에서 콘솔/네트워크 에러와 깨진 UI를 잡는다.
   발견한 오류는 곧바로 이터레이션 타겟으로 만든다.
2. **Playwright 사용 가능** (이 저장소 환경의 기본 폴백) → 2순위. 아래 절차.
3. **둘 다 없음** → UI 자동 클릭은 생략하고, 가능한 범위(빌드/로그/단위테스트)로 검증한 뒤
   "수동 UI 검증은 환경 제약으로 생략"이라고 정직하게 보고한다.

## codex computer-use 클릭 검증 (cmux)

목표는 "기능이 실제로 된다"를 눈으로 확인하는 것. 절차:

1. 앱을 cmux 내장 브라우저로 연다(로컬 dev 서버 URL 또는 배포 URL).
2. computer-use로 스크린샷을 찍어 현재 화면을 파악한다.
3. 핵심 사용자 흐름을 하나씩 클릭하며 진행한다(예: 로그인 → 입력 → 계산 → 결과).
4. 각 단계에서: 의도한 화면 전환이 일어났는가? 콘솔 에러는 없는가? 값이 맞는가?
5. 실패 지점을 스크린샷과 함께 기록 → 다음 이터레이션 타겟.

한 번에 앱 하나씩, 화면 하나씩 꼼꼼히 본다. "대충 열어보고 됐다"가 아니라 흐름을 끝까지 완주한다.

## Playwright 폴백 절차

**바로 쓰는 도구**: `autoresearch/scripts/verify_app.py` — URL을 열고 지정한 텍스트를 순서대로
클릭하며 콘솔/페이지 에러를 수집해 통과/실패를 판정한다(콘솔 에러 0 + 흐름 완주 = 통과).

```bash
python3 autoresearch/scripts/verify_app.py http://localhost:5173 \
    --click "로그인" --click "계산" --screenshot /tmp/verify.png
# 종료 코드: 통과 0 / 실패 1 / 브라우저 미가용 2  → SHIP 게이트로 사용 가능
```

판정 코어(classify_console/build_report)는 브라우저 없이도 단위 테스트되며, 브라우저 래퍼는
Playwright sync API를 쓴다. Playwright 미설치/브라우저 빌드 불일치면 종료 코드 2로 알리니
cmux/codex 경로나 수동 검증으로 폴백한다. 직접 스크립트를 짜려면 아래 패턴을 참고한다.

브라우저 바이너리는 `$PLAYWRIGHT_BROWSERS_PATH`에 설치돼 있다. 헤드리스로 흐름을 자동화한다.

```bash
# 1) 앱 dev 서버 기동 (예: engineering-calculator 같은 TS 앱)
#    npm install && npm run dev  → http://localhost:5173 등
# 2) 검증 스크립트 실행
node autoresearch/scripts/.. 또는 즉석 스크립트로:
```

```js
// 즉석 검증 예시 (node, @playwright/test 또는 playwright 사용)
const { chromium } = require('playwright');
(async () => {
  const errors = [];
  const browser = await chromium.launch();           // PLAYWRIGHT_BROWSERS_PATH 자동 사용
  const page = await browser.newPage();
  page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto(process.env.APP_URL || 'http://localhost:5173');
  // 핵심 흐름 클릭
  await page.getByRole('button', { name: '계산' }).click().catch(()=>{});
  await page.screenshot({ path: '/tmp/verify.png', fullPage: true });
  console.log('CONSOLE_ERRORS', JSON.stringify(errors));
  await browser.close();
  process.exit(errors.length ? 1 : 0);
})();
```

- 콘솔 에러가 0이고 핵심 흐름이 완주되면 VERIFY 통과.
- 스크린샷(`/tmp/verify.png`)은 `SendUserFile`로 사용자에게 보여줄 수 있다.
- 셀렉터는 텍스트/role 기반으로 견고하게. 흐름 완주 실패 자체가 회귀 신호다.

## 검증 결과 처리

- 통과 → SHIP(커밋·푸시) 진행.
- 실패 → 채택 후보라도 **롤백**하고, 실패를 다음 이터레이션 최우선 타겟으로 등록.
- 어느 경로로 검증했는지(cmux/playwright/생략)를 커밋 메시지·원장에 정직하게 남긴다.
