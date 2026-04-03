import os
from typing import List, Optional
from openpyxl.drawing.image import Image as XlImage
from PIL import Image as PilImage
from expense_report.config import RECEIPT_EXTENSIONS, RECEIPT_MAX_WIDTH_INCHES, RECEIPT_ROW_GAP


def collect_receipt_files(folder_path: str) -> List[str]:
    files = []
    for fname in sorted(os.listdir(folder_path)):
        if os.path.splitext(fname)[1].lower() in RECEIPT_EXTENSIONS:
            files.append(os.path.join(folder_path, fname))
    return files


def validate_taxi_receipts(has_taxi: bool, receipt_files: List[str]) -> Optional[str]:
    if not has_taxi:
        return None
    if not receipt_files:
        return "택시비 항목이 있지만 영수증 이미지가 없습니다. 영수증을 폴더에 추가한 후 다시 실행하세요."
    return None


def attach_receipts(ws, file_paths: list[str]) -> None:
    """영수증 이미지를 가로로 나란히 배치. 최대 너비 4.29인치/장."""
    max_width_px = int(RECEIPT_MAX_WIDTH_INCHES * 72)
    col_width_px = max_width_px + 10  # 이미지 간 약간의 간격
    default_col_char_width = 8.43     # Excel 기본 열 너비 (문자 수)
    px_per_char = 7                   # 대략적 변환

    for i, fpath in enumerate(file_paths):
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

        # 가로 배치: 각 이미지를 다른 열에 배치
        col_letter = chr(ord("A") + i)
        ws.column_dimensions[col_letter].width = col_width_px / px_per_char
        ws.add_image(xl_img, f"{col_letter}1")
