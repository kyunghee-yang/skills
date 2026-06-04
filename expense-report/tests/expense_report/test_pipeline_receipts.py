"""run_pipeline 영수증 첨부 통합 커버리지(폴더에 이미지가 있을 때)."""
import os
import sys

import openpyxl
from PIL import Image as PilImage

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from expense_report.main import run_pipeline
from tests.fixtures import build_sample_xls  # type: ignore


def test_run_pipeline_attaches_receipts(tmp_path, sample_template):
    sub = tmp_path / "202603"
    sub.mkdir()
    build_sample_xls(str(sub / "간편서비스_승인내역.xls"))
    # 영수증 이미지 2장을 폴더에 넣는다
    for i in range(2):
        PilImage.new("RGB", (120, 90), (230, 230, 230)).save(str(sub / f"r{i}.png"), "PNG")

    result = run_pipeline(str(sub), notion_data=None, template_path=sample_template)
    assert result["receipt_count"] == 2

    wb = openpyxl.load_workbook(result["created_file"])
    assert len(wb["영수증 첨부"]._images) == 2  # 결의서에 부착됨
