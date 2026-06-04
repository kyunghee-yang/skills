#!/usr/bin/env python3
"""AutoResearch 루프 원장(ledger) 관리.

이터레이션마다 무엇을 시도했고 채택/폐기했는지를 .autoresearch/ledger.json에 기록한다.
세션이 바뀌어도 이어서 작업하고, 폐기한 가설을 중복 시도하지 않기 위한 영속 상태.

사용법:
  python3 loop_ledger.py status                      # 진행 요약
  python3 loop_ledger.py next                         # 다음 이터레이션 번호
  python3 loop_ledger.py start --target T --hypothesis H [--research R ...]
  python3 loop_ledger.py record --decision adopted|discarded [옵션...]
  python3 loop_ledger.py discard --hypothesis H --reason WHY

원장 경로는 git 루트(없으면 cwd)의 .autoresearch/ledger.json. --ledger로 직접 지정 가능.
"""
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def git_root() -> Path:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        if out:
            return Path(out)
    except Exception:
        pass
    return Path.cwd()


def git_branch() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return ""


def ledger_path(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    return git_root() / ".autoresearch" / "ledger.json"


def load(path: Path) -> dict:
    if path.exists():
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    return {
        "branch": git_branch(),
        "started_at": now_iso(),
        "iteration": 0,
        "iterations": [],
        "discarded_hypotheses": [],
    }


def save(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def cmd_status(data: dict) -> None:
    its = data.get("iterations", [])
    adopted = [i for i in its if i.get("decision") == "adopted"]
    discarded = [i for i in its if i.get("decision") == "discarded"]
    print(f"브랜치: {data.get('branch') or '(unknown)'}")
    print(f"시작: {data.get('started_at')}")
    print(f"완료 이터레이션: {len(its)} (채택 {len(adopted)}, 폐기 {len(discarded)})")
    print(f"다음 번호: {data.get('iteration', 0) + 1}")
    if its:
        last = its[-1]
        print(f"마지막: #{last.get('n')} [{last.get('decision')}] {last.get('target')}")
        print(f"        가설: {last.get('hypothesis')}")
    dh = data.get("discarded_hypotheses", [])
    if dh:
        print(f"폐기 가설 {len(dh)}건 (중복 방지용):")
        for h in dh[-10:]:
            print(f"  - {h}")


def cmd_next(data: dict) -> None:
    print(data.get("iteration", 0) + 1)


def cmd_start(data: dict, args) -> int:
    n = data.get("iteration", 0) + 1
    entry = {
        "n": n,
        "target": args.target,
        "hypothesis": args.hypothesis,
        "research": args.research or [],
        "ab": None,
        "decision": "in_progress",
        "verify": None,
        "commit": None,
        "ts": now_iso(),
    }
    data["iterations"].append(entry)
    data["iteration"] = n
    if not data.get("branch"):
        data["branch"] = git_branch()
    print(f"이터레이션 #{n} 시작: {args.target}")
    return 0


def cmd_record(data: dict, args) -> int:
    its = data.get("iterations", [])
    if not its:
        print("기록할 이터레이션이 없습니다. 먼저 start 하세요.", file=sys.stderr)
        return 1
    entry = its[-1]
    entry["decision"] = args.decision
    if args.ab:
        try:
            entry["ab"] = json.loads(args.ab)
        except json.JSONDecodeError:
            entry["ab"] = {"note": args.ab}
    if args.verify:
        entry["verify"] = args.verify
    if args.commit:
        entry["commit"] = args.commit
    entry["ts"] = now_iso()
    if args.decision == "discarded" and entry.get("hypothesis"):
        reason = f"{entry['hypothesis']} → 폐기"
        if args.reason:
            reason += f" ({args.reason})"
        data.setdefault("discarded_hypotheses", []).append(reason)
    print(f"이터레이션 #{entry['n']} 기록: {args.decision}")
    return 0


def cmd_discard(data: dict, args) -> int:
    text = args.hypothesis
    if args.reason:
        text += f" ({args.reason})"
    data.setdefault("discarded_hypotheses", []).append(text)
    print("폐기 가설 기록 완료")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="AutoResearch 루프 원장 관리")
    p.add_argument("--ledger", help="원장 파일 경로 직접 지정")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("status")
    sub.add_parser("next")

    sp = sub.add_parser("start")
    sp.add_argument("--target", required=True)
    sp.add_argument("--hypothesis", required=True)
    sp.add_argument("--research", action="append")

    rp = sub.add_parser("record")
    rp.add_argument("--decision", required=True, choices=["adopted", "discarded"])
    rp.add_argument("--ab", help='JSON 문자열, 예: {"metric":"오탐률","a":0.12,"b":0.04,"winner":"B"}')
    rp.add_argument("--verify")
    rp.add_argument("--commit")
    rp.add_argument("--reason")

    dp = sub.add_parser("discard")
    dp.add_argument("--hypothesis", required=True)
    dp.add_argument("--reason")

    args = p.parse_args()
    path = ledger_path(args.ledger)
    data = load(path)

    if args.cmd == "status":
        cmd_status(data)
        return 0
    if args.cmd == "next":
        cmd_next(data)
        return 0

    rc = 0
    if args.cmd == "start":
        rc = cmd_start(data, args)
    elif args.cmd == "record":
        rc = cmd_record(data, args)
    elif args.cmd == "discard":
        rc = cmd_discard(data, args)

    save(path, data)
    return rc


if __name__ == "__main__":
    sys.exit(main())
