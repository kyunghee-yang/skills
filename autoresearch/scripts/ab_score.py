#!/usr/bin/env python3
"""A/B 후보 점수 집계 및 승자 판정.

각 후보의 지표를 JSON으로 받아 가중 정규화 점수를 계산하고, 노이즈 임계값을 넘는 차이가
있을 때만 승자를 선언한다(아니면 동률 → 더 단순한 쪽 권장).

지표 JSON 형식:
{
  "name": "A",
  "metrics": {
    "pass_rate":   {"value": 0.94, "weight": 2.0, "higher_is_better": true},
    "time_ms":     {"value": 1200, "weight": 1.0, "higher_is_better": false},
    "tokens":      {"value": 85000, "weight": 0.5, "higher_is_better": false,
                    "stddev": 4000}
  }
}

사용법:
  python3 ab_score.py compare a.json b.json [--margin 0.03]
  python3 ab_score.py template            # 빈 템플릿 출력

점수화: 각 지표를 A·B 두 값으로 [0,1] 정규화(상대 비교) 후, higher_is_better가 false면 반전.
가중 평균이 최종 점수. 두 점수 차이가 margin 미만이거나, 우위 지표가 자신의 stddev 안에 있으면
'동률'로 판정.
"""
import argparse
import json
import sys


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize_pair(a: float, b: float, higher_is_better: bool) -> tuple[float, float]:
    """A·B 두 값을 상대 정규화. 더 좋은 쪽이 1.0에 가깝도록."""
    lo, hi = min(a, b), max(a, b)
    span = hi - lo
    if span == 0:
        return 0.5, 0.5
    na = (a - lo) / span  # 0..1, 값이 클수록 1
    nb = (b - lo) / span
    if not higher_is_better:
        na, nb = 1 - na, 1 - nb
    return na, nb


def score(a: dict, b: dict) -> dict:
    ma, mb = a.get("metrics", {}), b.get("metrics", {})
    keys = [k for k in ma if k in mb]
    if not keys:
        raise SystemExit("두 후보에 공통 지표가 없습니다.")

    total_w = 0.0
    sa = sb = 0.0
    rows = []
    any_real_edge = False
    for k in keys:
        da, db = ma[k], mb[k]
        w = float(da.get("weight", db.get("weight", 1.0)))
        hib = bool(da.get("higher_is_better", True))
        va, vb = float(da["value"]), float(db["value"])
        na, nb = normalize_pair(va, vb, hib)
        sa += na * w
        sb += nb * w
        total_w += w

        # 노이즈 판정: 두 후보 중 명시된 stddev 사용
        sd = max(float(da.get("stddev", 0)), float(db.get("stddev", 0)))
        diff = abs(va - vb)
        within_noise = sd > 0 and diff <= sd
        if not within_noise:
            any_real_edge = True
        better = "A" if na > nb else ("B" if nb > na else "=")
        rows.append({
            "metric": k, "a": va, "b": vb, "weight": w,
            "higher_is_better": hib, "better": better,
            "within_noise": within_noise,
        })

    if total_w == 0:
        # 모든 가중치가 0이면 비교 불가 → 동률(0.5/0.5)로 처리(0 나눗셈 방지).
        sa = sb = 0.5
        any_real_edge = False
    else:
        sa /= total_w
        sb /= total_w
    return {"score_a": round(sa, 4), "score_b": round(sb, 4),
            "rows": rows, "any_real_edge": any_real_edge}


def decide(result: dict, margin: float) -> str:
    sa, sb = result["score_a"], result["score_b"]
    if abs(sa - sb) < margin or not result["any_real_edge"]:
        return "TIE"
    return "A" if sa > sb else "B"


def cmd_compare(args) -> int:
    a, b = load(args.a), load(args.b)
    res = score(a, b)
    winner = decide(res, args.margin)
    na, nb = a.get("name", "A"), b.get("name", "B")
    print(f"=== A/B 비교: {na} vs {nb} ===")
    print(f"{'지표':<16}{na:>12}{nb:>12}  가중  우위  노이즈")
    for r in res["rows"]:
        print(f"{r['metric']:<16}{r['a']:>12}{r['b']:>12}"
              f"{r['weight']:>6}  {r['better']:^4}  {'예' if r['within_noise'] else '-'}")
    print(f"\n종합 점수: {na}={res['score_a']}  {nb}={res['score_b']}  (margin={args.margin})")
    if winner == "TIE":
        print("판정: 동률 → 더 단순/안전한 쪽 채택 권장 (보통 A 유지)")
    else:
        name = na if winner == "A" else nb
        print(f"판정: {winner} ({name}) 우세 → 채택 대상")
    # 스크립트 게이트용 종료 코드: B 우세면 0(채택), A 우세/동률이면 1(유지).
    # 예) `ab_score.py compare a.json b.json && <채택·커밋>`
    return 0 if winner == "B" else 1


def cmd_template(_args) -> int:
    tmpl = {
        "name": "A",
        "metrics": {
            "pass_rate": {"value": 0.0, "weight": 2.0, "higher_is_better": True},
            "time_ms": {"value": 0.0, "weight": 1.0, "higher_is_better": False, "stddev": 0.0},
            "tokens": {"value": 0.0, "weight": 0.5, "higher_is_better": False, "stddev": 0.0},
        },
    }
    print(json.dumps(tmpl, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="A/B 후보 점수 집계")
    sub = p.add_subparsers(dest="cmd", required=True)
    cp = sub.add_parser("compare")
    cp.add_argument("a")
    cp.add_argument("b")
    cp.add_argument("--margin", type=float, default=0.03,
                    help="이 미만의 점수차는 동률 (기본 0.03)")
    sub.add_parser("template")
    args = p.parse_args()
    if args.cmd == "compare":
        return cmd_compare(args)
    return cmd_template(args)


if __name__ == "__main__":
    sys.exit(main())
