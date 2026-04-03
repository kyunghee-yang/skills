from dataclasses import dataclass
import re
import xlrd
from expense_report.config import (
    XLS_COL_AMOUNT, XLS_COL_APPROVAL_NUMBER, XLS_COL_CARD_NUMBER,
    XLS_COL_DATE, XLS_COL_INSTALLMENT, XLS_COL_MERCHANT,
    XLS_COL_PURCHASE, XLS_COL_PURCHASE_DATE, XLS_COL_TIME,
    XLS_COL_TRANSACTION_TYPE, XLS_COL_TYPE, XLS_COL_VAT_OR_STATUS,
    XLS_DATA_START_ROW,
)

_DATE_PATTERN = re.compile(r"^\d{4}\.\d{2}\.\d{2}$")


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


@dataclass
class XlsMeta:
    period: str        # "2026-03-01 ~ 2026-03-31"
    domestic_count: str   # "39건"
    domestic_total: str   # "778,874원"
    overseas_count: str
    overseas_total: str
    cancel_count: str
    reject_count: str


def parse_xls_meta(file_path: str) -> XlsMeta:
    workbook = xlrd.open_workbook(file_path)
    sheet = workbook.sheet_by_index(0)
    return XlsMeta(
        period=_cell_str(sheet, 2, 4),
        domestic_count=_cell_str(sheet, 3, 5),
        domestic_total=_cell_str(sheet, 3, 13),
        overseas_count=_cell_str(sheet, 4, 5),
        overseas_total=_cell_str(sheet, 4, 13),
        cancel_count=_cell_str(sheet, 5, 5),
        reject_count=_cell_str(sheet, 5, 13),
    )


def parse_xls_all(file_path: str) -> list[Transaction]:
    """취소 건 포함 전체 트랜잭션 파싱 (Sheet1 원본용)."""
    workbook = xlrd.open_workbook(file_path)
    sheet = workbook.sheet_by_index(0)
    transactions = []
    row = XLS_DATA_START_ROW
    while row + 1 < sheet.nrows:
        date_val = _cell_str(sheet, row, XLS_COL_DATE)
        if not date_val or not _DATE_PATTERN.match(date_val):
            row += 2
            continue
        status = _cell_str(sheet, row + 1, XLS_COL_VAT_OR_STATUS)
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


def parse_xls(file_path: str) -> list[Transaction]:
    """취소 건 제외한 정상 트랜잭션 파싱 (분류용)."""
    return [txn for txn in parse_xls_all(file_path) if txn.status != "취소"]
