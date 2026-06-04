from expense_report.receipt import attach_receipts, collect_receipt_files, validate_taxi_receipts
import openpyxl, os, tempfile


def test_collect_receipt_files(sample_receipts_dir):
    files = collect_receipt_files(sample_receipts_dir)
    assert len(files) >= 3
    assert all(os.path.splitext(f)[1].lower() in {".jpg", ".jpeg", ".png"} for f in files)


def test_collect_sorted_by_name(sample_receipts_dir):
    files = collect_receipt_files(sample_receipts_dir)
    names = [os.path.basename(f) for f in files]
    assert names == sorted(names)


def test_attach_receipts_adds_images(sample_receipts_dir):
    files = collect_receipt_files(sample_receipts_dir)
    with tempfile.TemporaryDirectory() as tmpdir:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "영수증 첨부"
        test_path = os.path.join(tmpdir, "test.xlsx")
        wb.save(test_path)
        wb = openpyxl.load_workbook(test_path)
        attach_receipts(wb["영수증 첨부"], files)
        wb.save(test_path)
        wb2 = openpyxl.load_workbook(test_path)
        assert len(wb2["영수증 첨부"]._images) == len(files)


def test_validate_taxi_receipts_warns():
    assert validate_taxi_receipts(True, []) is not None
    assert "택시비" in validate_taxi_receipts(True, [])


def test_validate_taxi_no_warning_with_receipts():
    assert validate_taxi_receipts(True, ["/some/file.jpg"]) is None


def test_validate_no_taxi_no_warning():
    assert validate_taxi_receipts(False, []) is None


def test_attach_receipts_handles_more_than_26(tmp_path):
    """영수증 27장 이상도 올바른 열(AA, AB..)에 배치되어야 한다 (열 문자 오버플로 회귀)."""
    from PIL import Image as PilImage
    files = []
    for i in range(28):
        p = tmp_path / f"r_{i:02d}.png"
        PilImage.new("RGB", (50, 50), (200, 200, 200)).save(str(p), "PNG")
        files.append(str(p))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "영수증 첨부"
    attach_receipts(ws, files)
    assert len(ws._images) == 28
    # 27번째(i=26) 이후 열이 'AA','AB'로 정상 확장되었는지
    assert "AA" in ws.column_dimensions
    assert "AB" in ws.column_dimensions


def test_attach_receipts_resizes_large_image(tmp_path):
    """큰 이미지(>308px)는 max_width로 축소되고 높이는 비율 유지된다."""
    from PIL import Image as PilImage
    from expense_report.config import RECEIPT_MAX_WIDTH_INCHES
    max_w = int(RECEIPT_MAX_WIDTH_INCHES * 72)  # 308
    p = tmp_path / "big.png"
    PilImage.new("RGB", (400, 600), (255, 255, 255)).save(str(p), "PNG")
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "영수증 첨부"
    attach_receipts(ws, [str(p)])
    img = ws._images[0]
    assert img.width == max_w
    assert img.height == int(600 * (max_w / 400))  # 비율 유지


def test_attach_receipts_keeps_small_image_size(tmp_path):
    from PIL import Image as PilImage
    p = tmp_path / "small.png"
    PilImage.new("RGB", (100, 80), (255, 255, 255)).save(str(p), "PNG")
    wb = openpyxl.Workbook(); ws = wb.active; ws.title = "영수증 첨부"
    attach_receipts(ws, [str(p)])
    img = ws._images[0]
    assert (img.width, img.height) == (100, 80)  # 작은 이미지는 원본 유지
