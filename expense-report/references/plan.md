# Expense Report Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 하나카드 기명카드 승인내역(xls)을 읽어 회사 지출결의서 양식(xlsx)에 자동으로 데이터를 채우고, Notion 팀활동비 매칭 + 규칙 기반 자동 분류 + 영수증 첨부 + 요약 캡처까지 수행하는 Claude Code 스킬 + Python 스크립트 하이브리드 시스템

**Architecture:** Python 스크립트(main.py)가 xls 파싱, 분류, 엑셀 생성을 담당하고, Claude Code 스킬(SKILL.md)이 Notion MCP 조회 및 사용자 인터랙션을 오케스트레이션한다. 스크립트는 Notion 데이터를 JSON stdin으로 받아 독립 실행 가능하다.

**Tech Stack:** Python 3.9+, xlrd (xls 파싱), openpyxl (xlsx 생성), Pillow (이미지 크기), AppleScript (Excel 캡처)

**Spec:** `docs/superpowers/specs/2026-04-01-expense-report-design.md`

**Test data:** `/Users/ykh/Documents/drive/개인경비 지출결의서/2026/202603/` (3월 데이터 + 이미지 3장)

---

## File Map

| File | Responsibility |
|------|---------------|
| `src/expense-report/config.py` | 상수 정의 (기안자, 부서, 식대 상한, 경로 등) |
| `src/expense-report/parser.py` | xls 파싱: 2줄 1쌍 구조 → Transaction 리스트 |
| `src/expense-report/matcher.py` | Notion 데이터와 카드 거래 매칭 (사용일+금액) |
| `src/expense-report/classifier.py` | Rule 1~8 우선순위 분류 엔진 |
| `src/expense-report/writer.py` | 양식 복사 → Sheet1 원본 + Sheet2 분류 데이터 기입 |
| `src/expense-report/receipt.py` | 영수증 이미지 삽입 (최대 4.29인치 너비) |
| `src/expense-report/screenshot.py` | AppleScript Excel 요약 시트 캡처 |
| `src/expense-report/main.py` | CLI 엔트리포인트: 전체 파이프라인 조합 |
| `tests/expense-report/test_parser.py` | parser 테스트 |
| `tests/expense-report/test_matcher.py` | matcher 테스트 |
| `tests/expense-report/test_classifier.py` | classifier 테스트 |
| `tests/expense-report/test_writer.py` | writer 통합 테스트 |
| `tests/expense-report/test_receipt.py` | receipt 테스트 |
| `tests/expense-report/test_main.py` | main E2E 테스트 |
| `skills/expense-report/SKILL.md` | `/expense` Claude Code 스킬 정의 |
| `requirements.txt` | Python 의존성 |

---

### Task 1: Project Setup & Config

**Files:**
- Create: `src/expense-report/__init__.py`
- Create: `src/expense-report/config.py`
- Create: `tests/expense-report/__init__.py`
- Create: `requirements.txt`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p /Users/ykh/Documents/automate/src/expense-report
mkdir -p /Users/ykh/Documents/automate/tests/expense-report
touch /Users/ykh/Documents/automate/src/expense-report/__init__.py
touch /Users/ykh/Documents/automate/tests/expense-report/__init__.py
```

- [ ] **Step 2: Create requirements.txt**

```
xlrd>=2.0.2
openpyxl>=3.1.0
Pillow>=10.0.0
pytest>=7.0.0
```

- [ ] **Step 3: Install dependencies**

```bash
cd /Users/ykh/Documents/automate && pip3 install -r requirements.txt
```

Expected: All packages installed successfully

- [ ] **Step 4: Write config.py**

```python
# src/expense-report/config.py

DRAFTER_NAME = "양경희"
DEPARTMENT = "R&D본부"
CARD_LAST4 = "7592"

NOTION_DB_URL = "https://www.notion.so/wefun-platform/263270b243d0800faadbffde6ba5c9b0?v=263270b243d08023b856000c03fa97a0"
NOTION_USER_ID = "0f90d063-d2bb-4e09-9b39-f7bdc4883d2b"
NOTION_USER_URI = f"user://{NOTION_USER_ID}"

LUNCH_CAP = 10000
DINNER_CAP = 12000
LUNCH_HOURS = (11, 14)
DINNER_HOURS = (17, 22)
DOUBLE_MULTIPLIER = 2

TEMPLATE_PATH = "/Users/ykh/Documents/drive/개인경비 지출결의서/양식_법인카드_하나 20250716_개정.xlsx"
OUTPUT_FILENAME_TEMPLATE = "{yy}년{mm}월_법인카드_하나_양경희.xlsx"

RECEIPT_MAX_WIDTH_INCHES = 4.29
RECEIPT_MAX_WIDTH_EMU = int(4.29 * 914400)
RECEIPT_EXTENSIONS = {".jpg", ".jpeg", ".png"}
RECEIPT_ROW_GAP = 2

TAXI_HOME_ROUTE = "본사(강남) -> 집(김포)"

# xls parsing constants
XLS_DATA_START_ROW = 9  # 0-indexed
XLS_COL_DATE = 0
XLS_COL_TIME = 3
XLS_COL_MERCHANT = 6
XLS_COL_CARD_NUMBER = 7
XLS_COL_TYPE = 8
XLS_COL_AMOUNT = 9
XLS_COL_TRANSACTION_TYPE = 10
XLS_COL_APPROVAL_NUMBER = 11
XLS_COL_PURCHASE = 14
XLS_COL_PURCHASE_DATE = 15
XLS_COL_INSTALLMENT = 17
XLS_COL_VAT_OR_STATUS = 18

# Sheet 1 column mapping (1-indexed for openpyxl)
SHEET1_COL_DATE = 1        # A
SHEET1_COL_TIME = 4        # D
SHEET1_COL_MERCHANT = 7    # G
SHEET1_COL_CARD = 8        # H
SHEET1_COL_TYPE = 9        # I
SHEET1_COL_AMOUNT = 10     # J
SHEET1_COL_TXN_TYPE = 11   # K
SHEET1_COL_APPROVAL = 12   # L
SHEET1_COL_PURCHASE = 15   # O
SHEET1_COL_PURCHASE_DATE = 16  # P
SHEET1_COL_INSTALLMENT = 18   # R
SHEET1_COL_VAT = 19        # S
SHEET1_DATA_START_ROW = 10

# Sheet 2 column mapping (1-indexed)
SHEET2_COL_DRAFTER = 1     # A
SHEET2_COL_DEPT = 2        # B
SHEET2_COL_EXPENSE = 7     # G
SHEET2_COL_PROJECT = 8     # H
SHEET2_COL_USAGE = 10      # J
SHEET2_COL_COMPANION = 11  # K
SHEET2_COL_ROUTE = 12      # L
SHEET2_COL_VEHICLE = 13    # M
SHEET2_COL_ACCOUNT = 14    # N
SHEET2_DATA_START_ROW = 6
```

- [ ] **Step 5: Commit**

```bash
cd /Users/ykh/Documents/automate
git add src/expense-report/__init__.py src/expense-report/config.py tests/expense-report/__init__.py requirements.txt
git commit -m "feat: expense-report project setup and config constants"
```

---

### Task 2: XLS Parser

**Files:**
- Create: `src/expense-report/parser.py`
- Create: `tests/expense-report/test_parser.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/expense-report/test_parser.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from expense_report.parser import parse_xls, Transaction


TEST_XLS = "/Users/ykh/Documents/drive/개인경비 지출결의서/2026/202603/간편서비스_승인내역.xls"


def test_parse_xls_returns_transactions():
    transactions = parse_xls(TEST_XLS)
    assert len(transactions) > 0
    assert isinstance(transactions[0], Transaction)


def test_transaction_fields_populated():
    transactions = parse_xls(TEST_XLS)
    first = transactions[0]
    assert first.date != ""
    assert first.time != ""
    assert first.merchant != ""
    assert first.amount > 0


def test_cancelled_transactions_excluded():
    transactions = parse_xls(TEST_XLS)
    for txn in transactions:
        assert txn.status != "취소"


def test_amount_parsed_as_integer():
    transactions = parse_xls(TEST_XLS)
    for txn in transactions:
        assert isinstance(txn.amount, int)


def test_date_format():
    """이용일은 'YYYY.MM.DD' 형식"""
    transactions = parse_xls(TEST_XLS)
    for txn in transactions:
        parts = txn.date.split(".")
        assert len(parts) == 3
        assert len(parts[0]) == 4


def test_meta_extracted():
    """조회기간, 건수 등 메타데이터 추출"""
    transactions = parse_xls(TEST_XLS)
    # 3월 데이터: 39건 중 취소 3건 = 정상 36건 (paired rows)
    # 실제 정상 건수는 xls에서 확인
    assert len(transactions) > 30
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/ykh/Documents/automate && python3 -m pytest tests/expense-report/test_parser.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'expense_report'`

- [ ] **Step 3: Write parser.py**

```python
# src/expense-report/parser.py
from dataclasses import dataclass

import xlrd

from expense_report.config import (
    XLS_COL_AMOUNT,
    XLS_COL_APPROVAL_NUMBER,
    XLS_COL_CARD_NUMBER,
    XLS_COL_DATE,
    XLS_COL_INSTALLMENT,
    XLS_COL_MERCHANT,
    XLS_COL_PURCHASE,
    XLS_COL_PURCHASE_DATE,
    XLS_COL_TIME,
    XLS_COL_TRANSACTION_TYPE,
    XLS_COL_TYPE,
    XLS_COL_VAT_OR_STATUS,
    XLS_DATA_START_ROW,
)


@dataclass
class Transaction:
    date: str
    time: str
    merchant: str
    card_number: str
    usage_type: str
    amount: int
    transaction_type: str
    approval_number: str
    purchase_status: str
    purchase_date: str
    installment: str
    vat: str
    status: str


def _parse_amount(raw: str) -> int:
    if not raw:
        return 0
    cleaned = str(raw).replace(",", "").replace("원", "").strip()
    if not cleaned:
        return 0
    return int(float(cleaned))


def _cell_str(sheet, row: int, col: int) -> str:
    val = sheet.cell(row, col).value
    if val is None or val == "":
        return ""
    return str(val).strip()


def parse_xls(file_path: str) -> list[Transaction]:
    workbook = xlrd.open_workbook(file_path)
    sheet = workbook.sheet_by_index(0)

    transactions = []
    row = XLS_DATA_START_ROW

    while row + 1 < sheet.nrows:
        date_val = _cell_str(sheet, row, XLS_COL_DATE)
        if not date_val:
            row += 2
            continue

        status = _cell_str(sheet, row + 1, XLS_COL_VAT_OR_STATUS)
        if status == "취소":
            row += 2
            continue

        txn = Transaction(
            date=date_val,
            time=_cell_str(sheet, row, XLS_COL_TIME),
            merchant=_cell_str(sheet, row, XLS_COL_MERCHANT),
            card_number=_cell_str(sheet, row, XLS_COL_CARD_NUMBER),
            usage_type=_cell_str(sheet, row, XLS_COL_TYPE),
            amount=_parse_amount(_cell_str(sheet, row, XLS_COL_AMOUNT)),
            transaction_type=_cell_str(sheet, row, XLS_COL_TRANSACTION_TYPE),
            approval_number=_cell_str(sheet, row, XLS_COL_APPROVAL_NUMBER),
            purchase_status=_cell_str(sheet, row, XLS_COL_PURCHASE),
            purchase_date=_cell_str(sheet, row, XLS_COL_PURCHASE_DATE),
            installment=_cell_str(sheet, row, XLS_COL_INSTALLMENT),
            vat=_cell_str(sheet, row, XLS_COL_VAT_OR_STATUS),
            status=status,
        )
        transactions.append(txn)
        row += 2

    return transactions
```

Note: `src/expense-report` 디렉토리를 Python import 가능하게 하려면 디렉토리명의 하이픈을 언더스코어로 변경해야 합니다.

```bash
mv /Users/ykh/Documents/automate/src/expense-report /Users/ykh/Documents/automate/src/expense_report
mv /Users/ykh/Documents/automate/tests/expense-report /Users/ykh/Documents/automate/tests/expense_report
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/ykh/Documents/automate && python3 -m pytest tests/expense_report/test_parser.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/ykh/Documents/automate
git add src/expense_report/parser.py tests/expense_report/test_parser.py
git commit -m "feat: xls parser — reads card transactions, excludes cancellations"
```

---

### Task 3: Notion Data Matcher

**Files:**
- Create: `src/expense_report/matcher.py`
- Create: `tests/expense_report/test_matcher.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/expense_report/test_matcher.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from expense_report.matcher import NotionEntry, match_transactions
from expense_report.parser import Transaction


def _make_txn(date: str, amount: int, merchant: str = "바나프레소") -> Transaction:
    return Transaction(
        date=date, time="13:00", merchant=merchant,
        card_number="4201-****-****-7592", usage_type="국내일반",
        amount=amount, transaction_type="국내 일시불",
        approval_number="12345678", purchase_status="매입",
        purchase_date="2026-03-28", installment="-", vat="0",
        status="정상",
    )


def _make_notion(date: str, amount: float, companions: list[str]) -> NotionEntry:
    return NotionEntry(date=date, amount=amount, companions=companions)


def test_exact_match():
    txns = [_make_txn("2026.03.27", 27200)]
    notion = [_make_notion("2026-03-27", 27200, ["양경희", "김보민"])]
    matches = match_transactions(txns, notion)
    assert 0 in matches
    assert matches[0].companions == ["양경희", "김보민"]


def test_no_match_different_amount():
    txns = [_make_txn("2026.03.27", 27200)]
    notion = [_make_notion("2026-03-27", 15000, ["양경희"])]
    matches = match_transactions(txns, notion)
    assert 0 not in matches


def test_no_match_different_date():
    txns = [_make_txn("2026.03.27", 27200)]
    notion = [_make_notion("2026-03-28", 27200, ["양경희"])]
    matches = match_transactions(txns, notion)
    assert 0 not in matches


def test_multiple_transactions_partial_match():
    txns = [
        _make_txn("2026.03.27", 27200),
        _make_txn("2026.03.27", 2000),
        _make_txn("2026.03.26", 11300),
    ]
    notion = [
        _make_notion("2026-03-27", 27200, ["양경희", "김보민"]),
        _make_notion("2026-03-26", 11300, ["양경희", "성태현"]),
    ]
    matches = match_transactions(txns, notion)
    assert 0 in matches
    assert 1 not in matches
    assert 2 in matches
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/ykh/Documents/automate && python3 -m pytest tests/expense_report/test_matcher.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: Write matcher.py**

```python
# src/expense_report/matcher.py
from dataclasses import dataclass

from expense_report.parser import Transaction


@dataclass
class NotionEntry:
    date: str       # "2026-03-27" (ISO format)
    amount: float
    companions: list[str]


def _normalize_date(date_str: str) -> str:
    """'2026.03.27' 또는 '2026-03-27' → '2026-03-27'"""
    return date_str.replace(".", "-")


def match_transactions(
    transactions: list[Transaction],
    notion_entries: list[NotionEntry],
) -> dict[int, NotionEntry]:
    """카드 거래와 Notion 팀활동비를 (날짜, 금액)으로 매칭.

    Returns: {transaction_index: matched NotionEntry}
    """
    notion_lookup: dict[tuple[str, int], NotionEntry] = {}
    for entry in notion_entries:
        key = (_normalize_date(entry.date), int(entry.amount))
        notion_lookup[key] = entry

    matches: dict[int, NotionEntry] = {}
    used_keys: set[tuple[str, int]] = set()

    for idx, txn in enumerate(transactions):
        key = (_normalize_date(txn.date), txn.amount)
        if key in notion_lookup and key not in used_keys:
            matches[idx] = notion_lookup[key]
            used_keys.add(key)

    return matches


def parse_notion_json(raw_results: list[dict], user_map: dict[str, str]) -> list[NotionEntry]:
    """Notion query 결과 JSON을 NotionEntry 리스트로 변환.

    Args:
        raw_results: Notion DB query 결과의 results 배열
        user_map: {"user://xxx": "이름"} 매핑
    """
    entries = []
    for record in raw_results:
        usage = record.get("사용내역", "")
        if usage != "커피":
            continue

        date = record.get("date:사용일:start", "")
        amount = record.get("금액", 0)
        if not date or not amount:
            continue

        companion_raw = record.get("동반자", "[]")
        if isinstance(companion_raw, str):
            import json
            companion_ids = json.loads(companion_raw)
        else:
            companion_ids = companion_raw

        companions = []
        for uid in companion_ids:
            name = user_map.get(uid, uid)
            companions.append(name)

        entries.append(NotionEntry(date=date, amount=amount, companions=companions))

    return entries
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/ykh/Documents/automate && python3 -m pytest tests/expense_report/test_matcher.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/ykh/Documents/automate
git add src/expense_report/matcher.py tests/expense_report/test_matcher.py
git commit -m "feat: Notion transaction matcher — date+amount key matching"
```

---

### Task 4: Classification Engine

**Files:**
- Create: `src/expense_report/classifier.py`
- Create: `tests/expense_report/test_classifier.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/expense_report/test_classifier.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from expense_report.classifier import classify, Classification
from expense_report.matcher import NotionEntry
from expense_report.parser import Transaction


def _txn(merchant: str, time: str, amount: int) -> Transaction:
    return Transaction(
        date="2026.03.27", time=time, merchant=merchant,
        card_number="4201-****-****-7592", usage_type="국내일반",
        amount=amount, transaction_type="국내 일시불",
        approval_number="12345678", purchase_status="매입",
        purchase_date="2026-03-28", installment="-", vat="0",
        status="정상",
    )


# Rule 1: Notion 팀활동비 매칭
def test_rule1_notion_match():
    txn = _txn("바나프레소", "13:00", 27200)
    notion = NotionEntry(date="2026-03-27", amount=27200, companions=["양경희", "김보민"])
    result = classify(txn, notion_match=notion)
    assert result.usage == "팀 커피"
    assert result.expense_amount == 27200
    assert result.account == "복리후생비[회식비]"
    assert result.companion == "양경희,김보민"
    assert result.rule_number == 1


# Rule 2: 카카오T택시_가승인
def test_rule2_taxi_preauth():
    txn = _txn("카카오T택시_가승인", "22:16", 39900)
    result = classify(txn)
    assert result.usage == "택시 카드 선승인 취소 건"
    assert result.expense_amount == 0
    assert result.account == "여비교통비[택시]"
    assert result.rule_number == 2


# Rule 3: 카카오T일반택시(법인)
def test_rule3_corporate_taxi():
    txn = _txn("카카오T일반택시(법인)_0", "23:01", 40100)
    result = classify(txn)
    assert result.usage == "야근 택시비(배포)"
    assert result.expense_amount == 40100
    assert result.account == "여비교통비[택시]"
    assert result.rule_number == 3


# Rule 4: 일반 택시
def test_rule4_general_taxi():
    txn = _txn("카카오T일반택시_0", "23:30", 15000)
    result = classify(txn)
    assert result.expense_amount == 15000
    assert result.account == "여비교통비[택시]"
    assert result.route == "본사(강남) -> 집(김포)"
    assert result.is_manual is True  # 사용내역은 수기
    assert result.rule_number == 4


# Rule 5: 점심 식대
def test_rule5_lunch_under_cap():
    txn = _txn("신복면관", "12:30", 9800)
    result = classify(txn)
    assert result.usage == "점심 식대"
    assert result.expense_amount == 9800
    assert result.account == "복리후생비[식비]"
    assert result.companion == "양경희"
    assert result.rule_number == 5


def test_rule5_lunch_over_cap():
    txn = _txn("레스토랑", "12:00", 15000)
    result = classify(txn)
    assert result.expense_amount == 10000


def test_rule5_lunch_double_cap():
    txn = _txn("고급식당", "12:30", 25000)
    result = classify(txn)
    assert result.companion == "양경희,확인필요"


# Rule 6: 저녁 식대
def test_rule6_dinner_under_cap():
    txn = _txn("맥도날드", "19:00", 10000)
    result = classify(txn)
    assert result.usage == "저녁 식대"
    assert result.expense_amount == 10000
    assert result.account == "복리후생비[식비]"
    assert result.rule_number == 6


def test_rule6_dinner_over_cap():
    txn = _txn("맥도날드", "20:00", 16000)
    result = classify(txn)
    assert result.expense_amount == 12000


def test_rule6_dinner_double_cap():
    txn = _txn("고급식당", "18:00", 30000)
    result = classify(txn)
    assert result.companion == "양경희,확인필요"


# Rule 8: 수기
def test_rule8_manual():
    txn = _txn("네이버페이", "09:00", 50000)
    result = classify(txn)
    assert result.is_manual is True
    assert result.rule_number == 8


# Edge: 택시가 Notion에도 매칭되면 Rule 1 우선
def test_notion_takes_priority_over_taxi():
    txn = _txn("카카오T택시", "22:00", 5000)
    notion = NotionEntry(date="2026-03-27", amount=5000, companions=["양경희"])
    result = classify(txn, notion_match=notion)
    assert result.rule_number == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/ykh/Documents/automate && python3 -m pytest tests/expense_report/test_classifier.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: Write classifier.py**

```python
# src/expense_report/classifier.py
from dataclasses import dataclass, field

from expense_report.config import (
    DINNER_CAP,
    DINNER_HOURS,
    DOUBLE_MULTIPLIER,
    DRAFTER_NAME,
    LUNCH_CAP,
    LUNCH_HOURS,
    TAXI_HOME_ROUTE,
)
from expense_report.matcher import NotionEntry
from expense_report.parser import Transaction


@dataclass
class Classification:
    usage: str = ""
    expense_amount: int = 0
    account: str = ""
    companion: str = ""
    route: str = ""
    is_manual: bool = False
    rule_number: int = 8
    manual_fields: list[str] = field(default_factory=list)


def _parse_hour(time_str: str) -> int:
    parts = time_str.split(":")
    return int(parts[0])


def _is_in_hours(time_str: str, hour_range: tuple[int, int]) -> bool:
    hour = _parse_hour(time_str)
    return hour_range[0] <= hour < hour_range[1]


def classify(txn: Transaction, notion_match: NotionEntry | None = None) -> Classification:
    # Rule 1: Notion 팀활동비 매칭
    if notion_match is not None:
        return Classification(
            usage="팀 커피",
            expense_amount=txn.amount,
            account="복리후생비[회식비]",
            companion=",".join(notion_match.companions),
            rule_number=1,
        )

    merchant = txn.merchant

    # Rule 2: 카카오T택시_가승인
    if merchant == "카카오T택시_가승인":
        return Classification(
            usage="택시 카드 선승인 취소 건",
            expense_amount=0,
            account="여비교통비[택시]",
            companion=DRAFTER_NAME,
            rule_number=2,
        )

    # Rule 3: 카카오T일반택시(법인)
    if merchant.startswith("카카오T일반택시(법인)"):
        return Classification(
            usage="야근 택시비(배포)",
            expense_amount=txn.amount,
            account="여비교통비[택시]",
            companion=DRAFTER_NAME,
            rule_number=3,
        )

    # Rule 4: 일반 택시 (가맹점명에 "택시" 포함)
    if "택시" in merchant:
        return Classification(
            expense_amount=txn.amount,
            account="여비교통비[택시]",
            companion=DRAFTER_NAME,
            route=TAXI_HOME_ROUTE,
            is_manual=True,
            rule_number=4,
            manual_fields=["usage"],
        )

    # Rule 5: 점심 식대 (11:00~14:00)
    if _is_in_hours(txn.time, LUNCH_HOURS):
        companion = DRAFTER_NAME
        if txn.amount >= LUNCH_CAP * DOUBLE_MULTIPLIER:
            companion = f"{DRAFTER_NAME},확인필요"
        return Classification(
            usage="점심 식대",
            expense_amount=min(txn.amount, LUNCH_CAP),
            account="복리후생비[식비]",
            companion=companion,
            rule_number=5,
        )

    # Rule 6: 저녁 식대 (17:00~22:00)
    if _is_in_hours(txn.time, DINNER_HOURS):
        companion = DRAFTER_NAME
        if txn.amount >= DINNER_CAP * DOUBLE_MULTIPLIER:
            companion = f"{DRAFTER_NAME},확인필요"
        return Classification(
            usage="저녁 식대",
            expense_amount=min(txn.amount, DINNER_CAP),
            account="복리후생비[식비]",
            companion=companion,
            rule_number=6,
        )

    # Rule 8: 수기 입력
    return Classification(
        is_manual=True,
        rule_number=8,
        manual_fields=["usage", "expense_amount", "account", "companion"],
    )
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/ykh/Documents/automate && python3 -m pytest tests/expense_report/test_classifier.py -v
```

Expected: All 12 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/ykh/Documents/automate
git add src/expense_report/classifier.py tests/expense_report/test_classifier.py
git commit -m "feat: classification engine — 8 priority rules for expense categorization"
```

---

### Task 5: Excel Writer (Sheet 1 + Sheet 2)

**Files:**
- Create: `src/expense_report/writer.py`
- Create: `tests/expense_report/test_writer.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/expense_report/test_writer.py
import os
import sys
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import openpyxl

from expense_report.classifier import Classification
from expense_report.config import TEMPLATE_PATH
from expense_report.parser import Transaction
from expense_report.writer import write_expense_report


def _txn(date: str, time: str, merchant: str, amount: int) -> Transaction:
    return Transaction(
        date=date, time=time, merchant=merchant,
        card_number="4201-****-****-7592", usage_type="국내일반",
        amount=amount, transaction_type="국내 일시불",
        approval_number="12345678", purchase_status="매입",
        purchase_date="2026-03-28", installment="-", vat="1000",
        status="정상",
    )


def test_write_creates_file():
    transactions = [_txn("2026.03.27", "13:00", "바나프레소", 10300)]
    classifications = [
        Classification(
            usage="팀 커피", expense_amount=10300,
            account="복리후생비[회식비]", companion="양경희,김보민",
            rule_number=1,
        )
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test_output.xlsx")
        write_expense_report(transactions, classifications, output_path)
        assert os.path.exists(output_path)


def test_sheet1_data_filled():
    transactions = [_txn("2026.03.27", "13:00", "바나프레소", 10300)]
    classifications = [
        Classification(usage="팀 커피", expense_amount=10300,
                       account="복리후생비[회식비]", companion="양경희,김보민",
                       rule_number=1)
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test_output.xlsx")
        write_expense_report(transactions, classifications, output_path)
        wb = openpyxl.load_workbook(output_path, data_only=True)
        ws = wb["1.매출내역(원본)"]
        # Row 10 = first data entry
        assert ws.cell(10, 1).value == "2026.03.27"  # A10: 이용일
        assert ws.cell(10, 7).value == "바나프레소"    # G10: 가맹점명
        assert ws.cell(10, 10).value == 10300          # J10: 승인금액


def test_sheet2_classification_filled():
    transactions = [_txn("2026.03.27", "13:00", "바나프레소", 10300)]
    classifications = [
        Classification(usage="팀 커피", expense_amount=10300,
                       account="복리후생비[회식비]", companion="양경희,김보민",
                       rule_number=1)
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test_output.xlsx")
        write_expense_report(transactions, classifications, output_path)
        wb = openpyxl.load_workbook(output_path, data_only=True)
        ws = wb["2.(기명카드)사용내역"]
        # Row 6 = first data entry
        assert ws.cell(6, 1).value == "양경희"          # A6: 기안자
        assert ws.cell(6, 2).value == "R&D본부"         # B6: 부서
        assert ws.cell(6, 7).value == 10300             # G6: 경비 청구액
        assert ws.cell(6, 10).value == "팀 커피"         # J6: 사용내역
        assert ws.cell(6, 11).value == "양경희,김보민"    # K6: 동반자
        assert ws.cell(6, 14).value == "복리후생비[회식비]"  # N6: 계정과목


def test_manual_items_have_yellow_background():
    transactions = [_txn("2026.03.27", "09:00", "네이버페이", 50000)]
    classifications = [
        Classification(is_manual=True, rule_number=8,
                       manual_fields=["usage", "expense_amount", "account", "companion"])
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = os.path.join(tmpdir, "test_output.xlsx")
        write_expense_report(transactions, classifications, output_path)
        wb = openpyxl.load_workbook(output_path)
        ws = wb["2.(기명카드)사용내역"]
        fill = ws.cell(6, 10).fill  # J6: 사용내역
        assert fill.start_color.rgb == "00FFFF00" or fill.fgColor.rgb == "00FFFF00"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/ykh/Documents/automate && python3 -m pytest tests/expense_report/test_writer.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: Write writer.py**

```python
# src/expense_report/writer.py
import warnings

import openpyxl
from openpyxl.styles import PatternFill

from expense_report.classifier import Classification
from expense_report.config import (
    DEPARTMENT,
    DRAFTER_NAME,
    SHEET1_COL_AMOUNT,
    SHEET1_COL_APPROVAL,
    SHEET1_COL_CARD,
    SHEET1_COL_DATE,
    SHEET1_COL_INSTALLMENT,
    SHEET1_COL_MERCHANT,
    SHEET1_COL_PURCHASE,
    SHEET1_COL_PURCHASE_DATE,
    SHEET1_COL_TIME,
    SHEET1_COL_TXN_TYPE,
    SHEET1_COL_TYPE,
    SHEET1_COL_VAT,
    SHEET1_DATA_START_ROW,
    SHEET2_COL_ACCOUNT,
    SHEET2_COL_COMPANION,
    SHEET2_COL_DEPT,
    SHEET2_COL_DRAFTER,
    SHEET2_COL_EXPENSE,
    SHEET2_COL_ROUTE,
    SHEET2_COL_USAGE,
    SHEET2_DATA_START_ROW,
    TEMPLATE_PATH,
)
from expense_report.parser import Transaction

YELLOW_FILL = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")

MANUAL_HIGHLIGHT_COLS = [
    SHEET2_COL_EXPENSE,    # G
    SHEET2_COL_USAGE,      # J
    SHEET2_COL_COMPANION,  # K
    SHEET2_COL_ACCOUNT,    # N
]


def _write_sheet1(ws, transactions: list[Transaction]) -> None:
    row = SHEET1_DATA_START_ROW
    for txn in transactions:
        ws.cell(row, SHEET1_COL_DATE, txn.date)
        ws.cell(row, SHEET1_COL_TIME, txn.time)
        ws.cell(row, SHEET1_COL_MERCHANT, txn.merchant)
        ws.cell(row, SHEET1_COL_CARD, txn.card_number)
        ws.cell(row, SHEET1_COL_TYPE, txn.usage_type)
        ws.cell(row, SHEET1_COL_AMOUNT, txn.amount)
        ws.cell(row, SHEET1_COL_TXN_TYPE, txn.transaction_type)
        ws.cell(row, SHEET1_COL_APPROVAL, txn.approval_number)
        ws.cell(row, SHEET1_COL_PURCHASE, txn.purchase_status)
        ws.cell(row, SHEET1_COL_PURCHASE_DATE, txn.purchase_date)
        ws.cell(row, SHEET1_COL_INSTALLMENT, txn.installment)
        ws.cell(row, SHEET1_COL_VAT, txn.vat)
        ws.cell(row + 1, SHEET1_COL_VAT, txn.status)
        row += 2


def _write_sheet2(
    ws,
    transactions: list[Transaction],
    classifications: list[Classification],
) -> None:
    row = SHEET2_DATA_START_ROW
    for txn, cls in zip(transactions, classifications):
        ws.cell(row, SHEET2_COL_DRAFTER, DRAFTER_NAME)
        ws.cell(row, SHEET2_COL_DEPT, DEPARTMENT)

        if cls.is_manual and "expense_amount" in cls.manual_fields:
            for col in MANUAL_HIGHLIGHT_COLS:
                ws.cell(row, col).fill = YELLOW_FILL
        else:
            ws.cell(row, SHEET2_COL_EXPENSE, cls.expense_amount)

        if cls.usage:
            ws.cell(row, SHEET2_COL_USAGE, cls.usage)

        if cls.companion:
            ws.cell(row, SHEET2_COL_COMPANION, cls.companion)

        if cls.route:
            ws.cell(row, SHEET2_COL_ROUTE, cls.route)

        if cls.account:
            ws.cell(row, SHEET2_COL_ACCOUNT, cls.account)

        # 수기 필요 필드에만 노란 배경
        if cls.is_manual:
            for field_name in cls.manual_fields:
                col = _field_to_col(field_name)
                if col:
                    ws.cell(row, col).fill = YELLOW_FILL

        row += 1


def _field_to_col(field_name: str) -> int | None:
    mapping = {
        "usage": SHEET2_COL_USAGE,
        "expense_amount": SHEET2_COL_EXPENSE,
        "account": SHEET2_COL_ACCOUNT,
        "companion": SHEET2_COL_COMPANION,
    }
    return mapping.get(field_name)


def write_expense_report(
    transactions: list[Transaction],
    classifications: list[Classification],
    output_path: str,
) -> None:
    warnings.filterwarnings("ignore", category=UserWarning)
    wb = openpyxl.load_workbook(TEMPLATE_PATH)

    _write_sheet1(wb["1.매출내역(원본)"], transactions)
    _write_sheet2(wb["2.(기명카드)사용내역"], transactions, classifications)

    wb.save(output_path)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/ykh/Documents/automate && python3 -m pytest tests/expense_report/test_writer.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/ykh/Documents/automate
git add src/expense_report/writer.py tests/expense_report/test_writer.py
git commit -m "feat: Excel writer — fills Sheet1 raw data + Sheet2 classifications"
```

---

### Task 6: Receipt Image Attachment

**Files:**
- Create: `src/expense_report/receipt.py`
- Create: `tests/expense_report/test_receipt.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/expense_report/test_receipt.py
import os
import sys
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import openpyxl

from expense_report.receipt import attach_receipts, collect_receipt_files, validate_taxi_receipts


TEST_FOLDER = "/Users/ykh/Documents/drive/개인경비 지출결의서/2026/202603"


def test_collect_receipt_files():
    files = collect_receipt_files(TEST_FOLDER)
    assert len(files) == 3
    assert all(f.endswith((".jpg", ".jpeg", ".png", ".JPG", ".JPEG", ".PNG")) for f in files)


def test_collect_sorted_by_name():
    files = collect_receipt_files(TEST_FOLDER)
    names = [os.path.basename(f) for f in files]
    assert names == sorted(names)


def test_attach_receipts_adds_images():
    files = collect_receipt_files(TEST_FOLDER)
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a minimal workbook with "영수증 첨부" sheet
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "영수증 첨부"
        test_path = os.path.join(tmpdir, "test.xlsx")
        wb.save(test_path)

        wb = openpyxl.load_workbook(test_path)
        attach_receipts(wb["영수증 첨부"], files)
        wb.save(test_path)

        wb2 = openpyxl.load_workbook(test_path)
        ws2 = wb2["영수증 첨부"]
        assert len(ws2._images) == 3


def test_validate_taxi_receipts_warns():
    has_taxi = True
    receipt_files = []  # no receipts
    warning = validate_taxi_receipts(has_taxi, receipt_files)
    assert warning is not None
    assert "택시비" in warning


def test_validate_taxi_no_warning_with_receipts():
    has_taxi = True
    receipt_files = ["/some/file.jpg"]
    warning = validate_taxi_receipts(has_taxi, receipt_files)
    assert warning is None


def test_validate_no_taxi_no_warning():
    warning = validate_taxi_receipts(False, [])
    assert warning is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/ykh/Documents/automate && python3 -m pytest tests/expense_report/test_receipt.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: Write receipt.py**

```python
# src/expense_report/receipt.py
import os

from openpyxl.drawing.image import Image as XlImage
from openpyxl.utils.units import inches_to_EMU
from PIL import Image as PilImage

from expense_report.config import RECEIPT_EXTENSIONS, RECEIPT_MAX_WIDTH_INCHES, RECEIPT_ROW_GAP


def collect_receipt_files(folder_path: str) -> list[str]:
    files = []
    for fname in sorted(os.listdir(folder_path)):
        if os.path.splitext(fname)[1].lower() in RECEIPT_EXTENSIONS:
            files.append(os.path.join(folder_path, fname))
    return files


def validate_taxi_receipts(has_taxi: bool, receipt_files: list[str]) -> str | None:
    if not has_taxi:
        return None
    if not receipt_files:
        return "택시비 항목이 있지만 영수증 이미지가 없습니다. 영수증을 폴더에 추가한 후 다시 실행하세요."
    return None


def attach_receipts(ws, file_paths: list[str]) -> None:
    current_row = 1
    max_width_px = int(RECEIPT_MAX_WIDTH_INCHES * 72)  # 72 DPI baseline

    for fpath in file_paths:
        pil_img = PilImage.open(fpath)
        orig_width, orig_height = pil_img.size
        pil_img.close()

        if orig_width > max_width_px:
            scale = max_width_px / orig_width
            new_width = max_width_px
            new_height = int(orig_height * scale)
        else:
            new_width = orig_width
            new_height = orig_height

        xl_img = XlImage(fpath)
        xl_img.width = new_width
        xl_img.height = new_height

        cell_ref = f"A{current_row}"
        ws.add_image(xl_img, cell_ref)

        rows_needed = max(1, new_height // 15)  # ~15px per row default height
        current_row += rows_needed + RECEIPT_ROW_GAP
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/ykh/Documents/automate && python3 -m pytest tests/expense_report/test_receipt.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Commit**

```bash
cd /Users/ykh/Documents/automate
git add src/expense_report/receipt.py tests/expense_report/test_receipt.py
git commit -m "feat: receipt attachment — images with 4.29in max width + taxi validation"
```

---

### Task 7: Screenshot Module

**Files:**
- Create: `src/expense_report/screenshot.py`

- [ ] **Step 1: Write screenshot.py**

```python
# src/expense_report/screenshot.py
import glob
import os
import subprocess
import time


def capture_summary_sheet(xlsx_path: str, output_png_path: str) -> bool:
    """Excel에서 요약 시트를 열고 캡처하여 PNG로 저장.

    Returns: True if capture succeeded
    """
    abs_xlsx = os.path.abspath(xlsx_path)
    abs_png = os.path.abspath(output_png_path)

    open_script = f'''
    tell application "Microsoft Excel"
        activate
        open POSIX file "{abs_xlsx}"
        delay 2
        tell active workbook
            set active_sheet to sheet "요약"
            activate object active_sheet
        end tell
        delay 1
    end tell
    '''

    try:
        subprocess.run(["osascript", "-e", open_script], check=True, timeout=15)
        time.sleep(1)

        # Get Excel window ID
        wid_script = '''
        tell application "System Events"
            tell process "Microsoft Excel"
                set wid to id of front window
            end tell
        end tell
        return wid
        '''
        result = subprocess.run(
            ["osascript", "-e", wid_script],
            capture_output=True, text=True, timeout=10,
        )
        window_id = result.stdout.strip()

        if window_id:
            subprocess.run(
                ["screencapture", "-l", window_id, abs_png],
                check=True, timeout=10,
            )
        else:
            subprocess.run(
                ["screencapture", "-w", abs_png],
                check=True, timeout=10,
            )

        # Close without saving
        close_script = '''
        tell application "Microsoft Excel"
            close active workbook saving no
        end tell
        '''
        subprocess.run(["osascript", "-e", close_script], timeout=10)

        return os.path.exists(abs_png)

    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def find_xlsx_in_folder(folder_path: str) -> str | None:
    pattern = os.path.join(folder_path, "*법인카드*양경희*.xlsx")
    matches = glob.glob(pattern)
    if not matches:
        return None
    return matches[0]
```

- [ ] **Step 2: Commit**

```bash
cd /Users/ykh/Documents/automate
git add src/expense_report/screenshot.py
git commit -m "feat: screenshot module — AppleScript Excel summary capture"
```

Note: 스크린샷 모듈은 macOS GUI 의존성 때문에 자동화 테스트 대신 수동 검증으로 확인합니다.

---

### Task 8: Main CLI Entrypoint

**Files:**
- Create: `src/expense_report/main.py`
- Create: `tests/expense_report/test_main.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/expense_report/test_main.py
import json
import os
import sys
import tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from expense_report.main import run_pipeline


TEST_FOLDER = "/Users/ykh/Documents/drive/개인경비 지출결의서/2026/202603"


def test_run_pipeline_creates_xlsx():
    """Notion 데이터 없이 실행해도 엑셀이 생성됨"""
    with tempfile.TemporaryDirectory() as tmpdir:
        # 임시 폴더에 xls 심링크
        xls_src = os.path.join(TEST_FOLDER, "간편서비스_승인내역.xls")
        xls_dst = os.path.join(tmpdir, "간편서비스_승인내역.xls")
        os.symlink(xls_src, xls_dst)

        result = run_pipeline(tmpdir, notion_data=None)
        assert os.path.exists(result["created_file"])
        assert isinstance(result["manual_items"], list)
        assert result["total_count"] > 0


def test_run_pipeline_with_notion_data():
    """Notion 매칭 데이터로 팀 커피 분류 확인"""
    with tempfile.TemporaryDirectory() as tmpdir:
        xls_src = os.path.join(TEST_FOLDER, "간편서비스_승인내역.xls")
        xls_dst = os.path.join(tmpdir, "간편서비스_승인내역.xls")
        os.symlink(xls_src, xls_dst)

        # 3월 27일 바나프레소 27200원 매칭 데이터
        notion_data = {
            "entries": [
                {"date": "2026-03-27", "amount": 27200, "companions": ["양경희", "김보민"]}
            ]
        }

        result = run_pipeline(tmpdir, notion_data=notion_data)
        classified = result["classified_summary"]
        assert classified.get("rule_1", 0) >= 1


def test_run_pipeline_output_json():
    """stdout JSON 형식 확인"""
    with tempfile.TemporaryDirectory() as tmpdir:
        xls_src = os.path.join(TEST_FOLDER, "간편서비스_승인내역.xls")
        os.symlink(xls_src, os.path.join(tmpdir, "간편서비스_승인내역.xls"))

        result = run_pipeline(tmpdir, notion_data=None)
        # JSON serializable
        json_str = json.dumps(result, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert "created_file" in parsed
        assert "manual_items" in parsed
        assert "taxi_receipt_warning" in parsed
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/ykh/Documents/automate && python3 -m pytest tests/expense_report/test_main.py -v
```

Expected: FAIL — `ImportError`

- [ ] **Step 3: Write main.py**

```python
# src/expense_report/main.py
import json
import os
import sys
from collections import Counter

from expense_report.classifier import classify
from expense_report.config import OUTPUT_FILENAME_TEMPLATE, RECEIPT_EXTENSIONS
from expense_report.matcher import NotionEntry, match_transactions
from expense_report.parser import parse_xls
from expense_report.receipt import attach_receipts, collect_receipt_files, validate_taxi_receipts
from expense_report.writer import write_expense_report


def _extract_year_month(folder_path: str) -> tuple[str, str]:
    """폴더명에서 YYYYMM 추출. 예: '202603' → ('26', '03')"""
    basename = os.path.basename(folder_path.rstrip("/"))
    if len(basename) == 6 and basename.isdigit():
        return basename[2:4], basename[4:6]
    raise ValueError(f"폴더명에서 연월을 추출할 수 없습니다: {basename}")


def _find_xls(folder_path: str) -> str:
    for fname in os.listdir(folder_path):
        if fname.endswith(".xls") and not fname.startswith("."):
            return os.path.join(folder_path, fname)
    raise FileNotFoundError(f"간편서비스_승인내역.xls 파일을 찾을 수 없습니다: {folder_path}")


def run_pipeline(
    folder_path: str,
    notion_data: dict | None = None,
) -> dict:
    yy, mm = _extract_year_month(folder_path)

    xls_path = _find_xls(folder_path)
    transactions = parse_xls(xls_path)

    # Notion 매칭
    notion_entries = []
    if notion_data and "entries" in notion_data:
        for entry_dict in notion_data["entries"]:
            notion_entries.append(NotionEntry(
                date=entry_dict["date"],
                amount=entry_dict["amount"],
                companions=entry_dict["companions"],
            ))

    matches = match_transactions(transactions, notion_entries)

    # 분류
    classifications = []
    for idx, txn in enumerate(transactions):
        notion_match = matches.get(idx)
        cls = classify(txn, notion_match=notion_match)
        classifications.append(cls)

    # 엑셀 생성
    output_filename = OUTPUT_FILENAME_TEMPLATE.format(yy=yy, mm=mm)
    output_path = os.path.join(folder_path, output_filename)
    write_expense_report(transactions, classifications, output_path)

    # 영수증 첨부
    receipt_files = collect_receipt_files(folder_path)
    has_taxi = any(c.rule_number in (2, 3, 4) for c in classifications)
    taxi_warning = validate_taxi_receipts(has_taxi, receipt_files)

    if receipt_files:
        import warnings
        warnings.filterwarnings("ignore", category=UserWarning)
        import openpyxl
        wb = openpyxl.load_workbook(output_path)
        attach_receipts(wb["영수증 첨부"], receipt_files)
        wb.save(output_path)

    # 결과 집계
    rule_counter = Counter(c.rule_number for c in classifications)
    manual_items = []
    for idx, (txn, cls) in enumerate(zip(transactions, classifications)):
        if cls.rule_number == 8:
            manual_items.append({
                "row": idx + 1,
                "date": txn.date,
                "time": txn.time,
                "merchant": txn.merchant,
                "amount": txn.amount,
            })

    return {
        "created_file": output_path,
        "total_count": len(transactions),
        "classified_summary": {f"rule_{k}": v for k, v in sorted(rule_counter.items())},
        "manual_items": manual_items,
        "manual_count": len(manual_items),
        "taxi_receipt_warning": taxi_warning,
        "receipt_count": len(receipt_files),
    }


def main():
    import argparse
    ap = argparse.ArgumentParser(description="기명카드 지출결의서 생성")
    ap.add_argument("--folder", required=True, help="대상 폴더 경로")
    ap.add_argument("--notion-data", help="Notion 매칭 데이터 JSON 파일 경로")
    args = ap.parse_args()

    notion_data = None
    if args.notion_data:
        with open(args.notion_data) as f:
            notion_data = json.load(f)

    result = run_pipeline(args.folder, notion_data)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /Users/ykh/Documents/automate && python3 -m pytest tests/expense_report/test_main.py -v
```

Expected: All 3 tests PASS

- [ ] **Step 5: E2E manual verification with real data**

```bash
cd /Users/ykh/Documents/automate && python3 -m expense_report.main --folder "/Users/ykh/Documents/drive/개인경비 지출결의서/2026/202603"
```

Expected: JSON 출력 + xlsx 파일 생성

- [ ] **Step 6: Commit**

```bash
cd /Users/ykh/Documents/automate
git add src/expense_report/main.py tests/expense_report/test_main.py
git commit -m "feat: main CLI entrypoint — full pipeline orchestration"
```

---

### Task 9: Claude Code Skill (SKILL.md)

**Files:**
- Create: `skills/expense-report/SKILL.md`

- [ ] **Step 1: Create skills directory**

```bash
mkdir -p /Users/ykh/Documents/automate/skills/expense-report
```

- [ ] **Step 2: Write SKILL.md**

```markdown
---
name: expense
description: 기명카드 승인내역으로 지출결의서 엑셀 자동 생성. 폴더 경로를 지정하면 xls 파싱 → Notion 팀활동비 매칭 → 규칙 분류 → 엑셀 생성 → 영수증 첨부까지 수행.
---

# 지출결의서 생성 스킬

## 사용법
```
/expense {폴더경로}
```

폴더경로 예시: `/Users/ykh/Documents/drive/개인경비 지출결의서/2026/202603`

## 실행 절차

당신은 지출결의서 생성을 오케스트레이션하는 역할입니다. 아래 단계를 순서대로 수행하세요.

### Step 1: 폴더 검증

Bash 도구로 폴더 내 파일을 확인합니다:
```bash
ls -la "{폴더경로}"
```

- `간편서비스_승인내역.xls` 파일이 없으면 에러 메시지 출력 후 종료
- JPG/PNG 파일 목록을 기록해둡니다

### Step 2: 폴더명에서 연월 추출

폴더명 마지막 6자리가 YYYYMM 형식이어야 합니다 (예: 202603).
해당 연월로 Notion 쿼리 범위를 결정합니다.

### Step 3: Notion 팀활동비 조회

`mcp__notion__notion-query-database-view` 도구로 팀활동비 DB를 조회합니다:
- DB URL: `https://www.notion.so/wefun-platform/263270b243d0800faadbffde6ba5c9b0?v=263270b243d08023b856000c03fa97a0`

조회 결과에서:
1. `사용내역 == "커피"` 필터
2. `사용자`에 양경희 user ID(`user://0f90d063-d2bb-4e09-9b39-f7bdc4883d2b`) 포함 필터
3. `date:사용일:start`가 해당월 범위 필터

### Step 4: 사용자 이름 매핑

`mcp__notion__notion-get-users` 도구로 워크스페이스 사용자 목록을 조회합니다.
`동반자` 필드의 user ID를 실제 이름으로 변환합니다.

### Step 5: Notion 데이터를 JSON으로 저장

필터링된 Notion 데이터를 아래 형식으로 `/tmp/expense_notion_data.json`에 저장합니다:

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

Write 도구로 파일을 생성합니다.

### Step 6: Python 스크립트 실행

```bash
cd /Users/ykh/Documents/automate && python3 -m expense_report.main \
  --folder "{폴더경로}" \
  --notion-data /tmp/expense_notion_data.json
```

스크립트가 JSON을 stdout으로 출력합니다.

### Step 7: 결과 제시

출력된 JSON을 파싱하여 사용자에게 보여줍니다:

**자동 분류 요약:**
| 규칙 | 건수 |
|------|------|
| Rule 1: 팀 커피 (Notion 매칭) | N건 |
| Rule 2: 택시 가승인 취소 | N건 |
| ... | ... |
| Rule 8: 수기 필요 | N건 |

**수기 필요 항목** (있는 경우):
| # | 이용일 | 시간 | 가맹점명 | 금액 |
|---|--------|------|----------|------|
| 1 | ... | ... | ... | ... |

**경고** (있는 경우):
- 택시 영수증 경고 메시지 표시

### Step 8: 요약 캡처 (조건부)

수기 필요 항목이 **0건**이면:
```bash
cd /Users/ykh/Documents/automate && python3 -c "
from expense_report.screenshot import capture_summary_sheet
capture_summary_sheet('{생성된_xlsx_경로}', '{폴더경로}/요약.png')
"
```

수기 필요 항목이 **1건 이상**이면:
> "수기 입력이 필요한 항목이 N건 있습니다. 엑셀에서 노란색 셀을 채운 후 `/expense-capture {경로}`로 요약 캡처를 실행하세요."
```

- [ ] **Step 3: Write expense-capture SKILL.md**

같은 디렉토리에 캡처 전용 스킬도 생성:

```bash
mkdir -p /Users/ykh/Documents/automate/skills/expense-capture
```

```markdown
---
name: expense-capture
description: 지출결의서 수기 입력 완료 후 요약 시트를 PNG로 캡처. /expense 실행 후 수기 항목 편집 완료 시 사용.
---

# 지출결의서 요약 캡처

## 사용법
```
/expense-capture {폴더경로}
```

## 실행 절차

### Step 1: xlsx 파일 찾기

```bash
ls "{폴더경로}"/*법인카드*양경희*.xlsx
```

### Step 2: Rule 7 자동 채움

엑셀을 열어 `2.(기명카드)사용내역` 시트에서:
- 계정과목(N열) = "복리후생비[업무추진비]" 이고
- 경비 청구액(G열)이 빈칸인 행을 찾아
- 경비 청구액 = 이용금액(F열), 사용내역 = "업무추진비", 동반자 = "양경희" 로 채움

Python으로 실행:
```bash
cd /Users/ykh/Documents/automate && python3 -c "
import warnings; warnings.filterwarnings('ignore')
import openpyxl
wb = openpyxl.load_workbook('{xlsx_path}')
ws = wb['2.(기명카드)사용내역']
for row in range(6, ws.max_row + 1):
    account = ws.cell(row, 14).value
    expense = ws.cell(row, 7).value
    if account == '복리후생비[업무추진비]' and expense is None:
        ws.cell(row, 7).value = ws.cell(row, 6).value  # F열 → G열
        ws.cell(row, 10).value = '업무추진비'
        ws.cell(row, 11).value = '양경희'
wb.save('{xlsx_path}')
print('Rule 7 자동 채움 완료')
"
```

### Step 3: 요약 시트 캡처

```bash
cd /Users/ykh/Documents/automate && python3 -c "
from expense_report.screenshot import capture_summary_sheet
result = capture_summary_sheet('{xlsx_path}', '{폴더경로}/요약.png')
print('캡처 성공' if result else '캡처 실패')
"
```

### Step 4: 결과 안내

> "요약.png 저장 완료: {폴더경로}/요약.png"

Read 도구로 요약.png를 읽어 사용자에게 보여줍니다.
```

- [ ] **Step 4: Commit**

```bash
cd /Users/ykh/Documents/automate
git add skills/expense-report/SKILL.md skills/expense-capture/SKILL.md
git commit -m "feat: Claude Code skills — /expense and /expense-capture"
```

---

### Task 10: E2E Test with 3월 데이터

**Files:**
- 기존 3월 데이터로 전체 파이프라인 검증

- [ ] **Step 1: 전체 테스트 스위트 실행**

```bash
cd /Users/ykh/Documents/automate && python3 -m pytest tests/expense_report/ -v
```

Expected: All tests PASS

- [ ] **Step 2: 3월 데이터로 실제 실행**

```bash
cd /Users/ykh/Documents/automate && python3 -m expense_report.main \
  --folder "/Users/ykh/Documents/drive/개인경비 지출결의서/2026/202603"
```

Expected:
- JSON 출력에 total_count, classified_summary, manual_items 포함
- `26년03월_법인카드_하나_양경희.xlsx` 생성됨
- 영수증 이미지 3장 첨부됨

- [ ] **Step 3: 생성된 엑셀 검증**

Python으로 생성된 파일을 읽어 핵심 데이터 확인:

```bash
cd /Users/ykh/Documents/automate && python3 -c "
import warnings; warnings.filterwarnings('ignore')
import openpyxl
wb = openpyxl.load_workbook('/Users/ykh/Documents/drive/개인경비 지출결의서/2026/202603/26년03월_법인카드_하나_양경희.xlsx', data_only=True)

ws1 = wb['1.매출내역(원본)']
print('=== Sheet 1: 매출내역(원본) ===')
for row in [10, 12, 14]:
    date = ws1.cell(row, 1).value
    merchant = ws1.cell(row, 7).value
    amount = ws1.cell(row, 10).value
    print(f'  Row {row}: {date} | {merchant} | {amount}')

ws2 = wb['2.(기명카드)사용내역']
print('\n=== Sheet 2: 기명카드 사용내역 ===')
for row in range(6, 12):
    drafter = ws2.cell(row, 1).value
    usage = ws2.cell(row, 10).value
    account = ws2.cell(row, 14).value
    companion = ws2.cell(row, 11).value
    if drafter:
        print(f'  Row {row}: {drafter} | {usage} | {account} | {companion}')

ws_receipt = wb['영수증 첨부']
print(f'\n=== 영수증 첨부: {len(ws_receipt._images)}장 ===')
"
```

- [ ] **Step 4: 1월 완성본과 비교 검증**

기존 수동 작성된 1월 데이터 패턴과 비교하여 분류 정확도 확인:

```bash
cd /Users/ykh/Documents/automate && python3 -c "
import warnings; warnings.filterwarnings('ignore')
import openpyxl
wb = openpyxl.load_workbook('/Users/ykh/Documents/drive/개인경비 지출결의서/2026/202601/26년01월_법인카드_하나_양경희.xlsx', data_only=True)
ws = wb['2.(기명카드)사용내역']
print('=== 1월 분류 패턴 (참고용) ===')
for row in range(6, 20):
    usage = ws.cell(row, 10).value
    account = ws.cell(row, 14).value
    merchant = ws.cell(row, 16).value
    if usage:
        print(f'  {merchant} → {usage} / {account}')
"
```

- [ ] **Step 5: Commit**

```bash
cd /Users/ykh/Documents/automate
git add -A
git commit -m "feat: expense-report complete — tested with March 2026 data"
```
