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
