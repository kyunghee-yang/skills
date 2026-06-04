import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from expense_report.parser import Transaction, parse_xls


def test_parse_xls_returns_transactions(sample_xls):
    transactions = parse_xls(sample_xls)
    assert len(transactions) > 0
    assert all(isinstance(txn, Transaction) for txn in transactions)


def test_transaction_fields_populated(sample_xls):
    transactions = parse_xls(sample_xls)
    first = transactions[0]
    assert first.date != ""
    assert first.time != ""
    assert first.merchant != ""
    assert first.amount > 0


def test_cancelled_transactions_excluded(sample_xls):
    transactions = parse_xls(sample_xls)
    assert all(txn.status != "취소" for txn in transactions)


def test_amount_parsed_as_integer(sample_xls):
    transactions = parse_xls(sample_xls)
    assert all(isinstance(txn.amount, int) for txn in transactions)


def test_date_format(sample_xls):
    transactions = parse_xls(sample_xls)
    date_pattern = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")
    assert all(date_pattern.match(txn.date) for txn in transactions)


def test_count(sample_xls):
    transactions = parse_xls(sample_xls)
    assert len(transactions) > 30
