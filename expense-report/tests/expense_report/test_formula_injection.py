"""writer 수식 인젝션 방어 테스트.

악성 가맹점명(=HYPERLINK 등)이 결의서 셀에서 수식으로 저장되지 않아야 한다.
"""
import os
import tempfile

import openpyxl

from expense_report.classifier import Classification
from expense_report.parser import Transaction
from expense_report.writer import write_expense_report, _safe_cell


def test_safe_cell_prefixes_formula_triggers():
    assert _safe_cell("=1+1") == "'=1+1"
    assert _safe_cell("+1") == "'+1"
    assert _safe_cell("-1") == "'-1"
    assert _safe_cell("@x") == "'@x"
    # 정상 값/숫자는 불변
    assert _safe_cell("바나프레소") == "바나프레소"
    assert _safe_cell(10300) == 10300
    assert _safe_cell("") == ""


def _txn(merchant):
    return Transaction(date="2026.03.27", time="13:00", merchant=merchant,
        card_number="x", usage_type="국내일반", amount=10000,
        transaction_type="국내 일시불", approval_number="1", purchase_status="매입",
        purchase_date="2026-03-28", installment="-", vat="0", status="정상")


def test_malicious_merchant_not_stored_as_formula(sample_template):
    txns = [_txn('=HYPERLINK("http://evil","click")')]
    cls = [Classification(usage="점심", expense_amount=10000, account="복리후생비[식비]",
                          companion="양경희", rule_number=6)]
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "o.xlsx")
        write_expense_report(txns, cls, out, template_path=sample_template)
        wb = openpyxl.load_workbook(out)
        cell = wb["1.매출내역(원본)"].cell(10, 7)  # SHEET1_COL_MERCHANT
        assert cell.data_type != "f"          # 수식으로 저장되지 않음
        assert str(cell.value).startswith("'=")  # 텍스트로 살균됨
