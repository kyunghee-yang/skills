"""config._load_user_config 의 user-config 오버라이드 테스트.

config 는 모듈 로드 시 ~/.config/expense-report/config.json 을 읽어 모듈 전역을 바꾼다.
공유 모듈 전역을 오염시키지 않도록, HOME 을 격리한 서브프로세스에서 import 해 결과를 본다.
"""
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")


def _run_with_config(tmp_home: Path, cfg: dict) -> dict:
    cfg_dir = tmp_home / ".config" / "expense-report"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    (cfg_dir / "config.json").write_text(json.dumps(cfg), encoding="utf-8")

    code = textwrap.dedent(
        """
        import json, sys
        sys.path.insert(0, sys.argv[1])
        from expense_report import config as c
        print(json.dumps({
            "drafter": c.DRAFTER_NAME,
            "dept": c.DEPARTMENT,
            "template": c.TEMPLATE_PATH,
            "taxi": c.TAXI_HOME_ROUTE,
            "filename": c.OUTPUT_FILENAME_TEMPLATE,
        }, ensure_ascii=False))
        """
    )
    env = dict(os.environ, HOME=str(tmp_home))
    out = subprocess.run(
        [sys.executable, "-c", code, os.path.abspath(SRC)],
        capture_output=True, text=True, env=env, check=True,
    ).stdout.strip()
    return json.loads(out)


def test_template_path_override_expands_user(tmp_path):
    res = _run_with_config(tmp_path, {"template_path": "~/forms/my.xlsx"})
    assert res["template"] == str(tmp_path / "forms/my.xlsx")  # expanduser 적용


def test_drafter_and_filename_template(tmp_path):
    res = _run_with_config(tmp_path, {"drafter_name": "홍길동"})
    assert res["drafter"] == "홍길동"
    assert res["filename"].endswith("홍길동.xlsx")


def test_taxi_destination_formatting(tmp_path):
    res = _run_with_config(tmp_path, {"taxi_destination": "부천"})
    assert "부천" in res["taxi"]


def test_defaults_when_unrelated_config(tmp_path):
    # 무관한 키만 있는 config → 기본값 유지(크래시 없음)
    out = _run_with_config(tmp_path, {"unrelated": 1})
    assert out["drafter"]                       # 기본 기안자명 존재
    assert out["filename"].endswith(".xlsx")    # 기본 파일명 템플릿 유효
