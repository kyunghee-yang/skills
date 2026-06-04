import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from expense_report.matcher import NotionEntry, match_transactions
from expense_report.parser import Transaction


def _make_txn(date, amount, merchant="바나프레소"):
    return Transaction(
        date=date,
        time="13:00",
        merchant=merchant,
        card_number="4201-****-****-7592",
        usage_type="국내일반",
        amount=amount,
        transaction_type="국내 일시불",
        approval_number="12345678",
        purchase_status="매입",
        purchase_date="2026-03-28",
        installment="-",
        vat="0",
        status="정상",
    )


def _make_notion(date, amount, companions):
    return NotionEntry(date=date, amount=amount, companions=companions)


def test_exact_match():
    txn = _make_txn("2026.03.27", 27200)
    notion = _make_notion("2026-03-27", 27200, ["Alice"])
    result = match_transactions([txn], [notion])
    assert 0 in result
    assert result[0] == notion


def test_no_match_different_amount():
    txn = _make_txn("2026.03.27", 27200)
    notion = _make_notion("2026-03-27", 15000, ["Alice"])
    result = match_transactions([txn], [notion])
    assert result == {}


def test_no_match_different_date():
    txn = _make_txn("2026.03.27", 27200)
    notion = _make_notion("2026-03-28", 27200, ["Alice"])
    result = match_transactions([txn], [notion])
    assert result == {}


def test_multiple_transactions_partial_match():
    txns = [
        _make_txn("2026.03.27", 27200),
        _make_txn("2026.03.28", 15000),
        _make_txn("2026.03.29", 99999),
    ]
    notions = [
        _make_notion("2026-03-27", 27200, ["Alice"]),
        _make_notion("2026-03-28", 15000, ["Bob"]),
    ]
    result = match_transactions(txns, notions)
    assert len(result) == 2
    assert 0 in result
    assert 1 in result
    assert 2 not in result
    assert result[0].companions == ["Alice"]
    assert result[1].companions == ["Bob"]


# parse_notion_json 견고성/정상 동작
from expense_report.matcher import parse_notion_json


def test_parse_notion_json_basic():
    rec = {"사용내역": "커피", "date:사용일:start": "2026-03-27", "금액": 10000,
           "동반자": '["u1", "u2"]'}
    out = parse_notion_json([rec], {"u1": "Alice", "u2": "Bob"})
    assert len(out) == 1
    assert out[0].companions == ["Alice", "Bob"]
    assert out[0].amount == 10000


def test_parse_notion_json_skips_non_coffee():
    rec = {"사용내역": "택시", "date:사용일:start": "2026-03-27", "금액": 10000}
    assert parse_notion_json([rec], {}) == []


def test_parse_notion_json_skips_missing_date_or_amount():
    no_date = {"사용내역": "커피", "금액": 10000}
    no_amount = {"사용내역": "커피", "date:사용일:start": "2026-03-27"}
    assert parse_notion_json([no_date, no_amount], {}) == []


def test_parse_notion_json_handles_null_companion():
    # 회귀: 동반자=None 이어도 크래시하지 않고 companions=[] 로 처리
    rec = {"사용내역": "커피", "date:사용일:start": "2026-03-27", "금액": 10000, "동반자": None}
    out = parse_notion_json([rec], {})
    assert len(out) == 1 and out[0].companions == []


def test_parse_notion_json_handles_empty_string_companion():
    rec = {"사용내역": "커피", "date:사용일:start": "2026-03-27", "금액": 10000, "동반자": ""}
    out = parse_notion_json([rec], {})
    assert len(out) == 1 and out[0].companions == []


def test_parse_notion_json_handles_list_companion():
    rec = {"사용내역": "커피", "date:사용일:start": "2026-03-27", "금액": 10000,
           "동반자": ["u1"]}
    out = parse_notion_json([rec], {"u1": "Alice"})
    assert out[0].companions == ["Alice"]


# 금액 정규화 견고성 (Notion 금액이 정수/실수/문자열/쉼표/비정상)
from expense_report.matcher import _to_amount_int


def test_to_amount_int_variants():
    assert _to_amount_int(27200) == 27200
    assert _to_amount_int(27200.0) == 27200
    assert _to_amount_int("27200") == 27200
    assert _to_amount_int("27,200") == 27200
    assert _to_amount_int("27,200원") == 27200
    assert _to_amount_int("없음") is None
    assert _to_amount_int(None) is None
    assert _to_amount_int(True) is None  # bool 은 금액 아님


def test_match_with_comma_string_amount():
    txn = _make_txn("2026.03.27", 27200)
    notion = _make_notion("2026-03-27", "27,200", ["Alice"])  # 쉼표 문자열
    result = match_transactions([txn], [notion])
    assert 0 in result and result[0].companions == ["Alice"]


def test_match_skips_unparseable_amount():
    txn = _make_txn("2026.03.27", 27200)
    notion = _make_notion("2026-03-27", "N/A", ["Alice"])  # 파싱 불가 → 크래시 없이 미매칭
    assert match_transactions([txn], [notion]) == {}


# Notion 날짜가 datetime 형식일 때도 일자 단위로 매칭 (조사 확인 버그)
def test_match_with_datetime_notion_date():
    txn = _make_txn("2026.03.27", 27200)
    for d in ["2026-03-27", "2026-03-27T02:12:33.231Z", "2026-03-27T00:00:00+09:00"]:
        result = match_transactions([txn], [_make_notion(d, 27200, ["A"])])
        assert 0 in result, f"{d} 매칭 실패"


def test_normalize_date_strips_time():
    from expense_report.matcher import _normalize_date
    assert _normalize_date("2026.03.27") == "2026-03-27"
    assert _normalize_date("2026-03-27") == "2026-03-27"
    assert _normalize_date("2026-03-27T02:12:33.231Z") == "2026-03-27"
