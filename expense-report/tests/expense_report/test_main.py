import json
import os

from expense_report.main import run_pipeline
from fixtures import ANCHOR_AMOUNT, ANCHOR_DATE, build_sample_xls


def _make_folder(tmp_path):
    """'202603' 폴더에 합성 승인내역 .xls 를 넣고 폴더 경로를 반환한다."""
    sub = tmp_path / "202603"
    sub.mkdir()
    build_sample_xls(str(sub / "간편서비스_승인내역.xls"))
    return str(sub)


def test_run_pipeline_creates_xlsx(tmp_path, sample_template):
    sub = _make_folder(tmp_path)
    result = run_pipeline(sub, notion_data=None, template_path=sample_template)
    assert os.path.exists(result["created_file"])
    assert isinstance(result["manual_items"], list)
    assert result["total_count"] > 0


def test_run_pipeline_with_notion_data(tmp_path, sample_template):
    sub = _make_folder(tmp_path)
    # 앵커 거래(ANCHOR_DATE/ANCHOR_AMOUNT)와 매칭되어 rule_1(팀 커피)이 떨어져야 한다.
    notion_data = {"entries": [{
        "date": ANCHOR_DATE.replace(".", "-"),
        "amount": ANCHOR_AMOUNT,
        "companions": ["양경희", "김보민"],
    }]}
    result = run_pipeline(sub, notion_data=notion_data, template_path=sample_template)
    assert result["classified_summary"].get("rule_1", 0) >= 1


def test_run_pipeline_output_json(tmp_path, sample_template):
    sub = _make_folder(tmp_path)
    result = run_pipeline(sub, notion_data=None, template_path=sample_template)
    json_str = json.dumps(result, ensure_ascii=False)
    parsed = json.loads(json_str)
    assert "created_file" in parsed
    assert "manual_items" in parsed
    assert "taxi_receipt_warning" in parsed
