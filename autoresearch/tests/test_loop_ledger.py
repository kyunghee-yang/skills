from types import SimpleNamespace

import loop_ledger as L


def _empty():
    return {"branch": "b", "started_at": "t", "iteration": 0,
            "iterations": [], "discarded_hypotheses": []}


def test_start_increments_and_appends():
    data = _empty()
    L.cmd_start(data, SimpleNamespace(target="T", hypothesis="H", research=["r1"]))
    assert data["iteration"] == 1
    assert len(data["iterations"]) == 1
    assert data["iterations"][0]["decision"] == "in_progress"
    assert data["iterations"][0]["target"] == "T"


def test_record_adopted_sets_fields():
    data = _empty()
    L.cmd_start(data, SimpleNamespace(target="T", hypothesis="H", research=None))
    rc = L.cmd_record(data, SimpleNamespace(
        decision="adopted", ab='{"winner":"B"}', verify="ok", commit="abc", reason=None))
    assert rc == 0
    entry = data["iterations"][-1]
    assert entry["decision"] == "adopted"
    assert entry["ab"] == {"winner": "B"}
    assert entry["commit"] == "abc"


def test_record_discarded_logs_hypothesis():
    data = _empty()
    L.cmd_start(data, SimpleNamespace(target="T", hypothesis="가설X", research=None))
    L.cmd_record(data, SimpleNamespace(
        decision="discarded", ab=None, verify=None, commit=None, reason="느림"))
    assert any("가설X" in h and "느림" in h for h in data["discarded_hypotheses"])


def test_record_without_start_fails():
    data = _empty()
    rc = L.cmd_record(data, SimpleNamespace(
        decision="adopted", ab=None, verify=None, commit=None, reason=None))
    assert rc == 1


def test_record_invalid_ab_falls_back_to_note():
    data = _empty()
    L.cmd_start(data, SimpleNamespace(target="T", hypothesis="H", research=None))
    L.cmd_record(data, SimpleNamespace(
        decision="adopted", ab="not-json", verify=None, commit=None, reason=None))
    assert data["iterations"][-1]["ab"] == {"note": "not-json"}


def test_discard_appends():
    data = _empty()
    L.cmd_discard(data, SimpleNamespace(hypothesis="H2", reason="중복"))
    assert any("H2" in h for h in data["discarded_hypotheses"])


def test_load_returns_default_when_missing(tmp_path):
    data = L.load(tmp_path / "nope.json")
    assert data["iteration"] == 0
    assert data["iterations"] == []


def test_save_then_load_roundtrip(tmp_path):
    p = tmp_path / "ledger.json"
    data = _empty()
    L.cmd_start(data, SimpleNamespace(target="T", hypothesis="H", research=None))
    L.save(p, data)
    loaded = L.load(p)
    assert loaded["iteration"] == 1
    assert loaded["iterations"][0]["target"] == "T"
