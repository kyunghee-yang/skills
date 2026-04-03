import json
import os
import tempfile

from expense_report.main import run_pipeline

TEST_FOLDER = "/Users/ykh/Documents/drive/개인경비 지출결의서/2026/202603"


def test_run_pipeline_creates_xlsx():
    with tempfile.TemporaryDirectory() as tmpdir:
        sub = os.path.join(tmpdir, "202603")
        os.makedirs(sub)
        xls_src = os.path.join(TEST_FOLDER, "간편서비스_승인내역.xls")
        os.symlink(xls_src, os.path.join(sub, "간편서비스_승인내역.xls"))
        result = run_pipeline(sub, notion_data=None)
        assert os.path.exists(result["created_file"])
        assert isinstance(result["manual_items"], list)
        assert result["total_count"] > 0


def test_run_pipeline_with_notion_data():
    with tempfile.TemporaryDirectory() as tmpdir:
        sub = os.path.join(tmpdir, "202603")
        os.makedirs(sub)
        os.symlink(os.path.join(TEST_FOLDER, "간편서비스_승인내역.xls"), os.path.join(sub, "간편서비스_승인내역.xls"))
        notion_data = {"entries": [{"date": "2026-03-27", "amount": 27200, "companions": ["양경희", "김보민"]}]}
        result = run_pipeline(sub, notion_data=notion_data)
        assert result["classified_summary"].get("rule_1", 0) >= 1


def test_run_pipeline_output_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        sub = os.path.join(tmpdir, "202603")
        os.makedirs(sub)
        os.symlink(os.path.join(TEST_FOLDER, "간편서비스_승인내역.xls"), os.path.join(sub, "간편서비스_승인내역.xls"))
        result = run_pipeline(sub, notion_data=None)
        json_str = json.dumps(result, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert "created_file" in parsed
        assert "manual_items" in parsed
        assert "taxi_receipt_warning" in parsed
