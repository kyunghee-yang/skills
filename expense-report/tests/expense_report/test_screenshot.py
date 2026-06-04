from expense_report.screenshot import find_xlsx_in_folder


def test_find_xlsx_matches_drafter_name(tmp_path):
    target = tmp_path / "26년03월_법인카드_하나_홍길동.xlsx"
    target.write_text("x")
    (tmp_path / "무관한파일.xlsx").write_text("y")
    found = find_xlsx_in_folder(str(tmp_path), drafter_name="홍길동")
    assert found is not None and found.endswith("홍길동.xlsx")


def test_find_xlsx_returns_none_when_no_match(tmp_path):
    (tmp_path / "26년03월_법인카드_하나_김철수.xlsx").write_text("x")
    assert find_xlsx_in_folder(str(tmp_path), drafter_name="홍길동") is None


def test_find_xlsx_uses_config_default(tmp_path):
    # 인자 미지정 시 config.DRAFTER_NAME(기본 양경희) 패턴을 사용
    (tmp_path / "26년03월_법인카드_하나_양경희.xlsx").write_text("x")
    assert find_xlsx_in_folder(str(tmp_path)) is not None


def test_find_xlsx_reads_config_at_call_time(tmp_path, monkeypatch):
    # 회귀: import 시 값 복사가 아니라 호출 시점 config.DRAFTER_NAME 을 읽어야 한다
    from expense_report import config
    monkeypatch.setattr(config, "DRAFTER_NAME", "정칼타임")
    (tmp_path / "26년03월_법인카드_하나_정칼타임.xlsx").write_text("x")
    assert find_xlsx_in_folder(str(tmp_path)) is not None
