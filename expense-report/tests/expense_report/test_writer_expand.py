"""writer _ensure_pairs 행 확장(14쌍 초과) 직접 커버리지."""
import os
import tempfile

import openpyxl

from expense_report.classifier import Classification
from expense_report.parser import Transaction
from expense_report.writer import write_expense_report
from expense_report.config import SHEET1_DATA_START_ROW, SHEET1_COL_MERCHANT


def _txn(i):
    return Transaction(date="2026.03.%02d" % (1 + i % 28), time="13:00",
        merchant=f"가맹점{i}", card_number="x", usage_type="국내일반", amount=1000 + i,
        transaction_type="국내 일시불", approval_number=str(i), purchase_status="매입",
        purchase_date="2026-03-28", installment="-", vat="0", status="정상")


def test_expands_beyond_14_pairs(sample_template):
    n = 20  # > _TEMPLATE_PAIR_COUNT(14)
    txns = [_txn(i) for i in range(n)]
    cls = [Classification(usage="점심", expense_amount=1000, account="복리후생비[식비]",
                          companion="양경희", rule_number=6) for _ in range(n)]
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "o.xlsx")
        write_expense_report(txns, cls, out, all_transactions=txns, template_path=sample_template)
        ws = openpyxl.load_workbook(out)["1.매출내역(원본)"]
        # 각 거래가 2행 간격으로 모두 기록됐는지(마지막 거래 포함)
        for i in range(n):
            row = SHEET1_DATA_START_ROW + i * 2
            assert ws.cell(row, SHEET1_COL_MERCHANT).value == f"가맹점{i}"
