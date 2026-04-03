import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from expense_report.parser import Transaction, parse_xls

XLS_PATH = "/Users/ykh/Documents/drive/개인경비 지출결의서/2026/202603/간편서비스_승인내역.xls"


def test_parse_xls_returns_transactions():
    transactions = parse_xls(XLS_PATH)
    assert len(transactions) > 0
    assert all(isinstance(txn, Transaction) for txn in transactions)


def test_transaction_fields_populated():
    transactions = parse_xls(XLS_PATH)
    first = transactions[0]
    assert first.date != ""
    assert first.time != ""
    assert first.merchant != ""
    assert first.amount > 0


def test_cancelled_transactions_excluded():
    transactions = parse_xls(XLS_PATH)
    assert all(txn.status != "취소" for txn in transactions)


def test_amount_parsed_as_integer():
    transactions = parse_xls(XLS_PATH)
    assert all(isinstance(txn.amount, int) for txn in transactions)


def test_date_format():
    transactions = parse_xls(XLS_PATH)
    date_pattern = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
    assert all(date_pattern.match(txn.date) for txn in transactions)


def test_count():
    transactions = parse_xls(XLS_PATH)
    assert len(transactions) > 30
