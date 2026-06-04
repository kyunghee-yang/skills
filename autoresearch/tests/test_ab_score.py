import pytest

import ab_score


def _cand(name, **metrics):
    """metrics: key -> (value, weight, higher_is_better[, stddev])"""
    m = {}
    for k, spec in metrics.items():
        value, weight, hib = spec[0], spec[1], spec[2]
        entry = {"value": value, "weight": weight, "higher_is_better": hib}
        if len(spec) > 3:
            entry["stddev"] = spec[3]
        m[k] = entry
    return {"name": name, "metrics": m}


def test_normalize_pair_higher_is_better():
    na, nb = ab_score.normalize_pair(10, 20, True)
    assert nb > na
    assert (na, nb) == (0.0, 1.0)


def test_normalize_pair_lower_is_better():
    # 값이 작을수록 좋음 → 작은 값이 1.0
    na, nb = ab_score.normalize_pair(10, 20, False)
    assert (na, nb) == (1.0, 0.0)


def test_normalize_pair_equal_is_neutral():
    assert ab_score.normalize_pair(5, 5, True) == (0.5, 0.5)


def test_score_b_wins_on_all_metrics():
    a = _cand("A", acc=(0.8, 2.0, True), t=(1500, 1.0, False))
    b = _cand("B", acc=(0.95, 2.0, True), t=(1000, 1.0, False))
    res = ab_score.score(a, b)
    assert res["score_b"] > res["score_a"]
    assert res["any_real_edge"] is True


def test_decide_winner_b():
    a = _cand("A", acc=(0.8, 2.0, True))
    b = _cand("B", acc=(0.95, 2.0, True))
    res = ab_score.score(a, b)
    assert ab_score.decide(res, margin=0.03) == "B"


def test_decide_tie_when_identical():
    a = _cand("A", acc=(0.9, 1.0, True))
    res = ab_score.score(a, dict(a))
    assert ab_score.decide(res, margin=0.03) == "TIE"


def test_decide_tie_when_diff_within_noise():
    # 차이(0.01)가 stddev(0.05) 안 → 노이즈로 동률 처리
    a = _cand("A", acc=(0.90, 1.0, True, 0.05))
    b = _cand("B", acc=(0.91, 1.0, True, 0.05))
    res = ab_score.score(a, b)
    assert res["any_real_edge"] is False
    assert ab_score.decide(res, margin=0.0) == "TIE"


def test_score_requires_common_metric():
    a = _cand("A", x=(1, 1.0, True))
    b = _cand("B", y=(1, 1.0, True))
    with pytest.raises(SystemExit):  # 공통 지표 없으면 SystemExit
        ab_score.score(a, b)


def test_all_zero_weights_is_tie_not_crash():
    a = _cand("A", m=(1, 0.0, True))
    b = _cand("B", m=(2, 0.0, True))
    res = ab_score.score(a, b)  # 과거: ZeroDivisionError
    assert res["score_a"] == 0.5 and res["score_b"] == 0.5
    assert ab_score.decide(res, margin=0.03) == "TIE"


def test_cmd_compare_exit_codes(tmp_path):
    import json
    from types import SimpleNamespace
    a = tmp_path / "a.json"; b = tmp_path / "b.json"
    a.write_text(json.dumps(_cand("A", acc=(0.8, 2.0, True))))
    b.write_text(json.dumps(_cand("B", acc=(0.95, 2.0, True))))
    # B 우세 → 0(채택)
    assert ab_score.cmd_compare(SimpleNamespace(a=str(a), b=str(b), margin=0.03)) == 0
    # A 우세 → 1(유지): a/b 교체
    assert ab_score.cmd_compare(SimpleNamespace(a=str(b), b=str(a), margin=0.03)) == 1
    # 동률 → 1(유지)
    assert ab_score.cmd_compare(SimpleNamespace(a=str(a), b=str(a), margin=0.03)) == 1
