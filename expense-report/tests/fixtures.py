"""테스트용 합성 픽스처 생성기.

원작성자 로컬 경로에 의존하던 테스트를 신선한 클론·CI에서도 재현 가능하게 만들기 위해,
실제 카드사 승인내역 .xls 와 동일한 셀 레이아웃을 합성으로 생성한다.

레이아웃은 `expense_report.config`의 XLS_* 상수와 `parser.parse_xls_all`의 2행/건 구조를
그대로 따른다. 상수를 import 해서 쓰므로, 컬럼 인덱스가 바뀌어도 픽스처가 함께 따라간다.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import xlwt  # noqa: E402

from expense_report.config import (  # noqa: E402
    XLS_COL_AMOUNT, XLS_COL_APPROVAL_NUMBER, XLS_COL_CARD_NUMBER,
    XLS_COL_DATE, XLS_COL_INSTALLMENT, XLS_COL_MERCHANT,
    XLS_COL_PURCHASE, XLS_COL_PURCHASE_DATE, XLS_COL_TIME,
    XLS_COL_TRANSACTION_TYPE, XLS_COL_TYPE, XLS_COL_VAT_OR_STATUS,
    XLS_DATA_START_ROW,
)

# parser.test_count 는 정상 건수 > 30 을 요구하므로 넉넉히 35건 + 취소 3건을 만든다.
NORMAL_COUNT = 35
CANCELLED_COUNT = 3

# main 의 notion 매칭 테스트(test_run_pipeline_with_notion_data)는 (날짜, 금액)으로
# 매칭하므로, 결정론적으로 rule_1 이 떨어지도록 고정 앵커 거래를 첫 정상 건으로 둔다.
# 이 값을 바꾸면 해당 테스트의 notion_data 도 함께 맞춰야 한다.
ANCHOR_DATE = "2026.03.27"
ANCHOR_AMOUNT = 27200
ANCHOR_MERCHANT = "바나프레소"

# 점심/저녁/카페/택시 등 분류기 규칙이 골고루 타도록 가맹점을 순환시킨다.
_MERCHANTS = ["바나프레소", "스타벅스", "김밥천국", "카카오T일반택시(법인)",
              "네이버페이", "본죽", "투썸플레이스", "맘스터치"]
_TIMES = ["12:30", "18:10", "13:05", "21:40", "09:15", "12:55", "19:30", "11:20"]


def _max_col() -> int:
    return max(
        XLS_COL_DATE, XLS_COL_TIME, XLS_COL_MERCHANT, XLS_COL_CARD_NUMBER,
        XLS_COL_TYPE, XLS_COL_AMOUNT, XLS_COL_TRANSACTION_TYPE,
        XLS_COL_APPROVAL_NUMBER, XLS_COL_PURCHASE, XLS_COL_PURCHASE_DATE,
        XLS_COL_INSTALLMENT, XLS_COL_VAT_OR_STATUS,
    )


def build_sample_xls(path: str) -> str:
    """parser가 기대하는 레이아웃의 합성 승인내역 .xls 를 생성하고 경로를 반환한다."""
    wb = xlwt.Workbook(encoding="utf-8")
    ws = wb.add_sheet("승인내역")
    max_col = _max_col()

    # --- 메타 영역 (parse_xls_meta 가 읽는 셀들; 값 자체는 데모용) ---
    ws.write(2, 4, "2026.03.01 ~ 2026.03.31")
    ws.write(3, 5, f"{NORMAL_COUNT}건")
    ws.write(3, 13, "778,874원")
    ws.write(4, 5, "0건")
    ws.write(4, 13, "0원")
    ws.write(5, 5, f"{CANCELLED_COUNT}건")
    ws.write(5, 13, "0원")

    # 헤더 행이 데이터 시작 직전까지 차지하도록 라벨을 채워 row 인덱스를 맞춘다.
    for col in range(max_col + 1):
        ws.write(XLS_DATA_START_ROW - 1, col, f"h{col}")

    def write_txn(top_row: int, idx: int, status: str) -> None:
        # idx 0 = 고정 앵커 거래 (notion 매칭 테스트가 의존)
        if idx == 0:
            date, amount, merchant = ANCHOR_DATE, ANCHOR_AMOUNT, ANCHOR_MERCHANT
        else:
            day = 1 + (idx % 28)
            date = f"2026.03.{day:02d}"
            amount = 9000 + idx * 100
            merchant = _MERCHANTS[idx % len(_MERCHANTS)]
        ws.write(top_row, XLS_COL_DATE, date)
        ws.write(top_row, XLS_COL_TIME, _TIMES[idx % len(_TIMES)])
        ws.write(top_row, XLS_COL_MERCHANT, merchant)
        ws.write(top_row, XLS_COL_CARD_NUMBER, "4201-****-****-7592")
        ws.write(top_row, XLS_COL_TYPE, "국내일반")
        ws.write(top_row, XLS_COL_AMOUNT, f"{amount:,}")
        ws.write(top_row, XLS_COL_TRANSACTION_TYPE, "국내 일시불")
        ws.write(top_row, XLS_COL_APPROVAL_NUMBER, f"{10000000 + idx}")
        ws.write(top_row, XLS_COL_PURCHASE, "매입")
        ws.write(top_row, XLS_COL_PURCHASE_DATE, date)
        ws.write(top_row, XLS_COL_INSTALLMENT, "-")
        ws.write(top_row, XLS_COL_VAT_OR_STATUS, "1000")
        # 둘째 행: 상태 ("정상"/"취소")
        ws.write(top_row + 1, XLS_COL_VAT_OR_STATUS, status)

    row = XLS_DATA_START_ROW
    idx = 0
    for _ in range(NORMAL_COUNT):
        write_txn(row, idx, "정상")
        row += 2
        idx += 1
    for _ in range(CANCELLED_COUNT):
        write_txn(row, idx, "취소")
        row += 2
        idx += 1

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    wb.save(path)
    return path


def build_sample_template(path: str) -> str:
    """writer/main 이 기대하는 양식 .xlsx 를 합성 생성한다.

    실제 양식의 스타일·병합까지 똑같이 재현할 필요는 없고(테스트는 셀 '값'을 검증),
    writer 가 이름으로 접근하는 세 시트만 있으면 된다:
      - "1.매출내역(원본)"   : Sheet1 (메타 + 거래 원본, row 10~ 2행/건)
      - "2.(기명카드)사용내역" : Sheet2 (분류 결과, row 6~ 1행/건)
      - "영수증 첨부"          : run_pipeline 의 영수증 이미지 부착 대상
    """
    import openpyxl

    wb = openpyxl.Workbook()
    # 기본 시트를 첫 시트로 재사용
    s1 = wb.active
    s1.title = "1.매출내역(원본)"
    wb.create_sheet("2.(기명카드)사용내역")
    wb.create_sheet("영수증 첨부")

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    wb.save(path)
    return path


def build_sample_receipts(folder: str, count: int = 3) -> list[str]:
    """folder 안에 합성 영수증 이미지를 생성하고 정렬된 경로 목록을 반환한다.

    이름순 정렬 검증을 위해 zero-padded 파일명을 쓰고, .jpg/.png 를 섞어
    확장자 필터(RECEIPT_EXTENSIONS)도 함께 검증되게 한다.
    """
    from PIL import Image as PilImage

    os.makedirs(folder, exist_ok=True)
    paths = []
    for i in range(count):
        ext = ".jpg" if i % 2 == 0 else ".png"
        name = f"receipt_{i:02d}{ext}"
        path = os.path.join(folder, name)
        # 가로>4.29인치(=309px) 인 이미지를 만들어 attach_receipts 리사이즈 경로도 탄다.
        img = PilImage.new("RGB", (400, 600), (240, 240, 240))
        img.save(path, "JPEG" if ext == ".jpg" else "PNG")
        paths.append(path)
    return sorted(paths)
